import unittest
import numpy as np
from motor.ml_stats import (holm_correction, nadeau_bengio_t, hosmer_lemeshow,
                             delong_auc, cluster_bootstrap_ci, mae_metric)


class MLStatsTests(unittest.TestCase):
    def test_holm_monotonic(self):
        adj = holm_correction([0.01, 0.04, 0.2])
        self.assertTrue(all(adj[i] <= adj[i + 1] or adj[i] >= adj[i + 1] for i in range(len(adj) - 1)))
        self.assertGreaterEqual(adj[0], 0.01)

    def test_nadeau_bengio_identical(self):
        scores = [1.0, 1.1, 0.9, 1.0, 1.05]
        r = nadeau_bengio_t(scores, scores)
        self.assertEqual(r['p_value'], 1.0)

    def test_hosmer_lemeshow_synthetic(self):
        y = np.array([0, 0, 0, 1, 1, 1, 0, 1, 0, 1])
        p = np.array([0.1, 0.2, 0.15, 0.8, 0.7, 0.75, 0.3, 0.6, 0.25, 0.9])
        r = hosmer_lemeshow(y, p, n_bins=5)
        self.assertIn('chi2', r)
        self.assertIn('p_value', r)

    def test_delong_same_predictions(self):
        y = np.array([0, 0, 1, 1, 0, 1])
        p = np.array([0.2, 0.3, 0.7, 0.8, 0.4, 0.6])
        r = delong_auc(y, p, p)
        self.assertAlmostEqual(r['auc_a'], r['auc_b'])
        self.assertGreater(r['p_value'], 0.9)

    def test_holm_known_values(self):
        self.assertEqual([round(v, 4) for v in holm_correction([0.01, 0.04, 0.03])], [0.03, 0.06, 0.06])

    def test_delong_detects_better_model(self):
        rng = np.random.default_rng(0)
        y = rng.integers(0, 2, 400)
        good = y * 0.6 + rng.random(400) * 0.4
        r = delong_auc(y, good, rng.random(400))
        self.assertGreater(r['auc_a'], 0.9)
        self.assertLess(r['p_value'], 0.001)

    def test_selection_keeps_clearly_better_model(self):
        from motor.train_ml import _select_model
        rng = np.random.default_rng(1)
        y = rng.normal(100, 30, 3000).clip(0)
        h = rng.integers(0, 60, 3000)
        cv = {'baseline': {'fold_scores': [25, 24, 26], 'oof': np.full(3000, np.median(y))},
              'linear': {'fold_scores': [9, 9, 9], 'oof': y + rng.normal(0, 10, 3000)}}
        selected, info = _select_model(cv, y, np.ones(3000), h, False, 200, 0)
        self.assertEqual(selected, 'linear')
        self.assertFalse(info['comparisons'][0]['equivalent'])

    def test_bootstrap_deterministic(self):
        y = np.array([10., 20., 30., 40.])
        pred = np.array([12., 18., 28., 38.])
        w = np.ones(4)
        h = np.array([1, 1, 2, 2])
        a = cluster_bootstrap_ci(y, pred, w, h, mae_metric, n_boot=100, seed=42)
        b = cluster_bootstrap_ci(y, pred, w, h, mae_metric, n_boot=100, seed=42)
        self.assertEqual(a['ci_low'], b['ci_low'])
        self.assertEqual(a['ci_high'], b['ci_high'])


if __name__ == '__main__':
    unittest.main()
