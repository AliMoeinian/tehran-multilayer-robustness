"""Reconcile saved single-closure artifacts against their source dependencies."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import sqlite3

from .accessibility import ROOT


def audit(directory,network):
    summary=json.loads((directory/'summary.json').read_text())
    with network.open('rb') as stream:
        assert hashlib.file_digest(stream,'sha256').hexdigest()==summary['network_sha256']
    for name,digest in summary['artifact_sha256'].items():
        assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==digest,(name,'hash')
    def rows(name):
        with (directory/name).open(newline='') as stream:return list(csv.DictReader(stream))
    streets=rows('streets.csv');effects=rows('effects.csv')
    groups=json.loads((directory/'groups.json').read_text())
    db=sqlite3.connect(network.resolve().as_uri()+'?mode=ro',uri=True)
    source=collections.defaultdict(set)
    for street,key in db.execute('select street_segment,connection_id from bus_dependencies'):
        source[street].add(key)
    db.close()
    assert len(streets)==len(source)==summary['observed_streets']
    assert len({r['street'] for r in streets})==len(streets)
    assert {r['street'] for r in streets}==set(source)
    signatures={g['signature']:g for g in groups}
    assert len(signatures)==len(groups)==summary['distinct_dependency_signatures']
    memberships=collections.defaultdict(set)
    for row in streets:
        group=signatures[row['signature']];street=row['street']
        assert source[street]==set(group['failed_connections'])
        assert int(row['failed_connection_count'])==len(source[street])
        memberships[row['signature']].add(street)
    for signature,group in signatures.items():
        assert memberships[signature]==set(group['streets'])
        assert len(group['streets'])==len(set(group['streets']))
        encoded=json.dumps(tuple(sorted(group['failed_connections'])),separators=(',',':')).encode()
        assert hashlib.sha256(encoded).hexdigest()==signature
    baseline=json.loads((ROOT/'research/reports/m3-2026-11-01-summary.json').read_text())
    base={(r['mode'],r['max_line_changes'],r['walking_budget_m']):r['accessible_buildings']
          for r in baseline['results'] if r['mode']!='walk'}
    config=json.loads((ROOT/'research/config/baseline.json').read_text())
    expected={(s,k,w) for s in signatures for k in config['max_line_changes'] for w in config['walking_budgets_m']}
    observed=set()
    for row in effects:
        signature=row['signature'];k=int(row['max_line_changes']);w=int(row['walking_budget_m'])
        key=(signature,k,w);assert key not in observed;observed.add(key)
        assert int(row['street_count'])==len(memberships[signature])
        for mode in ['bus','bus_metro']:
            accessible=int(row[mode+'_accessible']);loss=int(row[mode+'_loss_buildings'])
            assert accessible+loss==base[mode,k,w] and loss>=0
            assert abs(float(row[mode+'_loss_share_all'])-loss/summary['all_buildings'])<1e-12
        assert int(row['bus_metro_accessible'])>=int(row['bus_accessible'])
        assert int(row['delta_metro_benefit_buildings'])==int(row['bus_loss_buildings'])-int(row['bus_metro_loss_buildings'])
    assert observed==expected
    for result in summary['results']:
        selected=[r for r in effects if int(r['max_line_changes'])==result['max_line_changes']
                  and int(r['walking_budget_m'])==result['walking_budget_m']]
        for mode in ['bus','bus_metro']:
            loss=mode+'_loss_buildings';stored=result[mode]
            assert stored['maximum_loss_buildings']==max(int(r[loss]) for r in selected)
            assert stored['streets_with_positive_loss']==sum(int(r['street_count']) for r in selected if int(r[loss])>0)
            mean=sum(int(r['street_count'])*int(r[loss]) for r in selected)/len(streets)
            assert abs(mean-stored['mean_loss_buildings_over_observed_streets'])<1e-12
        assert result['streets_with_negative_delta_metro_benefit']==sum(int(r['street_count']) for r in selected if int(r['delta_metro_benefit_buildings'])<0)
    print(json.dumps({'status':'passed','streets':len(streets),'signatures':len(groups),'effect_rows':len(effects)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=ROOT/'research/reports/m3-single-closures-2026-11-01')
    parser.add_argument('--network',type=Path,default=ROOT/'research/model/m2-v2/network.sqlite')
    args=parser.parse_args();audit(args.directory,args.network)
