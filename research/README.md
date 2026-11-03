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

## Completed full-validation controls

The [closure report](reports/validation-closure.en.md) records the all-way and
all-segment preservation census, all-scenario compact/full-node comparison and
final exclusions for all 28 previously flagged bus relations. Published numerical
results are unchanged. Reproduce the controls with:

```bash
python -m pip install -r requirements-validation.txt
python -m research.src.audit_all_lengths
python -m research.src.resolve_route_exclusions
python -m research.src.audit_all_solvers
python -m research.src.verify_full_validation
python -m research.src.make_validation_report
```

The full solver census runs every failed set without sampling and can take
substantial time. The full-node reference is compiled with Numba; it retains
float64 and the original node-level recurrence. CI verifies all frozen evidence
tables and the complete unit suite; it does not rerun the long census on every
commit. Route exclusions are eligibility decisions under the strict primary
contract, not source repairs or claims that the excluded services do not run.

## Completed path and registered sensitivity stage

The [English technical record](reports/path-sensitivity.en.md) contains every
registered extreme/negative-benefit case, 7,155 replayable origin/state
certificates, 18 common-domain OAT variants and the separate 310-way experiment.
Every variant includes its full single/pair domain, all W/K settings and both
mode sets. The registered variants together cover 25,555,443 physical-pair
scenarios. Eleven standalone editable SVGs accompany the record.

```bash
python -m research.src.prepare_sensitivity_models
python -m research.src.audit_compact_compilation
python -m research.src.decompose_interactions
python -m research.src.path_witnesses
python -m research.src.audit_path_witnesses
CENSUS_STARTED_UTC=$(python -c "from datetime import datetime,timezone; print(datetime.now(timezone.utc).isoformat())")
python -m research.src.sensitivity_runs
python -m research.src.audit_sensitivity
python -m research.src.write_sensitivity_execution --census-started-utc "$CENSUS_STARTED_UTC"
python -m research.src.make_path_figures
python -m research.src.make_sensitivity_report
python -m research.src.verify_sensitivity_evidence
python -m unittest discover -s tests -v
```

The full sequence is for a clean evidence workspace; preserve the distributed
frozen result folder before regenerating it. To check the published evidence
without repeating the long census, run `verify_sensitivity_evidence` only.
The six network builds are reproducible under ignored `research/model/`;
their configurations, build/geometry receipts and expanded-route order tables
are public. Frozen receipts preserve their byte hashes across checkouts.
Use `prepare_sensitivity_models --reuse-verified` to inventory existing builds.

Completeness is scoped to the declared experiments. The subsequent
[structural record](reports/structural-comparisons.en.md) completes the full
centrality/road-class/dependency comparator grid, all component/district/target
counts and all physical-pair feature associations. Conference claim/figure
selection and manuscript preparation remain next. Larger multi-segment failures,
equal-length failure budgets and combined-assumption experiments are unexecuted
optional extensions.


## Completed exact structural and descriptive stage

The [English report](reports/structural-comparisons.en.md) and
[evidence directory](reports/structural-2026-11-02/README.md) describe every
primary unit/pair, the complete uniform-junction corridor benchmark, all
components/districts/possible hospital groups and all 300 accepted-route overlaps.
Six editable SVG figures link to exact source tables. Run from a prepared
M1/M2 workspace:

```bash
python -m research.src.structural_centrality --build
python -m research.src.structural_blocks
python -u -m research.src.structural_blocks --run
python -m research.src.network_descriptives
python -m research.src.route_structure
python -m research.src.audit_route_structure
python -m research.src.structural_comparisons --pairs --singles
python -m research.src.export_structural_graph
python -m research.src.audit_structural --geometry --descriptives --centrality
python -m research.src.structural_figures
python -m research.src.write_structural_report
python -m research.src.verify_structural_evidence --freeze
```

Preserve the distributed frozen evidence before a clean rerun. Centrality is a
long exact calculation with atomic resumable checkpoints; run one instance and
do not rebuild its graph or change its source while it runs. The block method
aggregates all original junction OD demand exactly, rather than sampling it.
It retains every component and every positive physical geometry link. It is not
a legal driving or traffic model. Source mapping is sharded only to keep file
sizes manageable; every original occurrence remains in the ordered index.

To check published output without rerunning the long census, use
`python -m research.src.verify_structural_evidence`. The verification checks
public graph/mass/task identities, all target masks, district losses, rankings
and vector sources. The long centrality execution and full geometry/full-node
replays are distinguished from the checks actually repeated in CI. With a
rebuilt M1/M2 model, `python -m research.src.audit_route_structure --check-only`
also independently replays every route overlap without overwriting frozen
receipts.


## Literature positioning and manuscript claims

The [English claim plan](paper/literature-and-claims.en.md) records a targeted
21-record review, exact access/version limits, C1-C6, rejected novelty claims,
reviewer objections and selected source SVGs. The evidence builder only reads
existing frozen output; it adds no analytical records or simulations:

```bash
python research/paper/build_claim_evidence.py --check
```

It reconciles all 510,066 mechanism rows, every W/K/mode result and physical
multiplicity, and separates 16,289 identical-signature pairs from the 1,400,797
distinct-signature pairs. The main claim selection emphasizes shared versus
joint-only losses, their cancellation, traceable modal effects and sensitivity.
Weak centrality agreement and route-aware modeling are explicitly recognized as
precedented. The next writing work is Data/Model, Methods and Results; final
conference layout and submission review remain open.
