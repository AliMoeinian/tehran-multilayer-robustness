"""Census saved sensitivity domains and exact tie-aware ranking comparisons."""
import collections
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import time

import numpy as np
from scipy.stats import rankdata

from .accessibility import ROOT
from .pair_closures import write_gzip_csv
from .sensitivity_runs import read_gzip

OUT=ROOT/'research/reports/sensitivity-2026-11-01'
GRID=[(k,w) for k in [0,1,2] for w in [500,1000,2000]]
MODES=['bus','bus_metro']


def correlation(a,b):
    if np.ptp(a)==0 or np.ptp(b)==0:return None
    return float(np.corrcoef(rankdata(a),rankdata(b))[0,1])


def top_set(values,fraction,among_positive=False):
    positive=values[values>0]
    if not len(positive):return np.zeros(len(values),dtype=bool)
    count=min(len(positive),math.ceil((len(positive) if among_positive else len(values))*fraction))
    cutoff=np.partition(positive,len(positive)-count)[len(positive)-count]
    return values>=cutoff


def compare(a,b):
    result={'spearman':correlation(a,b),'sign_agreement':float(np.mean(np.sign(a)==np.sign(b)))}
    nonzero=(a!=0)|(b!=0)
    result['nonzero_union_elements']=int(nonzero.sum())
    result['nonzero_union_spearman']=correlation(a[nonzero],b[nonzero]) if nonzero.any() else None
    result['nonzero_union_sign_agreement']=float(np.mean(np.sign(a[nonzero])==np.sign(b[nonzero]))) if nonzero.any() else None
    for f in [.01,.05,.1]:
        first,second=top_set(a,f),top_set(b,f);union=np.count_nonzero(first|second)
        result[f'top_{int(100*f)}pct_jaccard']=float(np.count_nonzero(first&second)/union) if union else None
        result[f'top_{int(100*f)}pct_reference_count']=int(first.sum())
        result[f'top_{int(100*f)}pct_variant_count']=int(second.sum())
        first,second=top_set(a,f,True),top_set(b,f,True);union=np.count_nonzero(first|second)
        result[f'positive_top_{int(100*f)}pct_jaccard']=float(np.count_nonzero(first&second)/union) if union else None
        result[f'positive_top_{int(100*f)}pct_reference_count']=int(first.sum())
        result[f'positive_top_{int(100*f)}pct_variant_count']=int(second.sum())
    return result


