"""Summarize frozen results for manuscript claims; no experiments or new data.

Run from any directory. --check verifies the published JSON without rewriting it.
All pair statistics retain physical multiplicity, including identical signatures.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REPORTS = ROOT / 'research/reports'


def build():
    sources = {}

    def record(path):
        sources[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return path

    def read(path):
        return json.loads(record(path).read_text(encoding='utf-8'))

    def rows(path):
        record(path)
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', newline='', encoding='utf-8') as stream:
            yield from csv.DictReader(stream)

    totals = collections.defaultdict(collections.Counter)
    by_signature = collections.defaultdict(collections.Counter)
    mechanism_rows = 0
    for row in rows(REPORTS / 'sensitivity-2026-11-01/all-pair-mechanisms.csv.gz'):
        mode, k, w = row['mode'], int(row['max_line_changes']), int(row['walking_budget_m'])
        s, n, c = (int(row[field]) for field in ['shared_single_losses', 'new_joint_only_losses', 'interaction'])
        first, second, joint = (int(row[field]) for field in ['first_loss', 'second_loss', 'joint_loss'])
        count = int(row['street_pair_count'])
        assert n >= 0 and s >= 0 and c == n-s == joint-first-second and count > 0
        same = row['first_group'] == row['second_group']
        if same:
            assert n == 0 and first == second == joint == s and c == -joint
        category = 'both' if n and s else 'new_only' if n else 'shared_only' if s else 'neither'
        values = {'pairs':count, category:count, 'positive_C':count*int(c>0),
                  'negative_C':count*int(c<0), 'zero_C':count*int(c==0),
                  'balanced_nonzero':count*int(n==s and n>0),
                  'pairs_with_joint_only_losses':count*int(n>0)}
        totals[mode,k,w].update(values)
        by_signature[mode,k,w,'same_signature' if same else 'different_signatures'].update(values)
        mechanism_rows += 1
    assert mechanism_rows == 510066 and len(totals) == 18
    mechanism = []
    strata = []
    for (mode,k,w), counts in sorted(totals.items()):
        for category in ['both','new_only','shared_only','neither']:
            counts.setdefault(category, 0)
        assert counts['pairs'] == 1417086
        assert sum(counts[c] for c in ['both','new_only','shared_only','neither']) == counts['pairs']
        assert counts['positive_C']+counts['negative_C']+counts['zero_C'] == counts['pairs']
        assert counts['zero_C'] == counts['neither'] + counts['balanced_nonzero']
        mechanism.append({'mode':mode,'max_line_changes':k,'walking_budget_m':w,**dict(counts)})
        for label, expected in [('same_signature',16289),('different_signatures',1400797)]:
            values = by_signature[mode,k,w,label]
            assert values['pairs'] == expected
            strata.append({'mode':mode,'max_line_changes':k,'walking_budget_m':w,'stratum':label,
                           **{field:values[field] for field in ['pairs','positive_C','negative_C','zero_C',
                                      'balanced_nonzero','pairs_with_joint_only_losses']}})
    pair = read(REPORTS / 'm4-pairs-exhaustive-2026-11-01/summary.json')
    for row in pair['results']:
        for mode in ['bus','bus_metro']:
            a=totals[mode,row['max_line_changes'],row['walking_budget_m']]
            b=row[mode]
            assert a['positive_C']==b['positive_pairs'] and a['negative_C']==b['negative_pairs'] and a['zero_C']==b['zero_pairs']
    selected_variants = []
    for name in ['baseline','connector-25m','connector-50m','connector-250m','failure-whole-route',
                 'targets-emergency-tag','targets-human-inside','routes-semantic-extension','routes-derived-order']:
        folder=REPORTS/'sensitivity-2026-11-01/variants'/name
        summary=read(folder/'summary.json');assert summary['status']=='passed' and summary['unit_count']==1684
        settings=[]
        negative=collections.Counter()
        for r in rows(folder/'single-effects.csv.gz'):
            if int(r['bus_metro_loss']) > int(r['bus_loss']):
                negative[int(r['max_line_changes']),int(r['walking_budget_m'])] += int(r['unit_count'])
        for r in summary['results']:
            settings.append({**r,'units_with_higher_absolute_loss_with_metro':negative[r['max_line_changes'],r['walking_budget_m']]})
        selected_variants.append({'variant':name,'settings':settings})
    structural=REPORTS/'structural-2026-11-02'
    rank_rows=list(rows(structural/'single-benchmark-rank-comparisons.csv.gz'))
    ranks=[]
    for row in rank_rows:
        ranks.append({field:(row[field] if field in ['mode','benchmark'] else None if row[field]==''
                              else float(row[field]) if field in ['spearman','positive_top_5pct_jaccard'] else int(row[field]))
                      for field in ['mode','benchmark','max_line_changes','walking_budget_m','eligible_streets','spearman',
                                    'positive_top_5pct_jaccard','positive_top_5pct_reference_count','positive_top_5pct_variant_count']})
    target_counts={key:collections.Counter() for key in ['walk','bus','bus_metro']}
    origins=0
    for row in rows(structural/'building-reachable-target-groups.csv.gz'):
        origins+=1
        for label,field in [('walk','bus_b0_w1000'),('bus','bus_b2_w1000'),('bus_metro','bus_metro_b2_w1000')]:
            value=int(row[field]);t=target_counts[label]
            t['zero']+=int(value==0);t['one']+=int(value==1);t['at_least_two']+=int(value>=2)
    assert origins==65677
    for counts in target_counts.values():assert counts['zero']+counts['one']+counts['at_least_two']==origins
    route=read(structural/'route-structure-summary.json');description=read(structural/'descriptive-summary.json')
    primary=next(r for r in selected_variants[0]['settings'] if r['max_line_changes']==1 and r['walking_budget_m']==1000)
    assert primary['units_with_higher_absolute_loss_with_metro']==98
    derived=next(r for r in selected_variants[-1]['settings'] if r['max_line_changes']==1 and r['walking_budget_m']==1000)
    assert derived['units_with_higher_absolute_loss_with_metro']==0
    return {'status':'passed','evidence_version':'paper-claims-v1','selection_date':'2026-11-03',
            'scope':'Retrospective manuscript evidence selection from frozen published results; no new network simulation or external analytical records.',
            'reference_setting':{'walking_budget_m':1000,'max_line_changes':1,'all_original_buildings':origins},
            'observed_relations':{'bus':route['bus_relations'],'rail':route['rail_relations']},
            'connected_candidate_groups':description['candidate_groups_checked'],
            'mechanism_signature_rows_reconciled':mechanism_rows,'all_pair_mechanism_settings':mechanism,
            'signature_identity_strata':strata,'selected_variant_full_grids':selected_variants,
            'all_primary_proxy_comparisons':ranks,'reference_target_group_counts':{k:dict(v) for k,v in target_counts.items()},
            'input_sha256':dict(sorted(sources.items())),
            'builder_source_lf_sha256':hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    result=build();text=json.dumps(result,indent=2,sort_keys=True)+'\n';target=HERE/'claim-evidence.json'
    if args.check:
        assert target.read_bytes()==text.encode('utf-8'),'Claim evidence differs: inspect source or generator changes.'
    else:target.write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps({'status':'passed','all_signature_pair_rows':result['mechanism_signature_rows_reconciled'],
                      'all_pair_settings':len(result['all_pair_mechanism_settings']),
                      'signature_strata':len(result['signature_identity_strata']),'proxy_rows':len(result['all_primary_proxy_comparisons'])}))


if __name__=='__main__':main()
