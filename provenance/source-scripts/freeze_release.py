import pathlib,sqlite3,struct,json,csv,hashlib,shutil,datetime,zipfile,collections
import shapely
R=pathlib.Path('outputs/tehran_dataset_v1');(R/'audit_history').mkdir(exist_ok=True);(R/'scripts').mkdir(exist_ok=True)
def readcsv(name):return list(csv.DictReader(open(R/name,encoding='utf-8-sig')))
def writecsv(name,rows):
 keys=list(dict.fromkeys(k for x in rows for k in x))
 with open(R/name,'w',encoding='utf-8-sig',newline='') as f:
  if keys:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
# Diagnostic gap geometry can collapse to a point when coordinates coincide but OSM node IDs differ.
db=sqlite3.connect(R/'tehran_audited_layers.gpkg');collapsed=0
for fid,attrs,blob in db.execute('SELECT fid,attributes_json,geom FROM transit_gap_diagnostics').fetchall():
 geom=shapely.from_wkb(blob[40:])
 if not geom.is_valid and geom.length<1e-12:
  geom=shapely.geometry.Point(geom.coords[0]);a=json.loads(attrs);a['diagnostic_type']='coincident_coordinates_distinct_OSM_node_ids';x,y=geom.x,geom.y;data=b'GP'+bytes([0,3])+struct.pack('<i4d',4326,x,x,y,y)+shapely.to_wkb(geom,byte_order=1);db.execute('UPDATE transit_gap_diagnostics SET attributes_json=?,geom=? WHERE fid=?',(json.dumps(a,ensure_ascii=False),data,fid));collapsed+=1
if collapsed:db.execute("UPDATE gpkg_geometry_columns SET geometry_type_name='GEOMETRY' WHERE table_name='transit_gap_diagnostics'")
# Preserve unusual emergency values as explicit anomalies rather than treating them as yes.
hospital=readcsv('hospital_candidates.csv')
for r in hospital:
 if r['emergency_tag'] not in ('yes','no','unknown'):r['flags']=';'.join(filter(None,[r['flags'],'non_boolean_emergency_tag_requires_review']))
writecsv('hospital_candidates.csv',hospital)
for fid,attrs in db.execute('SELECT fid,attributes_json FROM hospital_candidates').fetchall():
 a=json.loads(attrs)
 if a['emergency_tag'] not in ('yes','no','unknown'):
  a['flags'].append('non_boolean_emergency_tag_requires_review');db.execute('UPDATE hospital_candidates SET attributes_json=? WHERE fid=?',(json.dumps(a,ensure_ascii=False),fid))
# Final authoritative CSVs; original stage screens are preserved as audit history.
for name in ['transit_routes.csv','transit_quarantine.csv','transit_ordered_paths_screened.csv','turn_restrictions.csv']:
 p=R/name
 if p.exists():shutil.move(str(p),str(R/'audit_history'/name))
shutil.copy2(R/'transit_reviewed_inventory.csv',R/'transit_routes.csv');shutil.copy2(R/'transit_derived_ordered_paths.csv',R/'transit_paths.csv');shutil.copy2(R/'turn_restriction_semantic_audit.csv',R/'turn_restrictions.csv')
review=readcsv('transit_routes.csv');status={r['relation_id']:r['status'] for r in review};deps=readcsv('bus_road_dependencies.csv')
for r in deps:r['route_status']=status[r['route_relation_id']];r['sequence_meaning']='original_active_OSM_member_order; use transit_paths.csv for derived order'
writecsv('bus_road_dependencies.csv',deps)
for name in ['tehran_city_osm_boundary.geojson','tehran_22_districts_osm.geojson','boundary_audit.json','city_district_gap.geojson','extraction_receipt.json']:
 shutil.copy2(pathlib.Path('outputs/dataset_candidate')/name,R/name)
shutil.copy2('work/iran_source/source_receipt.json',R/'primary_source_receipt.json');shutil.copy2('work/operator_reference/receipt.json',R/'historical_reference_receipt.json')
for name in ['final_audit.py','final_verify.py','add_line5.py','review_and_repair_transit.py','check_release_integrity.py','check_building_assembly.py','freeze_release.py']:
 p=pathlib.Path('work')/name
 if p.exists():shutil.copy2(p,R/'scripts'/name)
