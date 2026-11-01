"""Read-back checks for M2, including sampled independent source-length checks."""
import json
from pathlib import Path
import sqlite3

from pyproj import Transformer
import shapely
from shapely.ops import transform

from research.src.extract_routes import ROOT, csv_rows


def run():
    output=ROOT/'research/model/m2-v2'
    db=sqlite3.connect((output/'network.sqlite').as_uri()+'?mode=ro',uri=True)
    assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
    assert db.execute('select count(*) from walk_edges where length_m<0').fetchone()[0]==0
    missing=db.execute("select count(*) from connectors c where status='geometric_candidate' and not exists(select 1 from walk_edges w where w.u=c.anchor or w.v=c.anchor)").fetchone()[0]
    assert missing==0
    discrepancies=db.execute('''select t.connection_id from transit_connections t
        left join bus_dependencies b on b.connection_id=t.connection_id
        where t.mode='bus' group by t.connection_id
        having abs(coalesce(sum(b.overlap_m),0)-t.length_m)>0.00001''').fetchall()
    assert not discrepancies
    assert db.execute('''select count(*) from bus_dependencies b
      left join transit_connections t on t.connection_id=b.connection_id
      where t.connection_id is null or t.mode!='bus' or b.overlap_m<=0''').fetchone()[0]==0
    roles={f"stop:{s['route_relation_id']}:{s['stop_sequence']}":s['role'] for s in
           csv_rows(ROOT/'research/model/m1-v1/stops.csv')}
    for entity,board,alight in db.execute("select entity,board_allowed,alight_allowed from connectors where kind='stop'"):
        role=roles[entity]
        assert bool(board)==(not role.endswith('exit_only'))
        assert bool(alight)==(not role.endswith('entry_only'))
    cfg=json.loads((ROOT/'research/config/baseline.json').read_text())
    gpkg=ROOT/'data/extracted'/cfg['dataset_id']/'tehran_audited_layers.gpkg'
    src=sqlite3.connect(gpkg.as_uri()+'?mode=ro',uri=True)
    project=Transformer.from_crs(4326,32639,always_xy=True).transform
    sample=[]
    ids=[r[0] for r in db.execute('select distinct osm_way_id from walk_edges order by osm_way_id limit 20')]
    for wid in ids:
        blob=src.execute('select geom from roads_context where osm_id=?',(wid,)).fetchone()[0]
        source_length=transform(project,shapely.from_wkb(blob[40:])).length
        graph_length=db.execute('select sum(length_m) from walk_edges where osm_way_id=?',(wid,)).fetchone()[0]
        assert abs(source_length-graph_length)<1e-5
        sample.append({'way_id':wid,'source_length_m':source_length,'graph_length_m':graph_length})
    report={'status':'pass','scope':'full stored graph integrity, anchors, bus interval length consistency, permissions; 20 sampled source way lengths',
            'dangling_accepted_anchors':missing,'dependency_length_discrepancies':len(discrepancies),
            'sampled_source_way_lengths':sample,'not_certified':['entrances','barriers','current service','accessibility solver']}
    src.close();db.close()
    (output/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='sampled_source_way_lengths'},indent=2))


if __name__=='__main__':run()
