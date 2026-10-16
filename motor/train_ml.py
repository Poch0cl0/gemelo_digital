"""CRISP-DM pipeline: EDA, nested CV, hyperparameter search, statistics, explainability."""
import argparse
import os
os.environ.setdefault('OMP_NUM_THREADS', '2')
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import urllib.request
import zipfile

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import (mean_absolute_error, mean_squared_error, roc_auc_score,
                              average_precision_score, brier_score_loss, log_loss)
from sklearn.model_selection import (GroupKFold, GroupShuffleSplit, RandomizedSearchCV,
                                      StratifiedGroupKFold)
from threadpoolctl import threadpool_limits

from .eda import run_eda
from .ml import ROOT, ARTIFACTS, FEATURES, clean_features
from .ml_explain import (diagnostic_plots, partial_dependence, permutation_importance,
                          shap_global, _sample_indices)
from .ml_models import (CANDIDATE_ORDER, PARSIMONY, describe_space, fit_baseline, make_estimator,
                         param_distributions, predict_estimator)
from .ml_stats import (brier_metric, calibration_curve, calibration_slope_intercept,
                        cluster_bootstrap_ci, cluster_bootstrap_diff, delong_auc,
                        friedman_test, holm_correction, hosmer_lemeshow, mae_metric,
                        nadeau_bengio_t, nemenyi_posthoc, wilcoxon_signed_errors)
from .ml_text import cv_text, test_text

URL = 'https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHAMCS/stata/ed2022-stata.zip'
DATA = ROOT / 'datos' / 'nhamcs' / 'ed2022-stata.zip'
SEED = 20260923
TARGETS = [('visit_minutes', 'LOV'), ('wait_minutes', 'WAITTIME'), ('hospitalization', 'ADMITHOS')]


def _json_params(params):
    return {k: (v.item() if hasattr(v, 'item') else v) for k, v in params.items()}


def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        val = float(obj)
        return None if not np.isfinite(val) else val
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    return obj


def download():
    DATA.parent.mkdir(parents=True, exist_ok=True)
    if not DATA.exists():
        request = urllib.request.Request(URL, headers={'User-Agent': 'ABS-SD research data downloader'})
        with urllib.request.urlopen(request, timeout=120) as response:
            content = response.read()
        import io
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            if z.testzip() is not None:
                raise ValueError('Archivo ZIP corrupto')
        DATA.write_bytes(content)
    with zipfile.ZipFile(DATA) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith('.dta')]
        if len(members) != 1:
            raise ValueError('Se esperaba un único archivo Stata')
        with archive.open(members[0]) as file:
            return pd.read_stata(file, convert_categoricals=False)


def split_hospitals(raw):
    groups = raw.HOSPCODE
    trainval, test = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED).split(raw, groups=groups))
    splits = {'trainval': trainval, 'test': test}
    return splits


def evaluate(y, pred, w, classification=False):
    if classification:
        return {
            'brier': float(brier_score_loss(y, pred, sample_weight=w)),
            'log_loss': float(log_loss(y, pred, sample_weight=w, labels=[0, 1])),
            'roc_auc': float(roc_auc_score(y, pred, sample_weight=w)) if len(np.unique(y)) > 1 else None,
            'average_precision': float(average_precision_score(y, pred, sample_weight=w)),
        }
    return {
        'mae_minutes': float(mean_absolute_error(y, pred, sample_weight=w)),
        'rmse_minutes': float(np.sqrt(mean_squared_error(y, pred, sample_weight=w))),
        'mae_unweighted_minutes': float(mean_absolute_error(y, pred)),
    }


def _score_key(classification):
    return 'brier' if classification else 'mae_minutes'


def _make_scorer(classification):
    if classification:
        return 'neg_brier_score'
    return 'neg_mean_absolute_error'


def _fit_kwargs(estimator, w_norm, groups_tr):
    kwargs = {'groups': groups_tr}
    if hasattr(estimator, 'named_steps') and 'model' in estimator.named_steps:
        kwargs['model__sample_weight'] = w_norm
    else:
        kwargs['sample_weight'] = w_norm
    return kwargs


