"""Case-by-case disposition of every excluded strict bus relation.

Inspect frozen source members, both trace orientations, road-direction evidence,
loop/numbered-order alternatives and stop-area duplicates. No inferred sorting
is silently substituted for the primary model's recorded-order contract.
"""
import collections
import csv
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import osmium

from .accessibility import ROOT
from .extract_routes import csv_rows,order_status


def direction_limit(tags):
    """Conservative explicit direction diagnostic, not complete access routing."""
    if any('conditional' in k for k in tags):return None,'conditional access/direction not resolved'
    value=tags.get('oneway:bus',tags.get('oneway:psv',tags.get('oneway')))
    if value in ('no','0','false'):return 0,'explicit bidirectional'
    if value in ('yes','1','true'):direction=1
    elif value=='-1':direction=-1
    elif value is None and tags.get('junction')=='roundabout':direction=1
    else:return 0 if value is None else None,'no explicit limit' if value is None else 'unrecognized direction tag'
    if any(tags.get(k) in ('yes','designated','permissive') for k in ['bus:backward','psv:backward','bus:forward','psv:forward']):
        return None,'direction-specific bus access requires interpretation'
    if any('opposite' in str(v) for k,v in tags.items() if k.startswith(('busway','bus:lanes','psv:lanes'))):
        return None,'mapped contraflow lane needs explicit interpretation'
    return direction,'explicit one-way/roundabout evidence'


