"""Local browser interface. Run with python -m motor.ui."""
import argparse
from dataclasses import asdict
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
import webbrowser
from urllib.parse import urlsplit

from .model import Config, Policy, generate, simulate

STATIC = Path(__file__).with_name('web')
PAGE_ROUTES = ['/', '/operations', '/simulation', '/simulator', '/ml', '/asistente']
ASSETS = {'/scientific-export.js': ('scientific-export.js', 'text/javascript'),
          '/scientific-export.css': ('scientific-export.css', 'text/css'),
          '/export-preview': ('export-preview.html', 'text/html'),
          '/export-preview.js': ('export-preview.js', 'text/javascript'),
          '/': ('operations.html', 'text/html'), '/operations': ('operations.html', 'text/html'),
          '/simulation': ('simulation.html', 'text/html'), '/simulator': ('index.html', 'text/html'),
          '/ml': ('ml.html', 'text/html'), '/asistente': ('asistente.html', 'text/html'),
          '/simulation-shell.js': ('simulation-shell.js', 'text/javascript'),
          '/app.js': ('app.js', 'text/javascript'),
          '/ml-ui.js': ('ml-ui.js', 'text/javascript'),
          '/ml-lab.js': ('ml-lab.js', 'text/javascript'),
          '/ml-charts.js': ('ml-charts.js', 'text/javascript'),
          '/asistente.js': ('asistente.js', 'text/javascript'),
          '/twin-ui.js': ('twin-ui.js', 'text/javascript'),
          '/operations.js': ('operations.js', 'text/javascript'),
          '/operations.css': ('operations.css', 'text/css'),
          '/cohorte-ejemplo.json': ('cohorte-ejemplo.json', 'application/json'),
          '/style.css': ('style.css', 'text/css'),
          '/hospital3d.js': ('hospital3d.js', 'text/javascript')}


def not_found_message(route, api=False):
    """JSON body for unknown routes; page routes include a restart hint."""
    payload = {'error': 'Ruta no encontrada.'}
    if not api:
        payload['hint'] = (
            f'La ruta {route} no está registrada en este proceso. '
            'Si el código se actualizó recientemente, reinicia el servidor con: python -m motor.ui'
        )
        payload['pages'] = PAGE_ROUTES
    return payload


def _source_mtimes():
    root = Path(__file__).parent
    return {path: path.stat().st_mtime_ns for path in root.rglob('*.py')}


def _watch_and_reload(interval=1.0):
    baseline = _source_mtimes()
    while True:
        time.sleep(interval)
        current = _source_mtimes()
        if baseline != current:
            print('Código modificado; reiniciando servidor...', flush=True)
            os.execv(sys.executable, [sys.executable, '-m', 'motor.ui', *sys.argv[1:]])


def run_simulation(payload):
    if not isinstance(payload, dict):
        raise ValueError('La solicitud debe ser un objeto JSON.')
    config = payload.get('config', {})
    policy = payload.get('policy', {})
    if not isinstance(config, dict) or not isinstance(policy, dict):
        raise ValueError('Configuración y política deben ser objetos.')
    config = dict(config)
    if isinstance(config.get('priority_weights'), list):
        config['priority_weights'] = tuple(config['priority_weights'])
    try:
        c, p = Config(**config), Policy(**policy)
        c.validate()
        p.validate()
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Parámetros inválidos: {exc}') from exc
    seed = payload.get('seed', 1000)
    compare = payload.get('compare', False)
    if type(seed) is not int or not 0 <= seed <= 2**32-1:
        raise ValueError('La semilla debe ser un entero entre 0 y 4294967295.')
    if type(compare) is not bool:
        raise ValueError('La opción comparar debe ser booleana.')
    # Bound interactive requests; the research API remains unrestricted.
    if (c.horizon > 1440 or c.horizon / c.dt > 6000 or c.demand > 5 or
            any(getattr(c, key) > 200 for key in ('doctors','nurses','beds','icu','ventilators'))):
        raise ValueError('Límite interactivo: 1440 min, 6000 pasos, demanda ×5 y 200 unidades por recurso.')
    if 'cohort' in payload:
        from .cohort import parse_cohort
        patients, population = parse_cohort(payload['cohort'], c)
    else:
        patients = generate(c, seed)
        population = dict(mode='generated',kind='synthetic',records=len(patients))
    result = simulate(c, p, seed, patients, trace=True)
    comparisons = []
    if compare:
        for candidate in [Policy('fifo'), Policy('priority'),
                          Policy('tuned', p.reserve, p.release),
                          Policy('aging', p.reserve, p.release, p.aging_interval)]:
            metrics = (result['metrics'] if candidate == p else
                       simulate(c, candidate, seed, patients)['metrics'])
            comparisons.append(dict(policy=asdict(candidate), metrics=metrics))
    return dict(config=asdict(c), policy=asdict(p), seed=seed,
                result=result, comparisons=comparisons, population=population)