def load_variant(directory):
    summary=json.loads((directory/'summary.json').read_text())
    assert summary['status']=='passed'
    for name,digest in summary['artifact_sha256'].items():assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==digest
    units=read_gzip(directory/'units.csv.gz');groups=read_gzip(directory/'groups.csv.gz');unions=read_gzip(directory/'unions.csv.gz')
    connections=read_gzip(directory/'connections.csv.gz');singles=read_gzip(directory/'single-effects.csv.gz')
    assert len(units)==summary['unit_count'] and len({r['unit'] for r in units})==len(units)
    assert len(groups)==summary['signature_groups'] and len(unions)==summary['failed_union_count']
    group_sets={int(r['group']):set(json.loads(r['failed_connection_indices_json'])) for r in groups}
    assert set(group_sets)==set(range(len(groups)))
    union_sets={int(r['union']):set(json.loads(r['failed_connection_indices_json'])) for r in unions}
    assert set(union_sets)==set(range(len(unions)))
    connection_ids=set(range(len(connections)))
    assert all(s<=connection_ids for s in list(group_sets.values())+list(union_sets.values()))
    assert len({tuple(sorted(s)) for s in group_sets.values()})==len(groups)
    counts=collections.Counter(int(r['group']) for r in units)
    assert set(counts)==set(group_sets)
    single={};seen=set()
    for r in singles:
        g,k,w=int(r['group']),int(r['max_line_changes']),int(r['walking_budget_m']);key=g,k,w
        assert key not in seen;seen.add(key);assert (k,w) in GRID and int(r['unit_count'])==counts[g]
        single[g,k,w]=[int(r[mode+'_loss']) for mode in MODES]
    assert len(seen)==len(groups)*9
    shape=(len(groups),len(groups),9,2)
    loss=np.zeros(shape,dtype=np.int32);interaction=np.zeros(shape,dtype=np.int32)
    seen=set();multiplicity=collections.Counter();pair_counts=collections.Counter();union_values={}
    for r in read_gzip(directory/'pair-effects.csv.gz'):
        a,b,u,n,k,w=[int(r[f]) for f in ['first_group','second_group','union','unit_pair_count','max_line_changes','walking_budget_m']]
        key=a,b,k,w;assert key not in seen;seen.add(key);assert a<=b and (k,w) in GRID
        assert union_sets[u]==group_sets[a]|group_sets[b]
        expected=math.comb(counts[a],2) if a==b else counts[a]*counts[b]
        assert n==expected and n>0
        multiplicity[k,w]+=n;pair_counts[k,w]+=1;j=GRID.index((k,w))
        for md,mode in enumerate(MODES):
            joint,c=int(r[mode+'_joint_loss']),int(r[mode+'_interaction'])
            assert joint>=max(single[a,k,w][md],single[b,k,w][md])
            assert c==joint-single[a,k,w][md]-single[b,k,w][md]
            old=union_values.setdefault((u,k,w,md),joint);assert old==joint
            loss[a,b,j,md]=loss[b,a,j,md]=joint;interaction[a,b,j,md]=interaction[b,a,j,md]=c
    assert set(multiplicity)==set(GRID) and all(n==summary['physical_pair_count'] for n in multiplicity.values())
    assert all(n==summary['signature_pair_blocks'] for n in pair_counts.values())
    assert summary['physical_pair_count']==math.comb(len(units),2)
    assert len(seen)==summary['signature_pair_blocks']*9
    assert len(union_values)==len(unions)*18
    expected_blocks={(a,b) for a in counts for b in counts if a<=b and (a!=b or counts[a]>1)}
    assert {(a,b) for a,b,k,w in seen}==expected_blocks
    # Recompute every summary statistic with exact physical multiplicities.
    for record in summary['results']:
        k,w=record['max_line_changes'],record['walking_budget_m'];j=GRID.index((k,w))
        for md,mode in enumerate(MODES):
            r=record[mode];hist=collections.Counter()
            for a,b in expected_blocks:
                n=math.comb(counts[a],2) if a==b else counts[a]*counts[b]
                hist[int(interaction[a,b,j,md])]+=n
            assert r['positive_interaction_pairs']==sum(n for c,n in hist.items() if c>0)
            assert r['negative_interaction_pairs']==sum(n for c,n in hist.items() if c<0)
            assert r['zero_interaction_pairs']==hist[0]
            assert r['minimum_interaction']==min(hist) and r['maximum_interaction']==max(hist)
            assert r['maximum_joint_loss']==max(int(loss[a,b,j,md]) for a,b in expected_blocks)
            assert r['positive_loss_units']==sum(counts[g] for g in counts if single[g,k,w][md]>0)
            assert r['maximum_single_loss']==max(single[g,k,w][md] for g in counts)
            assert all(0<=single[g,k,w][md]<=r['baseline_accessible'] for g in counts)
    units=sorted(units,key=lambda r:r['unit']);ug=np.array([int(r['group']) for r in units])
    vectors=np.array([[single[g,k,w] for k,w in GRID] for g in ug],dtype=np.int32)
    return summary,units,ug,vectors,loss,interaction


