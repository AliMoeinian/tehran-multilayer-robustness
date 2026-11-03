"""Check draft tables and links against frozen evidence; no network computation.

This checks the two marked numerical tables, local references and registered
literature links. It does not validate every prose sentence or rendered layout.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent


def tables(evidence):
    selected = {
        row['mode']: row for row in evidence['all_pair_mechanism_settings']
        if row['walking_budget_m'] == 1000 and row['max_line_changes'] == 1
    }
    lines = ['| Mechanism category | Bus | Bus + rail |', '| --- | ---: | ---: |']
    labels = [
        ('Shared only: S > 0, N = 0', 'shared_only'),
        ('Joint-only: N > 0, S = 0', 'new_only'),
        ('Both: N > 0, S > 0', 'both'),
        ('Neither: N = S = 0', 'neither'),
        ('Total physical pairs', 'pairs'),
        ('Balanced nonzero, N = S > 0: subset of both', 'balanced_nonzero'),
    ]
    for label, field in labels:
        lines.append(f"| {label} | {selected['bus'][field]:,} | {selected['bus_metro'][field]:,} |")
    result = {'MECHANISMS': '\n'.join(lines)}
    variants = {row['variant']: row['settings'] for row in evidence['selected_variant_full_grids']}
    lines = [
        '| Variant | Healthy bus | Healthy full | Max pair loss, bus | Max pair loss, full | Units with greater full single loss |',
        '| --- | ---: | ---: | ---: | ---: | ---: |',
    ]
    labels = [
        ('Primary contract', 'baseline'), ('Connector limit 25 m', 'connector-25m'),
        ('Connector limit 250 m', 'connector-250m'), ('Whole-relation failure', 'failure-whole-route'),
        ('Emergency-tag targets', 'targets-emergency-tag'),
        ('Inside-city human targets', 'targets-human-inside'),
        ('Semantic route extension', 'routes-semantic-extension'),
        ('Geometric derived order', 'routes-derived-order'),
    ]
    for label, name in labels:
        row = next(r for r in variants[name] if r['walking_budget_m'] == 1000 and r['max_line_changes'] == 1)
        values = [row['bus']['baseline_accessible'], row['bus_metro']['baseline_accessible'],
                  row['bus']['maximum_joint_loss'], row['bus_metro']['maximum_joint_loss'],
                  row['units_with_higher_absolute_loss_with_metro']]
        lines.append('| ' + label + ' | ' + ' | '.join(f'{v:,}' for v in values) + ' |')
    result['SENSITIVITY'] = '\n'.join(lines)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update-tables', action='store_true', help='Deliberately replace only marked tables; review the diff.')
    args = parser.parse_args()
    evidence = json.loads((HERE / 'claim-evidence.json').read_text(encoding='utf-8'))
    path = HERE / 'manuscript.en.md'
    text = path.read_text(encoding='utf-8')
    for name, table in tables(evidence).items():
        start, end = f'<!-- BEGIN MANUSCRIPT_{name} -->', f'<!-- END MANUSCRIPT_{name} -->'
        assert text.count(start) == text.count(end) == 1, name
        pattern = re.escape(start) + r'\n(.*?)\n' + re.escape(end)
        found = re.search(pattern, text, re.S)
        assert found is not None, name
        if args.update_tables:
            text = text[:found.start(1)] + table + text[found.end(1):]
        else:
            assert found.group(1) == table, f'{name}: table differs from frozen claim evidence'
    if args.update_tables:
        path.write_text(text, encoding='utf-8', newline='\n')
    records = json.loads((HERE / 'literature-register.json').read_text(encoding='utf-8'))['records']
    registered_urls = {r[field] for r in records for field in ['url', 'inspected_url'] if r.get(field)}
    local_count = literature_count = 0
    for target in re.findall(r'\]\(([^)]+)\)', text):
        if target.startswith('https://'):
            if target.startswith(('https://doi.org/', 'https://arxiv.org/')):
                assert target in registered_urls, f'Unregistered literature URL: {target}'
                literature_count += 1
            continue
        local = unquote(target.split('#', 1)[0])
        assert local and (HERE / local).is_file(), f'Missing local reference: {target}'
        local_count += 1
    assert text.count('```') % 2 == 0, 'Unclosed fenced block'
    sections = re.findall(r'^## (\d+)\.', text, re.M)
    assert sections == [str(i) for i in range(1, 9)], 'Incomplete or reordered draft sections'
    print(json.dumps({'status': 'passed', 'numerical_tables': 2,
                      'table_data_rows': 14, 'local_links': local_count,
                      'registered_literature_links': literature_count,
                      'scope': 'Marked tables, links and section structure; prose and rendering require editorial review.'}))


if __name__ == '__main__':
    main()
