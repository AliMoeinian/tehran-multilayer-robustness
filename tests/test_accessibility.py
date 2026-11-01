import heapq
import math
import random
import tempfile
import sqlite3
from pathlib import Path
import unittest
import numpy as np
from research.src.accessibility import Stop,solve,run,ROOT


def brute_forward(adjacency,stops,rides,targets,origin,budget,cutoff):
    """Independent expanded-state forward search; count boarding in state."""
    terminal={}
    for n,c in targets:terminal[n]=min(c,terminal.get(n,math.inf))
    best={(0,origin,0):0};queue=[(0,0,origin,0)]
    while queue:
        cost,kind,node,used=heapq.heappop(queue)
        if cost!=best[kind,node,used]:continue
        edges=[]
        if kind==0:
            edges.extend((0,v,used,d) for v,d in adjacency[node])
            if used<budget:
                edges.extend((1,i,used+1,s.access_m) for i,s in enumerate(stops) if s.board and s.anchor==node)
        else:
            edges.extend((1,b,used,0) for a,b in rides if a==node)
            s=stops[node]
            if s.alight:edges.append((0,s.anchor,used,s.access_m))
        for k,v,u,d in edges:
            c=cost+d
            if c<=cutoff and c<best.get((k,v,u),math.inf):
                best[k,v,u]=c;heapq.heappush(queue,(c,k,v,u))
    return min([c+terminal[n] for (k,n,u),c in best.items() if k==0 and n in terminal and c+terminal[n]<=cutoff] or [math.inf])


class AccessibilityTests(unittest.TestCase):
    def test_first_boarding_and_cumulative_access_cost(self):
        graph=[[],[]];stops=[Stop(0,30),Stop(1,40)]
        layers=solve(graph,stops,[(0,1)],[(1,20)],1,100)
        self.assertTrue(math.isinf(layers[0][0]))
        self.assertEqual(layers[1][0],90)
        self.assertTrue(math.isinf(solve(graph,stops,[(0,1)],[(1,20)],1,80)[1][0]))

    def test_second_line_requires_second_boarding(self):
        graph=[[],[],[]];stops=[Stop(0,0),Stop(1,0),Stop(1,0),Stop(2,0)]
        layers=solve(graph,stops,[(0,1),(2,3)],[(2,0)],2,100)
        self.assertTrue(math.isinf(layers[1][0]));self.assertEqual(layers[2][0],0)

    def test_direction_is_not_reversed(self):
        layers=solve([[],[]],[Stop(0,0),Stop(1,0)],[(0,1)],[(0,0)],2,100)
        self.assertTrue(math.isinf(layers[2][1]))

    def test_entry_only_can_be_passed_but_not_used_to_alight(self):
        stops=[Stop(0,0),Stop(1,0,True,False),Stop(2,0)]
        self.assertEqual(solve([[],[],[]],stops,[(0,1),(1,2)],[(2,0)],1,100)[1][0],0)
        self.assertTrue(math.isinf(solve([[],[],[]],stops,[(0,1),(1,2)],[(1,0)],1,100)[1][0]))

    def test_exit_only_cannot_be_used_for_boarding(self):
        self.assertTrue(math.isinf(solve([[],[]],[Stop(0,0,False,True),Stop(1,0)],[(0,1)],[(1,0)],1,100)[1][0]))

    def test_negative_walk_cost_rejected(self):
        with self.assertRaises(ValueError):solve([[(1,-1)],[]],[],[],[(1,0)],0,100)

    def test_negative_target_cost_rejected(self):
        with self.assertRaises(ValueError):solve([[]],[],[],[(0,-1)],0,100)

    def test_mismatched_network_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);network=base/'network.sqlite';config=base/'config.json'
            config.write_text('{}')
            db=sqlite3.connect(network)
            db.execute('create table metadata(key text,value text)')
            db.execute("insert into metadata values('config_sha256','different')")
            db.commit();db.close()
            with self.assertRaisesRegex(ValueError,'configurations do not match'):
                run(network,ROOT/'research/runs/nonexistent-config-check',config)

    def test_stop_without_walking_connector_can_be_passed(self):
        stops=[Stop(0,0),Stop(-1,0,False,False),Stop(1,0)]
        self.assertEqual(solve([[],[]],stops,[(0,1),(1,2)],[(1,0)],1,100)[1][0],0)

    def test_multiple_targets_at_same_anchor_choose_smaller_cost(self):
        self.assertEqual(solve([[]],[],[],[(0,20),(0,2)],0,100)[0][0],2)

    def test_against_independent_expanded_state_search(self):
        rng=random.Random(184)
        for _ in range(30):
            adjacency=[[] for _ in range(6)]
            for u in range(6):
                for v in range(u+1,6):
                    if rng.random()<.25:
                        length=rng.randint(1,25);adjacency[u].append((v,length));adjacency[v].append((u,length))
            stops=[Stop(rng.randrange(6),rng.randint(0,9),rng.random()>.2,rng.random()>.2) for _ in range(5)]
            rides=[(a,b) for a in range(5) for b in range(5) if a!=b and rng.random()<.15]
            targets=[(4,8),(5,2)];layers=solve(adjacency,stops,rides,targets,3,50)
            for b in range(4):
                for origin in range(6):
                    expected=brute_forward(adjacency,stops,rides,targets,origin,b,50)
                    self.assertEqual(layers[b][origin],expected)


if __name__=='__main__':unittest.main()
