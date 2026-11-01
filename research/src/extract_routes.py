"""M1: reconstruct screened route traces and audit recorded stop order.

No stop reordering, invented links, street rerouting or operational certification.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import osmium
from pyproj import Transformer
from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parents[2]


def project_stop(point, coordinates, distance_tolerance=1, separation=20):
    """Project on every segment; detect separated, similarly near occurrences."""
    coordinates = np.asarray(coordinates, dtype=float)
    start, vector = coordinates[:-1], np.diff(coordinates, axis=0)
    squared = (vector * vector).sum(axis=1)
    lengths = np.sqrt(squared)
    fractions = np.clip(((np.asarray(point) - start) * vector).sum(axis=1) /
                        np.where(squared > 0, squared, 1), 0, 1)
    projected = start + fractions[:, None] * vector
    distances = np.linalg.norm(projected - point, axis=1)
    progress = np.r_[0, np.cumsum(lengths)[:-1]] + fractions * lengths
    best = int(np.argmin(distances))
    near = progress[distances <= distances[best] + distance_tolerance]
    return float(distances[best]), float(progress[best]), bool(np.ptp(near) > separation)


def ordered(progress, tolerance=1):
    return all(b >= a - tolerance for a, b in zip(progress, progress[1:]))


def order_status(progress, tolerance=1):
    if ordered(progress, tolerance):
        return "forward"
    if ordered([-x for x in progress], tolerance):
        return "opposes_trace"
    return "mixed"


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, records):
    if not records:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def run(config):
    cfg = json.loads(config.read_text(encoding="utf-8"))
    data = ROOT / "data/extracted" / cfg["dataset_id"]
    pbf = data / "tehran_context.osm.pbf"
    if not pbf.exists():
        raise FileNotFoundError("Run python scripts/verify_dataset.py --extract first")
    manifest = json.loads((data / "manifest.json").read_text())
    for name in ["tehran_context.osm.pbf", "transit_routes.csv", "transit_paths.csv"]:
        with (data / name).open("rb") as f:
            actual = hashlib.file_digest(f, "sha256").hexdigest()
        if actual != manifest["files"][name]["sha256"]:
            raise ValueError("Input identity mismatch: " + name)
    inventory = {int(r["relation_id"]): r for r in csv_rows(data / "transit_routes.csv")
                 if r["status"] == cfg["route_status"]}
    paths = collections.defaultdict(list)
    for row in csv_rows(data / "transit_paths.csv"):
        if int(row["route_relation_id"]) in inventory:
            paths[int(row["route_relation_id"])].append(row)

    class Relations(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.members = {}

        def relation(self, r):
            if r.id in inventory:
                self.members[r.id] = [(m.type, m.ref, m.role) for m in r.members]

    relations = Relations()
    relations.apply_file(str(pbf))
    needed = {int(r["way_id"]) for seq in paths.values() for r in seq}
    member_nodes, member_ways = set(), set()
    for members in relations.members.values():
        for typ, ident, role in members:
            if typ == "n":
                member_nodes.add(ident)
            elif typ == "w":
                member_ways.add(ident)

    needed_way_ids = needed | member_ways

    class Geometry(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.nodes, self.ways = {}, {}

        def node(self, n):
            if n.id in member_nodes:
                self.nodes[n.id] = ((n.location.lon, n.location.lat), dict(n.tags))

        def way(self, w):
            if w.id in needed_way_ids:
                self.ways[w.id] = (tuple(n.ref for n in w.nodes),
                                   [(n.lon, n.lat) for n in w.nodes], dict(w.tags))

    geometry = Geometry()
    geometry.apply_file(str(pbf), locations=True, idx="flex_mem")
    transform = Transformer.from_crs(4326, cfg["metric_crs"], always_xy=True)
    stop_rows, route_rows, connection_rows, traces = [], [], [], {}
    for rid, row in sorted(inventory.items()):
        flags, node_ids, coords = [], [], []
        way_for_edge = []
        seq = sorted(paths[rid], key=lambda r: int(r["sequence"]))
        for part in seq:
            nodes, points, _ = geometry.ways[int(part["way_id"])]
            if int(part["direction"]) == -1:
                nodes, points = nodes[::-1], points[::-1]
            if node_ids and node_ids[-1] != nodes[0]:
                flags.append("trace_endpoint_gap")
            node_ids.extend(nodes if not node_ids else nodes[1:])
            coords.extend(points if not coords else points[1:])
            way_for_edge.extend([int(part["way_id"])] * (len(nodes)-1))
        if len(coords) < 2:
            flags.append("missing_trace")
            metric = None
        else:
            metric = np.column_stack(transform.transform(*np.array(coords).T))
            traces[str(rid)] = {"node_ids": node_ids, "xy_m": metric.tolist(),
                                "edge_way_ids": way_for_edge}
        candidates = {"stop": [], "platform": []}
        for member_index, (typ, ident, role) in enumerate(relations.members.get(rid, [])):
            if "inactive" in role:
                continue
            if typ == "n" and ident in geometry.nodes:
                point, tags = geometry.nodes[ident]
            elif typ == "w" and ident in geometry.ways:
                _, xy, tags = geometry.ways[ident]
                if len(xy) < 2:
                    continue
                p = LineString(xy).interpolate(.5, normalized=True)
                point = (p.x, p.y)  # Explicit geometric midpoint, not a verified entrance.
            else:
                if role.startswith(("stop", "platform")):
                    flags.append("unsupported_stop_member")
                continue
            kind = ("stop" if role.startswith("stop") else
                    "platform" if role.startswith("platform") else
                    "stop" if tags.get("public_transport") == "stop_position" else
                    "platform" if tags.get("highway") == "bus_stop" or
                    tags.get("public_transport") == "platform" or
                    tags.get("railway") in ("station", "halt") else None)
            if kind:
                candidates[kind].append((member_index, typ, ident, role, point))
        # Prefer stop positions; do not combine paired positions/platforms as two stops.
        kind = "stop" if len(candidates["stop"]) >= 2 else "platform"
        stops = candidates[kind]
        if len(stops) < 2:
            flags.append("fewer_than_two_stops")
        progress = []
        local_rows = []
        for index, (mi, typ, ident, role, point) in enumerate(stops):
            d, along, ambiguous = (project_stop(transform.transform(*point), metric,
                cfg["projection_distance_tolerance_m"], cfg["ambiguous_progress_separation_m"])
                if metric is not None else (float("inf"), float("inf"), True))
            if d > cfg["stop_distance_limit_m"]:
                flags.append("stop_far_from_trace")
            if ambiguous:
                flags.append("ambiguous_trace_projection")
            progress.append(along)
            local_rows.append({"route_relation_id": rid, "stop_sequence": index,
                "source_member_index": mi, "osm_type": typ, "osm_id": ident,
                "role": role, "stop_representation": kind, "longitude": point[0],
                "latitude": point[1], "distance_to_trace_m": d,
                "trace_progress_m": along, "ambiguous_projection": ambiguous})
        order = order_status(progress, cfg["stop_order_tolerance_m"])
        if order != "forward":
            flags.append("recorded_stop_order_" + order)
        if any(abs(b-a) <= cfg["stop_order_tolerance_m"] for a,b in zip(progress,progress[1:])):
            flags.append("consecutive_stops_same_progress")
        flags = sorted(set(flags))
        status = "candidate_for_walking_connection_audit" if not flags else "needs_review"
        for stop in local_rows:
            stop["route_status"] = status
        stop_rows.extend(local_rows)
        route_rows.append({"relation_id": rid, "mode": row["mode"], "ref": row["ref"],
            "status": status, "flags": ";".join(flags), "selected_stop_kind": kind,
            "selected_stops": len(stops), "stop_position_candidates": len(candidates["stop"]),
            "platform_candidates": len(candidates["platform"]), "trace_way_count": len(seq)})
        if not flags:
            for a, b in zip(local_rows, local_rows[1:]):
                connection_rows.append({"route_relation_id": rid,
                    "from_sequence": a["stop_sequence"], "to_sequence": b["stop_sequence"],
                    "from_progress_m": a["trace_progress_m"], "to_progress_m": b["trace_progress_m"],
                    "length_along_recorded_trace_m": b["trace_progress_m"]-a["trace_progress_m"]})
    out = (ROOT / cfg["output_directory"]).resolve()
    if not out.is_relative_to(ROOT / "research/model"):
        raise ValueError("Output must stay inside research/model")
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "routes.csv", route_rows)
    write_csv(out / "stops.csv", stop_rows)
    write_csv(out / "connections.csv", connection_rows)
    (out / "traces.json").write_text(json.dumps(traces), encoding="utf-8")
    summary = {"config_version": cfg["config_version"], "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "dataset_id": cfg["dataset_id"], "input_routes": len(inventory),
        "route_status_by_mode": {mode: dict(collections.Counter(x["status"] for x in route_rows if x["mode"] == mode)) for mode in ["bus", "metro"]},
        "flag_counts": dict(collections.Counter(f for x in route_rows for f in x["flags"].split(";") if f)),
        "selected_stop_associations": len(stop_rows), "candidate_connections": len(connection_rows),
        "not_yet_implemented": ["walking connectors", "stop-area reconciliation", "street dependency slicing between stops", "accessibility solver", "simulation"],
        "meaning": "Recorded stop-order diagnostic; candidates are not a certified service or completed travel model."}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "research/config/baseline.json")
    run(parser.parse_args().config)
