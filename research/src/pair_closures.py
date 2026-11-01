"""Protocol-driven paired street closures using exact stop-metric contraction."""
import argparse
import collections
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import random
import time

import numpy as np

from .accessibility import ROOT,Stop,load_model,solve
from .compact_accessibility import CompactModel
from .single_closures import retained_rides


_WORKER=None


def initialize_worker(compact,ride_rows,stop_ids,modes,active,boardings,grid):
    global _WORKER
    _WORKER=(compact,ride_rows,stop_ids,modes,active,boardings,grid)


def evaluate_batch(unions):
    """Same deterministic equations/checks as the serial compact evaluation."""
    compact,ride_rows,stop_ids,modes,active,boardings,grid=_WORKER
    result=[]
    for failed in unions:
        counts={};layers={}
        for name,allowed in modes.items():
            rides=retained_rides(ride_rows,stop_ids,allowed,set(failed))
            costs=compact.costs(rides,boardings,active[name]);layers[name]=costs
            if any(not np.all(b<=a) for a,b in zip(costs,costs[1:])):raise AssertionError('Boarding monotonicity')
            counts[name]=[int(np.count_nonzero(costs[k+1]<=w)) for k,w in grid]
        if any(not np.all(a<=b) for a,b in zip(layers['bus_metro'],layers['bus'])):
            raise AssertionError('Metro monotonicity')
        result.append((failed,counts))
    return result


def pair_domain(groups):
    """All signature pairs representing distinct street pairs, including diagonals."""
    rows=[];unions=set()
    for i,a in enumerate(groups):
        for j in range(i,len(groups)):
            b=groups[j]
            weight=math.comb(len(a['streets']),2) if i==j else len(a['streets'])*len(b['streets'])
            if not weight:continue
            union=tuple(sorted(set(a['failed_connections'])|set(b['failed_connections'])))
            rows.append((i,j,weight,union));unions.add(union)
    return rows,sorted(unions)


def interaction(joint,first,second):return joint-first-second


