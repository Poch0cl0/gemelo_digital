import unittest
import numpy as np
import pandas as pd
from motor.eda import run_eda
from motor.ml import clean_features


class EDATests(unittest.TestCase):
    def test_eda_synthetic(self):
        n = 200
        raw = pd.DataFrame({
            'AGE': np.random.randint(18, 80, n),
            'SEX': np.random.choice([1, 2], n),
            'IMMEDR': np.random.randint(1, 6, n),
            'PULSE': np.random.randint(60, 120, n),
            'RESPR': np.random.randint(12, 24, n),
            'BPSYS': np.random.randint(100, 160, n),
            'BPDIAS': np.random.randint(60, 100, n),
            'PAINSCALE': np.random.randint(0, 11, n),
            'TEMPF': np.random.randint(960, 1000, n),
            'ARREMS': np.random.choice([1, 2], n),
            'ARRTIME': np.random.randint(800, 2000, n),
            'LOV': np.random.randint(30, 400, n),
            'WAITTIME': np.random.randint(5, 120, n),
            'ADMITHOS': np.random.choice([0, 1], n),
            'PATWT': np.ones(n),
            'HOSPCODE': np.repeat([1, 2, 3, 4], n // 4),
        })
        x = clean_features(raw)
        idx = np.arange(n)
        splits = {'train': idx[:100], 'validation': idx[100:150], 'test': idx[150:]}
        blocks = run_eda(raw, x, splits, raw.PATWT.to_numpy())
        self.assertIn('descriptives', blocks)
        self.assertIn('como_leer', blocks['descriptives'])
        self.assertIn('targets', blocks)
        self.assertIn('correlation', blocks)


if __name__ == '__main__':
    unittest.main()
