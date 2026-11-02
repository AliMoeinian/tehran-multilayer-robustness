"""Exact origin-set mechanism decomposition for every primary pair and W/K."""
import collections
import csv
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from .accessibility import ROOT
from .pair_closures import write_gzip_csv


def run():
    out=ROOT/'research/reports/sensitivity-2026-11-01';source=ROOT/'research/reports/m4-pairs-exhaustive-2026-11-01'
    index=json.loads((out/'mask-index.json').read_text());masks=np.load(out/'single-loss-masks.npz')
    group_ids={r['signature']:r['group_index'] for r in index['groups']}
    def rows(name):
        with gzip.open(source/name,'rt',newline='') as f:return list(csv.DictReader(f))
    pairs=rows('signature-pairs.csv.gz');effects=rows('union-effects.csv.gz')
    values={(int(r['union_id']),int(r['max_line_changes']),int(r['walking_budget_m'])):r for r in effects}
    summary=json.loads((source/'summary.json').read_text());counts={(r['max_line_changes'],r['walking_budget_m'],mode):r[mode] for r in summary['results'] for mode in ['bus','bus_metro']}
    modes=['bus','bus_metro'];grid=[(k,w) for k in [0,1,2] for w in [500,1000,2000]]
    lost={(i,mode,k,w):int(np.bitwise_count(masks[f'g{i}_{mode}_k{k}_w{w}']).sum()) for i in group_ids.values() for mode in modes for k,w in grid}
    stats={};selected={};table_rows=0
    def generate():
        nonlocal table_rows
        for mode in modes:
            for k,w in grid:
                stats[mode,k,w]=collections.Counter()
                min_c=counts[k,w,mode]['minimum_interaction_buildings'];max_c=counts[k,w,mode]['maximum_interaction_buildings']
                for pair in pairs:
                    a=group_ids[pair['first_signature']];b=group_ids[pair['second_signature']]
                    n=int(pair['street_pair_count']);uid=int(pair['union_id'])
                    overlap=int(np.bitwise_count(masks[f'g{a}_{mode}_k{k}_w{w}']&masks[f'g{b}_{mode}_k{k}_w{w}']).sum())
                    joint=counts[k,w,mode]['baseline_accessible']-int(values[uid,k,w][mode+'_accessible']) if 'baseline_accessible' in counts[k,w,mode] else None
                    # The pair summary does not repeat baseline counts.
                    if joint is None:
                        baseline=json.loads((ROOT/'research/reports/m3-2026-11-01-summary.json').read_text())
                        total=next(r['accessible_buildings'] for r in baseline['results'] if r['mode']==mode and r['max_line_changes']==k and r['walking_budget_m']==w)
                        counts[k,w,mode]['baseline_accessible']=total;joint=total-int(values[uid,k,w][mode+'_accessible'])
                    first,second=lost[a,mode,k,w],lost[b,mode,k,w]
                    new=joint-first-second+overlap;interaction=joint-first-second
                    assert overlap>=0 and new>=0 and interaction==new-overlap
                    label='both' if new and overlap else 'joint_only' if new else 'shared_only' if overlap else 'neither'
                    stats[mode,k,w][label]+=n
                    if k==1 and w==1000 and interaction in [min_c,max_c]:
                        identity=(a,b)
                        selected.setdefault(identity,{'first_group':a,'second_group':b,'union_id':uid,'street_pair_count':n,'selection_reasons':[]})['selection_reasons'].append({'mode':mode,'kind':'maximum' if interaction==max_c else 'minimum','interaction':interaction})
                    table_rows+=1
                    yield a,b,uid,mode,k,w,n,first,second,joint,overlap,new,interaction
    write_gzip_csv(out/'all-pair-mechanisms.csv.gz',['first_group','second_group','union_id','mode','max_line_changes','walking_budget_m','street_pair_count','first_loss','second_loss','joint_loss','shared_single_losses','new_joint_only_losses','interaction'],generate())
    single=list(csv.DictReader((ROOT/'research/reports/m3-single-closures-2026-11-01/effects.csv').open()))
    negative=[{'group_index':group_ids[r['signature']],'signature':r['signature'],'street_count':int(r['street_count'])} for r in single if r['max_line_changes']=='1' and r['walking_budget_m']=='1000' and int(r['delta_metro_benefit_buildings'])<0]
    expected=28337*18;assert table_rows==expected
    for s in stats.values():assert sum(s.values())==1417086
    cases={'rule':'all tied extrema at W=1000,K=1 in either mode; all negative-DeltaM single signatures; no sampled origins',
           'pairs':list(selected.values()),'negative_delta_singles':negative}
    (out/'path-case-registry.json').write_text(json.dumps(cases,indent=2)+'\n',encoding='utf-8',newline='\n')
    report={'status':'passed','signature_pair_mode_parameter_rows':table_rows,'physical_pairs_per_comparison':1417086,
        'identity':'C = new joint-only losses - shared single losses','all_new_loss_counts_nonnegative':True,
        'results':[{'mode':mode,'max_line_changes':k,'walking_budget_m':w,**dict(stats[mode,k,w])} for mode in modes for k,w in grid],
        'path_pair_cases':len(selected),'negative_delta_single_cases':len(negative),
        'table_sha256':hashlib.sha256((out/'all-pair-mechanisms.csv.gz').read_bytes()).hexdigest()}
    (out/'mechanism-summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'rows':table_rows,'path_pairs':len(selected),'negative_delta_singles':len(negative)}));return report


if __name__=='__main__':run()
