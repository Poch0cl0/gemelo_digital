"""Explainability: permutation importance, SHAP, PDP, diagnostic plots."""
import numpy as np

from .ml import FEATURES
from .ml_models import predict_estimator
from .ml_text import local_explanation


def _sample_indices(n, max_n=1000, seed=0):
    rng = np.random.default_rng(seed)
    if n <= max_n:
        return np.arange(n)
    return rng.choice(n, max_n, replace=False)


def permutation_importance(estimator, x, y, w, classification, constant, n_repeats=5, seed=0):
    """Increase of the weighted test error (MAE or Brier) when one feature is shuffled."""
    from sklearn.metrics import mean_absolute_error, brier_score_loss
    if estimator is None:
        return {col: {'mean': 0.0, 'std': 0.0} for col in FEATURES}
    rng = np.random.default_rng(seed)
    metric = ((lambda yp: brier_score_loss(y, yp, sample_weight=w)) if classification
              else (lambda yp: mean_absolute_error(y, yp, sample_weight=w)))
    base_score = metric(predict_estimator(estimator, x, classification, constant))
    importances = {}
    for col in FEATURES:
        deltas = []
        for _ in range(n_repeats):
            x_perm = x.copy()
            x_perm[col] = rng.permutation(x_perm[col].to_numpy())
            deltas.append(metric(predict_estimator(estimator, x_perm, classification, constant)) - base_score)
        importances[col] = {'mean': float(np.mean(deltas)), 'std': float(np.std(deltas))}
    return importances


def _shap_matrix(estimator, frame, classification, background):
    """SHAP values (n, len(FEATURES)) in the model's output scale (log-odds for classifiers)."""
    import shap
    if hasattr(estimator, 'named_steps'):
        prep, model = estimator[:-1], estimator.named_steps['model']
        bg = prep.transform(background if background is not None else frame)
        explainer = shap.LinearExplainer(model, bg)
        values = np.asarray(explainer.shap_values(prep.transform(frame)))
        names = prep.get_feature_names_out()
        grouped = np.zeros((values.shape[0], len(FEATURES)))
        for j, name in enumerate(names):
            base = name.split('__')[-1].replace('missingindicator_', '')
            grouped[:, FEATURES.index(base)] += values[:, j]
        return grouped
    values = shap.TreeExplainer(estimator).shap_values(frame)
    if isinstance(values, list):
        values = values[1] if classification else values[0]
    values = np.asarray(values)
    if values.ndim == 3:
        values = values[:, :, 1] if classification else values[:, :, 0]
    return values


def shap_scale(estimator, classification):
    if not classification:
        return 'minutos'
    if hasattr(estimator, 'named_steps') or 'HistGradient' in type(estimator).__name__:
        return 'log-odds'
    return 'probabilidad'


def shap_global(estimator, x, classification, constant, seed=0, max_samples=1000, background=None):
    """Mean |SHAP| per feature and a beeswarm sample."""
    if estimator is None:
        return {'available': False, 'message': 'El modelo seleccionado es una constante: ninguna variable cambia la predicción.'}
    try:
        idx = _sample_indices(len(x), max_samples, seed)
        xs = x.iloc[idx]
        sv = _shap_matrix(estimator, xs, classification, background if background is not None else xs.iloc[:200])
    except Exception as exc:
        return {'available': False, 'message': f'SHAP no disponible: {exc}'}
    mean_abs = {f: float(np.mean(np.abs(sv[:, i]))) for i, f in enumerate(FEATURES)}
    rng = np.random.default_rng(seed)
    rows = rng.choice(len(sv), min(250, len(sv)), replace=False)
    points = []
    for i, feat in enumerate(FEATURES):
        col = xs[feat].to_numpy()
        lo, hi = np.nanmin(col), np.nanmax(col)
        for j in rows:
            v = col[j]
            points.append({'feature': feat, 'shap': float(sv[j, i]),
                           'value': None if np.isnan(v) else float(v),
                           'scaled': None if np.isnan(v) or hi == lo else float((v - lo) / (hi - lo))})
    return {'available': True, 'scale': shap_scale(estimator, classification),
            'mean_abs_shap': mean_abs, 'beeswarm': points, 'n': int(len(xs))}


def partial_dependence(estimator, x, features=('triage', 'age', 'ambulance', 'arrival_hour', 'pulse', 'pain'),
                       classification=False, constant=None, seed=0):
    """Average prediction when a feature is fixed to each grid value (PDP)."""
    if estimator is None:
        return {}
    xs = x.iloc[_sample_indices(len(x), 800, seed)]
    curves = {}
    for feat in features:
        values = xs[feat].to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            continue
        grid = np.unique(values)
        if grid.size > 20:
            grid = np.unique(np.quantile(values, np.linspace(0.05, 0.95, 20)))
        average = []
        for g in grid:
            fixed = xs.copy()
            fixed[feat] = g
            average.append(float(np.mean(predict_estimator(estimator, fixed, classification, constant))))
        curves[feat] = {'grid': grid.tolist(), 'average': average}
    return curves


def diagnostic_plots(y, pred, x, classification):
    """ROC/PR for classification; observed vs predicted and residuals by triage for regression."""
    result = {}
    if classification:
        from sklearn.metrics import roc_curve, precision_recall_curve, auc
        fpr, tpr, _ = roc_curve(y, pred)
        prec, rec, _ = precision_recall_curve(y, pred)
        keep = np.unique(np.linspace(0, len(fpr) - 1, min(200, len(fpr))).astype(int))
        keep_pr = np.unique(np.linspace(0, len(prec) - 1, min(200, len(prec))).astype(int))
        result['roc'] = {'fpr': fpr[keep].tolist(), 'tpr': tpr[keep].tolist(), 'auc': float(auc(fpr, tpr))}
        result['pr'] = {'precision': prec[keep_pr].tolist(), 'recall': rec[keep_pr].tolist(),
                        'auc': float(auc(rec, prec)), 'prevalence': float(np.mean(y))}
    else:
        idx = _sample_indices(len(y), 500, 0)
        result['scatter'] = [{'observed': float(y[i]), 'predicted': float(pred[i])} for i in idx]
        residuals = {}
        triage = x['triage'].to_numpy()
        for level in range(1, 6):
            mask = triage == level
            if mask.sum() == 0:
                continue
            res = y[mask] - pred[mask]
            q1, med, q3 = np.percentile(res, [25, 50, 75])
            residuals[str(level)] = {'median': float(med), 'q1': float(q1), 'q3': float(q3),
                                     'mean': float(np.mean(res)), 'n': int(mask.sum())}
        result['residuals_by_triage'] = residuals
    return result


def local_shap(estimator, frame, classification, constant, background, target='visit_minutes'):
    """SHAP contributions for one profile plus a sentence describing the strongest ones."""
    if estimator is None:
        return {}, 'El modelo seleccionado es una constante: la predicción no depende del perfil.'
    try:
        sv = _shap_matrix(estimator, frame, classification, background)[0]
    except Exception:
        return {}, 'Explicación local no disponible para este estimador.'
    contributions = {FEATURES[i]: float(sv[i]) for i in range(len(FEATURES))}
    pred = float(predict_estimator(estimator, frame, classification, constant)[0])
    return contributions, local_explanation(contributions, pred, target, shap_scale(estimator, classification))