def run(wait_for_complete=False):
    protocol=json.loads((ROOT/'research/config/sensitivity-protocol.json').read_text())
    names=[r['id'] for r in protocol['variants']]+['whole-osm-way']
    reference=load_variant(OUT/'variants/baseline');base,base_units,bg,bs,bl,bc=reference
    assert base['model']['all_primary_published_counts_reproduced']
    idx=np.triu_indices(len(base_units),1);rank_rows=[];strata=[];coverage=[];metro_rows=[];length_edges=[0,25,50,100,250,500,1000,float('inf')]
    def append_comparison(label,kind,metric,mode,k,w,a,b):
        record={'variant':label,'domain':kind,'metric':metric,'mode':mode,'max_line_changes':k,'walking_budget_m':w,
            'elements_compared':len(a),**compare(a,b)};rank_rows.append(record)
    # Parameter sensitivity inside the frozen baseline, relative to W1000,K1.
    main=GRID.index((1,1000))
    for j,(k,w) in enumerate(GRID):
        for md,mode in enumerate(MODES):
            append_comparison('parameter-grid','single','loss',mode,k,w,bs[:,main,md],bs[:,j,md])
            for metric,matrix in [('joint_loss',bl),('interaction',bc)]:
                a=matrix[bg[idx[0]],bg[idx[1]],main,md];b=matrix[bg[idx[0]],bg[idx[1]],j,md]
                append_comparison('parameter-grid','pair',metric,mode,k,w,a,b)
    for name in names:
        folder=OUT/'variants'/name
        if wait_for_complete and not (folder/'summary.json').exists():
            print('Waiting for completed full variant',name,flush=True)
            while not (folder/'summary.json').exists():time.sleep(5)
        data=reference if name=='baseline' else load_variant(OUT/'variants'/name)
        summary,units,ug,single,loss,c=data
        assert summary['origin_id_order_sha256']==base['origin_id_order_sha256']
        assert summary['all_buildings']==65677
        assert summary['protocol_sha256']==hashlib.sha256((ROOT/'research/config/sensitivity-protocol.json').read_bytes()).hexdigest()
        coverage.append({'variant':name,'units':len(units),'pairs':summary['physical_pair_count'],'signature_pair_blocks':summary['signature_pair_blocks'],
            'rows_checked':summary['signature_pair_blocks']*9,'failed_unions':summary['failed_union_count']})
        own_idx=idx if len(units)==len(base_units) else np.triu_indices(len(units),1)
        for j,(k,w) in enumerate(GRID):
            r=next(r for r in summary['results'] if r['max_line_changes']==k and r['walking_budget_m']==w)
            benefit=r['bus_metro']['baseline_accessible']-r['bus']['baseline_accessible']
            assert benefit>=0
            for domain,delta in [('single',single[:,j,0]-single[:,j,1]),
                ('pair',loss[ug[own_idx[0]],ug[own_idx[1]],j,0]-loss[ug[own_idx[0]],ug[own_idx[1]],j,1])]:
                assert np.all(benefit+delta>=0)
                metro_rows.append({'variant':name,'domain':domain,'max_line_changes':k,'walking_budget_m':w,
                    'baseline_metro_benefit':benefit,'elements':len(delta),
                    'metro_lower_loss':int(np.count_nonzero(delta>0)),'equal_loss':int(np.count_nonzero(delta==0)),
                    'metro_higher_loss':int(np.count_nonzero(delta<0)),
                    'minimum_delta_benefit':int(delta.min()),'maximum_delta_benefit':int(delta.max())})
        if name!='whole-osm-way':
            assert [r['unit'] for r in units]==[r['unit'] for r in base_units]
            for j,(k,w) in enumerate(GRID):
                for md,mode in enumerate(MODES):
                    append_comparison(name,'single','loss',mode,k,w,bs[:,j,md],single[:,j,md])
                    for metric,old,new in [('joint_loss',bl,loss),('interaction',bc,c)]:
                        a=old[bg[idx[0]],bg[idx[1]],j,md];b=new[ug[idx[0]],ug[idx[1]],j,md]
                        append_comparison(name,'pair',metric,mode,k,w,a,b)
        else:
            byway=collections.defaultdict(list)
            for i,r in enumerate(base_units):byway[r['unit'].split(':')[0]].append(i)
            for j,(k,w) in enumerate(GRID):
                for md,mode in enumerate(MODES):
                    ref=np.array([max(bs[i,j,md] for i in byway[r['unit']]) for r in units])
                    append_comparison(name,'source-way','loss_vs_max_child_segment',mode,k,w,ref,single[:,j,md])
        lengths=np.array([float(r['length_m']) for r in units])
        for lower,upper in zip(length_edges,length_edges[1:]):
            mask=(lengths>=lower)&(lengths<upper)
            for j,(k,w) in enumerate(GRID):
                for md,mode in enumerate(MODES):
                    v=single[mask,j,md]
                    strata.append({'variant':name,'min_length_m':lower,'max_length_m':upper if math.isfinite(upper) else None,
                        'mode':mode,'max_line_changes':k,'walking_budget_m':w,'units':len(v),
                        'positive_loss_units':int(np.count_nonzero(v)),'median_loss':float(np.median(v)) if len(v) else None,
                        'p95_loss':float(np.percentile(v,95)) if len(v) else None,'maximum_loss':int(v.max()) if len(v) else None})
        print('Audited all rows and rankings',name,flush=True)
    def write(name,rows):write_gzip_csv(OUT/name,list(rows[0]),[[r[k] for k in rows[0]] for r in rows])
    write('ranking-stability.csv.gz',rank_rows);write('length-strata.csv.gz',strata);write('metro-loss-comparisons.csv.gz',metro_rows)
    report={'status':'passed','variants_checked':len(names),'comparisons':len(rank_rows),'coverage':coverage,
        'total_physical_pairs_over_variants':sum(r['pairs'] for r in coverage),'ranking':'Exact Spearman with average tied ranks, no sampling; constant vectors have undefined (null) correlation.',
        'top_sets':'Both full-domain and positive-subset fractions, including all cutoff ties; zero values excluded. Empty-union Jaccard is undefined. Nonzero-union ranks/sign agreement are also retained to expose zero-heavy agreement.',
        'length_control':'Full physical source-unit lengths; strata describe sensitivity and are not equal-length-budget failure experiments.',
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'artifact_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT/'ranking-stability.csv.gz',OUT/'length-strata.csv.gz',OUT/'metro-loss-comparisons.csv.gz']}}
    (OUT/'sensitivity-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait-for-complete',action='store_true')
    run(parser.parse_args().wait_for_complete)
