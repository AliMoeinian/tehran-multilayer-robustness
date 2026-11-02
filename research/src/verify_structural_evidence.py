"""Check complete public structural evidence without rerunning long Brandes.

Frozen receipts certify the original execution, not a new independent full
centrality computation. Public graph arithmetic, task coverage, bridge scores,
target masks and district totals are checked again on every verification.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import spearmanr

from .accessibility import ROOT

OUT = ROOT / 'research/reports/structural-2026-11-02'
FIG = ROOT / 'research/figures/structural-2026-11-02'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
lfsha = lambda p: hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def read(name):
    return json.loads((OUT / name).read_text())


def rows(name):
    if name == 'source-chain-mapping.csv.gz':
        for part in read('source-chain-index.json')['parts']:
            yield from rows(part['file'])
        return
    with gzip.open(OUT / name, 'rt', newline='', encoding='utf-8') as f:
        yield from csv.DictReader(f)


def freeze():
    for name in ['centrality-summary.json', 'centrality-audit.json', 'geometry-audit.json',
                 'descriptive-audit.json', 'route-structure-audit.json', 'single-benchmark-summary.json', 'pair-feature-summary.json']:
        assert read(name)['status'] == 'passed', name
    assert read('centrality-summary.json')['all_tasks_completed']
    sources = list((ROOT / 'research/src').glob('*.py'))
    artifacts = [p for p in OUT.rglob('*') if p.is_file() and p.name not in ['execution.json', 'PAUSED.en.md']]
    artifacts += list(FIG.glob('*.svg')) + [FIG / 'manifest.json']
    artifacts += [OUT.parent/'structural-comparisons.en.md']
    config = ROOT / 'research/config/structural-protocol.json'
    evaluated = {'centrality-summary.json':'structural_blocks.py',
                 'centrality-audit.json':'audit_structural.py',
                 'geometry-audit.json':'audit_structural.py',
                 'descriptive-audit.json':'audit_structural.py',
                 'descriptive-summary.json':'network_descriptives.py',
                 'route-structure-summary.json':'route_structure.py',
                 'route-structure-audit.json':'audit_route_structure.py',
                 'single-benchmark-summary.json':'structural_comparisons.py',
                 'pair-feature-summary.json':'structural_comparisons.py',
                 'graph-export.json':'export_structural_graph.py'}
    for report, module in evaluated.items():
        assert read(report)['source_code_sha256'] == sha(ROOT/'research/src'/module), (report,module)
    execution = {'status': 'completed', 'protocol_sha256': sha(config),
                 'source_code_lf_sha256': {p.name: lfsha(p) for p in sources},
                 'evaluated_source_code_sha256': {p.name: sha(p) for p in sources},
                 'report_source_modules': evaluated,
                 'artifact_sha256': {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in artifacts},
                 'line_endings': 'Only source code uses canonical LF hashing. All result and configuration hashes are strict bytes.',
                 'replay_scope': 'Public graph identities, complete source census, bridge products, all target masks and district effects; no claim of independently recomputing all large-block shortest paths in CI.'}
    (OUT / 'execution.json').write_text(json.dumps(execution, indent=2) + '\n', encoding='utf-8', newline='\n')


def graph():
    inventory = read('graph-inventory.json')
    vertex_rows = list(rows('junction-vertices.csv.gz'))
    n = len(vertex_rows)
    assert n == inventory['junction_graph_vertices'] == 317852
    assert [int(r['junction']) for r in vertex_rows] == list(range(n))
    assert len({r['canonical_native_node'] for r in vertex_rows}) == n
    od = np.array([int(r['od_weight']) for r in vertex_rows], np.int64)
    labels = np.array([int(r['component']) for r in vertex_rows], np.int64)
    assert np.isin(od, [0, 1]).all() and od.sum() == 317724
    del vertex_rows
    edge_rows = list(rows('junction-centrality.csv.gz'))
    m = len(edge_rows)
    assert m == 412775 and [int(r['chain_id']) for r in edge_rows] == list(range(m))
    u = np.array([int(r['u']) for r in edge_rows]); v = np.array([int(r['v']) for r in edge_rows])
    length = np.array([float(r['length_m']) for r in edge_rows])
    bc = np.array([float(r['edge_betweenness_raw']) for r in edge_rows])
    assert np.isfinite(length).all() and (length > 0).all()
    assert np.isfinite(bc).all() and (bc >= 0).all()
    assert (u >= 0).all() and (u < n).all() and (v >= 0).all() and (v < n).all()
    del edge_rows
    matrix = csr_matrix((np.ones(2*m), (np.r_[u,v], np.r_[v,u])), shape=(n,n))
    components, actual = connected_components(matrix, directed=False)
    assert components == inventory['components'] == 595
    # Canonical membership comparison: label spelling itself is irrelevant.
    for group in np.unique(labels): assert len(np.unique(actual[labels == group])) == 1
    assert len(np.unique(labels)) == components
    total = np.bincount(labels, weights=od).astype(np.int64)
    assert (bc <= total[labels[u]] * (total[labels[u]] - 1) / 2 + 1e-3).all()
    assert (bc[u == v] == 0).all()
    links = {}; occurrences = 0
    for r in rows('source-chain-mapping.csv.gz'):
        assert int(r['occurrence']) == occurrences
        occurrences += 1
        key = int(r['physical_edge']); chain = int(r['chain']); distance = float(r['source_length_m'])
        assert key >= 0 and 0 <= chain < m and distance > 0  # Actual frozen graph has no zero links.
        value = (int(r['first_node']), int(r['second_node']), chain, distance)
        assert value[0] < value[1]
        old = links.setdefault(key, value)
        assert old[:3] == value[:3] and abs(old[3] - distance) < 1e-5
    assert occurrences == 968041 and len(links) == 968022 and set(links) == set(range(968022))
    distances = collections.defaultdict(list)
    for a,b,chain,distance in links.values(): distances[chain].append(distance)
    assert set(distances) == set(range(m))
    assert all(abs(math.fsum(ds) - length[c]) < 1e-6 for c,ds in distances.items())
    del links, distances
    attachment = list(rows('block-attachment-masses.csv.gz'))
    block = np.array([int(r['block']) for r in attachment]); node = np.array([int(r['junction']) for r in attachment])
    weight = np.array([int(r['projected_od_weight']) for r in attachment], np.int64)
    nb = int(block.max())+1
    assert nb == 100238 and (weight >= 0).all()
    assert len(set(zip(block, node))) == len(block)
    assert all(int(r['component_od_total']) == total[labels[int(r['junction'])]] for r in attachment)
    del attachment
    forest = csr_matrix((np.ones(2*len(block)), (np.r_[node,n+block], np.r_[n+block,node])), shape=(n+nb,n+nb))
    roots, tree_labels = connected_components(forest, directed=False)
    assert len(block) == n+nb-roots  # An undirected simple graph with this identity is a forest.
    block_totals = np.bincount(block, weights=weight, minlength=nb).astype(np.int64)
    assert np.array_equal(block_totals[block], total[labels[node]])
    away = np.bincount(node, weights=total[labels[node]]-weight, minlength=n).astype(np.int64)
    assert np.array_equal(away+od, total[labels])
    memberships = collections.defaultdict(set)
    masses = {}
    for b,j,w in zip(block,node,weight): memberships[int(j)].add(int(b)); masses[int(b),int(j)] = int(w)
    edge_count = np.zeros(nb,np.int64); edge_block = np.full(m,-1,np.int64)
    for i,(a,b) in enumerate(zip(u,v)):
        if a == b: continue
        shared = memberships[int(a)] & memberships[int(b)]
        assert len(shared) == 1
        group = shared.pop(); edge_block[i] = group; edge_count[group] += 1
    assert (edge_count > 0).all() and (edge_count == 1).sum() == 98808
    bridge_distance = 0.; bridges = {}
    for i,group in enumerate(edge_block):
        if group >= 0 and edge_count[group] == 1:
            a,b = masses[group,int(u[i])], masses[group,int(v[i])]
            assert bc[i] == a*b
            bridge_distance += a*b*length[i]; bridges[i] = (group,a,b,a*b)
    bridge_rows = list(rows('bridge-centrality-audit.csv.gz'))
    assert len(bridge_rows) == len(bridges)
    for r in bridge_rows:
        assert bridges[int(r['chain'])] == tuple(int(r[k]) for k in ['block','first_branch_od','second_branch_od','edge_betweenness'])
    expected = {(int(b),int(j)):int(w) for b,j,w in zip(block,node,weight) if edge_count[b]>1 and w>0}
    seen = set(); distance_sum = bridge_distance
    for r in rows('centrality-source-census.csv.gz'):
        key = int(r['block']),int(r['junction'])
        assert key not in seen and int(r['projected_od_weight']) == expected[key]
        distance = float(r['weighted_distance_sum_m']); assert math.isfinite(distance) and distance >= 0
        seen.add(key); distance_sum += distance/2
    assert seen == set(expected) and len(seen) == 219879
    lhs = float(np.dot(bc,length)); error = abs(lhs-distance_sum)/max(1,distance_sum)
    assert error < 1e-7
    summary = read('centrality-summary.json')
    assert summary['all_tasks_completed'] and summary['no_sampling']
    assert summary['original_od_junctions'] == int(od.sum()) and summary['projected_block_sources'] == len(seen)
    return {'vertices':n,'chains':m,'source_occurrences':occurrences,'projected_sources':len(seen),'bridge_products':len(bridges),'distance_conservation_error':error}


def descriptives():
    owner_rows = list(rows('building-district-ownership.csv.gz'))
    ids = [r['origin'] for r in owner_rows]; owner = np.array([int(r['district']) for r in owner_rows])
    assert len(ids) == len(set(ids)) == 65677 and (owner == 0).sum() == 24
    assert set(owner) == set(range(23))
    index = read('target-group-mask-index.json'); assert len(index['groups']) == 236
    assert hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest() == index['origin_id_order_sha256']
    counts = np.zeros((2,4,3,len(ids)),np.uint16)
    coverage = {(r['group'],r['mode'],int(r['max_boardings']),int(r['walking_budget_m'])):int(r['accessible_origins']) for r in rows('target-group-coverage.csv.gz')}
    mask_count = 0
    with np.load(OUT/'hospital-group-reachability-masks.npz') as masks:
        for gi,group in enumerate(index['groups']):
            for md,mode in enumerate(['bus','bus_metro']):
                for b in range(4):
                    for wi,w in enumerate([500,1000,2000]):
                        bits = np.unpackbits(masks[f'g{gi}_{mode}_b{b}_w{w}'],bitorder='little')
                        assert bits[len(ids):].sum() == 0
                        bits = bits[:len(ids)]; assert int(bits.sum()) == coverage[group,mode,b,w]
                        counts[md,b,wi] += bits; mask_count += 1
        assert len(masks.files) == mask_count == 5664
    for i,r in enumerate(rows('building-reachable-target-groups.csv.gz')):
        assert r['origin'] == ids[i]
        for md,mode in enumerate(['bus','bus_metro']):
            for b in range(4):
                for wi,w in enumerate([500,1000,2000]): assert int(r[f'{mode}_b{b}_w{w}']) == counts[md,b,wi,i]
    baseline = {(r['mode'],int(r['max_line_changes']),int(r['walking_budget_m'])):r['accessible_buildings'] for r in json.loads((ROOT/'research/reports/m3-2026-11-01-summary.json').read_text())['results'] if r['max_line_changes'] is not None}
    for r in rows('district-baseline.csv.gz'):
        d=int(r['district']); md=['bus','bus_metro'].index(r['mode']); b=int(r['max_line_changes'])+1;wi=[500,1000,2000].index(int(r['walking_budget_m']))
        selected=counts[md,b,wi,owner==d]
        assert len(selected)==int(r['buildings']) and np.count_nonzero(selected)==int(r['accessible_buildings'])
    for md,mode in enumerate(['bus','bus_metro']):
        for k in [0,1,2]:
            for wi,w in enumerate([500,1000,2000]): assert np.count_nonzero(counts[md,k+1,wi]) == baseline[mode,k,w]
    assert (counts[1]>=counts[0]).all() and (counts[:,1:]>=counts[:,:-1]).all() and (counts[:,:,1:]>=counts[:,:,:-1]).all()
    signatures=json.loads((ROOT/'research/reports/sensitivity-2026-11-01/mask-index.json').read_text())
    lookup={key:int(d) for key,d in zip(ids,owner)};old_owner=np.array([lookup[key] for key in signatures['origins']])
    group_index={r['signature']:r['group_index'] for r in signatures['groups']}
    effects=collections.defaultdict(list)
    for r in rows('district-single-losses.csv.gz'):effects[r['signature'],r['mode'],int(r['max_line_changes']),int(r['walking_budget_m'])].append(r)
    checked=0
    with np.load(ROOT/'research/reports/sensitivity-2026-11-01/single-loss-masks.npz') as masks:
        for (signature,mode,k,w),records in effects.items():
            assert len(records)==23 and {int(r['district']) for r in records}==set(range(23))
            bits=np.unpackbits(masks[f'g{group_index[signature]}_{mode}_k{k}_w{w}'],bitorder='little')[:len(old_owner)]
            expected=np.bincount(old_owner,weights=bits,minlength=23).astype(int)
            for r in records:assert int(r['lost_buildings'])==expected[int(r['district'])];checked+=1
    assert checked==98532
    return {'target_masks':mask_count,'district_effect_rows':checked,'origins':len(ids)}


def comparisons():
    from .structural_comparisons import inputs
    features,groups,signature_index,gid,losses=inputs()
    joined=list(rows('street-structural-comparators.csv.gz'))
    assert len(joined)==1684 and [r['unit'] for r in joined]==[r['unit'] for r in features]
    benchmarks=list(rows('single-benchmark-rank-comparisons.csv.gz'));assert len(benchmarks)==72
    grid=[(k,w) for k in [0,1,2] for w in [500,1000,2000]]
    for r in benchmarks:
        proxy=np.array([float(s[r['benchmark']]) if s[r['benchmark']] else np.nan for s in joined]);valid=np.isfinite(proxy)
        outcome=losses[gid,grid.index((int(r['max_line_changes']),int(r['walking_budget_m']))),['bus','bus_metro'].index(r['mode'])]
        assert valid.sum()==int(r['eligible_streets'])==1684
        expected=float(spearmanr(outcome[valid],proxy[valid]).statistic) if np.ptp(outcome[valid]) and np.ptp(proxy[valid]) else None
        assert (r['spearman']=='') if expected is None else abs(float(r['spearman'])-expected)<1e-12
        for percent in [1,5,10]:
            sets=[]
            for values in [outcome[valid],proxy[valid]]:
                ordered=sorted((float(x) for x in values if x>0),reverse=True)
                count=min(len(ordered),math.ceil(len(ordered)*percent/100))
                sets.append(set(np.flatnonzero(values>=ordered[count-1])) if count else set())
            a,b=sets;expected=len(a&b)/len(a|b) if a|b else None
            field=f'positive_top_{percent}pct_jaccard'
            assert (r[field]=='') if expected is None else abs(float(r[field])-expected)<1e-12
            assert int(r[f'positive_top_{percent}pct_reference_count'])==len(a) and int(r[f'positive_top_{percent}pct_variant_count'])==len(b)
    pairs=list(rows('pair-feature-associations.csv.gz'));assert len(pairs)==72 and all(int(r['all_pairs'])==1417086 for r in pairs)
    strata=collections.defaultdict(list)
    for r in rows('pair-feature-strata.csv.gz'):strata[r['mode'],r['max_line_changes'],r['walking_budget_m']].append(r)
    assert len(strata)==18
    for group in strata.values():
        assert len(group)==24 and sum(int(r['pairs']) for r in group)==1417086
        for r in group:assert int(r['positive_C'])+int(r['zero_C'])+int(r['negative_C'])==int(r['pairs'])
    route=list(rows('route-descriptions.csv.gz'));overlap=list(rows('route-pair-overlap.csv.gz'))
    assert len(route)==25 and sum(r['mode']=='bus' for r in route)==11 and len(overlap)==300
    ids={r['relation_id'] for r in route};seen=set()
    for r in overlap:
        key=frozenset([r['first_relation'],r['second_relation']]);assert len(key)==2 and key<=ids and key not in seen;seen.add(key)
        assert 0<=float(r['length_jaccard'])<=1 and 0<=float(r['segment_key_jaccard'])<=1
    return {'single_benchmark_rows':len(benchmarks),'pair_association_rows':len(pairs),'all_route_pairs':len(overlap)}


def run():
    execution=read('execution.json');assert execution['status']=='completed'
    assert sha(ROOT/'research/config/structural-protocol.json')==execution['protocol_sha256']
    for name,digest in execution['source_code_lf_sha256'].items():assert lfsha(ROOT/'research/src'/name)==digest,name
    for name,digest in execution['artifact_sha256'].items():assert sha(ROOT/name)==digest,name
    result={'status':'passed',**graph(),**descriptives(),**comparisons()}
    manifest=json.loads((FIG/'manifest.json').read_text());assert manifest['figure_count']==6
    for r in manifest['figures']:
        path=FIG/r['figure'];assert sha(path)==r['sha256']
        for name,digest in r['source_sha256'].items():assert sha(ROOT/name)==digest
        tree=ET.parse(path);assert not tree.findall('.//{http://www.w3.org/2000/svg}image') and tree.findall('.//{http://www.w3.org/2000/svg}text')
    result['editable_svg_figures']=6
    print(json.dumps(result));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args()
    if args.freeze:freeze()
    run()
