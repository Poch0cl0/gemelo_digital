"""LangGraph assistant over the CRISP-DM ML report (Gemini, Ollama or DeepSeek)."""
import os
from pathlib import Path
import urllib.error
import urllib.request
from typing import Annotated, TypedDict


def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    except ImportError:
        pass


_load_env()

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from .agent_tools import LANGFLOW_TOOLS, TOOL_FUNCTIONS
from .langflow_client import langflow_configured, langflow_reachable

HERRAMIENTAS = [
    StructuredTool.from_function(fn)
    for fn in TOOL_FUNCTIONS + (LANGFLOW_TOOLS if langflow_configured() else [])
]

SYSTEM_PROMPT = """Eres un asistente experto en el informe CRISP-DM del módulo de aprendizaje automático
del hospital digital ABS-SD, entrenado sobre NHAMCS 2022 (visitas de urgencias en EE. UU.).

Reglas:
- Responde SIEMPRE en español.
- Usa las herramientas para obtener cifras; nunca inventes números ni nombres de modelos.
- Cita la prueba estadística que respalda cada afirmación (bootstrap por hospital, Holm, Wilcoxon, DeLong, etc.).
- Recuerda que el uso es experimental: no sustituye el simulador ni decisiones clínicas.
- Si falta información en el informe, dilo explícitamente.
- Sé conciso pero preciso; usa listas cuando compares varios objetivos.
- Usa narrativa_langflow solo si el usuario pide redacción narrativa, pedagógica o un párrafo para el artículo;
  las cifras deben venir siempre de las demás herramientas."""

OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen2.5:7b')
OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')
DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
DEEPSEEK_BASE = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
MAX_HISTORY = 6
_MOCK_MODEL = None


def _provider():
    explicit = os.environ.get('AGENT_PROVIDER', '').strip().lower()
    if explicit in ('ollama', 'deepseek', 'gemini', 'mock'):
        return explicit
    if _gemini_configured():
        return 'gemini'
    if os.environ.get('DEEPSEEK_API_KEY'):
        return 'deepseek'
    return 'ollama'


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _ollama_reachable():
    try:
        req = urllib.request.Request(f'{OLLAMA_HOST.rstrip("/")}/api/tags', method='GET')
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _deepseek_configured():
    return bool(os.environ.get('DEEPSEEK_API_KEY', '').strip())


def _gemini_api_key():
    return (os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY') or '').strip()


def _gemini_configured():
    return bool(_gemini_api_key())


def set_mock_model(model):
    """Inject a fake chat model for demos/tests (must support bind_tools + invoke)."""
    global _MOCK_MODEL, _GRAPH
    _MOCK_MODEL = model
    _GRAPH = None


def _model():
    if _MOCK_MODEL is not None:
        return _MOCK_MODEL.bind_tools(HERRAMIENTAS)
    provider = _provider()
    if provider == 'gemini':
        from langchain_google_genai import ChatGoogleGenerativeAI
        key = _gemini_api_key()
        if not key:
            raise ValueError('Define GEMINI_API_KEY o GOOGLE_API_KEY para usar el proveedor gemini.')
        return ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            api_key=key,
            temperature=0.1,
        ).bind_tools(HERRAMIENTAS)
    if provider == 'deepseek':
        from langchain_openai import ChatOpenAI
        key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
        if not key:
            raise ValueError('Define DEEPSEEK_API_KEY para usar el proveedor deepseek.')
        return ChatOpenAI(
            model=DEEPSEEK_MODEL,
            api_key=key,
            base_url=DEEPSEEK_BASE,
            temperature=0.1,
        ).bind_tools(HERRAMIENTAS)
    if provider == 'mock':
        raise ValueError('Modo mock activo sin modelo inyectado; usa set_mock_model() o demo_agent --mock.')
    from langchain_ollama import ChatOllama
    return ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_HOST, temperature=0.1).bind_tools(HERRAMIENTAS)


def _call_model(state: AgentState):
    response = _model().invoke(state['messages'])
    return {'messages': [response]}


def _build_graph():
    graph = StateGraph(AgentState)
    graph.add_node('agente', _call_model)
    graph.add_node('herramientas', ToolNode(HERRAMIENTAS))
    graph.add_edge(START, 'agente')
    graph.add_conditional_edges('agente', tools_condition, {'tools': 'herramientas', END: END})
    graph.add_edge('herramientas', 'agente')
    return graph.compile()


_GRAPH = None


def _graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()
    return _GRAPH


def _history_to_messages(history):
    messages = []
    for turn in history[-MAX_HISTORY:]:
        if not isinstance(turn, dict):
            continue
        role, content = turn.get('role'), turn.get('content')
        if role == 'user' and content:
            messages.append(HumanMessage(content=str(content)))
        elif role == 'assistant' and content:
            messages.append(AIMessage(content=str(content)))
    return messages


def _extract_tools_used(messages):
    used = []
    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, 'tool_calls', None):
            for call in msg.tool_calls:
                name = call.get('name') if isinstance(call, dict) else getattr(call, 'name', None)
                if name:
                    used.append(name)
    return used


