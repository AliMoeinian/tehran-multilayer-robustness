# Literature positioning and the conference-paper claim plan

**Decision date: 3 November 2026 (Asia/Tehran).** This is a completed targeted positioning review and evidence-selection record, not a manuscript, systematic review, or proof of worldwide novelty. The frozen analytical dataset and primary experiments are unchanged. Literature supplies methodological context, not additional analytical records.

The study has a defensible conference contribution as an **auditable, destination-specific dependency study on a screened mapped transit subnetwork**. Its strongest narrative is the complete two-street failure census and the separation of shared single losses from newly lost opportunities. Multilayer modeling, route identity, healthcare accessibility, marginal removal scores, and weak agreement between criticality measures are established ideas. None should be advertised as our invention.

## 1. Decisions after checking the literature

Keep the agreed working title: *Street–Route Dependencies and Structural Healthcare Accessibility Robustness in a Multilayer Network of Tehran*. In the abstract and first methods paragraph, state that the model covers **11 accepted bus relations and 14 rail relations**, rather than verified complete Tehran services. Relations are direction/representation instances, not necessarily distinct operating lines.

Use this bounded contribution statement:

> We evaluate how recorded street-to-bus dependencies shape constrained reachability from mapped building locations to healthcare candidates in Tehran. A complete single- and two-street disruption census separates shared losses from opportunities lost only under joint failure, and traces the resulting modal differences and their sensitivity to route representation, connectors, target selection, and failure policy.

This statement asserts what the implementation and evidence establish. It makes no priority claim. The network-science content is explicit: a typed multilayer path graph, an asymmetric dependency incidence relation, a set-valued failure response, pairwise discrete interaction, alternative-path substitution, and a structural centrality comparison. No passenger demand, waiting time, capacity, or hazard frequency is needed by this endpoint.

Two corrections to earlier conversational emphasis matter:

1. Weak betweenness/loss agreement is supporting evidence, not our main novelty. The supplied stress-test preprint already reports a small association with its access-loss measure.
2. Explicit routes and structural-only analysis also have precedents, including a September 2026 ordered-hypergraph study. Our implemented routing model is a directed, route-aware state graph plus dependency incidence; calling it a new hypergraph cascade would misdescribe it.

## 2. Search scope and reading depth

The review follows five connected questions: hospital/service accessibility under disruption; simultaneous link failures; bus/rail and infrastructure dependencies; route-preserving representations; and the choice of criticality/accessibility metrics. General searches were followed by exact-title searches and backward discovery from the 2026 multilayer review. Twenty transport/network records and one geographic-context record are retained. Unrelated biomedical uses of “multimodal” and “hypergraph” were excluded.

The [search log](search-log.json), [source register](literature-register.json), and [BibTeX file](references.bib) preserve the scope, primary URLs, versions and dates. Only publisher, author, institutional-repository, arXiv or author-article PMC text supports the comparison. Search snippets from third-party aggregators were discovery leads, not the basis for method claims.

Access codes in the tables below are **T**: relevant primary-text sections inspected; **P**: indexed primary sections inspected while direct access was incomplete; **A**: primary abstract/metadata only. A P or A record cannot justify a claim that an uninspected feature is absent. We did not obtain all supplements or rerun other authors' models. A preprint remains labeled as such. Online-first years and issue years are distinguished in the register.

The search found close precedents for each broad ingredient. Within the inspected evidence, we did not establish an earlier identical combination of recorded source-segment bus dependencies, bounded walking/boarding healthcare reachability, and a complete origin-set pair decomposition. This is a bounded search observation, **not evidence that no such study exists**. A “first study” sentence is unnecessary and should not appear in the manuscript.

## 3. Closest comparison studies

Each row describes the observed scope of the cited work, then the precise comparison to our implemented study. It is not a universal feature-absence matrix.

