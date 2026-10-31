import sys,json,hashlib, pathlib
sys.path.insert(0,str(pathlib.Path('work/pylibs').resolve()))
import osmium, shapely, pyproj
from shapely.geometry import shape,mapping,box
from shapely.ops import transform,unary_union
from shapely.validation import explain_validity
SRC=pathlib.Path('outputs/dataset_candidate/tehran_context.osm.pbf')
OUT=pathlib.Path('outputs/dataset_candidate');OUT.mkdir(exist_ok=True)
class Audit(osmium.SimpleHandler):
 def __init__(self):
  super().__init__();self.rels={};self.areas={};self.ways=set();self.nodes=set();self.factory=osmium.geom.GeoJSONFactory();self.n=0
 def node(self,n):self.nodes.add(n.id)
 def way(self,w):self.ways.add(w.id)
 def relation(self,r):
  t=dict(r.tags)
  if r.id==6663864 or (t.get('boundary')=='administrative' and ('تهران' in t.get('name',''))):
   self.rels[r.id]={'tags':t,'version':r.version,'timestamp':str(r.timestamp),'members':[(m.type,m.ref,m.role) for m in r.members]}
 def area(self,a):
  t=dict(a.tags)
  if a.orig_id()==6663864 or (t.get('boundary')=='administrative' and 'تهران' in t.get('name','')):
   try:self.areas[a.orig_id()]=shape(json.loads(self.factory.create_multipolygon(a)))
   except Exception as e: print('area error',a.orig_id(),str(e))
