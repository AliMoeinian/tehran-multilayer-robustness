"""Complete district, component, route-overlap and target-group descriptions."""
import collections
import csv
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import re as regex
import sqlite3

import numpy as np
import osmium
import shapely
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

from .accessibility import ROOT,load_model
from .full_graph_reference import walking_csr,relax,solve_full
from .pair_closures import write_gzip_csv
from .sensitivity_runs import gp_geometry
from .structural_centrality import OUT,MODEL,sha


def run():
    OUT.mkdir(exist_ok=True);m=load_model(ROOT/'research/model/m2-v2/network.sqlite',ROOT/'research/config/baseline.json')
    cfg=m.cfg;source=ROOT/'data/extracted'/cfg['dataset_id'];db=sqlite3.connect((source/'tehran_audited_layers.gpkg').as_uri()+'?mode=ro',uri=True)
    polygons={int(i):gp_geometry(blob) for i,blob in db.execute('select osm_id,geom from municipal_districts')}
    class Admin(osmium.SimpleHandler):
        def __init__(self):super().__init__();self.tags={}
        def relation(self,r):
            if r.id in polygons:self.tags[r.id]=dict(r.tags)
    admin=Admin();admin.apply_file(str(source/'tehran_context.osm.pbf'))
    refs={rid:int(tags.get('ref') or regex.search(r'\d+',tags['name']).group()) for rid,tags in admin.tags.items()}
    assert set(refs.values())==set(range(1,23))
    origins=[r for r in m.connectors.values() if r[1]=='building'];assert len(origins)==65677
    metadata={f'building:{typ}{ident}':json.loads(raw) for typ,ident,raw in db.execute('select osm_type,osm_id,attributes_json from buildings_city')}
    assert set(metadata)=={r[0] for r in origins}
    points=shapely.points(np.array([[metadata[r[0]]['point_lon'],metadata[r[0]]['point_lat']] for r in origins]))
    district_ids=sorted(polygons,key=lambda rid:(refs[rid],rid));tree=shapely.STRtree([polygons[rid] for rid in district_ids])
    matches=tree.query(points,predicate='covered_by');owners=np.zeros(len(origins),np.int64);match_count=np.zeros(len(origins),np.int64)
    for i,j in matches.T:
        ref=refs[district_ids[j]];match_count[i]+=1
        if owners[i]==0 or ref<owners[i]:owners[i]=ref
    denominator=np.bincount(owners,minlength=23);assert denominator.sum()==65677
    anchors=np.array([m.node_ids[r[3]] if r[5]=='geometric_candidate' else 0 for r in origins],np.int64)
    access=np.array([r[4] if r[5]=='geometric_candidate' else np.inf for r in origins]);eligible=np.isfinite(access)
    write_gzip_csv(OUT/'building-district-ownership.csv.gz',['origin','district','covering_district_polygons','connector_accepted','point_lon','point_lat','footprint_district_relation_ids'],
        [(r[0],int(owners[i]),int(match_count[i]),bool(eligible[i]),metadata[r[0]]['point_lon'],metadata[r[0]]['point_lat'],json.dumps(metadata[r[0]]['district_relation_ids'],separators=(',',':'))) for i,r in enumerate(origins)])
    (OUT/'district-index.json').write_text(json.dumps({'districts':[{'district':refs[rid],'relation_id':rid,'recorded_name':admin.tags[rid]['name']} for rid in district_ids],
        'unassigned_code':0,'ambiguous_points':int((match_count>1).sum()),'unassigned_origins':int(denominator[0]),
        'rule':'Stored representative point covered by district polygon; lowest district number then relation ID resolves any overlap. Number comes from source ref or recorded source name.'},indent=2)+'\n',encoding='utf-8',newline='\n')
    print('All district assignments',denominator.tolist(),flush=True)
    ptr,neighbor,length=walking_csr(m.adjacency);n=len(m.adjacency);m.adjacency=[]
    sa=np.array([s.anchor for s in m.stops],np.int64);sc=np.array([s.access_m for s in m.stops])
    start=np.array([m.stop_ids[a] for key,a,b,mode in m.ride_rows],np.int64);end=np.array([m.stop_ids[b] for key,a,b,mode in m.ride_rows],np.int64)
    mode_arrays={}
    for mode,allowed in [('bus',{'bus'}),('bus_metro',{'bus','metro'})]:
        active=np.array([m.stop_modes[k] in allowed for k in m.stop_keys]);rides=np.array([md in allowed for key,a,b,md in m.ride_rows])
        mode_arrays[mode]=(np.array([s.board for s in m.stops])&active,np.array([s.alight for s in m.stops])&active,start[rides],end[rides])
    targets=[r for r in m.connectors.values() if r[1]=='hospital' and r[5]=='geometric_candidate']
    tn=np.array([m.node_ids[r[3]] for r in targets],np.int64);tc=np.array([r[4] for r in targets])
    groups=sorted({r[2] for r in targets});assert len(groups)==236
    group_masks={};group_counts=np.zeros((2,4,3,len(origins)),np.uint16);group_coverage=[]
    zero=relax(ptr,neighbor,length,np.full(n,np.inf),tn,tc,2000.)
    base={mode:solve_full(ptr,neighbor,length,sa,sc,*arrays,zero,3,2000.,anchors,access) for mode,arrays in mode_arrays.items()}
    # Per-mode full-node output and every aggregate threshold must reproduce M3.
    published=json.loads((ROOT/'research/reports/m3-2026-11-01-summary.json').read_text())
    expected={(r['mode'],r['max_line_changes'],r['walking_budget_m']):r['accessible_buildings'] for r in published['results']}
    for mode,values in base.items():
        for k in [0,1,2]:
            for w in [500,1000,2000]:assert int(np.count_nonzero(values[k+1]<=w))==expected[mode,k,w]
    for gi,group in enumerate(groups):
        selected=np.array([r[2]==group for r in targets]);walking=relax(ptr,neighbor,length,np.full(n,np.inf),tn[selected],tc[selected],2000.)
        for md,(mode,arrays) in enumerate(mode_arrays.items()):
            values=solve_full(ptr,neighbor,length,sa,sc,*arrays,walking,3,2000.,anchors,access)
            for b in range(4):
                for j,w in enumerate([500,1000,2000]):
                    found=values[b]<=w;group_counts[md,b,j]+=found
                    group_masks[f'g{gi}_{mode}_b{b}_w{w}']=np.packbits(found,bitorder='little')
                    group_coverage.append((group,mode,b,w,int(found.sum()),int(selected.sum())))
        if (gi+1)%10==0:print('All-target-group census',gi+1,'/',len(groups),flush=True)
    for md,mode in enumerate(mode_arrays):
        for b in range(4):
            for j,w in enumerate([500,1000,2000]):assert np.array_equal(group_counts[md,b,j]>0,base[mode][b]<=w)
    assert np.all(group_counts[1]>=group_counts[0]) and np.all(group_counts[:,1:]>=group_counts[:,:-1]) and np.all(group_counts[:,:,1:]>=group_counts[:,:,:-1])
    assert not group_counts[:,:,:,~eligible].any()
    np.savez_compressed(OUT/'hospital-group-reachability-masks.npz',**group_masks)
    origin_digest=hashlib.sha256(json.dumps([r[0] for r in origins],separators=(',',':')).encode()).hexdigest()
    (OUT/'target-group-mask-index.json').write_text(json.dumps({'groups':groups,'origin_order':'building-district-ownership.csv.gz row order','origin_id_order_sha256':origin_digest,'origin_count':len(origins),'bitorder':'little','boarding_layers':[0,1,2,3],'walking_budgets_m':[500,1000,2000]},indent=2)+'\n',encoding='utf-8',newline='\n')
    write_gzip_csv(OUT/'target-group-coverage.csv.gz',['group','mode','max_boardings','walking_budget_m','accessible_origins','candidate_features'],group_coverage)
    headers=['origin','district']+[f'{mode}_b{b}_w{w}' for mode in mode_arrays for b in range(4) for w in [500,1000,2000]]
    write_gzip_csv(OUT/'building-reachable-target-groups.csv.gz',headers,[(r[0],int(owners[i]),*map(int,group_counts[:,:,:,i].ravel())) for i,r in enumerate(origins)])
    district_rows=[]
    for district in range(23):
        own=owners==district
        for md,mode in enumerate(mode_arrays):
            for k in [0,1,2]:
                for j,w in enumerate([500,1000,2000]):
                    values=group_counts[md,k+1,j,own];accessible=int(np.count_nonzero(values))
                    district_rows.append((district,mode,k,w,int(own.sum()),int((eligible&own).sum()),accessible,accessible/int(own.sum()) if own.any() else None,
                        float(values.mean()) if len(values) else None,int(values.max()) if len(values) else None))
    write_gzip_csv(OUT/'district-baseline.csv.gz',['district','mode','max_line_changes','walking_budget_m','buildings','connected_buildings','accessible_buildings','share_all_buildings','mean_reachable_candidate_groups','maximum_reachable_candidate_groups'],district_rows)
    single=ROOT/'research/reports/m3-single-closures-2026-11-01';old_index=json.loads((ROOT/'research/reports/sensitivity-2026-11-01/mask-index.json').read_text())
    where={r[0]:i for i,r in enumerate(origins)};connected_owner=np.array([owners[where[key]] for key in old_index['origins']])
    with (single/'effects.csv').open(newline='') as f:effects={(r['signature'],int(r['max_line_changes']),int(r['walking_budget_m'])):r for r in csv.DictReader(f)}
    loss_rows=[];summary_acc=collections.defaultdict(lambda:[0,0,0])
    with np.load(ROOT/'research/reports/sensitivity-2026-11-01/single-loss-masks.npz') as masks:
        for group in old_index['groups']:
            for mode in mode_arrays:
                for k in [0,1,2]:
                    for w in [500,1000,2000]:
                        row=effects[group['signature'],k,w];multiplicity=int(row['street_count'])
                        lost=np.unpackbits(masks[f"g{group['group_index']}_{mode}_k{k}_w{w}"],bitorder='little')[:len(connected_owner)]
                        bydistrict=np.bincount(connected_owner,weights=lost,minlength=23).astype(int)
                        assert int(bydistrict.sum())==int(row[mode+'_loss_buildings'])
                        for district,value in enumerate(bydistrict):
                            loss_rows.append((group['signature'],multiplicity,district,mode,k,w,int(value)))
                            acc=summary_acc[district,mode,k,w];acc[0]+=multiplicity*int(value);acc[1]=max(acc[1],int(value));acc[2]+=multiplicity*int(value>0)
    write_gzip_csv(OUT/'district-single-losses.csv.gz',['signature','street_count','district','mode','max_line_changes','walking_budget_m','lost_buildings'],loss_rows)
    write_gzip_csv(OUT/'district-loss-summary.csv.gz',['district','mode','max_line_changes','walking_budget_m','buildings','mean_loss_over_1684_streets','maximum_single_loss','positive_loss_streets','maximum_loss_share_all_buildings'],
        [(district,mode,k,w,int(denominator[district]),a/1684,b,c,b/int(denominator[district]) if denominator[district] else None) for (district,mode,k,w),(a,b,c) in sorted(summary_acc.items())])
    # Unbudgeted graph components are descriptions, not accessibility measures.
    walk_nodes=np.repeat(np.arange(n),np.diff(ptr));component_rows=[];component_summary=[]
    target_groups=[r[2] for r in targets]
    for mode in ['walk','bus','bus_metro']:
        if mode=='walk':a=walk_nodes;c=neighbor;size=n
        else:
            board,alight,rs,re=mode_arrays[mode];active=np.array([m.stop_modes[key] in ({'bus'} if mode=='bus' else {'bus','metro'}) for key in m.stop_keys])
            selected=np.flatnonzero(active);mapping=np.full(len(active),-1,np.int64);mapping[selected]=np.arange(len(selected))+n
            a=np.r_[walk_nodes,sa[board],mapping[np.flatnonzero(alight)],mapping[rs]]
            c=np.r_[neighbor,mapping[np.flatnonzero(board)],sa[alight],mapping[re]];size=n+len(selected)
        matrix=csr_matrix((np.ones(len(a)),(a,c)),shape=(size,size))
        for connection in ['weak','strong']:
            number,labels=connected_components(matrix,directed=True,connection=connection)
            nc=np.bincount(labels,minlength=number);oc=np.bincount(labels[anchors[eligible]],minlength=number)
            tc_count=np.bincount(labels[tn],minlength=number);group_pairs=set(zip(labels[tn],target_groups));gc=collections.Counter(v for v,key in group_pairs)
            for i in range(number):component_rows.append((mode,connection,i,int(nc[i]),int(oc[i]),int(tc_count[i]),gc[i]))
            component_summary.append({'mode':mode,'connectivity':connection,'vertices':size,'directed_arcs':int(matrix.nnz),'components':number,'largest_component_vertices':int(nc.max()),'components_with_connected_origins':int(np.count_nonzero(oc))})
    write_gzip_csv(OUT/'model-components.csv.gz',['mode','connectivity','component','vertices','connected_buildings','target_candidate_features','possible_target_groups'],component_rows)
    db.close()
    report={'status':'passed','all_buildings':len(origins),'all_districts':22,'unassigned_origins':int(denominator[0]),'ambiguous_district_points':int((match_count>1).sum()),
        'candidate_groups_checked':len(groups),'candidate_features':len(targets),'all_group_union_thresholds_match_baseline':True,
        'mask_count':len(group_masks),'single_district_effect_rows':len(loss_rows),'all_single_losses_reconcile':True,'components':component_summary,
        'network_sha256':m.network_hash,'source_code_sha256':sha(Path(__file__))}
    report['artifact_sha256']={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and (p.name.startswith(('building-','district-','target-group-','hospital-group-','model-components')))}
    (OUT/'descriptive-summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report),flush=True)


if __name__=='__main__':run()
