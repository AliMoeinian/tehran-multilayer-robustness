"""Full-node shortest-path certificates for every origin in registered cases.

Witnesses minimize cumulative walking, not riding distance or travel time.
Strict improvements produce an acyclic predecessor forest even at zero cost.
"""
import collections
import csv
import gzip
import hashlib
import heapq
import json
import sqlite3
import time

import numba
import numpy as np

from .accessibility import ROOT, load_model
from .compact_accessibility import CompactModel
from .compiled_compact import evaluate
from .pair_closures import write_gzip_csv
from .single_closures import retained_rides


@numba.njit(cache=True, nogil=True)
def relax_parents(ptr, other, length, edge_ids, initial, seeds, costs, cutoff):
    distances=initial.copy()
    parent=np.full(len(initial),-1,np.int64)
    edge=np.full(len(initial),-1,np.int64)
    heap=[(np.float64(0),np.int64(0))];heap.pop()
    for i in range(len(seeds)):
        n=seeds[i];d=costs[i]
        if d<=cutoff and d<distances[n]:
            distances[n]=d;parent[n]=-2;edge[n]=i
            heapq.heappush(heap,(d,n))
    while heap:
        d,n=heapq.heappop(heap)
        if d!=distances[n]:continue
        for e in range(ptr[n],ptr[n+1]):
            v=other[e];candidate=d+length[e]
            if candidate<=cutoff and candidate<distances[v]:
                distances[v]=candidate;parent[v]=n;edge[v]=edge_ids[e]
                heapq.heappush(heap,(candidate,v))
    return distances,parent,edge


@numba.njit(cache=True,nogil=True)
def solve_witness(ptr,other,length,edge_ids,anchors,access,board,alight,
                  ride_start,ride_end,enabled,target_nodes,target_costs,max_b,cutoff):
    n=len(ptr)-1;s=len(anchors)
    dist=np.full((max_b+1,n),np.inf)
    parent=np.full((max_b+1,n),-1,np.int64)
    edge=np.full((max_b+1,n),-1,np.int64)
    onparent=np.full((max_b+1,s),-1,np.int64)
    dist[0],parent[0],edge[0]=relax_parents(ptr,other,length,edge_ids,dist[0],target_nodes,target_costs,cutoff)
    for b in range(1,max_b+1):
        onboard=np.full(s,np.inf)
        heap=[(np.float64(0),np.int64(0))];heap.pop()
        for i in range(s):
            if alight[i]:
                d=access[i]+dist[b-1,anchors[i]]
                if d<=cutoff:onboard[i]=d;heapq.heappush(heap,(d,np.int64(i)))
        while heap:
            d,node=heapq.heappop(heap)
            if d!=onboard[node]:continue
            for e in range(len(ride_start)):
                if enabled[e] and ride_end[e]==node:
                    v=ride_start[e]
                    if d<onboard[v]:
                        onboard[v]=d;onparent[b,v]=e;heapq.heappush(heap,(d,v))
        seeds=anchors.copy();costs=np.full(s,np.inf)
        for i in range(s):
            if board[i]:costs[i]=access[i]+onboard[i]
            if seeds[i]<0:seeds[i]=0
        dist[b],parent[b],edge[b]=relax_parents(ptr,other,length,edge_ids,dist[b-1],seeds,costs,cutoff)
    return dist,parent,edge,onparent


