import sys,pathlib,json,csv,collections,math,sqlite3,struct,hashlib,datetime,gzip
sys.path.insert(0,str(pathlib.Path('work/pylibs').resolve()))
import osmium,shapely,pyproj
from shapely.geometry import shape,Point,LineString,mapping
from shapely.ops import transform
from shapely.strtree import STRtree
from shapely.validation import explain_validity
ROOT=pathlib.Path('outputs/tehran_dataset_v1');ROOT.mkdir(exist_ok=True)
SRC=pathlib.Path('outputs/dataset_candidate/tehran_context.osm.pbf')
city=shape(json.load(open('outputs/dataset_candidate/tehran_city_osm_boundary.geojson',encoding='utf8'))['features'][0]['geometry'])
districts=[(f['properties']['osm_relation_id'],shape(f['geometry'])) for f in json.load(open('outputs/dataset_candidate/tehran_22_districts_osm.geojson',encoding='utf8'))['features']]
project=pyproj.Transformer.from_crs(4326,32639,always_xy=True).transform;citym=transform(project,city);dm=[(i,transform(project,g)) for i,g in districts]
known_highway={'motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary','tertiary_link','residential','living_street','unclassified','service','road','track','footway','path','steps','pedestrian','cycleway','bridleway','busway','bus_guideway','corridor','elevator','construction','proposed','platform','bus_stop','services','rest_area','emergency_access_point','raceway'}
drive_types={'motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary','tertiary_link','residential','living_street','unclassified','service','road'}
walk_types={'primary','primary_link','secondary','secondary_link','tertiary','tertiary_link','residential','living_street','unclassified','service','road','track','footway','path','steps','pedestrian','corridor'}
def denied(t,mode):
 keys={'drive':['motorcar','motor_vehicle','vehicle','access'],'walk':['foot','access'],'bus':['bus','psv','motor_vehicle','vehicle','access']}[mode]
 for k in keys:
  if k in t:return t[k] in ('no','private')
 return False
def oneway(t,mode='drive'):
 keys=['oneway:bus','oneway:psv','oneway'] if mode=='bus' else ['oneway:motorcar','oneway:motor_vehicle','oneway']
 v=next((t[k] for k in keys if k in t),None)
 if v in ('yes','1','true'):return [1]
 if v=='-1':return [-1]
 if v in ('no','0','false'):return [1,-1]
 if v is None:return [1] if t.get('junction')=='roundabout' or t.get('highway') in ('motorway','motorway_link') else [1,-1]
 return []
class H(osmium.SimpleHandler):
 def __init__(self):super().__init__();self.ways={};self.points={};self.rels={};self.buildings=[];self.hosp=[];self.area_errors=[];self.fac=osmium.geom.GeoJSONFactory()
 def node(self,n):
  t=dict(n.tags)
  if t.get('amenity')=='hospital' or t.get('healthcare')=='hospital' or t.get('highway')=='bus_stop' or t.get('public_transport') in ('platform','stop_position') or t.get('railway') in ('station','halt','subway_entrance'):
   self.points[n.id]={'tags':t,'xy':(n.location.lon,n.location.lat)}
   if t.get('amenity')=='hospital' or t.get('healthcare')=='hospital':self.hosp.append({'osm_type':'n','osm_id':n.id,'tags':t,'geometry':Point(n.location.lon,n.location.lat)})
 def way(self,w):
  t=dict(w.tags)
  if t.get('highway') or t.get('railway') or t.get('public_transport')=='platform':
   self.ways[w.id]={'tags':t,'nodes':[n.ref for n in w.nodes],'xy':[(n.lon,n.lat) for n in w.nodes]}
 def relation(self,r):self.rels[r.id]={'tags':dict(r.tags),'members':[(m.type,m.ref,m.role) for m in r.members]}
 def area(self,a):
  t=dict(a.tags);b=t.get('building') and t.get('building')!='no';hospital=t.get('amenity')=='hospital' or t.get('healthcare')=='hospital'
  if not (b or hospital):return
  typ='w' if a.from_way() else 'r';ident=a.orig_id()
  try:g=shape(json.loads(self.fac.create_multipolygon(a)))
  except Exception as e:self.area_errors.append({'osm_type':typ,'osm_id':ident,'error':str(e),'building':bool(b),'hospital':hospital});return
  row={'osm_type':typ,'osm_id':ident,'tags':t,'geometry':g}
  if b:self.buildings.append(row)
  if hospital:self.hosp.append(row)
