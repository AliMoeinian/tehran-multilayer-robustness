import sys,pathlib,json,csv
sys.path.insert(0,'work/pylibs');import osmium
rows=[];hospnonpoly=[]
class H(osmium.SimpleHandler):
 def way(self,w):
  t=dict(w.tags);b=t.get('building') and t.get('building')!='no';hp=t.get('amenity')=='hospital' or t.get('healthcare')=='hospital'
  if not (b or hp):return
  if len(w.nodes)<4 or w.nodes[0].ref!=w.nodes[-1].ref:
   row={'osm_type':'w','osm_id':w.id,'node_count':len(w.nodes),'name':t.get('name',''),'reason':'not_closed_polygon' if len(w.nodes)>=4 else 'too_few_polygon_nodes'}
   if b:rows.append(row)
   if hp:hospnonpoly.append(row)
h=H();h.apply_file('outputs/dataset_candidate/tehran_context.osm.pbf')
p=pathlib.Path('outputs/tehran_dataset_v1');p.mkdir(exist_ok=True)
(p/'unclosed_area_tags.json').write_text(json.dumps({'building_ways':rows,'hospital_ways':hospnonpoly},ensure_ascii=False,indent=2),encoding='utf8');print('Unclosed building ways',len(rows),'hospital ways',len(hospnonpoly))
