import sys,pathlib,json
sys.path.insert(0,'work/pylibs');import osmium
class H(osmium.SimpleHandler):
 def __init__(self):super().__init__();self.tagged={};self.assembled=set()
 def way(self,w):
  if w.tags.get('building') not in (None,'no'):self.tagged[('w',w.id)]={'osm_type':'w','osm_id':w.id,'closed':len(w.nodes)>=4 and w.nodes[0].ref==w.nodes[-1].ref,'nodes':len(w.nodes)}
 def relation(self,r):
  if r.tags.get('building') not in (None,'no'):self.tagged[('r',r.id)]={'osm_type':'r','osm_id':r.id,'relation_type':r.tags.get('type')}
 def area(self,a):
  if a.tags.get('building') not in (None,'no'):self.assembled.add(('w' if a.from_way() else 'r',a.orig_id()))
h=H();h.apply_file('outputs/tehran_dataset_v1/tehran_context.osm.pbf',locations=True,idx='flex_mem');d={'tagged_building_objects':len(h.tagged),'assembled_building_objects':len(h.assembled),'not_assembled':[h.tagged[k] for k in sorted(set(h.tagged)-h.assembled)]};pathlib.Path('outputs/tehran_dataset_v1/building_assembly_audit.json').write_text(json.dumps(d,indent=2),encoding='utf8');print(json.dumps(d))
