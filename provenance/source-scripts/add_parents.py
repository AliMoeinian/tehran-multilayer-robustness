import sys,pathlib,json
sys.path.insert(0,'work/pylibs')
import osmium
root=pathlib.Path('outputs/dataset_candidate');src='work/iran_source/iran-source.osm.pbf';p=root/'tehran_context.osm.pbf'
class Ids(osmium.SimpleHandler):
 def __init__(self):super().__init__();self.ids=set()
 def relation(self,r):self.ids.add(r.id)
i=Ids();i.apply_file(str(p))
class Rs(osmium.SimpleHandler):
 def __init__(self):super().__init__();self.rs={}
 def relation(self,r):
  if (r.tags.get('type')=='route' and r.tags.get('route') in ('bus','subway')) or (r.tags.get('type')=='route_master' and r.tags.get('route_master') in ('bus','subway')):
   self.rs[r.id]=r.replace(tags=dict(r.tags),members=[(m.type,m.ref,m.role) for m in r.members])
r=Rs();r.apply_file(src);selected=set(i.ids);changed=True
while changed:
 changed=False
 for ident,obj in r.rs.items():
  if ident not in selected and any(m[0]=='r' and m[1] in selected for m in obj.members):selected.add(ident);changed=True
extras=sorted(selected-i.ids);print('Additional parent relations',extras,flush=True)
with osmium.BackReferenceWriter(str(root/'tehran_complete.osm.pbf'),src,overwrite=True,remove_tags=False,relation_depth=5) as writer:
 class Copy(osmium.SimpleHandler):
  def __init__(self):super().__init__();self.k=0
  def node(self,n):writer.add_node(n)
  def way(self,w):writer.add_way(w)
  def relation(self,rel):
   while self.k<len(extras) and extras[self.k]<rel.id:writer.add_relation(r.rs[extras[self.k]]);self.k+=1
   writer.add_relation(rel)
 c=Copy();c.apply_file(str(p))
 while c.k<len(extras):writer.add_relation(r.rs[extras[c.k]]);c.k+=1
p.replace('work/initial_context.osm.pbf');(root/'tehran_complete.osm.pbf').replace(p)
d=json.load(open(root/'extraction_receipt.json',encoding='utf8'));d['added_upward_route_parent_ids']=extras;d['selection_rule']+='; upward bus/subway route and route_master relation closure, then backward completion again';(root/'extraction_receipt.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8');print('Parent completion finished',flush=True)
