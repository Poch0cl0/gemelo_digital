"""Demo del asistente LangGraph: simulación local o consulta real con Gemini/DeepSeek.

Ejemplos:
  python -m motor.demo_agent --mock
  python -m motor.demo_agent --gemini
  python -m motor.demo_agent --deepseek
"""
import argparse
import json
import os
import sys

from langchain_core.messages import AIMessage, ToolMessage


def _mock_model_for(question: str):
    """Simula un LLM que primero llama herramientas y luego responde con datos del informe."""
    from motor.agent_tools import listar_objetivos, seleccion_modelo

    q = question.lower()
    if 'ingreso' in q or 'hospital' in q or 'admithos' in q:
        tool, args, target = 'seleccion_modelo', {'objetivo': 'hospitalization'}, 'hospitalization'
    elif 'espera' in q or 'wait' in q:
        tool, args, target = 'seleccion_modelo', {'objetivo': 'wait_minutes'}, 'wait_minutes'
    elif 'estancia' in q or 'lov' in q:
        tool, args, target = 'seleccion_modelo', {'objetivo': 'visit_minutes'}, 'visit_minutes'
    else:
        tool, args, target = 'listar_objetivos', {}, None

    class MockBound:
        def __init__(self, parent):
            self._parent = parent

        def invoke(self, messages):
            if self._parent._turn == 0:
                self._parent._turn = 1
                return AIMessage(content='', tool_calls=[{
                    'name': tool, 'args': args, 'id': 'demo_call_1', 'type': 'tool_call',
                }])
            if target:
                data = json.loads(seleccion_modelo(target))
                text = (
                    f"Según el informe CRISP-DM, para **{target}** se eligió **{data.get('selected')}**. "
                    f"Justificación: {data.get('justification', '')}"
                )
            else:
                data = json.loads(listar_objetivos())
                text = 'Objetivos en el informe:\n' + '\n'.join(
                    f"- {row['label']}: modelo {row['modelo']} ({row['metrica']} prueba = {row['test']})"
                    for row in data
                )
            return AIMessage(content=text)

    class MockModel:
        def __init__(self):
            self._turn = 0

        def bind_tools(self, _tools):
            return MockBound(self)

    return MockModel()


def _print_step(label, text):
    print(f'\n--- {label} ---')
    print(text)


def run_demo(question, mode):
    from motor.agent import agent_status, answer, reset_graph, set_mock_model
    from motor.ml import model_status

    ml = model_status()
    if not ml.get('available'):
        print('ERROR:', ml.get('message', 'Informe no disponible. Ejecuta python -m motor.train_ml.'))
        return 1

    reset_graph()
    if mode == 'mock':
        os.environ['AGENT_PROVIDER'] = 'mock'
        set_mock_model(_mock_model_for(question))
        _print_step('Modo', 'Simulación LangGraph (sin API externa)')
    elif mode == 'gemini':
        os.environ['AGENT_PROVIDER'] = 'gemini'
        key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if not key:
            print('ERROR: Define GEMINI_API_KEY (https://aistudio.google.com/apikey)')
            return 1
        _print_step('Modo', f'Gemini API · modelo {os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")}')
    elif mode == 'deepseek':
        os.environ['AGENT_PROVIDER'] = 'deepseek'
        if not os.environ.get('DEEPSEEK_API_KEY'):
            print('ERROR: Define DEEPSEEK_API_KEY (https://platform.deepseek.com/api_keys)')
            return 1
        _print_step('Modo', f'DeepSeek API · modelo {os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")}')
    else:
        from motor.agent import _provider as detect_provider
        provider = detect_provider()
        os.environ.setdefault('AGENT_PROVIDER', provider)
        labels = {
            'gemini': f'Gemini API · modelo {os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")}',
            'deepseek': f'DeepSeek API · modelo {os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")}',
            'ollama': 'Ollama local',
        }
        _print_step('Modo', labels.get(provider, 'Ollama local'))

    status = agent_status()
    print('Estado:', status['message'])
    if not status.get('available') and mode != 'mock':
        return 1

    _print_step('Pregunta', question)
    print('Ejecutando grafo ReAct (agente -> herramientas -> agente)...', flush=True)

    try:
        result = answer(question)
    except Exception as exc:
        print('ERROR al invocar el grafo:', exc)
        return 1

    if result.get('tools_used'):
        _print_step('Herramientas LangGraph', ', '.join(result['tools_used']))
    _print_step('Respuesta', result['answer'])
    _print_step('Proveedor', result.get('provider', mode))
    print('\nDemo completada correctamente.')
    return 0


def main():
    parser = argparse.ArgumentParser(description='Demo del asistente LangGraph CRISP-DM')
    parser.add_argument('--mock', action='store_true', help='Simulación sin API externa')
    parser.add_argument('--gemini', action='store_true', help='Usar API Gemini (requiere GEMINI_API_KEY)')
    parser.add_argument('--deepseek', action='store_true', help='Usar API DeepSeek (requiere DEEPSEEK_API_KEY)')
    parser.add_argument('--question', '-q', default=(
        '¿Por qué se eligió el modelo para el ingreso hospitalario? Cita la justificación del informe.'
    ))
    args = parser.parse_args()
    mode = 'mock' if args.mock else 'gemini' if args.gemini else 'deepseek' if args.deepseek else 'ollama'
    sys.exit(run_demo(args.question, mode))


if __name__ == '__main__':
    main()