| Study / access | Verified emphasis | Relation to our contribution |
| --- | --- | --- |
| [L01 Schuster et al., 2024; inspected arXiv v1](https://doi.org/10.1016/j.tra.2024.104017) / T | Austrian automobile corridors, population-weighted nearest-hospital access, single and neighborhood stress tests. | Direct destination-specific stress-test precedent; our subject is street-dependent bus arcs and constrained multimodal building-to-candidate paths. |
| [L02 Tariverdi et al., 2023](https://doi.org/10.1038/s41598-023-28460-z) / P | Public-service accessibility and infrastructure criticality, demonstrated with healthcare and disaster disruption. | Healthcare access as a functional infrastructure endpoint is established. Our scenarios are hazard-independent structural counterfactuals. |
| [L03 Wang et al., 2016](https://doi.org/10.1080/23249935.2015.1137373) / T | Critical link combinations under equilibrium travel-cost response; joint critical sets need not follow individual-link rankings. | Multiple-failure criticality is established. We enumerate the declared two-unit domain and retain each origin's loss-set interpretation. |
| [L04 Iliopoulou and Makridis, 2023](https://doi.org/10.1016/j.physa.2023.129100) / A | Multi-objective search for transit disruption combinations using an assignment model. | A direct multi-link transit precedent. Our exhaustive finite two-unit census is not a claim to solve its operational optimization problem. |
| [L05 Zhang et al., 2023](https://doi.org/10.1016/j.ress.2023.109250) / T | Bus-route/subway interdependencies, route collinearity and dynamic coupled-map failures. | Route-dependent bus/rail disruption is established. Our mechanism is one-way source-street support deletion, without dynamic redistribution. |
| [L06 Boura and Ferguson, 2024](https://doi.org/10.1016/j.jtrangeo.2024.103934) / T | Geographic proximity modifies accessibility-based redundancy/substitutability for Scottish bus and rail. | Shared exposure can reduce modal alternatives. Our functional support rule is not a geographic hazard-footprint model. |
| [L07 Xu and Chopra, 2023](https://doi.org/10.1038/s41467-023-39999-w) / P | Multimodal interconnection, robustness and interoperability in Hong Kong. | Modal integration benefits are established; we examine matched target-specific losses and their mechanisms in an observed subnetwork. |
| [L08 Cao et al., 2025](https://doi.org/10.1038/s41598-025-95177-6) / P | Bus/subway station accessibility, actual walking transfer distances and robustness in Dalian. | Walking-informed modal coupling is established. Our cumulative walking/boarding feasibility endpoint and healthcare candidate set differ. |
| [L09 Gao, Shirazian et al., online 2025](https://doi.org/10.1080/10286608.2025.2601992) / P | OSM-based directed tram/subway networks, transfer links and percolation-based connectivity loss in Amsterdam. | OSM multimodal vulnerability is established. We preserve source-street bus support and evaluate a fixed complete pair domain. |
| [L10 Gao and Blekanov, 2026](https://doi.org/10.3390/e28090976) / T | Ordered route-preserving bus/metro hypergraphs, route-support pruning and distinct resilience diagnostics across 45 cities. | Route identity and structural diagnostics are established. Our target-constrained origin sets and physical source-segment failure units define a different analysis. |
| [L11 Guo et al., arXiv v2, 2025](https://arxiv.org/abs/2411.08782v2) / T | Accessibility-restoring bus redesign after rail disruption. | Accessibility-oriented multimodal recovery is established; we hold the recorded services fixed and do not optimize restoration. |
| [L18 Liao and van Wee, 2017](https://doi.org/10.1007/s11116-016-9701-y) / P | Travel options, route overlap, flexible destinations and multimodal robustness. | Neither alternative destinations nor shared-route dependence is a new concept; we operationalize specific failure-set counts. |
| [L21 Liu and Miller, 2025 issue; online 2024](https://doi.org/10.1177/23998083241272098) / P | Route-removal accessibility contributions, with nonlocalized and nonlinear effects. | Marginal accessibility loss and nonadditivity are precedented. Our units are supporting streets that disable sets of bus connections. |

### The especially important stress-test comparison

In [the supplied arXiv v1, Section 4.1](https://arxiv.org/html/2307.02250v1), Schuster et al. report approximately 0.09 Spearman association between betweenness and ACIS. Equation 5 uses municipality-to-hospital pairs within 100 km. Our comparator uses uniform junction pairs on an undirected mapped-corridor graph. The small coefficients are therefore neither a new general discovery nor a matched replication. Journal metadata is verified, but these detailed observations are explicitly version-bound to v1.

Our own 0.0949 (bus) and -0.0256 (bus+rail) coefficients support only this statement: **the selected generic corridor comparator does not closely reproduce the primary destination-specific ranking**. They do not demonstrate superiority over a hospital-targeted, demand-matched or mode-matched baseline. We avoid that stronger claim; a new long centrality run is not required for the bounded manuscript.

### Supporting methodological anchors

| Source / access | Use in the manuscript |
| --- | --- |
| [L12 Jafino et al., 2020 issue](https://doi.org/10.1080/01441647.2019.1703843) / P | Purpose-dependent criticality metrics and rank comparison; weak agreement is not itself a novelty claim. |
| [L13 Palk et al., 2026](https://doi.org/10.1002/net.70021) / P | Representation and assessment choices must match the question and available data. |
| [L14 Sfiligoj et al., arXiv 2026](https://arxiv.org/abs/2603.21130v1) / T | Multilayer terminology, disruption/recovery distinction and discovery of close transport studies. |
| [L15 Buldyrev et al., 2010](https://doi.org/10.1038/nature08932) / A | General dependency-failure context; our model does not implement reciprocal percolation or a feedback cascade. |
| [L16 Kivela et al., 2014](https://doi.org/10.1093/comnet/cnu016) / A | General multilayer-network terminology, not an algorithmic novelty justification. |
| [L19 Luo et al., 2019](https://doi.org/10.1016/j.jtrangeo.2019.102505) / P | Connect network representation to a transport-relevant endpoint rather than reporting topology alone. |
| [L20 Liu et al., 2024](https://doi.org/10.1016/j.jtrangeo.2023.103769) / A | Contrast scheduled/real-time accessibility with our static geometric feasibility endpoint. |

The earlier supplied [PLOS paper L17](https://doi.org/10.1371/journal.pone.0341276) concerns Tehran green-space connectivity. It is geographic context, not a direct transport-disruption comparator. Its boundary/data files are not imported; our frozen boundary is unchanged.

## 4. Exactly what the model measures

Let R(F;W,K) be the set of original building features that can reach at least one connected healthcare candidate after street-set F disables its dependent consecutive-stop bus arcs. Paths respect recorded direction, boarding/alighting roles, cumulative walking W, and at most K+1 boardings. Riding contributes zero to the walking-cost label. Walking and rail remain fixed; buses do not reroute.

The original denominator is 65,677 building features, not population. There are 236 connected possible destination groups; their clinical independence is not verified. Origins use the frozen city mask and paths/targets may extend into the context. Twenty-four district-unassigned origins remain in the full denominator.

For a unit e, write L_e=R(empty)\R({e}); for a pair, L_ef=R(empty)\R({e,f}). Deletion monotonicity gives L_e union L_f subset L_ef. Define:

```math
S(e,f)=|L_e\cap L_f|,\quad
N(e,f)=|L_{ef}\setminus(L_e\cup L_f)|,\quad
C(e,f)=|L_{ef}|-|L_e|-|L_f|=N(e,f)-S(e,f).
```

This is inclusion-exclusion, **not a new theorem**. The empirical content is the distribution, locations, affected origins, path mechanisms and sensitivity of N and S. A negative C is overlap relative to adding two single losses; it is not beneficial closure. A zero C can have N=S>0. Even N=S=0 can accompany positive additive joint loss; “neither mechanism” does not mean “no harm.”

For modal comparison, M(F)=|R_full(F)|-|R_bus(F)| and DeltaM(F)=M(F)-M(empty). M(F)>=0 follows from including the bus paths in the full model; it is a construction property. DeltaM measures changes relative to different healthy baselines. A negative DeltaM is not a Braess paradox or evidence that deleting metro improves access.

## 5. Claim register and evidence

Exact supporting values and full grids are in [claim-evidence.json](claim-evidence.json), generated by [the evidence builder](build_claim_evidence.py) solely from frozen output. Selection is retrospective manuscript development, not a new preregistered experiment or hypothesis test. W=1,000 m, K=1 is the same reference setting used in the earlier reports; every W/K grid remains available.

### C1 — Primary: losses combine through two distinct origin-set mechanisms

**Permitted wording:** “The complete observed two-street census separates newly lost opportunities from shared single losses; these mechanisms can coexist or cancel in the net interaction.”

| Physical-pair category, reference setting | Bus | Bus + rail |
| --- | ---: | ---: |
| Shared losses only: S>0, N=0 | 42,379 | 40,872 |
| Joint-only losses only: N>0, S=0 | 14,579 | 9,516 |
| Both: N>0, S>0 | 11,433 | 10,430 |
| Neither: N=S=0 | 1,348,695 | 1,356,268 |
| Total distinct physical pairs | 1,417,086 | 1,417,086 |
| Balanced nonzero mechanisms, N=S>0 (subset of “both”) | **1,229** | **2,023** |

Each of the first four counts is disjoint and together exhausts the domain. The final row must not be added again. All 510,066 signature-pair/mode/parameter rows were reconciled and expanded with exact physical multiplicity. The identity is algebraic; the counts are empirical finite-model outputs. Do not label every N>0 pair “superadditive”: positive net C additionally requires N>S.

### C2 — Primary: the pair result is not solely duplicate failure signatures

Two different streets can disable the same set of bus connections. There are 16,289 such physical pairs; for these, L_ef=L_e=L_f, N=0 and C=-|L_e| by construction. They are valid physical scenarios but cannot by themselves demonstrate a new combined-loss mechanism.

| Different-signature pairs only, reference setting | Bus | Bus + rail |
| --- | ---: | ---: |
| Domain | 1,400,797 | 1,400,797 |
| Positive C | 15,719 | 11,439 |
| Negative C | 43,086 | 39,411 |
| Pairs with N>0 | 26,012 | 19,946 |

Thus the observed two-mechanism pattern persists beyond identical failed-graph pairs. This is a stratified summary of the existing census, not a new sampled experiment. The full domain remains the primary denominator; this stratum is a transparent diagnostic.

### C3 — Secondary: modal differences have an inspectable, representation-sensitive mechanism

Healthy reachable origins are 26,360 (bus) and 29,105 (full); at least two possible target groups are reachable from 13,528 and 18,404 origins. These are structural opportunity counts. Maximum single losses are 224 and 219; maximum pair losses are 439 and 351. Maxima can come from different scenarios, so their difference is not a paired treatment effect.

In the primary model, 98 physical single units have a greater absolute loss with rail relative to their own baseline. The seven corresponding signatures have replayable witnesses involving a metro-to-bus dependency; 13 additional full-baseline origins explain the excess-loss component. Under the derived-order reconstruction, that 98-unit pattern is zero at the reference setting. Report both facts together. Treat this as a certified mechanism in the primary representation, not a universal cost of metro or the headline discovery.

### C4 — Primary qualification: quantitative inference depends on the modeling contract

At the reference setting, a 25 m connector contract gives full healthy access of 18,589 versus 29,105 under the primary contract. Whole-route deletion gives maximum pair losses of 648 bus / 427 full versus 439 / 351 with local arc deletion. The emergency-tag target variant changes the endpoint and yields different losses; its tags are not clinical verification. Route-extension/reordering alternatives are reconstruction hypotheses, not better operational truth chosen because they improve access.

These changes must accompany the result narrative. The registered OAT suite covers 19 variants including the separate way aggregation; it does not cover every combined assumption or calibrate real-world uncertainty. Neither connector sensitivity nor matched results in nested contexts proves verified entrances or extract completeness.

### C5 — Supporting: generic structural ranking differs from this functional ranking

Uniform-junction weighted betweenness has Spearman 0.0949 (bus) and -0.0256 (full) against single-unit loss; the positive-top-5% Jaccard is zero in both reference comparisons. Tied top sets have actual sizes 50/85 and 47/85, respectively. The OD sets, mode rules and target meaning differ between the comparator and outcome. This is descriptive agreement, not predictive validation, causal adjustment, or a test that all centralities are ineffective. Keep the full 72-row grid in the supplement.

### C6 — Supporting: reproducibility and geographic descriptions

The complete primary domain, strict source identities, 7,155 selected-case path certificates, full-node solver controls, and exact source-unit mappings make the result inspectable. This is a reproducibility contribution, not certification of complete real-world service. District loss shares are shares of mapped building features. District maxima may arise under different failures and must not be summed as one event. No population-equity conclusion is supported.

## 6. Claims explicitly rejected

| Do not write | Reason / replacement |
| --- | --- |
| “The first multilayer/hypergraph transport vulnerability study” | L05-L10, L14 and L16 are direct precedents. State the implemented dependency/endpoint combination. |
| “The first healthcare accessibility stress test” | L01-L02 precede it. Describe the multimodal source-street case. |
| “We discover that joint failures need not be additive” | L03-L04 and L21 already motivate combination/nonlinear effects. Present measured N/S patterns. |
| “Our new theorem C=N-S” | It is inclusion-exclusion. Use it as an explanatory decomposition. |
| “Centrality fails to predict hospital access” | L01/L12 are precedents; our comparison is not a matched prediction study. |
| “Metro causes a paradox or worsens access” | Nested path sets guarantee the opposite for matched absolute access; DeltaM compares healthy-baseline changes. |
| “We model a Buldyrev-like cascading failure / phase transition” | No reciprocal feedback, iterative capacity failure or transition analysis is implemented. |
| “Losses represent patients, passengers or population” | Origin weights are equal mapped building features. |
| “A robust operational closure plan for all Tehran” | Incomplete observed relations, no operational validation, probabilities, costs or rerouting optimization. |
| “Sensitivity proves real-world validity” | OAT comparisons expose contract dependence; they do not validate missing observations. |

## 7. Why this question, and who could use the output?

Planning a bus-passability restriction changes a set of service connections, not merely one abstract link. Two restrictions can disable different alternatives used by the same origin. A component ranking alone therefore does not describe all combined scenarios. The study supplies a source-identifiable screening record: which street pairs lose which mapped building opportunities, which bus connections support them, and which modeled alternatives explain the outcome.

Potential users are bus-service continuity analysts and teams coordinating street restrictions. The appropriate action is **closer review of flagged dependencies and concurrent restrictions**, supported by a local map/trace inspection. This is not a validated agency requirement, a calibrated consequence forecast, or a recommendation to close lower-ranked roads. To make an operational decision, they would need their own current service, entrance, incident and management information; those records are not imported into this study.

## 8. Main figures and tables selected for the conference narrative

This selects evidence and panel roles. Final composition and font/layout adjustment require the conference page/template constraints; no final composite is claimed here. The existing SVGs retain their frozen hashes. Page budgeting is a provisional editorial choice, not an official venue requirement.

| Item | Purpose and selected existing evidence | Caption constraint |
| --- | --- | --- |
| Figure 1 | Observed coverage and eligibility: [network map](../figures/progress-2026-11-01/02-study-network-map.svg), with the route-screening counts from [screening](../figures/progress-2026-11-01/01-route-screening.svg). | “Screened mapped subnetwork”; show relation counts, source date, origin/target rules. A compact dependency/path-state schematic can be composed during manuscript layout. |
| Figure 2 | Main result: [complete pair-interaction grid](../figures/pairs-exhaustive-2026-11-01/01-positive-pair-interaction.svg), and [N/S decomposition of every registered extremum](../figures/sensitivity-2026-11-02/pair-mechanisms-all-extrema.svg). | Full pair grid versus deliberately selected extrema must be distinguished; negative/zero C is not harmless closure. |
| Figure 3 | Modal mechanism plus its qualification: [metro-to-bus witness](../figures/sensitivity-2026-11-02/metro-bus-witness.svg) and [sensitivity of maximum losses](../figures/sensitivity-2026-11-02/sensitivity-maximum-losses.svg). | A selected certified path explains possibility, not prevalence or operational behavior. Put the route-order sensitivity beside it. |
| Optional Figure 4 | [All proxy correlations](../figures/structural-2026-11-02/single-loss-proxy-correlations.svg), only if space permits and with the OD mismatch stated. | Supporting comparison, not a superiority claim. |
| Table 1 | Frozen source/scope inventory, path constraints, 11/14 relation subset, 65,677 origins, 236 connected possible groups and 1,684 failure units. | Dataset-wide counts must not be confused with accepted model counts. |
| Table 2 | C1 mechanism census including the balanced-nonzero subset, C2 signature diagnostic, and a compact sensitivity/claim qualification. | Retain physical multiplicity; nested subsets must not be summed as disjoint categories. |

District maps, all route-overlap pairs, candidate-group ECDF, road-class distributions, all path cases and full sensitivity/rank grids remain supplementary evidence. They do not need to compete for main-paper space. The intended main story is dependency-aware **pair loss mechanisms**, not an inventory of every available graph statistic.

## 9. Reviewer critique and response plan

| Likely objection | Evidence-based response and boundary |
| --- | --- |
| “Only 11 bus relations: this is not all Tehran.” | Agree. Present an observed-subnetwork case study, eligibility funnel and route variants. No sampling-representativeness or complete-service claim. |
| “The negative interaction is trivial when two streets fail the same arcs.” | Show the 16,289 identical-signature pairs separately and the full 1,400,797-pair distinct-signature diagnostic. |
| “The decomposition is elementary.” | Agree. Its role is interpreting exact origin-level outcomes and certifiable paths; do not claim a new combinatorial theorem. |
| “Weak centrality agreement is expected with different OD sets.” | Agree. Relegate C5 to supporting evidence and avoid claiming superiority over targeted/demand-matched baselines. |
| “Local fragments of a damaged bus line may not operate.” | The endpoint is potential connectivity of retained arcs. Whole-route deletion is reported as a different policy, not a proven real-world bound. |
| “Free riding ignores long journeys.” | Riding contributes zero to walking cost, so the endpoint is explicitly not total distance, time or attractiveness. Boarding constraints remain enforced; no time interpretation is introduced. |
| “Most C values are zero.” | Report full denominators and positive/negative mechanisms. Some zero C values are balanced nonzero N/S; others can still have additive loss. No p-values treat pairs as independent. |
| “The whole exercise is sensitive to mapping assumptions.” | Quantify that dependence instead of choosing the most favorable model. Keep the same frozen primary contract. |
| “What is new after these precedents?” | A transparent case-based combination of source-street dependencies, bounded target reachability, a complete pair census, origin-set explanations and explicit representation sensitivity. Acceptance/priority is not guaranteed by this review. |

The bounded claims above require **no new heavy experiment**. A hospital-targeted betweenness benchmark would become necessary only for a stronger comparative-superiority claim, which is not selected. Hazard probabilities, demand/capacity models, new maps, larger-failure curves and clinical validation would answer different questions and remain outside the selected scope.

## 10. Next writing step

Write the English **Data and model**, **Methods**, and **Results** sections around C1-C4, preserving the typed dependency mechanism and full finite domains. Use C5-C6 as supporting/supplementary material. Then draft the introduction against the specific precedents above, and write the discussion, limitations, title refinement and abstract after the narrative is stable. A venue name/template and page limit will eventually be needed for final formatting, but they do not block the scientific prose draft.

To reproduce the claim evidence without rerunning network simulations:

```bash
python research/paper/build_claim_evidence.py --check
```

For a deliberate update after reviewing changed frozen inputs, run the builder without `--check`, inspect the JSON diff and revise the prose consistently. It reconciles all 510,066 mechanism rows, both modes/all nine settings, physical signature strata, selected sensitivity grids and all 72 proxy rows. The [cumulative reports](../reports/research-progress.en.md) remain the detailed technical foundation.
