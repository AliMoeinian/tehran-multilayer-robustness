import unittest
import numpy as np
from research.src.audit_sensitivity import correlation, top_set, compare


class SensitivityRankingTests(unittest.TestCase):
    def test_cutoff_ties_all_enter_and_zeros_never_enter(self):
        values=np.array([0,0,2,2,5,-1])
        self.assertEqual(top_set(values,.34).tolist(),[False,False,True,True,True,False])
        self.assertEqual(top_set(values,1).tolist(),[False,False,True,True,True,False])
        self.assertFalse(top_set(np.array([0,0,-1]),.1).any())

    def test_tie_aware_correlation_and_undefined_constant(self):
        self.assertAlmostEqual(correlation(np.array([0,1,1,2]),np.array([3,2,2,0])),-1.)
        self.assertIsNone(correlation(np.zeros(4),np.arange(4)))
        result=compare(np.array([1,2,3,4]),np.array([4,3,2,1]))
        self.assertEqual(result['top_1pct_jaccard'],0.)
        self.assertIsNone(compare(np.zeros(5),np.zeros(5))['top_1pct_jaccard'])
