"""Verify frozen receipts without rerunning the long sensitivity census."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from .accessibility import ROOT
from .write_sensitivity_execution import source_sha256_lf


def run():
    out=ROOT/'research/reports/sensitivity-2026-11-01'
    protocol=ROOT/'research/config/sensitivity-protocol.json'
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    read=lambda p:json.loads(p.read_text())
    def hashes(folder,values):
        for name,digest in values.items():assert sha(folder/name)==digest,(folder,name)
    declaration=read(protocol);names=[r['id'] for r in declaration['variants']]+['whole-osm-way']
    primary=None;scenarios=0
    execution=read(out/'execution.json');assert execution['status']=='completed'
    assert execution['protocol_sha256']==sha(protocol)
    assert execution['receipt_writer_sha256']==sha(ROOT/'research/src/write_sensitivity_execution.py')
    assert execution['source_code_sha256'].keys()==execution['source_code_lf_sha256'].keys()
    for name,digest in execution['source_code_lf_sha256'].items():
        assert source_sha256_lf(ROOT/'research/src'/name)==digest,name
    hashes(ROOT,execution['requirements_sha256'])
    for name in names:
        folder=out/'variants'/name;r=read(folder/'summary.json');assert r['status']=='passed'
        hashes(folder,r['artifact_sha256']);assert r['protocol_sha256']==sha(protocol)
        assert sha(folder/'summary.json')==execution['variant_summary_sha256'][name]
        assert r['variant']['id']==name and r['all_buildings']==65677 and len(r['results'])==9
        assert {(q['max_line_changes'],q['walking_budget_m']) for q in r['results']}=={(k,w) for k in [0,1,2] for w in [500,1000,2000]}
        assert (r['unit_count'],r['physical_pair_count'])==((310,47895) if name=='whole-osm-way' else (1684,1417086))
        if primary is None:primary=r['origin_id_order_sha256']
        assert primary==r['origin_id_order_sha256'];scenarios+=r['physical_pair_count']
    models=read(out/'model-builds.json');assert models['status']=='passed' and len(models['models'])==6
    assert sha(ROOT/'research/src/prepare_sensitivity_models.py')==models['source_code_sha256']
    for r in models['models']:
        hashes(out/'model-audits'/r['model'],r['evidence_sha256'])
        assert sha(ROOT/'research/config/sensitivity-models'/(r['model']+'.json'))==r['config_sha256']
    hashes(ROOT/'research/src',models['builder_source_sha256'])
    kernel=read(out/'compiled-kernel-audit.json');assert kernel['status']=='passed'
    assert kernel['failed_sets_checked']==27857 and kernel['origin_budget_cells_checked']==14299778096 and kernel['maximum_absolute_difference_m']==0
    hashes(ROOT/'research/src',kernel['source_code_sha256'])
    paths=read(out/'path-summary.json');pa=read(out/'path-audit.json');assert paths['status']==pa['status']=='passed'
    hashes(out,paths['artifact_sha256']);hashes(out,pa['artifact_sha256'])
    assert sha(ROOT/'research/src/path_witnesses.py')==paths['source_code_sha256']
    assert sha(ROOT/'research/src/audit_path_witnesses.py')==pa['source_sha256']
    assert paths['origin_state_certificates']==pa['certificates_replayed']==7155
    assert pa['case_memberships_match_all_published_losses'] and pa['all_seven_negative_groups_same_13_extra_origins']
    mechanisms=read(out/'mechanism-summary.json');assert mechanisms['status']=='passed'
    assert sha(out/'all-pair-mechanisms.csv.gz')==mechanisms['table_sha256']
    assert mechanisms['signature_pair_mode_parameter_rows']==510066
    # Every packed single-loss mask reconciles with the published scalar losses.
    mask_index=read(out/'mask-index.json');mask_count=0
    assert len(mask_index['origins'])==len(set(mask_index['origins']))==64166
    with (ROOT/'research/reports/m3-single-closures-2026-11-01/effects.csv').open(newline='') as f:
        expected={(r['signature'],int(r['max_line_changes']),int(r['walking_budget_m'])):r for r in csv.DictReader(f)}
    with np.load(out/'single-loss-masks.npz') as masks:
        for g in mask_index['groups']:
            for k in [0,1,2]:
                for w in [500,1000,2000]:
                    row=expected[g['signature'],k,w]
                    for mode in ['bus','bus_metro']:
                        a=masks[f"g{g['group_index']}_{mode}_k{k}_w{w}"]
                        assert len(a)==(64166+7)//8
                        assert int(np.bitwise_count(a).sum())==int(row[mode+'_loss_buildings'])
                        assert np.unpackbits(a,bitorder='little')[64166:].sum()==0
                        mask_count+=1
        assert len(masks.files)==mask_count==4284
    audit=read(out/'sensitivity-audit.json');assert audit['status']=='passed' and audit['variants_checked']==19
    assert audit['total_physical_pairs_over_variants']==scenarios==25555443
    hashes(out,audit['artifact_sha256']);assert sha(ROOT/'research/src/audit_sensitivity.py')==audit['source_sha256']
    figure=ROOT/'research/figures/sensitivity-2026-11-02';svg_count=0
    for name in ['path-manifest.json','sensitivity-manifest.json']:
        r=read(figure/name);hashes(figure,r['svg_sha256'])
        if name=='path-manifest.json':hashes(out,r['sources'])
        else:hashes(ROOT,r['source_sha256'])
        source='make_path_figures.py' if name.startswith('path') else 'make_sensitivity_report.py'
        assert sha(ROOT/'research/src'/source)==r['source_code_sha256']
        for filename in r['svg_sha256']:
            tree=ET.parse(figure/filename);assert not tree.findall('.//{http://www.w3.org/2000/svg}image')
            assert tree.findall('.//{http://www.w3.org/2000/svg}text');svg_count+=1
    assert svg_count==11
    result={'status':'passed','variants':19,'physical_pairs_over_variants':scenarios,
        'packed_loss_masks_verified':mask_count,'path_certificates':7155,'editable_vector_figures':svg_count}
    print(json.dumps(result));return result


if __name__=='__main__':run()
