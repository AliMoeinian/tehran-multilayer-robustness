"""Exact articulation/block decomposition, retaining all junction OD mass."""
import json
import time
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
import numba
import numpy as np
from scipy.sparse import csr_matrix
from .structural_centrality import MODEL,OUT
from .structural_centrality import RUN,sha
from .pair_closures import write_gzip_csv
from pathlib import Path


@numba.njit(cache=True)
def edge_blocks(ptr,neighbor,edge_id,m):
    n=len(ptr)-1;disc=np.full(n,-1,np.int64);low=np.zeros(n,np.int64)
    parent=np.full(n,-1,np.int64);pe=np.full(n,-1,np.int64);cursor=ptr[:-1].copy()
    nodes=np.empty(n,np.int64);estack=np.empty(m,np.int64);es=0
    block=np.full(m,-1,np.int64);clock=0;nb=0
    for root in range(n):
        if disc[root]>=0:continue
        disc[root]=clock;low[root]=clock;clock+=1;nodes[0]=root;size=1
        while size:
            node=nodes[size-1]
            if cursor[node]<ptr[node+1]:
                pos=cursor[node];cursor[node]+=1;v=neighbor[pos];e=edge_id[pos]
                if v==node:continue
                if disc[v]<0:
                    parent[v]=node;pe[v]=e;estack[es]=e;es+=1
                    disc[v]=clock;low[v]=clock;clock+=1;nodes[size]=v;size+=1
                elif e!=pe[node] and disc[v]<disc[node]:
                    estack[es]=e;es+=1;low[node]=min(low[node],disc[v])
            else:
                size-=1;p=parent[node]
                if p>=0:
                    low[p]=min(low[p],low[node])
                    if low[node]>=disc[p]:
                        while True:
                            es-=1;e=estack[es];block[e]=nb
                            if e==pe[node]:break
                        nb+=1
        assert es==0
    return block,nb


@numba.njit(cache=True)
def tree_masses(ptr,neighbor,od,n_original):
    n=len(ptr)-1;parent=np.full(n,-1,np.int64);root_of=np.full(n,-1,np.int64)
    order=np.empty(n,np.int64);size=0;roots=0
    for root in range(n):
        if root_of[root]>=0:continue
        roots+=1;start=size;order[size]=root;size+=1;root_of[root]=root;cursor=start
        while cursor<size:
            node=order[cursor];cursor+=1
            for i in range(ptr[node],ptr[node+1]):
                v=neighbor[i]
                if v==parent[node]:continue
                assert root_of[v]<0
                parent[v]=node;root_of[v]=root;order[size]=v;size+=1
    mass=np.zeros(n,np.int64);mass[:n_original]=od
    for i in range(size-1,-1,-1):
        node=order[i]
        if parent[node]>=0:mass[parent[node]]+=mass[node]
    return parent,root_of,mass,roots


