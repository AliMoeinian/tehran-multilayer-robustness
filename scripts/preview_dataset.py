"""Lightweight static overview from the frozen GeoPackage; no tiles or web data."""
import pathlib,sys,sqlite3,json,struct,math
ROOT=pathlib.Path(__file__).resolve().parents[1]
import shapely,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from pyproj import Transformer
receipt=json.loads((ROOT/'data/release.json').read_text());R=ROOT/'data/extracted'/receipt['dataset_id'];O=ROOT/'docs/assets';O.mkdir(exist_ok=True)
c=sqlite3.connect((R/'tehran_audited_layers.gpkg').as_uri()+'?mode=ro',uri=True)
tr=Transformer.from_crs(4326,32639,always_xy=True)
def geom(b):return shapely.from_wkb(b[8+{0:0,1:32,2:48,3:48,4:64}[(b[3]>>1)&7]:])
def lineparts(g):
 if g.geom_type=='Polygon':yield np.asarray(g.exterior.coords)
 elif g.geom_type in ('LineString','LinearRing'):yield np.asarray(g.coords)
 elif hasattr(g,'geoms'):
  for p in g.geoms:yield from lineparts(p)
def xy(a):
 x,y=tr.transform(a[:,0],a[:,1]);return np.column_stack((x,y))/1000
def lines(table,choose=lambda a:True):
 out=[]
 for a,b in c.execute(f'select attributes_json,geom from {table}'):
  if choose(json.loads(a)):out.extend(xy(p) for p in lineparts(geom(b)))
 return out
city=lines('city_boundary');district=lines('municipal_districts')
allcity=np.vstack(city);lo=allcity.min(axis=0)-[2,2];hi=allcity.max(axis=0)+[2,2]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12})
fig,axs=plt.subplots(1,3,figsize=(18,6),layout='constrained',facecolor='#f6f8fc')
def base(ax):
 ax.set_facecolor('#ffffff');ax.add_collection(LineCollection(district,colors='#9ba8bb',linewidths=.45,zorder=6))
 ax.add_collection(LineCollection(city,colors='#263f61',linewidths=1.4,zorder=7));ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_aspect('equal');ax.set_xticks([]);ax.set_yticks([])
 for s in ax.spines.values():s.set_color('#d3dbe7')
 x=lo[0]+1.5;y=lo[1]+1;ax.plot([x,x+5],[y,y],color='#263f61',lw=2,zorder=9);ax.text(x+2.5,y+.35,'5 km',ha='center',fontsize=8)
def legend(ax,items):
 ax.legend(handles=[Line2D([0],[0],color=co,lw=2,label=label,marker=mark,markersize=5,linestyle='None' if mark else '-') for co,label,mark in items],loc='upper left',fontsize=8,framealpha=.95)
for ax in axs.flat:base(ax)
ax=axs[0]
pts=np.array([[d['point_lon'],d['point_lat']] for (a,) in c.execute('select attributes_json from buildings_city') for d in [json.loads(a)]])
p=xy(pts);ax.scatter(p[:,0],p[:,1],s=.18,alpha=.45,color='#798897',rasterized=True,zorder=2)
major=lines('roads_context',lambda a:a['tags'].get('highway','').replace('_link','') in {'motorway','trunk','primary','secondary','tertiary'})
ax.add_collection(LineCollection(major,colors='#d89b35',linewidths=.38,alpha=.7,zorder=3))
ax.set_title('A  |  City, streets and building origins',loc='left',weight='bold',pad=12)
legend(ax,[('#798897','65,677 selected building points','.'),('#d89b35','Major road classes (context)',''),('#263f61','City boundary + 22 districts','')])
ax=axs[1]
other=lines('transit_active_member_geometry',lambda a:a['status']!='continuous_ordered_path_screened')
bus=lines('transit_active_member_geometry',lambda a:a['status']=='continuous_ordered_path_screened' and a['mode']=='bus')
rail=lines('transit_active_member_geometry',lambda a:a['status']=='continuous_ordered_path_screened' and a['mode']=='metro')
for ls,co,lw,alpha in [(other,'#d0b7a6',.6,.55),(bus,'#087f8c',1,.9),(rail,'#7b49b3',1.4,.95)]:ax.add_collection(LineCollection(ls,colors=co,linewidths=lw,alpha=alpha,zorder=3))
ax.set_title('B  |  Recorded public transport: 2026 OSM',loc='left',weight='bold',pad=12)
legend(ax,[('#087f8c','39 bus relations: strict structural screen',''),('#7b49b3','14 rail relations: strict structural screen',''),('#d0b7a6','Other member geometry: flags / review','')])
ax=axs[2];groups={}
for a,b in c.execute('select attributes_json,geom from hospital_screened_candidates'):
 d=json.loads(a);key=d.get('screen_decision','unknown');pt=geom(b).representative_point();groups.setdefault(key,[]).append((pt.x,pt.y))
for k,co,marker in [('facility_type_needs_review','#c18b37','x'),('excluded_nonhuman','#aeb5bf','x'),('human_hospital_candidate','#d94862','o')]:
 if groups.get(k):
  ps=xy(np.array(groups[k]));ax.scatter(ps[:,0],ps[:,1],c=co,s=15,marker=marker,alpha=.8,linewidths=.6,zorder=4)
ax.set_title('C  |  Mapped hospital candidates',loc='left',weight='bold',pad=12)
legend(ax,[('#d94862','249 human hospital candidate features','o'),('#c18b37','69 features: facility type needs review','x'),('#aeb5bf','3 nonhuman features: excluded','x')])
fig.suptitle('TEHRAN | OSM-only public dataset',fontsize=20,weight='bold',color='#263f61')
fig.supxlabel('OSM snapshot: 2026-10-29 21:21:26 UTC | Same map extent, UTM 39N | Context totals may extend outside view\n(c) OpenStreetMap contributors, ODbL 1.0 | www.openstreetmap.org/copyright | Structural screening is not service certification.',fontsize=9)
fig.savefig(O/'dataset-overview.png',dpi=160,facecolor=fig.get_facecolor());plt.close(fig);c.close()
print(O/'dataset-overview.png')
