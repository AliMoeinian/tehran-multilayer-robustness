import sys,pathlib,json,csv,collections,sqlite3,struct,math,re,difflib,hashlib
sys.path.insert(0,str(pathlib.Path('work/pylibs').resolve()))
import osmium,shapely,pyproj
from shapely.geometry import LineString,MultiLineString,Point,mapping
from shapely.ops import transform,nearest_points
R=pathlib.Path('outputs/tehran_dataset_v1');SRC=R/'tehran_context.osm.pbf';project=pyproj.Transformer.from_crs(4326,32639,always_xy=True).transform
city=shapely.geometry.shape(json.load(open('outputs/dataset_candidate/tehran_city_osm_boundary.geojson',encoding='utf8'))['features'][0]['geometry'])
class Rel(osmium.SimpleHandler):
 def __init__(self):super().__init__();self.rs={};self.needed=set()
 def relation(self,r):
  t=dict(r.tags)
  if t.get('type')=='route' and (t.get('route') in ('bus','subway') or r.id in (443301,7735261)):
   mem=[(m.type,m.ref,m.role) for m in r.members];self.rs[r.id]={'tags':t,'members':mem};self.needed.update(i for typ,i,role in mem if typ=='w')
a=Rel();a.apply_file(str(SRC))
class Geom(osmium.SimpleHandler):
 def __init__(self):super().__init__();self.ws={};self.ns={}
 def node(self,n):
  t=dict(n.tags)
  if t.get('highway')=='bus_stop' or t.get('public_transport') in ('platform','stop_position') or t.get('railway') in ('station','halt'):self.ns[n.id]={'tags':t,'xy':(n.location.lon,n.location.lat)}
 def way(self,w):
  if w.id in a.needed:self.ws[w.id]={'tags':dict(w.tags),'ns':[n.ref for n in w.nodes],'xy':[(n.lon,n.lat) for n in w.nodes]}
g=Geom();g.apply_file(str(SRC),locations=True,idx='flex_mem');print('Transit geometries loaded',len(g.ws),flush=True)
def stop(m):
 typ,i,role=m
 if 'inactive' in role:return False
 if role.startswith(('stop','platform')):return True
 t=g.ns.get(i,{}).get('tags',{}) if typ=='n' else g.ws.get(i,{}).get('tags',{})
 return t.get('highway') in ('bus_stop','platform') or t.get('public_transport') in ('platform','stop_position') or t.get('railway') in ('station','halt')
def orientations(w,mode,role):
 t=w['tags'];v=next((t[k] for k in ('oneway:bus','oneway:psv','oneway') if k in t),None) if mode=='bus' else t.get('oneway')
 if v in ('yes','1','true'):s=[1]
 elif v=='-1':s=[-1]
 elif v in ('no','0','false'):s=[1,-1]
 elif v is None:s=[1] if mode=='bus' and (t.get('junction')=='roundabout' or t.get('highway') in ('motorway','motorway_link')) else [1,-1]
 else:s=[]
 return [x for x in s if role not in ('forward','backward') or x==(1 if role=='forward' else -1)]
def ordered(seq,mode):
 states={None:[]}
 for wid,role in seq:
  w=g.ws[wid];ns=w['ns'];new={}
  for d in orientations(w,mode,role):
   start,end=(ns[0],ns[-1]) if d==1 else (ns[-1],ns[0])
   for prev,path in states.items():
    if prev is None or prev==start:new.setdefault(end,path+[(wid,d)])
  states=new
  if not states:return []
 return list(states.values())
