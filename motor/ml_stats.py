"""Statistical tests for ML evaluation: bootstrap, DeLong, Friedman, Holm, calibration."""
import numpy as np
from scipy import stats


def holm_correction(p_values):
    """Holm-Bonferroni step-down adjusted p-values, in the original order."""
    p = np.asarray(p_values, dtype=float)
    m = len(p)
    if m == 0:
        return []
    order = np.argsort(p)
    adjusted = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[idx]))
        adjusted[idx] = running
    return adjusted.tolist()


def weighted_median(y, w):
    order = np.argsort(y)
    y, w = np.asarray(y)[order], np.asarray(w)[order]
    return float(y[np.searchsorted(w.cumsum(), w.sum() / 2)])


def _hospital_index(hospitals):
    hosp = np.asarray(hospitals)
    ids = np.unique(hosp)
    return ids, {h: np.flatnonzero(hosp == h) for h in ids}


def cluster_bootstrap_ci(y, pred, w, hospitals, metric_fn, n_boot=2000, seed=0, alpha=0.05):
    """Percentile CI resampling hospitals (clusters) with replacement."""
    rng = np.random.default_rng(seed)
    ids, idx = _hospital_index(hospitals)
    values = []
    for _ in range(n_boot):
        sample = np.concatenate([idx[h] for h in rng.choice(ids, len(ids))])
        values.append(metric_fn(y[sample], pred[sample], w[sample]))
    lo, hi = np.percentile(values, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {'point': float(metric_fn(y, pred, w)), 'ci_low': float(lo), 'ci_high': float(hi),
            'n_boot': n_boot, 'clusters': int(len(ids))}


def cluster_bootstrap_diff(y, pred_a, pred_b, w, hospitals, metric_fn, n_boot=2000, seed=0, alpha=0.05):
    """CI of metric(a) - metric(b) on the same hospital resamples; p is the two-sided bootstrap p."""
    rng = np.random.default_rng(seed)
    ids, idx = _hospital_index(hospitals)
    diffs = []
    for _ in range(n_boot):
        sample = np.concatenate([idx[h] for h in rng.choice(ids, len(ids))])
        diffs.append(metric_fn(y[sample], pred_a[sample], w[sample]) -
                     metric_fn(y[sample], pred_b[sample], w[sample]))
    diffs = np.asarray(diffs)
    lo, hi = np.percentile(diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    p = min(1.0, 2 * min((diffs >= 0).mean(), (diffs <= 0).mean()))
    return {'diff': float(metric_fn(y, pred_a, w) - metric_fn(y, pred_b, w)),
            'ci_low': float(lo), 'ci_high': float(hi), 'p_value': float(p), 'n_boot': n_boot}


def wilcoxon_signed_errors(y, pred_model, pred_baseline):
    """One-sided Wilcoxon signed-rank: are model absolute errors smaller than the baseline's?"""
    err_m = np.abs(y - pred_model)
    err_b = np.abs(y - pred_baseline)
    if np.allclose(err_m, err_b):
        return {'statistic': 0.0, 'p_value': 1.0, 'median_diff': 0.0}
    stat, p = stats.wilcoxon(err_m, err_b, alternative='less')
    return {'statistic': float(stat), 'p_value': float(p), 'median_diff': float(np.median(err_m - err_b))}


def _midrank(x):
    order = np.argsort(x)
    xs = x[order]
    n = len(x)
    ranks = np.zeros(n)
    i = 0
    while i < n:
        j = i
        while j < n and xs[j] == xs[i]:
            j += 1
        ranks[i:j] = 0.5 * (i + j - 1) + 1
        i = j
    out = np.empty(n)
    out[order] = ranks
    return out


def _delong_components(y, scores):
    pos, neg = scores[y == 1], scores[y == 0]
    m, n = len(pos), len(neg)
    tx, ty, tz = _midrank(pos), _midrank(neg), _midrank(np.concatenate([pos, neg]))
    auc = (tz[:m].sum() - m * (m + 1) / 2) / (m * n)
    v10 = (tz[:m] - tx) / n
    v01 = 1 - (tz[m:] - ty) / m
    return auc, v10, v01


def delong_auc(y_true, pred_a, pred_b):
    """DeLong (1988) test for two correlated ROC AUCs, using the Sun & Xu (2014) midrank algorithm."""
    y = np.asarray(y_true, dtype=int)
    a, b = np.asarray(pred_a, dtype=float), np.asarray(pred_b, dtype=float)
    m, n = int((y == 1).sum()), int((y == 0).sum())
    if m < 2 or n < 2:
        return {'auc_a': None, 'auc_b': None, 'z': None, 'p_value': None}
    auc_a, v10a, v01a = _delong_components(y, a)
    auc_b, v10b, v01b = _delong_components(y, b)
    s10 = np.cov(np.vstack([v10a, v10b]))
    s01 = np.cov(np.vstack([v01a, v01b]))
    cov = s10 / m + s01 / n
    var = cov[0, 0] + cov[1, 1] - 2 * cov[0, 1]
    se_a = float(np.sqrt(cov[0, 0]))
    ci_a = [float(auc_a - 1.96 * se_a), float(auc_a + 1.96 * se_a)]
    if var <= 0:
        return {'auc_a': float(auc_a), 'auc_b': float(auc_b), 'auc_a_ci': ci_a, 'z': 0.0, 'p_value': 1.0}
    z = (auc_a - auc_b) / np.sqrt(var)
    return {'auc_a': float(auc_a), 'auc_b': float(auc_b), 'auc_a_ci': ci_a,
            'z': float(z), 'p_value': float(2 * stats.norm.sf(abs(z)))}


def hosmer_lemeshow(y_true, pred, n_bins=10):
    """Hosmer-Lemeshow goodness of fit over risk deciles (df = groups - 2)."""
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(pred, dtype=float), 1e-6, 1 - 1e-6)
    order = np.argsort(p)
    y, p = y[order], p[order]
    chi2, groups = 0.0, 0
    for b in np.array_split(np.arange(len(y)), n_bins):
        if len(b) == 0:
            continue
        obs1, exp1 = y[b].sum(), p[b].sum()
        exp0 = len(b) - exp1
        if exp1 <= 0 or exp0 <= 0:
            continue
        chi2 += (obs1 - exp1) ** 2 / exp1 + ((len(b) - obs1) - exp0) ** 2 / exp0
        groups += 1
    df = max(groups - 2, 1)
    return {'chi2': float(chi2), 'df': int(df), 'p_value': float(stats.chi2.sf(chi2, df))}


def calibration_curve(y_true, pred, n_bins=10):
    """Mean predicted risk vs observed rate per risk decile."""
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(pred, dtype=float)
    order = np.argsort(p)
    y, p = y[order], p[order]
    return [{'predicted': float(p[b].mean()), 'observed': float(y[b].mean()), 'n': int(len(b))}
            for b in np.array_split(np.arange(len(y)), n_bins) if len(b)]


def calibration_slope_intercept(y_true, pred):
    """Logistic recalibration: logit P(y=1) = intercept + slope * logit(pred). Ideal: 0 and 1."""
    from sklearn.linear_model import LogisticRegression
    y = np.asarray(y_true, dtype=int)
    if len(np.unique(y)) < 2:
        return {'intercept': None, 'slope': None}
    p = np.clip(np.asarray(pred, dtype=float), 1e-6, 1 - 1e-6)
    logit = np.log(p / (1 - p)).reshape(-1, 1)
    fit = LogisticRegression(C=1e6, max_iter=1000).fit(logit, y)
    return {'intercept': float(fit.intercept_[0]), 'slope': float(fit.coef_[0, 0])}


def friedman_test(fold_scores):
    """Friedman test of candidate models over the same CV folds (lower score = better)."""
    names = list(fold_scores)
    matrix = np.array([fold_scores[n] for n in names])
    if matrix.shape[0] < 3 or matrix.shape[1] < 2:
        return {'statistic': None, 'p_value': None}
    stat, p = stats.friedmanchisquare(*matrix)
    return {'statistic': float(stat), 'p_value': float(p), 'folds': int(matrix.shape[1])}


def nemenyi_posthoc(fold_scores, alpha=0.05):
    """Nemenyi critical difference of mean ranks (Demsar 2006); rank 1 = best (lowest error)."""
    names = list(fold_scores)
    matrix = np.array([fold_scores[n] for n in names])
    k, n = matrix.shape
    if n < 2 or k < 2:
        return {'critical_difference': None, 'mean_ranks': {}, 'pairs': []}
    ranks = np.apply_along_axis(stats.rankdata, 0, matrix).mean(axis=1)
    q_alpha = stats.studentized_range.ppf(1 - alpha, k, np.inf) / np.sqrt(2)
    cd = float(q_alpha * np.sqrt(k * (k + 1) / (6 * n)))
    pairs = [{'a': names[i], 'b': names[j], 'rank_diff': float(abs(ranks[i] - ranks[j])),
              'significant': bool(abs(ranks[i] - ranks[j]) > cd)}
             for i in range(k) for j in range(i + 1, k)]
    return {'critical_difference': cd, 'mean_ranks': {names[i]: float(ranks[i]) for i in range(k)},
            'pairs': pairs}


def nadeau_bengio_t(fold_scores_a, fold_scores_b, test_train_ratio=0.25):
    """Corrected resampled t-test (Nadeau & Bengio 2003) on paired CV fold scores (a - b)."""
    a = np.asarray(fold_scores_a, dtype=float)
    b = np.asarray(fold_scores_b, dtype=float)
    k = len(a)
    if k < 2:
        return {'t': None, 'p_value': None, 'mean_diff': None}
    diff = a - b
    mean_diff = float(diff.mean())
    var = diff.var(ddof=1)
    if var == 0:
        return {'t': 0.0, 'p_value': 1.0, 'mean_diff': mean_diff}
    t = mean_diff / np.sqrt((1 / k + test_train_ratio) * var)
    return {'t': float(t), 'p_value': float(2 * stats.t.sf(abs(t), df=k - 1)), 'mean_diff': mean_diff}


def mae_metric(y, pred, w):
    from sklearn.metrics import mean_absolute_error
    return float(mean_absolute_error(y, pred, sample_weight=w))


def brier_metric(y, pred, w):
    from sklearn.metrics import brier_score_loss
    return float(brier_score_loss(y, pred, sample_weight=w))
