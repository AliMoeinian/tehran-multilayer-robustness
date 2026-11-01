"""Rebuild the English progress report's static SVG figures and numeric tables.

Reads frozen local evidence only. M1 must have produced traces.json for the map.
SVGs contain vector marks and editable text; PNGs are ignored review previews.
"""
import collections
import csv
import hashlib
import json
from pathlib import Path
import sqlite3

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Polygon
import numpy as np
from pyproj import Transformer
import shapely
from shapely.ops import transform

from .accessibility import ROOT

REPORTS=ROOT/'research/reports'
OUT=ROOT/'research/figures/progress-2026-11-01'
PREVIEW=ROOT/'research/runs/progress-figure-preview'
BUS='#0072B2';METRO='#D55E00';WALK='#667085';INK='#202936';GRID='#E5E7EB'


def read_json(path):return json.loads(path.read_text(encoding='utf-8'))


def read_csv(path):
    with path.open(newline='',encoding='utf-8') as stream:return list(csv.DictReader(stream))


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    OUT.mkdir(parents=True,exist_ok=True);PREVIEW.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':10,
        'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':8,'text.color':INK,
        'axes.labelcolor':INK,'axes.edgecolor':'#89919C','axes.linewidth':.6,
        'axes.spines.top':False,'axes.spines.right':False,'grid.color':GRID,
        'grid.linewidth':.6,'svg.fonttype':'none','svg.hashsalt':'tehran-progress-v1',
        'savefig.facecolor':'white','figure.facecolor':'white'})
    inputs=[REPORTS/'m1-2026-11-01-summary.json',REPORTS/'m2-2026-11-01-summary.json',
            REPORTS/'m3-2026-11-01-summary.json',
            REPORTS/'m3-single-closures-2026-11-01/summary.json',
            REPORTS/'m3-single-closures-2026-11-01/effects.csv',
            ROOT/'research/model/m1-v1/routes.csv',ROOT/'research/model/m1-v1/traces.json']
    m1,m2,baseline,closures=[read_json(p) for p in inputs[:4]]
    effects=read_csv(inputs[4]);routes=read_csv(inputs[5]);traces=read_json(inputs[6])
    assert m1['config_sha256']==m2['config_sha256']==baseline['config_sha256']==closures['config_sha256']
    accepted_counts=collections.Counter(r['mode'] for r in routes if r['status']=='candidate_for_walking_connection_audit')
    assert accepted_counts=={'bus':11,'metro':14}
    figure_names=[]
    def save(fig,name):
        fig.savefig(OUT/(name+'.svg'),bbox_inches='tight',metadata={'Date':None,
            'Creator':'Tehran Multilayer Robustness; make_progress_figures.py'})
        svg=OUT/(name+'.svg')
        svg.write_bytes(svg.read_bytes().replace(b'\r\n',b'\n'))
        fig.savefig(PREVIEW/(name+'.png'),dpi=170,bbox_inches='tight')
        plt.close(fig);figure_names.append(name)

    fig,ax=plt.subplots(figsize=(6.7,2.65));y=np.arange(2)
    accepted=[m1['route_status_by_mode'][mode]['candidate_for_walking_connection_audit'] for mode in ['bus','metro']]
    review=[m1['route_status_by_mode'][mode].get('needs_review',0) for mode in ['bus','metro']]
    ax.barh(y,accepted,color=BUS,height=.48,label='Accepted for the current model')
    ax.barh(y,review,left=accepted,color='#D9DDE3',height=.48,hatch='///',edgecolor='white',label='Retained for review')
    for i,(a,r) in enumerate(zip(accepted,review)):
        ax.text(a/2,i,str(a),ha='center',va='center',color='white',fontweight='bold')
        if r:ax.text(a+r/2,i,str(r),ha='center',va='center')
    ax.set(yticks=y,yticklabels=['Bus relations','Rail relations'],xlabel='Number of OSM route relations',xlim=(0,42))
    ax.invert_yaxis();ax.set_xticks([0,10,20,30,40]);ax.set_axisbelow(True);ax.grid(axis='x')
    ax.legend(loc='upper center',bbox_to_anchor=(.5,1.30),ncol=2,frameon=False,fontsize=8)
    fig.subplots_adjust(top=.77,bottom=.23,left=.20,right=.98);save(fig,'01-route-screening')

    dataset=ROOT/'data/extracted'/m2['dataset_id'];gpkg=dataset/'tehran_audited_layers.gpkg'
    inputs.append(gpkg)
    db=sqlite3.connect(gpkg.as_uri()+'?mode=ro',uri=True)
    project=Transformer.from_crs(4326,32639,always_xy=True).transform
    def raw_geom(blob):
        size={0:0,1:32,2:48,3:48,4:64}[(blob[3]>>1)&7]
        return shapely.from_wkb(blob[8+size:])
    def geom(blob):return transform(project,raw_geom(blob))
    boundary=geom(db.execute('select geom from city_boundary').fetchone()[0])
    districts=[geom(r[0]) for r in db.execute('select geom from municipal_districts')]
    network=ROOT/'research/model/m2-v2/network.sqlite';inputs.append(network)
    assert digest(network)==baseline['network_sha256']==closures['network_sha256']
    model=sqlite3.connect(network.as_uri()+'?mode=ro',uri=True)
    targets={r[0] for r in model.execute("select entity from connectors where kind='hospital' and status='geometric_candidate'")}
    hospital_xy=[]
    for raw,blob in db.execute('select attributes_json,geom from hospital_screened_candidates'):
        a=json.loads(raw)
        if f"hospital:{a['osm_type']}{a['osm_id']}" in targets:
            point=raw_geom(blob).representative_point();x,y=project(point.x,point.y)
            hospital_xy.append((x/1000,y/1000))
    db.close();model.close();assert len(hospital_xy)==baseline['target_features']
    fig,ax=plt.subplots(figsize=(7.1,5.4))
    for polygon in boundary.geoms:
        ax.add_patch(Polygon(np.asarray(polygon.exterior.coords)/1000,facecolor='#F3F4F6',edgecolor=INK,lw=.8,zorder=0))
    for district in districts:
        for polygon in getattr(district,'geoms',[district]):
            xy=np.asarray(polygon.exterior.coords)/1000;ax.plot(xy[:,0],xy[:,1],color='#C4C9D1',lw=.35,zorder=1)
    for row in routes:
        if row['status']!='candidate_for_walking_connection_audit':continue
        xy=np.asarray(traces[row['relation_id']]['xy_m'])/1000
        ax.plot(xy[:,0],xy[:,1],color=BUS if row['mode']=='bus' else METRO,
                lw=1.05 if row['mode']=='bus' else .85,alpha=.85,zorder=3)
    h=np.asarray(hospital_xy);ax.scatter(h[:,0],h[:,1],s=7,marker='+',linewidths=.5,color=INK,zorder=2)
    ax.set_aspect('equal',adjustable='box');ax.set_xlabel('Easting (km; WGS 84 / UTM zone 39N)');ax.set_ylabel('Northing (km)')
    handles=[Line2D([],[],color=BUS,lw=1.4,label='Accepted bus traces (11 relations)'),
             Line2D([],[],color=METRO,lw=1.4,label='Accepted rail traces (14 relations)'),
             Line2D([],[],color=INK,marker='+',ls='',label='Connected hospital candidates (241 features)'),
             Patch(facecolor='#F3F4F6',edgecolor=INK,label='OSM study boundary; district outlines')]
    ax.legend(handles=handles,loc='upper left',fontsize=7.5,frameon=True,framealpha=.95)
    ax.margins(.035);fig.tight_layout(rect=(0,.035,1,1))
    fig.text(.98,.012,'Map data: © OpenStreetMap contributors · ODbL 1.0 · Geofabrik',ha='right',fontsize=6.5,color=WALK)
    save(fig,'02-study-network-map')

    lookup={(r['mode'],r['max_line_changes'],r['walking_budget_m']):r for r in baseline['results']}
    fig,axes=plt.subplots(1,3,figsize=(7.2,3.0),sharey=True);ws=[500,1000,2000]
    for k,ax in enumerate(axes):
        for mode,color,marker,label in [('walk',WALK,'s','Walking only'),('bus',BUS,'o','Walking + bus'),('bus_metro',METRO,'^','Walking + bus + metro')]:
            vals=[lookup[mode,None if mode=='walk' else k,w]['share_all_buildings']*100 for w in ws]
            ax.plot(ws,vals,color=color,marker=marker,lw=1.4,ms=4,label=label)
        ax.set(title=f'({chr(97+k)}) K = {k}',xlabel='Walking budget W (m)',xticks=ws,ylim=(0,85))
        ax.tick_params(axis='x',labelrotation=0);ax.grid(axis='y');ax.yaxis.set_major_formatter(PercentFormatter())
    axes[0].set_ylabel('Accessible building locations / 65,677')
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',ncol=3,frameon=False,fontsize=8)
    fig.subplots_adjust(top=.79,bottom=.22,wspace=.15,left=.10,right=.98);save(fig,'03-intact-accessibility')

    numeric=[]
    fig,axes=plt.subplots(1,3,figsize=(7.2,3),sharex=True,sharey=True)
    for ax,w in zip(axes,ws):
        rows=[r for r in effects if int(r['max_line_changes'])==1 and int(r['walking_budget_m'])==w]
        for mode,color,style,label in [('bus',BUS,'-','Without metro'),('bus_metro',METRO,'--','With metro')]:
            losses=np.repeat([int(r[mode+'_loss_buildings']) for r in rows],[int(r['street_count']) for r in rows])
            assert len(losses)==closures['observed_streets']
            x=np.arange(0,261);survival=np.array([np.count_nonzero(losses>value)/len(losses) for value in x])
            ax.step(x,survival*100,where='post',color=color,ls=style,lw=1.4,label=label)
            numeric.append({'walking_budget_m':w,'max_line_changes':1,'mode':mode,
                            'loss_counts':dict(sorted(collections.Counter(map(int,losses)).items()))})
        ax.set(title=f'W = {w:,} m',xlabel='Loss threshold (buildings)',xlim=(0,260),ylim=(0,60),xticks=[0,100,200])
        ax.grid(axis='y');ax.yaxis.set_major_formatter(PercentFormatter())
    axes[0].set_ylabel('Street segments with loss > threshold')
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',ncol=2,frameon=False,fontsize=8)
    fig.subplots_adjust(top=.79,bottom=.22,left=.10,right=.98,wspace=.15);save(fig,'04-single-closure-loss-distribution')

    rows=[r for r in effects if int(r['max_line_changes'])==1 and int(r['walking_budget_m'])==1000]
    pairs=collections.Counter()
    for r in rows:pairs[int(r['bus_loss_buildings']),int(r['bus_metro_loss_buildings'])]+=int(r['street_count'])
    lower=sum(n for (x,y),n in pairs.items() if y<x);same=sum(n for (x,y),n in pairs.items() if y==x);higher=sum(n for (x,y),n in pairs.items() if y>x)
    assert lower+same+higher==closures['observed_streets']
    fig,(ax,bar)=plt.subplots(1,2,figsize=(7.2,3.4),gridspec_kw={'width_ratios':[1,1.05]})
    ax.plot([0,240],[0,240],ls='--',color=WALK,lw=.8,zorder=1)
    ax.scatter([x for x,y in pairs],[y for x,y in pairs],s=[.6*n for n in pairs.values()],
               color='#A8B5C7',edgecolors=INK,linewidths=.5,zorder=2)
    ax.set(xlim=(-22,240),ylim=(-22,240),xlabel='Loss without metro (buildings)',ylabel='Loss with metro (buildings)',title='(a) Paired closure effects')
    ax.set_aspect('equal');ax.text(137,156,'Equal loss',color=WALK,fontsize=8,rotation=45)
    size_handles=[ax.scatter([],[],s=.6*n,facecolor='#A8B5C7',edgecolors=INK,lw=.5,label=f'{n:,}') for n in [10,100,1000]]
    ax.legend(handles=size_handles,title='Street segments',loc='upper left',fontsize=7,title_fontsize=7,frameon=False,labelspacing=1.3,borderpad=1.1)
    vals=[lower,same,higher];colors=[BUS,'#A8AFBA',METRO]
    bar.barh(range(3),vals,color=colors,height=.55)
    for i,n in enumerate(vals):bar.text(n+18,i,f'{n:,}',va='center',fontsize=9)
    bar.set(yticks=range(3),yticklabels=['Lower loss\nwith metro','Equal loss','Higher loss\nwith metro'],xlim=(0,1400),xlabel='Number of street segments',title='(b) Direction of the loss difference')
    bar.invert_yaxis();bar.xaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v:,.0f}'));bar.set_axisbelow(True);bar.grid(axis='x')
    fig.subplots_adjust(left=.09,right=.98,top=.88,bottom=.19,wspace=.75);save(fig,'05-metro-loss-comparison')

    source_rows={'baseline':baseline['results'],'closure_summary':closures['results'],
                 'closure_distributions':numeric,'metro_loss_comparison':{'lower':lower,'equal':same,'higher':higher},
                 'map':{'bus_relations':11,'rail_relations':14,'hospital_features':len(hospital_xy),'crs':'EPSG:32639'}}
    (OUT/'figure-data.json').write_text(json.dumps(source_rows,indent=2)+'\n',encoding='utf-8',newline='\n')
    manifest={'generated_by':'research/src/make_progress_figures.py','script_sha256':digest(Path(__file__)),
              'source_sha256':{p.relative_to(ROOT).as_posix():digest(p) for p in inputs},
              'output_sha256':{p.name:digest(p) for p in sorted(OUT.iterdir()) if p.suffix in {'.svg','.json'} and p.name!='manifest.json'},
              'review_previews':'research/runs/progress-figure-preview (ignored)',
              'scope':'Static vector figures from frozen local evidence; no external data or inferred service coverage.'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    report=REPORTS/'research-progress.en.md'
    text=report.read_text(encoding='utf-8')
    def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
    baseline_table=table(['K','W (m)','Walking only','Walking + bus','Walking + bus + metro'],
        [[k,f'{w:,}']+[f"{lookup[mode,None if mode=='walk' else k,w]['accessible_buildings']:,}" for mode in ['walk','bus','bus_metro']] for k in [0,1,2] for w in ws])
    closure_table=table(['K','W (m)','Positive-loss streets: bus','Positive-loss streets: bus + metro','Maximum loss: bus','Maximum loss: bus + metro'],
        [[r['max_line_changes'],f"{r['walking_budget_m']:,}"]+[f"{r[mode][field]:,}" for field in ['streets_with_positive_loss','maximum_loss_buildings'] for mode in ['bus','bus_metro']] for r in closures['results']])
    for marker,value in [('BASELINE_TABLE',baseline_table),('CLOSURE_TABLE',closure_table)]:
        start='<!-- BEGIN '+marker+' -->';end='<!-- END '+marker+' -->'
        before,rest=text.split(start,1);_,after=rest.split(end,1);text=before+start+'\n'+value+'\n'+end+after
    report.write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps({'figures':figure_names,'output':str(OUT),'paired_loss_counts':[lower,same,higher]}))


if __name__=='__main__':main()
