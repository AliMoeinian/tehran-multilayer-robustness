import unittest

import numpy as np

from research.src.accessibility import Stop
from research.src.compact_accessibility import CompactModel
from research.src.pair_closures import interaction,pair_domain,physical_pair


class PairTests(unittest.TestCase):
    def test_physical_pair_unranking_is_distinct_and_complete(self):
        a=['a','b','c'];b=['d','e']
        self.assertEqual([physical_pair(a,a,i,True) for i in range(3)],[('a','b'),('a','c'),('b','c')])
        self.assertEqual(len(set(physical_pair(a,b,i) for i in range(6))),6)

    def test_domain_retains_distinct_same_signature_streets(self):
        groups=[{'streets':['a','b','c'],'failed_connections':['x']},
                {'streets':['d','e'],'failed_connections':['y']}]
        rows,unions=pair_domain(groups)
        self.assertEqual(sum(n for a,b,n,u in rows),10)
        self.assertEqual([(a,b,n) for a,b,n,u in rows],[(0,0,3),(0,1,6),(1,1,1)])
        self.assertEqual(unions,[('x',),('x','y'),('y',)])

    def test_union_grouping_does_not_erase_pair_identity(self):
        groups=[{'streets':['a','b'],'failed_connections':['x']},
                {'streets':['c'],'failed_connections':['x','y']},
                {'streets':['d'],'failed_connections':['y']}]
        rows,unions=pair_domain(groups)
        self.assertEqual(sum(n for a,b,n,u in rows),6)
        self.assertEqual(len([r for r in rows if r[3]==('x','y')]),3)

    def test_redundant_routes_yield_positive_interaction(self):
        compact=CompactModel([[],[]],[Stop(0,0),Stop(1,0),Stop(0,0),Stop(1,0)],[(1,0)],[0],[0],100)
        def loss(rides):return 1-int(np.isfinite(compact.costs(rides,1)[1][0]))
        self.assertEqual(interaction(loss([]),loss([(0,1)]),loss([(2,3)])),1)

    def test_series_failures_yield_negative_interaction(self):
        compact=CompactModel([[],[],[]],[Stop(0,0),Stop(1,0),Stop(2,0)],[(2,0)],[0],[0],100)
        def loss(rides):return 1-int(np.isfinite(compact.costs(rides,1)[1][0]))
        self.assertEqual(interaction(loss([]),loss([(0,1)]),loss([(1,2)])),-1)
        self.assertEqual(interaction(0,0,0),0)


if __name__=='__main__':unittest.main()