h=H();h.apply_file(str(SRC),locations=True,idx='flex_mem');print('Read geometry',len(h.ways),len(h.buildings),len(h.hosp),flush=True)
# GeoPackage storing inspected geometry and JSON attributes; intentionally no fabricated connections.
gpkg=ROOT/'tehran_audited_layers.gpkg'
if gpkg.exists():gpkg.unlink()
db=sqlite3.connect(gpkg);db.executescript('PRAGMA application_id=1196444487; PRAGMA user_version=10300; CREATE TABLE gpkg_spatial_ref_sys(srs_name TEXT NOT NULL,srs_id INTEGER NOT NULL PRIMARY KEY,organization TEXT NOT NULL,organization_coordsys_id INTEGER NOT NULL,definition TEXT NOT NULL,description TEXT); CREATE TABLE gpkg_contents(table_name TEXT NOT NULL PRIMARY KEY,data_type TEXT NOT NULL,identifier TEXT UNIQUE,description TEXT DEFAULT "",last_change DATETIME NOT NULL,min_x DOUBLE,min_y DOUBLE,max_x DOUBLE,max_y DOUBLE,srs_id INTEGER); CREATE TABLE gpkg_geometry_columns(table_name TEXT NOT NULL,column_name TEXT NOT NULL,geometry_type_name TEXT NOT NULL,srs_id INTEGER NOT NULL,z TINYINT NOT NULL,m TINYINT NOT NULL,PRIMARY KEY(table_name,column_name));')
for sid,name,org,definition in [(-1,'Undefined Cartesian','NONE','undefined'),(0,'Undefined Geographic','NONE','undefined'),(4326,'WGS 84','EPSG',pyproj.CRS(4326).to_wkt(version='WKT1_GDAL'))]:db.execute('INSERT INTO gpkg_spatial_ref_sys VALUES(?,?,?,?,?,?)',(name,sid,org,sid,definition,''))
now=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
def table(name,geomtype='GEOMETRY'):
 db.execute(f'CREATE TABLE {name}(fid INTEGER PRIMARY KEY AUTOINCREMENT,osm_type TEXT,osm_id INTEGER,status TEXT,attributes_json TEXT,geom BLOB)');db.execute('INSERT INTO gpkg_contents(table_name,data_type,identifier,last_change,srs_id) VALUES(?,?,?,?,?)',(name,'features',name,now,4326));db.execute('INSERT INTO gpkg_geometry_columns VALUES(?,?,?,?,?,?)',(name,'geom',geomtype,4326,0,0))
def put(tab,typ,ident,status,attrs,g):
 blob=None
 if g is not None and not g.is_empty:
  x1,y1,x2,y2=g.bounds;blob=b'GP'+bytes([0,3])+struct.pack('<i4d',4326,x1,x2,y1,y2)+shapely.to_wkb(g,byte_order=1)
 db.execute(f'INSERT INTO {tab}(osm_type,osm_id,status,attributes_json,geom) VALUES(?,?,?,?,?)',(typ,ident,status,json.dumps(attrs,ensure_ascii=False),blob))
for name,gt in [('city_boundary','MULTIPOLYGON'),('municipal_districts','MULTIPOLYGON'),('roads_context','LINESTRING'),('buildings_city','MULTIPOLYGON'),('hospital_candidates','GEOMETRY')]:table(name,gt)
put('city_boundary','r',6663864,'OSM_boundary_not_officially_verified',{},city)
for i,g in districts:put('municipal_districts','r',i,'valid_OSM_geometry',{},g)
# Road quality and weak connectivity for explicit generic passenger-car candidate filter.
parent={};sizes={}
def find(x):
 while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
 return x
def union(a,b):
 for x in (a,b):
  if x not in parent:parent[x]=x;sizes[x]=1
 a=find(a);b=find(b)
 if a!=b:
  if sizes[a]<sizes[b]:a,b=b,a
  parent[b]=a;sizes[a]+=sizes[b]
