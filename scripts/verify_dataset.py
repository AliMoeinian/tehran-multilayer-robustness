"""Verify the bundled OSM-only distribution using only the Python standard library."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import zipfile

ROOT = Path(__file__).resolve().parents[1]
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", action="store_true", help="Extract once to ignored data/extracted/")
    args = parser.parse_args()
    receipt = json.loads((ROOT / "data/release.json").read_text())
    archive = ROOT / "data" / receipt["archive"]
    if receipt.get("parts"):
        for part in receipt["parts"]:
            path = ROOT / "data" / part["file"]
            assert path.stat().st_size == part["bytes"], path.name
            with path.open("rb") as f:
                assert hashlib.file_digest(f, "sha256").hexdigest() == part["sha256"], path.name
        if not archive.exists():
            temporary = archive.with_suffix(".assembling")
            with temporary.open("wb") as out:
                for part in receipt["parts"]:
                    with (ROOT / "data" / part["file"]).open("rb") as src:
                        shutil.copyfileobj(src, out)
            with temporary.open("rb") as f:
                assert hashlib.file_digest(f, "sha256").hexdigest() == receipt["sha256"]
            temporary.replace(archive)
    with archive.open("rb") as f:
        assert hashlib.file_digest(f, "sha256").hexdigest() == receipt["sha256"], "Archive hash mismatch"
    assert archive.stat().st_size == receipt["bytes"]
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None, "ZIP CRC failed"
        prefix = receipt["dataset_id"] + "/"
        manifest = json.loads(z.read(prefix + "manifest.json"))
        assert set(z.namelist()) == {prefix + p for p in manifest["files"]} | {prefix + "manifest.json"}
        for name, metadata in manifest["files"].items():
            raw = z.read(prefix + name)
            assert len(raw) == metadata["bytes"], name
            assert hashlib.sha256(raw).hexdigest() == metadata["sha256"], name
        if args.extract:
            target = ROOT / "data/extracted" / receipt["dataset_id"]
            if target.exists():
                raise FileExistsError(f"Refusing to overwrite: {target}")
            target.mkdir(parents=True)
            # All names are checked against our manifest; no arbitrary archive paths.
            for name in list(manifest["files"]) + ["manifest.json"]:
                path = target / name
                if path.parent != target:
                    raise ValueError("Unexpected nested/path-traversal name")
                with z.open(prefix + name) as src, path.open("wb") as out:
                    shutil.copyfileobj(src, out)
            uri = (target / "tehran_audited_layers.gpkg").as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True) as db:
                assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                actual = {t: db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for (t,) in db.execute("SELECT table_name FROM gpkg_contents").fetchall()}
                assert actual == manifest["layers"]
            db.close()
            print("Extracted to", target.relative_to(ROOT))
    inventory = json.loads((ROOT / "provenance/source-scripts/inventory.json").read_text())
    for item in inventory:
        path = ROOT / "provenance/source-scripts" / item["file"]
        with path.open("rb") as f:
            assert hashlib.file_digest(f, "sha256").hexdigest() == item["sha256"], item["file"]
    print("PASS: archive identity, CRC, member inventory, data hashes and archived-source hashes")
    print("Dataset:", manifest["dataset_id"], "| Layers:", len(manifest["layers"]))


if __name__ == "__main__":
    main()
