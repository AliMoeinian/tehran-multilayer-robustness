"""Rebuild six declared OAT models, or verify and inventory existing builds."""
import argparse
import hashlib
import json
from pathlib import Path

from .accessibility import ROOT
from . import extract_routes,build_connections,audit_all_lengths


def run(reuse_verified=False):
    out=ROOT/'research/reports/sensitivity-2026-11-01';receipts=[]
    for name in ['shared-250','tie-min','tie-max','centroid','extended','derived']:
        cfg=ROOT/f'research/config/sensitivity-models/{name}.json'
        data=json.loads(cfg.read_text());m1=ROOT/data['output_directory']
        m2=ROOT/f'research/model/sensitivity/m2-{name}'
        evidence=out/'model-audits'/name
        if not reuse_verified:
            extract_routes.run(cfg)
            build_connections.run(cfg,250 if name=='shared-250' else 100,m2)
            audit_all_lengths.run(m2/'network.sqlite',evidence)
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        first=json.loads((m1/'summary.json').read_text());second=json.loads((m2/'summary.json').read_text())
        lengths=json.loads((evidence/'all-lengths.json').read_text())
        assert first['config_sha256']==second['config_sha256']==sha(cfg)
        assert lengths['status']=='passed' and lengths['network_sha256']==sha(m2/'network.sqlite')
        assert lengths['all_way_table_sha256']==sha(evidence/'all-way-lengths.csv.gz')
        # Preserve component receipts and route-order evidence for both expanded
        # route assumptions; primary/tie/centroid stop tables are reproducible.
        for stage,source in [('m1',m1/'summary.json'),('m2',m2/'summary.json')]:
            (evidence/f'{stage}-summary.json').write_text(source.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
        if name in ['extended','derived']:
            for filename in ['routes.csv','stops.csv','connections.csv']:
                (evidence/filename).write_text((m1/filename).read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
        receipts.append({'model':name,'config_sha256':sha(cfg),'network_sha256':lengths['network_sha256'],
            'candidate_routes':second['candidate_routes'],'walking_edges':second['walking_edges'],
            'accepted_buildings':second['connectors_by_kind']['building'].get('geometric_candidate',0),
            'target_features':second['connectors_by_kind']['hospital'].get('geometric_candidate',0),
            'geometry_status':lengths['status'],'evidence_sha256':{p.name:sha(p) for p in evidence.iterdir() if p.is_file()}})
    report={'status':'passed','models':receipts,'all_models_built_and_all_way_length_audits_passed':True,
        'source_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'builder_source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(extract_routes.__file__),Path(build_connections.__file__),Path(audit_all_lengths.__file__)]}}
    (out/'model-builds.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reuse-verified',action='store_true');run(p.parse_args().reuse_verified)
