"""Compare every primary origin vector before/after compact JIT compilation."""
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .accessibility import ROOT,load_model
from .compact_accessibility import CompactModel
from .compiled_compact import evaluate
from .single_closures import retained_rides


def run():
    started=time.perf_counter();out=ROOT/'research/reports/sensitivity-2026-11-01';out.mkdir(exist_ok=True)
    m=load_model(ROOT/'research/model/m2-v2/network.sqlite',ROOT/'research/config/baseline.json')
    origins=[r for r in m.connectors.values() if r[1]=='building' and r[5]=='geometric_candidate']
    anchors=np.array([m.node_ids[r[3]] for r in origins]);access=np.array([r[4] for r in origins])
    model=CompactModel(m.adjacency,m.stops,m.targets,anchors,access,2000.)
    m.adjacency=[];m.node_ids={}
    modes={'bus':{'bus'},'bus_metro':{'bus','metro'}}
    active={name:np.array([m.stop_modes[k] in allowed for k in m.stop_keys]) for name,allowed in modes.items()}
    grid=[(k,w) for k in m.cfg['max_line_changes'] for w in m.cfg['walking_budgets_m']]
    single=ROOT/'research/reports/m3-single-closures-2026-11-01';pairs=ROOT/'research/reports/m4-pairs-exhaustive-2026-11-01'
    groups=json.loads((single/'groups.json').read_text());group_map={g['signature']:tuple(g['failed_connections']) for g in groups}
    scenarios={():None};scenarios.update({v:None for v in group_map.values()})
    with gzip.open(pairs/'unions.csv.gz','rt',newline='') as f:uid={int(r['union_id']):tuple(json.loads(r['failed_connections_json'])) for r in csv.DictReader(f)}
    scenarios.update({v:None for v in uid.values()});expected={}
    for r in json.loads((ROOT/'research/reports/m3-2026-11-01-summary.json').read_text())['results']:
        if r['mode']!='walk':expected[(),r['mode'],r['max_line_changes'],r['walking_budget_m']]=r['accessible_buildings']
    with (single/'effects.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            for mode in modes:expected[group_map[r['signature']],mode,int(r['max_line_changes']),int(r['walking_budget_m'])]=int(r[mode+'_accessible'])
    with gzip.open(pairs/'union-effects.csv.gz','rt',newline='') as f:
        for r in csv.DictReader(f):
            for mode in modes:expected[uid[int(r['union_id'])],mode,int(r['max_line_changes']),int(r['walking_budget_m'])]=int(r[mode+'_accessible'])
    def calculate(failed,compare=True):
        values={};maximum=0.
        for mode,allowed in modes.items():
            rides=retained_rides(m.ride_rows,m.stop_ids,allowed,set(failed))
            result=evaluate(model,m.stops,rides,3,2000.,active[mode]);values[mode]=result
            if compare:
                original=np.array(model.costs(rides,3,active[mode]))
                np.testing.assert_allclose(result,original,rtol=1e-12,atol=1e-8)
                assert np.array_equal(np.isfinite(result),np.isfinite(original))
                finite=np.isfinite(result)
                maximum=max(maximum,float(np.max(np.abs(result[finite]-original[finite]))))
            for k,w in grid:assert int(np.count_nonzero(result[k+1]<=w))==expected[failed,mode,k,w]
        return maximum,values
    _,baseline=calculate(())
    masks={};metadata=[]
    for index,g in enumerate(groups):
        _,values=calculate(tuple(g['failed_connections']),False)
        for mode in modes:
            for k,w in grid:
                loss=(baseline[mode][k+1]<=w)&(values[mode][k+1]>w)
                masks[f'g{index}_{mode}_k{k}_w{w}']=np.packbits(loss,bitorder='little')
        metadata.append({'group_index':index,'signature':g['signature']})
    np.savez_compressed(out/'single-loss-masks.npz',**masks)
    (out/'mask-index.json').write_text(json.dumps({'origins':[r[0] for r in origins],'groups':metadata,'bitorder':'little','origin_count':len(origins)},indent=2)+'\n',encoding='utf-8',newline='\n')
    maximum=0.;done=0;last=time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as executor:
        for value,unused in executor.map(calculate,sorted(scenarios)):
            maximum=max(maximum,value);done+=1
            if time.perf_counter()-last>10:print('Compact compilation census',done,'/',len(scenarios),'seconds',round(time.perf_counter()-started,1),flush=True);last=time.perf_counter()
    assert done==len(scenarios)
    report={'status':'passed','failed_sets_checked':done,'modes':2,'origin_count':len(origins),'boarding_layers':4,
        'origin_budget_cells_checked':done*2*len(origins)*4,'maximum_absolute_difference_m':maximum,
        'threshold_counts':'all exactly match the published primary','elapsed_seconds':time.perf_counter()-started,
        'source_code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('compiled_compact.py')]}}
    (out/'compiled-kernel-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':run()
