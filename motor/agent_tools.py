"""LangGraph tools: compact slices of the CRISP-DM report for the assistant."""
import json
import math
from typing import Any

from .ml import model_status

TARGETS = {
    'visit_minutes': 'Estancia total (LOV)',
    'wait_minutes': 'Espera hasta atención (WAITTIME)',
    'hospitalization': 'Ingreso hospitalario (ADMITHOS)',
}
EDA_BLOCKS = {'descriptives', 'targets', 'by_triage', 'correlation', 'partitions'}
METRIC_KEYS = {'visit_minutes': 'mae_minutes', 'wait_minutes': 'mae_minutes', 'hospitalization': 'brier'}


def _report():
    status = model_status()
    if not status.get('available'):
        raise ValueError(status.get('message', 'Informe no disponible. Ejecuta python -m motor.train_ml.'))
    return status['report']


def _target(report, objetivo):
    if objetivo not in TARGETS:
        raise ValueError(f'Objetivo desconocido: {objetivo}. Usa: {", ".join(TARGETS)}.')
    return report['targets'][objetivo]


def _round(value, digits=4):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {k: _round(v, digits) for k, v in value.items()}
    if isinstance(value, list):
        return [_round(v, digits) for v in value]
    return value


def _json(data: Any) -> str:
    return json.dumps(_round(data), ensure_ascii=False)


def _top_importance(block, n=8):
    if not isinstance(block, dict):
        return {}
    ranked = sorted(block.items(), key=lambda kv: kv[1].get('mean', 0) if isinstance(kv[1], dict) else kv[1], reverse=True)
    return {k: v for k, v in ranked[:n]}


def _pdp_summary(pdp):
    out = {}
    for feat, curve in (pdp or {}).items():
        grid, avg = curve.get('grid', []), curve.get('average', [])
        if not grid or not avg:
            continue
        out[feat] = {'min': avg[0], 'max': avg[-1], 'range': avg[-1] - avg[0], 'n_points': len(grid)}
    return out


def contexto_general() -> str:
    """Fuente de datos, particiones, modo de entrenamiento y limitaciones del estudio."""
    r = _report()
    return _json({
        'source': r.get('source'),
        'trained_utc': r.get('trained_utc'),
        'quick_mode': r.get('quick_mode'),
        'split': r.get('split'),
        'business': r.get('business'),
        'limits': r.get('limits'),
        'schema_version': r.get('schema_version'),
    })


def listar_objetivos() -> str:
    """Lista los tres objetivos predictivos con modelo elegido y métrica principal."""
    r = _report()
    items = []
    for key, label in TARGETS.items():
        t = r['targets'][key]
        mk = METRIC_KEYS[key]
        items.append({
            'objetivo': key,
            'label': label,
            'modelo': t.get('selected'),
            'modelo_key': t.get('selected_key'),
            'metrica': mk,
            'test': t.get('test_selected', {}).get(mk),
            'baseline': t.get('test_baseline', {}).get(mk),
        })
    return _json(items)


def resumen_objetivo(objetivo: str) -> str:
    """Métricas de prueba, referencia, mejora relativa y conteos para un objetivo."""
    r = _report()
    t = _target(r, objetivo)
    mk = METRIC_KEYS[objetivo]
    test_v = t['test_selected'].get(mk)
    base_v = t['test_baseline'].get(mk)
    improvement = None
    if test_v is not None and base_v:
        improvement = 1 - test_v / base_v
    return _json({
        'objetivo': objetivo,
        'label': TARGETS[objetivo],
        'modelo': t.get('selected'),
        'selected_key': t.get('selected_key'),
        'metrica': mk,
        'test_selected': t.get('test_selected'),
        'test_baseline': t.get('test_baseline'),
        'mejora_relativa': improvement,
        'counts': t.get('counts'),
        'eligible': t.get('eligible'),
    })


def pruebas_estadisticas(objetivo: str) -> str:
    """Bootstrap, Wilcoxon o DeLong, Hosmer-Lemeshow y calibración para un objetivo."""
    r = _report()
    t = _target(r, objetivo)
    stats = dict(t.get('statistics', {}))
    for key in ('como_leer', 'interpretacion'):
        stats.pop(key, None)
    return _json({'objetivo': objetivo, 'statistics': stats})


def validacion_cruzada(objetivo: str) -> str:
    """Medias, desviaciones y puntuaciones por pliegue de validación cruzada."""
    r = _report()
    t = _target(r, objetivo)
    cv = {}
    for name, block in t.get('cv', {}).items():
        if not isinstance(block, dict) or 'fold_scores' not in block:
            continue
        cv[name] = {'mean': block.get('mean'), 'std': block.get('std'), 'fold_scores': block.get('fold_scores'),
                    'oof': block.get('oof')}
    return _json({'objetivo': objetivo, 'cv': cv})


