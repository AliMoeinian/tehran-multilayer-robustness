# Conference-paper development

Read [the complete first scientific draft](manuscript.en.md) and its
[evidence/editorial review](manuscript-review.en.md). The draft contains all
scientific sections; conference formatting and submission review remain open.

The [literature and claim plan](literature-and-claims.en.md)
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
python research/paper/check_manuscript.py
```

Omit `--check` only for a deliberate regeneration, review the diff, and update
the prose consistently. The builder accounts for every 510,066 mechanism row
and restores all physical-pair multiplicities at every mode/parameter setting.
Balanced nonzero losses and identical-signature pairs are reported explicitly.

The analytical source snapshot remains `2026-10-29T21:21:26Z`. Literature review
date and publication dates are manuscript metadata, not a new dataset vintage.
Full texts and external study datasets are linked, not redistributed here.

The manuscript checker compares both marked result tables with frozen evidence,
checks local and registered literature links, and checks section structure. It
does not validate all prose or publication rendering. `--update-tables` is an
explicit regeneration option; inspect the diff and update dependent prose.

Next: author review and revision of scientific draft 1, then venue-specific
layout with an identified template/page limit. Larger multi-segment failure,
equal-length budgets, matched-target centrality and operational calibration are
not silently added to the selected scope.
