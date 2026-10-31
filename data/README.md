# Dataset: OSM-only public distribution

`tehran-osm-v1.1-public.zip` is the data artifact bundled in this repository
as numbered `*.zip.part001`, `*.zip.part002`, … volumes. The verifier checks
each part and automatically joins them into the original ZIP on first run.
Its identity and SHA-256 are in [release.json](release.json); the inventory and
individual file hashes are in [manifest.json](manifest.json) and inside the ZIP.

```bash
python scripts/verify_dataset.py
python scripts/verify_dataset.py --extract
```

The second command extracts to ignored `data/extracted/<dataset_id>/`, refuses
to overwrite an existing extraction, and verifies SQLite integrity/layer counts.
The extracted GeoPackage is larger than 100 MiB; only the compressed archive
volumes are tracked. The joined ZIP and extracted files are ignored. A standard
clone includes all volumes; no Git LFS account or third-party download is required.

## Scope

- Dataset ID: `tehran-osm-20261029T212126Z-v1.1-public`.
- Parent: local mixed-source `tehran-osm-20261029T212126Z-v1.1`.
- Source: OpenStreetMap contributors, distributed by Geofabrik Iran.
- OSM snapshot: **2026-10-29 21:21:26 UTC**.
- City boundary: OSM relation **6663864**, with 22 municipal districts.
- Context rectangle: `[50.9, 35.4, 51.95, 36.05]` (west, south, east, north).
- Coordinates: EPSG:4326; metric preparation uses EPSG:32639.
- Database license: **ODbL 1.0**, © OpenStreetMap contributors.

## Included layers

| GeoPackage layer | Records |
|---|---:|
| `city_boundary` | 1 |
| `municipal_districts` | 22 |
| `roads_context` | 218,322 |
| `buildings_city` | 65,677 |
| `hospital_candidates` | 321 |
| `hospital_screened_candidates` | 321 |
| `transit_active_member_geometry` | 361 |
| `transit_gap_diagnostics` | 427 |

The archive also includes the unchanged OSM context PBF, GeoJSON boundaries,
CSV inventories, route–street membership, derived route ordering, restriction
audits and exception registries. The raw PBF contains 2,081,117 nodes,
365,896 ways and 4,016 relations. Road-way counts are not routing-edge counts.

Of the transit inventory, 39 bus and 14 rail **relations** pass the strict
structural screen; these are not certified operating lines. Hospital screening
labels 249 features as human-hospital candidates in 244 possible groups, not
244 independently verified institutions. Inspect statuses before analysis.

## Public versus local release

This is a **derived public distribution**, not the original local archive under
a new filename. Three historical GeoPackage layers, historical CSV/SQLite data,
reference-derived crosswalks, and external hospital website-evidence fields were
removed. The GeoPackage was vacuumed after removal; no dropped historical pages
are intentionally retained. Original OSM geometry and the raw PBF were preserved.
New checksums identify this distribution. See [provenance](../docs/provenance.md).

Missing operational schedules, passenger flows and verified entrances are not
filled synthetically. The public dataset is a source for the planned structural
model; it is not a ready-made operational routing engine.
