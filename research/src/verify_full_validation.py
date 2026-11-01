"""Verify completeness of every stored full-validation evidence table."""
import collections
import csv
import gzip
import hashlib
import json

import numpy as np

from .accessibility import ROOT,load_model,solve


def run():
    base=ROOT/'research/reports/validation-2026-11-01'
    load=lambda name:json.loads((base/name).read_text())
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    lengths=load('all-lengths.json');solvers=load('all-solvers.json');routes=load('route-dispositions.json')
    assert lengths['status']==solvers['status']=='passed' and routes['status']=='completed'
    assert lengths['network_sha256']==solvers['network_sha256']
    assert sha(base/'all-way-lengths.csv.gz')==lengths['all_way_table_sha256']
    assert sha(base/'all-solver-scenarios.csv.gz')==solvers['scenario_table_sha256']
    assert lengths['failure_count']==0 and not lengths['failures']
    with gzip.open(base/'all-way-lengths.csv.gz','rt',newline='') as stream:way_rows=list(csv.DictReader(stream))
    assert len(way_rows)==len({r['way_id'] for r in way_rows})==lengths['walking_ways_checked']
    assert sum(int(r['stored_edges_checked']) for r in way_rows)==lengths['stored_edges_checked']
    assert sum(int(r['source_segments_checked']) for r in way_rows)==lengths['source_segments_checked']
    assert all(abs(float(r['source_length_m'])-float(r['graph_length_m']))<=lengths['absolute_tolerance_m'] for r in way_rows)
    single=ROOT/'research/reports/m3-single-closures-2026-11-01'
    groups=json.loads((single/'groups.json').read_text())
    expected={tuple()};expected.update(tuple(g['failed_connections']) for g in groups)
    pairs=ROOT/'research/reports/m4-pairs-exhaustive-2026-11-01'
    with gzip.open(pairs/'unions.csv.gz','rt',newline='') as stream:expected.update(tuple(json.loads(r['failed_connections_json'])) for r in csv.DictReader(stream))
    digests={hashlib.sha256(json.dumps(value,separators=(',',':')).encode()).hexdigest() for value in expected}
    assert len(digests)==len(expected)==solvers['distinct_failed_sets_checked']
    observed=set();maximum=0.;cells=0
    with gzip.open(base/'all-solver-scenarios.csv.gz','rt',newline='') as stream:
        for row in csv.DictReader(stream):
            key=(row['failed_set_sha256'],row['mode']);assert key not in observed;observed.add(key)
            assert row['status']=='passed'
            assert int(row['origin_budget_cells_checked'])==solvers['origins_checked_per_layer']*solvers['boarding_layers']
            maximum=max(maximum,float(row['maximum_absolute_difference_m']));cells+=int(row['origin_budget_cells_checked'])
    assert observed=={(value,mode) for value in digests for mode in ['bus','bus_metro']}
    assert cells==solvers['origin_budget_mode_scenario_cells_checked']
    assert maximum==solvers['maximum_absolute_difference_m']
    assert len(routes['cases'])==len({r['relation_id'] for r in routes['cases']})==routes['relations_reviewed']==28
    assert routes['admitted']==0 and routes['final_exclusions']==28 and not routes['primary_model_changed']
    assert all(c['backward_transitions'] and c['final_decision'].startswith('excluded_') for c in routes['cases'])
    # Directly recompute the three walking-only published baseline counts too.
    model=load_model(ROOT/'research/model/m2-v2/network.sqlite',ROOT/'research/config/baseline.json')
    cutoff=max(model.cfg['walking_budgets_m'])
    walking=solve(model.adjacency,[],[],model.targets,0,cutoff)[0]
    buildings=[r for r in model.connectors.values() if r[1]=='building']
    costs=np.array([walking[model.node_ids[r[3]]]+r[4] if r[5]=='geometric_candidate' else np.inf for r in buildings])
    baseline=json.loads((ROOT/'research/reports/m3-2026-11-01-summary.json').read_text())
    walking_counts=[]
    for row in baseline['results']:
        if row['mode']=='walk':
            count=int(np.count_nonzero(costs<=row['walking_budget_m']))
            assert count==row['accessible_buildings']
            walking_counts.append({'walking_budget_m':row['walking_budget_m'],'accessible_buildings':count})
    report={'status':'passed','way_rows':len(way_rows),'solver_scenario_mode_rows':len(observed),
            'origin_budget_cells':cells,'route_dispositions':len(routes['cases']),'walking_only_counts':walking_counts}
    (base/'completeness.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report));return report


if __name__=='__main__':run()
