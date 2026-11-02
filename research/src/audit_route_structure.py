"""Replay all accepted-route overlap rows using independent GEOS unions.

The production calculation uses numeric interval merging. This replay uses
GEOS line union/intersection on a one-dimensional axis for each source key.
"""
import argparse
import csv
import itertools
import json
import math
from pathlib import Path
import sqlite3

import numpy as np
from shapely.geometry import LineString
from shapely.ops import unary_union

from .accessibility import ROOT
from .sensitivity_runs import read_gzip
from .structural_centrality import OUT, sha


def run(write=True):
    descriptions=read_gzip(OUT/'route-descriptions.csv.gz')
    traces=json.loads((ROOT/'research/model/m1-v1/traces.json').read_text())
    with (ROOT/'research/model/m1-v1/stops.csv').open(newline='',encoding='utf-8') as f:
        stops=list(csv.DictReader(f))
    route_geometry={}
    for row in descriptions:
        rid=row['relation_id'];trace=traces[rid];xy=trace['xy_m']
        lengths=[math.hypot(q[0]-p[0],q[1]-p[1]) for p,q in zip(xy,xy[1:])]
        # Use the recorded projection progress to define the same stop interval.
        progress=np.r_[0,np.cumsum(lengths)]
        selected=[r for r in stops if r['route_relation_id']==rid]
        first=min(float(r['trace_progress_m']) for r in selected)
        last=max(float(r['trace_progress_m']) for r in selected)
        segments={}
        for i,distance in enumerate(lengths):
            lo=max(first,progress[i])-progress[i];hi=min(last,progress[i+1])-progress[i]
            if hi-lo<=1e-7:continue
            a,b=trace['node_ids'][i:i+2]
            key=f"w{trace['edge_way_ids'][i]}:n{min(a,b)}:n{max(a,b)}"
            if a>b:lo,hi=distance-hi,distance-lo
            segments.setdefault(key,[]).append(LineString([(float(lo),0),(float(hi),0)]))
        geometry={key:unary_union(value) for key,value in segments.items()}
        route_geometry[rid]=geometry
        assert int(row['stop_occurrences'])==len(selected)
        assert int(row['selected_stop_member_occurrences'])==sum(r['stop_representation']=='stop' for r in selected)
        assert len(geometry)==int(row['unique_source_segments'])
        assert abs(sum(g.length for g in geometry.values())-float(row['unique_traversed_source_geometry_m']))<1e-6
    overlaps=read_gzip(OUT/'route-pair-overlap.csv.gz');seen=set();maximum_error=0.
    for row in overlaps:
        a,b=row['first_relation'],row['second_relation'];pair=frozenset([a,b])
        assert pair not in seen and len(pair)==2;seen.add(pair)
        first,second=route_geometry[a],route_geometry[b]
        keys=first.keys()&second.keys();union=first.keys()|second.keys()
        shared=math.fsum(first[key].intersection(second[key]).length for key in keys)
        length=math.fsum(g.length for g in first.values())+math.fsum(g.length for g in second.values())-shared
        error=abs(shared-float(row['shared_source_geometry_m']));maximum_error=max(maximum_error,error)
        assert error<1e-6 and int(row['shared_source_segment_keys'])==len(keys) and int(row['union_source_segment_keys'])==len(union)
        assert abs(float(row['length_jaccard'])-shared/length)<1e-10
        assert abs(float(row['segment_key_jaccard'])-len(keys)/len(union))<1e-12
    assert seen=={frozenset(p) for p in itertools.combinations(route_geometry,2)} and len(seen)==300
    features=read_gzip(OUT/'street-features.csv.gz');index={r['unit']:r for r in features}
    db=sqlite3.connect((ROOT/'research/model/m2-v2/network.sqlite').as_uri()+'?mode=ro',uri=True)
    connections={};relations={};lengths={}
    for connection,unit,distance in db.execute('select connection_id,street_segment,overlap_m from bus_dependencies'):
        connections.setdefault(unit,set()).add(connection)
        relations.setdefault(unit,set()).add(connection.split(':')[0])
        lengths.setdefault(unit,[]).append(distance)
    db.close();assert set(index)==set(connections) and len(index)==1684
    for unit,row in index.items():
        assert int(row['dependent_bus_relations'])==len(relations[unit])
        assert int(row['dependent_connections'])==len(connections[unit])
        assert set(json.loads(row['route_ids_json']))==relations[unit]
        assert abs(float(row['dependent_interval_occurrence_m'])-math.fsum(lengths[unit]))<1e-6
        assert relations[unit]=={rid for rid,geometry in route_geometry.items() if unit in geometry}
    report={'status':'passed','all_relations_replayed':len(route_geometry),'all_distinct_pairs_replayed':len(seen),
            'all_source_dependency_units_replayed':len(index),'maximum_shared_length_difference_m':maximum_error,
            'method':'Independent GEOS unary_union/intersection of source-key intervals; dependency incidence reconciled with complete stored M2 table.',
            'source_code_sha256':sha(Path(__file__))}
    if write:
        (OUT/'route-structure-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report));return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    run(write=not args.check_only)
