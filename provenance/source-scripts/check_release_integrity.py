import sys,pathlib,json,collections,hashlib
sys.path.insert(0,'work/pylibs');import osmium
p=pathlib.Path('outputs/tehran_dataset_v1/tehran_context.osm.pbf')
class H(osmium.SimpleHandler):
 def __init__(self):super().__init__();self.ids={'n':set(),'w':set(),'r':set()};self.c=collections.Counter();self.missingways=[];self.rels=[];self.duplicates=[];self.last=(-1,-1);self.order_errors=0
 def check(self,typ,i):
  key=({'n':0,'w':1,'r':2}[typ],i)
  if key<self.last:self.order_errors+=1
  self.last=key
  if i in self.ids[typ]:self.duplicates.append([typ,i])
  self.ids[typ].add(i);self.c[typ]+=1
 def node(self,n):self.check('n',n.id)
 def way(self,w):
  self.check('w',w.id);missing=[n.ref for n in w.nodes if n.ref not in self.ids['n']]
  if missing:self.missingways.append([w.id,missing])
  if w.tags.get('highway'):self.c['highway_ways']+=1
 def relation(self,r):
  self.check('r',r.id);self.rels.append((r.id,[(m.type,m.ref,m.role) for m in r.members]))
h=H();h.apply_file(str(p));mr=[{'id':i,'missing':[(t,k,role) for t,k,role in mem if k not in h.ids[t]]} for i,mem in h.rels];mr=[r for r in mr if r['missing']]
d={'counts':dict(h.c),'duplicate_ids':h.duplicates,'ordering_errors':h.order_errors,'ways_with_missing_nodes':len(h.missingways),'relations_with_missing_members':len(mr),'way_issues':h.missingways,'relation_issues':mr,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
(p.parent/'reference_integrity.json').write_text(json.dumps(d,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in d.items() if k not in ('way_issues','relation_issues')}))
