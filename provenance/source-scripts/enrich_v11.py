"""Read-only source enrichment. No missing road segments are invented."""
import pathlib,sqlite3,json,csv,collections,math,re,difflib,shutil,datetime,struct,hashlib,sys
sys.path.insert(0,str(pathlib.Path('work/pylibs').resolve()))
import shapely,numpy as np,pyproj
from shapely.geometry import Point,LineString,shape
from shapely.ops import transform
BASE=pathlib.Path('outputs/tehran_dataset_v1');OUT=pathlib.Path('outputs/tehran_dataset_v1_1');OUT.mkdir(exist_ok=True)
for p in BASE.iterdir():
 if p.is_file() and p.name not in ('manifest.json','README_fa.md','QUALITY_REPORT_fa.md','verify_release.ipynb'):
  shutil.copy2(p,OUT/p.name)
(OUT/'baseline_audit').mkdir(exist_ok=True)
for name in ['manifest.json','README_fa.md','QUALITY_REPORT_fa.md','final_audit_summary.json']:
 shutil.copy2(BASE/name,OUT/'baseline_audit'/name)
(OUT/'sources').mkdir(exist_ok=True);shutil.copy2('work/operator_reference/reference.sqlite',OUT/'sources/irantracking_20240514.sqlite')
if pathlib.Path('outputs/irantracking_recheck/live_recheck.json').exists():shutil.copy2('outputs/irantracking_recheck/live_recheck.json',OUT/'sources/irantracking_live_recheck.json')
now=datetime.datetime.now(datetime.timezone.utc).isoformat();pr=pyproj.Transformer.from_crs(4326,32639,always_xy=True).transform
city=shape(json.load(open(BASE/'tehran_city_osm_boundary.geojson',encoding='utf8'))['features'][0]['geometry'])
def dump(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def csvout(name,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with open(OUT/name,'w',encoding='utf-8-sig',newline='') as f:
  if keys:w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)
def readcsv(name):return list(csv.DictReader(open(BASE/name,encoding='utf-8-sig')))
def geom(b):return shapely.from_wkb(b[40:])
def norm(s):return re.sub(r'\s+',' ',(s or '').replace('ي','ی').replace('ك','ک').replace('\u200c',' ')).strip()
def sim(a,b):return difflib.SequenceMatcher(None,norm(a),norm(b)).ratio() if a and b else 0.
def codes(x):return {s.strip() for s in x.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹','0123456789')).split(';') if s.strip()}
db=sqlite3.connect(OUT/'tehran_audited_layers.gpkg');db.row_factory=sqlite3.Row
def table(name,gt):
 db.execute(f'DROP TABLE IF EXISTS {name}');db.execute(f'CREATE TABLE {name}(fid INTEGER PRIMARY KEY AUTOINCREMENT,source_id TEXT,status TEXT,attributes_json TEXT,geom BLOB)')
 db.execute('INSERT OR REPLACE INTO gpkg_contents(table_name,data_type,identifier,last_change,srs_id) VALUES(?,?,?,?,?)',(name,'features',name,now,4326))
 db.execute('INSERT OR REPLACE INTO gpkg_geometry_columns VALUES(?,?,?,?,?,?)',(name,'geom',gt,4326,0,0))
def put(tab,key,status,attrs,g):
 x1,y1,x2,y2=g.bounds;b=b'GP'+bytes([0,3])+struct.pack('<i4d',4326,x1,x2,y1,y2)+shapely.to_wkb(g,byte_order=1)
 db.execute(f'INSERT INTO {tab}(source_id,status,attributes_json,geom) VALUES(?,?,?,?)',(str(key),status,json.dumps(attrs,ensure_ascii=False),b))
ref=sqlite3.connect('file:work/operator_reference/reference.sqlite?mode=ro',uri=True);ref.row_factory=sqlite3.Row
stations={r['StationCode']:dict(r) for r in ref.execute('SELECT * FROM Stations')};rstop=collections.defaultdict(list)
for r in ref.execute('SELECT * FROM RouteStations ORDER BY RouteID,StationOrder,StationCode'):rstop[r['RouteID']].append(dict(r))
refs={};bycode=collections.defaultdict(list)
for row in ref.execute('SELECT * FROM Routes'):
 r=dict(row);pts=[tuple(map(float,s.split(','))) for s in r['Vertices'].strip(';').split(';') if s]
 assert all(45<x<60 and 25<y<45 for x,y in pts)
 r['geom']=LineString(pts);r['metric']=transform(pr,r['geom']);refs[r['RouteID']]=r;bycode[str(r['RouteCode'])].append(r)
table('historical_bus_stops_2024','POINT');table('historical_route_stops_2024','POINT')
srows=[];rsrows=[];rqa=[]
for sid,s in stations.items():
 p=Point(s['Longitude'],s['Latitude']);assert p.is_valid and 45<p.x<60 and 25<p.y<45
 row={**s,'source_date':'2024-05-14','inside_city_point':city.covers(p),'context_bbox':50.9<=p.x<=51.95 and 35.4<=p.y<=36.05,'current_operation_verified':False}
 srows.append(row);put('historical_bus_stops_2024',sid,'historical_not_current_service',row,p)
for rid,r in refs.items():
 rows=rstop[rid];orders=[s['StationOrder'] for s in rows];dist=[];progress=[]
 for s in rows:
  st=stations[s['StationCode']];p=Point(st['Longitude'],st['Latitude']);pm=transform(pr,p);dd=pm.distance(r['metric']);along=r['metric'].project(pm);dist.append(dd);progress.append(along)
  row={**s,'route_code':r['RouteCode'],'station_name':st['StationName'],'longitude':p.x,'latitude':p.y,'distance_to_historical_shape_m':dd,'shape_projection_m':along,'source_date':'2024-05-14'}
  rsrows.append(row);put('historical_route_stops_2024',f'{rid}:{s["StationCode"]}','source_order_not_boarding_validation',row,p)
 delta=np.diff(progress);direction=1 if np.median(delta)>=0 else -1;back=int(sum(delta*direction < -100))
 flags=[]
 if len(orders)!=len(set(orders)):flags.append('duplicate_station_order')
 if orders and orders!=list(range(min(orders),max(orders)+1)):flags.append('source_station_order_has_gap')
 if sum(s['IsLastStation']==1 for s in rows)!=1 or (rows and rows[-1]['IsLastStation']!=1):flags.append('terminal_marker_not_unique_at_last_order')
 if dist and max(dist)>100:flags.append('station_more_than_100m_from_source_shape')
 if back:flags.append('projection_has_backtracking_or_loop_ambiguity')
 rqa.append({'reference_route_id':rid,'route_code':r['RouteCode'],'direction_raw':r['Direction'],'from':r['OriginationName'],'to':r['DestinationName'],'station_count':len(rows),'line_intersects_city':city.intersects(r['geom']),'shape_length_m':r['metric'].length,'station_shape_p95_m':float(np.quantile(dist,.95)) if dist else None,'station_shape_max_m':max(dist) if dist else None,'shape_progress_direction':direction,'projection_backtracks_over_100m':back,'flags':';'.join(flags),'source_date':'2024-05-14'})
csvout('historical_bus_stations_2024.csv',srows);csvout('historical_bus_route_stations_2024.csv',rsrows);csvout('historical_bus_route_quality_2024.csv',rqa)
print('Historical route/station export complete',len(rsrows),flush=True)
# Same-code candidates are compared in both geometric directions. Alias tokens are kept.
def sample(g,spacing=150,cap=400):
 parts=list(g.geoms) if hasattr(g,'geoms') else [g];length=sum(p.length for p in parts);step=max(spacing,length/cap);pts=[]
 for p in parts:
  count=max(2,int(math.ceil(p.length/step))+1);pts.extend(p.interpolate(j/(count-1),normalized=True) for j in range(count))
 return pts
def distances(points,g):return np.asarray(shapely.distance(points,g),dtype=float)
paths=collections.defaultdict(list)
for row in readcsv('transit_paths.csv'):paths[int(row['route_relation_id'])].append(row)
ends={}
# Endpoint coordinates of already derived paths; no street is added or reordered here.
needed={int(x['way_id']) for ss in paths.values() for x in (ss[0],ss[-1])};wayends={}
for batch in [list(needed)[i:i+500] for i in range(0,len(needed),500)]:
 for w,b in db.execute('SELECT osm_id,geom FROM roads_context WHERE osm_id IN ('+','.join('?' for _ in batch)+')',batch):
  coords=list(geom(b).coords);wayends[w]=(coords[0],coords[-1])
for rid,ss in paths.items():
 ss.sort(key=lambda x:int(x['sequence']));f,l=ss[0],ss[-1];fw,lw=int(f['way_id']),int(l['way_id'])
 if fw in wayends and lw in wayends:ends[rid]=(transform(pr,Point(wayends[fw][0 if f['direction']=='1' else 1])),transform(pr,Point(wayends[lw][1 if l['direction']=='1' else 0])))
cross=[];selection=[];route_geoms={}
for rid,status,j,b in db.execute('SELECT osm_id,status,attributes_json,geom FROM transit_active_member_geometry').fetchall():
 a=json.loads(j)
 if a['mode']!='bus':continue
 g=geom(b);gm=transform(pr,g);route_geoms[rid]=gm;points=sample(gm);opts={r['RouteID']:r for c in codes(a.get('ref','')) for r in bycode.get(c,[])};cc=[]
 for refid,r in opts.items():
  ds=distances(points,r['metric']);rev=distances(sample(r['metric']),gm);name=(sim(a['tags'].get('from'),r['OriginationName'])+sim(a['tags'].get('to'),r['DestinationName']))/2
  endpoints=None
  if rid in ends:endpoints=ends[rid][0].distance(Point(r['metric'].coords[0]))+ends[rid][1].distance(Point(r['metric'].coords[-1]))
  row={'osm_relation_id':rid,'osm_ref':a.get('ref',''),'osm_status':status,'reference_route_id':refid,'reference_route_code':r['RouteCode'],'reference_from':r['OriginationName'],'reference_to':r['DestinationName'],'name_similarity':name,'osm_to_reference_p95_m':float(np.quantile(ds,.95)),'reference_to_osm_p95_m':float(np.quantile(rev,.95)),'osm_fraction_within_100m':float(np.mean(ds<=100)),'reference_fraction_within_100m':float(np.mean(rev<=100)),'ordered_endpoint_distance_sum_m':endpoints,'reference_date':'2024-05-14','not_current_service_certification':True}
  cc.append(row)
 if not cc:selection.append({'osm_relation_id':rid,'osm_ref':a.get('ref',''),'osm_status':status,'matching_status':'no_reference_code_match','reference_route_id':''});continue
 # Explicit directional evidence rather than arbitrarily choosing a geometrically similar opposite direction.
 ranked=sorted(cc,key=lambda x:(-x['name_similarity'],x['osm_to_reference_p95_m']+x['reference_to_osm_p95_m'],x['reference_route_id']))
 best=ranked[0];direction='ambiguous_direction_candidates_retained'
 if len(ranked)==1:direction='single_code_candidate_not_service_verification'
 elif best['name_similarity']>=.6 and best['name_similarity']-ranked[1]['name_similarity']>=.1:direction='endpoint_name_supported'
 elif rid in ends:
  er=sorted(cc,key=lambda x:x['ordered_endpoint_distance_sum_m']);
  if er[1]['ordered_endpoint_distance_sum_m']-er[0]['ordered_endpoint_distance_sum_m']>=500:best=er[0];direction='ordered_geometry_endpoints_supported'
 for c in cc:c['selected_for_diagnostics']=c is best;c['direction_selection_status']=direction;cross.append(c)
 selection.append({**best,'matching_status':direction,'both_p95_le_100m':best['osm_to_reference_p95_m']<=100 and best['reference_to_osm_p95_m']<=100})
csvout('bus_reference_candidates_2024.csv',cross);csvout('bus_reference_crosswalk_2024.csv',selection)
# Historical stops are associated with current relation geometry for diagnostics only.
station_checks=[]
for sel in selection:
 if not sel.get('reference_route_id'):continue
 rid=sel['osm_relation_id'];refid=sel['reference_route_id']
 for s in rstop[refid]:
  st=stations[s['StationCode']];p=transform(pr,Point(st['Longitude'],st['Latitude']));distance=p.distance(route_geoms[rid])
  station_checks.append({'osm_relation_id':rid,'reference_route_id':refid,'station_code':s['StationCode'],'station_order':s['StationOrder'],'distance_to_current_route_members_m':distance,'within_100m':distance<=100,'direction_selection_status':sel['matching_status'],'boarding_access_verified':False,'source_date':'2024-05-14'})
csvout('historical_stop_to_osm_route_diagnostics.csv',station_checks)
print('Crosswalk complete',len(cross),'candidate direction pairs',flush=True)
# Human-facility screening keeps source objects and separates uncertain classifications.
table('hospital_screened_candidates','GEOMETRY');hospital=[]
evidence={
 'erfanhospital.ir':{'url':'https://erfanhospital.ir/fa/امکانات-درمانی/بخش-ها/بخش-اورژانس','claim':'hospital website describes 24-hour emergency department','page_date':'not stated','kind':'department_page_found_not_current_capacity_certification'},
 'armanhospital.com':{'url':'https://armanhospital.com/emergency/','claim':'hospital website describes 24-hour emergency department','page_date':'2022-03-11','kind':'department_page_found_not_current_capacity_certification'}}
for typ,ident,j,b in db.execute('SELECT osm_type,osm_id,attributes_json,geom FROM hospital_candidates').fetchall():
 a=json.loads(j);t=a['tags'];name=norm(t.get('name'));text=' '.join([name,t.get('name:en',''),t.get('operator','')]).lower();hw=t.get('healthcare','');am=t.get('amenity','');flags=[]
 if am=='veterinary' or re.search('دامپزش|veterinar|persianpet',text):decision='excluded_nonhuman';flags.append('nonhuman_tag_or_explicit_name')
 elif hw in ('dentist','clinic','doctor','doctors','laboratory','psychotherapist') or re.search('مطب|دندان|کلینیک|درمانگاه|ارتوپدی فنی|مرکز بهداشت|بخش کرونا|ساختمان شماره',text) or (name.startswith(('دکتر','دكتر','Dr.','Dr ')) and 'بیمارستان' not in name) or re.search('buccal_fat|بوکال|prosthetics|orthotics',t.get('healthcare:speciality','')):decision='facility_type_needs_review';flags.append('conflicting_tag_or_nonhospital_name')
 elif not name and typ=='n':decision='facility_type_needs_review';flags.append('unnamed_point')
 else:decision='human_hospital_candidate'
 specialist=bool(re.search('اعصاب و روان|سرطان|کودکان|چشم|سوختگی|مغز و اعصاب|ترمیمی و پلاستیک',text));em=t.get('emergency','unknown')
 if specialist:flags.append('specialist_scope_requires_scenario')
 web=t.get('website',t.get('contact:website',''));ev=next((v for k,v in evidence.items() if k in web),None)
 row={'osm_type':typ,'osm_id':ident,'name':name,'candidate_group_id':a.get('candidate_group_id',f'{typ}{ident}'),'inside_city':a['inside_city_representative_point'],'emergency_tag':em,'screen_decision':decision,'specialist_scope_flag':specialist,'primary_osm_proxy_target':decision=='human_hospital_candidate' and em=='yes' and not specialist,'extended_scope_osm_proxy_target':decision=='human_hospital_candidate' and em=='yes','uncertain_hospital_sensitivity_candidate':decision=='human_hospital_candidate' and em=='unknown','external_evidence':ev['kind'] if ev else 'not_established_in_bounded_review','external_source_url':ev['url'] if ev else '','external_page_date':ev['page_date'] if ev else '','flags':';'.join(flags),'entrance_verified':False,'general_emergency_capacity_verified':False}
 hospital.append(row);put('hospital_screened_candidates',f'{typ}{ident}',decision,row,geom(b))
csvout('hospital_screening_registry.csv',hospital);dump('hospital_external_evidence.json',{'review_scope':'bounded convenience sample of 7 source-linked hospital websites; not random or representative','evidence':evidence,'not_retrieved_or_no_department_evidence':['sinahospital.tums.ac.ir','payambaranhospital.ir','atiehhospital.ir','niayeshhospital.ir','mehrhospitaltehran.com'],'claim_limit':'department website presence, not field verification, real-time availability, geocoded entrance or universal service eligibility','checked_utc':now})
for tab in ['historical_bus_stops_2024','historical_route_stops_2024','hospital_screened_candidates']:
 bb=[geom(row[0]).bounds for row in db.execute(f'SELECT geom FROM {tab}')];bound=(min(x[0] for x in bb),min(x[1] for x in bb),max(x[2] for x in bb),max(x[3] for x in bb));db.execute('UPDATE gpkg_contents SET min_x=?,min_y=?,max_x=?,max_y=? WHERE table_name=?',(*bound,tab))
assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';db.commit();db.close();ref.close()
summary={'version':'1.1','created_utc':now,'historical_source_date':'2024-05-14','historical_stations':len(srows),'historical_route_station_links':len(rsrows),'historical_route_records':len(rqa),'historical_order_gap_routes':sum('source_station_order_has_gap' in x['flags'] for x in rqa),'historical_routes_with_station_distance_over_100m':sum('station_more_than_100m' in x['flags'] for x in rqa),'historical_routes_with_projection_backtracking_flag':sum('projection_has_backtracking' in x['flags'] for x in rqa),'crosswalk_relations':len(selection),'crosswalk_relations_with_code_candidate':sum(bool(x.get('reference_route_id')) for x in selection),'direction_status_counts':dict(collections.Counter(x['matching_status'] for x in selection)),'both_way_geometry_p95_le_100m':sum(x.get('both_p95_le_100m',False) for x in selection),'historical_stop_osm_route_diagnostic_pairs':len(station_checks),'hospital_screen_counts':dict(collections.Counter(x['screen_decision'] for x in hospital)),'raw_emergency_yes_features':sum(x['emergency_tag']=='yes' for x in hospital),'primary_proxy_target_features':sum(x['primary_osm_proxy_target'] for x in hospital),'primary_proxy_target_candidate_groups':len({x['candidate_group_id'] for x in hospital if x['primary_osm_proxy_target']}),'extended_scope_proxy_features':sum(x['extended_scope_osm_proxy_target'] for x in hospital),'external_department_evidence_features':sum(x['external_source_url']!='' for x in hospital),'claims':{'current_citywide_bus_network_certified':False,'turn_aware_routing_graph_implemented':False,'all_hospital_services_verified':False,'historical_route_shape_joined_to_current_road_ids':False,'street_segments_invented':False},'stopping_rule':'Use audited available source snapshots with explicit flags. Lack of independent certification does not block freezing this dataset; unresolved records do not become verified.'}
dump('enrichment_summary.json',summary)
print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
