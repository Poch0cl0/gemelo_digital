import http.client
import json
import threading
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from motor.agent_tools import (
    TOOL_FUNCTIONS, analisis_exploratorio, contexto_general, explicabilidad,
    listar_objetivos, narrativa_langflow, resumen_objetivo, seleccion_modelo,
)
from motor.ml import model_status
from motor.ui import make_server


class AgentToolTests(unittest.TestCase):
    @unittest.skipUnless(model_status()['available'], 'Train artifacts first')
    def test_tools_return_compact_json(self):
        needs_target = {'resumen_objetivo', 'pruebas_estadisticas', 'validacion_cruzada',
                        'seleccion_modelo', 'hiperparametros', 'explicabilidad'}
        for fn in TOOL_FUNCTIONS:
            with self.subTest(tool=fn.__name__):
                if fn.__name__ in needs_target:
                    payload = fn('visit_minutes')
                elif fn.__name__ == 'analisis_exploratorio':
                    payload = fn('descriptives')
                else:
                    payload = fn()
                data = json.loads(payload)
                self.assertIsInstance(data, (dict, list))
                self.assertLess(len(payload), 8000, fn.__name__)

    @unittest.skipUnless(model_status()['available'], 'Train artifacts first')
    def test_selection_contains_justification(self):
        data = json.loads(seleccion_modelo('hospitalization'))
        self.assertIn('justification', data)
        self.assertTrue(data['justification'])

    def test_invalid_objective(self):
        with self.assertRaises(ValueError):
            resumen_objetivo('objetivo_inexistente')

    def test_invalid_eda_block(self):
        with self.assertRaises(ValueError):
            analisis_exploratorio('bloque_inexistente')


class AgentGraphTests(unittest.TestCase):
    def test_message_text_from_content_blocks(self):
        from motor.agent import _message_text
        from langchain_core.messages import AIMessage

        msg = AIMessage(content=[{'type': 'text', 'text': 'Respuesta en bloques.'}])
        self.assertEqual(_message_text(msg), 'Respuesta en bloques.')

    def test_answer_with_mocked_graph(self):
        from langchain_core.messages import AIMessage, ToolMessage

        tool_call = {'name': 'listar_objetivos', 'args': {}, 'id': 'call_1', 'type': 'tool_call'}
        first = AIMessage(content='', tool_calls=[tool_call])
        second = AIMessage(content='Hay tres objetivos predictivos en el informe.')

        class FakeGraph:
            def invoke(self, state):
                return {'messages': state['messages'] + [first, ToolMessage(content='[]', tool_call_id='call_1'), second]}

        with patch('motor.agent._graph', return_value=FakeGraph()):
            from motor.agent import answer, reset_graph
            reset_graph()
            result = answer('¿Cuántos objetivos hay?', [])
            self.assertIn('tres objetivos', result['answer'].lower())
            self.assertIn('listar_objetivos', result['tools_used'])

    def test_empty_question_raises(self):
        from motor.agent import answer
        with self.assertRaises(ValueError):
            answer('   ')


class LangFlowClientTests(unittest.TestCase):
    def test_run_flow_extracts_message_text(self):
        from motor.langflow_client import run_flow

        payload = json.dumps({
            'outputs': [{
                'outputs': [{
                    'results': {
                        'message': {'text': 'Narrativa de prueba generada por LangFlow.'},
                    },
                }],
            }],
        }).encode('utf-8')
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = payload
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch('motor.langflow_client.LANGFLOW_FLOW_ID', 'flow-test'), \
             patch('urllib.request.urlopen', return_value=mock_resp):
            text = run_flow('hola')
        self.assertEqual(text, 'Narrativa de prueba generada por LangFlow.')

    def test_run_flow_url_error(self):
        from motor.langflow_client import run_flow

        with patch('motor.langflow_client.LANGFLOW_FLOW_ID', 'flow-test'), \
             patch('urllib.request.urlopen', side_effect=urllib.error.URLError('refused')):
            with self.assertRaises(RuntimeError) as ctx:
                run_flow('hola')
        self.assertIn('LangFlow no responde', str(ctx.exception))

    @unittest.skipUnless(model_status()['available'], 'Train artifacts first')
    def test_narrativa_langflow_returns_error_on_failure(self):
        with patch('motor.langflow_client.run_flow', side_effect=RuntimeError('LangFlow caído')):
            data = json.loads(narrativa_langflow('visit_minutes', 'pedagógico'))
        self.assertEqual(data['objetivo'], 'visit_minutes')
        self.assertIn('error', data)

    def test_langflow_tool_registered_when_configured(self):
        with patch('motor.langflow_client.langflow_configured', return_value=True):
            import importlib
            import motor.agent as agent_mod
            importlib.reload(agent_mod)
            names = [t.name for t in agent_mod.HERRAMIENTAS]
            self.assertIn('narrativa_langflow', names)
        import importlib
        import motor.agent as agent_mod
        importlib.reload(agent_mod)

    def test_langflow_tool_not_registered_without_config(self):
        with patch('motor.langflow_client.langflow_configured', return_value=False):
            import importlib
            import motor.agent as agent_mod
            importlib.reload(agent_mod)
            names = [t.name for t in agent_mod.HERRAMIENTAS]
            self.assertNotIn('narrativa_langflow', names)
        import importlib
        import motor.agent as agent_mod
        importlib.reload(agent_mod)


class AgentRouteTests(unittest.TestCase):
    def test_agent_page_routes(self):
        server = make_server(0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=30)
            for path in ['/asistente', '/asistente.js']:
                conn.request('GET', path)
                response = conn.getresponse()
                response.read()
                self.assertEqual(response.status, 200, path)
            conn.request('GET', '/api/agent/status')
            response = conn.getresponse()
            data = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertIn('available', data)
            self.assertIn('langflow', data)
            conn.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == '__main__':
    unittest.main()
