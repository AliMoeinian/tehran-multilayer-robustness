import sys,pathlib,json,collections,datetime,hashlib
sys.path.insert(0,str(pathlib.Path('work/pylibs').resolve()))
import osmium
BASE=pathlib.Path('work/iran_source/iran-source.osm.pbf')
OUT=pathlib.Path('outputs/dataset_candidate');OUT.mkdir(exist_ok=True)
old=json.load(open('outputs/transit_reference_audit.json',encoding='utf8'))
missing={(m[0],m[1]) for r in old['routes'] for m in r['missing']};missing.add(('w',180404359))
city_ids={6663864,*json.load(open('outputs/boundary_audit.json',encoding='utf8'))['district_check']['ids']}
excluded={12948648,12948649,12948650,12948655,12952689,12952691,12952692,12952693}
class Extract(osmium.SimpleHandler):
 def __init__(self,w):super().__init__();self.writer=w;self.nodes=set();self.ways=set();self.count=collections.Counter();self.found_missing=set();self.rels=[];self.seenrel=set()
 def node(self,n):
  if ('n',n.id) in missing:self.found_missing.add(('n',n.id))
  if 50.9<=n.location.lon<=51.95 and 35.4<=n.location.lat<=36.05:
   self.nodes.add(n.id);self.writer.add_node(n);self.count['seed_nodes']+=1
 def way(self,w):
  if ('w',w.id) in missing:self.found_missing.add(('w',w.id))
  if any(n.ref in self.nodes for n in w.nodes):self.ways.add(w.id);self.writer.add_way(w);self.count['seed_ways']+=1
 def relation(self,r):
  typ=r.tags.get('type');mode=r.tags.get('route');touch=any((m.type=='w' and m.ref in self.ways) or (m.type=='n' and m.ref in self.nodes) for m in r.members)
  keep=r.id in city_ids or (touch and typ in ('restriction','multipolygon')) or (touch and typ=='route' and mode in ('bus','subway') and r.id not in excluded)
  if r.id in {x['id'] for x in old['routes'] if x['missing']} or r.id==10342457:
   self.rels.append({'id':r.id,'tags':dict(r.tags),'version':r.version,'timestamp':str(r.timestamp),'members':[(m.type,m.ref,m.role) for m in r.members]})
  if keep:self.writer.add_relation(r);self.count['seed_relations']+=1
hdr=osmium.io.Reader(str(BASE)).header()
print('Source timestamp',hdr.get('osmosis_replication_timestamp'),flush=True)
with osmium.BackReferenceWriter(str(OUT/'tehran_context.osm.pbf'),str(BASE),overwrite=True,remove_tags=False,relation_depth=5) as writer:
 h=Extract(writer);h.apply_file(str(BASE));print('Seed pass complete',dict(h.count),flush=True)
res={'source_timestamp':hdr.get('osmosis_replication_timestamp'),'selection_bbox':[50.9,35.4,51.95,36.05],'selection_rule':'all nodes in bbox, ways with >=1 such node; touching multipolygons and restrictions; touching bus/subway routes except 8 named intercity routes; city+22 districts; backward reference completion depth 5; referenced tags retained','seed_counts':dict(h.count),'missing_objects_in_original_distinct':len(missing),'recovered_in_source':len(h.found_missing),'still_absent_in_source':sorted(missing-h.found_missing),'original_problem_relations_from_new_source':h.rels,'excluded_intercity_relation_ids':sorted(excluded)}
(OUT/'extraction_receipt.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf8');print('Extract written',flush=True)
