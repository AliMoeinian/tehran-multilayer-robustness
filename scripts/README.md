# Supported commands and code scope

Run commands from the repository root with Python 3.11+.

## Current portable tools

```bash
python scripts/verify_dataset.py
python scripts/verify_dataset.py --extract
```

Verification/extraction uses the standard library only. It verifies the numbered
archive volumes and joins the exact original ZIP automatically, then checks its
hash, CRC, complete member inventory and every file hash. Extraction additionally
checks SQLite integrity and GeoPackage layer counts. Existing extracted data is
never overwritten. These checks do not certify real-world transit operations.

To regenerate the overview after extraction:

```bash
python -m pip install -r requirements-research.txt
python scripts/preview_dataset.py
```

The map is an OSM-only preview, not a simulation result. It uses no web tiles.

## Publication packaging

`build_public_dataset.py` packages an existing complete local v1.1 directory:

```bash
python scripts/build_public_dataset.py --source /path/to/local/tehran_dataset_v1_1 --output /path/to/new/output
```

It refuses to overwrite an archive and never modifies the input. It requires
the complete frozen parent, which is not bundled here. It performs no download,
geocoding or new OSM extraction. Public archive hashes are supplied separately.

## Archived construction logic

`provenance/source-scripts/` contains selected exact original scripts for source
selection/reference closure, boundary/geometry audits, road/building/hospital
derivation, restrictions, route ordering and local v1.1 enrichment. See its
README and SHA-256 inventory. This is an auditable historical implementation,
not the future research model. Some scripts depend on local intermediates or
the excluded historical database. Do not treat the archive as a working CLI.

No credentials, vendored dependencies, scratch downloads, copied papers or
experimental model output are committed. Follow `TODO.md` for implementation.
