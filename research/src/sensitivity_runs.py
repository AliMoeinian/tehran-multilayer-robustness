"""Exhaustive one-factor sensitivity censuses on declared closure domains."""
from concurrent.futures import ThreadPoolExecutor
import collections
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
from pyproj import Transformer
import shapely
from shapely.ops import substring,transform
import sqlite3

from .accessibility import ROOT,Stop,load_model
from .compact_accessibility import CompactModel
from .compiled_compact import costs as compact_costs
from .pair_closures import write_gzip_csv


def read_gzip(path):
    with gzip.open(path,'rt',newline='') as f:return list(csv.DictReader(f))


def gp_geometry(blob):
    n={0:0,1:32,2:48,3:48,4:64}[(blob[3]>>1)&7]
    return shapely.from_wkb(blob[8+n:])


def source_metadata():
    cfg=json.loads((ROOT/'research/config/baseline.json').read_text())
    source=ROOT/'data/extracted'/cfg['dataset_id']/'tehran_audited_layers.gpkg'
    db=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    project=Transformer.from_crs(4326,32639,always_xy=True).transform
    boundary=transform(project,gp_geometry(db.execute('select geom from city_boundary').fetchone()[0]))
    hospitals={}
    for raw, in db.execute('select attributes_json from hospital_screened_candidates'):
        a=json.loads(raw);hospitals[f"hospital:{a['osm_type']}{a['osm_id']}"]=a
    groups=json.loads((ROOT/'research/reports/m3-single-closures-2026-11-01/groups.json').read_text())
    units=sorted(street for g in groups for street in g['streets']);wanted=set(units)
    ways={int(s.split(':')[0][1:]) for s in units};lengths={};way_lengths={}
    for wid,raw,blob in db.execute('select osm_id,attributes_json,geom from roads_context where osm_id in ('+','.join('?' for w in ways)+')',sorted(ways)):
        a=json.loads(raw);g=transform(project,gp_geometry(blob));xy=np.asarray(g.coords);ns=a['node_ids'];way_lengths[f'w{wid}']=g.length
        for i in range(len(ns)-1):
            first,second=sorted(ns[i:i+2]);key=f'w{wid}:n{first}:n{second}'
            if key in wanted:lengths[key]=float(np.linalg.norm(xy[i+1]-xy[i]))
    assert set(lengths)==wanted and len(ways)==310
    db.close();return boundary,hospitals,units,lengths,way_lengths


