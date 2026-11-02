"""Standalone, editable SVG figures from the complete path-case evidence."""
import collections
import csv
import gzip
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import shapely
from shapely.ops import substring

from .accessibility import ROOT
from .sensitivity_runs import read_gzip

OUT=ROOT/'research/reports/sensitivity-2026-11-01'
FIG=ROOT/'research/figures/sensitivity-2026-11-02'
PREVIEW=ROOT/'research/runs/sensitivity-figure-preview'
BLUE='#0072B2';ORANGE='#D55E00';DARK='#243447';GRAY='#9BA6B2'


def setup():
    FIG.mkdir(parents=True,exist_ok=True);PREVIEW.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.fonttype':'none',
        'svg.hashsalt':'tehran-sensitivity-v1','axes.spines.top':False,'axes.spines.right':False,
        'axes.linewidth':.6,'axes.edgecolor':'#89919C','savefig.facecolor':'white'})


def save(fig,name):
    path=FIG/(name+'.svg');fig.savefig(path,bbox_inches='tight',metadata={'Date':None})
    path.write_bytes(b'\n'.join(line.rstrip() for line in path.read_bytes().splitlines())+b'\n')
    fig.savefig(PREVIEW/(name+'.png'),bbox_inches='tight',dpi=150);plt.close(fig)
    return path


