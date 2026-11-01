"""Render the frozen sampled-pair results as static, editable-text SVG figures."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .accessibility import ROOT


def main():
    source=ROOT/'research/reports/m4-pairs-2026-11-01'
    out=ROOT/'research/figures/pairs-2026-11-01';out.mkdir(parents=True,exist_ok=True)
    preview=ROOT/'research/runs/pair-figure-preview';preview.mkdir(parents=True,exist_ok=True)
    summary=json.loads((source/'summary.json').read_text());cases=json.loads((source/'extreme-cases.json').read_text())
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':10,
        'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#89919C',
        'axes.linewidth':.6,'svg.fonttype':'none','svg.hashsalt':'tehran-pairs-v1'})
    def save(fig,name):
        p=out/(name+'.svg');fig.savefig(p,bbox_inches='tight',metadata={'Date':None})
        p.write_bytes(b'\n'.join(line.rstrip() for line in p.read_bytes().splitlines())+b'\n')
        fig.savefig(preview/(name+'.png'),dpi=170,bbox_inches='tight');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(6.9,3.05),sharey=True)
    lookup={(r['max_line_changes'],r['walking_budget_m']):r for r in summary['results']}
    for ax,mode,title in zip(axes,['bus','bus_metro'],['Without metro','With metro']):
        values=np.array([[lookup[k,w][mode]['positive_pairs'] for w in [500,1000,2000]] for k in [0,1,2]])
        im=ax.pcolormesh(np.arange(4)-.5,np.arange(4)-.5,values,cmap='Blues',vmin=0,vmax=10,rasterized=False)
        ax.set_ylim(2.5,-.5)
        for i in range(3):
            for j in range(3):ax.text(j,i,str(values[i,j]),ha='center',va='center',color='white' if values[i,j]>=6 else '#202936',fontsize=11)
        ax.set(xticks=range(3),xticklabels=['500','1,000','2,000'],yticks=range(3),yticklabels=['0','1','2'],xlabel='Walking budget W (m)',title=title)
    axes[0].set_ylabel('Additional-boardings budget K')
    fig.subplots_adjust(top=.84,bottom=.22,left=.09,right=.82,wspace=.16)
    cax=fig.add_axes([.86,.22,.025,.62]);colorbar=fig.colorbar(im,cax=cax,ticks=[0,2,4,6,8,10],label='Pairs with positive interaction / 512')
    colorbar.solids.set_rasterized(False)
    save(fig,'01-positive-pair-interaction')

    selected=[r for r in cases if r['mode']=='bus_metro' and r['max_line_changes']==1 and r['walking_budget_m']==1000]
    positive=max(selected,key=lambda r:r['interaction_buildings']);negative=min(selected,key=lambda r:r['interaction_buildings'])
    fig,axes=plt.subplots(1,2,figsize=(6.9,3.1),sharey=True)
    for ax,case,title in zip(axes,[positive,negative],['(a) Positive interaction','(b) Negative interaction']):
        values=[case['first_loss_buildings'],case['second_loss_buildings'],case['joint_loss_buildings']]
        bars=ax.bar(range(3),values,color=['#A8AFBA','#667085','#0072B2'],width=.6)
        additive=values[0]+values[1]
        ax.axhline(additive,color='#D55E00',ls='--',lw=1,label='Sum of single losses')
        for rect,value in zip(bars,values):ax.text(rect.get_x()+rect.get_width()/2,value+4,str(value),ha='center',va='bottom')
        ax.set(xticks=range(3),xticklabels=['First only','Second only','Both'],ylim=(0,285),title=title)
        ax.text(.04,.91,f"C = {case['interaction_buildings']:+d} buildings",transform=ax.transAxes,fontsize=9)
    axes[0].set_ylabel('Accessible building locations lost')
    axes[1].legend(loc='upper center',bbox_to_anchor=(.5,-.16),frameon=False,fontsize=8)
    fig.subplots_adjust(left=.10,right=.98,top=.86,bottom=.25,wspace=.16)
    save(fig,'02-pair-interaction-examples')
    data={'scope':'512 uniformly sampled distinct street pairs, seed 20261101; figures are not exhaustive-domain estimates',
          'positive_example':positive,'negative_example':negative,'results':summary['results']}
    (out/'figure-data.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    manifest={'script_sha256':sha(Path(__file__)),'source_sha256':{p.name:sha(p) for p in [source/'summary.json',source/'extreme-cases.json']},
        'output_sha256':{p.name:sha(p) for p in out.iterdir() if p.name!='manifest.json'}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'output':str(out),'svg_count':2}))


if __name__=='__main__':main()