def prepare(variant,boundary,hospitals,units,lengths,way_lengths):
    factor=variant['factor'];value=variant.get('value')
    name={'nearest_tie_policy':{'min_way_id':'tie-min','max_way_id':'tie-max'}.get(value),
          'origin_point_policy':'centroid','route_subset':{'strict_plus_semantic_flags_with_recorded_stop_order':'extended','strict_geometry_with_explicit_geometric_stop_order':'derived'}.get(value)}.get(factor) or 'shared-250'
    cfg_path=ROOT/f'research/config/sensitivity-models/{name}.json'
    cfg=json.loads(cfg_path.read_text());network=ROOT/f'research/model/sensitivity/m2-{name}/network.sqlite'
    m=load_model(network,cfg_path);db=sqlite3.connect(network.as_uri()+'?mode=ro',uri=True)
    connector_limit=float(value) if factor=='connector_limit' else 100.
    covered=None;mask=None
    if factor=='city_buffer_m':
        mask=boundary.buffer(float(value)+1e-7);shapely.prepare(mask)
        xy=np.full((len(m.node_ids),2),np.nan)
        for key,x,y in db.execute('select node_id,x_m,y_m from walk_nodes'):
            if key in m.node_ids:xy[m.node_ids[key]]=(x,y)
        assert np.all(np.isfinite(xy))
        n=db.execute('select count(*) from walk_edges').fetchone()[0]
        aa=np.empty(n,dtype=np.int64);bb=np.empty(n,dtype=np.int64);dd=np.empty(n)
        for i,(a,b,d) in enumerate(db.execute('select u,v,length_m from walk_edges')):aa[i]=m.node_ids[a];bb[i]=m.node_ids[b];dd[i]=d
        geoms=shapely.linestrings(np.stack([xy[aa],xy[bb]],axis=1));keep=shapely.covers(mask,geoms)
        zero=dd<=1e-12
        if np.any(zero):keep[zero]=shapely.covers(mask,shapely.points(xy[aa[zero]]))
        adjacency=[[] for _ in m.adjacency]
        for a,b,d in zip(aa[keep],bb[keep],dd[keep]):adjacency[a].append((int(b),float(d)));adjacency[b].append((int(a),float(d)))
        m.adjacency=adjacency
        points={r[0]:(r[1],r[2]) for r in db.execute('select entity,x_m,y_m from entity_points')}
        covered={}
        for key,r in m.connectors.items():
            if r[3] not in m.node_ids:covered[key]=False;continue
            start=np.array(points[key]);end=xy[m.node_ids[r[3]]]
            geometry=shapely.Point(start) if np.linalg.norm(start-end)<=1e-12 else shapely.LineString([start,end])
            covered[key]=bool(mask.covers(geometry))
    def permitted(key,row):return row[5]=='geometric_candidate' and row[4]<=connector_limit and (covered is None or covered[key])
    targets=[]
    for key,r in m.connectors.items():
        if r[1]!='hospital' or not permitted(key,r):continue
        a=hospitals[key];target_set=value if factor=='target_set' else 'human_all'
        if target_set.startswith('emergency') and not a['primary_osm_proxy_target']:continue
        if target_set.endswith('inside_city') or target_set=='emergency_inside_city':
            if not a['inside_city']:continue
        targets.append((m.node_ids[r[3]],r[4]))
    buildings=[r for r in m.connectors.values() if r[1]=='building'];assert len(buildings)==65677
    anchors=np.array([m.node_ids[r[3]] if permitted(r[0],r) else 0 for r in buildings])
    access=np.array([r[4] if permitted(r[0],r) else np.inf for r in buildings])
    stops=[Stop(s.anchor,s.access_m,s.board and permitted(key,m.connectors[key]),s.alight and permitted(key,m.connectors[key])) for key,s in zip(m.stop_keys,m.stops)]
    rows=m.ride_rows;ids={key:i for i,(key,a,b,mode) in enumerate(rows)}
    active=np.ones(len(rows),dtype=bool)
    if mask is not None:
        initial=ROOT/cfg['output_directory'];traces=json.loads((initial/'traces.json').read_text())
        with (initial/'stops.csv').open(newline='') as f:positions={f"stop:{r['route_relation_id']}:{r['stop_sequence']}":float(r['trace_progress_m']) for r in csv.DictReader(f)}
        lines={rid:shapely.LineString(np.asarray(t['xy_m'])) for rid,t in traces.items()}
        for i,(key,a,b,mode) in enumerate(rows):
            rid=key.split(':')[0];active[i]=mask.covers(substring(lines[rid],positions[a],positions[b]))
    incidence={unit:set() for unit in units}
    route_connections=collections.defaultdict(set)
    for i,(key,a,b,mode) in enumerate(rows):
        if mode=='bus' and active[i]:route_connections[key.split(':')[0]].add(i)
    for street,key in db.execute('select street_segment,connection_id from bus_dependencies'):
        if street in incidence and active[ids[key]]:
            if factor=='failure_policy' and value=='independent_bus':continue
            if factor=='failure_policy' and value=='whole_route':incidence[street].update(route_connections[key.split(':')[0]])
            else:incidence[street].add(ids[key])
    domain='primary_segments'
    if variant['id']=='whole-osm-way':
        mapped=collections.defaultdict(set)
        for unit,failed in incidence.items():mapped[unit.split(':')[0]].update(failed)
        incidence=dict(mapped);unit_lengths=way_lengths;domain='source_ways'
    else:unit_lengths=lengths
    walking_edge_count=sum(map(len,m.adjacency))//2
    incident_walking_nodes=sum(bool(row) for row in m.adjacency)
    compact=CompactModel(m.adjacency,stops,targets,anchors,access,2000.)
    m.adjacency=[];m.node_ids={}
    start=np.array([m.stop_ids[a] for key,a,b,mode in rows],dtype=np.int64)
    end=np.array([m.stop_ids[b] for key,a,b,mode in rows],dtype=np.int64)
    mode_arrays={};model_name=name
    for name,modes in [('bus',{'bus'}),('bus_metro',{'bus','metro'})]:
        allow=np.array([m.stop_modes[k] in modes for k in m.stop_keys])
        mode_arrays[name]=(np.array([s.board for s in stops])&allow,np.array([s.alight for s in stops])&allow,
                           active&np.array([mode in modes for key,a,b,mode in rows]))
    metadata={'model_name':model_name,'network_sha256':m.network_hash,'model_config_sha256':m.config_hash,
        'connector_limit_m':connector_limit,'connected_origins':int(np.count_nonzero(np.isfinite(access))),
        'target_features':len(targets),'boardable_stop_occurrences':sum(s.board for s in stops),
        'route_relations':dict(collections.Counter(mode for key,mode in {(key.split(':')[0],mode) for key,a,b,mode in rows})),
        'active_riding_connections':int(active.sum()),'closure_domain':domain,
        'walking_edges':walking_edge_count,'incident_walking_nodes':incident_walking_nodes,
        'all_origin_ids':[r[0] for r in buildings]}
    db.close()
    return compact,mode_arrays,start,end,incidence,unit_lengths,metadata,rows


