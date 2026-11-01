"""Render the exhaustive paired-closure census as editable-text vector SVGs."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter,MaxNLocator
import numpy as np

from .accessibility import ROOT


def main():
    source=ROOT/'research/reports/m4-pairs-exhaustive-2026-11-01'
    out=ROOT/'research/figures/pairs-exhaustive-2026-11-01';out.mkdir(parents=True,exist_ok=True)
    preview=ROOT/'research/runs/pair-figure-preview';preview.mkdir(parents=True,exist_ok=True)
    summary=json.loads((source/'summary.json').read_text());cases=json.loads((source/'extreme-cases.json').read_text())
    assert summary['selection']['exhaustive'] and summary['evaluated_street_pairs']==summary['domain']['street_pairs']
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':10,
        'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#89919C',
        'axes.linewidth':.6,'svg.fonttype':'none','svg.hashsalt':'tehran-pairs-v1'})
    def save(fig,name):
        p=out/(name+'.svg');fig.savefig(p,bbox_inches='tight',metadata={'Date':None})
        p.write_bytes(b'\n'.join(line.rstrip() for line in p.read_bytes().splitlines())+b'\n')
        fig.savefig(preview/(name+'.png'),dpi=170,bbox_inches='tight');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(6.9,3.05),sharey=True)
    lookup={(r['max_line_changes'],r['walking_budget_m']):r for r in summary['results']}
    maximum=max(r[mode]['positive_pairs'] for r in summary['results'] for mode in ['bus','bus_metro'])
    for ax,mode,title in zip(axes,['bus','bus_metro'],['Without metro','With metro']):
        values=np.array([[lookup[k,w][mode]['positive_pairs'] for w in [500,1000,2000]] for k in [0,1,2]])
        im=ax.pcolormesh(np.arange(4)-.5,np.arange(4)-.5,values,cmap='Blues',vmin=0,vmax=maximum,rasterized=False)
        ax.set_ylim(2.5,-.5)
        for i in range(3):
            for j in range(3):ax.text(j,i,f'{values[i,j]:,}',ha='center',va='center',color='white' if values[i,j]>=maximum*.6 else '#202936',fontsize=9)
        ax.set(xticks=range(3),xticklabels=['500','1,000','2,000'],yticks=range(3),yticklabels=['0','1','2'],xlabel='Walking budget W (m)',title=title)
    axes[0].set_ylabel('Additional-boardings budget K')
    fig.subplots_adjust(top=.84,bottom=.22,left=.09,right=.82,wspace=.16)
    cax=fig.add_axes([.86,.22,.025,.62]);colorbar=fig.colorbar(im,cax=cax,label='Pairs with positive interaction')
    colorbar.locator=MaxNLocator(nbins=5,integer=True);colorbar.formatter=FuncFormatter(lambda x,p:f'{x:,.0f}');colorbar.update_ticks()
    colorbar.solids.set_rasterized(False)
    save(fig,'01-positive-pair-interaction')

    selected=[r for r in cases if r['mode']=='bus_metro' and r['max_line_changes']==1 and r['walking_budget_m']==1000]
    positive=max(selected,key=lambda r:r['interaction_buildings']);negative=min(selected,key=lambda r:r['interaction_buildings'])
    ymax=1.25*max(max(c['first_loss_buildings']+c['second_loss_buildings'],c['joint_loss_buildings']) for c in [positive,negative])
    fig,axes=plt.subplots(1,2,figsize=(6.9,3.1),sharey=True)
    for ax,case,title in zip(axes,[positive,negative],['(a) Positive interaction','(b) Negative interaction']):
        values=[case['first_loss_buildings'],case['second_loss_buildings'],case['joint_loss_buildings']]
        bars=ax.bar(range(3),values,color=['#A8AFBA','#667085','#0072B2'],width=.6)
        additive=values[0]+values[1]
        ax.axhline(additive,color='#D55E00',ls='--',lw=1,label='Sum of single losses')
        for rect,value in zip(bars,values):ax.text(rect.get_x()+rect.get_width()/2,value+ymax*.015,str(value),ha='center',va='bottom')
        ax.set(xticks=range(3),xticklabels=['First only','Second only','Both'],ylim=(0,ymax),title=title)
        ax.text(.04,.91,f"C = {case['interaction_buildings']:+d} buildings",transform=ax.transAxes,fontsize=9)
    axes[0].set_ylabel('Accessible building locations lost')
    axes[1].legend(loc='upper center',bbox_to_anchor=(.5,-.16),frameon=False,fontsize=8)
    fig.subplots_adjust(left=.10,right=.98,top=.86,bottom=.25,wspace=.16)
    save(fig,'02-pair-interaction-examples')
    data={'scope':f"Complete census of all {summary['evaluated_street_pairs']:,} distinct observed street pairs; no sampling",
          'positive_example':positive,'negative_example':negative,'results':summary['results']}
    (out/'figure-data.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    manifest={'script_sha256':sha(Path(__file__)),'source_sha256':{p.name:sha(p) for p in [source/'summary.json',source/'extreme-cases.json']},
        'output_sha256':{p.name:sha(p) for p in out.iterdir() if p.name!='manifest.json'}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    def table(headers,rows):
        return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])
    main_rows=[]
    chosen=lookup[1,1000]
    for field,label in [('negative_pairs','Negative-interaction pairs'),('zero_pairs','Zero-interaction pairs'),
                        ('positive_pairs','Positive-interaction pairs'),('minimum_interaction_buildings','Minimum C (buildings)'),
                        ('maximum_interaction_buildings','Maximum C (buildings)'),('mean_interaction_buildings','Mean C (buildings)'),
                        ('maximum_joint_loss_buildings','Maximum joint loss (buildings)')]:
        main_rows.append([label]+[f"{chosen[mode][field]:,.6f}" if field=='mean_interaction_buildings' else f"{chosen[mode][field]:,}" for mode in ['bus','bus_metro']])
    main_table=table(['Measure','Walking + bus','Walking + bus + metro'],main_rows)
    grid_rows=[]
    for row in summary['results']:
        for mode,label in [('bus','Bus'),('bus_metro','Bus + metro')]:
            values=row[mode]
            grid_rows.append([row['max_line_changes'],f"{row['walking_budget_m']:,}",label]+[f'{values[f]:,}' for f in ['negative_pairs','zero_pairs','positive_pairs','minimum_interaction_buildings','maximum_interaction_buildings','maximum_joint_loss_buildings']])
    grid_table=table(['K','W (m)','Mode','C < 0','C = 0','C > 0','Min C','Max C','Max joint loss'],grid_rows)
    audit=json.loads((source/'audit.json').read_text())
    assert audit['status']=='passed' and audit['evaluated_street_pairs']==summary['evaluated_street_pairs']
    replacements={'EXECUTION':f"The completed run used **{summary['workers']} worker processes** and took **{summary['elapsed_seconds']:.1f} seconds** on the local machine. All **{summary['union_scenarios_evaluated']:,} union scenarios** and **{summary['signature_pairs_evaluated']:,} signature pairs** are present; their weights sum to **{summary['evaluated_street_pairs']:,} physical pairs**. Runtime is descriptive, not a guaranteed performance bound.",
        'AUDIT':f"**Independent audit: passed.** Every physical pair was verified. All **{audit['effect_rows']:,} effect rows**, **{audit['signature_pairs']:,} signature pairs**, **{audit['union_scenarios']:,} union scenarios**, and **{audit['parameter_comparisons']} parameter/mode summaries** reconciled.",
        'MAIN':main_table,'GRID':grid_table,
        'EXAMPLES':f"In the full model at W=1,000 m and K=1, a maximum-interaction case has single losses **{positive['first_loss_buildings']:,}** and **{positive['second_loss_buildings']:,}**, joint loss **{positive['joint_loss_buildings']:,}**, and C = **{positive['interaction_buildings']:+,}** building locations (union ID **{positive['union_id']}**). A minimum-interaction case has single losses **{negative['first_loss_buildings']:,}** and **{negative['second_loss_buildings']:,}**, joint loss **{negative['joint_loss_buildings']:,}**, and C = **{negative['interaction_buildings']:+,}** (union ID **{negative['union_id']}**). Both are traceable in [extreme-cases.json](m4-pairs-exhaustive-2026-11-01/extreme-cases.json)."}
    def update(path,blocks):
        text=path.read_text(encoding='utf-8')
        for marker,value in blocks.items():
            begin='<!-- BEGIN '+marker+' -->';end='<!-- END '+marker+' -->'
            before,rest=text.split(begin,1);_,after=rest.split(end,1);text=before+begin+'\n'+value+'\n'+end+after
        path.write_text(text,encoding='utf-8',newline='\n')
    update(ROOT/'research/reports/paired-closures.en.md',replacements)
    update(ROOT/'research/reports/research-progress.en.md',{'PAIR_MAIN':main_table})
    print(json.dumps({'output':str(out),'svg_count':2}))


if __name__=='__main__':main()
