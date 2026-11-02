"""Independently replay every saved certificate against frozen graph records."""
import collections
import csv
import gzip
import hashlib
import json
import math
import sqlite3
from pathlib import Path

import numpy as np
from pyproj import Transformer
import shapely
from shapely.ops import transform

from .accessibility import ROOT
from .pair_closures import write_gzip_csv
from .sensitivity_runs import gp_geometry

OUT=ROOT/'research/reports/sensitivity-2026-11-01'


def primary_coordinates(connectors,edges):
    shared=sqlite3.connect((ROOT/'research/model/sensitivity/m2-shared-250/network.sqlite').as_uri()+'?mode=ro',uri=True)
    # Native OSM node IDs are stable. Synthetic split IDs are NOT stable across
    # connector-limit builds and must be reconstructed from primary progress.
    xy={key:(x,y) for key,x,y in shared.execute("select node_id,x_m,y_m from walk_nodes where node_id like 'n%'")}
    points={key:(x,y) for key,x,y in shared.execute('select entity,x_m,y_m from entity_points')};shared.close()
    with (ROOT/'research/model/m2-v2/connectors.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    pending=collections.defaultdict(list)
    for r in rows:
        if r['status']=='geometric_candidate' and r['anchor_node'].startswith('w'):
            pending[int(r['way_id'])].append((r['anchor_node'],float(r['progress_m'])))
    cfg=json.loads((ROOT/'research/config/baseline.json').read_text())
    src=sqlite3.connect((ROOT/'data/extracted'/cfg['dataset_id']/'tehran_audited_layers.gpkg').as_uri()+'?mode=ro',uri=True)
    project=Transformer.from_crs(4326,32639,always_xy=True).transform
    for wid,blob in src.execute('select osm_id,geom from roads_context'):
        if wid not in pending:continue
        g=transform(project,gp_geometry(blob))
        for key,progress in pending[wid]:
            p=g.interpolate(progress);xy[key]=(p.x,p.y)
    src.close()
    required={v for u,v,d in edges.values()}|{u for u,v,d in edges.values()}
    assert required<=xy.keys()
    maximum=0.
    for u,v,d in edges.values():
        observed=math.dist(xy[u],xy[v]);difference=abs(observed-d);maximum=max(maximum,difference)
        assert difference<1e-5
    connector_maximum=0.
    for key,r in connectors.items():
        if r[5]!='geometric_candidate':continue
        difference=abs(math.dist(points[key],xy[r[3]])-r[4]);connector_maximum=max(connector_maximum,difference)
        assert difference<1e-5
    return xy,points,{'walking_edges_checked':len(edges),'maximum_edge_geometry_difference_m':maximum,
        'accepted_connectors_checked':sum(r[5]=='geometric_candidate' for r in connectors.values()),
        'maximum_connector_geometry_difference_m':connector_maximum}


def run():
    db=sqlite3.connect((ROOT/'research/model/m2-v2/network.sqlite').as_uri()+'?mode=ro',uri=True)
    connectors={r[0]:r for r in db.execute('select entity,kind,group_id,anchor,length_m,status,board_allowed,alight_allowed from connectors')}
    edges={eid:(u,v,d) for eid,u,v,d in db.execute('select edge_id,u,v,length_m from walk_edges')}
    rides={key:(a,b,d,mode) for key,a,b,d,mode in db.execute('select connection_id,from_stop,to_stop,length_m,mode from transit_connections')};db.close()
    xy,points,geometry=primary_coordinates(connectors,edges)
    failed=json.loads((OUT/'path-failed-sets.json').read_text());seen=set();success=0;profiles=[];patterns=collections.Counter();max_difference=0.;used_edges=set();accessible={};sequences={}
    with gzip.open(OUT/'path-witnesses.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            r=json.loads(line);key=r['failed_set'],r['mode'],r['origin'];assert key not in seen;seen.add(key)
            origin=connectors[r['origin']];assert origin[1]=='building' and origin[5]=='geometric_candidate'
            d=r['minimum_walking_m'];assert r['accessible_1000m']==(d is not None and d<=1000)
            accessible[key]=r['accessible_1000m']
            if not r['accessible_1000m']:assert 'legs' not in r;continue
            assert abs(r['origin_connector_m']-origin[4])<1e-9
            node=origin[3];cost=origin[4];boardings=0;ride_length=0.;ride_modes=[];conns=[]
            for leg in r['legs']:
                if leg['kind']=='walk':
                    total=0.
                    for eid in leg['edge_ids']:
                        u,v,length=edges[eid];assert node in (u,v);node=v if node==u else u;total+=length;used_edges.add(eid)
                    assert abs(total-leg['length_m'])<1e-8;cost+=total
                else:
                    board,alight=connectors[leg['board_stop']],connectors[leg['alight_stop']]
                    assert board[6] and alight[7] and node==board[3];boardings+=1;stop=board[0]
                    assert abs(board[4]-leg['board_connector_m'])<1e-9 and abs(alight[4]-leg['alight_connector_m'])<1e-9
                    for connection in leg['connection_ids']:
                        a,b,length,mode=rides[connection];assert a==stop and connection not in failed[r['failed_set']]
                        assert mode=='bus' or r['mode']=='bus_metro';stop=b;ride_length+=length;conns.append(connection)
                    assert stop==alight[0]
                    if leg['connection_ids']:ride_modes.append(rides[leg['connection_ids'][0]][3])
                    cost+=board[4]+alight[4];node=alight[3]
            target=connectors[r['target']];assert target[1]=='hospital' and target[5]=='geometric_candidate' and target[3]==node
            assert abs(target[4]-r['target_connector_m'])<1e-9
            cost+=target[4];assert boardings==r['boardings']<=2
            assert abs(cost-r['walking_cost_sum_m'])<1e-7
            difference=abs(cost-d);max_difference=max(max_difference,difference);assert difference<1e-7
            assert ride_modes==r['riding_mode_sequence'];patterns[','.join(ride_modes) or 'walk']+=1
            sequences[key]=tuple(ride_modes)
            profiles.append((r['origin'],r['mode'],r['failed_set'],d,ride_length,boardings,','.join(ride_modes),r['target']))
            success+=1
    summary=json.loads((OUT/'path-summary.json').read_text());assert success==summary['successful_paths'] and len(seen)==summary['origin_state_certificates']
    assert summary['maximum_compact_full_walking_difference_m']<1e-8
    registry=json.loads((OUT/'path-case-registry.json').read_text())
    groups=json.loads((ROOT/'research/reports/m3-single-closures-2026-11-01/groups.json').read_text())
    set_ids={tuple(v):k for k,v in failed.items()};expected=set();members=0;membership_counts=collections.Counter();extra_by_group=collections.defaultdict(set)
    with gzip.open(OUT/'path-case-members.csv.gz','rt',newline='') as f:
        for r in csv.DictReader(f):
            members+=1
            if r['case'].startswith('pair-'):
                case=registry['pairs'][int(r['case'].split('-')[1])]
                a=tuple(groups[case['first_group']]['failed_connections']);b=tuple(groups[case['second_group']]['failed_connections'])
                joint=tuple(sorted(set(a)|set(b)))
                for state in [(),a,b,joint]:expected.add((set_ids[state],r['mode'],r['origin']))
                key=lambda s:(set_ids[s],r['mode'],r['origin'])
                assert accessible[key(())] and not accessible[key(joint)]
                first,second=not accessible[key(a)],not accessible[key(b)]
                category='shared' if first and second else 'joint_only' if not first and not second else 'one_single'
                assert r['category']==category;membership_counts[r['case'],r['mode']]+=1
            else:
                state=tuple(groups[int(r['case'].split('-')[-1])]['failed_connections'])
                for mode in ['bus','bus_metro']:
                    for s in [(),state]:expected.add((set_ids[s],mode,r['origin']))
                key=lambda s,md:(set_ids[s],md,r['origin'])
                buslost=accessible[key((),'bus')] and not accessible[key(state,'bus')]
                fulllost=accessible[key((),'bus_metro')] and not accessible[key(state,'bus_metro')]
                assert buslost or fulllost
                extra=fulllost and not accessible[key((),'bus')]
                rescued=buslost and not fulllost
                assert r['category']==('extra_full_baseline_lost' if extra else 'bus_loss_rescued' if rescued else 'common_loss')
                membership_counts[r['case'],'bus']+=int(buslost);membership_counts[r['case'],'bus_metro']+=int(fulllost)
                if extra:
                    extra_by_group[r['case']].add(r['origin'])
                    assert sequences[key((),'bus_metro')]==('metro','bus')
    assert expected==seen and members==summary['case_origin_memberships']
    baseline=json.loads((ROOT/'research/reports/m3-2026-11-01-summary.json').read_text())
    base={r['mode']:r['accessible_buildings'] for r in baseline['results'] if r['max_line_changes']==1 and r['walking_budget_m']==1000}
    union_counts={}
    with gzip.open(ROOT/'research/reports/m4-pairs-exhaustive-2026-11-01/union-effects.csv.gz','rt',newline='') as f:
        for r in csv.DictReader(f):
            if r['max_line_changes']=='1' and r['walking_budget_m']=='1000':
                union_counts[int(r['union_id'])]={md:base[md]-int(r[md+'_accessible']) for md in ['bus','bus_metro']}
    for i,c in enumerate(registry['pairs']):
        for md in ['bus','bus_metro']:assert membership_counts[f'pair-{i}',md]==union_counts[c['union_id']][md]
    with (ROOT/'research/reports/m3-single-closures-2026-11-01/effects.csv').open(newline='') as f:
        single={r['signature']:r for r in csv.DictReader(f) if r['max_line_changes']=='1' and r['walking_budget_m']=='1000'}
    for c in registry['negative_delta_singles']:
        label=f"negative-delta-{c['group_index']}";row=single[c['signature']]
        for md in ['bus','bus_metro']:assert membership_counts[label,md]==base[md]-int(row[md+'_accessible'])
    assert len(extra_by_group)==7 and all(len(s)==13 for s in extra_by_group.values())
    assert len({tuple(sorted(s)) for s in extra_by_group.values()})==1
    write_gzip_csv(OUT/'path-ride-profiles.csv.gz',['origin','mode','failed_set','walking_m','riding_m','boardings','mode_sequence','target'],profiles)
    # Compact coordinates for every witness walking edge, plus all used origins,
    # targets and stop occurrences. Full geometry census above covers the graph.
    nodes={n for e in used_edges for n in edges[e][:2]}
    used_entities={r[0] for r in profiles}|{r[-1] for r in profiles}|{k for k,v in connectors.items() if v[1]=='stop'}
    write_gzip_csv(OUT/'path-node-coordinates.csv.gz',['node','x_m','y_m'],[(n,*xy[n]) for n in sorted(nodes)])
    write_gzip_csv(OUT/'path-entity-coordinates.csv.gz',['entity','x_m','y_m'],[(k,*points[k]) for k in sorted(used_entities)])
    write_gzip_csv(OUT/'path-walking-edges.csv.gz',['edge_id','u','v','length_m'],[(e,*edges[e]) for e in sorted(used_edges)])
    report={'status':'passed','certificates_replayed':len(seen),'successful_paths_replayed':success,
        'maximum_walking_cost_difference_m':max_difference,'geometry':geometry,'mode_sequences':dict(patterns),
        'case_memberships_match_all_published_losses':True,'all_seven_negative_groups_same_13_extra_origins':True,
        'every_extra_origin_full_baseline_witness_mode_sequence':['metro','bus'],
        'riding_distance_km':{'median':float(np.median([r[4] for r in profiles])/1000),'p95':float(np.percentile([r[4] for r in profiles],95)/1000),'max':max(r[4] for r in profiles)/1000},
        'interpretation':'Riding lengths describe selected minimum-walking witnesses, not shortest total-distance journeys or feasible travel times.',
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    report['artifact_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('path-*') if p.name!='path-audit.json'}
    (OUT/'path-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2));return report


if __name__=='__main__':run()