road_rows=[];walkgeoms=[];walkids=[];drivegeoms=[];driveids=[]
for i,w in h.ways.items():
 t=w['tags'];hw=t.get('highway')
 if not hw:continue
 flags=[];xy=w['xy'];g=LineString(xy) if len(xy)>1 else None
 if hw not in known_highway:flags.append('unrecognized_highway_value')
 if g is None or g.is_empty or g.length==0:flags.append('degenerate_geometry')
 if t.get('area')=='yes':flags.append('area_not_linear_road')
 ow=oneway(t)
 if not ow:flags.append('unrecognized_oneway_value')
 if any(':conditional' in k for k in t):flags.append('conditional_tags_require_scenario')
 drive=hw in drive_types and not denied(t,'drive') and t.get('area')!='yes' and g is not None and g.length>0 and bool(ow)
 walk=(hw in walk_types or t.get('foot') in ('yes','designated','permissive')) and not denied(t,'walk') and t.get('area')!='yes' and g is not None and g.length>0
 if drive:
  for a,b in zip(w['nodes'],w['nodes'][1:]):union(a,b)
 if drive or walk:
  gm=transform(project,g)
  if walk:walkgeoms.append(gm);walkids.append(i)
  if drive:drivegeoms.append(gm);driveids.append(i)
 road_rows.append({'osm_way_id':i,'highway':hw,'drive_candidate':drive,'walk_candidate':walk,'oneway_orientations':';'.join(map(str,ow)),'flags':';'.join(flags),'node_count':len(w['nodes'])})
 put('roads_context','w',i,'flagged' if flags else 'raw_tags_screened',{'tags':t,'flags':flags,'drive_candidate':drive,'walk_candidate':walk,'node_ids':w['nodes']},g)
components=collections.Counter(find(x) for x in parent);largest=max(components,key=components.get) if components else None
for r in road_rows:
 w=h.ways[r['osm_way_id']];r['weak_component_nodes']=components[find(w['nodes'][0])] if r['drive_candidate'] else '';r['largest_weak_component']=find(w['nodes'][0])==largest if r['drive_candidate'] else ''
print('Roads screened',len(road_rows),flush=True)
# Buildings: prefer relation representation over its outer/inner way members; deduplicate identical footprint geometry.
building_rel_members={m[1] for r in h.rels.values() if r['tags'].get('building') not in (None,'no') for m in r['members'] if m[0]=='w' and m[2] in ('outer','inner','')}
walktree=STRtree(walkgeoms);drivetree=STRtree(drivegeoms);seenfoot={};building_rows=[];building_issues=[]
for b in sorted(h.buildings,key=lambda x:0 if x['osm_type']=='r' else 1):
 typ,i,t,g=b['osm_type'],b['osm_id'],b['tags'],b['geometry']
 if typ=='w' and i in building_rel_members:building_issues.append({'osm_type':typ,'osm_id':i,'reason':'relation_member_duplicate_representation'});continue
 if not g.is_valid or g.is_empty:building_issues.append({'osm_type':typ,'osm_id':i,'reason':'invalid_geometry','detail':explain_validity(g)});continue
 key=shapely.normalize(g).wkb
 if key in seenfoot:building_issues.append({'osm_type':typ,'osm_id':i,'reason':'identical_footprint','retained':seenfoot[key]});continue
 seenfoot[key]=f'{typ}{i}';gm=transform(project,g)
 if not gm.intersects(citym):continue
 ratio=gm.intersection(citym).area/gm.area if gm.area else 0
 inside=ratio>.5 or (abs(ratio-.5)<1e-12 and citym.covers(gm.representative_point()))
 if not inside:continue
 pt=g.representative_point();pm=transform(project,pt);did=[di for di,dg in dm if dg.covers(pm)];wi=int(walktree.nearest(pm));di=int(drivetree.nearest(pm));wd=pm.distance(walkgeoms[wi]);dd=pm.distance(drivegeoms[di]);attrs={'tags':t,'inside_area_fraction':ratio,'boundary_crossing':ratio<1-1e-9,'district_relation_ids':did,'point_lon':pt.x,'point_lat':pt.y,'nearest_walk_way':walkids[wi],'nearest_walk_distance_m':wd,'nearest_drive_way':driveids[di],'nearest_drive_distance_m':dd,'connector_status':'geometric_candidate_only_no_barrier_or_entrance_validation','demand_weight':1,'weight_meaning':'building_count_not_population'}
 building_rows.append({'osm_type':typ,'osm_id':i,'inside_area_fraction':ratio,'boundary_crossing':attrs['boundary_crossing'],'district_relation_ids':';'.join(map(str,did)),'nearest_walk_distance_m':wd,'nearest_drive_distance_m':dd,'connector_status':attrs['connector_status']})
 put('buildings_city',typ,i,'selected_by_majority_area',attrs,g)
