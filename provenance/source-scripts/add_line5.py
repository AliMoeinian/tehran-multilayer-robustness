import sys,pathlib,json
sys.path.insert(0,'work/pylibs');import osmium
root=pathlib.Path('outputs/tehran_dataset_v1');root.mkdir(exist_ok=True)
ids={443301,7735261,7735262};extras={}
class Source(osmium.SimpleHandler):
 def relation(self,r):
  if r.id in ids:extras[r.id]=r.replace(tags=dict(r.tags),members=[(m.type,m.ref,m.role) for m in r.members])
s=Source();s.apply_file('work/iran_source/iran-source.osm.pbf');assert set(extras)==ids
class Existing(osmium.SimpleHandler):
 def __init__(self):super().__init__();self.ids=set()
 def relation(self,r):self.ids.add(r.id)
e=Existing();e.apply_file('outputs/dataset_candidate/tehran_context.osm.pbf');todo=sorted(ids-e.ids)
with osmium.BackReferenceWriter(str(root/'tehran_context.osm.pbf'),'work/iran_source/iran-source.osm.pbf',overwrite=True,remove_tags=False,relation_depth=5) as writer:
 class Copy(osmium.SimpleHandler):
  def __init__(self):super().__init__();self.k=0
  def node(self,n):writer.add_node(n)
  def way(self,w):writer.add_way(w)
  def relation(self,r):
   while self.k<len(todo) and todo[self.k]<r.id:writer.add_relation(extras[todo[self.k]]);self.k+=1
   writer.add_relation(r)
 c=Copy();c.apply_file('outputs/dataset_candidate/tehran_context.osm.pbf')
 while c.k<len(todo):writer.add_relation(extras[todo[c.k]]);c.k+=1
(root/'line5_addition.json').write_text(json.dumps({'added_relation_ids':todo,'source':'same Geofabrik Iran snapshot 2026-10-29T21:21:26Z','selection_reason':'Tehran Metro Line 5 is route=train, not route=subway; both directions and route_master retained','tags':{i:dict(x.tags) for i,x in extras.items()}},ensure_ascii=False,indent=2),encoding='utf8');print('Added line5',todo,flush=True)
