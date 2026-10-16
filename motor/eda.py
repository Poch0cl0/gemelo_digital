"""Exploratory data analysis for NHAMCS 2022 with interpretable outputs."""
import numpy as np
import pandas as pd
from scipy import stats

from .ml import FEATURES
from .ml_stats import holm_correction
from .ml_text import eda_block_text


def _weighted_stats(series, weights):
    s = series.dropna()
    w = weights.loc[s.index]
    if len(s) == 0:
        return {'n': 0, 'missing': 1.0}
    q1, med, q3 = np.percentile(s, [25, 50, 75])
    iqr = q3 - q1
    outliers = ((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum()
    return {
        'n': int(len(s)),
        'missing': float(series.isna().mean()),
        'mean': float(np.average(s, weights=w)),
        'median': float(np.median(s)),
        'q1': float(q1), 'q3': float(q3),
        'min': float(s.min()), 'max': float(s.max()),
        'outliers_iqr': int(outliers),
    }


def _histogram(series, weights, bins=20):
    s = series.dropna()
    w = weights.loc[s.index].to_numpy()
    counts, edges = np.histogram(s, bins=bins, weights=w)
    return {'bins': [float(e) for e in edges], 'counts': [float(c) for c in counts]}


def run_eda(raw, x, splits, weights):
    """Run full EDA; returns dict with data + como_leer + interpretacion per block."""
    targets = {'visit_minutes': 'LOV', 'wait_minutes': 'WAITTIME', 'hospitalization': 'ADMITHOS'}
    w = pd.Series(weights, index=raw.index)
    blocks = {}

    # Descriptives per feature
    desc = {}
    for col in FEATURES:
        desc[col] = {
            'weighted': _weighted_stats(x[col], w),
            'unweighted': _weighted_stats(x[col], pd.Series(1.0, index=x.index)),
            'histogram': _histogram(x[col], w),
        }
    blocks['descriptives'] = {
        'data': desc,
        **eda_block_text('descriptives', desc),
    }

    # Target distributions
    target_blocks = {}
    for key, col in targets.items():
        y = pd.to_numeric(raw[col], errors='coerce')
        if key == 'hospitalization':
            valid = y.isin([0, 1])
            prev = float(np.average(y[valid], weights=w[valid]))
            target_blocks[key] = {
                'prevalence': prev,
                'n': int(valid.sum()),
                'histogram': {'bins': [0, 0.5, 1], 'counts': [float((y == 0).sum()), float((y == 1).sum())]},
            }
        else:
            valid = y >= 0
            target_blocks[key] = {
                **_weighted_stats(y[valid], w[valid]),
                'histogram': _histogram(y[valid], w[valid], bins=30),
                'log_histogram': _histogram(np.log1p(y[valid]), w[valid], bins=30),
            }
    blocks['targets'] = {
        'data': target_blocks,
        **eda_block_text('targets', target_blocks),
    }

    # By triage
    triage_blocks = {}
    kw_p = {}
    for key, col in targets.items():
        y = pd.to_numeric(raw[col], errors='coerce')
        by_level = {}
        groups = []
        for level in range(1, 6):
            mask = (x['triage'] == level) & y.notna()
            if key == 'hospitalization':
                mask &= y.isin([0, 1])
            else:
                mask &= y >= 0
            if mask.sum() == 0:
                continue
            vals = y[mask]
            by_level[str(level)] = {
                'n': int(mask.sum()),
                'median': float(vals.median()),
                'q1': float(vals.quantile(0.25)),
                'q3': float(vals.quantile(0.75)),
            }
            groups.append(vals.to_numpy())
        if len(groups) >= 2:
            stat, p = stats.kruskal(*groups)
            kw_p[key] = float(p)
        triage_blocks[key] = by_level
    blocks['by_triage'] = {
        'data': triage_blocks,
        'kruskal_p': kw_p,
        **eda_block_text('by_triage', triage_blocks, kw_p),
    }

    # Spearman correlation
    corr_cols = list(FEATURES) + list(targets.keys())
    frame = x.copy()
    for key, col in targets.items():
        frame[key] = pd.to_numeric(raw[col], errors='coerce')
    corr = frame[corr_cols].corr(method='spearman').round(4)
    corr_data = {r: {c: float(corr.loc[r, c]) if pd.notna(corr.loc[r, c]) else None
                     for c in corr_cols} for r in corr_cols}
    blocks['correlation'] = {
        'data': corr_data,
        **eda_block_text('correlation', corr_data),
    }

    # Partition comparison (train vs validation vs test)
    part_p = []
    part_names = []
    for col in FEATURES[:4]:
        for a, b in [('train', 'validation'), ('train', 'test'), ('validation', 'test')]:
            ia, ib = splits[a], splits[b]
            sa = x.iloc[ia][col].dropna()
            sb = x.iloc[ib][col].dropna()
            if len(sa) < 5 or len(sb) < 5:
                continue
            stat, p = stats.ks_2samp(sa, sb)
            part_p.append(float(p))
            part_names.append(f'{col}_{a}_vs_{b}')
    if part_p:
        adj = holm_correction(part_p)
        partition_tests = [{'variable': part_names[i], 'ks_p': part_p[i], 'holm_p': adj[i]}
                           for i in range(len(part_p))]
    else:
        partition_tests = []
    blocks['partitions'] = {
        'data': partition_tests,
        **eda_block_text('partitions', partition_tests),
    }

    return blocks