def run():
    started=time.perf_counter();out=ROOT/'research/reports/sensitivity-2026-11-01'
    m=load_model(ROOT/'research/model/m2-v2/network.sqlite',ROOT/'research/config/baseline.json')
    origins=[r for r in m.connectors.values() if r[1]=='building' and r[5]=='geometric_candidate']
    anchors=np.array([m.node_ids[r[3]] for r in origins]);access=np.array([r[4] for r in origins])
    compact=CompactModel(m.adjacency,m.stops,m.targets,anchors,access,2000.)
    groups=json.loads((ROOT/'research/reports/m3-single-closures-2026-11-01/groups.json').read_text())
    registry=json.loads((out/'path-case-registry.json').read_text())
    signatures=[tuple(g['failed_connections']) for g in groups]
    failures={()}
    for r in registry['pairs']:
        a,b=signatures[r['first_group']],signatures[r['second_group']]
        failures.update([a,b,tuple(sorted(set(a)|set(b)))])
    failures.update(signatures[r['group_index']] for r in registry['negative_delta_singles'])
    modes={'bus':{'bus'},'bus_metro':{'bus','metro'}}
    stop_allowed={name:np.array([m.stop_modes[k] in allowed for k in m.stop_keys]) for name,allowed in modes.items()}
    values={}
    for failed in sorted(failures):
        for mode,allowed in modes.items():
            rides=retained_rides(m.ride_rows,m.stop_ids,allowed,set(failed))
            values[failed,mode]=evaluate(compact,m.stops,rides,2,2000.,stop_allowed[mode])
    del compact
    requests=collections.defaultdict(set);members=[];case_summary=[]
    for i,case in enumerate(registry['pairs']):
        a,b=signatures[case['first_group']],signatures[case['second_group']]
        joint=tuple(sorted(set(a)|set(b)));label=f'pair-{i}'
        for mode in modes:
            base=values[(),mode][2]<=1000
            first=base&(values[a,mode][2]>1000);second=base&(values[b,mode][2]>1000)
            lost=base&(values[joint,mode][2]>1000)
            new=lost&~first&~second;shared=first&second
            case_summary.append({'case':label,'mode':mode,'affected_origins':int(lost.sum()),
                'shared_single_losses':int(shared.sum()),'new_joint_only_losses':int(new.sum()),
                'interaction':int(new.sum()-shared.sum())})
            for j in np.flatnonzero(lost):
                kind='shared' if shared[j] else 'joint_only' if new[j] else 'one_single'
                members.append((label,mode,origins[j][0],kind))
                for failed in [(),a,b,joint]:requests[failed,mode].add(int(j))
    for case in registry['negative_delta_singles']:
        failed=signatures[case['group_index']];label=f"negative-delta-{case['group_index']}"
        busbase=values[(),'bus'][2]<=1000;fullbase=values[(),'bus_metro'][2]<=1000
        buslost=busbase&(values[failed,'bus'][2]>1000)
        fulllost=fullbase&(values[failed,'bus_metro'][2]>1000)
        extra=fulllost&~busbase;rescued=buslost&~fulllost
        assert int(buslost.sum()-fulllost.sum())==int(rescued.sum()-extra.sum())
        case_summary.append({'case':label,'bus_loss':int(buslost.sum()),'bus_metro_loss':int(fulllost.sum()),
            'extra_full_baseline_lost':int(extra.sum()),'bus_loss_rescued':int(rescued.sum())})
        for j in np.flatnonzero(buslost|fulllost):
            kind='extra_full_baseline_lost' if extra[j] else 'bus_loss_rescued' if rescued[j] else 'common_loss'
            members.append((label,'comparison',origins[j][0],kind))
            for mode in modes:
                for f in [(),failed]:requests[f,mode].add(int(j))
    write_gzip_csv(out/'path-case-members.csv.gz',['case','mode','origin','category'],members)
    db=sqlite3.connect((ROOT/'research/model/m2-v2/network.sqlite').as_uri()+'?mode=ro',uri=True)
    walk_rows=list(db.execute('select edge_id,u,v,length_m from walk_edges'));db.close()
    adj=[[] for _ in m.adjacency];edge_lengths={}
    for eid,u,v,d in walk_rows:
        u,v=m.node_ids[u],m.node_ids[v];adj[u].append((v,d,eid));adj[v].append((u,d,eid));edge_lengths[eid]=d
    ptr=np.r_[0,np.cumsum([len(row) for row in adj])].astype(np.int64)
    other=np.array([v for row in adj for v,d,eid in row],dtype=np.int64)
    lengths=np.array([d for row in adj for v,d,eid in row])
    edge_ids=np.array([eid for row in adj for v,d,eid in row],dtype=np.int64)
    del adj,walk_rows;m.adjacency=[]
    sa=np.array([s.anchor for s in m.stops],dtype=np.int64);sc=np.array([s.access_m for s in m.stops])
    rs=np.array([m.stop_ids[a] for key,a,b,mode in m.ride_rows]);re=np.array([m.stop_ids[b] for key,a,b,mode in m.ride_rows])
    targets=[r for r in m.connectors.values() if r[1]=='hospital' and r[5]=='geometric_candidate']
    tn=np.array([m.node_ids[r[3]] for r in targets]);tc=np.array([r[4] for r in targets])
    failed_ids={f:hashlib.sha256(json.dumps(f,separators=(',',':')).encode()).hexdigest() for f in failures}
    witness_count=0;success=0;max_difference=0.;ride_patterns=collections.Counter();used_edges=set();used_origins=set();used_targets=set()
    with gzip.open(out/'path-witnesses.jsonl.gz','wt',encoding='utf-8',newline='') as stream:
        for number,((failed,mode),selected) in enumerate(sorted(requests.items()),1):
            enabled=np.array([md in modes[mode] and key not in failed for key,a,b,md in m.ride_rows])
            board=np.array([s.board for s in m.stops])&stop_allowed[mode]
            alight=np.array([s.alight for s in m.stops])&stop_allowed[mode]
            dist,parent,edge,onparent=solve_witness(ptr,other,lengths,edge_ids,sa,sc,board,alight,rs,re,enabled,tn,tc,2,2000.)
            projected=dist[:,anchors]+access
            projected[projected>2000]=np.inf
            reference=values[failed,mode]
            assert np.array_equal(np.isfinite(projected),np.isfinite(reference))
            finite=np.isfinite(reference)
            difference=float(np.max(np.abs(projected[finite]-reference[finite])))
            assert difference<1e-8;max_difference=max(max_difference,difference)
            assert np.array_equal(projected<=1000,reference<=1000)
            for j in sorted(selected):
                value=projected[2,j];record={'origin':origins[j][0],'mode':mode,'failed_set':failed_ids[failed],
                    'minimum_walking_m':float(value) if np.isfinite(value) else None,'accessible_1000m':bool(value<=1000)}
                if value<=1000:
                    node=int(anchors[j]);b=2;cost=float(access[j]);legs=[];boardings=0;ride_modes=[];visits=0
                    while True:
                        visits+=1;assert visits<100000
                        nxt=int(parent[b,node])
                        if nxt>=0:
                            eid=int(edge[b,node]);d=edge_lengths[eid];cost+=d;used_edges.add(eid)
                            if legs and legs[-1]['kind']=='walk':legs[-1]['edge_ids'].append(eid);legs[-1]['length_m']+=d
                            else:legs.append({'kind':'walk','edge_ids':[eid],'length_m':d})
                            node=nxt;continue
                        if nxt==-1:
                            assert b>0;b-=1;continue
                        seed=int(edge[b,node])
                        if b==0:
                            target=targets[seed];assert node==tn[seed];cost+=target[4]
                            record['target']=target[0];record['target_connector_m']=target[4];used_targets.add(target[0]);break
                        stop=seed;assert board[stop] and node==sa[stop]
                        cost+=sc[stop];boardings+=1;boarding=stop;connections=[]
                        while onparent[b,stop]>=0:
                            e=int(onparent[b,stop]);assert enabled[e] and rs[e]==stop
                            connections.append(m.ride_rows[e][0]);stop=int(re[e])
                            assert len(connections)<=len(m.ride_rows)
                        assert alight[stop];cost+=sc[stop]
                        if connections:ride_modes.append(m.stop_modes[m.stop_keys[boarding]])
                        legs.append({'kind':'ride','board_stop':m.stop_keys[boarding],'alight_stop':m.stop_keys[stop],
                            'board_connector_m':float(sc[boarding]),'alight_connector_m':float(sc[stop]),'connection_ids':connections})
                        node=int(sa[stop]);b-=1
                    assert boardings<=2 and abs(cost-value)<1e-7
                    record.update({'origin_connector_m':float(access[j]),'legs':legs,'boardings':boardings,'walking_cost_sum_m':cost,
                        'riding_mode_sequence':ride_modes})
                    ride_patterns[','.join(ride_modes) or 'walk']+=1;success+=1;used_origins.add(origins[j][0])
                stream.write(json.dumps(record,separators=(',',':'))+'\n');witness_count+=1
            print('Path certificates',number,'/',len(requests),'origins',len(selected),flush=True)
    (out/'path-failed-sets.json').write_text(json.dumps({failed_ids[f]:list(f) for f in sorted(failures)},indent=2)+'\n',encoding='utf-8')
    report={'status':'passed','case_rule':registry['rule'],'pair_cases':len(registry['pairs']),
        'negative_delta_cases':len(registry['negative_delta_singles']),'unique_state_mode_requests':len(requests),
        'case_origin_memberships':len(members),'origin_state_certificates':witness_count,'successful_paths':success,
        'maximum_compact_full_walking_difference_m':max_difference,'walking_edge_ids_used':len(used_edges),
        'riding_mode_sequences':dict(ride_patterns),'case_results':case_summary,
        'unreachable_meaning':'No path within 1000m walking and two boardings; null minimum means no path within the 2000m search cutoff.',
        'tie_policy':'One deterministic shortest-walking witness, not every tied path; riding distance is not optimized.',
        'network_sha256':m.network_hash,
        'elapsed_seconds':time.perf_counter()-started}
    from pathlib import Path
    report['source_code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['artifact_sha256']={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in
        ['path-case-members.csv.gz','path-case-registry.json','path-failed-sets.json','path-witnesses.jsonl.gz']}
    (out/'path-summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Completed all registered path cases',witness_count,flush=True)
    return report


if __name__=='__main__':run()