h=Audit();h.apply_file(str(SRC),locations=True,idx='flex_mem')
print('Relations',[(i,r['tags'].get('name'),r['tags'].get('admin_level'),i in h.areas) for i,r in h.rels.items()])
(OUT/'boundary_relations_inventory.json').write_text(json.dumps(h.rels,ensure_ascii=False,indent=2),encoding='utf8')
assert 6663864 in h.areas,'City polygon could not be assembled'
g=h.areas[6663864];proj=pyproj.Transformer.from_crs(4326,32639,always_xy=True).transform;gm=transform(proj,g);bbox=box(50.9,35.4,51.95,36.05)
report={'source_file':str(SRC),'sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),'osmium_version':osmium.__version__ if hasattr(osmium,'__version__') else '4.3.2','shapely_version':shapely.__version__,'relation_id':6663864,'relation_metadata':h.rels[6663864], 'geometry_type':g.geom_type,'valid':g.is_valid,'validity_reason':explain_validity(g),'empty':g.is_empty,'parts':len(g.geoms),'holes':sum(len(p.interiors) for p in g.geoms),'bounds_lon_lat':list(g.bounds),'area_km2_UTM39N':gm.area/1e6,'perimeter_km_UTM39N':gm.length/1000,'covered_by_requested_bbox':bbox.covers(g),'outside_bbox_area_km2':transform(proj,g.difference(bbox)).area/1e6,'missing_boundary_way_members':[m for m in h.rels[6663864]['members'] if m[0]=='w' and m[1] not in h.ways]}
for b in (0,1000,3000,5000,10000):
 region=gm.buffer(b) if b else gm
 bm=transform(proj,bbox)
 report.setdefault('buffer_coverage',[]).append({'buffer_m':b,'covered_by_bbox':bm.covers(region),'outside_bbox_area_km2':region.difference(bm).area/1e6})
# Municipal-district polygons are an internal OSM cross-check, not independent reference.
districts=[(i,h.areas[i]) for i,r in h.rels.items() if i in h.areas and r['tags'].get('admin_level')=='9' and 'منطقه' in r['tags'].get('name','')]
if districts:
 u=unary_union([x for i,x in districts]);report['district_check']={'count':len(districts),'ids':[i for i,x in districts],'union_area_km2':transform(proj,u).area/1e6,'city_minus_districts_km2':transform(proj,g.difference(u)).area/1e6,'districts_minus_city_km2':transform(proj,u.difference(g)).area/1e6,'overlap_area_km2':sum(transform(proj,x).area for i,x in districts)/1e6-transform(proj,u).area/1e6}
features=[{'type':'Feature','properties':{'osm_relation_id':6663864,'name':'Tehran city (OSM)','source':'OpenStreetMap via BBBike','data_snapshot':'2026-10-29T21:21:26Z','official_boundary_verified':False},'geometry':mapping(g)}]
(OUT/'tehran_city_osm_boundary.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False),encoding='utf8')
(OUT/'boundary_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k!='relation_metadata'},ensure_ascii=False,indent=2))
# Additional geometric checks and map; executed after boundary_audit.py.
from pyproj import Geod
report['geodesic_area_km2']=abs(Geod(ellps='WGS84').geometry_area_perimeter(g)[0])/1e6
report['district_geometries_valid']=all(x.is_valid for i,x in districts)
report['all_city_exterior_rings_closed']=all(p.exterior.is_ring for p in g.geoms)
report['geometry_modified']=False
wanted={m[1] for m in h.rels[6663864]['members'] if m[0]=='w'}
class WayCheck(osmium.SimpleHandler):
 def __init__(self):super().__init__();self.missing=[];self.refs=0
 def way(self,w):
  if w.id in wanted:
   for n in w.nodes:
    self.refs+=1
    if n.ref not in h.nodes:self.missing.append([w.id,n.ref])
c=WayCheck();c.apply_file(str(SRC));report['boundary_node_reference_count']=c.refs;report['missing_boundary_nodes']=c.missing
features_d=[{'type':'Feature','properties':{'osm_relation_id':i,**h.rels[i]['tags']},'geometry':mapping(x)} for i,x in districts]
(OUT/'tehran_22_districts_osm.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features_d},ensure_ascii=False),encoding='utf8')
gap=g.difference(u)
(OUT/'city_district_gap.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{'note':'OSM city minus OSM municipal districts; do not automatically delete'},'geometry':mapping(gap)}]}),encoding='utf8')
report['district_gap_bounds']=list(gap.bounds)
report['district_gap_percent_of_city']=100*gap.area/g.area
(OUT/'boundary_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axs=plt.subplots(1,2,figsize=(13,6),layout='constrained')
for ax in axs:
 for p in g.geoms:
  x,y=p.exterior.xy;ax.fill(x,y,color='#dcece7',ec='#006454',lw=1.6,label='OSM city boundary')
 for i,d in districts:
  for p in d.geoms if d.geom_type=='MultiPolygon' else [d]:
   ax.plot(*p.exterior.xy,color='#777777',lw=.55)
   if ax==axs[1]:
    label=h.rels[i]['tags']['name'].split()[1];label=label.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹','0123456789'));pt=p.representative_point();ax.text(pt.x,pt.y,label,fontsize=7,ha='center')
 ax.set_aspect(1/0.812);ax.set_xlabel('Longitude (WGS84)');ax.set_ylabel('Latitude (WGS84)');ax.grid(alpha=.2)
axs[0].plot(*bbox.exterior.xy,color='#be7e15',lw=2)
axs[0].set_title('Downloaded rectangle and Tehran city')
axs[1].set_xlim(51.06,51.64);axs[1].set_ylim(35.54,35.85);axs[1].set_title('City and 22 municipal districts (OSM)')
if not gap.is_empty:
 for p in gap.geoms if hasattr(gap,'geoms') else [gap]:
  if p.geom_type=='Polygon':axs[1].fill(*p.exterior.xy,color='red')
fig.suptitle('Tehran boundary audit | OSM snapshot 2026-10-29 21:21 UTC | not an official cadastral certification',fontsize=11)
fig.savefig(OUT/'tehran_boundary_audit.png',dpi=180);plt.close(fig)
print('Additional checks:',json.dumps({k:report[k] for k in ['geodesic_area_km2','district_geometries_valid','all_city_exterior_rings_closed','missing_boundary_nodes','district_gap_bounds','district_gap_percent_of_city']}))
