"""M2: walking graph, explicit geometric connectors and bus street dependencies.

All geometry comes from the bundled OSM data. No external routing is used.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import sqlite3

import numpy as np
from pyproj import Transformer
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import transform as transform_geometry
from shapely.strtree import STRtree

from research.src.extract_routes import ROOT, csv_rows, write_csv


def overlapping_segments(progress, start, end, tolerance=1e-7):
    """Indices with positive interval overlap; a touching endpoint is excluded."""
    if end < start:
        raise ValueError("Reversed interval")
    return np.flatnonzero(np.minimum(progress[1:], end) -
                          np.maximum(progress[:-1], start) > tolerance).tolist()


def cut_positions(start, end, anchors, tolerance=1e-7):
    """Stable chain of endpoints and distinct interior anchors."""
    result = [float(start)]
    for x in sorted(anchors):
        if start + tolerance < x < end - tolerance and x - result[-1] > tolerance:
            result.append(float(x))
    result.append(float(end))
    return result


def boarding_permissions(role):
    return not role.endswith('exit_only'), not role.endswith('entry_only')


def run(config, connector_limit=100, output=None):
    cfg = json.loads(config.read_text())
    source = ROOT / "data/extracted" / cfg["dataset_id"]
    initial = ROOT / cfg["output_directory"]
    prior = json.loads((initial/'summary.json').read_text())
    config_hash = hashlib.sha256(config.read_bytes()).hexdigest()
    if prior['config_sha256'] != config_hash or prior['dataset_id'] != cfg['dataset_id']:
        raise ValueError('M1 configuration does not match M2 input')
    out = (output or ROOT / "research/model/m2-v2").resolve()
    if not out.is_relative_to(ROOT / 'research/model'):
        raise ValueError('Output must stay inside research/model')
    if not np.isfinite(connector_limit) or connector_limit < 0:
        raise ValueError('Connector limit must be finite and nonnegative')
    out.mkdir(parents=True, exist_ok=True)
    if (out / "network.sqlite").exists():
        raise FileExistsError("M2 output exists; choose a new run or explicitly archive it")
    p = source / "tehran_audited_layers.gpkg"
    manifest = json.loads((source / "manifest.json").read_text())
    with p.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != manifest["files"][p.name]["sha256"]:
            raise ValueError("GeoPackage identity mismatch")
    db = sqlite3.connect(p.as_uri()+"?mode=ro", uri=True)
    project = Transformer.from_crs(4326,32639,always_xy=True).transform
    ways, origins, hospitals = [], [], []
    def geometry(blob):
        size = {0:0,1:32,2:48,3:48,4:64}[(blob[3]>>1)&7]
        return shapely.from_wkb(blob[8+size:])
    for wid, raw, blob in db.execute("SELECT osm_id,attributes_json,geom FROM roads_context"):
        a = json.loads(raw)
        if not a['walk_candidate']:
            continue
        g = transform_geometry(project,geometry(blob))
        xy = np.asarray(g.coords)
        ns = a['node_ids']
        if len(ns) != len(xy):
            raise ValueError("Walking way node/coordinate mismatch")
        cumulative = np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
        if cumulative[-1] > 0:
            ways.append({'id':wid,'geometry':g,'nodes':ns,'progress':cumulative})
    origin_policy=cfg.get('origin_point_policy','stored_representative_point')
    query="SELECT osm_type,osm_id,attributes_json,geom FROM buildings_city" if origin_policy=='centroid' else "SELECT osm_type,osm_id,attributes_json,NULL FROM buildings_city"
    for typ, ident, raw, blob in db.execute(query):
        a=json.loads(raw)
        outside=False
        if origin_policy=='centroid':
            footprint=geometry(blob);point=footprint.centroid;outside=not footprint.covers(point)
            location=Point(project(point.x,point.y))
        else:location=Point(project(a['point_lon'],a['point_lat']))
        origins.append({'key':f'building:{typ}{ident}','kind':'building',
                        'group':f'{typ}{ident}','point':location,'centroid_outside_footprint':outside})
    for raw, blob in db.execute("SELECT attributes_json,geom FROM hospital_screened_candidates"):
        a=json.loads(raw)
        if a['screen_decision']!='human_hospital_candidate':
            continue
        g=geometry(blob).representative_point()
        hospitals.append({'key':f"hospital:{a['osm_type']}{a['osm_id']}",'kind':'hospital',
                          'group':a['candidate_group_id'],'point':Point(project(g.x,g.y))})
    db.close()
    routes = {r['relation_id']:r for r in csv_rows(initial/'routes.csv')}
    stops = [s for s in csv_rows(initial/'stops.csv') if
             routes[s['route_relation_id']]['status']=='candidate_for_walking_connection_audit']
    entities=origins+hospitals
    for s in stops:
        entities.append({'key':f"stop:{s['route_relation_id']}:{s['stop_sequence']}",
            'kind':'stop','group':f"{s['osm_type']}{s['osm_id']}",
            'role':s['role'],
            'point':Point(project(float(s['longitude']),float(s['latitude'])))})
    tree=STRtree([w['geometry'] for w in ways])
    queries=np.asarray([e['point'] for e in entities],dtype=object)
    tie_policy=cfg.get('nearest_tie_policy','one_STRtree_result')
    indices,distances=tree.query_nearest(queries,return_distance=True,all_matches=tie_policy in ['min_way_id','max_way_id'])
    nearest={};ties=collections.Counter()
    for (i,j),d in zip(indices.T,distances):
        i,j=int(i),int(j);ties[i]+=1
        if i not in nearest:nearest[i]=(j,float(d))
        elif ((tie_policy=='min_way_id' and ways[j]['id']<ways[nearest[i][0]]['id']) or
              (tie_policy=='max_way_id' and ways[j]['id']>ways[nearest[i][0]]['id'])):nearest[i]=(j,float(d))
    anchors=collections.defaultdict(list); connector_rows=[]
    for i,e in enumerate(entities):
        j,d=nearest[i];w=ways[j];along=float(w['geometry'].project(e['point']))
        status='geometric_candidate' if d<=connector_limit else 'beyond_distance_limit'
        connector_rows.append({'entity':e['key'],'kind':e['kind'],'group':e['group'],
            'way_id':w['id'],'progress_m':along,'distance_m':d,'status':status,
            'anchor_node':'','entrance_or_barrier_verified':False,
            'board_allowed':boarding_permissions(e.get('role',''))[0] if e['kind']=='stop' else False,
            'alight_allowed':boarding_permissions(e.get('role',''))[1] if e['kind']=='stop' else False})
        if d<=connector_limit:anchors[j].append((along,len(connector_rows)-1))
    target=sqlite3.connect(out/'network.sqlite')
    target.executescript('''
      CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
      CREATE TABLE walk_edges(edge_id INTEGER PRIMARY KEY,u TEXT,v TEXT,length_m REAL,osm_way_id INTEGER);
      CREATE TABLE connectors(entity TEXT PRIMARY KEY,kind TEXT,group_id TEXT,anchor TEXT,length_m REAL,status TEXT,board_allowed INTEGER,alight_allowed INTEGER);
      CREATE TABLE transit_connections(connection_id TEXT PRIMARY KEY,route_id INTEGER,from_stop TEXT,to_stop TEXT,length_m REAL,mode TEXT);
      CREATE TABLE bus_dependencies(connection_id TEXT,street_segment TEXT,osm_way_id INTEGER,overlap_m REAL);
    ''')
    store_coordinates=cfg.get('store_node_coordinates',False)
    if store_coordinates:
        target.executescript('CREATE TABLE walk_nodes(node_id TEXT PRIMARY KEY,x_m REAL,y_m REAL); CREATE TABLE entity_points(entity TEXT PRIMARY KEY,x_m REAL,y_m REAL,centroid_outside_footprint INTEGER);')
        target.executemany('INSERT INTO entity_points VALUES(?,?,?,?)',[(e['key'],e['point'].x,e['point'].y,int(e.get('centroid_outside_footprint',False))) for e in entities])
    edge_rows=[]
    for j,w in enumerate(ways):
        cumulative=w['progress'];by_segment=collections.defaultdict(list)
        if store_coordinates:
            xy=np.asarray(w['geometry'].coords)
            target.executemany('INSERT OR IGNORE INTO walk_nodes VALUES(?,?,?)',[(f'n{node}',float(p[0]),float(p[1])) for node,p in zip(w['nodes'],xy)])
        for along,index in anchors.get(j,[]):
            node_index=int(np.argmin(np.abs(cumulative-along)))
            if abs(cumulative[node_index]-along)<=1e-7:
                connector_rows[index]['anchor_node']=f"n{w['nodes'][node_index]}"
            else:
                segment=int(np.searchsorted(cumulative,along,side='right')-1)
                by_segment[segment].append((along,index))
        for k,(a,b) in enumerate(zip(cumulative,cumulative[1:])):
            if b-a<=1e-7:
                if w['nodes'][k] != w['nodes'][k+1]:
                    edge_rows.append((f"n{w['nodes'][k]}",f"n{w['nodes'][k+1]}",float(b-a),w['id']))
                continue
            selected=by_segment.get(k,[])
            cuts=cut_positions(a,b,[x for x,_ in selected])
            names=[f"n{w['nodes'][k]}"]+[f"w{w['id']}:{k}:{q}" for q in range(1,len(cuts)-1)]+[f"n{w['nodes'][k+1]}"]
            if store_coordinates and len(cuts)>2:
                points=[xy[k]+(position-a)/(b-a)*(xy[k+1]-xy[k]) for position in cuts[1:-1]]
                target.executemany('INSERT OR IGNORE INTO walk_nodes VALUES(?,?,?)',[(name,float(p[0]),float(p[1])) for name,p in zip(names[1:-1],points)])
            for along,index in selected:
                q=int(np.argmin(np.abs(np.asarray(cuts)-along)))
                connector_rows[index]['anchor_node']=names[q]
            edge_rows.extend((names[q],names[q+1],cuts[q+1]-cuts[q],w['id']) for q in range(len(cuts)-1))
        if len(edge_rows)>20000:
            target.executemany('INSERT INTO walk_edges(u,v,length_m,osm_way_id) VALUES(?,?,?,?)',edge_rows);edge_rows=[]
    target.executemany('INSERT INTO walk_edges(u,v,length_m,osm_way_id) VALUES(?,?,?,?)',edge_rows)
    target.executemany('INSERT INTO connectors VALUES(?,?,?,?,?,?,?,?)',[(x['entity'],x['kind'],x['group'],x['anchor_node'],x['distance_m'],x['status'],x['board_allowed'],x['alight_allowed']) for x in connector_rows])
    traces=json.loads((initial/'traces.json').read_text())
    conn=csv_rows(initial/'connections.csv');dep_count=0
    for c in conn:
        rid=c['route_relation_id'];trace=traces[rid]
        a,b=float(c['from_progress_m']),float(c['to_progress_m'])
        xy=np.asarray(trace['xy_m']);progress=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
        key=f"{rid}:{c['from_sequence']}:{c['to_sequence']}";mode=routes[rid]['mode']
        target.execute('INSERT INTO transit_connections VALUES(?,?,?,?,?,?)',(key,int(rid),f"stop:{rid}:{c['from_sequence']}",f"stop:{rid}:{c['to_sequence']}",b-a,mode))
        if mode=='bus':
            deps=[]
            for k in overlapping_segments(progress,a,b):
                u,v=sorted(trace['node_ids'][k:k+2]);wid=trace['edge_way_ids'][k]
                length=min(progress[k+1],b)-max(progress[k],a)
                deps.append((key,f'w{wid}:n{u}:n{v}',wid,float(length)))
            target.executemany('INSERT INTO bus_dependencies VALUES(?,?,?,?)',deps);dep_count+=len(deps)
            if abs(sum(d[3] for d in deps)-(b-a))>1e-5:
                raise ValueError('Dependency length does not reconstruct connection')
    target.execute('CREATE INDEX dependency_street ON bus_dependencies(street_segment)')
    target.execute('CREATE INDEX walk_u ON walk_edges(u)');target.execute('CREATE INDEX walk_v ON walk_edges(v)')
    for k,v in {'walking_edges':'undirected; lengths in metres',
                'connectors':'geometric candidates; no entrance/barrier verification',
                'street_unit':'OSM way + unordered adjacent node pair; carriageways not conflated',
                'config_sha256':hashlib.sha256(config.read_bytes()).hexdigest(),
                'connector_limit_m':connector_limit}.items():
        target.execute('INSERT INTO metadata VALUES(?,?)',(k,str(v)))
    target.commit()
    assert target.execute('pragma integrity_check').fetchone()[0]=='ok'
    missing=target.execute("SELECT count(*) FROM connectors WHERE status='geometric_candidate' AND anchor=''").fetchone()[0]
    assert missing==0
    summary={'dataset_id':cfg['dataset_id'],'stage':'m2-v2','config_sha256':config_hash,'connector_limit_m':connector_limit,
        'walking_ways':len(ways),'walking_edges':target.execute('select count(*) from walk_edges').fetchone()[0],
        'connectors_by_kind':{kind:dict(collections.Counter(x['status'] for x in connector_rows if x['kind']==kind)) for kind in ['building','hospital','stop']},
        'transit_connections':len(conn),'bus_dependency_segment_occurrences':dep_count,
        'unique_bus_street_segments':target.execute('select count(distinct street_segment) from bus_dependencies').fetchone()[0],
        'candidate_routes':dict(collections.Counter(routes[r]['mode'] for r in {c['route_relation_id'] for c in conn})),
        'restricted_stop_associations':sum(x['kind']=='stop' and not(x['board_allowed'] and x['alight_allowed']) for x in connector_rows),
        'pending':['stop-area reconciliation','review of excluded routes','transfer-state accessibility solver','connectivity coverage and failure simulation'],
        'nearest_tie_policy':'one STRtree nearest result; equal-distance alternatives not resolved; connector sensitivity remains necessary'}
    if store_coordinates:
        summary.update({'nearest_tie_policy':tie_policy,'origin_point_policy':origin_policy,
                        'entities_with_multiple_nearest_ways':sum(n>1 for n in ties.values()),
                        'centroids_outside_footprint':sum(e.get('centroid_outside_footprint',False) for e in origins)})
    target.close()
    write_csv(out/'connectors.csv',connector_rows)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=ROOT/'research/config/baseline.json')
    p.add_argument('--connector-limit-m',type=float,default=100)
    p.add_argument('--output',type=Path,default=None)
    args=p.parse_args();run(args.config,args.connector_limit_m,args.output)