class Handler(BaseHTTPRequestHandler):
    def send(self, status, data, content_type='application/json; charset=utf-8'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; object-src 'none'; frame-ancestors 'self'")
        self.end_headers()
        self.wfile.write(data)

    def json_response(self, status, data):
        self.send(status, json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8'))

    def do_GET(self):
        route = urlsplit(self.path).path
        if self.path == '/api/defaults':
            self.json_response(200, dict(config=asdict(Config()), policy=asdict(Policy())))
        elif self.path == '/api/ml/status':
            from .ml import model_status
            self.json_response(200, model_status())
        elif self.path == '/api/ml/report':
            from .ml import model_status
            status = model_status()
            if not status.get('available'):
                return self.json_response(404, {'error': status.get('message', 'Informe no disponible.')})
            self.json_response(200, status['report'])
        elif self.path == '/api/agent/status':
            try:
                from .agent import agent_status
                self.json_response(200, agent_status())
            except ImportError:
                self.json_response(200, {'available': False, 'dependencies_ok': False,
                                           'message': 'Instala las dependencias: python -m pip install -r requirements-agent.txt'})
        elif self.path == '/api/twin/status':
            from .twin_store import status
            self.json_response(200, status(self.server.twin_db))
        elif self.path.startswith('/api/ops/'):
            from .operations import SPECS, dashboard, get_hospital, list_records
            pieces=urlsplit(self.path).path.strip('/').split('/')
            if len(pieces)==3 and pieces[2]=='dashboard':self.json_response(200,dashboard(self.server.twin_db))
            elif len(pieces)==3 and pieces[2]=='hospital':self.json_response(200,get_hospital(self.server.twin_db))
            elif len(pieces)==3 and (pieces[2] in SPECS or pieces[2]=='assignments'):
                query=urlsplit(self.path).query
                self.json_response(200,list_records(pieces[2],self.server.twin_db,'archived=1' in query))
            else:self.json_response(404,{'error':'Ruta de operaciones no encontrada.'})
        elif route in ASSETS:
            name, mime = ASSETS[route]
            self.send(200, (STATIC / name).read_bytes(), mime+'; charset=utf-8')
        else:
            self.json_response(404, not_found_message(route, api=route.startswith('/api/')))

    def do_POST(self):
        route = urlsplit(self.path).path
        if route not in ('/api/simulate', '/api/ml/predict', '/api/agent/chat', '/api/twin/events') and not route.startswith('/api/ops/'):
            return self.json_response(404, not_found_message(route, api=True))
        origin = self.headers.get('Origin')
        allowed = f'http://127.0.0.1:{self.server.server_port}'
        if origin and origin != allowed:
            return self.json_response(403, {'error': 'Origen no permitido.'})
        if self.command!='DELETE' and self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.json_response(415, {'error': 'Se requiere application/json.'})
        try:
            route=urlsplit(self.path).path
            if self.command=='DELETE':payload={}
            else:
                length = int(self.headers.get('Content-Length', '0'))
                max_length = 262144 if route == '/api/simulate' else 65536 if route == '/api/agent/chat' else 16384
                if not 0 < length <= max_length:raise ValueError('Tamaño de solicitud inválido.')
                payload = json.loads(self.rfile.read(length))
            with self.server.simulation_lock:
                if route == '/api/ml/predict':
                    from .ml import predict_profile
                    result = predict_profile(payload)
                elif route == '/api/agent/chat':
                    from .agent import answer
                    if not isinstance(payload, dict) or 'question' not in payload:
                        raise ValueError('Se requiere el campo question.')
                    history = payload.get('history', [])
                    if not isinstance(history, list):
                        raise ValueError('history debe ser una lista.')
                    result = answer(str(payload['question']), history[-6:])
                elif route == '/api/twin/events':
                    from .twin_store import ingest
                    if not isinstance(payload, dict) or set(payload) != {'source','event'}:
                        raise ValueError('Se requiere el objeto source y un event.')
                    result = ingest(payload['event'],payload['source'],self.server.twin_db)
                elif route == '/api/simulate':
                    result = run_simulation(payload)
                else:
                    from .operations import archive_record,create_assignment,release_assignment,restore_record,save_record,update_hospital
                    parts=route.strip('/').split('/')
                    if len(parts) not in (3,4,5) or parts[:2]!=['api','ops']:raise ValueError('Ruta de operaciones inválida.')
                    entity=parts[2]
                    if len(parts)==5 and entity=='assignments' and parts[4]=='release' and self.command=='POST':
                        result=release_assignment(int(parts[3]),self.server.twin_db)
                    elif len(parts)==5 and parts[4]=='restore' and self.command=='POST':
                        result=restore_record(entity,int(parts[3]),self.server.twin_db)
                    elif self.command=='POST' and len(parts)==3:
                        if entity=='hospital':result=update_hospital(payload,self.server.twin_db)
                        elif entity=='assignments':result=create_assignment(payload,self.server.twin_db)
                        else:result=save_record(entity,payload,path=self.server.twin_db)
                    elif self.command=='PUT' and len(parts)==4:
                        record_id=int(parts[3])
                        if entity=='hospital':result=update_hospital(payload,self.server.twin_db)
                        else:result=save_record(entity,payload,record_id,self.server.twin_db)
                    elif self.command=='DELETE' and len(parts)==4:
                        result=archive_record(entity,int(parts[3]),self.server.twin_db)
                    else:raise ValueError('Método no admitido para esta ruta.')
            self.json_response(200, result)
        except (ValueError, TypeError, UnicodeError) as exc:
            self.json_response(400, {'error': str(exc)})
        except LookupError as exc:
            self.json_response(404, {'error': str(exc)})
        except sqlite3.IntegrityError as exc:
            self.json_response(409, {'error': 'El cambio infringe una relación o valor único; revisa códigos y asignaciones.'})
        except ImportError:
            hint = 'requirements-agent.txt' if route == '/api/agent/chat' else 'requirements-ml.txt'
            self.json_response(503, {'error': f'Instala las dependencias de {hint}.'})
        except sqlite3.Error:
            self.json_response(500, {'error': 'No se pudo persistir el evento del gemelo.'})
        except Exception as exc:
            if route == '/api/agent/chat':
                self.json_response(502, {'error': f'Error del asistente: {exc}'})
            else:
                raise

    def do_PUT(self):self.do_POST()
    def do_DELETE(self):self.do_POST()


def make_server(port=8765, twin_db=None):
    from .database import DEFAULT_DB, connect
    from .demo_seed import seed_demo
    database_path = Path(twin_db) if twin_db is not None else DEFAULT_DB
    connect(database_path).close()
    seed_demo(database_path)
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.simulation_lock = threading.Lock()
    server.twin_db = database_path
    return server


def main():
    parser = argparse.ArgumentParser(description='Interfaz local del motor ABS–SD')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--reload', action='store_true',
                        help='Reiniciar automáticamente si cambian los archivos .py de motor/')
    args = parser.parse_args()
    if args.reload:
        threading.Thread(target=_watch_and_reload, daemon=True).start()
    with make_server(args.port) as server:
        url = f'http://127.0.0.1:{server.server_port}'
        print(f'Motor ABS-SD: {url} (Ctrl+C para cerrar)', flush=True)
        print(f'Páginas: {", ".join(PAGE_ROUTES)}', flush=True)
        if args.reload:
            print('Recarga automática activada (--reload)', flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
