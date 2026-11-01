import unittest

import numpy as np

from research.src.accessibility import Stop, solve
from research.src.single_closures import dependency_groups, retained_rides
from tests.test_accessibility import brute_forward


class ClosureTests(unittest.TestCase):
    def test_grouping_is_exact_deduplicated_and_deterministic(self):
        rows=[('a','x'),('a','y'),('b','y'),('b','x'),('b','x'),('c','x')]
        expected={('x',):['c'],('x','y'):['a','b']}
        self.assertEqual(dependency_groups(rows),expected)
        self.assertEqual(dependency_groups(reversed(rows)),expected)

    def test_closure_removes_only_dependent_arc_and_retains_metro(self):
        rows=[('b1','s0','s1','bus'),('b2','s1','s2','bus'),('m1','s0','s2','metro')]
        ids={'s0':0,'s1':1,'s2':2}
        self.assertEqual(retained_rides(rows,ids,{'bus','metro'},{'b1'}),[(1,2),(0,2)])
        self.assertEqual(retained_rides(rows,ids,{'bus'},{'unrelated'}),[(0,1),(1,2)])

    def test_grouped_results_match_individual_closures_and_forward_search(self):
        adjacency=[[(1,15)],[(0,15)],[]]
        stops=[Stop(0,1),Stop(1,1),Stop(2,1)]
        rows=[('b1','a','b','bus'),('b2','b','c','bus')]
        ids={'a':0,'b':1,'c':2}
        dependencies=[('x','b1'),('y','b1'),('z','b2')]
        grouped={}
        for failed,streets in dependency_groups(dependencies).items():
            rides=retained_rides(rows,ids,{'bus'},set(failed))
            layers=solve(adjacency,stops,rides,[(2,2)],2,100)
            for street in streets:grouped[street]=layers
        for street in ['x','y','z']:
            failed={key for edge,key in dependencies if edge==street}
            rides=retained_rides(rows,ids,{'bus'},failed)
            individual=solve(adjacency,stops,rides,[(2,2)],2,100)
            for budget in range(3):
                np.testing.assert_array_equal(individual[budget],grouped[street][budget])
                for origin in range(3):
                    self.assertEqual(individual[budget][origin],
                        brute_forward(adjacency,stops,rides,[(2,2)],origin,budget,100))

    def test_closure_breaks_through_ride_but_keeps_unaffected_local_arc(self):
        stops=[Stop(0,0),Stop(1,0),Stop(2,0)]
        layers=solve([[],[],[]],stops,[(1,2)],[(2,0)],1,100)
        self.assertTrue(np.isinf(layers[1][0]))
        self.assertEqual(layers[1][1],0)

    def test_metro_need_not_reduce_closure_loss(self):
        # The bus feeds metro: metro creates a new opportunity exposed to closure.
        stops=[Stop(0,0),Stop(1,0),Stop(2,0)];adjacency=[[],[],[]]
        def reachable(rides):
            return int(np.isfinite(solve(adjacency,stops,rides,[(2,0)],2,100)[2][0]))
        bus_loss=reachable([(0,1)])-reachable([])
        full_loss=reachable([(0,1),(1,2)])-reachable([(1,2)])
        self.assertEqual(bus_loss-full_loss,-1)


if __name__=='__main__':unittest.main()