def seleccion_modelo(objetivo: str) -> str:
    """Ranking, comparaciones con Holm, Friedman, Nemenyi y justificación de selección."""
    r = _report()
    sel = _target(r, objetivo).get('selection', {})
    nemenyi = sel.get('nemenyi', {})
    if isinstance(nemenyi, dict) and 'pairs' in nemenyi:
        nemenyi = {**nemenyi, 'pairs': nemenyi['pairs'][:10]}
    return _json({
        'objetivo': objetivo,
        'selected': sel.get('selected'),
        'best_cv': sel.get('best_cv'),
        'method': sel.get('method'),
        'justification': sel.get('justification'),
        'ranking': sel.get('ranking'),
        'comparisons': sel.get('comparisons'),
        'friedman': sel.get('friedman'),
        'nemenyi': nemenyi,
    })


def hiperparametros(objetivo: str) -> str:
    """Mejores hiperparámetros, espacio de búsqueda y estabilidad entre pliegues."""
    r = _report()
    tuning = _target(r, objetivo).get('tuning', {})
    fold_params = tuning.get('fold_params', {})
    compact_fold = {k: v[:3] if isinstance(v, list) else v for k, v in fold_params.items()}
    return _json({
        'objetivo': objetivo,
        'best_params': tuning.get('best_params'),
        'final_model': tuning.get('final_model'),
        'search_space': tuning.get('search_space'),
        'fold_params_sample': compact_fold,
        'inner_cv': tuning.get('inner_cv'),
    })


def explicabilidad(objetivo: str) -> str:
    """Top de permutación, SHAP medio y resumen de dependencia parcial (sin beeswarm completo)."""
    r = _report()
    ex = _target(r, objetivo).get('explainability', {})
    shap = ex.get('shap', {})
    shap_compact = {k: shap.get(k) for k in ('available', 'scale', 'n', 'message') if k in shap}
    if 'mean_abs_shap' in shap:
        shap_compact['mean_abs_shap'] = _top_importance(shap['mean_abs_shap'], 8)
    diag = ex.get('diagnostics', {})
    diag_compact = {k: diag[k] for k in ('roc', 'pr', 'prevalence') if k in diag}
    if 'scatter' in diag:
        scatter = diag['scatter']
        diag_compact['scatter_n'] = len(scatter.get('observed', [])) if isinstance(scatter, dict) else len(scatter)
    return _json({
        'objetivo': objetivo,
        'permutation_top': _top_importance(ex.get('permutation', {}), 8),
        'shap': shap_compact,
        'pdp_summary': _pdp_summary(ex.get('pdp', {})),
        'diagnostics': diag_compact,
    })


def analisis_exploratorio(bloque: str) -> str:
    """Un bloque EDA: descriptives, targets, by_triage, correlation o partitions."""
    if bloque not in EDA_BLOCKS:
        raise ValueError(f'Bloque EDA desconocido: {bloque}. Usa: {", ".join(sorted(EDA_BLOCKS))}.')
    r = _report()
    block = r.get('eda', {}).get(bloque, {})
    compact = {k: v for k, v in block.items() if k in ('como_leer', 'interpretacion', 'kruskal_p')}
    data = block.get('data')
    if bloque == 'descriptives' and isinstance(data, dict):
        compact['data'] = {k: {'weighted': v.get('weighted')} for k, v in list(data.items())[:11]}
    elif bloque == 'correlation' and isinstance(data, dict):
        compact['data'] = data
    elif bloque == 'partitions' and isinstance(data, list):
        compact['data'] = data[:20]
    else:
        compact['data'] = data
    return _json({'bloque': bloque, **compact})


def narrativa_langflow(objetivo: str, enfoque: str) -> str:
    """Redacta una explicación narrativa (pedagógica, ejecutiva o para artículo) de un objetivo
    usando el flow de LangFlow. Úsala solo cuando el usuario pida redacción, no para obtener cifras."""
    from .langflow_client import run_flow

    try:
        contexto = {
            'resumen': json.loads(resumen_objetivo(objetivo)),
            'seleccion': json.loads(seleccion_modelo(objetivo)),
        }
        prompt = (
            f'Enfoque solicitado: {enfoque}\n'
            f'Objetivo: {objetivo} ({TARGETS.get(objetivo, objetivo)})\n'
            'Redacta en español una explicación narrativa usando SOLO las cifras del contexto JSON.\n'
            'Cita las pruebas estadísticas cuando compares modelos. No inventes números.\n'
            f'Contexto JSON:\n{json.dumps(contexto, ensure_ascii=False)}'
        )
        narrativa = run_flow(prompt)
        return _json({'objetivo': objetivo, 'enfoque': enfoque, 'narrativa': narrativa})
    except Exception as exc:
        return _json({'objetivo': objetivo, 'enfoque': enfoque, 'error': str(exc)})


TOOL_FUNCTIONS = [
    contexto_general,
    listar_objetivos,
    resumen_objetivo,
    pruebas_estadisticas,
    validacion_cruzada,
    seleccion_modelo,
    hiperparametros,
    explicabilidad,
    analisis_exploratorio,
]

LANGFLOW_TOOLS = [narrativa_langflow]
