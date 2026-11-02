"""Exact source-unit comparisons and physical-pair spatial associations."""
import argparse
import collections
import csv
import gzip
import json
from pathlib import Path

import numpy as np

from .accessibility import ROOT
from .audit_sensitivity import compare,correlation
from .pair_closures import write_gzip_csv
from .sensitivity_runs import read_gzip
from .structural_centrality import OUT,MODEL,sha

GRID=[(k,w) for k in [0,1,2] for w in [500,1000,2000]]
MODES=['bus','bus_metro']


def inputs():
    features=read_gzip(OUT/'street-features.csv.gz');assert len(features)==1684
    groups=json.loads((ROOT/'research/reports/m3-single-closures-2026-11-01/groups.json').read_text())
    signature_index={r['signature']:i for i,r in enumerate(groups)}
    unit_group={s:i for i,g in enumerate(groups) for s in g['streets']}
    gid=np.array([unit_group[r['unit']] for r in features])
    with (ROOT/'research/reports/m3-single-closures-2026-11-01/effects.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    losses=np.zeros((len(groups),9,2),np.int32)
    for r in rows:
        j=GRID.index((int(r['max_line_changes']),int(r['walking_budget_m'])))
        for md,mode in enumerate(MODES):losses[signature_index[r['signature']],j,md]=int(r[mode+'_loss_buildings'])
    return features,groups,signature_index,gid,losses


def pairs():
    features,groups,signature_index,gid,losses=inputs();pairs_dir=ROOT/'research/reports/m4-pairs-exhaustive-2026-11-01'
    registry=read_gzip(pairs_dir/'street-index.csv.gz')
    # The new feature domain is the same exact set, independent of source order.
    fields=registry[0].keys();street_field=next(k for k in fields if any(str(r[k]).startswith('w') and ':n' in str(r[k]) for r in registry[:1]))
    assert {r[street_field] for r in registry}=={r['unit'] for r in features}
    first,second=np.triu_indices(len(features),1);assert len(first)==1417086
    xy=np.array([[float(r['x_m']),float(r['y_m'])] for r in features]);distance=np.linalg.norm(xy[first]-xy[second],axis=1)
    route_sets=[json.loads(r['route_ids_json']) for r in features];routes=sorted({k for row in route_sets for k in row},key=int)
    bits=np.array([sum(1<<routes.index(k) for k in row) for row in route_sets],np.uint16)
    shared=np.bitwise_count(bits[first]&bits[second]);assert shared.max()<=2
    union_index=np.full((len(groups),len(groups)),-1,np.int32)
    for r in read_gzip(pairs_dir/'signature-pairs.csv.gz'):
        a,b=signature_index[r['first_signature']],signature_index[r['second_signature']]
        union_index[a,b]=union_index[b,a]=int(r['union_id'])
    uid=union_index[gid[first],gid[second]];assert (uid>=0).all()
    baseline=json.loads((ROOT/'research/reports/m3-2026-11-01-summary.json').read_text())
    intact={(r['mode'],r['max_line_changes'],r['walking_budget_m']):r['accessible_buildings'] for r in baseline['results']}
    joint=np.zeros((int(uid.max())+1,9,2),np.int32)
    with gzip.open(pairs_dir/'union-effects.csv.gz','rt',newline='') as f:
        for r in csv.DictReader(f):
            k,w=int(r['max_line_changes']),int(r['walking_budget_m']);j=GRID.index((k,w))
            for md,mode in enumerate(MODES):joint[int(r['union_id']),j,md]=intact[mode,k,w]-int(r[mode+'_accessible'])
    bins=np.array([0,250,500,1000,2000,5000,10000,20000,np.inf]);distance_bin=np.searchsorted(bins,distance,side='right')-1
    associations=[];strata=[]
    for j,(k,w) in enumerate(GRID):
        for md,mode in enumerate(MODES):
            loss=joint[uid,j,md];interaction=loss-losses[gid[first],j,md]-losses[gid[second],j,md]
            for label,values in [('joint_loss',loss),('interaction',interaction)]:
                for name,proxy in [('midpoint_distance_m',distance),('shared_bus_relations',shared)]:
                    nonzero=values!=0
                    associations.append((mode,k,w,label,name,len(values),correlation(proxy,values),int(nonzero.sum()),correlation(proxy[nonzero],values[nonzero]) if nonzero.any() else None))
            for i in range(len(bins)-1):
                for count in [0,1,2]:
                    selected=(distance_bin==i)&(shared==count);v=interaction[selected];l=loss[selected]
                    strata.append((mode,k,w,bins[i],bins[i+1] if np.isfinite(bins[i+1]) else None,count,int(selected.sum()),int((v>0).sum()),int((v==0).sum()),int((v<0).sum()),float(v.mean()) if len(v) else None,float(l.mean()) if len(l) else None))
            assert sum(r[6] for r in strata if r[:3]==(mode,k,w))==1417086
            print('All physical-pair feature associations',mode,k,w,flush=True)
    write_gzip_csv(OUT/'pair-feature-associations.csv.gz',['mode','max_line_changes','walking_budget_m','outcome','feature','all_pairs','spearman_all','nonzero_outcome_pairs','spearman_nonzero_outcome'],associations)
    write_gzip_csv(OUT/'pair-feature-strata.csv.gz',['mode','max_line_changes','walking_budget_m','distance_min_m','distance_max_m','shared_bus_relations','pairs','positive_C','zero_C','negative_C','mean_C','mean_joint_loss'],strata)
    report={'status':'passed','all_physical_pairs':1417086,'mode_parameter_comparisons':18,'association_rows':len(associations),'strata_rows':len(strata),
        'distance':'EPSG:32639 Euclidean distance between full source-segment midpoints; not network/travel distance.',
        'scope':'All pairs; exact tied ranks. Nonzero-outcome correlations condition on the outcome and are descriptive, not unbiased predictive validation. No p-values or independent-pair assumptions.',
        'source_code_sha256':sha(Path(__file__)),'artifact_sha256':{name:sha(OUT/name) for name in ['pair-feature-associations.csv.gz','pair-feature-strata.csv.gz']}}
    (OUT/'pair-feature-summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')


def singles():
    features,groups,signature_index,gid,losses=inputs()
    summary=json.loads((OUT/'centrality-summary.json').read_text());assert summary['status']=='passed'
    centrality=read_gzip(OUT/'junction-centrality.csv.gz');values=np.array([float(r['edge_betweenness_raw']) for r in centrality]);g=np.load(MODEL/'graph.npz')
    source_key={(int(wid),int(a),int(b)):i for i,(wid,a,b) in enumerate(zip(g['source_way'],g['source_u'],g['source_v']))}
    chain_of=g['chain_of'];source_edge=g['source_edge'];joined=[]
    for r in features:
        index=source_key[int(r['way_id']),int(r['first_node']),int(r['second_node'])];edge=int(source_edge[index])
        chain=int(chain_of[edge]) if edge>=0 else -1
        joined.append({**r,'chain_id':chain,'junction_edge_betweenness':float(values[chain]) if chain>=0 else None})
    fields=list(joined[0]);write_gzip_csv(OUT/'street-structural-comparators.csv.gz',fields,[[r[k] for k in fields] for r in joined])
    benchmarks=['dependent_bus_relations','dependent_connections','length_m','junction_edge_betweenness'];rows=[];classes=[];strata=[]
    lengths=np.array([float(r['length_m']) for r in joined]);bins=[0,25,50,100,250,500,1000,np.inf]
    for j,(k,w) in enumerate(GRID):
        for md,mode in enumerate(MODES):
            outcome=losses[gid,j,md]
            for name in benchmarks:
                proxy=np.array([float(r[name]) if r[name] is not None else np.nan for r in joined]);valid=np.isfinite(proxy);positive=(outcome>0)&valid
                result={'mode':mode,'max_line_changes':k,'walking_budget_m':w,'benchmark':name,'all_streets':1684,'eligible_streets':int(valid.sum()),
                    **compare(outcome[valid],proxy[valid]),'positive_loss_streets':int(positive.sum()),'spearman_positive_loss':correlation(outcome[positive],proxy[positive]) if positive.any() else None}
                rows.append(result)
                for lo,hi in zip(bins,bins[1:]):
                    mask=valid&(lengths>=lo)&(lengths<hi)
                    strata.append((mode,k,w,name,lo,hi if np.isfinite(hi) else None,int(mask.sum()),correlation(outcome[mask],proxy[mask]) if mask.any() else None))
            for highway in sorted({r['highway'] for r in joined}):
                mask=np.array([r['highway']==highway for r in joined]);v=outcome[mask]
                classes.append((mode,k,w,highway,int(mask.sum()),int((v>0).sum()),float(v.mean()),float(np.median(v)),int(v.max()),float(np.median(lengths[mask]))))
    write_gzip_csv(OUT/'single-benchmark-rank-comparisons.csv.gz',list(rows[0]),[[r[k] for k in rows[0]] for r in rows])
    write_gzip_csv(OUT/'single-benchmark-length-strata.csv.gz',['mode','max_line_changes','walking_budget_m','benchmark','min_length_m','max_length_m','streets','spearman'],strata)
    write_gzip_csv(OUT/'single-loss-by-road-class.csv.gz',['mode','max_line_changes','walking_budget_m','highway','streets','positive_loss_streets','mean_loss','median_loss','maximum_loss','median_source_length_m'],classes)
    report={'status':'passed','all_streets':1684,'centrality_available':sum(r['chain_id']>=0 for r in joined),'rank_comparison_rows':len(rows),'length_strata_rows':len(strata),'class_rows':len(classes),
        'centrality_definition':'Exact uniform-junction OD, undirected mapped highway/path context; not traffic or legal driving.',
        'road_class':'Nominal categories; no invented numeric hierarchy score. Correlations and cutoff-tie positive top sets are descriptive. Each original source unit retains its own weight, even where geometry maps to the same centrality chain.',
        'source_code_sha256':sha(Path(__file__)),'artifact_sha256':{name:sha(OUT/name) for name in ['street-structural-comparators.csv.gz','single-benchmark-rank-comparisons.csv.gz','single-benchmark-length-strata.csv.gz','single-loss-by-road-class.csv.gz']}}
    (OUT/'single-benchmark-summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--pairs',action='store_true');parser.add_argument('--singles',action='store_true');a=parser.parse_args()
    if a.pairs:pairs()
    if a.singles:singles()