def _fit_candidate(name, x_tr, y_tr, w_tr, groups_tr, classification, quick, seed):
    constant = fit_baseline(y_tr, w_tr, classification)
    if name == 'baseline':
        return {'name': 'baseline_weighted_median' if not classification else 'baseline_prevalence',
                'model': None, 'constant': constant, 'params': {}}
    estimator = make_estimator(name, classification, seed)
    dist, n_iter = param_distributions(name, classification, quick=quick)
    inner_cv = GroupKFold(n_splits=3)
    w_norm = w_tr / w_tr.mean()
    search = RandomizedSearchCV(
        estimator, dist, n_iter=n_iter, cv=inner_cv, scoring=_make_scorer(classification),
        random_state=seed, n_jobs=1, refit=True,
    )
    search.fit(x_tr, y_tr, **_fit_kwargs(estimator, w_norm, groups_tr))
    return {'name': name, 'model': search.best_estimator_, 'constant': constant,
            'params': search.best_params_, 'cv_score': float(search.best_score_)}


def _outer_splits(x, y, groups, indices, classification, quick, seed):
    n_splits = 3 if quick else 5
    if classification:
        cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        return list(cv.split(x.iloc[indices], y[indices], groups.iloc[indices]))
    return list(GroupKFold(n_splits=n_splits).split(x.iloc[indices], groups=groups.iloc[indices]))


def _nested_cv(name, x, y, w, groups, indices, splits, classification, quick, seed):
    """Outer folds over hospitals; returns fold scores, tuned params and out-of-fold predictions."""
    metric_key = _score_key(classification)
    fold_scores, fold_params = [], []
    oof = np.empty(len(indices))
    for fold, (tr_rel, va_rel) in enumerate(splits):
        tr_idx, va_idx = indices[tr_rel], indices[va_rel]
        fitted = _fit_candidate(name, x.iloc[tr_idx], y[tr_idx], w[tr_idx], groups.iloc[tr_idx],
                                classification, quick, seed + fold)
        pred = predict_estimator(fitted['model'], x.iloc[va_idx], classification, fitted['constant'])
        oof[va_rel] = pred
        fold_scores.append(evaluate(y[va_idx], pred, w[va_idx], classification)[metric_key])
        fold_params.append(fitted.get('params', {}))
    return fold_scores, fold_params, oof


def _select_model(cv_results, y, w, hospitals, classification, n_boot, seed):
    """Best out-of-fold metric, then the simplest model that is not significantly worse than the best
    (hospital bootstrap of paired out-of-fold errors, Holm-adjusted) and not worse than the baseline.
    Nadeau-Bengio on fold scores is reported as a complementary, lower-powered test."""
    metric_fn = brier_metric if classification else mae_metric
    oof_metric = {n: metric_fn(y, r['oof'], w) for n, r in cv_results.items()}
    ranking = sorted(((n, float(np.mean(r['fold_scores'])), float(np.std(r['fold_scores'])), oof_metric[n])
                      for n, r in cv_results.items()), key=lambda t: (t[3], PARSIMONY.get(t[0], 99)))
    best = ranking[0][0]
    others = [r[0] for r in ranking[1:]]
    boot = [cluster_bootstrap_diff(y, cv_results[n]['oof'], cv_results[best]['oof'], w, hospitals,
                                   metric_fn, n_boot, seed) for n in others]
    holm = holm_correction([b['p_value'] for b in boot])
    ratio = 1 / (len(cv_results[best]['fold_scores']) - 1)
    comparisons, eligible = [], [best]
    for n, b, p_adj in zip(others, boot, holm):
        nb = nadeau_bengio_t(cv_results[n]['fold_scores'], cv_results[best]['fold_scores'], ratio)
        ok = p_adj > 0.05 and (n == 'baseline' or oof_metric[n] <= oof_metric['baseline'])
        comparisons.append({'model': n, 'vs': best, 'mean_diff': b['diff'], 'ci_low': b['ci_low'], 'ci_high': b['ci_high'],
                            'p_value': b['p_value'], 'p_holm': p_adj, 'nb_t': nb['t'], 'nb_p': nb['p_value'],
                            'equivalent': bool(ok)})
        if ok:
            eligible.append(n)
    selected = min(eligible, key=lambda n: PARSIMONY.get(n, 99))
    justification = f'Mejor métrica fuera de pliegue: {best} ({oof_metric[best]:.4f}). '
    if selected == best:
        justification += 'Todos los modelos más simples son significativamente peores (bootstrap por hospital con Holm), así que se conserva el mejor.'
    else:
        c = next(c for c in comparisons if c['model'] == selected)
        justification += (f'Se elige {selected} por parsimonia: su diferencia con el mejor ({c["mean_diff"]:+.4f}, '
                          f'IC 95 % {c["ci_low"]:+.4f} a {c["ci_high"]:+.4f}, p Holm = {c["p_holm"]:.3f}) no es significativa.')
    return selected, {'selected': selected, 'best_cv': best, 'method': 'Bootstrap por hospital de predicciones fuera de pliegue + Holm',
                      'ranking': [{'name': n, 'mean': m, 'std': s, 'oof': o} for n, m, s, o in ranking],
                      'comparisons': comparisons, 'justification': justification}


