"""Editable, source-backed research figures; no display sampling."""
import argparse
import json
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon
from matplotlib.colors import Normalize
import numpy as np
from pyproj import Transformer
from shapely.ops import transform

from .accessibility import ROOT
from .sensitivity_runs import read_gzip, gp_geometry
from .structural_centrality import OUT, sha

FIG = ROOT / 'research/figures/structural-2026-11-02'
BLUE, GOLD, INK = '#25668a', '#bd741e', '#26313a'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
                     'svg.fonttype': 'none', 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.labelcolor': INK,
                     'text.color': INK, 'savefig.facecolor': 'white'})


def run(include_centrality=True):
    FIG.mkdir(parents=True, exist_ok=True)
    records = []

    def save(fig, name, sources, scope):
        # Matplotlib rasterizes long colorbars automatically; keep exports vector.
        for axis in fig.axes:
            for collection in axis.collections:
                collection.set_rasterized(False)
        path = FIG / (name + '.svg')
        fig.savefig(path, bbox_inches='tight', metadata={'Date': None,
                    'Description': scope})
        svg = path.read_text(encoding='utf-8')
        path.write_text('\n'.join(line.rstrip() for line in svg.splitlines()) + '\n',
                        encoding='utf-8', newline='\n')
        fig.savefig(ROOT / 'research/runs/structural-v1' / (name + '.png'), dpi=150, bbox_inches='tight')
        plt.close(fig)
        records.append({'figure': path.name, 'sha256': sha(path), 'scope': scope,
                        'source_sha256': {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in sources}})

    index = json.loads((OUT / 'district-index.json').read_text())['districts']
    source = ROOT / 'data/extracted/tehran-osm-20261029T212126Z-v1.1-public/tehran_audited_layers.gpkg'
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as db:
        polygons = {int(i): gp_geometry(b) for i, b in db.execute('select osm_id,geom from municipal_districts')}
    project = Transformer.from_crs(4326, 32639, always_xy=True).transform
    polygons = {r['district']: transform(project, polygons[r['relation_id']]) for r in index}
    baseline = {int(r['district']): r for r in read_gzip(OUT / 'district-baseline.csv.gz')
                if r['mode'] == 'bus_metro' and r['max_line_changes'] == '1' and r['walking_budget_m'] == '1000'}
    losses = {int(r['district']): r for r in read_gzip(OUT / 'district-loss-summary.csv.gz')
              if r['mode'] == 'bus_metro' and r['max_line_changes'] == '1' and r['walking_budget_m'] == '1000'}
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for ax, field, rows, title in zip(axes,
            ['share_all_buildings', 'maximum_loss_share_all_buildings'], [baseline, losses],
            ['Healthy structural access', 'Largest single-closure loss']):
        patches, colors = [], []
        maximum = max(float(r[field]) * 100 for d, r in rows.items() if d > 0)
        for district, geometry in polygons.items():
            for part in getattr(geometry, 'geoms', [geometry]):
                # District holes remain white by drawing their rings separately.
                patches.append(Polygon(np.asarray(part.exterior.coords) / 1000))
                colors.append(float(rows[district][field]) * 100)
        collection = PatchCollection(patches, cmap='Blues', norm=Normalize(0, maximum), edgecolor='white', linewidth=.6)
        collection.set_array(np.asarray(colors)); ax.add_collection(collection)
        for district, geometry in polygons.items():
            for part in getattr(geometry, 'geoms', [geometry]):
                for ring in part.interiors:
                    ax.add_patch(Polygon(np.asarray(ring.coords) / 1000, facecolor='white', edgecolor='white', linewidth=.3))
            point = geometry.representative_point()
            label_color = 'white' if float(rows[district][field]) * 100 > maximum * .55 else INK
            ax.text(point.x / 1000, point.y / 1000, str(district), ha='center', va='center', fontsize=7, color=label_color)
        ax.autoscale_view(); ax.set_aspect('equal'); ax.set_axis_off(); ax.set_title(title)
        fig.colorbar(collection, ax=ax, shrink=.65, label='% of all recorded buildings in district')
    fig.suptitle('Bus + metro | cumulative walk ≤ 1,000 m | at most one line change')
    fig.text(.04, -.015, 'All 22 source districts; 24 city origins in polygon gaps retained separately. Geometry: © OpenStreetMap contributors.', fontsize=8)
    save(fig, 'district-access-and-loss', [source, OUT/'district-index.json', OUT/'district-baseline.csv.gz', OUT/'district-loss-summary.csv.gz'],
         'District denominators are all recorded buildings, not population; separate panel scales. OSM district polygons are not certified legal boundaries.')

    rows = read_gzip(OUT/'building-reachable-target-groups.csv.gz')
    fig, ax = plt.subplots(figsize=(7, 4))
    for mode, b, label, color, style in [('bus', 0, 'Walking only', '#666666', ':'),
            ('bus', 2, 'Bus', GOLD, '--'), ('bus_metro', 2, 'Bus + metro', BLUE, '-')]:
        values = np.asarray([int(r[f'{mode}_b{b}_w1000']) for r in rows])
        x, counts = np.unique(values, return_counts=True)
        ax.step(np.r_[0, x], np.r_[0, np.cumsum(counts)/len(rows)], where='post', label=label, color=color, linestyle=style, linewidth=1.7)
    ax.set(xlabel='Reachable possible hospital groups', ylabel='Cumulative share of all recorded buildings', ylim=(0, 1.02))
    ax.grid(axis='y', color='#eeeeee'); ax.legend(frameon=False)
    ax.set_title('Candidate-destination multiplicity | walk ≤ 1,000 m; at most two boardings')
    fig.text(.1, -.02, 'All 65,677 origins, including rejected connectors. Possible groups are not clinically verified alternatives.', fontsize=8)
    save(fig, 'candidate-group-count-ecdf', [OUT/'building-reachable-target-groups.csv.gz'],
         'Exact ECDF over all origins. Zero reachable groups includes rejected connectors and no feasible modeled path.')

    routes = read_gzip(OUT/'route-descriptions.csv.gz')
    routes.sort(key=lambda r: (r['mode'] != 'bus', int(r['relation_id'])))
    position = {r['relation_id']: i for i, r in enumerate(routes)}
    matrix = np.eye(len(routes))
    pairs = read_gzip(OUT/'route-pair-overlap.csv.gz')
    for r in pairs:
        a, b = position[r['first_relation']], position[r['second_relation']]
        matrix[a,b] = matrix[b,a] = float(r['length_jaccard'])
    fig, ax = plt.subplots(figsize=(8.4, 7))
    heat = ax.pcolormesh(np.arange(26), np.arange(26), matrix, cmap='Blues', vmin=0, vmax=1, edgecolors='white', linewidth=.3)
    labels = [f"{'B' if r['mode']=='bus' else 'R'} {r['relation_id']}" for r in routes]
    ax.set_xticks(np.arange(25)+.5, labels, rotation=90, fontsize=7)
    ax.set_yticks(np.arange(25)+.5, labels, fontsize=7); ax.invert_yaxis(); ax.set_aspect('equal')
    ax.axvline(11, color=INK, linewidth=1); ax.axhline(11, color=INK, linewidth=1)
    fig.colorbar(heat, ax=ax, shrink=.7, label='Shared / union source interval length')
    ax.set_title('All 300 accepted relation pairs | source-geometry overlap')
    fig.text(.1, -.01, 'B: bus; R: rail. Relation IDs identify direction/representation instances, not unique operating lines.', fontsize=8)
    save(fig, 'route-overlap-matrix', [OUT/'route-descriptions.csv.gz', OUT/'route-pair-overlap.csv.gz'],
         'Every accepted relation pair; interval unions merge repeat traversals. Distinct source ways remain distinct. Diagonal is the identity, not an evaluated distinct pair.')

    strata = [r for r in read_gzip(OUT/'pair-feature-strata.csv.gz') if r['max_line_changes']=='1' and r['walking_budget_m']=='1000']
    starts = [0,250,500,1000,2000,5000,10000,20000]
    labels = ['0–250','250–500','500–1k','1–2k','2–5k','5–10k','10–20k','≥20k']
    fig, axes = plt.subplots(1,2, figsize=(10,4), sharey=True)
    for ax, mode in zip(axes, ['bus','bus_metro']):
        for shared, color, marker in [(0, '#666666', 'o'), (1, BLUE, 's'), (2, GOLD, '^')]:
            records2 = {float(r['distance_min_m']): r for r in strata if r['mode']==mode and int(r['shared_bus_relations'])==shared}
            values = [float(records2[x]['mean_C']) if int(records2[x]['pairs']) else np.nan for x in starts]
            ax.plot(np.arange(8), values, marker=marker, color=color, label=f'{shared} shared bus relations', linewidth=1.3, markersize=4)
        ax.axhline(0, color=INK, linewidth=.7); ax.set_xticks(np.arange(8), labels, rotation=40, ha='right')
        ax.set_title('Bus' if mode=='bus' else 'Bus + metro'); ax.set_xlabel('Source midpoint distance bin (m)')
    axes[0].set_ylabel('Mean signed pair interaction C (buildings)'); axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle('Every 1,417,086 physical pair | walk ≤ 1,000 m; at most one line change')
    fig.text(.06,-.13,'Each point averages every pair in its fixed bin; empty bins are absent. Pair dependence precludes independent-observation inference.',fontsize=8)
    save(fig,'pair-interaction-by-distance',[OUT/'pair-feature-strata.csv.gz'],
         'Mean signed interaction, retaining every physical pair and multiplicity. Distance is Euclidean midpoint distance, not travel distance. No error bars or causal inference.')

    if include_centrality:
        rows = read_gzip(OUT/'single-benchmark-rank-comparisons.csv.gz')
        benchmarks = ['dependent_bus_relations','dependent_connections','length_m','junction_edge_betweenness']
        short = ['Dependent bus relations','Dependent stop connections','Source segment length','Junction edge betweenness']
        grid = [(k,w) for k in [0,1,2] for w in [500,1000,2000]]
        fig, axes = plt.subplots(1,2, figsize=(10,4.4),sharey=True)
        for ax,mode in zip(axes,['bus','bus_metro']):
            values = np.full((4,9), np.nan)
            for r in rows:
                if r['mode']==mode and r['spearman']:
                    values[benchmarks.index(r['benchmark']),grid.index((int(r['max_line_changes']),int(r['walking_budget_m'])))]=float(r['spearman'])
            heat=ax.pcolormesh(np.arange(10),np.arange(5),np.ma.masked_invalid(values),cmap='BrBG',vmin=-1,vmax=1,edgecolors='white',linewidth=.5)
            ax.set_xticks(np.arange(9)+.5,[f'{w}\n{k}' for k,w in grid],fontsize=8)
            ax.set_yticks(np.arange(4)+.5,short);ax.invert_yaxis()
            for a in range(4):
                for b in range(9):ax.text(b+.5,a+.5,f'{values[a,b]:.2f}' if np.isfinite(values[a,b]) else '—',ha='center',va='center',fontsize=8)
            ax.set_title('Bus' if mode=='bus' else 'Bus + metro');ax.set_xlabel('Walking budget (m) / maximum line changes')
        axes[0].set_ylim(4,0)
        fig.colorbar(heat,ax=axes.ravel().tolist(),label='Spearman correlation',fraction=.025,pad=.03)
        fig.suptitle('Structural proxy versus destination-specific single-closure loss | all 1,684 units')
        save(fig,'single-loss-proxy-correlations',[OUT/'single-benchmark-rank-comparisons.csv.gz'],
             'All 72 full-domain tied-rank correlations. Constant vectors are undefined. Exact uniform-junction betweenness is a structural corridor comparator, not traffic.')

        rows = [r for r in read_gzip(OUT/'single-loss-by-road-class.csv.gz') if r['max_line_changes']=='1' and r['walking_budget_m']=='1000']
        categories=sorted({r['highway'] for r in rows});fig,axes=plt.subplots(1,2,figsize=(9,4.5),sharey=True,sharex=True)
        for ax,mode,color in zip(axes,['bus','bus_metro'],[GOLD,BLUE]):
            byclass={r['highway']:r for r in rows if r['mode']==mode}
            ax.barh(np.arange(len(categories)),[float(byclass[c]['mean_loss']) for c in categories],color=color)
            ax.set_yticks(np.arange(len(categories)),[f"{c} (n={byclass[c]['streets']})" for c in categories]);ax.invert_yaxis();ax.set_xlabel('Mean single-closure loss (buildings)')
            ax.set_title('Bus' if mode=='bus' else 'Bus + metro');ax.grid(axis='x',color='#eeeeee');ax.set_axisbelow(True)
        axes[0].set_ylim(len(categories)-.5,-.5)
        fig.suptitle('Recorded highway classes | walk ≤ 1,000 m; at most one line change')
        save(fig,'single-loss-by-highway-class',[OUT/'single-loss-by-road-class.csv.gz'],
             'All 1,684 source units; nominal recorded highway classes, no numeric hierarchy and no causal adjustment. Unequal class size is shown explicitly.')

    manifest={'status':'passed','editable_svg_text':True,'figure_count':len(records),'source_code_sha256':sha(Path(__file__)),'figures':records}
    (FIG/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'figures':len(records),'directory':str(FIG)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--descriptives-only',action='store_true');args=parser.parse_args()
    run(not args.descriptives_only)