print('Buildings selected',len(building_rows),flush=True)
# Hospital node/campus representation grouping without inferring real service eligibility.
hosp_polys=[x for x in h.hosp if x['osm_type']!='n' and x['geometry'].is_valid];hospital_rows=[];hsp_issues=[]
for x in h.hosp:
 typ,i,t,g=x['osm_type'],x['osm_id'],x['tags'],x['geometry'];flags=[]
 if not g.is_valid:flags.append('invalid_geometry')
 containers=[p for p in hosp_polys if typ=='n' and p['geometry'].covers(g)]
 if len(containers)==1:group=f"{containers[0]['osm_type']}{containers[0]['osm_id']}";flags.append('node_inside_hospital_campus_possible_duplicate')
 else:group=f'{typ}{i}'
 if len(containers)>1:flags.append('ambiguous_multiple_campuses')
 point=g.representative_point();pm=transform(project,point);nid=int(drivetree.nearest(pm));attrs={'tags':t,'candidate_group_id':group,'inside_city_representative_point':city.covers(point),'emergency_tag':t.get('emergency','unknown'),'service_verification':'not_externally_verified','entrance_verification':'not_verified','nearest_drive_way':driveids[nid],'nearest_drive_distance_m':pm.distance(drivegeoms[nid]),'flags':flags}
 hospital_rows.append({'osm_type':typ,'osm_id':i,'name':t.get('name',''),'group_id':group,'inside_city':attrs['inside_city_representative_point'],'emergency_tag':attrs['emergency_tag'],'nearest_drive_distance_m':attrs['nearest_drive_distance_m'],'flags':';'.join(flags),'service_verification':'not_externally_verified'})
 put('hospital_candidates',typ,i,'candidate_not_verified_emergency',attrs,g)
# Non-geometric hospital relations need explicit accounting.
geom_hosp={(x['osm_type'],x['osm_id']) for x in h.hosp}
for i,r in h.rels.items():
 if (r['tags'].get('amenity')=='hospital' or r['tags'].get('healthcare')=='hospital') and ('r',i) not in geom_hosp:hsp_issues.append({'osm_type':'r','osm_id':i,'reason':'hospital_relation_without_assembled_area','tags':r['tags']})
# Transit: differentiate parent containers, active line ways, legacy stops, strict order and direction screening.
routes=[];paths=[];dependency=[];transit_issues=[]
def is_stop(typ,ident,role):
 if 'inactive' in role:return False
 if role.startswith(('stop','platform')):return True
 t=h.points.get(ident,{}).get('tags',{}) if typ=='n' else h.ways.get(ident,{}).get('tags',{}) if typ=='w' else h.rels.get(ident,{}).get('tags',{})
 return t.get('highway') in ('bus_stop','platform') or t.get('public_transport') in ('stop_position','platform','stop_area') or t.get('railway') in ('station','halt')
