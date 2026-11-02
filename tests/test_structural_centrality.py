import itertools
import unittest
import numpy as np
from research.src.structural_centrality import brandes_batch
from research.src.structural_blocks import weighted_batch,edge_blocks,tree_masses
from scipy.sparse import csr_matrix


def csr(edges,n):
    rows=[[] for _ in range(n)]
    for i,(a,b,d) in enumerate(edges):rows[a].append((b,i,d));rows[b].append((a,i,d))
    return (np.r_[0,np.cumsum([len(r) for r in rows])].astype(np.int64),
        np.array([a for r in rows for a,i,d in r],np.int64),
        np.array([i for r in rows for a,i,d in r],np.int64),
        np.array([float(d) for r in rows for a,i,d in r]))


def brute(edges,n,od):
    adjacency=[[] for _ in range(n)];result=np.zeros(len(edges));distance_sum=0.
    for e,(a,b,d) in enumerate(edges):adjacency[a].append((b,e,d));adjacency[b].append((a,e,d))
    for source,target in itertools.combinations(np.flatnonzero(od),2):
        paths=[]
        def visit(node,visited,path,cost):
            if node==target:paths.append((cost,path));return
            for v,e,d in adjacency[node]:
                if v not in visited:visit(v,visited|{v},path+[e],cost+d)
        visit(int(source),{int(source)},[],0.)
        if not paths:continue
        shortest=min(d for d,path in paths);selected=[path for d,path in paths if d==shortest]
        distance_sum+=shortest
        for path in selected:
            for e in path:result[e]+=1/len(selected)
    return result,distance_sum


class ExactStructuralTests(unittest.TestCase):
    def test_block_projection_preserves_every_od_pair(self):
        rng=np.random.default_rng(134)
        for trial in range(60):
            n=7;edges=[(a,b,int(rng.integers(1,5))) for a in range(n) for b in range(a+1,n) if rng.random()<.3]
            if trial%4==0:edges.extend([(0,1,1),(0,1,1)])
            ptr,neighbor,eid,length=csr(edges,n);blocks,nb=edge_blocks(ptr,neighbor,eid,len(edges));od=rng.random(n)>.2
            membership=sorted({(int(blocks[e]),v) for e,(a,b,d) in enumerate(edges) for v in [a,b]})
            aa=np.array([n+b for b,v in membership],int);bb=np.array([v for b,v in membership],int)
            tree=csr_matrix((np.ones(2*len(aa)),(np.r_[aa,bb],np.r_[bb,aa])),shape=(n+nb,n+nb))
            parent,roots,mass,root_count=tree_masses(tree.indptr.astype(np.int64),tree.indices.astype(np.int64),od,n)
            result=np.zeros(len(edges))
            for block in range(nb):
                vertices=[v for b,v in membership if b==block];where={v:i for i,v in enumerate(vertices)}
                weights=np.array([mass[v] if parent[v]==n+block else mass[roots[n+block]]-mass[n+block] for v in vertices],float)
                ids=[e for e in range(len(edges)) if blocks[e]==block]
                local=[(where[edges[e][0]],where[edges[e][1]],edges[e][2]) for e in ids]
                actual,ds=weighted_batch(*csr(local,len(vertices)),weights,np.flatnonzero(weights),len(local))
                result[ids]=actual/2
            expected,ds=brute(edges,n,od);np.testing.assert_allclose(result,expected,atol=1e-10)
    def test_all_paths_in_weighted_parallel_disconnected_controls(self):
        rng=np.random.default_rng(91)
        for trial in range(40):
            n=6;edges=[(a,b,int(rng.integers(1,5))) for a in range(n) for b in range(a+1,n) if rng.random()<.35]
            if trial%4==0:edges.extend([(0,1,1),(0,1,1)])
            od=rng.random(n)>.2;sources=np.flatnonzero(od)
            actual,dist,reachable=brandes_batch(*csr(edges,n),od,sources,len(edges))
            expected,ds=brute(edges,n,od)
            np.testing.assert_allclose(actual/2,expected,atol=1e-12)
            self.assertAlmostEqual(float(dist.sum()/2),ds)
            self.assertAlmostEqual(float(np.dot(actual/2,[r[2] for r in edges])),ds)

    def test_degree_two_geometry_is_not_extra_demand(self):
        raw=[(0,1,1),(1,2,1),(2,3,1),(0,4,2),(4,3,1)]
        od=np.array([True,False,False,True,False])
        values,_,_=brandes_batch(*csr(raw,5),od,np.flatnonzero(od),len(raw))
        expected,_=brute(raw,5,od);np.testing.assert_allclose(values/2,expected)
        np.testing.assert_allclose(expected,[.5]*5)
