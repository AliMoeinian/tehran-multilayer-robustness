# Implementation decisions

## 2026-11-01: M1 extraction and stop-order audit

Use `config/baseline.json` as the explicit initial contract. Source data remain
immutable; model output is ignored by Git. The 2024 reference is not used.

The initial task is a diagnostic, not an automatic route repair. A continuous
way trace can have stops recorded in another order; passing the earlier street
screen is insufficient for a transit itinerary. Preserve such cases for review,
distinguish reversed and mixed order, and do not reverse stop lists by fiat.

Buildings are equal-weight origin locations; hospital groups are mapped target
candidates. Walking budget is cumulative over the entire trip. The first
boarding does not consume a line change. No rerouting or service schedule is
assumed. Connector policy and boarding/alighting state transitions are still
implementation work, not completed features.

## 2026-11-01: M2 geometric network construction

Keep the primary stop order unchanged. The 27 mixed-order and one opposing-order
bus relations remain in review; existing trace continuity alone does not resolve
the intended stopping sequence. A separate order-review JSON records backward
steps and source representation. No station or street geometry was added.

Use a declared 100 m geometric connector limit for this initial build, not an
empirical access threshold. Split walking segments at connector projections,
retain native node identities including zero-length source adjacency, and keep
boarding/alighting role permissions. Nearest-way ties select one candidate and
are an explicit sensitivity issue. Graph presence is not an assertion of public
entrance access or actual service.

Source segments intersecting a bus stop-to-stop interval with positive length
become dependencies; a boundary touch is excluded. The dependency lengths must
sum to the recorded interval length. Distinct source carriageways are not merged.
The next solver must account for cumulative walking, line-change state and the
stored role restrictions before any accessibility statistic is reported.

## 2026-11-01: M3 baseline solver

Implement reverse boarding-budget dynamic programming, checked against independent
forward expanded-state search on small graphs. An origin's geometric access length
is counted in the same cumulative walking budget as every transfer and target access.
At most K line changes means at most K+1 boardings under our conservative convention:
even reboarding the same route consumes a new boarding. Never allow a free reset.

Do not remove onboard occurrences merely because their walking connector is rejected;
vehicles may pass through them. Disable boarding/alighting there instead. Disabled
modes lose boarding/alighting permissions and riding arcs. The model is static,
direction-aware and walking-cost-based, with no timetable, capacity or waiting model.

The finite cutoff is the largest configured W (2000 m). An infinite output therefore
means no eligible path within that search budget, not no path of any length. Publish
the whole parameter grid; the K=1 report table is only a readability slice. No claim
about the entire city's operating transit network follows from this screened subset.
