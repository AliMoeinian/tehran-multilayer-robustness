# Scientific draft 1: evidence and editorial review

**Date:** 3 November 2026 (Asia/Tehran). **Artifact:** [manuscript.en.md](manuscript.en.md).

The first prose draft contains an abstract, Introduction, Related work, Data and model, Methods, Results, Discussion, Limitations/reproducibility and Conclusion. It is ready for scientific discussion within the documented model scope. It is not declared submission-ready. No dataset, frozen result or existing SVG was modified, and no new network experiment was run.

## Evidence coverage

| Draft location | Evidence actually used | Review outcome |
| --- | --- | --- |
| Abstract; Sections 3 and 5.1 | [Cumulative data/model record](../reports/research-progress.en.md), Sections 2–7; [claim evidence](claim-evidence.json), reference setting and target counts | Origin denominator is 65,677; accepted connectors are a subset. Features, groups, relations, arcs and source segments remain distinct. |
| Section 3.2 | [Final exclusions](../reports/validation-closure.en.md), Section 4 | All 28 excluded relations fail the order contract; one also fails distance. The reverse-monotone case and distance-conflict case are different relations. The draft does not conflate them or call exclusions proof of inactive services. |
| Sections 3.3 and 4.1 | Cumulative record, Sections 4–5; [baseline configuration](../config/baseline.json) | Walking is undirected; riding is directed. W is cumulative walking, K permits K+1 total boardings. Source support uses way ID plus native adjacent-node pair. |
| Sections 4.2 and 5.2; Table 2 | [Complete mechanism table](../reports/sensitivity-2026-11-01/all-pair-mechanisms.csv.gz), summarized in claim evidence | Inclusion–exclusion is an identity. First four categories exhaust every physical pair; balanced nonzero cases are a nested subset. Neither zero C nor N=S=0 implies zero joint damage. |
| Sections 4.3 and 5.3 | [Pair census](../reports/paired-closures.en.md); claim evidence signature strata | Exact multiplicity is preserved. All 16,289 same-signature pairs are retained and separated from 1,400,797 different-signature pairs. No empirical sampling or independent-pair inference is claimed. |
| Section 4.4 | [Full validation](../reports/validation-closure.en.md); [path replay](../reports/path-sensitivity.en.md), Sections 1 and 3 | Complete solver comparison and selected-case witness coverage are separate scopes. Floating-point agreement is not symbolic exactness. Stored infinite distance is bounded by the walking cutoff. |
| Sections 4.5 and 5.4 | Path/sensitivity record, Section 4; all selected variant single effects summarized in claim evidence | Nested modal accessibility and differing intact baselines are explicit. The primary 98-unit pattern is paired with its disappearance under both expanded route representations. No metro-harm or Braess claim. |
| Section 5.5; Table 3 | Path/sensitivity record, Sections 5–6; claim evidence selected variant grids | All eight table rows use the same primary physical failure universe. Connector changes affect all access entity types. Maxima need not refer to matched pairs. Route reconstruction is an assumption. |
| Section 5.6 | [Structural record](../reports/structural-comparisons.en.md); claim evidence proxy rows | All sources in the exact comparator are completed. Uniform-junction OD differs from the functional endpoint. Spearman and tied positive-top sets are descriptive. |
| Section 2 | [Literature register](literature-register.json), [claim plan](literature-and-claims.en.md), [bibliography](references.bib) | Every linked DOI/preprint is registered. Source access depth is retained; unseen methods are not asserted absent. Detailed stress-test observation is explicitly v1-bound. |
| Figures 1–3 and linked companion panels | Existing frozen SVGs in the selected figure plan | Referenced rather than regenerated. Captions distinguish full-domain results, selected extrema and a single witness illustration. Final composite and typography checks await the venue layout. |

## Checks and their limits

`python research/paper/build_claim_evidence.py --check` replays the existing evidence summary over all 510,066 mechanism rows, 18 settings, 36 signature strata and 72 proxy comparisons. It does not rerun the network experiment.

`python research/paper/check_manuscript.py` independently constructs the two marked draft result tables from the saved claim evidence and requires exact equality. It checks every local Markdown link, each DOI/arXiv link against the source register, fenced-block balance and all eight numbered sections. The tables contain 14 data rows: six mechanism rows and eight sensitivity rows. The default is read-only. `--update-tables` replaces only these marked tables and requires a deliberate prose/diff review afterward. The evidence builder must also pass; a valid table against a stale summary alone is insufficient.

This automated check does **not** validate every numerical token in prose, scientific novelty, the accuracy of external papers, or rendered publication layout. The editorial pass covered every draft section, checked the consequential prose claims against the sources listed above, and retained the following boundaries:

- The primary result is the pair mechanism census and contract sensitivity; generic centrality and the negative-DeltaM example are supporting evidence.
- Completeness applies to the declared finite domain. It does not mean complete Tehran transit coverage or verified hospital capability.
- An accessibility loss is counted only against its mode-specific intact set. Unconnected origins remain in the common denominator.
- All parameter grids remain available; the reference grid is a presentation choice already used in earlier reports, not a new favorable selection.
- One-factor model comparisons are not confidence intervals or a full combined-assumption analysis. Expanded routes are evaluated on the original exposure domain.
- No claim of a new theorem, first-ever model, operational cascade, phase transition, forecast or validated closure plan is made.
- Open source code/results support reproducibility; computational checks are not independent validation of actual services or entrances.

## Remaining manuscript work

1. Discuss the scientific draft with the author and revise emphasis or wording while retaining evidence traceability.
2. Apply the actual conference template, page limit, author/affiliation details and reference style; make the selected final figure composites. This draft's three numbered evidence figures and companion links are not final camera-ready panels.
3. Recheck all prose/table/figure denominators after condensation, resolve bibliography formatting and render the complete submission. No PDF layout or venue compliance is claimed in this Markdown stage.
4. Complete the final scientific/submission checklist. Larger failures, equal-length budgets and joint-assumption experiments remain unexecuted optional extensions, not missing results silently included here.

The first complete scientific prose draft is delivered. Author review, final evidence selection after condensation, venue layout and submission review remain open.
