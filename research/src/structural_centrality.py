"""Exact all-junction weighted edge betweenness on the full context corridor graph.

Degree-two geometry vertices are not OD locations. All mapped highway/path
segments and all components are retained; this is not a legal vehicle graph.
Zero-length links are equivalence links, not positive-distance route choices.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
import hashlib
import heapq
import json
from pathlib import Path
import sqlite3
import time

import numba
import numpy as np
from pyproj import Transformer
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
import shapely

from .accessibility import ROOT
from .sensitivity_runs import gp_geometry
from .pair_closures import write_gzip_csv

MODEL=ROOT/'research/model/structural-v1'
OUT=ROOT/'research/reports/structural-2026-11-02'
RUN=ROOT/'research/runs/structural-v1'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    MODEL.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((ROOT/'research/config/baseline.json').read_text())
    source=ROOT/'data/extracted'/cfg['dataset_id']/'tehran_audited_layers.gpkg'
    db=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    project=Transformer.from_crs(4326,32639,always_xy=True)
    aa=[];bb=[];dd=[];way=[];way_metadata={};road_rows=0
    for wid,raw,blob in db.execute('select osm_id,attributes_json,geom from roads_context order by osm_id'):
        road_rows+=1;a=json.loads(raw);xy=np.asarray(gp_geometry(blob).coords)
        x,y=project.transform(xy[:,0],xy[:,1]);xy=np.column_stack((x,y));nodes=a['node_ids']
        assert len(nodes)==len(xy)
        way_metadata[str(wid)]={'highway':a['tags'].get('highway','unknown'),'drive_candidate':a['drive_candidate'],'walk_candidate':a['walk_candidate']}
        for u,v,p,q in zip(nodes,nodes[1:],xy,xy[1:]):
            aa.append(min(u,v));bb.append(max(u,v));dd.append(float(np.linalg.norm(q-p)));way.append(wid)
    db.close();aa=np.asarray(aa,dtype=np.int64);bb=np.asarray(bb,dtype=np.int64);dd=np.asarray(dd);way=np.asarray(way,dtype=np.int64)
    native=np.unique(np.r_[aa,bb]);u=np.searchsorted(native,aa);v=np.searchsorted(native,bb)
    zero=dd<=1e-7
    z=csr_matrix((np.ones(int(zero.sum())),(u[zero],v[zero])),shape=(len(native),len(native)))
    _,quotient=connected_components(z,directed=False)
    qu,qv=quotient[u],quotient[v];pairs=np.column_stack((np.minimum(qu,qv),np.maximum(qu,qv)))
    positive=(qu!=qv)&~zero
    unique,first,inverse=np.unique(pairs[positive],axis=0,return_index=True,return_inverse=True)
    length=dd[positive][first]
    assert np.max(np.abs(length[inverse]-dd[positive]))<1e-5
    source_edge=np.full(len(dd),-1,dtype=np.int64);source_edge[positive]=inverse
    n=int(quotient.max()+1);degree=np.bincount(unique.ravel(),minlength=n)
    ptr=np.r_[0,np.cumsum(degree)].astype(np.int64);neigh=np.empty(2*len(unique),np.int64);eid=np.empty_like(neigh);cursor=ptr.copy()
    for e,(a,b) in enumerate(unique):
        k=cursor[a];neigh[k]=b;eid[k]=e;cursor[a]+=1
        k=cursor[b];neigh[k]=a;eid[k]=e;cursor[b]+=1
    important=degree!=2;original_important=important.copy();visited=np.zeros(len(unique),bool);chain_of=np.full(len(unique),-1,np.int64)
    chains=[];chain_counts=[]
    def follow(start,edge):
        node=start;previous_edge=edge;total=[];chain=[]
        while True:
            assert not visited[previous_edge];visited[previous_edge]=True;chain.append(previous_edge);total.append(length[previous_edge])
            a,b=unique[previous_edge];node=int(b if node==a else a)
            if important[node]:break
            candidates=eid[ptr[node]:ptr[node+1]];assert len(candidates)==2
            previous_edge=int(candidates[1] if candidates[0]==previous_edge else candidates[0])
        index=len(chains);chain_of[chain]=index
        chains.append((start,node,float(__import__('math').fsum(total))));chain_counts.append(len(chain))
    for node in np.flatnonzero(important):
        for e in eid[ptr[node]:ptr[node+1]]:
            if not visited[e]:follow(int(node),int(e))
    cycles=0
    for e,(a,b) in enumerate(unique):
        if not visited[e]:important[a]=True;follow(int(a),e);cycles+=1
    assert visited.all() and (chain_of>=0).all()
    retained=np.flatnonzero(important);position=np.full(n,-1,np.int64);position[retained]=np.arange(len(retained))
    cu=np.array([position[a] for a,b,d in chains],np.int64);cv=np.array([position[b] for a,b,d in chains],np.int64);cd=np.array([d for a,b,d in chains])
    assert (cd>0).all()
    cdeg=np.bincount(np.r_[cu,cv],minlength=len(retained));cp=np.r_[0,np.cumsum(cdeg)].astype(np.int64)
    cn=np.empty(2*len(cu),np.int64);ce=np.empty_like(cn);cl=np.empty(len(cn));cursor=cp.copy()
    for e,(a,b,d) in enumerate(zip(cu,cv,cd)):
        k=cursor[a];cn[k]=b;ce[k]=e;cl[k]=d;cursor[a]+=1
        k=cursor[b];cn[k]=a;ce[k]=e;cl[k]=d;cursor[b]+=1
    od=original_important[retained]
    matrix=csr_matrix((np.ones(len(cn)),cn,cp),shape=(len(retained),len(retained)))
    components,labels=connected_components(matrix,directed=False)
    np.savez_compressed(MODEL/'graph.npz',ptr=cp,neighbor=cn,edge_id=ce,length=cl,u=cu,v=cv,edge_length=cd,od=od,component=labels,
        source_u=aa,source_v=bb,source_way=way,source_length=dd,source_edge=source_edge,chain_of=chain_of,native_ids=native,quotient=quotient,retained=retained)
    (MODEL/'way-metadata.json').write_text(json.dumps(way_metadata),encoding='utf-8',newline='\n')
    report={'status':'passed','source_sha256':sha(source),'road_rows':road_rows,'original_adjacent_occurrences':len(dd),'native_nodes':len(native),
        'zero_length_occurrences':int(zero.sum()),'positive_unique_physical_edges':len(unique),'quotient_nodes':n,
        'junction_graph_vertices':len(retained),'od_junctions_and_endpoints':int(od.sum()),'junction_graph_edges':len(cu),
        'components':components,'pure_degree_two_cycle_components':cycles,'all_source_occurrences_accounted_for':True,
        'graph_sha256':sha(MODEL/'graph.npz'),'definition':'Uniform OD at every degree-not-two quotient junction/endpoint in every component. Degree-two geometry vertices are not demand; all original positive spatial edges map to complete chains. Pure cycles with no junctions have no OD pairs. Undirected full roads_context graph, not legal driving or population flow.'}
    (OUT/'graph-inventory.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2),flush=True);return report


@numba.njit(cache=True,nogil=True)
def brandes_batch(ptr,neighbor,edge_id,length,od,sources,edge_count):
    n=len(ptr)-1;result=np.zeros(edge_count);distance_sum=np.zeros(len(sources));reachable=np.zeros(len(sources),np.int64)
    for k in range(len(sources)):
        source=sources[k];dist=np.full(n,np.inf);sigma=np.zeros(n);delta=np.zeros(n)
        dist[source]=0.;sigma[source]=1.;stack=np.empty(n,np.int64);size=0
        heap=[(np.float64(0),np.int64(source))]
        while heap:
            d,node=heapq.heappop(heap)
            if d!=dist[node]:continue
            stack[size]=node;size+=1
            if od[node] and node!=source:distance_sum[k]+=d;reachable[k]+=1
            for i in range(ptr[node],ptr[node+1]):
                other=neighbor[i];candidate=d+length[i]
                if candidate<dist[other]:
                    dist[other]=candidate;sigma[other]=sigma[node];heapq.heappush(heap,(candidate,other))
                elif candidate==dist[other]:sigma[other]+=sigma[node]
        for t in range(size-1,-1,-1):
            node=stack[t]
            for i in range(ptr[node],ptr[node+1]):
                other=neighbor[i]
                if dist[other]+length[i]==dist[node]:
                    value=sigma[other]/sigma[node]*((1. if od[node] else 0.)+delta[node])
                    result[edge_id[i]]+=value;delta[other]+=value
    return result,distance_sum,reachable


def run():
    RUN.mkdir(parents=True,exist_ok=True);g=np.load(MODEL/'graph.npz');inventory=json.loads((OUT/'graph-inventory.json').read_text())
    assert sha(MODEL/'graph.npz')==inventory['graph_sha256']
    sources=np.flatnonzero(g['od']);m=len(g['u']);checkpoint=RUN/'checkpoint.npz'
    total=np.zeros(m);sums=np.full(len(sources),np.nan);counts=np.full(len(sources),-1,np.int64)
    if checkpoint.exists():
        old=np.load(checkpoint);assert str(old['graph_hash'])==inventory['graph_sha256'] and str(old['code_hash'])==sha(Path(__file__))
        total=old['centrality'];sums=old['distance_sums'];counts=old['reachable_counts']
    # Compile on a two-vertex control; timing excludes compilation.
    brandes_batch(np.array([0,1,2]),np.array([1,0]),np.array([0,0]),np.array([1.,1.]),np.ones(2,bool),np.array([0]),1)
    remaining=np.flatnonzero(counts<0);chunks=[remaining[i:i+32] for i in range(0,len(remaining),32)]
    started=time.perf_counter();completed_before=int(np.count_nonzero(counts>=0))
    args=[g[k] for k in ['ptr','neighbor','edge_id','length','od']]
    def calculate(indices):return indices,brandes_batch(*args,sources[indices],m)
    with ThreadPoolExecutor(max_workers=4) as pool:
        iterator=iter(chunks);pending={}
        for _ in range(4):
            chunk=next(iterator,None)
            if chunk is not None:pending[pool.submit(calculate,chunk)]=chunk
        while pending:
            ready,_=wait(pending,return_when=FIRST_COMPLETED)
            for future in ready:
                del pending[future];indices,(values,ds,rc)=future.result();assert np.all(counts[indices]<0)
                total+=values;sums[indices]=ds;counts[indices]=rc
                temporary=RUN/'checkpoint.next.npz'
                np.savez_compressed(temporary,centrality=total,distance_sums=sums,reachable_counts=counts,graph_hash=inventory['graph_sha256'],code_hash=sha(Path(__file__)))
                temporary.replace(checkpoint)
                done=int(np.count_nonzero(counts>=0));elapsed=time.perf_counter()-started;speed=(done-completed_before)/elapsed
                print('Exact junction sources',done,'/',len(sources),'elapsed_s',round(elapsed,1),'sources_per_s',round(speed,3),'projected_remaining_s',round((len(sources)-done)/speed,1),flush=True)
                chunk=next(iterator,None)
                if chunk is not None:pending[pool.submit(calculate,chunk)]=chunk
    assert (counts>=0).all() and np.isfinite(total).all()
    total/=2;lhs=float(np.dot(total,g['edge_length']));rhs=float(sums.sum()/2)
    assert abs(lhs-rhs)<=1e-7*max(1,rhs),(lhs,rhs)
    write_gzip_csv(OUT/'junction-centrality.csv.gz',['chain_id','u','v','length_m','edge_betweenness_raw'],[(i,int(a),int(b),d,c) for i,(a,b,d,c) in enumerate(zip(g['u'],g['v'],g['edge_length'],total))])
    write_gzip_csv(OUT/'centrality-source-census.csv.gz',['junction','reachable_other_od','sum_distance_m'],[(int(s),int(c),float(d)) for s,c,d in zip(sources,counts,sums)])
    report={'status':'passed','source_count':len(sources),'all_od_sources_computed':True,'no_sampling':True,
        'ordered_reachable_pairs':int(counts.sum()),'edge_length_betweenness_sum':lhs,'all_pair_distance_sum':rhs,
        'relative_conservation_difference':abs(lhs-rhs)/max(1,rhs),'graph_sha256':inventory['graph_sha256'],'source_code_sha256':sha(Path(__file__)),
        'artifact_sha256':{p.name:sha(p) for p in [OUT/'junction-centrality.csv.gz',OUT/'centrality-source-census.csv.gz']}}
    (OUT/'centrality-summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--build',action='store_true');parser.add_argument('--run',action='store_true');a=parser.parse_args()
    if a.build:build()
    if a.run:run()