# Independent final read-back of every packaged geometry.
geomqa={}
for tab,declared in db.execute('SELECT table_name,geometry_type_name FROM gpkg_geometry_columns').fetchall():
 n=bad=invalid=0;types=collections.Counter()
 for (blob,) in db.execute(f'SELECT geom FROM {tab} WHERE geom IS NOT NULL'):
  n+=1
  if blob[:2]!=b'GP' or blob[2]!=0 or blob[3]!=3 or struct.unpack('<i',blob[4:8])[0]!=4326:bad+=1;continue
  geom=shapely.from_wkb(blob[40:]);types[geom.geom_type]+=1;invalid+=not geom.is_valid
  x1,x2,y1,y2=struct.unpack('<4d',blob[8:40]);bad+=any(abs(a-b)>1e-9 for a,b in zip((x1,y1,x2,y2),geom.bounds))
 geomqa[tab]={'count':n,'binary_or_envelope_errors':bad,'invalid_geometry_count':invalid,'actual_types':dict(types),'declared_type':declared}
assert all(v['binary_or_envelope_errors']==0 and v['invalid_geometry_count']==0 for v in geomqa.values()),geomqa
assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
now=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z');db.execute('UPDATE gpkg_contents SET last_change=?',(now,));db.commit();db.close()
integrity=json.load(open(R/'reference_integrity.json'));assert integrity['ways_with_missing_nodes']==0 and integrity['relations_with_missing_members']==0 and not integrity['duplicate_ids'] and integrity['ordering_errors']==0
summary=json.load(open(R/'final_audit_summary.json',encoding='utf8'));summary['initial_context_source_sha256']=summary.pop('source_pbf_sha256');summary['source_pbf_sha256']=integrity['sha256'];summary['raw_counts']=integrity['counts'];summary['final_transit_review']=json.load(open(R/'transit_review_summary.json',encoding='utf8'));summary['geopackage_verification']=geomqa;summary['collapsed_diagnostic_lines_converted_to_points']=collapsed;summary['building_assembly_audit']=json.load(open(R/'building_assembly_audit.json'));summary['current_release_status']='frozen audited source-and-derived dataset v1.0 with explicit quality flags; not a complete operational bus service inventory';summary['final_created_utc']=now
(R/'final_audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');(R/'geopackage_validation.json').write_text(json.dumps(geomqa,indent=2),encoding='utf8')
# Historic comparison metrics, explicitly not current-service certification.
comp=[x for x in readcsv('bus_reference_comparison_2024.csv') if x.get('reference_route_id')];metrics={'matched_route_relations':len(comp),'relations_with_p95_sample_distance_to_reference_le_100m':sum(float(x['p95_distance_m'])<=100 for x in comp),'meaning':'sampled agreement with 2024 shape, not verification of 2026 operation or full topology'}
(R/'historical_comparison_summary.json').write_text(json.dumps(metrics,indent=2),encoding='utf8')
manifest={'dataset_id':'tehran-osm-20261029T212126Z-v1.0','version':'1.0','release_status':'frozen_with_documented_limitations','frozen_utc':now,'primary_source':'OpenStreetMap via Geofabrik Iran','data_timestamp_utc':'2026-10-29T21:21:26Z','data_timestamp_tehran':'2026-10-30T00:51:26+03:30','primary_source_archive_sha256':'9cac1960b89a1ac1f464412aa0d6ef6f0c02a1b745cb218ba23d37d8dcbc9f01','primary_source_archive_relative_location':'../source_archive/iran-geofabrik-20261029T212126Z.osm.pbf','city_relation_id':6663864,'city_definition':'OSM Tehran city boundary with 22 municipal districts; official legal equivalence not independently verified','context_bbox':[50.9,35.4,51.95,36.05],'historical_reference_date':'2024-05-14','historical_reference_role':'separate auxiliary comparison, not merged into 2026 OSM raw geometry','licenses':{'OSM':'ODbL; attribution OpenStreetMap contributors','historical_reference':'publicly downloadable; explicit redistribution license not established'},'readiness':{'reference_complete_OSM_source':True,'valid_exported_geometry':True,'building_mask_and_quality_registries':True,'route_dependency_membership_inventory_with_flags':True,'structurally_screened_transit_subset':True,'complete_current_citywide_operational_bus_network_certified':False,'real_emergency_service_or_response_time_certified':False,'all_routing_turn_semantics_implemented':False,'barrier_aware_building_and_hospital_connectors_certified':False},'raw_reference_integrity':integrity,'files':{}}
(R/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');print('Final verification done',len(geomqa),'layers; collapsed diagnostic points',collapsed)
