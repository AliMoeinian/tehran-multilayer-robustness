"""Census comparison of compact and full-walking-node solver origin vectors."""
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import hashlib
import json
from pathlib import Path
import threading
import time

import numba
import numpy as np

from .accessibility import ROOT,Stop,load_model,solve
from .compact_accessibility import CompactModel
from .full_graph_reference import walking_csr,relax,solve_full
from .single_closures import retained_rides


def run(workers=4):
    started=time.perf_counter();out=ROOT/'research/reports/validation-2026-11-01';out.mkdir(exist_ok=True)
    local=ROOT/'research/runs/full-solver-census-v1';local.mkdir(exist_ok=True)
    config=ROOT/'research/config/baseline.json';network=ROOT/'research/model/m2-v2/network.sqlite'
    source=ROOT/'research/reports/m4-pairs-exhaustive-2026-11-01'
    prior=json.loads((source/'summary.json').read_text());m=load_model(network,config)
    if (prior['network_sha256'],prior['config_sha256'])!=(m.network_hash,m.config_hash):raise ValueError('Input identities differ')
    groups=json.loads((ROOT/'research/reports/m3-single-closures-2026-11-01/groups.json').read_text())
    scenarios={():{'baseline'}}
    for group in groups:scenarios.setdefault(tuple(group['failed_connections']),set()).add('single')
    with gzip.open(source/'unions.csv.gz','rt',newline='') as stream:
        for row in csv.DictReader(stream):scenarios.setdefault(tuple(json.loads(row['failed_connections_json'])),set()).add('pair')
    scenarios=sorted(scenarios)
    accepted=[r for r in m.connectors.values() if r[1]=='building' and r[5]=='geometric_candidate']
    origins=np.array([m.node_ids[r[3]] for r in accepted]);origin_access=np.array([r[4] for r in accepted])
    cutoff=float(max(m.cfg['walking_budgets_m']));max_b=max(m.cfg['max_line_changes'])+1
    grid=[(k,w) for k in m.cfg['max_line_changes'] for w in m.cfg['walking_budgets_m']]
    compact=CompactModel(m.adjacency,m.stops,m.targets,origins,origin_access,cutoff)
    csr=walking_csr(m.adjacency)
    walking=relax(*csr,np.full(len(m.adjacency),np.inf),np.array([n for n,c in m.targets]),np.array([c for n,c in m.targets]),cutoff)
    anchors=np.array([s.anchor for s in m.stops]);access=np.array([s.access_m for s in m.stops])
    modes={'bus':{'bus'},'bus_metro':{'bus','metro'}}
    active={name:np.array([m.stop_modes[key] in allowed for key in m.stop_keys]) for name,allowed in modes.items()}
    board={name:np.array([s.board for s in m.stops])&a for name,a in active.items()}
    alight={name:np.array([s.alight for s in m.stops])&a for name,a in active.items()}
    expected={}
    def key(failed,name,k,w):return (failed,name,k,w)
    baseline=json.loads((ROOT/'research/reports/m3-2026-11-01-summary.json').read_text())
    for r in baseline['results']:
        if r['mode']!='walk':expected[key((),r['mode'],r['max_line_changes'],r['walking_budget_m'])]=r['accessible_buildings']
    single_path=ROOT/'research/reports/m3-single-closures-2026-11-01/effects.csv'
    group_by_id={g['signature']:tuple(g['failed_connections']) for g in groups}
    with single_path.open(newline='') as stream:
        for r in csv.DictReader(stream):
            for mode in modes:expected[key(group_by_id[r['signature']],mode,int(r['max_line_changes']),int(r['walking_budget_m']))]=int(r[mode+'_accessible'])
    with gzip.open(source/'unions.csv.gz','rt',newline='') as stream:union_ids={int(r['union_id']):tuple(json.loads(r['failed_connections_json'])) for r in csv.DictReader(stream)}
    with gzip.open(source/'union-effects.csv.gz','rt',newline='') as stream:
        for r in csv.DictReader(stream):
            for mode in modes:expected[key(union_ids[int(r['union_id'])],mode,int(r['max_line_changes']),int(r['walking_budget_m']))]=int(r[mode+'_accessible'])
    def evaluate(failed,compare_python=False):
        rows=[]
        for mode,allowed in modes.items():
            rides=retained_rides(m.ride_rows,m.stop_ids,allowed,set(failed))
            start=np.array([a for a,b in rides],dtype=np.int64);end=np.array([b for a,b in rides],dtype=np.int64)
            reference=solve_full(*csr,anchors,access,board[mode],alight[mode],start,end,walking,max_b,cutoff,origins,origin_access)
            reduced=np.array(compact.costs(rides,max_b,active[mode]))
            finite=np.isfinite(reference);other=np.isfinite(reduced)
            if not np.array_equal(finite,other):raise AssertionError('Finite-path disagreement')
            difference=np.abs(reference[finite]-reduced[finite])
            maximum=float(np.max(difference)) if len(difference) else 0.
            np.testing.assert_allclose(reference,reduced,rtol=1e-12,atol=1e-8)
            for k,w in grid:
                n=int(np.count_nonzero(reference[k+1]<=w))
                if n!=expected[key(failed,mode,k,w)]:raise AssertionError('Published count mismatch')
                if n!=int(np.count_nonzero(reduced[k+1]<=w)):raise AssertionError('Threshold count mismatch')
            if compare_python:
                stops=[Stop(s.anchor,s.access_m,bool(board[mode][i]),bool(alight[mode][i])) for i,s in enumerate(m.stops)]
                original=solve(m.adjacency,stops,rides,m.targets,max_b,cutoff,walking)
                for b in range(max_b+1):
                    values=original[b][origins]+origin_access;values[values>cutoff]=np.inf
                    np.testing.assert_array_equal(reference[b],values)
            rows.append([hashlib.sha256(json.dumps(failed,separators=(',',':')).encode()).hexdigest(),mode,len(failed),len(origins)*(max_b+1),maximum,'passed'])
        return rows
    # Compile and check the original Python solver before the exhaustive pass.
    evaluate((),True)
    print('Full solver census scenarios',len(scenarios),'origins',len(origins),flush=True)
    maximum=0.;completed=0;last=time.perf_counter()
    with gzip.open(out/'all-solver-scenarios.csv.gz','wt',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(['failed_set_sha256','mode','failed_connection_count','origin_budget_cells_checked','maximum_absolute_difference_m','status'])
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for rows in executor.map(evaluate,scenarios):
                writer.writerows(rows);maximum=max(maximum,max(row[4] for row in rows));completed+=1
                if time.perf_counter()-last>10:
                    stream.flush();print('Solver census',completed,'/',len(scenarios),'seconds',round(time.perf_counter()-started,1),flush=True);last=time.perf_counter()
    if completed!=len(scenarios):raise AssertionError('Incomplete solver census')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report={'status':'passed','scope':'all baseline, all single signatures and every pair-failure union; all connected-origin vectors at all boarding budgets; exact published grid counts',
        'distinct_failed_sets_checked':completed,'pair_unions_checked':len(union_ids),'single_signatures_checked':len(groups),
        'modes_checked':len(modes),'origins_checked_per_layer':len(origins),'boarding_layers':max_b+1,
        'origin_budget_mode_scenario_cells_checked':completed*len(modes)*len(origins)*(max_b+1),
        'maximum_absolute_difference_m':maximum,'relative_tolerance':1e-12,'absolute_tolerance_m':1e-8,
        'published_threshold_counts':'all exactly matched','compiled_reference':'full walking-node reverse-budget DP; no contraction; fastmath disabled',
        'numba_version':numba.__version__,'network_sha256':m.network_hash,'config_sha256':m.config_hash,
        'source_code_sha256':{p.name:sha(p) for p in [Path(__file__),Path(__file__).with_name('full_graph_reference.py')]},
        'scenario_table_sha256':sha(out/'all-solver-scenarios.csv.gz'),'elapsed_seconds':time.perf_counter()-started,'workers':workers}
    (out/'all-solvers.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':run()
