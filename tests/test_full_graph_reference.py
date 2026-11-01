import random
import unittest

import numpy as np

from research.src.accessibility import Stop,solve
try:
    from research.src.full_graph_reference import walking_csr,relax,solve_full
    AVAILABLE=True
except ImportError:AVAILABLE=False


@unittest.skipUnless(AVAILABLE,'Install requirements-validation.txt for the compiled reference tests')
class FullReferenceTests(unittest.TestCase):
    def test_all_nodes_against_original_solver(self):
        rng=random.Random(341)
        for _ in range(30):
            adjacency=[[] for _ in range(6)]
            for a in range(6):
                for b in range(a+1,6):
                    if rng.random()<.35:
                        d=float(rng.randrange(0,20));adjacency[a].append((b,d));adjacency[b].append((a,d))
            stops=[Stop(rng.randrange(6),float(rng.randrange(5)),rng.random()>.2,rng.random()>.2) for _ in range(5)]
            rides=[(a,b) for a in range(5) for b in range(5) if a!=b and rng.random()<.2]
            csr=walking_csr(adjacency);targets=[(4,2.),(5,4.)]
            walking=relax(*csr,np.full(6,np.inf),np.array([4,5]),np.array([2.,4.]),50.)
            result=solve_full(*csr,np.array([s.anchor for s in stops]),np.array([s.access_m for s in stops]),
                np.array([s.board for s in stops]),np.array([s.alight for s in stops]),
                np.array([a for a,b in rides],dtype=np.int64),np.array([b for a,b in rides],dtype=np.int64),
                walking,3,50.,np.arange(6),np.zeros(6))
            np.testing.assert_array_equal(result,np.array(solve(adjacency,stops,rides,targets,3,50)))


if __name__=='__main__':unittest.main()
