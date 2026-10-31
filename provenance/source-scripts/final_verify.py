import sys,pathlib,json,csv,sqlite3,collections,struct,hashlib
sys.path.insert(0,'work/pylibs');import osmium,shapely
R=pathlib.Path('outputs/tehran_dataset_v1');db=sqlite3.connect(R/'tehran_audited_layers.gpkg')
class H(osmium.SimpleHandler):
 def __init__(self):super().__init__();self.rs={}
 def relation(self,r):self.rs[r.id]={'tags':dict(r.tags),'members':[(m.type,m.ref,m.role) for m in r.members]}
h=H();h.apply_file('outputs/dataset_candidate/tehran_context.osm.pbf')
# index is only an acceleration structure, not a change to any OSM geometry.
db.execute('CREATE INDEX IF NOT EXISTS road_osm_id ON roads_context(osm_id)')
wanted={m[1] for r in h.rs.values() if r['tags'].get('type') in ('restriction','route') for m in r['members'] if m[0]=='w'};ways={}
ls=list(wanted)
for a in range(0,len(ls),800):
 vals=ls[a:a+800];query='SELECT osm_id,attributes_json FROM roads_context WHERE osm_id IN ('+','.join('?' for _ in vals)+')'
 for i,s in db.execute(query,vals):ways[i]=json.loads(s)
def readcsv(name):return list(csv.DictReader(open(R/name,encoding='utf-8-sig')))
def writecsv(name,rows):
 with open(R/name,'w',encoding='utf-8-sig',newline='') as f:
  if rows:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
# Add explicit unknown role and access-policy flags; never infer bus permission from geometry alone.
rr=readcsv('transit_routes.csv')
for row in rr:
 r=h.rs[int(row['relation_id'])];extra=[]
 for typ,i,role in r['members']:
  if typ!='w' or 'inactive' in role or role.startswith(('platform','stop')):continue
  if i not in ways:continue
  t=ways[i]['tags']
  if t.get('public_transport')=='platform' or t.get('highway') in ('bus_stop','platform'):continue
  if role not in ('','forward','backward'):extra.append('unrecognized_line_member_role')
  if row['mode']=='bus':
   modeval=next((t[k] for k in ('bus','psv','motor_vehicle','vehicle','access') if k in t),None)
   if modeval in ('no','private'):extra.append('bus_access_permission_needs_review')
 if extra:
  row['flags']=';'.join(sorted(set(filter(None,row['flags'].split(';')+extra))))
  if row['status']=='passes_structural_screen_only':row['status']='quarantine_member_semantics'
writecsv('transit_routes.csv',rr);writecsv('transit_quarantine.csv',[r for r in rr if r['status'].startswith('quarantine')]);valid={int(r['relation_id']) for r in rr if r['status']=='passes_structural_screen_only'}
writecsv('transit_ordered_paths_screened.csv',[r for r in readcsv('transit_ordered_paths_screened.csv') if int(r['route_relation_id']) in valid])
status={r['relation_id']:r['status'] for r in rr}
writecsv('bus_road_dependencies.csv',[{**r,'route_status':status[r['route_relation_id']]} for r in readcsv('bus_road_dependencies.csv')])
# Distinguish genuinely absent required roles from valid but more complex via-way restrictions.
tr=[]
for ident,r in h.rs.items():
 t=r['tags']
 if t.get('type')!='restriction':continue
 fr=[m for m in r['members'] if m[2]=='from'];to=[m for m in r['members'] if m[2]=='to'];via=[m for m in r['members'] if m[2]=='via'];reason='';conditional=any(':conditional' in k for k in t);mode_specific=any(k.startswith('restriction:') and k!='restriction:conditional' for k in t) or bool(t.get('except'))
 if not fr or not to or not via:reason='required_member_role_absent_in_source'
 elif len(fr)!=1 or len(to)!=1 or fr[0][0]!='w' or to[0][0]!='w':reason='complex_from_to_schema_review'
 elif fr[0][1] not in ways or to[0][1] not in ways:reason='nonhighway_member_review'
 elif len(via)==1 and via[0][0]=='n':
  v=via[0][1]
  if v not in ways[fr[0][1]]['node_ids'] or v not in ways[to[0][1]]['node_ids']:reason='via_node_not_on_from_and_to_ways'
  elif conditional or mode_specific:reason='conditional_or_mode_exception_model_required'
  elif t.get('restriction') not in ('no_left_turn','no_right_turn','no_straight_on','no_u_turn','only_left_turn','only_right_turn','only_straight_on','only_u_turn'):reason='unrecognized_restriction_value_review'
  else:reason='simple_via_node_structure_pass_only'
 elif all(m[0]=='w' for m in via):
  seq=[fr[0][1]]+[m[1] for m in via]+[to[0][1]]
  if any(x not in ways for x in seq):reason='via_way_nonhighway_member_review'
  elif any(not set(ways[a]['node_ids']).intersection(ways[b]['node_ids']) for a,b in zip(seq,seq[1:])):reason='via_way_member_chain_not_connected'
  else:reason='via_way_structure_pass_state_model_required'
 else:reason='complex_via_schema_review'
 tr.append({'relation_id':ident,'restriction':t.get('restriction',''),'audit_status':reason,'tags_json':json.dumps(t,ensure_ascii=False),'members_json':json.dumps(r['members'])})