def _message_text(msg):
    """Normalize AIMessage content (Gemini 3+ may return content blocks instead of str)."""
    if not isinstance(msg, AIMessage):
        return ''
    text = getattr(msg, 'text', None)
    if isinstance(text, str) and text.strip():
        return text
    content = msg.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                piece = block.get('text') or block.get('content')
                if piece:
                    parts.append(str(piece))
        return ''.join(parts)
    return str(content) if content else ''


def answer(question, history=None):
    """Run the ReAct graph and return the assistant reply."""
    if not question or not str(question).strip():
        raise ValueError('La pregunta no puede estar vacía.')
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    messages.extend(_history_to_messages(history or []))
    messages.append(HumanMessage(content=str(question).strip()))
    result = _graph().invoke({'messages': messages})
    out_messages = result['messages']
    reply = ''
    for msg in reversed(out_messages):
        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, 'tool_calls', None):
            reply = _message_text(msg)
            break
    if not reply:
        for msg in reversed(out_messages):
            if isinstance(msg, AIMessage) and msg.content:
                reply = _message_text(msg)
                if reply:
                    break
    return {
        'answer': reply or 'No pude generar una respuesta.',
        'tools_used': _extract_tools_used(out_messages),
        'provider': _provider(),
    }


def _langflow_status():
    from .langflow_client import LANGFLOW_URL
    configured = langflow_configured()
    return {
        'configured': configured,
        'reachable': langflow_reachable() if configured else False,
        'url': LANGFLOW_URL,
    }


def agent_status():
    """Check dependencies, report availability and LLM backend connectivity."""
    provider = _provider()
    status = {
        'available': False,
        'provider': provider,
        'ollama_model': OLLAMA_MODEL,
        'ollama_host': OLLAMA_HOST,
        'gemini_model': GEMINI_MODEL,
        'deepseek_model': DEEPSEEK_MODEL,
        'report_available': False,
        'dependencies_ok': False,
        'llm_ok': False,
        'message': '',
        'langflow': _langflow_status(),
    }
    try:
        import langgraph  # noqa: F401
        status['dependencies_ok'] = True
        if provider == 'gemini':
            import langchain_google_genai  # noqa: F401
        elif provider == 'deepseek':
            import langchain_openai  # noqa: F401
        elif provider == 'ollama':
            import langchain_ollama  # noqa: F401
    except ImportError:
        extras = {'gemini': ' (langchain-google-genai)', 'deepseek': ' (langchain-openai)'}
        extra = extras.get(provider, '')
        status['message'] = f'Instala las dependencias: python -m pip install -r requirements-agent.txt{extra}'
        return status
    from .ml import model_status as ml_status
    ml = ml_status()
    status['report_available'] = ml.get('available', False)
    if not status['report_available']:
        status['message'] = ml.get('message', 'Ejecuta python -m motor.train_ml para generar el informe.')
        return status
    if provider == 'mock':
        status['llm_ok'] = True
        status['available'] = True
        status['message'] = 'Asistente en modo simulación (mock).'
        status['trained_utc'] = ml.get('report', {}).get('trained_utc')
        return status
    if provider == 'gemini':
        status['llm_ok'] = _gemini_configured()
        if not status['llm_ok']:
            status['message'] = (
                'Define GEMINI_API_KEY con tu clave de https://aistudio.google.com/apikey '
                'o usa AGENT_PROVIDER=ollama para Ollama local.'
            )
            return status
        status['available'] = True
        status['message'] = f'Asistente listo (Gemini · {GEMINI_MODEL}).'
        status['trained_utc'] = ml.get('report', {}).get('trained_utc')
        return status
    if provider == 'deepseek':
        status['llm_ok'] = _deepseek_configured()
        if not status['llm_ok']:
            status['message'] = (
                'Define la variable de entorno DEEPSEEK_API_KEY con tu clave de https://platform.deepseek.com '
                'o usa AGENT_PROVIDER=gemini / ollama.'
            )
            return status
        status['available'] = True
        status['message'] = f'Asistente listo (DeepSeek · {DEEPSEEK_MODEL}).'
        status['trained_utc'] = ml.get('report', {}).get('trained_utc')
        return status
    status['llm_ok'] = _ollama_reachable()
    if not status['llm_ok']:
        status['message'] = (
            f'Ollama no responde en {OLLAMA_HOST}. Instala Ollama, ejecuta "ollama pull {OLLAMA_MODEL}", '
            'o define GEMINI_API_KEY para usar la API de Gemini.'
        )
        return status
    status['available'] = True
    status['message'] = f'Asistente listo (Ollama · {OLLAMA_MODEL}).'
    status['trained_utc'] = ml.get('report', {}).get('trained_utc')
    return status


def reset_graph():
    """Clear cached graph and mock model (for tests)."""
    global _GRAPH, _MOCK_MODEL
    _GRAPH = None
    _MOCK_MODEL = None