def run_variant(variant,shared):
    started=time.perf_counter();out=ROOT/'research/reports/sensitivity-2026-11-01/variants'/variant['id']
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True)
    compact,modes,ride_start,ride_end,incidence,lengths,metadata,ride_rows=prepare(variant,*shared)
    groups=collections.defaultdict(list)
    for unit,failed in sorted(incidence.items()):groups[tuple(sorted(failed))].append(unit)
    keys=sorted(groups);group_ids={key:i for i,key in enumerate(keys)}
    pair_blocks=[];union_set=set()
    for a,first in enumerate(keys):
        for b in range(a,len(keys)):
            second=keys[b];n=math.comb(len(groups[first]),2) if a==b else len(groups[first])*len(groups[second])
            if not n:continue
            union=tuple(sorted(set(first)|set(second)));pair_blocks.append((a,b,n,union));union_set.add(union)
    unions=sorted(union_set);union_ids={u:i for i,u in enumerate(unions)}
    expected_pairs=math.comb(len(incidence),2);assert sum(n for a,b,n,u in pair_blocks)==expected_pairs
    grid=[(k,w) for k in [0,1,2] for w in [500,1000,2000]]
    def evaluate(failed):
        valid=np.ones(len(ride_start),dtype=bool)
        if failed:valid[np.array(failed,dtype=np.int64)]=False
        output={}
        for mode,(board,alight,allowed) in modes.items():
            keep=allowed&valid
            values=compact_costs(compact.walking,compact.transfers,compact.target_cost,compact.edge_stop,compact.edge_cost,
                compact.starts,compact.origins,board,alight,ride_start[keep],ride_end[keep],3,2000.)
            assert np.all(values[1:]<=values[:-1])
            output[mode]=[int(np.count_nonzero(values[k+1]<=w)) for k,w in grid]
        assert all(a>=b for a,b in zip(output['bus_metro'],output['bus']))
        return failed,output
    _,baseline=evaluate(());cache={():baseline};required=sorted(set(keys)|union_set)
    print('Sensitivity',variant['id'],'units',len(incidence),'groups',len(keys),'unions',len(unions),'pairs',expected_pairs,flush=True)
    last=time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as executor:
        for i,(failed,values) in enumerate(executor.map(evaluate,required),1):
            for mode in modes:assert all(a<=b for a,b in zip(values[mode],baseline[mode]))
            cache[failed]=values
            if time.perf_counter()-last>10:print(variant['id'],i,'/',len(required),'seconds',round(time.perf_counter()-started,1),flush=True);last=time.perf_counter()
    loss=lambda failed,mode,j:baseline[mode][j]-cache[failed][mode][j]
    if variant['id']=='baseline':
        source=ROOT/'research/reports/m4-pairs-exhaustive-2026-11-01'
        ids={key:i for i,(key,a,b,mode) in enumerate(ride_rows)}
        published=json.loads((ROOT/'research/reports/m3-2026-11-01-summary.json').read_text())
        for row in published['results']:
            if row['mode']=='walk':assert int(np.count_nonzero(compact.walking<=row['walking_budget_m']))==row['accessible_buildings']
            else:assert baseline[row['mode']][grid.index((row['max_line_changes'],row['walking_budget_m']))]==row['accessible_buildings']
        original_groups=json.loads((ROOT/'research/reports/m3-single-closures-2026-11-01/groups.json').read_text())
        old={g['signature']:tuple(sorted(ids[key] for key in g['failed_connections'])) for g in original_groups}
        with (ROOT/'research/reports/m3-single-closures-2026-11-01/effects.csv').open(newline='') as f:
            for row in csv.DictReader(f):
                j=grid.index((int(row['max_line_changes']),int(row['walking_budget_m'])))
                for mode in modes:assert cache[old[row['signature']]][mode][j]==int(row[mode+'_accessible'])
        union_map={int(r['union_id']):tuple(sorted(ids[key] for key in json.loads(r['failed_connections_json']))) for r in read_gzip(source/'unions.csv.gz')}
        for row in read_gzip(source/'union-effects.csv.gz'):
            j=grid.index((int(row['max_line_changes']),int(row['walking_budget_m'])))
            for mode in modes:assert cache[union_map[int(row['union_id'])]][mode][j]==int(row[mode+'_accessible'])
        metadata['all_primary_published_counts_reproduced']=True
    write_gzip_csv(out/'units.csv.gz',['unit','length_m','group'],[(unit,lengths[unit],group_ids[key]) for key in keys for unit in groups[key]])
    write_gzip_csv(out/'groups.csv.gz',['group','failed_connection_indices_json'],[(i,json.dumps(key,separators=(',',':'))) for i,key in enumerate(keys)])
    write_gzip_csv(out/'connections.csv.gz',['connection_index','connection_id','mode'],[(i,key,mode) for i,(key,a,b,mode) in enumerate(ride_rows)])
    write_gzip_csv(out/'unions.csv.gz',['union','failed_connection_indices_json'],[(i,json.dumps(key,separators=(',',':'))) for i,key in enumerate(unions)])
    write_gzip_csv(out/'single-effects.csv.gz',['group','unit_count','max_line_changes','walking_budget_m','bus_loss','bus_metro_loss'],
        [(i,len(groups[key]),k,w,loss(key,'bus',j),loss(key,'bus_metro',j)) for i,key in enumerate(keys) for j,(k,w) in enumerate(grid)])
    def pair_rows():
        for a,b,n,u in pair_blocks:
            for j,(k,w) in enumerate(grid):
                first,second=keys[a],keys[b];joint_bus=loss(u,'bus',j);joint_full=loss(u,'bus_metro',j)
                assert joint_bus>=max(loss(first,'bus',j),loss(second,'bus',j))
                assert joint_full>=max(loss(first,'bus_metro',j),loss(second,'bus_metro',j))
                yield a,b,union_ids[u],n,k,w,joint_bus,joint_full,joint_bus-loss(first,'bus',j)-loss(second,'bus',j),joint_full-loss(first,'bus_metro',j)-loss(second,'bus_metro',j)
    write_gzip_csv(out/'pair-effects.csv.gz',['first_group','second_group','union','unit_pair_count','max_line_changes','walking_budget_m','bus_joint_loss','bus_metro_joint_loss','bus_interaction','bus_metro_interaction'],pair_rows())
    results=[]
    for j,(k,w) in enumerate(grid):
        record={'max_line_changes':k,'walking_budget_m':w}
        for mode in modes:
            histogram=collections.Counter()
            for a,b,n,u in pair_blocks:histogram[loss(u,mode,j)-loss(keys[a],mode,j)-loss(keys[b],mode,j)]+=n
            record[mode]={'baseline_accessible':baseline[mode][j],
                'positive_loss_units':sum(len(groups[key]) for key in keys if loss(key,mode,j)>0),
                'maximum_single_loss':max(loss(key,mode,j) for key in keys),
                'positive_interaction_pairs':sum(n for c,n in histogram.items() if c>0),
                'negative_interaction_pairs':sum(n for c,n in histogram.items() if c<0),'zero_interaction_pairs':histogram[0],
                'minimum_interaction':min(histogram),'maximum_interaction':max(histogram),
                'maximum_joint_loss':max(loss(u,mode,j) for u in unions)}
        results.append(record)
    origin_ids=metadata.pop('all_origin_ids')
    origin_digest=hashlib.sha256(json.dumps(origin_ids,separators=(',',':')).encode()).hexdigest()
    report={'status':'passed','variant':variant,'protocol_sha256':hashlib.sha256((ROOT/'research/config/sensitivity-protocol.json').read_bytes()).hexdigest(),
        'unit_count':len(incidence),'physical_pair_count':expected_pairs,'signature_groups':len(keys),'signature_pair_blocks':len(pair_blocks),
        'failed_union_count':len(unions),'all_buildings':65677,'origin_id_order_sha256':origin_digest,
        'walking_only':[{'walking_budget_m':w,'accessible':int(np.count_nonzero(compact.walking<=w))} for w in [500,1000,2000]],
        'model':metadata,'results':results,'elapsed_seconds':time.perf_counter()-started,
        'artifact_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}}
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Completed sensitivity',variant['id'],round(report['elapsed_seconds'],1),flush=True)
    return report


def run():
    protocol=json.loads((ROOT/'research/config/sensitivity-protocol.json').read_text());shared=source_metadata()
    variants=protocol['variants']+[{'id':'whole-osm-way','factor':'segmentation'}]
    for variant in variants:run_variant(variant,shared)


if __name__=='__main__':run()
