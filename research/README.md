# Research implementation

This directory implements the research roadmap incrementally. The first module
audits the stop order on already structurally screened OSM route traces.

From the repository root:

```bash
python -m pip install -r requirements-research.txt
python scripts/verify_dataset.py --extract  # only if not yet extracted
python -m unittest discover -s tests -v
python -m research.src.extract_routes --config research/config/baseline.json
```

Output is written to ignored `research/model/m1-v1/`: route inventory, selected
stop associations, candidate consecutive-stop connections and a summary.
Compact, dated evidence in `research/reports/` is version-controlled separately.

## M1 conventions

- Only the strict 39 bus / 14 rail relations are inspected, from the public OSM
  snapshot. Raw input hashes are verified before reading.
- Way directions follow the existing derived path. Endpoint node continuity is
  checked; stops are never reordered to force agreement.
- Prefer recorded stop positions when at least two exist; otherwise use recorded
  platforms/legacy stop features. This avoids counting both representations as
  two stops, but is not a complete stop-area reconciliation algorithm.
- A way-platform is represented by its geometric line midpoint. It is not an
  entrance. Relation-valued stop members are explicitly flagged as unsupported.
- Stop-to-trace distances and progress use UTM 39N. Similarly near but widely
  separated projection occurrences are flagged instead of choosing a loop branch.
- A route is a candidate only if chosen stop order follows the trace, distance
  is within the configured limit, and no ambiguity or endpoint gap is found.
  The 100 m limit is a declared diagnostic convention, not calibrated validity.
- Opposite and mixed orders are distinguished. Neither proves an OSM error:
  route-member ordering or the earlier orientation selection may be responsible.

Remaining work includes stop-area reconciliation, review of direction conflicts,
walking connectors, exact street dependency slices between stops, the stateful
accessibility solver and simulation. Current candidates are not a final model.
No transit operation, population demand or travel-time certification is inferred.