for ident,r in h.rels.items():
 t=r['tags'];mode=t.get('route')
 if t.get('type')!='route' or mode not in ('bus','subway'):continue
 children=[m[1] for m in r['members'] if m[0]=='r' and h.rels.get(m[1],{}).get('tags',{}).get('type')=='route'];stops=[m for m in r['members'] if is_stop(*m)];seq=[];flags=[]
 for typ,i,role in r['members']:
  if typ!='w' or 'inactive' in role or is_stop(typ,i,role):continue
  w=h.ways.get(i)
  if w is None:flags.append('nontransport_way_member');continue
  wt=w['tags']
  if mode=='bus' and not wt.get('highway'):flags.append('nonhighway_line_member');continue
  if mode=='subway' and wt.get('railway') not in ('rail','subway','light_rail','tram','narrow_gauge'):flags.append('nonrail_line_member');continue
  seq.append((i,role))
  if mode=='bus':dependency.append({'route_relation_id':ident,'member_sequence':len(seq)-1,'way_id':i,'role':role,'active_member':True})
 # components of line geometry: all shared node IDs, no geometric crossing inference.
 par={}
 def rf(x):
  par.setdefault(x,x)
  while par[x]!=x:par[x]=par[par[x]];x=par[x]
  return x
 for wid,role in seq:
  ns=h.ways[wid]['nodes']
  if ns:
   a=rf(ns[0])
   for n in ns[1:]:b=rf(n);par[b]=a
 ncomp=len({rf(n) for n in par});geoincity=any(city.intersects(LineString(h.ways[wid]['xy'])) for wid,role in seq if len(h.ways[wid]['xy'])>1)
 stop_city=sum(typ=='n' and i in h.points and city.covers(Point(h.points[i]['xy'])) for typ,i,role in stops)
 states={None:[]}
 for wid,role in seq:
  w=h.ways[wid];ns=w['nodes'];allowed=oneway(w['tags'],'bus') if mode=='bus' else ([1] if w['tags'].get('oneway') in ('yes','1') else [-1] if w['tags'].get('oneway')=='-1' else [1,-1])
  if role=='forward':allowed=[a for a in allowed if a==1]
  if role=='backward':allowed=[a for a in allowed if a==-1]
  new={}
  if ns:
   for direction in allowed:
    a,b=(ns[0],ns[-1]) if direction==1 else (ns[-1],ns[0])
    for prev,path in states.items():
     if prev is None or prev==a:new.setdefault(b,path+[(wid,direction)])
  states=new
  if not states:break
 oriented=next(iter(states.values()),None) if seq else None
 if children:status='parent_container_not_independent_trip'
 elif not geoincity and not stop_city:status='context_only_outside_city'
 elif not seq:status='quarantine_no_active_line_geometry'
 elif ncomp!=1:status='quarantine_disconnected_member_geometry'
 elif oriented is None:status='quarantine_order_or_direction_unresolved'
 elif len(stops)<2:status='quarantine_insufficient_identified_stops'
 elif flags:status='quarantine_member_semantics'
 else:status='passes_structural_screen_only'
 if mode=='bus' and any(any(':conditional' in k for k in h.ways[wid]['tags']) for wid,role in seq):flags.append('conditional_road_tags_not_evaluated')
 row={'relation_id':ident,'mode':mode,'name':t.get('name',''),'ref':t.get('ref',''),'public_transport_version':t.get('public_transport:version','legacy_or_unspecified'),'status':status,'active_way_members':len(seq),'unique_active_ways':len({wid for wid,role in seq}),'line_components':ncomp,'identified_stop_platform_members':len(stops),'stop_node_members_inside_city':stop_city,'line_intersects_city':geoincity,'child_route_relations':';'.join(map(str,children)),'flags':';'.join(sorted(set(flags)))};routes.append(row)
 if status=='passes_structural_screen_only':
  for order,(wid,direction) in enumerate(oriented):paths.append({'route_relation_id':ident,'sequence':order,'way_id':wid,'direction':direction})
 if status.startswith('quarantine'):transit_issues.append(row)
# Restrictions: validate member shape and via connectivity. Conditional/mode-specific cases remain explicit.
restr=[];supported=[]
for ident,r in h.rels.items():
 t=r['tags']
 if t.get('type')!='restriction':continue
 fr=[m for m in r['members'] if m[2]=='from'];to=[m for m in r['members'] if m[2]=='to'];via=[m for m in r['members'] if m[2]=='via'];flags=[];status=''
 cond=any(':conditional' in k for k in t);special=any(k.startswith('restriction:') and k!='restriction:conditional' for k in t) or bool(t.get('except'))
 if len(fr)!=1 or len(to)!=1 or len(via)!=1 or fr[0][0]!='w' or to[0][0]!='w':status='quarantine_complex_member_schema'
 elif via[0][0]!='n':status='quarantine_via_way_needs_state_model'
 else:
  v=via[0][1];fw=h.ways.get(fr[0][1]);tw=h.ways.get(to[0][1]);kind=t.get('restriction','')
  if fw is None or tw is None:status='quarantine_nontransport_member'
  elif v not in fw['nodes'] or v not in tw['nodes']:status='quarantine_via_not_shared'
  elif kind not in ('no_left_turn','no_right_turn','no_straight_on','no_u_turn','only_left_turn','only_right_turn','only_straight_on','only_u_turn'):status='quarantine_unrecognized_or_mode_specific_kind'
  elif cond or special:status='quarantine_conditional_or_mode_exception'
  else:status='passes_via_node_structural_screen';supported.append({'relation_id':ident,'from_way':fr[0][1],'via_node':v,'to_way':to[0][1],'restriction':kind})
 row={'relation_id':ident,'restriction':t.get('restriction',''),'status':status,'tags_json':json.dumps(t,ensure_ascii=False),'members_json':json.dumps(r['members'])};restr.append(row)
