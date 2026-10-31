"""Make the OSM-only distribution from the frozen, mixed-source local v1.1.

The input is never modified. The historical reference and all its derived tables
are deliberately excluded. This is packaging, not a new OSM extraction pipeline.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import zipfile

PUBLIC_ID = "tehran-osm-20261029T212126Z-v1.1-public"
ARCHIVE_NAME = "tehran-osm-v1.1-public.zip"
REMOVE_FIELDS = {"external_evidence", "external_source_url", "external_page_date"}
HISTORICAL_LAYERS = {
    "bus_reference_shapes_2024", "historical_bus_stops_2024",
    "historical_route_stops_2024",
}
FILES = [
    "tehran_context.osm.pbf", "tehran_city_osm_boundary.geojson",
    "tehran_22_districts_osm.geojson", "city_district_gap.geojson",
    "road_inventory.csv", "buildings_city.csv", "building_exceptions.csv",
    "hospital_candidates.csv", "bus_road_dependencies.csv",
    "transit_routes.csv", "transit_paths.csv", "transit_gap_diagnostics.csv",
    "turn_restrictions.csv", "turn_restrictions_via_node_screened.csv",
    "building_assembly_audit.json", "geometry_and_hospital_exceptions.json",
    "unclosed_area_tags.json", "nonpolygon_building_relations.json",
    "line5_addition.json", "reference_integrity.json", "extraction_receipt.json",
    "transit_reordering_log.json", "boundary_audit.json",
]


def sha256(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def build(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents:
        raise ValueError("Output must be outside the frozen input directory")
    parent = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if parent["dataset_id"] != "tehran-osm-20261029T212126Z-v1.1":
        raise ValueError("Expected frozen v1.1 input")
    for name in FILES + ["tehran_audited_layers.gpkg", "hospital_screening_registry.csv", "transit_review_summary.json"]:
        if sha256(source / name) != parent["files"][name]["sha256"]:
            raise ValueError(f"Input hash mismatch: {name}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tehran-public-") as tmp:
        package = Path(tmp) / PUBLIC_ID
        package.mkdir()
        for name in FILES:
            shutil.copyfile(source / name, package / name)
        with (source / "hospital_screening_registry.csv").open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fields = [k for k in reader.fieldnames if k not in REMOVE_FIELDS]
            with (package / "hospital_screening_registry.csv").open("w", encoding="utf-8-sig", newline="") as out:
                writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(reader)
        summary = json.loads((source / "transit_review_summary.json").read_text(encoding="utf-8"))
        summary = {k: summary[k] for k in ["routes", "deterministically_reordered_relations", "gap_diagnostic_links", "line5_included"]}
        (package / "transit_review_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        db_path = package / "tehran_audited_layers.gpkg"
        shutil.copyfile(source / db_path.name, db_path)
        with sqlite3.connect(db_path) as db:
            db.execute("PRAGMA secure_delete=ON")
            for table in HISTORICAL_LAYERS:
                db.execute(f'DROP TABLE "{table}"')
                db.execute("DELETE FROM gpkg_contents WHERE table_name=?", (table,))
                db.execute("DELETE FROM gpkg_geometry_columns WHERE table_name=?", (table,))
                db.execute("DELETE FROM sqlite_sequence WHERE name=?", (table,))
            for fid, raw in db.execute("SELECT fid,attributes_json FROM hospital_screened_candidates").fetchall():
                attrs = json.loads(raw)
                for key in REMOVE_FIELDS:
                    attrs.pop(key, None)
                db.execute("UPDATE hospital_screened_candidates SET attributes_json=? WHERE fid=?", (json.dumps(attrs, ensure_ascii=False), fid))
            db.commit()
            # DROP alone leaves old page contents; VACUUM physically rebuilds DB.
            db.execute("VACUUM")
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert db.execute("PRAGMA freelist_count").fetchone()[0] == 0
            layers = {t: db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for (t,) in db.execute("SELECT table_name FROM gpkg_contents").fetchall()}
        db.close()
        notice = """# Tehran OSM-only public dataset

Derived distribution of local v1.1, not a byte-identical copy of its mixed-source archive.
Contains OpenStreetMap data (c) OpenStreetMap contributors, distributed by Geofabrik.
Database license: Open Database License 1.0 (ODbL).
https://opendatacommons.org/licenses/odbl/1-0/
https://www.openstreetmap.org/copyright

OSM snapshot: 2026-10-29T21:21:26Z. City relation: 6663864; 22 districts.
Context bbox: [50.9, 35.4, 51.95, 36.05]. Geometry CRS: EPSG:4326.
Distances and areas in the source audits use EPSG:32639.

IranTracking historical shapes, stations, station-order tables, crosswalks and
historical diagnostics are NOT included: redistribution permission is unestablished.
External hospital website evidence fields are also removed.
Raw OSM PBF and retained source geometry are unchanged; GeoPackage was rebuilt
after removing three historical layers and external hospital evidence attributes.
All feature counts are records, not certified distinct operating facilities/lines.
Quality flags remain. There is no completed travel-routing model or simulation result.
The full national Iran source is identified by hash but is not bundled.
"""
        (package / "README.md").write_text(notice, encoding="utf-8")
        manifest = {
            "dataset_id": PUBLIC_ID,
            "parent_dataset_id": parent["dataset_id"],
            "parent_manifest_sha256": sha256(source / "manifest.json"),
            "public_distribution": "OSM-only; historical reference excluded",
            "data_timestamp_utc": parent["data_timestamp_utc"],
            "source": "OpenStreetMap contributors via Geofabrik Iran",
            "license": "ODbL-1.0",
            "license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
            "attribution": "(c) OpenStreetMap contributors",
            "source_archive_sha256": parent["primary_source_archive_sha256"],
            "pbf_sha256": sha256(package / "tehran_context.osm.pbf"),
            "layers": layers,
            "removed_layers": sorted(HISTORICAL_LAYERS),
            "removed_hospital_fields": sorted(REMOVE_FIELDS),
            "files": {p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in sorted(package.iterdir())},
        }
        (package / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        target = output / ARCHIVE_NAME
        if target.exists():
            raise FileExistsError(target)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for p in sorted(package.iterdir()):
                # Fixed ZIP dates make packaging deterministic for identical inputs.
                info = zipfile.ZipInfo(f"{PUBLIC_ID}/{p.name}", (2026, 10, 31, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, p.read_bytes(), compresslevel=6)
        receipt = {"dataset_id": PUBLIC_ID, "archive": target.name, "bytes": target.stat().st_size, "sha256": sha256(target)}
        receipt["parts"] = split_archive(target)
        (output / "release.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return receipt


def split_archive(target, chunk_bytes=3 * 1024 * 1024):
    """Store small Git-friendly volumes; joining recreates the exact ZIP bytes."""
    parts = []
    with Path(target).open("rb") as src:
        while raw := src.read(chunk_bytes):
            path = Path(str(target) + f".part{len(parts) + 1:03d}")
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
            parts.append({"file": path.name, "bytes": len(raw), "sha256": sha256(path)})
    return parts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2))
