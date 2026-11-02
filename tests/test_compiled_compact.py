import contextlib
import io
import random
import unittest

import numpy as np

from research.src.accessibility import Stop
from research.src.compact_accessibility import CompactModel
try:
    from research.src.compiled_compact import evaluate
    AVAILABLE=True
except ImportError:AVAILABLE=False


@unittest.skipUnless(AVAILABLE,'Install requirements-validation.txt')
class CompiledCompactTests(unittest.TestCase):
    def test_complete_vectors_match_python_on_varied_graphs(self):
        rng=random.Random(18520)
        for _ in range(60):
            n=rng.randrange(2,12);adjacency=[[] for _ in range(n)]
            for a in range(n):
                for b in range(a+1,n):
                    if rng.random()<.3:
                        d=float(rng.randrange(0,20));adjacency[a].append((b,d));adjacency[b].append((a,d))
            size=rng.randrange(1,15)
            stops=[Stop(rng.randrange(n),float(rng.randrange(8)),rng.random()>.2,rng.random()>.2) for _ in range(size)]
            rides=[(a,b) for a in range(size) for b in range(size) if a!=b and rng.random()<.12]
            with contextlib.redirect_stdout(io.StringIO()):model=CompactModel(adjacency,stops,[(n-1,2.)],list(range(n)),[0]*n,50)
            for active in [np.ones(size,dtype=bool),np.array([rng.random()>.3 for s in stops])]:
                np.testing.assert_array_equal(evaluate(model,stops,rides,3,50,active),np.array(model.costs(rides,3,active)))


if __name__=='__main__':unittest.main()