def train(quick=False):
    raw = download()
    if len(raw) != 16025:
        raise ValueError('El archivo no corresponde a los 16025 registros esperados de 2022')
    x = clean_features(raw)
    splits = split_hospitals(raw)
    weights = pd.to_numeric(raw.PATWT, errors='coerce').to_numpy(dtype=float)
    groups = raw.HOSPCODE
    ARTIFACTS.mkdir(exist_ok=True)
    n_boot = 200 if quick else 2000

    # Legacy split for EDA partition tests
    trainval_idx = splits['trainval']
    a, b = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=SEED + 1)
               .split(raw.iloc[trainval_idx], groups=groups.iloc[trainval_idx]))
    eda_splits = {'train': trainval_idx[a], 'validation': trainval_idx[b], 'test': splits['test']}

    eda_blocks = run_eda(raw, x, eda_splits, weights)

    report = {
        'schema_version': 2,
        'source': {
            'name': 'CDC/NCHS NHAMCS 2022',
            'url': URL,
            'documentation': 'https://www.cdc.gov/nchs/nhamcs/documentation/index.html',
            'sha256': hashlib.sha256(DATA.read_bytes()).hexdigest(),
            'records': len(raw),
        },
        'trained_utc': datetime.now(timezone.utc).isoformat(),
        'seed': SEED,
        'quick_mode': quick,
        'versions': {
            'python': platform.python_version(),
            'sklearn': sklearn.__version__,
            'pandas': pd.__version__,
            'numpy': np.__version__,
            'joblib': joblib.__version__,
        },
        'business': {
            'objective': 'Acompañar la simulación ABS–SD con predicciones exploratorias de estancia, espera e ingreso.',
            'como_leer': 'Contexto CRISP-DM: el modelo no decide atención ni sustituye el motor de simulación.',
            'interpretacion': 'Uso experimental con datos NHAMCS 2022 (EE. UU.); sin validación clínica en Perú.',
        },
        'eda': eda_blocks,
        'preparation': {
            'features': FEATURES,
            'feature_missing_fraction': x.isna().mean().to_dict(),
            'cleaning': 'Códigos negativos y fuera de rango → NaN; imputación mediana en modelos lineales.',
            'como_leer': 'Reglas de limpieza y variables de llegada/triaje admitidas.',
            'interpretacion': 'Solo información disponible al arribo; sin disposición ni tratamientos posteriores.',
        },
        'split': {
            name: {'records': len(idx), 'hospitals': sorted(int(v) for v in groups.iloc[idx].unique())}
            for name, idx in splits.items()
        },
        'targets': {},
        'limits': [
            'Datos de visitas estadounidenses en 2022; sin validación local ni de víctimas masivas.',
            'LOV incluye espera: no equivale a service ni a ocupación exclusiva de un médico.',
            'Triaje NHAMCS 1–5 no se convierte automáticamente a P0/P1/P2.',
            'Bootstrap por hospital aproxima incertidumbre; no modela diseño complejo de encuesta (CSTRATM/CPSUM).',
            'Hospitalización significa ingreso en el mismo hospital (ADMITHOS).',
        ],
    }

    bundle = {}
    exports = []
    background_samples = {}

    for target, column in TARGETS:
        classification = target == 'hospitalization'
        y = pd.to_numeric(raw[column], errors='coerce').to_numpy(dtype=float)
        valid = np.isfinite(y) & np.isfinite(weights) & (weights > 0)
        valid &= np.isin(y, [0, 1]) if classification else (y >= 0)
        trval = trainval_idx[valid[trainval_idx]]
        te = splits['test'][valid[splits['test']]]

        cv_results = {}
        outer = _outer_splits(x, y, groups, trval, classification, quick, SEED)
        for cand in CANDIDATE_ORDER:
            scores, params, oof = _nested_cv(cand, x, y, weights, groups, trval, outer, classification, quick, SEED)
            cv_results[cand] = {'fold_scores': scores, 'fold_params': params, 'oof': oof}
            print(f'  {target} {cand}: CV {np.mean(scores):.4f}', flush=True)

        selected_name, selection = _select_model(cv_results, y[trval], weights[trval], groups.iloc[trval].to_numpy(),
                                                 classification, n_boot, SEED)
        friedman = friedman_test({k: v['fold_scores'] for k, v in cv_results.items()})
        nemenyi = nemenyi_posthoc({k: v['fold_scores'] for k, v in cv_results.items()})

        final_fit = _fit_candidate(selected_name, x.iloc[trval], y[trval], weights[trval],
                                    groups.iloc[trval], classification, quick, SEED)
        pred_te = predict_estimator(final_fit['model'], x.iloc[te], classification, final_fit['constant'])
        baseline_fit = _fit_candidate('baseline', x.iloc[trval], y[trval], weights[trval],
                                       groups.iloc[trval], classification, quick, SEED)
        pred_base = predict_estimator(None, x.iloc[te], classification, baseline_fit['constant'])
        hosp_te = groups.iloc[te].to_numpy()

        metric_fn = brier_metric if classification else mae_metric
        stats_block = {
            'metric_ci': cluster_bootstrap_ci(y[te], pred_te, weights[te], hosp_te, metric_fn, n_boot, SEED),
            'diff_vs_baseline': cluster_bootstrap_diff(y[te], pred_te, pred_base, weights[te], hosp_te,
                                                      metric_fn, n_boot, SEED),
        }
        if classification:
            stats_block['delong'] = delong_auc(y[te], pred_te, pred_base)
            stats_block['comparison_p'] = stats_block['delong'].get('p_value')
            stats_block['hosmer_lemeshow'] = hosmer_lemeshow(y[te], pred_te)
            stats_block['calibration'] = calibration_curve(y[te], pred_te)
            stats_block['calibration_fit'] = calibration_slope_intercept(y[te], pred_te)
        else:
            stats_block['wilcoxon'] = wilcoxon_signed_errors(y[te], pred_te, pred_base)
            stats_block['comparison_p'] = stats_block['wilcoxon'].get('p_value')

        explain = {
            'permutation': permutation_importance(final_fit['model'], x.iloc[te], y[te], weights[te],
                                                   classification, final_fit['constant'], seed=SEED),
            'shap': shap_global(final_fit['model'], x.iloc[te], classification, final_fit['constant'], SEED,
                                background=x.iloc[trval[_sample_indices(len(trval), 200, SEED)]]),
            'pdp': partial_dependence(final_fit['model'], x.iloc[te], classification=classification,
                                       constant=final_fit['constant'], seed=SEED),
            'diagnostics': diagnostic_plots(y[te], pred_te, x.iloc[te], classification),
        }

        test_by_triage, triage_p = {}, []
        triage_te = x.iloc[te].triage.to_numpy()
        for level in range(1, 6):
            mask = triage_te == level
            if mask.sum() < 20:
                continue
            diff = cluster_bootstrap_diff(y[te][mask], pred_te[mask], pred_base[mask], weights[te][mask],
                                          hosp_te[mask], metric_fn, max(200, n_boot // 4), SEED)
            test_by_triage[str(level)] = {
                'n': int(mask.sum()),
                **evaluate(y[te][mask], pred_te[mask], weights[te][mask], classification),
                'baseline_metric': metric_fn(y[te][mask], pred_base[mask], weights[te][mask]),
                'diff_vs_baseline': diff,
            }
            triage_p.append((str(level), diff['p_value']))
        for (level, _), p_adj in zip(triage_p, holm_correction([p for _, p in triage_p])):
            test_by_triage[level]['diff_vs_baseline']['p_holm'] = p_adj

        cv_summary = {k: {'mean': float(np.mean(v['fold_scores'])),
                          'std': float(np.std(v['fold_scores'])),
                          'fold_scores': [float(s) for s in v['fold_scores']],
                          'oof': evaluate(y[trval], v['oof'], weights[trval], classification)}
                      for k, v in cv_results.items()}

        report['targets'][target] = {
            'label': column,
            'selected': final_fit['name'] if selected_name != 'baseline' else baseline_fit['name'],
            'selected_key': selected_name,
            'eligible': int(valid.sum()),
            'counts': {'trainval': len(trval), 'test': len(te)},
            'cv': {**cv_summary, **cv_text(target, cv_summary, selected_name)},
            'tuning': {'best_params': _json_params(final_fit.get('params', {})),
                       'final_model': selected_name,
                       'search_space': {c: describe_space(c, classification, quick) for c in CANDIDATE_ORDER},
                       'fold_params': {c: [_json_params(p) for p in v['fold_params']]
                                       for c, v in cv_results.items()},
                       'inner_cv': 'GroupKFold(3) por hospital, RandomizedSearchCV, pesos PATWT'},
            'selection': {**selection, 'friedman': friedman, 'nemenyi': nemenyi},
            'test_selected': evaluate(y[te], pred_te, weights[te], classification),
            'test_baseline': evaluate(y[te], pred_base, weights[te], classification),
            'test_by_triage': test_by_triage,
            'statistics': {**stats_block, **test_text(target, {'test_selected': evaluate(y[te], pred_te, weights[te], classification)}, stats_block)},
            'explainability': explain,
        }

        bundle[target] = {
            'name': report['targets'][target]['selected'],
            'model': final_fit['model'],
            'constant': final_fit['constant'],
        }
        bg_idx = _sample_indices(len(trval), 200, SEED)
        background_samples[target] = x.iloc[trval[bg_idx]]

        exports.append(pd.DataFrame({
            'record_index': te, 'hospital': groups.iloc[te].to_numpy(),
            'target': target, 'observed': y[te], 'prediction': pred_te,
            'baseline': pred_base, 'weight': weights[te],
        }))
        print(target, json.dumps({
            'selected': report['targets'][target]['selected'],
            'test': report['targets'][target]['test_selected'],
            'baseline': report['targets'][target]['test_baseline'],
        }), flush=True)

    bundle['_background'] = background_samples
    joblib.dump(bundle, ARTIFACTS / 'modelos.joblib', compress=3)
    report['model_sha256'] = hashlib.sha256((ARTIFACTS / 'modelos.joblib').read_bytes()).hexdigest()
    code_files = [Path(__file__), Path(__file__).with_name('ml.py'), Path(__file__).with_name('eda.py'),
                  Path(__file__).with_name('ml_stats.py'), Path(__file__).with_name('ml_models.py'),
                  Path(__file__).with_name('ml_explain.py')]
    report['code_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in code_files if p.exists()}
    pd.concat(exports).to_csv(ARTIFACTS / 'predicciones_prueba.csv', index=False)
    report['predictions_sha256'] = hashlib.sha256((ARTIFACTS / 'predicciones_prueba.csv').read_bytes()).hexdigest()
    (ARTIFACTS / 'informe.json').write_text(
        json.dumps(_json_safe(report), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print('Guardado en', ARTIFACTS, flush=True)


def main():
    parser = argparse.ArgumentParser(description='Entrenamiento CRISP-DM NHAMCS')
    parser.add_argument('--quick', action='store_true', help='Modo rápido para pruebas (menos pliegues y bootstrap)')
    args = parser.parse_args()
    with threadpool_limits(limits=2):
        train(quick=args.quick)


if __name__ == '__main__':
    main()