def unique_chain_reorder(seq,mode):
 if not seq:return [],'empty'
 incidence=collections.defaultdict(list)
 for k,(wid,role) in enumerate(seq):
  ns=g.ws[wid]['ns']
  if ns[0]==ns[-1]:return [],'closed_way_requires_review'
  incidence[ns[0]].append(k);incidence[ns[-1]].append(k)
 if any(len(x)>2 for x in incidence.values()):return [],'branch_or_repeated_way_ambiguity'
 ends=[n for n,x in incidence.items() if len(x)==1]
 if len(ends)!=2:return [],'not_single_open_endpoint_chain'
 solutions=[]
 for start in ends:
  here=start;used=set();path=[];ok=True
  while len(used)<len(seq):
   opts=[k for k in incidence[here] if k not in used]
   if len(opts)!=1:ok=False;break
   k=opts[0];wid,role=seq[k];ns=g.ws[wid]['ns'];d=1 if ns[0]==here else -1
   if d not in orientations(g.ws[wid],mode,role):ok=False;break
   used.add(k);path.append((wid,d));here=ns[-1] if d==1 else ns[0]
  if ok:solutions.append(path)
 if len(solutions)==1:return solutions,'unique_chain_and_unique_direction'
 if len(solutions)>1:return [],'two_valid_directions_no_proven_anchor'
 return [],'no_complete_directed_endpoint_chain'
# Historical reference parsed using actual observed lon,lat values, not the blog's axis description.
refdb=sqlite3.connect('file:work/operator_reference/reference.sqlite?mode=ro',uri=True);refdb.row_factory=sqlite3.Row
refrows=[];ref_by_code=collections.defaultdict(list)
for r in refdb.execute('SELECT * FROM Routes'):
 r=dict(r);coords=[]
 try:
  for s in (r['Vertices'] or '').strip(';').split(';'):
   if s:
    x,y=map(float,s.split(','));assert 45<x<60 and 25<y<45;coords.append((x,y))
 except Exception:coords=[]
 if len(coords)>=2:
  r['geom']=LineString(coords);r['metric']=transform(project,r['geom']);ref_by_code[str(r['RouteCode'])].append(r);refrows.append(r)
ref_quality={'last_update':list(refdb.execute('SELECT * FROM LastUpdate').fetchone()),'route_count':refdb.execute('SELECT count(*) FROM Routes').fetchone()[0],'valid_route_geometries':len(refrows),'station_count':refdb.execute('SELECT count(*) FROM Stations').fetchone()[0],'route_station_count':refdb.execute('SELECT count(*) FROM RouteStations').fetchone()[0],'orphan_route_station_route_ids':refdb.execute('SELECT count(*) FROM RouteStations rs LEFT JOIN Routes r ON rs.RouteID=r.RouteID WHERE r.RouteID IS NULL').fetchone()[0],'orphan_route_station_station_codes':refdb.execute('SELECT count(*) FROM RouteStations rs LEFT JOIN Stations s ON rs.StationCode=s.StationCode WHERE s.StationCode IS NULL').fetchone()[0],'use':'historical supporting comparison only, not certified 2026 service truth','receipt':json.load(open('work/operator_reference/receipt.json'))}
refdb.close()
def norm(s):return re.sub(r'\s+',' ',(s or '').replace('ي','ی').replace('ك','ک').replace('\u200c',' ')).strip()
def similarity(a,b):return difflib.SequenceMatcher(None,norm(a),norm(b)).ratio()
def lineparts(seq):return [LineString(g.ws[i]['xy']) for i,role in seq if len(g.ws[i]['xy'])>=2]
db=sqlite3.connect(R/'tehran_audited_layers.gpkg')
def table(name,gt):
 db.execute(f'CREATE TABLE IF NOT EXISTS {name}(fid INTEGER PRIMARY KEY AUTOINCREMENT,osm_id INTEGER,status TEXT,attributes_json TEXT,geom BLOB)');db.execute(f'DELETE FROM {name}');db.execute('INSERT OR REPLACE INTO gpkg_contents(table_name,data_type,identifier,last_change,srs_id) VALUES(?,?,?,?,?)',(name,'features',name,'2026-10-30T00:00:00Z',4326));db.execute('INSERT OR REPLACE INTO gpkg_geometry_columns VALUES(?,?,?,?,?,?)',(name,'geom',gt,4326,0,0))
def put(tab,i,status,attrs,geom):
 x1,y1,x2,y2=geom.bounds;blob=b'GP'+bytes([0,3])+struct.pack('<i4d',4326,x1,x2,y1,y2)+shapely.to_wkb(geom,byte_order=1);db.execute(f'INSERT INTO {tab}(osm_id,status,attributes_json,geom) VALUES(?,?,?,?)',(i,status,json.dumps(attrs,ensure_ascii=False),blob))
