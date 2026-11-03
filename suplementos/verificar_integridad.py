"""Comprueba las copias inventariadas; no escribe ni modifica resultados."""
from pathlib import Path
import hashlib,json

repo=Path(__file__).resolve().parents[1]
inventory=json.loads((repo/'suplementos/INVENTARIO_ENTREGA.json').read_text(encoding='utf-8'))
failed=[]
for record in inventory['files']:
    path=repo/record['path']
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
        failed.append(record['path'])
print(json.dumps({'checked':len(inventory['files']),'failed':failed},ensure_ascii=False))
raise SystemExit(bool(failed))
