"""Model candidates and hyperparameter search spaces for NHAMCS ML pipeline."""
import numpy as np
from scipy.stats import loguniform, randint, uniform
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (HistGradientBoostingClassifier, HistGradientBoostingRegressor,
                              RandomForestClassifier, RandomForestRegressor)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from .ml import FEATURES

CANDIDATE_ORDER = ['baseline', 'linear', 'decision_tree', 'random_forest', 'hist_gradient_boosting']
PARSIMONY = {name: i for i, name in enumerate(CANDIDATE_ORDER)}


def _numeric_pipeline(estimator):
    return Pipeline([
        ('imputer', SimpleImputer(strategy='median', add_indicator=True)),
        ('scaler', StandardScaler()),
        ('model', estimator),
    ])


def make_estimator(name, classification, seed):
    if name == 'baseline':
        return None
    if name == 'linear':
        if classification:
            return _numeric_pipeline(LogisticRegression(max_iter=500, random_state=seed))
        return _numeric_pipeline(Ridge(random_state=seed))
    if name == 'decision_tree':
        if classification:
            return DecisionTreeClassifier(random_state=seed)
        return DecisionTreeRegressor(random_state=seed)
    if name == 'random_forest':
        if classification:
            return RandomForestClassifier(random_state=seed, n_jobs=1)
        return RandomForestRegressor(random_state=seed, n_jobs=1)
    if name == 'hist_gradient_boosting':
        if classification:
            return HistGradientBoostingClassifier(random_state=seed, early_stopping=False)
        return HistGradientBoostingRegressor(loss='absolute_error', random_state=seed, early_stopping=False)
    raise ValueError(f'Candidato desconocido: {name}')


def param_distributions(name, classification, quick=False):
    if name == 'baseline':
        return {}
    n_iter = 8 if quick else 25
    if name == 'linear':
        if classification:
            return {'model__C': loguniform(1e-2, 1e2)}, n_iter
        return {'model__alpha': loguniform(1e-2, 1e3)}, n_iter
    if name == 'decision_tree':
        return {'max_depth': randint(2, 12), 'min_samples_leaf': randint(20, 200)}, n_iter
    if name == 'random_forest':
        return {'n_estimators': randint(50, 200), 'max_depth': randint(3, 16),
                'min_samples_leaf': randint(10, 100)}, n_iter
    if name == 'hist_gradient_boosting':
        return {'learning_rate': loguniform(0.01, 0.2), 'max_leaf_nodes': randint(8, 48),
                'min_samples_leaf': randint(20, 150), 'l2_regularization': loguniform(1e-2, 100),
                'max_iter': randint(80, 300)}, n_iter
    raise ValueError(f'Candidato desconocido: {name}')


def describe_space(name, classification, quick=False):
    """Readable search space: {'params': {name: 'loguniform(a, b)'}, 'n_iter': n}."""
    if name == 'baseline':
        return {'params': {}, 'n_iter': 0}
    dist, n_iter = param_distributions(name, classification, quick)
    described = {}
    for key, d in dist.items():
        lo, hi = d.support()
        kind = d.dist.name
        if kind == 'randint':
            described[key] = f'entero uniforme [{int(lo)}, {int(hi)}]'
        else:
            described[key] = f'{kind} [{lo:g}, {hi:g}]'
    return {'params': described, 'n_iter': n_iter}


def predict_estimator(estimator, x, classification, constant=None):
    if estimator is None:
        return np.full(len(x), constant)
    if classification:
        return estimator.predict_proba(x)[:, 1]
    pred = estimator.predict(x)
    return np.maximum(0, pred)


def fit_baseline(y, w, classification):
    if classification:
        return float(np.average(y, weights=w))
    from .ml_stats import weighted_median
    return weighted_median(y, w)
