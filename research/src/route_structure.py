"""All accepted-route source overlaps and all primary street feature records."""
import collections
import csv
import itertools
import json
from pathlib import Path
import sqlite3

import numpy as np
from pyproj import Transformer

from .accessibility import ROOT
from .pair_closures import write_gzip_csv
from .sensitivity_runs import gp_geometry
from .structural_centrality import OUT,MODEL,sha


def merge_intervals(intervals):
    result=[]
    for a,b in sorted(intervals):
        if result and a<=result[-1][1]:result[-1]=(result[-1][0],max(result[-1][1],b))
        else:result.append((a,b))
    return result


def shared_length(first,second):
    i=j=0;total=0.
    while i<len(first) and j<len(second):
        a,b=first[i];c,d=second[j];total+=max(0,min(b,d)-max(a,c))
        if b<d:i+=1
        else:j+=1
    return total


def run():
    OUT.mkdir(exist_ok=True)
    groups=json.loads((ROOT/'research/reports/m3-single-closures-2026-11-01/groups.json').read_text())
    streets=sorted(s for g in groups for s in g['streets']);assert len(streets)==len(set(streets))==1684
    network=ROOT/'research/model/m2-v2/network.sqlite';db=sqlite3.connect(network.as_uri()+'?mode=ro',uri=True)
    rides=list(db.execute('select connection_id,route_id,from_stop,to_stop,length_m,mode from transit_connections'))
    route_ids={str(r[1]) for r in rides};route_mode={str(r[1]):r[5] for r in rides}
    incidence=collections.defaultdict(set);connections=collections.defaultdict(set);overlap=collections.Counter()
    for key,street,length in db.execute('select connection_id,street_segment,overlap_m from bus_dependencies'):
        incidence[street].add(key.split(':')[0]);connections[street].add(key);overlap[street]+=length
    assert set(incidence)==set(streets);db.close()
    source=ROOT/'data/extracted/tehran-osm-20261029T212126Z-v1.1-public/tehran_audited_layers.gpkg'
    db=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);wanted={int(s.split(':')[0][1:]) for s in streets};wanted_keys=set(streets)
    project=Transformer.from_crs(4326,32639,always_xy=True)
    features={}
    for wid,raw,blob in db.execute('select osm_id,attributes_json,geom from roads_context'):
        if wid not in wanted:continue
        a=json.loads(raw);xy=np.asarray(gp_geometry(blob).coords);x,y=project.transform(xy[:,0],xy[:,1]);xy=np.column_stack((x,y));nodes=a['node_ids']
        for first,second,p,q in zip(nodes,nodes[1:],xy,xy[1:]):
            low,high=sorted([first,second]);key=f'w{wid}:n{low}:n{high}'
            if key not in wanted_keys:continue
            middle=(p+q)/2;features[key]={'unit':key,'way_id':wid,'first_node':low,'second_node':high,
                'length_m':float(np.linalg.norm(q-p)),'x_m':float(middle[0]),'y_m':float(middle[1]),'highway':a['tags'].get('highway','unknown'),
                'dependent_bus_relations':len(incidence[key]),'dependent_connections':len(connections[key]),
                'dependent_interval_occurrence_m':overlap[key],'route_ids_json':json.dumps(sorted(incidence[key],key=int),separators=(',',':'))}
    db.close();assert set(features)==wanted_keys
    fields=list(features[streets[0]])
    write_gzip_csv(OUT/'street-features.csv.gz',fields,[[features[s][f] for f in fields] for s in streets])
    initial=ROOT/'research/model/m1-v1';traces=json.loads((initial/'traces.json').read_text())
    with (initial/'stops.csv').open(newline='',encoding='utf-8') as f:stop_rows=list(csv.DictReader(f))
    with (initial/'routes.csv').open(newline='',encoding='utf-8') as f:route_rows={r['relation_id']:r for r in csv.DictReader(f)}
    geometry={};descriptions=[]
    for rid in sorted(route_ids,key=int):
        trace=traces[rid];xy=np.asarray(trace['xy_m']);length=np.linalg.norm(np.diff(xy,axis=0),axis=1);progress=np.r_[0,np.cumsum(length)]
        stops=[r for r in stop_rows if r['route_relation_id']==rid];a=min(float(s['trace_progress_m']) for s in stops);b=max(float(s['trace_progress_m']) for s in stops)
        intervals=collections.defaultdict(list)
        for i,d in enumerate(length):
            left=max(a,progress[i])-progress[i];right=min(b,progress[i+1])-progress[i]
            if right-left<=1e-7:continue
            u,v=trace['node_ids'][i:i+2];lo,hi=sorted([u,v]);key=f"w{trace['edge_way_ids'][i]}:n{lo}:n{hi}"
            intervals[key].append((float(left),float(right)) if u<=v else (float(d-right),float(d-left)))
        geometry[rid]={key:merge_intervals(values) for key,values in intervals.items()}
        unique_length=sum(y-x for values in geometry[rid].values() for x,y in values)
        descriptions.append((rid,route_mode[rid],route_rows[rid]['ref'],len(stops),sum(s['stop_representation']=='stop' for s in stops),
            float(progress[-1]),b-a,unique_length,len(geometry[rid]),sum(str(r[1])==rid for r in rides)))
        if route_mode[rid]=='bus':assert set(geometry[rid])=={s for s in streets if rid in incidence[s]}
    write_gzip_csv(OUT/'route-descriptions.csv.gz',['relation_id','mode','ref','stop_occurrences','selected_stop_member_occurrences','full_oriented_trace_m','between_first_last_stop_trace_m','unique_traversed_source_geometry_m','unique_source_segments','consecutive_stop_connections'],descriptions)
    pairs=[]
    for a,b in itertools.combinations(sorted(route_ids,key=int),2):
        first,second=geometry[a],geometry[b];intersection=first.keys()&second.keys();union=first.keys()|second.keys()
        shared=sum(shared_length(first[key],second[key]) for key in intersection)
        l1=sum(y-x for values in first.values() for x,y in values);l2=sum(y-x for values in second.values() for x,y in values)
        pairs.append((a,b,route_mode[a],route_mode[b],len(intersection),len(union),len(intersection)/len(union),shared,shared/(l1+l2-shared) if l1+l2>shared else None))
    assert len(pairs)==300
    write_gzip_csv(OUT/'route-pair-overlap.csv.gz',['first_relation','second_relation','first_mode','second_mode','shared_source_segment_keys','union_source_segment_keys','segment_key_jaccard','shared_source_geometry_m','length_jaccard'],pairs)
    distribution=collections.Counter((len(incidence[s]),len(connections[s])) for s in streets)
    write_gzip_csv(OUT/'dependency-concentration.csv.gz',['dependent_bus_relations','dependent_connections','street_units'],[(r,c,n) for (r,c),n in sorted(distribution.items())])
    report={'status':'passed','primary_source_streets':1684,'accepted_route_relations':len(route_ids),'all_route_pairs':300,
        'bus_relations':sum(v=='bus' for v in route_mode.values()),'rail_relations':sum(v=='metro' for v in route_mode.values()),
        'maximum_dependent_relations':max(len(v) for v in incidence.values()),'maximum_dependent_connections':max(len(v) for v in connections.values()),
        'all_dependency_keys_match_effect_domain':True,'overlap_meaning':'Intersection of actual traversed intervals on identical source way/node-pair keys. Parallel corridors with distinct source keys are not merged. Relation instances are not unique services or passenger counts.',
        'source_code_sha256':sha(Path(__file__)),'network_sha256':sha(network)}
    report['artifact_sha256']={name:sha(OUT/name) for name in ['street-features.csv.gz','route-descriptions.csv.gz','route-pair-overlap.csv.gz','dependency-concentration.csv.gz']}
    (OUT/'route-structure-summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report),flush=True)


if __name__=='__main__':run()
