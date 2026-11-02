"""Complete geometry, component, district, target-mask and centrality receipts."""
import argparse
import collections
import csv
import gzip
import json
import math
from pathlib import Path
import sqlite3

import numba
import numpy as np
from pyproj import Transformer
import shapely

from .accessibility import ROOT,load_model
from .pair_closures import write_gzip_csv
from .sensitivity_runs import gp_geometry,read_gzip
from .structural_centrality import MODEL,OUT,sha


def geometry():
    g=dict(np.load(MODEL/'graph.npz'));inventory=json.loads((OUT/'graph-inventory.json').read_text())
    assert sha(MODEL/'graph.npz')==inventory['graph_sha256']
    source=ROOT/'data/extracted/tehran-osm-20261029T212126Z-v1.1-public/tehran_audited_layers.gpkg'
    assert sha(source)==inventory['source_sha256']
    db=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);project=Transformer.from_crs(4326,32639,always_xy=True)
    source_u,source_v,source_way,source_length=[g[k] for k in ['source_u','source_v','source_way','source_length']]
    pointer=0;max_difference=0.;way_rows=[]
    for wid,raw,blob in db.execute('select osm_id,attributes_json,geom from roads_context order by osm_id'):
        a=json.loads(raw);xy=np.asarray(gp_geometry(blob).coords);x,y=project.transform(xy[:,0],xy[:,1]);nodes=a['node_ids'];maximum=0.
        for i,(first,second) in enumerate(zip(nodes,nodes[1:])):
            low,high=sorted([first,second]);d=math.hypot(x[i+1]-x[i],y[i+1]-y[i])
            assert (int(source_way[pointer]),int(source_u[pointer]),int(source_v[pointer]))==(wid,low,high)
            difference=abs(source_length[pointer]-d);maximum=max(maximum,difference);assert difference<1e-5;pointer+=1
        max_difference=max(max_difference,maximum);way_rows.append((wid,len(nodes)-1,maximum))
    assert pointer==len(source_length)==968041 and len(way_rows)==218322;db.close()
    write_gzip_csv(OUT/'all-corridor-way-audit.csv.gz',['source_way','adjacent_occurrences','maximum_length_difference_m'],way_rows)
    se=g['source_edge'];positive=se>=0;canonical,first=np.unique(se[positive],return_index=True)
    assert np.array_equal(canonical,np.arange(len(g['chain_of'])))
    rows=np.flatnonzero(positive)[first];native=g['native_ids'];quotient=g['quotient']
    a=quotient[np.searchsorted(native,source_u[rows])];b=quotient[np.searchsorted(native,source_v[rows])];d=source_length[rows]
    assert np.max(np.abs(d[se[positive]]-source_length[positive]))<1e-5
    degree=np.bincount(np.r_[a,b],minlength=int(quotient.max()+1));retained=g['retained'];od=g['od']
    assert np.array_equal(od,degree[retained]!=2)
    omitted=np.ones(len(degree),bool);omitted[retained]=False;assert np.all(degree[omitted]==2)
    chain=g['chain_of'];order=np.argsort(chain,kind='stable');counts=np.bincount(chain,minlength=len(g['u']));starts=np.r_[0,np.cumsum(counts)]
    chain_rows=[];max_chain_difference=0.
    for cid in range(len(counts)):
        edges=order[starts[cid]:starts[cid+1]];adj=collections.defaultdict(list)
        for e in edges:adj[int(a[e])].append((int(b[e]),int(e)));adj[int(b[e])].append((int(a[e]),int(e)))
        start=int(retained[g['u'][cid]]);end=int(retained[g['v'][cid]]);node=start;visited=set()
        for step in range(len(edges)):
            choices=[(v,e) for v,e in adj[node] if e not in visited];assert choices
            other,e=choices[0];visited.add(e);node=other
            if node==end:assert step==len(edges)-1
            if step<len(edges)-1:assert degree[node]==2
        assert node==end and len(visited)==len(edges)
        difference=abs(math.fsum(d[edges])-g['edge_length'][cid]);assert difference<1e-5
        max_chain_difference=max(max_chain_difference,difference);chain_rows.append((cid,len(edges),difference))
    assert sum(counts)==len(canonical)
    write_gzip_csv(OUT/'all-corridor-chain-audit.csv.gz',['chain','source_physical_links','length_difference_m'],chain_rows)
    report={'status':'passed','all_road_rows':len(way_rows),'all_adjacent_occurrences':pointer,'all_canonical_links':len(canonical),
        'all_chains':len(counts),'all_chain_topologies_verified':True,'maximum_source_length_difference_m':max_difference,'maximum_chain_length_difference_m':max_chain_difference,
        'source_code_sha256':sha(Path(__file__)),'artifact_sha256':{n:sha(OUT/n) for n in ['all-corridor-way-audit.csv.gz','all-corridor-chain-audit.csv.gz']}}
    (OUT/'geometry-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print('All corridor geometry and chains passed',flush=True)


@numba.njit(cache=True)
def union_roots(n,a,b):
    parent=np.arange(n);size=np.ones(n,np.int64)
    for first,second in zip(a,b):
        while parent[first]!=first:parent[first]=parent[parent[first]];first=parent[first]
        while parent[second]!=second:parent[second]=parent[parent[second]];second=parent[second]
        if first!=second:
            if size[first]<size[second]:first,second=second,first
            parent[second]=first;size[first]+=size[second]
    for i in range(n):
        while parent[i]!=parent[parent[i]]:parent[i]=parent[parent[i]]
    return parent


def directed_parts(adjacency,strong):
    reverse=[[] for _ in adjacency]
    for a,row in enumerate(adjacency):
        for b in row:reverse[b].append(a)
    if not strong:
        seen=set();parts=[]
        for source in range(len(adjacency)):
            if source in seen:continue
            seen.add(source);stack=[source];part=[]
            while stack:
                a=stack.pop();part.append(a)
                for b in adjacency[a]+reverse[a]:
                    if b not in seen:seen.add(b);stack.append(b)
            parts.append(part)
        return parts
    seen=set();order=[]
    for source in range(len(adjacency)):
        if source in seen:continue
        seen.add(source);stack=[(source,0)]
        while stack:
            a,i=stack[-1]
            if i==len(adjacency[a]):order.append(a);stack.pop();continue
            b=adjacency[a][i];stack[-1]=(a,i+1)
            if b not in seen:seen.add(b);stack.append((b,0))
    seen=set();parts=[]
    for source in reversed(order):
        if source in seen:continue
        seen.add(source);stack=[source];part=[]
        while stack:
            a=stack.pop();part.append(a)
            for b in reverse[a]:
                if b not in seen:seen.add(b);stack.append(b)
        parts.append(part)
    return parts


def components():
    m=load_model(ROOT/'research/model/m2-v2/network.sqlite',ROOT/'research/config/baseline.json');n=len(m.adjacency)
    a=np.repeat(np.arange(n),[len(row) for row in m.adjacency]);b=np.array([v for row in m.adjacency for v,d in row],np.int64);m.adjacency=[]
    root=union_roots(n,a,b);unique,label=np.unique(root,return_inverse=True);size=np.bincount(label);count=len(unique)
    oc=np.zeros(count,np.int64);tc=np.zeros(count,np.int64);tg=collections.defaultdict(set)
    for key,row in m.connectors.items():
        if row[5]!='geometric_candidate':continue
        component=int(label[m.node_ids[row[3]]])
        if row[1]=='building':oc[component]+=1
        if row[1]=='hospital':tc[component]+=1;tg[component].add(row[2])
    expected=collections.defaultdict(collections.Counter)
    for r in read_gzip(OUT/'model-components.csv.gz'):
        expected[r['mode'],r['connectivity']][tuple(int(r[k]) for k in ['vertices','connected_buildings','target_candidate_features','possible_target_groups'])]+=1
    for mode in ['walk','bus','bus_metro']:
        allowed=set() if mode=='walk' else {'bus'} if mode=='bus' else {'bus','metro'}
        keys=[key for key in m.stop_keys if m.stop_modes[key] in allowed];ids={key:i+count for i,key in enumerate(keys)}
        adjacency=[[] for _ in range(count+len(keys))]
        for key in keys:
            s=m.stops[m.stop_ids[key]]
            if s.board:adjacency[int(label[s.anchor])].append(ids[key])
            if s.alight:adjacency[ids[key]].append(int(label[s.anchor]))
        for key,first,second,md in m.ride_rows:
            if md in allowed:adjacency[ids[first]].append(ids[second])
        for connection in ['weak','strong']:
            actual=collections.Counter()
            for part in directed_parts(adjacency,connection=='strong'):
                native=[x for x in part if x<count];groups=set().union(*(tg[v] for v in native))
                values=(int(sum(size[x] for x in native)+sum(x>=count for x in part)),int(sum(oc[x] for x in native)),int(sum(tc[x] for x in native)),len(groups))
                actual[values]+=1
            assert actual==expected[mode,connection],(mode,connection)
    print('All component partitions match independent union-find/Kosaraju replay',flush=True)


def descriptives():
    summary=json.loads((OUT/'descriptive-summary.json').read_text());assert summary['status']=='passed'
    for name,digest in summary['artifact_sha256'].items():assert sha(OUT/name)==digest
    owners=read_gzip(OUT/'building-district-ownership.csv.gz');ids=[r['origin'] for r in owners];assert len(ids)==len(set(ids))==65677
    owner=np.array([int(r['district']) for r in owners]);index=json.loads((OUT/'district-index.json').read_text())
    source=ROOT/'data/extracted/tehran-osm-20261029T212126Z-v1.1-public/tehran_audited_layers.gpkg';db=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    polygons={i:gp_geometry(blob) for i,blob in db.execute('select osm_id,geom from municipal_districts')}
    points=shapely.points(np.array([[float(r['point_lon']),float(r['point_lat'])] for r in owners]));expected=np.zeros(len(ids),np.int64)
    for district in sorted(index['districts'],key=lambda r:-r['district']):expected[shapely.covers(polygons[district['relation_id']],points)]=district['district']
    assert np.array_equal(owner,expected)
    city=gp_geometry(db.execute('select geom from city_boundary').fetchone()[0]);inside=shapely.covers(city,points)
    unassigned_inside=int(np.count_nonzero((owner==0)&inside));unassigned_outside=int(np.count_nonzero((owner==0)&~inside));db.close()
    npz=np.load(OUT/'hospital-group-reachability-masks.npz');mask_index=json.loads((OUT/'target-group-mask-index.json').read_text())
    coverage={(r['group'],r['mode'],int(r['max_boardings']),int(r['walking_budget_m'])):int(r['accessible_origins']) for r in read_gzip(OUT/'target-group-coverage.csv.gz')}
    groups=mask_index['groups'];counts=np.zeros((2,4,3,len(ids)),np.uint16);checked=0
    for gi,group in enumerate(groups):
        for md,mode in enumerate(['bus','bus_metro']):
            for b in range(4):
                for j,w in enumerate([500,1000,2000]):
                    raw=npz[f'g{gi}_{mode}_b{b}_w{w}'];bits=np.unpackbits(raw,bitorder='little');assert bits[len(ids):].sum()==0
                    bits=bits[:len(ids)];assert int(bits.sum())==coverage[group,mode,b,w]
                    counts[md,b,j]+=bits;checked+=1
    assert checked==len(npz.files)==5664
    rows=read_gzip(OUT/'building-reachable-target-groups.csv.gz');assert [r['origin'] for r in rows]==ids
    for i,r in enumerate(rows):
        for md,mode in enumerate(['bus','bus_metro']):
            for b in range(4):
                for j,w in enumerate([500,1000,2000]):assert int(r[f'{mode}_b{b}_w{w}'])==counts[md,b,j,i]
    # Independent older full-node solver vectors, already frozen before this task.
    baseline=ROOT/'research/runs/m3-baseline-v1';prior=json.loads((baseline/'summary.json').read_text());assert prior['network_sha256']==summary['network_sha256']
    with (baseline/'building_costs.csv').open(newline='') as f:old={r['building']:r for r in csv.DictReader(f)}
    assert set(old)==set(ids)
    for md,mode in enumerate(['bus','bus_metro']):
        for b in range(4):
            cost=np.array([float(old[key][f'{mode}_boardings_{b}']) if old[key][f'{mode}_boardings_{b}'] else np.inf for key in ids])
            for j,w in enumerate([500,1000,2000]):assert np.array_equal(counts[md,b,j]>0,cost<=w)
    denominator=np.bincount(owner,minlength=23)
    for r in read_gzip(OUT/'district-baseline.csv.gz'):
        district=int(r['district']);md=['bus','bus_metro'].index(r['mode']);b=int(r['max_line_changes'])+1;j=[500,1000,2000].index(int(r['walking_budget_m']));values=counts[md,b,j,owner==district]
        assert int(r['buildings'])==denominator[district] and int(r['accessible_buildings'])==np.count_nonzero(values)
        if len(values):assert abs(float(r['mean_reachable_candidate_groups'])-float(values.mean()))<1e-12
    old_index=json.loads((ROOT/'research/reports/sensitivity-2026-11-01/mask-index.json').read_text());lookup={key:i for i,key in enumerate(ids)}
    old_owner=np.array([owner[lookup[key]] for key in old_index['origins']]);group_map={r['signature']:r['group_index'] for r in old_index['groups']}
    bysetting=collections.defaultdict(list);actual_rows=0
    with np.load(ROOT/'research/reports/sensitivity-2026-11-01/single-loss-masks.npz') as old_masks:
        for r in read_gzip(OUT/'district-single-losses.csv.gz'):
            key=(r['signature'],r['mode'],int(r['max_line_changes']),int(r['walking_budget_m']));bysetting[key].append(r)
        for (signature,mode,k,w),records in bysetting.items():
            assert len(records)==23 and {int(r['district']) for r in records}==set(range(23))
            mask=np.unpackbits(old_masks[f'g{group_map[signature]}_{mode}_k{k}_w{w}'],bitorder='little')[:len(old_owner)]
            loss=np.bincount(old_owner,weights=mask,minlength=23).astype(int)
            for r in records:assert int(r['lost_buildings'])==loss[int(r['district'])];actual_rows+=1
    assert actual_rows==98532
    components()
    report={'status':'passed','all_origin_ownerships_checked':len(ids),'all_target_masks_decoded':checked,'all_candidate_group_counts_checked':len(ids)*24,
        'target_union_matches_prior_full_solver_vectors':True,'all_district_effect_rows_checked':actual_rows,'independent_component_replay':'union-find walking components, then directed quotient-graph DFS/Kosaraju',
        'unassigned_inside_city_district_gaps':unassigned_inside,'unassigned_outside_city_points':unassigned_outside,
        'source_code_sha256':sha(Path(__file__)),'prior_baseline_cost_table_sha256':sha(baseline/'building_costs.csv')}
    (OUT/'descriptive-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report),flush=True)


def centrality():
    g=dict(np.load(MODEL/'graph.npz'));b=dict(np.load(MODEL/'blocks.npz'));membership=b['membership'];weights=b['weights'];labels=g['component'];od=g['od'];n=len(od)
    total=np.bincount(labels,weights=od).astype(np.int64);nb=len(b['edge_counts'])
    block_total=np.bincount(membership[:,0],weights=weights,minlength=nb).astype(np.int64)
    for block,node in membership:assert block_total[block]==total[labels[node]]
    away=np.bincount(membership[:,1],weights=total[labels[membership[:,1]]]-weights,minlength=n).astype(np.int64)
    assert np.array_equal(away+od,total[labels])
    write_gzip_csv(OUT/'block-attachment-masses.csv.gz',['block','junction','projected_od_weight','component_od_total'],[(int(block),int(node),int(weight),int(total[labels[node]])) for (block,node),weight in zip(membership,weights)])
    result=read_gzip(OUT/'junction-centrality.csv.gz');assert len(result)==len(g['u'])
    value=np.array([float(r['edge_betweenness_raw']) for r in result]);assert np.isfinite(value).all() and (value>=0).all()
    np.testing.assert_allclose([float(r['length_m']) for r in result],g['edge_length'],rtol=0,atol=0)
    edge_block=b['edge_block'];ec=b['edge_counts'];member_ptr=np.r_[0,np.cumsum(np.bincount(membership[:,0],minlength=nb))]
    bridges=[]
    for e,block in enumerate(edge_block):
        if block<0:assert g['u'][e]==g['v'][e] and value[e]==0;continue
        if ec[block]==1:
            w=weights[member_ptr[block]:member_ptr[block+1]];assert len(w)==2
            expected=int(w[0])*int(w[1]);assert value[e]==expected
            bridges.append((e,int(block),int(w[0]),int(w[1]),expected))
    write_gzip_csv(OUT/'bridge-centrality-audit.csv.gz',['chain','block','first_branch_od','second_branch_od','edge_betweenness'],bridges)
    sources=read_gzip(OUT/'centrality-source-census.csv.gz');seen=set();expected={(int(block),int(node)):int(weight) for (block,node),weight in zip(membership,weights) if ec[block]>1 and weight>0}
    ds=0.
    for r in sources:
        key=int(r['block']),int(r['junction']);assert key not in seen and int(r['projected_od_weight'])==expected[key]
        seen.add(key);ds+=float(r['weighted_distance_sum_m'])/2
    assert seen==set(expected)
    ds+=math.fsum(float(row[-1])*g['edge_length'][row[0]] for row in bridges)
    lhs=float(np.dot(value,g['edge_length']));assert abs(lhs-ds)<1e-7*max(1,ds)
    summary=json.loads((OUT/'centrality-summary.json').read_text());assert summary['status']=='passed' and summary['all_tasks_completed']
    for name,digest in summary['artifact_sha256'].items():assert sha(OUT/name)==digest
    report={'status':'passed','all_attachment_mass_rows':len(membership),'all_original_od_mass_preserved':int(od.sum()),'all_bridge_products_verified':len(bridges),
        'all_projected_source_rows_verified':len(sources),'all_chain_scores_checked':len(result),'relative_global_distance_conservation_error':abs(lhs-ds)/max(1,ds),
        'block_weight_check':'Every block partitions its component OD mass; every original vertex satisfies branch-flow conservation. The block-cut graph is a forest, so these mass messages are uniquely determined.',
        'source_code_sha256':sha(Path(__file__)),'artifact_sha256':{name:sha(OUT/name) for name in ['block-attachment-masses.csv.gz','bridge-centrality-audit.csv.gz']}}
    (OUT/'centrality-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--geometry',action='store_true');p.add_argument('--descriptives',action='store_true');p.add_argument('--centrality',action='store_true');a=p.parse_args()
    if a.geometry:geometry()
    if a.descriptives:descriptives()
    if a.centrality:centrality()