def run():
    cfg=json.loads((ROOT/'research/config/baseline.json').read_text());base=ROOT/'research/model/m1-v1'
    routes={r['relation_id']:r for r in csv_rows(base/'routes.csv')}
    excluded={rid:r for rid,r in routes.items() if r['status']=='needs_review'}
    assert len(excluded)==28
    stops=collections.defaultdict(list)
    for row in csv_rows(base/'stops.csv'):stops[row['route_relation_id']].append(row)
    traces=json.loads((base/'traces.json').read_text())
    needed={w for rid in excluded for w in traces[rid]['edge_way_ids']}
    pbf=ROOT/'data/extracted'/cfg['dataset_id']/'tehran_context.osm.pbf'
    class Source(osmium.SimpleHandler):
        def __init__(self):super().__init__();self.ways={};self.relations={};self.areas=collections.defaultdict(list)
        def way(self,w):
            if w.id in needed:self.ways[w.id]={'nodes':[n.ref for n in w.nodes],'tags':dict(w.tags)}
        def relation(self,r):
            if str(r.id) in excluded:self.relations[str(r.id)]={'tags':dict(r.tags),'members':[(m.type,m.ref,m.role) for m in r.members]}
            if r.tags.get('public_transport')=='stop_area':
                for m in r.members:self.areas[(m.type,m.ref)].append(r.id)
    source=Source();source.apply_file(str(pbf))
    records=[];steps=[]
    for rid,row in sorted(excluded.items(),key=lambda x:int(x[0])):
        local=stops[rid];trace=traces[rid];raw=source.relations[rid]
        progress=[float(s['trace_progress_m']) for s in local]
        backward=[]
        for a,b in zip(local,local[1:]):
            delta=float(b['trace_progress_m'])-float(a['trace_progress_m'])
            shared=set(source.areas[a['osm_type'],int(a['osm_id'])])&set(source.areas[b['osm_type'],int(b['osm_id'])])
            if delta < -cfg['stop_order_tolerance_m']:
                backward.append({'from_sequence':int(a['stop_sequence']),'to_sequence':int(b['stop_sequence']),
                    'from_osm_id':int(a['osm_id']),'to_osm_id':int(b['osm_id']),'progress_change_m':delta,
                    'shared_stop_areas':sorted(shared)})
            steps.append({'relation_id':rid,'from_sequence':a['stop_sequence'],'to_sequence':b['stop_sequence'],
                'from_osm_id':a['osm_id'],'to_osm_id':b['osm_id'],'progress_change_m':delta,
                'violates_recorded_order':delta < -cfg['stop_order_tolerance_m'],'shared_stop_areas':';'.join(map(str,sorted(shared)))})
        diagnostic=collections.Counter();source_roles=collections.Counter(m[2] for m in raw['members'] if m[0]=='w')
        roles_by_way=collections.defaultdict(set)
        for typ,wid,role in raw['members']:
            if typ=='w':roles_by_way[wid].add(role)
        for a,b,wid in zip(trace['node_ids'],trace['node_ids'][1:],trace['edge_way_ids']):
            way=source.ways[wid];pairs=set(zip(way['nodes'],way['nodes'][1:]))
            forward=(a,b) in pairs;reverse=(b,a) in pairs
            if forward==reverse:diagnostic['source_orientation_ambiguous']+=1;continue
            direction=1 if forward else -1;limit,reason=direction_limit(way['tags'])
            if ('forward' in roles_by_way[wid] and direction==1) or ('backward' in roles_by_way[wid] and direction==-1):
                diagnostic['reverse_trace_conflicts_with_explicit_member_role']+=1
            if limit is None:diagnostic['direction_needs_interpretation']+=1
            elif limit==0:diagnostic['unrestricted_by_explicit_direction']+=1
            elif direction==limit:diagnostic['forward_trace_supported_reverse_opposes_oneway']+=1
            else:diagnostic['forward_trace_opposes_explicit_oneway']+=1
        far=[int(s['osm_id']) for s in local if float(s['distance_to_trace_m'])>cfg['stop_distance_limit_m']]
        ambiguous=[int(s['osm_id']) for s in local if s['ambiguous_projection']=='True']
        forward=order_status(progress,cfg['stop_order_tolerance_m'])
        reversed_status=order_status([-p for p in progress],cfg['stop_order_tolerance_m'])
        numbered=[m for m in raw['members'] if re.search(r'(?:stop|platform):\d+$',m[2])]
        closed=trace['node_ids'][0]==trace['node_ids'][-1]
        # No case is admitted by simply forcing a preferred permutation.
        reasons=['recorded stop sequence contradicts oriented trace']
        if far:reasons.append('stop-to-trace distance exceeds initial 100 m contract')
        if ambiguous:reasons.append('ambiguous projection')
        if numbered or closed or not backward:raise AssertionError('New source-supported order alternative needs explicit resolution')
        if int(row['stop_position_candidates'])>=2:raise AssertionError('Unexamined stop-position alternative')
        decision='excluded_source_order_conflict'
        if far:decision='excluded_source_order_and_distance_conflict'
        records.append({'relation_id':int(rid),'ref':row['ref'],'source_tags':raw['tags'],
            'source_members':raw['members'],'stop_count':len(local),'stop_representation':row['selected_stop_kind'],
            'forward_order':forward,'reversed_trace_order':reversed_status,'backward_transitions':backward,
            'maximum_stop_distance_m':max(float(s['distance_to_trace_m']) for s in local),
            'far_stop_ids':far,'ambiguous_stop_ids':ambiguous,'closed_trace':closed,
            'numbered_stop_roles_available':len(numbered),'alternative_stop_positions':int(row['stop_position_candidates']),
            'oneway_diagnostic_edge_counts':dict(diagnostic),'source_way_roles':dict(source_roles),
            'source_ordered_stop_ids':[int(s['osm_id']) for s in local],
            'geometrically_sorted_stop_ids':[int(s['osm_id']) for s in sorted(local,key=lambda s:float(s['trace_progress_m']))],
            'sorting_disposition':'a derived-order hypothesis, not source-order verification; not substituted into frozen primary model',
            'final_decision':decision,'reasons':reasons,
            'resolution':'terminal exclusion under the recorded-order primary contract; not a claim of nonoperation or permanent irreparability'})
    assert len(records)==len(excluded) and {str(r['relation_id']) for r in records}==set(excluded)
    out=ROOT/'research/reports/validation-2026-11-01';out.mkdir(exist_ok=True)
    with (out/'excluded-route-transitions.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(steps[0]),lineterminator='\n');writer.writeheader();writer.writerows(steps)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report={'status':'completed','scope':'all 28 excluded strict bus relations; case-by-case source evidence and explicit final primary-model disposition',
        'relations_reviewed':len(records),'admitted':0,'final_exclusions':len(records),'primary_model_changed':False,
        'decision_counts':dict(collections.Counter(r['final_decision'] for r in records)),
        'data_limit':'derived geometric sorting may be feasible but does not resolve which conflicting source ordering is operationally correct',
        'source_pbf_sha256':sha(pbf),'source_code_sha256':sha(Path(__file__)),'cases':records}
    (out/'route-dispositions.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2));return report


if __name__=='__main__':run()