writecsv('turn_restriction_semantic_audit.csv',tr)
# Verify every exported GPKG geometry decodes and matches its stored envelope and SRS.
verify={}
for table,gt in db.execute('SELECT table_name,geometry_type_name FROM gpkg_geometry_columns').fetchall():
 n=0;bad=0;invalid=0;types=collections.Counter()
 for (blob,) in db.execute(f'SELECT geom FROM {table} WHERE geom IS NOT NULL'):
  n+=1
  if blob[:2]!=b'GP' or blob[2]!=0 or blob[3]!=3 or struct.unpack('<i',blob[4:8])[0]!=4326:bad+=1;continue
  geom=shapely.from_wkb(blob[40:]);types[geom.geom_type]+=1
  if not geom.is_valid:invalid+=1
  x1,x2,y1,y2=struct.unpack('<4d',blob[8:40]);bounds=geom.bounds
  if any(abs(a-b)>1e-9 for a,b in zip((x1,y1,x2,y2),bounds)):bad+=1
 verify[table]={'feature_count':n,'invalid_binary_or_envelope':bad,'invalid_geometry':invalid,'geometry_types':dict(types)}
# Point-on-surface hospital associations remain candidates, not verified unique facilities.
hosp=readcsv('hospital_candidates.csv');bld=readcsv('buildings_city.csv')
summary=json.load(open(R/'final_audit_summary.json',encoding='utf8'));summary['transit_status_by_mode']={m:dict(collections.Counter(r['status'] for r in rr if r['mode']==m)) for m in ('bus','subway')};summary['restriction_semantic_status']=dict(collections.Counter(r['audit_status'] for r in tr));summary['geopackage_verification']=verify;summary['hospital_features_inside_city']=sum(r['inside_city']=='True' for r in hosp);summary['hospital_features_outside_city']=sum(r['inside_city']=='False' for r in hosp);summary['hospital_emergency_tag_counts']=dict(collections.Counter(r['emergency_tag'] for r in hosp));summary['building_exception_reasons']=dict(collections.Counter(r['reason'] for r in readcsv('building_exceptions.csv')));summary['transit_context_only']=[{'id':r['relation_id'],'mode':r['mode'],'name':r['name']} for r in rr if r['status']=='context_only_outside_city'];summary['release_readiness']={'frozen_audited_OSM_snapshot':True,'complete_citywide_bus_routing_dataset':False,'externally_verified_emergency_facility_inventory':False,'turn_aware_road_graph':False,'entrance_and_barrier_validated_building_connectors':False}
(R/'final_audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');db.commit();db.close();print(json.dumps({'transit':summary['transit_status_by_mode'],'restrictions':summary['restriction_semantic_status'],'gpkg':verify,'hosp_inside':summary['hospital_features_inside_city'],'emergency_tags':summary['hospital_emergency_tag_counts']},ensure_ascii=False,indent=2))