# Save inspectable registries.
def csvout(name,rows):
 with (ROOT/name).open('w',encoding='utf-8-sig',newline='') as f:
  if rows:
   writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
for name,rows in [('road_inventory.csv',road_rows),('buildings_city.csv',building_rows),('building_exceptions.csv',building_issues),('hospital_candidates.csv',hospital_rows),('transit_routes.csv',routes),('transit_quarantine.csv',transit_issues),('bus_road_dependencies.csv',dependency),('transit_ordered_paths_screened.csv',paths),('turn_restrictions.csv',restr),('turn_restrictions_via_node_screened.csv',supported)]:csvout(name,rows)
# Keep all geometry failures including features the area assembler could not produce.
(ROOT/'geometry_and_hospital_exceptions.json').write_text(json.dumps({'area_factory_errors':h.area_errors,'hospital_nonarea_relations':hsp_issues},ensure_ascii=False,indent=2),encoding='utf8')
for table_name in ['city_boundary','municipal_districts','roads_context','buildings_city','hospital_candidates']:
 # bounds may be conservative; all features lie within the stored context objects.
 bounds=[struct.unpack('<4d',row[0][8:40]) for row in db.execute(f'SELECT geom FROM {table_name} WHERE geom IS NOT NULL')]; bounds=(min(b[0] for b in bounds),min(b[2] for b in bounds),max(b[1] for b in bounds),max(b[3] for b in bounds)) if bounds else (None,None,None,None); db.execute('UPDATE gpkg_contents SET min_x=?,min_y=?,max_x=?,max_y=? WHERE table_name=?',(*bounds,table_name))
db.commit();print('SQLite integrity',db.execute('PRAGMA integrity_check').fetchone()[0],flush=True);db.close()
summary={'source_pbf_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),'transit_status_by_mode':{m:dict(collections.Counter(r['status'] for r in routes if r['mode']==m)) for m in ('bus','subway')},'transit_relations':len(routes),'restriction_status':dict(collections.Counter(r['status'] for r in restr)),'road_count':len(road_rows),'road_flag_counts':dict(collections.Counter(flag for r in road_rows for flag in r['flags'].split(';') if flag)),'drive_candidate_weak_components':len(components),'drive_candidate_nodes':len(parent),'largest_drive_weak_component_nodes':components[largest] if largest else 0,'building_geometry_candidates':len(h.buildings),'buildings_selected_city':len(building_rows),'building_exceptions':len(building_issues),'buildings_crossing_city_boundary':sum(r['boundary_crossing'] for r in building_rows),'buildings_without_unique_district':sum(len(r['district_relation_ids'].split(';'))!=1 or not r['district_relation_ids'] for r in building_rows),'building_walk_candidate_distance_over_100m':sum(r['nearest_walk_distance_m']>100 for r in building_rows),'hospital_features':len(hospital_rows),'hospital_candidate_groups':len({r['group_id'] for r in hospital_rows}),'hospital_emergency_yes_features':sum(r['emergency_tag']=='yes' for r in hospital_rows),'hospital_emergency_unknown_features':sum(r['emergency_tag']=='unknown' for r in hospital_rows),'nonarea_hospital_relations':len(hsp_issues),'area_factory_errors':len(h.area_errors),'created_utc':now,'limitations':['Structural screens are not real-world service verification.','No turn-aware routing graph, boarding/alighting validation or barrier-aware connectors are certified.','Weak components ignore direction and turn restrictions; disconnected components retained.','Hospital features are candidates; emergency eligibility is not externally verified.','Road oneway candidate rules and mode access rules are documented screening choices, not a complete routing profile.','50% building-area rule is a study convention; alternate boundary sensitivity remains analysis work.']}
(ROOT/'final_audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
