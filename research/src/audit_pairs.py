"""Independently reconcile saved pair samples, unions, and interaction summaries."""
import argparse
import collections
import csv
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import random

from .accessibility import ROOT


def audit(directory):
    def data(name):return json.loads((directory/name).read_text())
    def rows(name):
        with gzip.open(directory/name,'rt',newline='') as stream:return list(csv.DictReader(stream))
    summary=data('summary.json');selection=data('selection.json');protocol=data('protocol.json')
    for name,digest in summary['artifact_sha256'].items():
        assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==digest,name
    assert hashlib.sha256((directory/'protocol.json').read_bytes()).hexdigest()==summary['protocol_sha256']
    source=ROOT/'research/reports/m3-single-closures-2026-11-01'
    groups=json.loads((source/'groups.json').read_text());by_signature={g['signature']:g for g in groups}
    baseline=json.loads((ROOT/'research/reports/m3-2026-11-01-summary.json').read_text())
    for field in ['network_sha256','config_sha256']:assert summary[field]==baseline[field]
    with (source/'effects.csv').open(newline='') as stream:singles=list(csv.DictReader(stream))
    single={(r['signature'],int(r['max_line_changes']),int(r['walking_budget_m'])):r for r in singles}
    base={(r['mode'],r['max_line_changes'],r['walking_budget_m']):r['accessible_buildings'] for r in baseline['results']}
    domain_pairs=[];domain_unions=set();domain_size=0
    for i,a in enumerate(groups):
        for j in range(i,len(groups)):
            b=groups[j];n=math.comb(len(a['streets']),2) if i==j else len(a['streets'])*len(b['streets'])
            if n:
                union=tuple(sorted(set(a['failed_connections']).union(b['failed_connections'])))
                domain_pairs.append((a,b,n,union,i==j));domain_unions.add(union);domain_size+=n
    assert domain_size==summary['domain']['street_pairs']==math.comb(summary['domain']['street_count'],2)
    ordered_unions=sorted(domain_unions)
    assert len(ordered_unions)==summary['domain']['union_count']
    sampled=collections.Counter();expected_physical={}
    if selection['exhaustive']:
        sampled.update({(a['signature'],b['signature']):n for a,b,n,u,same in domain_pairs})
    else:
        ranks=sorted(random.Random(protocol['fallback_seed']).sample(range(domain_size),protocol['fallback_uniform_street_pair_sample_size']))
        assert ranks==selection['sampled_street_pair_ranks']
        position=0;offset=0
        for a,b,n,u,same in domain_pairs:
            selected=[]
            while position<len(ranks) and ranks[position]<offset+n:
                rank=ranks[position];selected.append(rank-offset)
                sampled[a['signature'],b['signature']]+=1;position+=1
            if selected:
                # Independent reference enumerates the block's Cartesian product
                # or combinations rather than using the runner's unranking helper.
                block=itertools.combinations(a['streets'],2) if same else itertools.product(a['streets'],b['streets'])
                wanted=set(selected)
                for local,pair in enumerate(block):
                    if local in wanted:expected_physical[offset+local]=tuple(pair)
                    if local>=max(wanted):break
            offset+=n
        physical=rows('sampled-street-pairs.csv.gz')
        observed={int(r['pair_rank']):(r['first_street'],r['second_street']) for r in physical}
        assert len(observed)==len(physical)==len(ranks)
        assert observed==expected_physical
        assert len({tuple(sorted(pair)) for pair in observed.values()})==len(ranks)
        assert all(a!=b for a,b in observed.values())
    pairs=rows('signature-pairs.csv.gz');unions=rows('unions.csv.gz');effects=rows('union-effects.csv.gz')
    assert {(r['first_signature'],r['second_signature']):int(r['street_pair_count']) for r in pairs}==dict(sampled)
    assert len(pairs)==len(sampled)
    union_map={int(r['union_id']):tuple(json.loads(r['failed_connections_json'])) for r in unions}
    assert len(union_map)==len(unions)==selection['evaluated_pair_unions']
    for uid,union in union_map.items():assert ordered_unions[uid]==union
    assert {int(r['union_id']) for r in pairs}==set(union_map)
    for r in pairs:
        a=by_signature[r['first_signature']];b=by_signature[r['second_signature']]
        assert union_map[int(r['union_id'])]==tuple(sorted(set(a['failed_connections'])|set(b['failed_connections'])))
    parameters={(r['max_line_changes'],r['walking_budget_m']) for r in summary['results']}
    lookup={(int(r['union_id']),int(r['max_line_changes']),int(r['walking_budget_m'])):r for r in effects}
    assert len(lookup)==len(effects)==len(union_map)*len(parameters)
    assert set(lookup)=={(uid,k,w) for uid in union_map for k,w in parameters}
    histograms=[]
    for result in summary['results']:
        k=result['max_line_changes'];w=result['walking_budget_m']
        for mode in ['bus','bus_metro']:
            hist=collections.Counter();joint_max=0
            for row in pairs:
                effect=lookup[int(row['union_id']),k,w];n=int(row['street_pair_count'])
                assert int(effect['bus_metro_accessible'])>=int(effect['bus_accessible'])
                joint=base[mode,k,w]-int(effect[mode+'_accessible'])
                first=int(single[row['first_signature'],k,w][mode+'_loss_buildings'])
                second=int(single[row['second_signature'],k,w][mode+'_loss_buildings'])
                assert joint>=max(first,second)
                hist[joint-first-second]+=n;joint_max=max(joint_max,joint)
            assert sum(hist.values())==summary['evaluated_street_pairs']
            stored=result[mode]
            assert stored['negative_pairs']==sum(n for c,n in hist.items() if c<0)
            assert stored['zero_pairs']==hist[0]
            assert stored['positive_pairs']==sum(n for c,n in hist.items() if c>0)
            assert stored['minimum_interaction_buildings']==min(hist)
            assert stored['maximum_interaction_buildings']==max(hist)
            assert stored['maximum_joint_loss_buildings']==joint_max
            assert abs(stored['mean_interaction_buildings']-sum(c*n for c,n in hist.items())/sum(hist.values()))<1e-12
            histograms.append({'mode':mode,'max_line_changes':k,'walking_budget_m':w,'counts':{str(c):n for c,n in sorted(hist.items())}})
    assert histograms==data('interaction-distributions.json')
    for case in data('extreme-cases.json'):
        mode=case['mode'];k=case['max_line_changes'];w=case['walking_budget_m']
        a=case['first_signature'];b=case['second_signature'];uid=case['union_id']
        assert case['street_pair_count']==sampled[a,b]
        first=int(single[a,k,w][mode+'_loss_buildings']);second=int(single[b,k,w][mode+'_loss_buildings'])
        joint=base[mode,k,w]-int(lookup[uid,k,w][mode+'_accessible'])
        assert (first,second,joint,joint-first-second)==(case['first_loss_buildings'],case['second_loss_buildings'],case['joint_loss_buildings'],case['interaction_buildings'])
    report={'status':'passed','scope':'saved pair identities, seeded selection, dependency unions, all effect rows and interaction summaries',
            'sampled_street_pairs':summary['evaluated_street_pairs'],'signature_pairs':len(pairs),
            'union_scenarios':len(unions),'effect_rows':len(effects),'parameter_comparisons':len(parameters)*2}
    print(json.dumps(report));return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,default=ROOT/'research/reports/m4-pairs-2026-11-01')
    a=p.parse_args();audit(a.directory)
