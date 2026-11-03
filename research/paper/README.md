# Conference-paper development

Start with [the literature and claim plan](literature-and-claims.en.md).
It selects the scientific contribution, maps C1-C6 to inspectable evidence,
records rejected overclaims, and chooses existing SVGs for manuscript layout.
It is a positioning document, not a finished manuscript or systematic review.

- [Primary-source register](literature-register.json): 21 curated records,
  reading depth, source versions and methodological locators.
- [BibTeX bibliography](references.bib): journal/preprint status preserved.
- [Search scope and limitations](search-log.json): no proof-of-absence claim.
- [Claim evidence](claim-evidence.json): complete pair-mechanism grids,
  identical/different-signature strata, sensitivity summaries and proxy results.
- [Evidence builder](build_claim_evidence.py): only summarizes existing frozen
  outputs; no new simulation or external analytical data.

```bash
python research/paper/build_claim_evidence.py --check
```

Omit `--check` only for a deliberate regeneration, review the diff, and update
the prose consistently. The builder accounts for every 510,066 mechanism row
and restores all physical-pair multiplicities at every mode/parameter setting.
Balanced nonzero losses and identical-signature pairs are reported explicitly.

The analytical source snapshot remains `2026-10-29T21:21:26Z`. Literature review
date and publication dates are manuscript metadata, not a new dataset vintage.
Full texts and external study datasets are linked, not redistributed here.

Next: draft Data/Model, Methods and Results around the bounded C1-C4 claims;
then Introduction, Discussion, limitations and abstract. Venue-specific final
layout awaits an identified template/page limit. Larger multi-segment failure,
equal-length budgets, matched-target centrality and operational calibration are
not silently added to the selected scope.
