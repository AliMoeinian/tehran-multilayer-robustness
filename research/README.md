# Research implementation

For the cumulative English methods/results narrative and five publication-oriented
SVG figures, see [the progress report](reports/research-progress.en.md).
After reconstructing M1/M2, rebuild its figures and numeric tables with:

```bash
python -m research.src.make_progress_figures
```

The figure generator requires the frozen model identity used by the published
results. It writes SVGs, source rows and hashes under `research/figures/` and
ignored PNG review previews under `research/runs/progress-figure-preview/`.
It does not rerun or modify the underlying experiments.

## Exhaustive paired closures

The [paired-closure report](reports/paired-closures.en.md) covers every one of
1,417,086 physical street pairs, all nine W/K settings, and both mode sets.
After preparing the frozen model, reproduce it with:

```bash
python -m research.src.pair_closures --protocol research/config/pair-protocol.json --output research/runs/<new-complete-run> --workers 4
python -m research.src.audit_pairs --directory research/runs/<new-complete-run>
python -m research.src.make_pair_figures
```

The protocol requires exhaustive computation regardless of runtime. Exact
union grouping avoids repeated graph calculations and retains every physical
pair and signature-pair identity. The independent audit streams through every
physical pair and reconciles the full effect grid. CI audits the frozen complete
output and unit tests; it does not rerun the entire simulation on every commit.

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

Remaining work includes stop-area reconciliation and review of direction conflicts.
M2/M3 below build and solve the screened subset; current candidates are not a final model.
No transit operation, population demand or travel-time certification is inferred.

## M2: walking graph and dependencies

After the M1 module, run once per clean output directory:

```bash
python -m research.src.build_connections --connector-limit-m 100
```

`research/model/m2-v2/network.sqlite` contains undirected walking edges, geometric
connectors, directed consecutive-stop connections and bus dependency intervals.
All are derived from the same public OSM snapshot. Output refuses overwrite.
Walking graph and street slicing are implemented by M2; M3 adds the accessibility solver.

Connectors project to walking-way geometry and split its source segments at
the projected positions. Original OSM node identity is retained; crossings
without shared nodes do not become links. A source segment with distinct node
IDs and coincident coordinates is retained as a zero-length topological edge.
The straight geometric connector is a study convention, not verified access.
An equal-distance nearest-way tie currently selects one STRtree result; connector
sensitivity is required before interpreting results.

Stop entry-only/exit-only roles are stored as boarding/alighting permissions.
The M3 solver respects these fields; passing through a stop while
riding does not require alighting. Bus dependencies use the positive overlap
between the stop-to-stop trace interval and each original adjacent-node segment.
Endpoint touching alone does not create a dependency. The stored street key
combines OSM way ID and unordered node pair; distinct carriageways are not merged.

## M3: cumulative-walking accessibility

```bash
python -m research.src.accessibility --output research/runs/<new-run>
```

The solver computes exact minimum cumulative walking under an at-most boarding
budget, with directed riding and entry/exit constraints. First boarding is free
of line changes; every subsequent boarding, including reboarding the same route,
consumes another unit. Interchanges use walking and connector costs; no zero-cost
route reset is allowed. Vehicle motion has zero *walking* cost, not zero travel time.

The implementation uses reverse dynamic programming and incremental multi-source
Dijkstra. Search is truncated at the largest configured walking budget, so infinity
does not establish global disconnection. Buildings outside the connector contract
remain in the full denominator with no eligible model path. All parameter-grid
results and input hashes are saved, together with per-building costs in ignored runs.

The initial baseline is in `reports/m3-2026-11-01.md`.
Existing M1/M2 reports describe the implementation state at their own milestones.

## M3: exhaustive observed single closures

```bash
python -m research.src.single_closures --output research/runs/<new-closure-run>
```

For every observed source street segment supporting accepted bus connections,
remove all dependent consecutive-stop bus arcs. Walking and metro remain fixed;
no rerouting is introduced. This isolates the street-to-bus dependency mechanism.
It does not simulate a pedestrian blockage or an entire street corridor closure.
Street keys retain OSM way ID and adjacent node IDs; distinct carriageways remain
distinct. Segments outside accepted bus dependencies are outside this experiment.

Equal sets of failed connection IDs yield identical graphs and are computed once.
The street-to-signature mapping preserves every street unit, and all 9 W/K pairs
are evaluated both with and without metro. Results include absolute building losses
and shares with the full 65,677-building denominator. The difference in metro
benefit is `bus_loss - bus_metro_loss` and can have either sign.

The command verifies matching network/config hashes, reproduces the published M3
baseline, and checks nodewise monotonicity under deletion, added metro and larger
boarding budgets. It publishes no global disconnection or operational claims.
`effects.csv` has one row per signature and parameter pair; join `streets.csv` on
signature to recover per-street effects. `groups.json` lists failed connection IDs.
Generated output directories refuse overwrite. Published result copies and hashes
are in `reports/m3-single-closures-2026-11-01*`.