def run():
    setup();paths=[];summary=json.loads((OUT/'path-summary.json').read_text())
    pairs=[r for r in summary['case_results'] if r['case'].startswith('pair-')]
    fig,axes=plt.subplots(1,2,figsize=(10,4.2),sharey=True)
    for ax,mode,title in zip(axes,['bus','bus_metro'],['Walking + bus','Walking + bus + metro']):
        rows=[r for r in pairs if r['mode']==mode];y=np.arange(len(rows))
        new=[r['new_joint_only_losses'] for r in rows];shared=[-r['shared_single_losses'] for r in rows]
        ax.barh(y,new,color=ORANGE,label='New joint-only losses',height=.6)
        ax.barh(y,shared,color=BLUE,label='Shared single losses (subtracted)',height=.6)
        ax.scatter([r['interaction'] for r in rows],y,marker='D',s=16,color=DARK,zorder=3,label='Net interaction C')
        ax.axvline(0,color=DARK,lw=.6);ax.set_title(title);ax.set_yticks(y,[r['case'] for r in rows]);ax.set_xlim(-240,210)
        ax.set_xlabel('Building-feature counts');ax.grid(axis='x',alpha=.15)
    axes[0].invert_yaxis()
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=3,fontsize=8)
    fig.tight_layout(rect=(0,.1,1,1));paths.append(save(fig,'pair-mechanisms-all-extrema'))
    negative=[r for r in summary['case_results'] if r['case'].startswith('negative')]
    fig,ax=plt.subplots(figsize=(8,3.7));y=np.arange(len(negative))
    ax.barh(y,[r['bus_loss_rescued'] for r in negative],color=BLUE,height=.6,label='Bus-baseline losses rescued')
    ax.barh(y,[-r['extra_full_baseline_lost'] for r in negative],color=ORANGE,height=.6,label='Extra full-baseline opportunities lost (subtracted)')
    ax.scatter([r['bus_loss']-r['bus_metro_loss'] for r in negative],y,marker='D',color=DARK,s=22,zorder=3,label='Change in metro benefit')
    ax.set_yticks(y,[r['case'].replace('negative-delta-','Group ') for r in negative]);ax.invert_yaxis()
    ax.axvline(0,color=DARK,lw=.7);ax.set_xlabel('Building-feature counts');ax.set_title('Every negative-DeltaM single signature · W=1,000 m, K=1')
    ax.set_xlim(-16,10)
    handles,labels=ax.get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=1,frameon=False,fontsize=8)
    fig.tight_layout(rect=(0,.22,1,1));paths.append(save(fig,'negative-metro-decomposition'))
    entities={r['entity']:np.array([float(r['x_m']),float(r['y_m'])])/1000 for r in read_gzip(OUT/'path-entity-coordinates.csv.gz')}
    members=read_gzip(OUT/'path-case-members.csv.gz')
    traces=json.loads((ROOT/'research/model/m1-v1/traces.json').read_text())
    lines={rid:np.asarray(r['xy_m'])/1000 for rid,r in traces.items()}
    with (ROOT/'research/model/m1-v1/routes.csv').open(newline='') as f:route_modes={r['relation_id']:r['mode'] for r in csv.DictReader(f)}
    colors={'joint_only':ORANGE,'shared':BLUE,'one_single':DARK};markers={'joint_only':'^','shared':'s','one_single':'o'}
    for page in range(4):
        fig,axes=plt.subplots(2,2,figsize=(8.2,7.5))
        for local,case_index in enumerate(range(page*2,page*2+2)):
            label=f'pair-{case_index}'
            all_rows=[r for r in members if r['case']==label]
            all_xy=np.array([entities[r['origin']] for r in all_rows]);lo=all_xy.min(axis=0)-.35;hi=all_xy.max(axis=0)+.35
            for col,mode in enumerate(['bus','bus_metro']):
                ax=axes[local,col]
                for rid,line in lines.items():ax.plot(line[:,0],line[:,1],lw=.45,color=GRAY,alpha=.45,zorder=1)
                rows=[r for r in all_rows if r['mode']==mode]
                for category in colors:
                    points=np.array([entities[r['origin']] for r in rows if r['category']==category])
                    if len(points):ax.scatter(points[:,0],points[:,1],s=9,c=colors[category],marker=markers[category],lw=0,zorder=2)
                evidence=next(r for r in pairs if r['case']==label and r['mode']==mode)
                ax.set(xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),aspect='equal')
                ax.set_title(f"{label} · {'bus' if col==0 else 'bus + metro'}\nLoss={len(rows)}, C={evidence['interaction']:+d}",fontsize=9)
                ax.set_xlabel('UTM easting (km)');ax.set_ylabel('UTM northing (km)');ax.ticklabel_format(useOffset=False,style='plain')
                ax.tick_params(labelsize=8)
        handles=[Line2D([],[],color=colors[c],marker=markers[c],ls='',ms=5,label=l) for c,l in [('joint_only','Joint-only loss'),('shared','Shared single loss'),('one_single','One-single loss')]]
        fig.legend(handles=handles,loc='lower center',ncol=3,frameon=False,fontsize=8)
        fig.text(.5,-.012,'© OpenStreetMap contributors · ODbL 1.0 | EPSG:32639',ha='center',fontsize=7,color='#526171')
        fig.suptitle('All affected origins in registered extreme cases · W=1,000 m, K=1',fontsize=10)
        fig.tight_layout(rect=(0,.04,1,.96));paths.append(save(fig,f'all-extreme-origin-maps-{page+1}'))
    # One deterministically selected witness illustrates the already exhaustive
    # certificate set. It is not a sample used for any quantitative inference.
    extra=sorted({r['origin'] for r in members if r['case']=='negative-delta-105' and r['category']=='extra_full_baseline_lost'})
    states=json.loads((OUT/'path-failed-sets.json').read_text());intact=next(k for k,v in states.items() if not v)
    with gzip.open(OUT/'path-witnesses.jsonl.gz','rt') as f:
        chosen=next(json.loads(line) for line in f if (lambda r:r['origin']==extra[0] and r['mode']=='bus_metro' and r['failed_set']==intact)(json.loads(line)))
    nodes={r['node']:np.array([float(r['x_m']),float(r['y_m'])])/1000 for r in read_gzip(OUT/'path-node-coordinates.csv.gz')}
    edges={int(r['edge_id']):r for r in read_gzip(OUT/'path-walking-edges.csv.gz')}
    with (ROOT/'research/model/m1-v1/stops.csv').open(newline='') as f:stops={f"stop:{r['route_relation_id']}:{r['stop_sequence']}":float(r['trace_progress_m']) for r in csv.DictReader(f)}
    fig,ax=plt.subplots(figsize=(7,5.2));bounds=[]
    for leg in chosen['legs']:
        if leg['kind']=='walk':
            for eid in leg['edge_ids']:
                e=edges[eid];line=np.array([nodes[e['u']],nodes[e['v']]])
                ax.plot(line[:,0],line[:,1],color=DARK,lw=1.4);bounds.extend(line)
        else:
            for connection in leg['connection_ids']:
                rid,a,b=connection.split(':');line=substring(shapely.LineString(np.asarray(traces[rid]['xy_m'])),stops[f'stop:{rid}:{a}'],stops[f'stop:{rid}:{b}'])
                xy=np.asarray(line.coords)/1000;ax.plot(xy[:,0],xy[:,1],color=BLUE if route_modes[rid]=='metro' else ORANGE,lw=1.8);bounds.extend(xy)
    points=np.array([entities[k] for k in extra]);ax.scatter(points[:,0],points[:,1],s=14,color=DARK,marker='^',label='All 13 extra-baseline lost origins',zorder=5)
    target=entities[chosen['target']];ax.scatter(*target,marker='P',s=70,c=DARK,label='Witness target',zorder=6)
    origin=entities[chosen['origin']];ax.scatter(*origin,marker='o',s=65,facecolors='none',edgecolors=DARK,label='Illustrated origin',zorder=7)
    bounds=np.vstack([bounds,points,target]);lo=bounds.min(axis=0)-.5;hi=bounds.max(axis=0)+.5
    ax.set(xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),aspect='equal',xlabel='UTM easting (km)',ylabel='UTM northing (km)')
    ax.set_title('Metro → bus dependence in a baseline minimum-walking witness',fontsize=10)
    handles,labels=ax.get_legend_handles_labels();handles.extend([Line2D([],[],color=BLUE,lw=2),Line2D([],[],color=ORANGE,lw=2),Line2D([],[],color=DARK,lw=1.4)])
    labels.extend(['Metro trace','Bus trace','Walking network edges']);ax.legend(handles,labels,frameon=False,fontsize=8,loc='best')
    ax.ticklabel_format(useOffset=False,style='plain');fig.tight_layout()
    fig.text(.5,-.012,'© OpenStreetMap contributors · ODbL 1.0 | EPSG:32639',ha='center',fontsize=7,color='#526171')
    paths.append(save(fig,'metro-bus-witness'))
    manifest={'source_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('path-*')},
        'reconstructed_model_inputs_sha256':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [ROOT/'research/model/m1-v1/traces.json',ROOT/'research/model/m1-v1/routes.csv',ROOT/'research/model/m1-v1/stops.csv']},
        'svg_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'illustration_origin':chosen['origin'],'illustration_target':chosen['target'],
        'map_note':'EPSG:32639. Extreme maps show windows around every affected origin; source closure segments may lie outside these windows. Grey lines are accepted route traces. Witness traces are mapping associations; stop-to-trace offsets are not extra modeled walking legs.'}
    (FIG/'path-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');return paths


if __name__=='__main__':run()
