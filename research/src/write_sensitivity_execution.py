"""Inventory a completed census and its explicitly recorded UTC start time."""
import argparse
import datetime
import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

from .accessibility import ROOT


def source_sha256_lf(path):
    """Portable source identity: normalize only CRLF line endings to LF."""
    return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def run(started_utc):
    start=datetime.datetime.fromisoformat(started_utc)
    if start.tzinfo is None:raise ValueError('A timezone-aware, genuinely recorded census start is required')
    out=ROOT/'research/reports/sensitivity-2026-11-01'
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    protocol=json.loads((ROOT/'research/config/sensitivity-protocol.json').read_text())
    summaries=sorted((out/'variants').glob('*/summary.json'))
    expected={r['id'] for r in protocol['variants']}|{'whole-osm-way'}
    assert {p.parent.name for p in summaries}==expected
    assert all(json.loads(p.read_text())['status']=='passed' for p in summaries)
    assert start.timestamp()<=min(p.stat().st_mtime for p in summaries)
    code=['sensitivity_runs.py','compiled_compact.py','compact_accessibility.py','accessibility.py','pair_closures.py']
    report={'status':'completed','census_started_utc':start.astimezone(datetime.timezone.utc).isoformat(),
        'last_variant_written_utc':datetime.datetime.fromtimestamp(max(p.stat().st_mtime for p in summaries),datetime.timezone.utc).isoformat(),
        'osm_snapshot_utc':'2026-10-29T21:21:26Z','protocol_sha256':sha(ROOT/'research/config/sensitivity-protocol.json'),
        'source_code_sha256':{n:sha(ROOT/'research/src'/n) for n in code},
        'source_code_lf_sha256':{n:source_sha256_lf(ROOT/'research/src'/n) for n in code},
        'source_identity_policy':'Retain raw evaluated-source hashes; cross-platform verification uses only CRLF-to-LF normalization. Dataset and result artifact hashes remain exact byte hashes.',
        'requirements_sha256':{n:sha(ROOT/n) for n in ['requirements-research.txt','requirements-validation.txt']},
        'variant_summary_sha256':{p.parent.name:sha(p) for p in summaries},
        'python':sys.version,'platform':platform.platform(),
        'package_versions':{n:importlib.metadata.version(n) for n in ['numpy','numba','scipy','shapely','pyproj','matplotlib','osmium']},
        'physical_pair_scenarios_over_variants':sum(json.loads(p.read_text())['physical_pair_count'] for p in summaries),
        'receipt_writer_sha256':sha(Path(__file__)),
        'note':'Complete declared finite domains, not all possible subsets of failed streets. Last output timestamp is read from the finished census files; preserve it before copying/regenerating outputs.'}
    (out/'execution.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--census-started-utc',required=True)
    run(parser.parse_args().census_started_utc)
