"""HTTP client for optional LangFlow sub-agent flows (stdlib only)."""
import json
import os
import urllib.error
import urllib.request

LANGFLOW_URL = os.environ.get('LANGFLOW_URL', 'http://127.0.0.1:7860').rstrip('/')
LANGFLOW_FLOW_ID = os.environ.get('LANGFLOW_FLOW_ID', '').strip()
LANGFLOW_API_KEY = os.environ.get('LANGFLOW_API_KEY', '').strip()
LANGFLOW_TIMEOUT = int(os.environ.get('LANGFLOW_TIMEOUT', '60'))


def langflow_configured() -> bool:
    return bool(LANGFLOW_FLOW_ID)


def langflow_reachable() -> bool:
    if not langflow_configured():
        return False
    try:
        req = urllib.request.Request(f'{LANGFLOW_URL}/health', method='GET')
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def _extract_message_text(payload: dict) -> str:
    outputs = payload.get('outputs') or []
    if not outputs:
        raise RuntimeError('LangFlow devolvió una respuesta sin outputs.')
    inner = outputs[0].get('outputs') or []
    if not inner:
        raise RuntimeError('LangFlow devolvió una respuesta sin outputs internos.')
    results = inner[0].get('results') or {}
    message = results.get('message')
    if isinstance(message, dict):
        text = message.get('text') or message.get('message')
        if text:
            return str(text)
    if isinstance(message, str) and message.strip():
        return message
    text = results.get('text')
    if text:
        return str(text)
    raise RuntimeError('LangFlow devolvió una respuesta sin texto en results.message.text.')


def run_flow(message: str) -> str:
    """Run a LangFlow chat flow and return the assistant text."""
    if not langflow_configured():
        raise RuntimeError('LANGFLOW_FLOW_ID no está definido.')
    body = json.dumps({
        'input_value': message,
        'input_type': 'chat',
        'output_type': 'chat',
    }).encode('utf-8')
    url = f'{LANGFLOW_URL}/api/v1/run/{LANGFLOW_FLOW_ID}?stream=false'
    headers = {'Content-Type': 'application/json'}
    if LANGFLOW_API_KEY:
        headers['x-api-key'] = LANGFLOW_API_KEY
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=LANGFLOW_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'LangFlow HTTP {exc.code}: {detail[:500]}') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'LangFlow no responde en {LANGFLOW_URL}: {exc.reason}') from exc
    return _extract_message_text(payload)
