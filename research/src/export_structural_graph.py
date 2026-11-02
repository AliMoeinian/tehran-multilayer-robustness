"""Publish the evaluated graph and complete source-to-chain provenance.

CSV numbers, rather than a platform-specific compressed NumPy container, define
the public evaluated graph. This does not recompute or change any weights.
"""
import json
from pathlib import Path

import numpy as np

from .pair_closures import write_gzip_csv
from .structural_centrality import MODEL, OUT, sha


def run():
    g = dict(np.load(MODEL / 'graph.npz'))
    inventory = json.loads((OUT / 'graph-inventory.json').read_text())
    assert sha(MODEL / 'graph.npz') == inventory['graph_sha256']
    canonical = np.full(int(g['quotient'].max()) + 1, np.iinfo(np.int64).max)
    np.minimum.at(canonical, g['quotient'], g['native_ids'])
    retained_native = canonical[g['retained']]
    vertices = OUT / 'junction-vertices.csv.gz'
    write_gzip_csv(vertices, ['junction', 'canonical_native_node', 'od_weight', 'component'],
                   ((i, int(node), int(od), int(component)) for i, (node, od, component)
                    in enumerate(zip(retained_native, g['od'], g['component']))))
    mapping = OUT / 'source-chain-mapping'
    mapping.mkdir(exist_ok=True)
    parts = []
    for start in range(0, len(g['source_u']), 50000):
        end = min(start+50000, len(g['source_u']))
        part = mapping / f'part-{len(parts):03d}.csv.gz'
        write_gzip_csv(part,
                   ['occurrence', 'source_way', 'first_node', 'second_node',
                    'source_length_m', 'physical_edge', 'chain'],
                   ((i, int(way), int(a), int(b), float(length), int(edge),
                     int(g['chain_of'][edge]) if edge >= 0 else -1)
                    for i, (way, a, b, length, edge) in enumerate(zip(
                        g['source_way'][start:end], g['source_u'][start:end], g['source_v'][start:end],
                        g['source_length'][start:end], g['source_edge'][start:end]), start)))
        parts.append({'file': f'source-chain-mapping/{part.name}', 'first_occurrence':start,
                      'occurrences':end-start, 'sha256':sha(part)})
    mapping_index = OUT / 'source-chain-index.json'
    mapping_index.write_text(json.dumps({'source_occurrences':len(g['source_u']), 'parts':parts,
        'order':'Read parts in listed order. Every original occurrence is retained exactly once; sharding only bounds file sizes.'},indent=2)+'\n',encoding='utf-8',newline='\n')
    report = {'status': 'passed', 'vertices': len(g['od']),
              'od_junctions': int(g['od'].sum()),
              'source_occurrences': len(g['source_u']),
              'graph_sha256': inventory['graph_sha256'],
              'definition': 'All evaluated vertices, including zero-OD storage cycle vertices; every original source occurrence maps to its physical link and chain. Chain endpoints, lengths and final scores are in junction-centrality.csv.gz.',
              'source_code_sha256': sha(Path(__file__)),
              'artifact_sha256': {str(p.relative_to(OUT)).replace('\\','/'): sha(p) for p in [vertices, mapping_index, *mapping.glob('*.csv.gz')]}}
    (OUT / 'graph-export.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    run()