def build():
    g=np.load(MODEL/'graph.npz');u,v=g['u'],g['v'];n=len(g['od'])
    block,nb=edge_blocks(g['ptr'],g['neighbor'],g['edge_id'],len(u))
    assert np.array_equal(block<0,u==v)
    valid=block>=0;membership=np.unique(np.r_[np.column_stack((block[valid],u[valid])),np.column_stack((block[valid],v[valid]))],axis=0)
    bnodes=n+membership[:,0];vnodes=membership[:,1]
    tree=csr_matrix((np.ones(2*len(membership)),(np.r_[bnodes,vnodes],np.r_[vnodes,bnodes])),shape=(n+nb,n+nb))
    parent,root_of,mass,roots=tree_masses(tree.indptr.astype(np.int64),tree.indices.astype(np.int64),g['od'],n)
    assert len(membership)==n+nb-roots
    weights=np.empty(len(membership),np.int64)
    for i,(b,node) in enumerate(membership):
        bn=n+b
        if parent[node]==bn:weights[i]=mass[node]
        else:assert parent[bn]==node;weights[i]=mass[root_of[bn]]-mass[bn]
    ec=np.bincount(block[valid],minlength=nb);vc=np.bincount(membership[:,0],minlength=nb)
    totals=np.bincount(membership[:,0],weights=weights,minlength=nb).astype(np.int64)
    assert all(totals[b]==mass[root_of[n+b]] for b in range(nb))
    np.savez_compressed(MODEL/'blocks.npz',edge_block=block,membership=membership,weights=weights,edge_counts=ec,vertex_counts=vc)
    order=np.argsort(vc)[::-1]
    report={'status':'passed','blocks':nb,'bridge_blocks':int(np.count_nonzero(ec==1)),
        'nontrivial_blocks':int(np.count_nonzero(ec>1)),
        'largest_blocks':[{'block':int(b),'vertices':int(vc[b]),'edges':int(ec[b]),'projected_od_mass':int(totals[b])} for b in order[:10]],
        'identity':'In each block, attachment weight at v is all original OD mass in the corresponding block-cut-tree branch. Sum of attachment weights equals the original connected-component OD mass. Bridges have betweenness equal to the product of their two branch masses.'}
    (OUT/'block-inventory.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report,indent=2),flush=True)
    return report


@numba.njit(cache=True,nogil=True)
def weighted_batch(ptr,neighbor,eid,length,weights,sources,m):
    n=len(ptr)-1;out=np.zeros(m);sums=np.zeros(len(sources))
    for k in range(len(sources)):
        source=sources[k];dist=np.full(n,np.inf);sigma=np.zeros(n);delta=np.zeros(n)
        heap=np.empty(n,np.int64);position=np.full(n,-1,np.int64);stack=np.empty(n,np.int64)
        dist[source]=0.;sigma[source]=1.;heap[0]=source;position[source]=0;size=1;count=0
        while size:
            node=heap[0];size-=1;position[node]=-2;stack[count]=node;count+=1
            if size:
                value=heap[size];heap[0]=value;position[value]=0;p=0
                while True:
                    left=2*p+1
                    if left>=size:break
                    right=left+1;child=left
                    if right<size:
                        a,b=heap[right],heap[left]
                        if dist[a]<dist[b] or (dist[a]==dist[b] and a<b):child=right
                    a,b=heap[child],heap[p]
                    if dist[a]>dist[b] or (dist[a]==dist[b] and a>=b):break
                    heap[p],heap[child]=a,b;position[a]=p;position[b]=child;p=child
            sums[k]+=weights[source]*weights[node]*dist[node]
            for i in range(ptr[node],ptr[node+1]):
                other=neighbor[i];candidate=dist[node]+length[i]
                if candidate<dist[other]:
                    assert position[other]!=-2
                    dist[other]=candidate;sigma[other]=sigma[node]
                    p=position[other]
                    if p<0:p=size;heap[p]=other;position[other]=p;size+=1
                    while p:
                        q=(p-1)//2;a,b=heap[p],heap[q]
                        if dist[a]>dist[b] or (dist[a]==dist[b] and a>=b):break
                        heap[p],heap[q]=b,a;position[a]=q;position[b]=p;p=q
                elif candidate==dist[other]:sigma[other]+=sigma[node]
        for t in range(count-1,-1,-1):
            node=stack[t];assert np.isfinite(sigma[node])
            for i in range(ptr[node],ptr[node+1]):
                other=neighbor[i]
                if dist[other]+length[i]==dist[node]:
                    value=sigma[other]/sigma[node]*(weights[node]+delta[node])
                    out[eid[i]]+=weights[source]*value;delta[other]+=value
    return out,sums


def block_graph(g,b,edge_indices,membership,weights):
    vertices=membership[:,1];u=np.searchsorted(vertices,g['u'][edge_indices]);v=np.searchsorted(vertices,g['v'][edge_indices]);d=g['edge_length'][edge_indices]
    a=np.r_[u,v];other=np.r_[v,u];e=np.r_[np.arange(len(u)),np.arange(len(u))];length=np.r_[d,d]
    order=np.argsort(a,kind='stable');ptr=np.r_[0,np.cumsum(np.bincount(a,minlength=len(vertices)))].astype(np.int64)
    return ptr,other[order].astype(np.int64),e[order].astype(np.int64),length[order],weights.astype(float)


def run():
    graph_hash=sha(MODEL/'graph.npz');blocks_hash=sha(MODEL/'blocks.npz');code_hash=sha(Path(__file__))
    g={k:v for k,v in np.load(MODEL/'graph.npz').items() if k in ['u','v','edge_length','od']}
    b=np.load(MODEL/'blocks.npz');membership=b['membership'];weights=b['weights'];edge_block=b['edge_block'];ec=b['edge_counts']
    nb=len(ec);member_ptr=np.r_[0,np.cumsum(np.bincount(membership[:,0],minlength=nb))]
    valid=np.flatnonzero(edge_block>=0);edge_order=valid[np.argsort(edge_block[valid],kind='stable')];edge_ptr=np.r_[0,np.cumsum(ec)]
    result=np.zeros(len(g['u']));distance_sum=0.;bridge_count=0
    tasks=[];prepared={};ledger=[];nontrivial=np.flatnonzero(ec>1)
    # Largest block first provides an honest steady-state runtime measurement.
    for block in np.flatnonzero(ec==1):
        lo,hi=member_ptr[block:block+2];w=weights[lo:hi];assert len(w)==2
        e=edge_order[edge_ptr[block]];value=float(w[0])*float(w[1]);result[e]=value;distance_sum+=value*g['edge_length'][e];bridge_count+=1
    for block in sorted(nontrivial,key=lambda x:-int(b['vertex_counts'][x])):
        lo,hi=member_ptr[block:block+2];rows=membership[lo:hi];w=weights[lo:hi]
        edges=edge_order[edge_ptr[block]:edge_ptr[block+1]]
        prepared[int(block)]=(block_graph(g,block,edges,rows,w),edges,rows[:,1],w)
        sources=np.flatnonzero(w>0)
        for i in range(0,len(sources),32):tasks.append((int(block),sources[i:i+32]))
    checkpoint=RUN/'block-checkpoint.npz';done=np.zeros(len(tasks),bool)
    if checkpoint.exists():
        saved=np.load(checkpoint);assert str(saved['code_sha256'])==sha(Path(__file__))
        assert str(saved['graph_sha256'])==sha(MODEL/'graph.npz') and str(saved['blocks_sha256'])==sha(MODEL/'blocks.npz')
        result=saved['result'];distance_sum=float(saved['distance_sum']);done=saved['done'];ledger=saved['ledger'].tolist()
        saved.close()  # Windows cannot replace an open checkpoint archive.
    weighted_batch(np.array([0,1,2]),np.array([1,0]),np.array([0,0]),np.ones(2),np.ones(2),np.array([0]),1)
    def calculate(index):
        block,sources=tasks[index];arrays,edges,vertices,w=prepared[block]
        return index,weighted_batch(*arrays,sources,len(edges))
    remaining=iter(np.flatnonzero(~done));started=time.perf_counter();processed=0;last_checkpoint=started
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending={}
        for _ in range(4):
            i=next(remaining,None)
            if i is not None:pending[pool.submit(calculate,int(i))]=i
        while pending:
            ready,_=wait(pending,return_when=FIRST_COMPLETED)
            for future in ready:
                del pending[future];index,(values,ds)=future.result();assert not done[index]
                block,sources=tasks[index];arrays,edges,vertices,w=prepared[block]
                result[edges]+=values/2;distance_sum+=float(ds.sum()/2);done[index]=True
                ledger.extend((block,int(vertices[s]),int(w[s]),float(d)) for s,d in zip(sources,ds));processed+=len(sources)
                if time.perf_counter()-last_checkpoint>30 or done.all():
                    temp=RUN/'block-checkpoint.next.npz';np.savez_compressed(temp,result=result,distance_sum=distance_sum,done=done,ledger=np.array(ledger),code_sha256=code_hash,graph_sha256=graph_hash,blocks_sha256=blocks_hash);temp.replace(checkpoint);last_checkpoint=time.perf_counter()
                elapsed=time.perf_counter()-started;speed=processed/elapsed
                print('Exact projected block sources',len(ledger),'/',sum(len(t[1]) for t in tasks),'tasks',int(done.sum()),'/',len(tasks),'sources_per_s',round(speed,2),'remaining_s',round(sum(len(tasks[i][1]) for i in np.flatnonzero(~done))/speed),flush=True)
                i=next(remaining,None)
                if i is not None:pending[pool.submit(calculate,int(i))]=i
    lhs=float(np.dot(result,g['edge_length']));assert abs(lhs-distance_sum)<1e-7*max(1,distance_sum)
    write_gzip_csv(OUT/'junction-centrality.csv.gz',['chain_id','u','v','length_m','edge_betweenness_raw'],[(i,int(a),int(c),d,value) for i,(a,c,d,value) in enumerate(zip(g['u'],g['v'],g['edge_length'],result))])
    write_gzip_csv(OUT/'centrality-source-census.csv.gz',['block','junction','projected_od_weight','weighted_distance_sum_m'],[(int(a),int(c),int(w),float(d)) for a,c,w,d in ledger])
    report={'status':'passed','method':'Exact weighted block-cut decomposition; bridge products and all nontrivial-block projected OD sources',
        'original_od_junctions':int(g['od'].sum()),'projected_block_sources':len(ledger),'bridge_blocks_solved_analytically':bridge_count,
        'all_nontrivial_blocks':len(nontrivial),'all_tasks_completed':bool(done.all()),'no_sampling':True,
        'edge_length_betweenness_sum':lhs,'all_pair_distance_sum':distance_sum,'relative_conservation_difference':abs(lhs-distance_sum)/max(1,distance_sum),
        'graph_sha256':sha(MODEL/'graph.npz'),'blocks_sha256':sha(MODEL/'blocks.npz'),'source_code_sha256':sha(Path(__file__)),
        'artifact_sha256':{p.name:sha(p) for p in [OUT/'junction-centrality.csv.gz',OUT/'centrality-source-census.csv.gz']}}
    (OUT/'centrality-summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report),flush=True)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--run',action='store_true');a=p.parse_args();run() if a.run else build()
