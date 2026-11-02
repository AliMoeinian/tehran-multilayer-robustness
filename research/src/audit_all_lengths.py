"""Read-only census of source-way lengths and every split source segment."""
import collections
import csv
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import sqlite3

import numpy as np
from pyproj import Transformer
import shapely

from .accessibility import ROOT


def run(network=None,output=None):
    out=output or ROOT/'research/reports/validation-2026-11-01';out.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((ROOT/'research/config/baseline.json').read_text())
    source=ROOT/'data/extracted'/cfg['dataset_id']/'tehran_audited_layers.gpkg'
    network=network or ROOT/'research/model/m2-v2/network.sqlite'
    db=sqlite3.connect(network.as_uri()+'?mode=ro',uri=True)
    src=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    project=Transformer.from_crs(4326,32639,always_xy=True)
    grouped=itertools.groupby(db.execute('select osm_way_id,u,v,length_m from walk_edges order by osm_way_id,edge_id'),lambda x:x[0])
    graph=iter(grouped);current=next(graph,None)
    failures=[];ways=0;segments=0;edges=0;zero_ways=0;source_rows=0;maximum_way=0.;maximum_segment=0.
    with gzip.open(out/'all-way-lengths.csv.gz','wt',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(['way_id','source_length_m','graph_length_m','absolute_difference_m','source_segments_checked','stored_edges_checked'])
        for wid,raw,blob in src.execute('select osm_id,attributes_json,geom from roads_context order by osm_id'):
            source_rows+=1;a=json.loads(raw)
            if not a['walk_candidate']:continue
            envelope={0:0,1:32,2:48,3:48,4:64}[(blob[3]>>1)&7]
            geometry=shapely.from_wkb(blob[8+envelope:]);xy=np.asarray(geometry.coords)
            x,y=project.transform(xy[:,0],xy[:,1]);coordinates=np.column_stack([x,y])
            lengths=[math.hypot(*(b-a)) for a,b in zip(coordinates,coordinates[1:])]
            original=shapely.LineString(coordinates).length
            if original==0:zero_ways+=1;continue
            while current is not None and current[0]<wid:
                failures.append({'way_id':current[0],'issue':'graph way not eligible in source'});list(current[1]);current=next(graph,None)
            rows=list(current[1]) if current is not None and current[0]==wid else []
            if current is not None and current[0]==wid:current=next(graph,None)
            if not rows:failures.append({'way_id':wid,'issue':'missing source way in graph'})
            pointer=0;nodes=a['node_ids'];way_segments=0
            if len(nodes)!=len(coordinates):raise ValueError('Source node/coordinate mismatch')
            for k,(first,second,length) in enumerate(zip(nodes,nodes[1:],lengths)):
                if length<=1e-7 and first==second:continue
                way_segments+=1;start=f'n{first}';end=f'n{second}';chain=[]
                while pointer<len(rows):
                    _,u,v,d=rows[pointer];pointer+=1;chain.append(d)
                    if u!=start:failures.append({'way_id':wid,'segment':k,'issue':'broken split chain','expected':start,'observed':u})
                    if not math.isfinite(d) or d<0:failures.append({'way_id':wid,'segment':k,'issue':'invalid graph length'})
                    if v==end:break
                    expected=f'w{wid}:{k}:{len(chain)}'
                    if v!=expected:failures.append({'way_id':wid,'segment':k,'issue':'unexpected interior split anchor','expected':expected,'observed':v})
                    start=v
                else:failures.append({'way_id':wid,'segment':k,'issue':'source segment endpoint not reached'})
                difference=abs(math.fsum(chain)-length);maximum_segment=max(maximum_segment,difference)
                if difference>1e-5:failures.append({'way_id':wid,'segment':k,'issue':'segment length discrepancy','absolute_difference_m':difference})
            if pointer!=len(rows):failures.append({'way_id':wid,'issue':'extra stored graph edges'})
            stored=math.fsum(r[3] for r in rows);difference=abs(stored-original)
            maximum_way=max(maximum_way,difference)
            if difference>1e-5:failures.append({'way_id':wid,'issue':'way length discrepancy','absolute_difference_m':difference})
            writer.writerow([wid,original,stored,difference,way_segments,len(rows)])
            ways+=1;segments+=way_segments;edges+=len(rows)
            if ways%25000==0:print('Length census ways',ways,flush=True)
    while current is not None:
        failures.append({'way_id':current[0],'issue':'extra graph way'});list(current[1]);current=next(graph,None)
    expected_edges=db.execute('select count(*) from walk_edges').fetchone()[0]
    expected_ways=db.execute('select count(distinct osm_way_id) from walk_edges').fetchone()[0]
    if edges!=expected_edges or ways!=expected_ways:failures.append({'issue':'global edge/way coverage discrepancy'})
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report={'status':'passed' if not failures else 'failed','scope':'every eligible source walking way, every source segment and every stored split edge',
        'source_road_rows_examined':source_rows,'walking_ways_checked':ways,'source_segments_checked':segments,
        'stored_edges_checked':edges,'zero_length_source_ways_excluded_by_builder':zero_ways,
        'absolute_tolerance_m':1e-5,'maximum_way_difference_m':maximum_way,'maximum_segment_difference_m':maximum_segment,
        'failure_count':len(failures),'failures':failures,'network_sha256':sha(network),'geopackage_sha256':sha(source),
        'all_way_table_sha256':sha(out/'all-way-lengths.csv.gz'),'source_code_sha256':sha(Path(__file__))}
    (out/'all-lengths.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2));db.close();src.close()
    if failures:raise AssertionError('Full length/topology census failed; inspect report')
    return report


if __name__=='__main__':run()
