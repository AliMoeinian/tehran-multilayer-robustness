import contextlib
import io
import random
import unittest

import numpy as np

from research.src.accessibility import Stop,solve
from research.src.compact_accessibility import CompactModel
from tests.test_accessibility import brute_forward


class CompactTests(unittest.TestCase):
    def test_independent_forward_and_full_graph_on_random_failures(self):
        rng=random.Random(20261101)
        for _ in range(30):
            adjacency=[[] for _ in range(6)]
            for a in range(6):
                for b in range(a+1,6):
                    if rng.random()<.3:
                        length=rng.randrange(1,20);adjacency[a].append((b,length));adjacency[b].append((a,length))
            stops=[Stop(rng.randrange(6),rng.randrange(6),rng.random()>.2,rng.random()>.2) for _ in range(5)]
            rows=[(a,b) for a in range(5) for b in range(5) if a!=b and rng.random()<.2]
            targets=[(4,2),(5,5)]
            with contextlib.redirect_stdout(io.StringIO()):
                compact=CompactModel(adjacency,stops,targets,list(range(6)),[0]*6,50)
            for rides in [rows,rows[1:]]:
                result=compact.costs(rides,3)
                full=solve(adjacency,stops,rides,targets,3,50)
                for b in range(4):
                    np.testing.assert_array_equal(result[b],full[b])
                    for origin in range(6):
                        self.assertEqual(result[b][origin],brute_forward(adjacency,stops,rides,targets,origin,b,50))

    def test_pass_through_rejected_connector_and_origin_cost(self):
        stops=[Stop(0,2),Stop(-1,0,False,False),Stop(1,3)]
        compact=CompactModel([[],[]],stops,[(1,4)],[0],[5],100)
        self.assertEqual(compact.costs([(0,1),(1,2)],1)[1][0],14)

    def test_disabled_modes_cannot_board_or_alight(self):
        compact=CompactModel([[],[]],[Stop(0,0),Stop(1,0)],[(1,0)],[0],[0],100)
        self.assertTrue(np.isinf(compact.costs([],2,[False,False])[2][0]))

    def test_no_stops_and_cutoff(self):
        compact=CompactModel([[]],[],[(0,4)],[0],[3],5)
        self.assertTrue(all(np.isinf(v[0]) for v in compact.costs([],3)))


if __name__=='__main__':unittest.main()
