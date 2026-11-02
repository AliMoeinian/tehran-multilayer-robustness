import numpy as np
import unittest

from research.src.accessibility import Stop, solve
from research.src.path_witnesses import solve_witness


def check_parent_solver_all_small_random_graphs():
    rng=np.random.default_rng(2411)
    for trial in range(60):
        n=12;s=5;adj=[[] for _ in range(n)];rows=[]
        for a in range(n):
            for b in range(a+1,n):
                if rng.random()<.2:
                    d=float(rng.integers(0,8));eid=len(rows)
                    adj[a].append((b,d,eid));adj[b].append((a,d,eid));rows.append((a,b,d))
        ptr=np.r_[0,np.cumsum([len(r) for r in adj])].astype(np.int64)
        other=np.array([a for row in adj for a,d,e in row],dtype=np.int64)
        length=np.array([d for row in adj for a,d,e in row])
        edges=np.array([e for row in adj for a,d,e in row],dtype=np.int64)
        anchors=rng.integers(n,size=s);access=rng.integers(0,3,size=s).astype(float)
        board=rng.random(s)>.2;alight=rng.random(s)>.2
        rs=np.array([0,1,2,3,4],dtype=np.int64);re=np.array([1,2,0,4,3],dtype=np.int64)
        enabled=rng.random(5)>.3
        tn=np.array([2,8],dtype=np.int64);tc=np.array([1.,2.])
        dist,parent,edge,onparent=solve_witness(ptr,other,length,edges,anchors,access,board,alight,rs,re,enabled,tn,tc,3,20.)
        reference=solve([[(a,d) for a,d,e in row] for row in adj],
            [Stop(int(a),d,bool(b),bool(c)) for a,d,b,c in zip(anchors,access,board,alight)],
            [(int(a),int(b)) for a,b,keep in zip(rs,re,enabled) if keep],list(zip(tn,tc)),3,20.)
        np.testing.assert_allclose(dist,np.array(reference))
        for budget in range(4):
            for start in np.flatnonzero(np.isfinite(dist[budget])):
                b=budget;node=int(start);total=0.;visits=0
                while True:
                    visits+=1;assert visits<100
                    nxt=parent[b,node]
                    if nxt>=0:
                        a,c,d=rows[edge[b,node]];assert {a,c}=={node,nxt}
                        total+=d;node=int(nxt);continue
                    if nxt==-1:assert b>0;b-=1;continue
                    seed=edge[b,node]
                    if b==0:
                        assert node==tn[seed];total+=tc[seed];break
                    stop=seed;assert board[stop] and node==anchors[stop];total+=access[stop]
                    rides=0
                    while onparent[b,stop]>=0:
                        e=onparent[b,stop];assert enabled[e] and rs[e]==stop
                        stop=re[e];rides+=1;assert rides<=5
                    assert alight[stop];total+=access[stop];node=int(anchors[stop]);b-=1
                assert abs(total-dist[budget,start])<1e-9


class PathWitnessTests(unittest.TestCase):
    def test_every_parent_chain_on_varied_directed_zero_cost_graphs(self):
        check_parent_solver_all_small_random_graphs()