table('transit_active_member_geometry','MULTILINESTRING');table('bus_reference_shapes_2024','LINESTRING');table('transit_gap_diagnostics','LINESTRING')
for r in refrows:put('bus_reference_shapes_2024',r['RouteID'],'historical_reference_not_2026_validation',{'route_code':r['RouteCode'],'from':r['OriginationName'],'to':r['DestinationName'],'last_update':'2024-05-14','source_url':ref_quality['receipt']['url']},r['geom'])
results=[];paths=[];repaired=[];comparison=[];gaps=[]
for ident,r in a.rs.items():
 t=r['tags'];mode='bus' if t.get('route')=='bus' else 'metro';seq=[];stops=[m for m in r['members'] if stop(m)];flags=[]
 children=[i for typ,i,role in r['members'] if typ=='r' and i in a.rs]
 for m in r['members']:
  typ,i,role=m
  if typ!='w' or 'inactive' in role or stop(m):continue
  w=g.ws.get(i)
  if not w:continue
  if mode=='bus' and not w['tags'].get('highway'):continue
  if mode=='metro' and w['tags'].get('railway') not in ('rail','subway','light_rail','tram','narrow_gauge'):continue
  seq.append((i,role))
  if role not in ('','forward','backward'):flags.append('nonstandard_line_member_role')
  if mode=='bus':
   mt=w['tags'];mv=next((mt[k] for k in ('bus','psv','motor_vehicle','vehicle','access') if k in mt),None)
   if mv in ('no','private'):flags.append('bus_access_tag_requires_review')
   if any(':conditional' in k for k in mt):flags.append('conditional_road_rule_not_evaluated')
 if t.get('fixme'):flags.append('source_fixme_present')
 lines=lineparts(seq);geom=MultiLineString(lines) if lines else None;in_city=geom is not None and city.intersects(geom)
 # connected components based on shared OSM node identifiers
 par={};waygroup={}
 def find(x):
  par.setdefault(x,x)
  while par[x]!=x:par[x]=par[par[x]];x=par[x]
  return x
 for wid,role in seq:
  ns=g.ws[wid]['ns'];root=find(ns[0])
  for n in ns[1:]:par[find(n)]=root
 comps=collections.defaultdict(list)
 for wid,role in seq:comps[find(g.ws[wid]['ns'][0])].append(wid)
 ncomp=len(comps)
 path_options=ordered(seq,mode) if seq else [];repair_reason='not_attempted';chosen=path_options[0] if path_options else None
 if not chosen and ncomp==1 and seq:
  opts,repair_reason=unique_chain_reorder(seq,mode)
  if opts:chosen=opts[0];repaired.append({'relation_id':ident,'method':repair_reason,'original_member_way_sequence':[i for i,role in seq],'derived_way_sequence':[i for i,d in chosen],'adds_or_removes_ways':False})
 if children:status='parent_container'
 elif not in_city:status='context_only'
 elif ncomp>1:status='member_geometry_components_need_review'
 elif not chosen:status='order_or_direction_needs_review'
 elif len(stops)<2:status='stop_semantics_need_review'
 elif flags:status='continuous_path_with_explicit_semantic_flags'
 else:status='continuous_ordered_path_screened'
 if chosen:
  for k,(wid,d) in enumerate(chosen):paths.append({'route_relation_id':ident,'sequence':k,'way_id':wid,'direction':d,'status':status,'method':'unique_chain_reorder' if any(x['relation_id']==ident for x in repaired) else 'OSM_member_order_with_orientation_resolution'})
 metrics={'relation_id':ident,'mode':mode,'osm_route_value':t.get('route'),'name':t.get('name',''),'ref':t.get('ref',''),'status':status,'member_components':ncomp,'identified_stop_platform_members':len(stops),'active_member_way_count':len(seq),'line_intersects_city':in_city,'repair_reason':repair_reason,'flags':';'.join(sorted(set(flags)))};results.append(metrics)
 if geom:put('transit_active_member_geometry',ident,status,{**metrics,'tags':t},geom)
 if mode=='bus' and geom:
  code=str(t.get('ref','')).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹','0123456789'));candidates=ref_by_code.get(code,[]);pm=transform(project,geom)
  if candidates:
   # Select reference direction primarily by recorded endpoint names, then median shape proximity; all scores retained.
   scored=[];sample=[]
   for line in pm.geoms:
    n=max(2,min(50,math.ceil(line.length/100)))
    sample.extend(line.interpolate(k/(n-1),normalized=True) for k in range(n))
   for ref in candidates:
    distances=sorted(p.distance(ref['metric']) for p in sample);med=distances[len(distances)//2];name_score=(similarity(t.get('from'),ref['OriginationName'])+similarity(t.get('to'),ref['DestinationName']))/2;scored.append((name_score,-med,ref,distances))
   name_score,_,ref,dist=max(scored,key=lambda x:(x[0],x[1]));comparison.append({'osm_relation_id':ident,'osm_ref':code,'reference_route_id':ref['RouteID'],'reference_from':ref['OriginationName'],'reference_to':ref['DestinationName'],'endpoint_name_similarity':name_score,'sample_count':len(dist),'median_distance_m':dist[len(dist)//2],'p95_distance_m':dist[min(len(dist)-1,int(.95*len(dist)))],'fraction_within_50m':sum(d<=50 for d in dist)/len(dist),'fraction_within_100m':sum(d<=100 for d in dist)/len(dist),'reference_year':2024,'comparison_status':'historical_agreement_metrics_not_current_truth'})
  else:comparison.append({'osm_relation_id':ident,'osm_ref':code,'comparison_status':'no_exact_route_code_in_2024_reference'})
 # Gap locations: nearest distance between components. Diagnostic straight lines are not added to routing network.
 if ncomp>1 and len(comps)<=25:
  cg=[MultiLineString([LineString(g.ws[w]['xy']) for w in ids if len(g.ws[w]['xy'])>=2]) for ids in comps.values()];visited={0}
  while len(visited)<len(cg):
   choices=[(cg[x].distance(cg[y]),x,y) for x in visited for y in range(len(cg)) if y not in visited];_,x,y=min(choices);p1,p2=nearest_points(cg[x],cg[y]);diagnostic=LineString([p1,p2]);length=transform(project,diagnostic).length
   gap={'route_relation_id':ident,'from_component':x,'to_component':y,'gap_euclidean_m':length,'not_a_route_edge':True};gaps.append(gap);put('transit_gap_diagnostics',ident,'diagnostic_only_not_traversable',gap,diagnostic);visited.add(y)
 print('',end='')
def csvout(name,rows):
 keys=list(dict.fromkeys(k for row in rows for k in row))
 with open(R/name,'w',encoding='utf-8-sig',newline='') as f:
  if keys:
   w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
for name,rows in [('transit_reviewed_inventory.csv',results),('transit_derived_ordered_paths.csv',paths),('bus_reference_comparison_2024.csv',comparison),('transit_gap_diagnostics.csv',gaps)]:csvout(name,rows)
(R/'transit_reordering_log.json').write_text(json.dumps(repaired,ensure_ascii=False,indent=2),encoding='utf8');(R/'historical_reference_quality.json').write_text(json.dumps(ref_quality,ensure_ascii=False,indent=2),encoding='utf8')
for tab in ['transit_active_member_geometry','bus_reference_shapes_2024','transit_gap_diagnostics']:
 bs=[struct.unpack('<4d',row[0][8:40]) for row in db.execute(f'SELECT geom FROM {tab}')];b=(min(x[0] for x in bs),min(x[2] for x in bs),max(x[1] for x in bs),max(x[3] for x in bs)) if bs else (None,None,None,None);db.execute('UPDATE gpkg_contents SET min_x=?,min_y=?,max_x=?,max_y=? WHERE table_name=?',(*b,tab))
db.commit();db.close()
summary={'routes':{m:dict(collections.Counter(x['status'] for x in results if x['mode']==m)) for m in ('bus','metro')},'deterministically_reordered_relations':len(repaired),'historical_comparisons_with_exact_code':sum('reference_route_id' in x for x in comparison),'historical_comparisons_without_exact_code':sum('reference_route_id' not in x for x in comparison),'gap_diagnostic_links':len(gaps),'reference_quality':{k:v for k,v in ref_quality.items() if k!='receipt'},'line5_included':all(i in a.rs for i in (443301,7735261))}
(R/'transit_review_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
