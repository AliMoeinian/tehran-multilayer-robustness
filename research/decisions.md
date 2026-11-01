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
