"""Exhaustive observed street-segment closures with exact dependency grouping."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import time

import numpy as np

from .accessibility import ROOT, Stop, load_model, solve


def dependency_groups(rows):
    """Group streets only when their sets of failed connection IDs are equal."""
    dependencies=collections.defaultdict(set)
    for street,connection in rows:dependencies[street].add(connection)
    groups=collections.defaultdict(list)
    for street,connections in sorted(dependencies.items()):
        groups[tuple(sorted(connections))].append(street)
    return dict(sorted(groups.items()))


def retained_rides(ride_rows,stop_ids,modes,failed):
    return [(stop_ids[a],stop_ids[b]) for key,a,b,mode in ride_rows
            if mode in modes and key not in failed]


def run(network,output,config,baseline_reference=None):
    output=output.resolve()
    if not output.is_relative_to(ROOT/'research/runs'):
        raise ValueError('Output must stay in research/runs')
    if output.exists():raise FileExistsError(output)
    started=time.perf_counter();m=load_model(network,config)
    db=sqlite3.connect(network.resolve().as_uri()+'?mode=ro',uri=True)
    dependency_rows=list(db.execute('select street_segment,connection_id from bus_dependencies'))
    db.close()
    bus_ids={key for key,_,_,mode in m.ride_rows if mode=='bus'}
    if any(key not in bus_ids for _,key in dependency_rows):
        raise ValueError('Dependency refers to a non-bus or missing connection')
    groups=dependency_groups(dependency_rows)
    if not groups:raise ValueError('No observed bus street dependencies')
    cutoff=max(m.cfg['walking_budgets_m']);boardings=max(m.cfg['max_line_changes'])+1
    buildings=[r for r in m.connectors.values() if r[1]=='building']
    accepted=[r for r in buildings if r[5]=='geometric_candidate']
    anchors=np.array([m.node_ids[r[3]] for r in accepted],dtype=int)
    access=np.array([r[4] for r in accepted])
    walking=solve(m.adjacency,[],[],m.targets,0,cutoff)[0]
    grid=[(k,w) for k in m.cfg['max_line_changes'] for w in m.cfg['walking_budgets_m']]
    def counts(layers):
        return [int(np.count_nonzero(layers[k+1][anchors]+access<=w)) for k,w in grid]
    modes={'bus':{'bus'},'bus_metro':{'bus','metro'}}
    stops={name:[Stop(s.anchor,s.access_m,s.board and m.stop_modes[key] in allowed,
                     s.alight and m.stop_modes[key] in allowed)
                 for key,s in zip(m.stop_keys,m.stops)] for name,allowed in modes.items()}
    baseline_layers={name:solve(m.adjacency,stops[name],retained_rides(m.ride_rows,m.stop_ids,allowed,set()),
                               m.targets,boardings,cutoff,walking) for name,allowed in modes.items()}
    baseline={name:counts(layers) for name,layers in baseline_layers.items()}
    baseline_reference=baseline_reference or ROOT/'research/reports/m3-2026-11-01-summary.json'
    expected=json.loads(baseline_reference.read_text())
    if expected['network_sha256']!=m.network_hash or expected['config_sha256']!=m.config_hash:
        raise ValueError('Published baseline uses different inputs')
    for name in modes:
        reference={(r['max_line_changes'],r['walking_budget_m']):r['accessible_buildings']
                   for r in expected['results'] if r['mode']==name}
        if baseline[name]!=[reference[pair] for pair in grid]:
            raise AssertionError('Baseline regression')
    output.mkdir(parents=True)
    group_rows=[];results=[];street_rows=[]
    print('Testing',sum(map(len,groups.values())),'streets in',len(groups),'exact groups',flush=True)
    for index,(failed,streets) in enumerate(groups.items(),1):
        signature=hashlib.sha256(json.dumps(failed,separators=(',',':')).encode()).hexdigest()
        group_rows.append({'signature':signature,'failed_connections':list(failed),'streets':streets})
        street_rows.extend((street,signature,len(failed)) for street in streets)
        scenario={}
        layers_by_mode={}
        for name,allowed in modes.items():
            layers=solve(m.adjacency,stops[name],retained_rides(m.ride_rows,m.stop_ids,allowed,set(failed)),
                         m.targets,boardings,cutoff,walking)
            # Stronger than count checks: no node gains walking-budget accessibility.
            if any(not np.all(after>=before) for before,after in zip(baseline_layers[name],layers)):
                raise AssertionError('Deletion improved a node cost')
            if any(not np.all(b<=a) for a,b in zip(layers,layers[1:])):
                raise AssertionError('Larger boarding budget worsened cost')
            scenario[name]=counts(layers);layers_by_mode[name]=layers
        if any(not np.all(full<=bus) for full,bus in zip(layers_by_mode['bus_metro'],layers_by_mode['bus'])):
            raise AssertionError('Adding metro worsened a node cost')
        for j,(k,w) in enumerate(grid):
            bus_loss=baseline['bus'][j]-scenario['bus'][j]
            metro_loss=baseline['bus_metro'][j]-scenario['bus_metro'][j]
            results.append({'signature':signature,'street_count':len(streets),'max_line_changes':k,
                'walking_budget_m':w,'bus_accessible':scenario['bus'][j],
                'bus_metro_accessible':scenario['bus_metro'][j],
                'bus_loss_buildings':bus_loss,'bus_metro_loss_buildings':metro_loss,
                'bus_loss_share_all':bus_loss/len(buildings),
                'bus_metro_loss_share_all':metro_loss/len(buildings),
                'delta_metro_benefit_buildings':bus_loss-metro_loss})
        print(f'Completed {index}/{len(groups)} ({time.perf_counter()-started:.1f}s)',flush=True)
    def write_csv(path,rows,fields):
        with path.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    write_csv(output/'effects.csv',results,list(results[0]))
    write_csv(output/'streets.csv',[dict(zip(['street','signature','failed_connection_count'],r)) for r in street_rows],
              ['street','signature','failed_connection_count'])
    (output/'groups.json').write_text(json.dumps(group_rows,indent=2)+'\n',encoding='utf-8',newline='\n')
    grid_summary=[]
    for k,w in grid:
        rows=[r for r in results if r['max_line_changes']==k and r['walking_budget_m']==w]
        item={'max_line_changes':k,'walking_budget_m':w}
        for mode in modes:
            column=mode+'_loss_buildings'
            item[mode]={'baseline_accessible':baseline[mode][grid.index((k,w))],
                'streets_with_positive_loss':sum(r['street_count'] for r in rows if r[column]>0),
                'maximum_loss_buildings':max(r[column] for r in rows),
                'mean_loss_buildings_over_observed_streets':sum(r[column]*r['street_count'] for r in rows)/len(street_rows)}
        item['streets_with_negative_delta_metro_benefit']=sum(r['street_count'] for r in rows if r['delta_metro_benefit_buildings']<0)
        grid_summary.append(item)
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())}
    summary={'stage':'m3-single-closures-v1','network_sha256':m.network_hash,'config_sha256':m.config_hash,
        'observed_streets':len(street_rows),'distinct_dependency_signatures':len(groups),
        'all_buildings':len(buildings),'connected_buildings':len(accepted),
        'closure_policy':'remove dependent consecutive-stop bus arcs; walking and metro fixed; no rerouting',
        'grouping':'exact equality of failed connection ID sets, no approximation',
        'domain':'all street segments supporting the 11 accepted bus relations; not all Tehran streets',
        'loss_definition':'baseline accessible building count minus closure accessible count; shares divide by all buildings',
        'delta_metro_definition':'M(F)-M(empty) = bus_loss - bus_metro_loss; may have either sign',
        'invariants':'reference baseline reproduced; nodewise deletion, boarding-budget and added-metro monotonicity passed',
        'results':grid_summary,'artifact_sha256':files,'elapsed_seconds':time.perf_counter()-started}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(summary,indent=2),flush=True)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network',type=Path,default=ROOT/'research/model/m2-v2/network.sqlite')
    parser.add_argument('--output',type=Path,default=ROOT/'research/runs/m3-single-closures-v1')
    parser.add_argument('--config',type=Path,default=ROOT/'research/config/baseline.json')
    parser.add_argument('--baseline',type=Path,help='Matching baseline summary; default is published M3 baseline')
    args=parser.parse_args();run(args.network,args.output,args.config,args.baseline)