def physical_pair(first,second,rank,same_group=False):
    """Canonical within-block order: cross product, or lexicographic combinations."""
    if not same_group:return first[rank//len(second)],second[rank%len(second)]
    for index in range(len(first)-1):
        count=len(first)-index-1
        if rank<count:return first[index],first[index+1+rank]
        rank-=count
    raise ValueError('Pair rank outside block')


def write_gzip_csv(path,fields,rows):
    # mtime and filename are fixed for reproducible compressed public artifacts.
    with path.open('wb') as raw:
        with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as compressed:
            with io.TextIOWrapper(compressed,encoding='utf-8',newline='') as stream:
                writer=csv.writer(stream,lineterminator='\n');writer.writerow(fields);writer.writerows(rows)


def run(network,output,config,protocol_path,selection_reference=None,workers=1):
    output=output.resolve()
    if not output.is_relative_to(ROOT/'research/runs'):raise ValueError('Output must stay in research/runs')
    if output.exists():raise FileExistsError(output)
    if workers<1:raise ValueError('workers must be positive')
    started=time.perf_counter();protocol=json.loads(protocol_path.read_text())
    source=ROOT/'research/reports/m3-single-closures-2026-11-01'
    groups=json.loads((source/'groups.json').read_text())
    single_summary=json.loads((source/'summary.json').read_text())
    with (source/'effects.csv').open(newline='') as stream:single=list(csv.DictReader(stream))
    pairs,unions=pair_domain(groups);union_ids={u:i for i,u in enumerate(unions)}
    total=sum(row[2] for row in pairs);streets=sum(len(g['streets']) for g in groups)
    if total!=math.comb(streets,2):raise AssertionError('Pair multiplicity mismatch')
    output.mkdir(parents=True)
    domain={'street_count':streets,'street_pairs':total,'signature_pairs':len(pairs),'union_count':len(unions),
            'same_signature_street_pairs':sum(n for a,b,n,u in pairs if a==b)}
    def save_json(name,value):
        (output/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
    save_json('protocol.json',protocol);save_json('domain.json',domain)
    print('Pair domain',json.dumps(domain),flush=True)
    m=load_model(network,config)
    if (m.network_hash,m.config_hash)!=(single_summary['network_sha256'],single_summary['config_sha256']):
        raise ValueError('Pair and published single-closure inputs differ')
    accepted=[r for r in m.connectors.values() if r[1]=='building' and r[5]=='geometric_candidate']
    anchors=np.array([m.node_ids[r[3]] for r in accepted]);access=np.array([r[4] for r in accepted])
    cutoff=max(m.cfg['walking_budgets_m']);boardings=max(m.cfg['max_line_changes'])+1
    grid=[(k,w) for k in m.cfg['max_line_changes'] for w in m.cfg['walking_budgets_m']]
    modes={'bus':{'bus'},'bus_metro':{'bus','metro'}}
    compact=CompactModel(m.adjacency,m.stops,m.targets,anchors,access,cutoff)
    active={name:np.array([m.stop_modes[key] in allowed for key in m.stop_keys]) for name,allowed in modes.items()}
    def evaluate(failed,check_full=False):
        result={};mode_costs={}
        for name,allowed in modes.items():
            rides=retained_rides(m.ride_rows,m.stop_ids,allowed,set(failed))
            costs=compact.costs(rides,boardings,active[name]);mode_costs[name]=costs
            result[name]=[int(np.count_nonzero(costs[k+1]<=w)) for k,w in grid]
            if check_full:
                stops=[Stop(s.anchor,s.access_m,s.board and bool(active[name][i]),s.alight and bool(active[name][i])) for i,s in enumerate(m.stops)]
                full=solve(m.adjacency,stops,rides,m.targets,boardings,cutoff)
                for b in range(boardings+1):
                    reference=full[b][anchors]+access;reference[reference>cutoff]=np.inf
                    np.testing.assert_allclose(costs[b],reference,rtol=1e-12,atol=1e-8)
                if result[name]!=[int(np.count_nonzero(full[k+1][anchors]+access<=w)) for k,w in grid]:
                    raise AssertionError('Full-network threshold mismatch')
            if any(not np.all(b<=a) for a,b in zip(costs,costs[1:])):raise AssertionError('Boarding monotonicity')
        if any(not np.all(a<=b) for a,b in zip(mode_costs['bus_metro'],mode_costs['bus'])):
            raise AssertionError('Metro monotonicity')
        return result
    baseline=evaluate((),True)
    single_losses={r['signature']:{name:[0]*len(grid) for name in modes} for r in single}
    for r in single:
        index=grid.index((int(r['max_line_changes']),int(r['walking_budget_m'])))
        for name in modes:single_losses[r['signature']][name][index]=int(r[name+'_loss_buildings'])
    cache={};checked=0
    for index,g in enumerate(groups):
        failed=tuple(sorted(g['failed_connections']))
        value=evaluate(failed,index in [0,59,118,177,237])
        for name in modes:
            if value[name]!=[baseline[name][j]-single_losses[g['signature']][name][j] for j in range(len(grid))]:
                raise AssertionError('Published single-closure mismatch')
        cache[failed]=value;checked+=1
    print('Validated baseline and',checked,'single signatures',flush=True)
    new=[u for u in unions if u not in cache]
    indices=np.linspace(0,len(new)-1,min(len(new),protocol['benchmark_union_count']),dtype=int)
    probe=[new[int(i)] for i in indices]
    bench=time.perf_counter()
    for index,u in enumerate(probe):cache[u]=evaluate(u,index in [0,len(probe)//2,len(probe)-1])
    # Exclude the separately measured full-solver checks from cost projection.
    bench=time.perf_counter()
    for u in probe:cache[u]=evaluate(u)
    per_union=(time.perf_counter()-bench)/len(probe)
    projected=per_union*len(new)
    force_exhaustive=protocol.get('scope')=='exhaustive'
    exhaustive=force_exhaustive or projected<=protocol['maximum_projected_exhaustive_seconds']
    fixed_selection=json.loads(selection_reference.read_text()) if selection_reference else None
    if fixed_selection is not None:exhaustive=fixed_selection['exhaustive']
    if force_exhaustive and not exhaustive:raise ValueError('Exhaustive protocol cannot use a sampled selection')
    selection={'exhaustive':exhaustive,'benchmark_seconds_per_union':per_union,
        'projected_exhaustive_seconds':projected,'benchmark_union_count':len(probe),
        'decision_basis':'runtime only; no interaction outcomes used for selection'}
    if fixed_selection is not None:selection['decision_basis']='reproduce the fixed recorded selection; current benchmark does not change the sample'
    if force_exhaustive:selection['decision_basis']='explicit exhaustive protocol; runtime does not change scope; no sampling'
    if not exhaustive:
        # Sample ranks uniformly over physical street pairs, not signature pairs.
        ranks=sorted(random.Random(protocol['fallback_seed']).sample(range(total),min(total,protocol['fallback_uniform_street_pair_sample_size'])))
        if fixed_selection is not None and ranks!=fixed_selection['sampled_street_pair_ranks']:
            raise ValueError('Recorded sample differs from protocol seed/domain')
        selected=[];offset=0;position=0;sampled_pairs=[]
        for a,b,n,u in pairs:
            count=0
            while position<len(ranks) and ranks[position]<offset+n:
                first,second=physical_pair(groups[a]['streets'],groups[b]['streets'],ranks[position]-offset,a==b)
                sampled_pairs.append((ranks[position],first,second))
                count+=1;position+=1
            if count:selected.append((a,b,count,u))
            offset+=n
        pairs=selected;selection['sampled_street_pair_ranks']=ranks
        write_gzip_csv(output/'sampled-street-pairs.csv.gz',['pair_rank','first_street','second_street'],sampled_pairs)
    required=sorted({u for _,_,_,u in pairs});selection['evaluated_pair_unions']=len(required)
    save_json('selection.json',selection)
    print('Selection',json.dumps({k:v for k,v in selection.items() if k!='sampled_street_pair_ranks'}),flush=True)
    last=time.perf_counter();pending=[u for u in required if u not in cache]
    args=(compact,m.ride_rows,m.stop_ids,modes,active,boardings,grid)
    if workers==1:
        initialize_worker(*args)
        batch_results=map(evaluate_batch,[pending[i:i+64] for i in range(0,len(pending),64)])
        executor=None
    else:
        executor=ProcessPoolExecutor(max_workers=workers,initializer=initialize_worker,initargs=args)
        # Duplicate reference scenarios verify worker serialization/evaluation too.
        checks=[(),tuple(sorted(groups[0]['failed_connections']))]
        batch_results=executor.map(evaluate_batch,[checks]+[pending[i:i+64] for i in range(0,len(pending),64)])
    try:
        with (output/'union-checkpoints.jsonl').open('w',encoding='utf-8',newline='\n') as checkpoint:
            for batch in batch_results:
                for u,value in batch:
                    if u==():
                        if value!=baseline:raise AssertionError('Worker baseline mismatch')
                    elif u in cache:
                        if value!=cache[u]:raise AssertionError('Worker single mismatch')
                    else:cache[u]=value
                    checkpoint.write(json.dumps([u,value],separators=(',',':'))+'\n')
                checkpoint.flush()
                if time.perf_counter()-last>10:
                    done=sum(u in cache for u in required)
                    print('Pair unions',done,'/',len(required),'elapsed',round(time.perf_counter()-started,1),flush=True);last=time.perf_counter()
    finally:
        if executor is not None:executor.shutdown(wait=True,cancel_futures=True)
    if any(u not in cache for u in required):raise AssertionError('Incomplete union computation')
    evaluated_pair_count=sum(n for a,b,n,u in pairs)
    summaries=[];histograms=[];top_cases=[]
    for j,(k,w) in enumerate(grid):
        item={'max_line_changes':k,'walking_budget_m':w}
        for name in modes:
            hist=collections.Counter();top=[];min_joint=0;max_joint=0
            for a,b,n,u in pairs:
                joint=baseline[name][j]-cache[u][name][j]
                first=single_losses[groups[a]['signature']][name][j];second=single_losses[groups[b]['signature']][name][j]
                if joint<max(first,second):raise AssertionError('Pair loss smaller than constituent loss')
                c=interaction(joint,first,second);hist[c]+=n;max_joint=max(max_joint,joint)
                top.append((c,a,b,n,union_ids[u],joint,first,second))
            item[name]={'negative_pairs':sum(n for c,n in hist.items() if c<0),
                'zero_pairs':hist[0],'positive_pairs':sum(n for c,n in hist.items() if c>0),
                'minimum_interaction_buildings':min(hist),'maximum_interaction_buildings':max(hist),
                'mean_interaction_buildings':sum(c*n for c,n in hist.items())/evaluated_pair_count,
                'maximum_joint_loss_buildings':max_joint}
            histograms.append({'mode':name,'max_line_changes':k,'walking_budget_m':w,
                               'counts':dict(sorted(hist.items()))})
            for entry in sorted(top,reverse=True)[:5]+sorted(top)[:5]:
                c,a,b,n,uid,joint,first,second=entry
                top_cases.append({'mode':name,'max_line_changes':k,'walking_budget_m':w,
                    'first_signature':groups[a]['signature'],'second_signature':groups[b]['signature'],
                    'street_pair_count':n,'union_id':uid,'interaction_buildings':c,
                    'joint_loss_buildings':joint,'first_loss_buildings':first,'second_loss_buildings':second})
        summaries.append(item)
    write_gzip_csv(output/'signature-pairs.csv.gz',['first_signature','second_signature','street_pair_count','union_id'],
        [(groups[a]['signature'],groups[b]['signature'],n,union_ids[u]) for a,b,n,u in pairs])
    write_gzip_csv(output/'unions.csv.gz',['union_id','failed_connections_json'],
        [(union_ids[u],json.dumps(u,separators=(',',':'))) for u in required])
    write_gzip_csv(output/'union-effects.csv.gz',['union_id','max_line_changes','walking_budget_m','bus_accessible','bus_metro_accessible'],
        [(union_ids[u],k,w,cache[u]['bus'][j],cache[u]['bus_metro'][j]) for u in required for j,(k,w) in enumerate(grid)])
    if exhaustive:
        street_keys=[street for g in groups for street in g['streets']]
        street_ids={street:i for i,street in enumerate(street_keys)}
        write_gzip_csv(output/'street-index.csv.gz',['street_index','street','signature'],
            [(street_ids[street],street,g['signature']) for g in groups for street in g['streets']])
        def physical_rows():
            rank=0
            for a,b,n,u in pairs:
                for local in range(n):
                    first,second=physical_pair(groups[a]['streets'],groups[b]['streets'],local,a==b)
                    yield rank,street_ids[first],street_ids[second],union_ids[u]
                    rank+=1
        write_gzip_csv(output/'physical-pairs.csv.gz',['pair_rank','first_street_index','second_street_index','union_id'],physical_rows())
    save_json('interaction-distributions.json',histograms);save_json('extreme-cases.json',top_cases)
    summary={'stage':'m4-pairs-exhaustive-v1' if force_exhaustive else 'm4-pairs-v1','network_sha256':m.network_hash,'config_sha256':m.config_hash,
        'protocol_sha256':hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        'source_code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('compact_accessibility.py')]},
        'domain':domain,'selection':{k:v for k,v in selection.items() if k!='sampled_street_pair_ranks'},
        'evaluated_street_pairs':evaluated_pair_count,'all_buildings':single_summary['all_buildings'],
        'single_signatures_reproduced':checked,'full_graph_scenarios_compared':9,
        'workers':workers,'union_scenarios_evaluated':len(required),'signature_pairs_evaluated':len(pairs),
        'distance_tolerance':'1e-8 m absolute / 1e-12 relative; exact threshold-count agreement required',
        'interaction_unit':'building count; divide by all_buildings for accessibility-share interaction',
        'pair_measure':'each distinct unordered physical source-segment pair has equal weight; no failure-probability interpretation',
        'results':summaries,'elapsed_seconds':time.perf_counter()-started,
        'artifact_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.name!='union-checkpoints.jsonl'}}
    save_json('summary.json',summary);print(json.dumps(summary,indent=2),flush=True)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network',type=Path,default=ROOT/'research/model/m2-v2/network.sqlite')
    parser.add_argument('--output',type=Path,default=ROOT/'research/runs/m4-pairs-v1')
    parser.add_argument('--config',type=Path,default=ROOT/'research/config/baseline.json')
    parser.add_argument('--protocol',type=Path,default=ROOT/'research/config/pair-protocol.json')
    parser.add_argument('--selection',type=Path,help='Reproduce a fixed published selection instead of selecting scope by current runtime')
    parser.add_argument('--workers',type=int,default=1)
    a=parser.parse_args();run(a.network,a.output,a.config,a.protocol,a.selection,a.workers)
