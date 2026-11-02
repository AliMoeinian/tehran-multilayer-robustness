# Structural-stage evidence

The [technical report](../structural-comparisons.en.md) defines the methods,
denominators and interpretation. The source dataset is the frozen public
`tehran-osm-20261029T212126Z-v1.1-public` distribution. No new transport,
population or clinical records enter these calculations.

| Files | Grain and meaning |
| --- | --- |
| `graph-inventory.json`, `block-inventory.json` | Full context corridor graph and exact block decomposition |
| `junction-vertices.csv.gz` | Every evaluated storage vertex, canonical native ID, OD flag and component |
| `junction-centrality.csv.gz` | Every chain, its endpoints/length and raw uniform-junction edge betweenness |
| `source-chain-index.json`, `source-chain-mapping/*.csv.gz` | Every original adjacent source occurrence and its physical-edge/chain IDs; repeated aliases are retained; ordered complete file parts bound publication file sizes |
| `block-attachment-masses.csv.gz` | Every block attachment and its projected original-OD mass |
| `centrality-source-census.csv.gz` | Every positive projected source in nontrivial blocks; bridge masses are checked separately |
| `bridge-centrality-audit.csv.gz` | Every bridge and the exact product of its two branch masses |
| `street-features.csv.gz`, `street-structural-comparators.csv.gz` | All 1,684 physical failure units; source geometry, dependencies and containing-chain score |
| `single-benchmark-*.csv.gz`, `single-loss-by-road-class.csv.gz` | Full comparator grids, tie-aware top sets, fixed length strata and nominal highway classes |
| `route-descriptions.csv.gz`, `route-pair-overlap.csv.gz` | All 25 accepted relations and all 300 distinct unordered relation pairs |
| `dependency-concentration.csv.gz` | Counts of primary units by bus-relation and stop-connection dependence |
| `model-components.csv.gz` | Every weak and strong component of each accepted mode graph, without walking/boarding budgets |
| `building-district-ownership.csv.gz`, `district-index.json` | Every original origin and its representative-point district; district 0 preserves source gaps |
| `district-baseline.csv.gz`, `district-single-losses.csv.gz`, `district-loss-summary.csv.gz` | Every owner/setting baseline, every failure-signature/owner/setting loss, and physical-unit-weighted summaries |
| `building-reachable-target-groups.csv.gz` | Every original origin's possible-destination-group count, for both modes, boarding layers 0–3 and walking budgets 500/1,000/2,000 m |
| `hospital-group-reachability-masks.npz`, `target-group-mask-index.json` | All 5,664 packed binary masks; group and origin order are explicitly indexed |
| `target-group-coverage.csv.gz` | Accessible-origin counts per possible destination group and setting |
| `pair-feature-associations.csv.gz`, `pair-feature-strata.csv.gz` | Complete physical-pair distance/shared-relation descriptions in every primary setting; not independent pair samples |
| `*-audit.json`, `all-corridor-*-audit.csv.gz` | Execution receipts and complete geometry/chain audit tables |
| `checkpoint-provenance.json` | Audited resume-file fix; numerical kernel and saved completed contributions retained |
| `execution.json` | Strict-byte artifact inventory, evaluated source hashes and portable canonical-LF code hashes |

`K` counts additional boardings, so K = 1 permits at most two total boardings.
The target-group masks use **total boardings b**, not K. Layer b = 0 is walking
only. Outcome counts refer to building features, not people. Source-segment
length is in metres; betweenness is an unnormalized unordered junction-pair
path-fraction count. No travel-time, clinical-capacity or legal driving claim
is attached to these fields.

The graph includes all mapped highway/path context rather than a largest
component. Degree-two shape points are retained in chain geometry but are not
OD demand. Different source occurrences can map to the same physical edge;
different physical primary failure units can map to the same chain. Restore
unit multiplicity when comparing closures; do not deduplicate by centrality.

NPZ is a standard NumPy ZIP archive. Packed masks have little bit order and
zero padding after the 65,677th origin. Read exact origin row order from
`building-district-ownership.csv.gz`, validate its indexed digest, and use
`numpy.unpackbits(value, bitorder='little')[:65677]`.

To verify the published evidence without rerunning the long centrality census:

```bash
python -m research.src.verify_structural_evidence
```

This replays arithmetic and complete coverage identities against the published
graph and masks. It does not independently recompute all large-block shortest
paths. Source-level geometry and full-node audit receipts remain inspectable;
the report lists commands for repeating them. Generated local model containers
and partial execution checkpoints are excluded from publication.

OSM-derived records and databases: **© OpenStreetMap contributors, ODbL 1.0**;
see [the data license](../../../DATA_LICENSE.md). Original project code and
documentation use [MIT](../../../LICENSE).
