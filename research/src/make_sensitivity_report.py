"""Build the English path/sensitivity record from completed, audited outputs."""
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .accessibility import ROOT
from .sensitivity_runs import read_gzip
from .make_path_figures import FIG,OUT,setup,save,BLUE,ORANGE,DARK


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])


def fmt(x,digits=3):return 'undefined' if x in [None,''] else f'{float(x):.{digits}f}'


def run():
    setup();audit=json.loads((OUT/'sensitivity-audit.json').read_text());assert audit['status']=='passed'
    path=json.loads((OUT/'path-summary.json').read_text());pa=json.loads((OUT/'path-audit.json').read_text());assert pa['status']=='passed'
    protocol=json.loads((ROOT/'research/config/sensitivity-protocol.json').read_text())
    names=[r['id'] for r in protocol['variants']]+['whole-osm-way']
    variants={name:json.loads((OUT/'variants'/name/'summary.json').read_text()) for name in names}
    main=lambda d:next(r for r in d['results'] if r['max_line_changes']==1 and r['walking_budget_m']==1000)
    ranks=read_gzip(OUT/'ranking-stability.csv.gz');primary=[r for r in ranks if r['walking_budget_m']=='1000' and r['max_line_changes']=='1']
    lookup={(r['variant'],r['domain'],r['metric'],r['mode']):r for r in primary}
    paths=[];labels=[n.replace('targets-','target: ').replace('connector-','connector: ').replace('failure-','failure: ').replace('routes-','routes: ') for n in names[:-1]]
    fig,axes=plt.subplots(1,2,figsize=(10,7.5),sharey=True)
    y=np.arange(len(labels))
    for ax,mode,title,color in zip(axes,['bus','bus_metro'],['Walking + bus','Walking + bus + metro'],[ORANGE,BLUE]):
        values=[main(variants[n])[mode]['baseline_accessible'] for n in names[:-1]]
        ax.barh(y,values,color=color,height=.62);ax.axvline(values[0],color=DARK,ls='--',lw=.8)
        ax.set_title(title);ax.set_xlabel('Accessible building features');ax.set_xlim(0,65677)
        ax.set_yticks(y,labels);ax.grid(axis='x',alpha=.15)
        for i,value in enumerate(values):ax.text(value+400,i,f'{value:,}',va='center',fontsize=8)
    axes[0].invert_yaxis();fig.suptitle('One factor at a time · healthy network · W=1,000 m, K=1',fontsize=11)
    fig.tight_layout();paths.append(save(fig,'sensitivity-healthy-access'))
    fig,axes=plt.subplots(1,2,figsize=(10,7.5),sharey=True)
    for ax,mode,title in zip(axes,['bus','bus_metro'],['Walking + bus','Walking + bus + metro']):
        vals=[main(variants[n])[mode] for n in names[:-1]]
        ax.scatter([r['maximum_single_loss'] for r in vals],y,marker='o',color=BLUE,s=22,label='Maximum single loss')
        ax.scatter([r['maximum_joint_loss'] for r in vals],y,marker='D',color=ORANGE,s=20,label='Maximum paired loss')
        for i,r in enumerate(vals):ax.plot([r['maximum_single_loss'],r['maximum_joint_loss']],[i,i],color='#CDD3DA',lw=.8,zorder=0)
        ax.set_yticks(y,labels);ax.set_title(title);ax.set_xlabel('Building-feature losses');ax.set_xlim(left=0);ax.grid(axis='x',alpha=.15)
    maximum=max(main(variants[n])[mode]['maximum_joint_loss'] for n in names[:-1] for mode in ['bus','bus_metro'])
    for ax in axes:ax.set_xlim(0,maximum*1.08)
    axes[0].invert_yaxis();handles,legend=axes[0].get_legend_handles_labels();fig.legend(handles,legend,loc='lower center',ncol=2,frameon=False)
    fig.suptitle('Complete matched closure domains · W=1,000 m, K=1',fontsize=11);fig.tight_layout(rect=(0,.04,1,.97));paths.append(save(fig,'sensitivity-maximum-losses'))
    # All variants, all thresholds: numeric annotations and a missing-value mask
    # make undefined constant-vector correlations explicit.
    for mode in ['bus','bus_metro']:
        fig,axes=plt.subplots(1,2,figsize=(10,7.2),sharey=True)
        for ax,domain,metric,title in zip(axes,['single','pair'],['loss','interaction'],['Single-loss Spearman','Pair-interaction Spearman']):
            array=np.full((len(names)-1,9),np.nan)
            for r in ranks:
                if r['variant'] not in names[:-1] or r['domain']!=domain or r['metric']!=metric or r['mode']!=mode:continue
                col=[(k,w) for k in [0,1,2] for w in [500,1000,2000]].index((int(r['max_line_changes']),int(r['walking_budget_m'])))
                if r['spearman']!='':array[names.index(r['variant']),col]=float(r['spearman'])
            cmap=plt.get_cmap('cividis').copy();cmap.set_bad('#D9DDE2')
            image=ax.pcolormesh(np.ma.masked_invalid(array),vmin=-1,vmax=1,cmap=cmap,rasterized=False)
            ax.set_xlim(0,9);ax.set_ylim(len(labels),0)
            ax.set_yticks(np.arange(len(labels))+.5,labels);ax.set_xticks(np.arange(9)+.5,[f'{w}\n{k}' for k in [0,1,2] for w in [500,1000,2000]])
            ax.set_xlabel('Walking budget W (m) / additional boardings K');ax.set_title(title,fontsize=10)
            for i in range(array.shape[0]):
                for j in range(9):
                    x=array[i,j];ax.text(j+.5,i+.5,'—' if np.isnan(x) else f'{x:.2f}',ha='center',va='center',fontsize=7,color='black' if np.isnan(x) or x>.2 else 'white')
        mode_title='walking + bus' if mode=='bus' else 'walking + bus + metro'
        fig.suptitle(f'Ranking relative to the frozen model at matching W/K · {mode_title}',fontsize=11)
        fig.tight_layout(rect=(0,0,.94,.96));cax=fig.add_axes([.945,.16,.012,.68]);cb=fig.colorbar(image,cax=cax)
        cb.solids.set_rasterized(False)
        paths.append(save(fig,f'ranking-grid-{mode}'))
    (FIG/'sensitivity-manifest.json').write_text(json.dumps({'source_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_sha256':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT/'sensitivity-audit.json',OUT/'ranking-stability.csv.gz']+[OUT/'variants'/n/'summary.json' for n in names]},
        'svg_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}},indent=2)+'\n',encoding='utf-8')
    metadata=table(['Variant','Connected origins','Targets','Active ride arcs','Bus / rail relations','Signature groups','Pairs'],[
        [name,variants[name]['model']['connected_origins'],variants[name]['model']['target_features'],variants[name]['model']['active_riding_connections'],
         f"{variants[name]['model']['route_relations'].get('bus',0)} / {variants[name]['model']['route_relations'].get('metro',0)}",variants[name]['signature_groups'],f"{variants[name]['physical_pair_count']:,}"] for name in names])
    numeric=[]
    for mode in ['bus','bus_metro']:
        rows=[]
        for name in names:
            r=main(variants[name])[mode]
            rows.append([name,r['baseline_accessible'],r['positive_loss_units'],r['maximum_single_loss'],r['maximum_joint_loss'],r['minimum_interaction'],r['maximum_interaction'],r['positive_interaction_pairs'],r['negative_interaction_pairs']])
        numeric.append(f"### {'Walking + bus' if mode=='bus' else 'Walking + bus + metro'}\n\n"+table(['Variant','Healthy access','Positive single units','Max single L','Max paired L','Min C','Max C','C > 0 pairs','C < 0 pairs'],rows))
    rank_table=table(['Variant','Bus single rho','Full single rho','Bus pair-C rho','Full pair-C rho','Full positive-top-5% single Jaccard'],[
        [n,*[fmt(lookup[n,d,m,md]['spearman']) for d,m,md in [('single','loss','bus'),('single','loss','bus_metro'),('pair','interaction','bus'),('pair','interaction','bus_metro')]],fmt(lookup[n,'single','loss','bus_metro']['positive_top_5pct_jaccard'])] for n in names[:-1]])
    metro=read_gzip(OUT/'metro-loss-comparisons.csv.gz')
    metro_table=table(['Variant','Single: lower / equal / higher loss with metro','Pair: lower / equal / higher loss with metro'],[
        [name,*[' / '.join(f"{int(row[f]):,}" for f in ['metro_lower_loss','equal_loss','metro_higher_loss']) for row in
            [next(r for r in metro if r['variant']==name and r['domain']==domain and r['walking_budget_m']=='1000' and r['max_line_changes']=='1') for domain in ['single','pair']]]] for name in names])
    pair_table=table(['Case','Mode','Union loss','Shared single losses','New joint-only losses','C'],[
        [r['case'],r['mode'],r['affected_origins'],r['shared_single_losses'],r['new_joint_only_losses'],r['interaction']] for r in path['case_results'] if r['case'].startswith('pair-')])
    negative_table=table(['Group','Physical streets','Bus L','Full L','Bus losses rescued','Extra baseline lost','DeltaM'],[
        [r['case'].split('-')[-1],next(c['street_count'] for c in json.loads((OUT/'path-case-registry.json').read_text())['negative_delta_singles'] if str(c['group_index'])==r['case'].split('-')[-1]),r['bus_loss'],r['bus_metro_loss'],r['bus_loss_rescued'],r['extra_full_baseline_lost'],r['bus_loss']-r['bus_metro_loss']] for r in path['case_results'] if r['case'].startswith('negative')])
    total_pairs=audit['total_physical_pairs_over_variants']
    equal_rows={name:all(variants[name]['artifact_sha256'][filename]==variants['baseline']['artifact_sha256'][filename] for filename in
        ['groups.csv.gz','connections.csv.gz','units.csv.gz','single-effects.csv.gz','pair-effects.csv.gz'])
        and variants[name]['results']==variants['baseline']['results'] for name in names[:-1]}
    identical=[name for name,equal in equal_rows.items() if equal and name!='baseline']
    unequal=[name for name,equal in equal_rows.items() if not equal]
    invariants=table(['Common-domain variant','Every encoded baseline/single/pair outcome identical to reference'],[[n,str(equal_rows[n])] for n in names[:-1]])
    derived_main=main(variants['routes-derived-order'])
    target_rank=lookup['targets-emergency-tag','single','loss','bus_metro']
    derived_higher=next(r for r in metro if r['variant']=='routes-derived-order' and r['domain']=='single' and r['walking_budget_m']=='1000' and r['max_line_changes']=='1')['metro_higher_loss']
    text=f'''# Path explanations and exhaustive model sensitivity

**Record completed:** 2 November 2026 (Asia/Tehran). This report extends the [cumulative methods/results](research-progress.en.md), [exhaustive paired closures](paired-closures.en.md), and [complete primary-model validation](validation-closure.en.md). It uses only the frozen public OSM dataset. No new operational, population, timetable or healthcare records enter the analysis.

## 1. What this stage completes

The registered [sensitivity protocol](../config/sensitivity-protocol.json) contains 18 one-factor variants, including the reference, plus one separate source-way aggregation. Every common-domain variant covers all 1,684 primary source segments and all 1,417,086 unordered distinct physical pairs, at all nine W/K settings and both mode sets. The source-way test covers all 310 supporting OSM ways and all 47,895 unordered way pairs. Across the 19 variants there are **{total_pairs:,} physical-pair scenarios**, expanded to **{total_pairs*18:,} mode/parameter results**. Computation groups only exactly identical failed-connection sets; it does not sample streets, pairs, origins or W/K settings.

Path interpretation covers all tied minimum/maximum interaction signature pairs at W=1,000 m, K=1 in either mode and all seven negative-DeltaM single signatures. All affected origins in those registered cases are included. This case domain deliberately concerns extrema and the metro interpretation, not every positive-loss pair in the census. One shortest-walking witness is retained per reachable origin/state; enumerating every tied path is unnecessary for a reachability certificate and is not claimed.

The previous full-node/compact census remains valid and primary experiment values are unchanged. A further complete compilation audit checks all 27,857 primary failed sets, both modes, four boarding layers and 64,166 connected origins: **14,299,778,096 cells**, maximum discrepancy **0.0 m**, with every published threshold count reproduced. Compilation uses float64 and disables fastmath.

## 2. Exact origin-set explanation of pair interaction

Let A0 be the intact accessible-origin set and Le=A0\\Ae the origins lost after closure e. Under edge deletion, Le and Lf are subsets of Lef, the joint-loss set. Define S=Le intersect Lf and N=Lef\\(Le union Lf). Inclusion-exclusion gives **C=|Lef|-|Le|-|Lf|=|N|-|S|**. S describes losses counted twice by adding single losses. N describes origins that survive either single closure but fail under both. Negative C is overlap of losses, not a beneficial effect of closing streets. Positive C is net joint-only loss; it can coexist with shared losses.

The complete [mechanism table](sensitivity-2026-11-01/all-pair-mechanisms.csv.gz) has 510,066 signature-pair/mode/parameter rows, with exact physical-pair multiplicities. Every N and S is nonnegative and every interaction reconciles. The origin bitsets are [retained](sensitivity-2026-11-01/single-loss-masks.npz) with an explicit [origin/signature index](sensitivity-2026-11-01/mask-index.json). These are deterministic set counts, not independent statistical replicates.

At W=1,000 m, K=1, bus-only pairs comprise 42,379 shared-only, 14,579 joint-only, 11,433 with both mechanisms, and 1,348,695 with neither. The corresponding full-layer counts are 40,872, 9,516, 10,430 and 1,356,268. Each row of four totals 1,417,086. A pair with both mechanisms may have positive, negative or zero net C.

### All registered extrema

{pair_table}

![Exact decomposition for every registered extreme pair](../figures/sensitivity-2026-11-02/pair-mechanisms-all-extrema.svg)

The eight signature-pair cases preserve all tied extrema. Their physical multiplicities and full failed-connection identities are in the [case registry](sensitivity-2026-11-01/path-case-registry.json). They are not eight equally probable real incidents, and repeated equivalent graphs are not independent evidence.

## 3. Path reconstruction and independent replay

`path_witnesses.py` adds predecessor forests to the original full-node reverse dynamic program. Walking Dijkstra records the next graph edge toward the selected target or boarding seed. Onboard reverse propagation records a directed consecutive-stop connection. An alighting event reduces the remaining boarding budget by one. Inherited cheaper states retain the previous layer. Strict improvements, including on zero-cost edges, avoid cycles in the selected predecessor forest. The objective remains minimum cumulative walking with at most two boardings for these cases; no speed or waiting time is assigned.

For every requested failed-set/mode state, the reconstructed full-node distances are compared against the compact origin vectors for all 64,166 connected origins and all three layers (0, 1 and 2 boardings), including finite/infinite patterns and the 1,000 m classification. There are {path['unique_state_mode_requests']} such state/mode requests and {path['unique_state_mode_requests']*64166*3:,} origin-layer comparisons. Maximum discrepancy is {path['maximum_compact_full_walking_difference_m']:.3g} m. All threshold classifications agree.

The output contains **{path['case_origin_memberships']:,} case/origin memberships**, **{path['origin_state_certificates']:,} unique origin/state/mode certificates**, and **{path['successful_paths']:,} successful paths**. The remainder are explicit failures under the walking/boarding constraint. Null minimum walking means no path within the 2,000 m search cutoff, not global disconnection. Finite values above 1,000 m also fail the selected constraint.

An independent replay reads graph records afresh and checks every walking edge endpoint, source connection direction, permitted mode, boarding/alighting permission, failed-connection exclusion, target identity, boarding ledger and summed walking cost. Maximum replay discrepancy is {pa['maximum_walking_cost_difference_m']:.3g} m. It also reconstructs coordinates and checks **all {pa['geometry']['walking_edges_checked']:,} primary walking edges** and **all {pa['geometry']['accepted_connectors_checked']:,} accepted connectors**. Synthetic split-node IDs are reconstructed from primary way progress; they are never copied by ID from a differently split model. Maximum geometric discrepancies are {pa['geometry']['maximum_edge_geometry_difference_m']:.3g} m for edges and {pa['geometry']['maximum_connector_geometry_difference_m']:.3g} m for connectors.

Artifacts: [all witnesses](sensitivity-2026-11-01/path-witnesses.jsonl.gz), [case memberships](sensitivity-2026-11-01/path-case-members.csv.gz), [failed sets](sensitivity-2026-11-01/path-failed-sets.json), [path summary](sensitivity-2026-11-01/path-summary.json), [independent replay/geometry audit](sensitivity-2026-11-01/path-audit.json), [descriptive riding lengths](sensitivity-2026-11-01/path-ride-profiles.csv.gz). Walking edge IDs refer to the frozen model and are accompanied by the used-edge and coordinate tables.

### Maps of every affected origin in the extreme cases

All markers use actual EPSG:32639 coordinates. The panels are windows around affected origins, so causal source-closure segments may be outside the displayed windows. Grey lines show accepted route traces. These maps display all affected origins in each case; overlapping markers are not a density estimate. The loss and interaction counts are supplied beside the maps and in the complete membership table.

![Extreme cases 0–1](../figures/sensitivity-2026-11-02/all-extreme-origin-maps-1.svg)

![Extreme cases 2–3](../figures/sensitivity-2026-11-02/all-extreme-origin-maps-2.svg)

![Extreme cases 4–5](../figures/sensitivity-2026-11-02/all-extreme-origin-maps-3.svg)

![Extreme cases 6–7](../figures/sensitivity-2026-11-02/all-extreme-origin-maps-4.svg)

## 4. Why the metro-benefit change can be negative

The intact accessible sets satisfy Abus subset Afull. For a matched failure, define R as bus-baseline losses rescued by the full-layer model, and E as lost full-baseline origins outside the intact bus accessible set. Then **DeltaM=Lbus-Lfull=|R|-|E|**. Thus a negative change in metro benefit is compatible with full-layer access being at least bus-only access in every intact and failed state. It does not show that adding metro physically worsens accessibility.

{negative_table}

All seven groups share 13 extra-baseline lost origins; 6 or 7 bus-baseline losses are rescued. The saved full-baseline witnesses for those extra origins use **metro then bus**, exposing a last-mile bus dependency. This is a verified model path mechanism, not evidence of actual passenger itineraries, capacity cascades or operational service failure. The seven groups represent 98 physical source segments. No negative case is omitted.

![All seven negative-benefit cases](../figures/sensitivity-2026-11-02/negative-metro-decomposition.svg)

![Illustrative certified metro-to-bus path](../figures/sensitivity-2026-11-02/metro-bus-witness.svg)

The last map selects the lexicographically first extra-baseline origin in group 105 to illustrate one certificate; this illustration is not the sample used for any quantitative result. All 13 extra-baseline locations are plotted. Platform/stop-to-trace projection is a mapping association; it is not an additional walking leg in the model. The linework can therefore have small geometric gaps at mapping associations. The model charges the documented walking-network access offsets.

Across all {path['successful_paths']:,} successful certificates, descriptive riding lengths have median {pa['riding_distance_km']['median']:.2f} km, 95th percentile {pa['riding_distance_km']['p95']:.2f} km and maximum {pa['riding_distance_km']['max']:.2f} km. These certificates are selected by walking cost, not minimum total length. Their distribution pertains to this case/witness set and must not be described as a citywide trip-length distribution. No riding-length or time feasibility bound is claimed.

## 5. Sensitivity design and construction

The 18 common-domain variants change one registered factor relative to the frozen model. They are not a Cartesian product or a probabilistic uncertainty distribution. All use the same ordered universe of 65,677 equal-weight building features. Rejected connectors remain in the denominator with infinite accessibility cost. The common failure universe stays the 1,684 primary supporting source segments, even when an expanded route set has additional supporting streets. Consequently the expanded-route results are exhaustive **on the common primary exposure domain**, not on every newly introduced dependency street.

- **Connector limits:** 25, 50, 100 (reference) and 250 m. Limits apply to origins, targets and boarding/alighting access. Through-riding is retained at inaccessible stops. A shared 250 m split graph is filtered for the smaller limits; extra degree-two split vertices preserve walking distances. The reference variant reproduces every earlier published baseline, single and pair threshold count.
- **Equal-nearest alternatives:** deterministic minimum-way-ID and maximum-way-ID policies evaluate every equal-nearest choice returned by STRtree. These are two explicit policies, not lower/upper bounds on all possible entrances. There are 431 entities with multiple nearest-way matches in these builds.
- **Origin location:** the stored representative point is replaced by the WGS84 footprint centroid, then projected to EPSG:32639. This is a geometric sensitivity assumption, not an estimated entrance. There are 426 centroids outside their own footprint; they are retained as a deliberately different location convention and reported, not called valid interior points.
- **Targets:** all screened human hospital candidates (reference), the emergency-tag subset, human candidates inside the city, and the emergency-tag subset inside the city. The network and origin universe stay fixed. These are tag/geometry definitions, not clinically verified emergency capability.
- **Context:** the available graph is restricted to city masks buffered by 1, 3, 5 and 10 km. Entire stored walking edges, geometric access connectors and riding-trace intervals must be covered. No geometry is extended beyond the available source. Agreement with the full extract indicates convergence only within this available context; unseen roads outside the extract remain untested.
- **Failure semantics:** local consecutive-stop bus-arc deletion (reference), deletion of every accepted connection of each affected recorded bus relation, and an independent-bus counterfactual that deletes no bus connections. Walking and metro remain fixed in all three. The last case is a mechanism control, not a claim that actual bus service ignores street closures.
- **Route subset:** a semantic-extension build includes continuously traced flagged relations only when their recorded stop order passes the same checks; the resulting model has 17 bus and 16 rail relations. A separate geometric-order hypothesis sorts uniquely projected stops along strict traces, while retaining the original source-member index, yielding 38 bus and 14 rail relations. The latter is an explicit reconstruction assumption, not verified operation or a silent source repair. The 360.03 m offset route remains excluded. Expanded models do not replace the frozen 11-bus/14-rail primary model.
- **Segmentation:** every supporting source way aggregates its dependent primary segments, yielding a distinct 310-unit, 47,895-pair experiment. It is reported separately because its failures have different physical lengths and meanings.

Six network builds support these comparisons. Every build passed a complete source-way/split-chain length census, with the receipts, configuration hashes, network hashes, route/stop evidence for the expanded models, and construction summaries in [model-builds.json](sensitivity-2026-11-01/model-builds.json) and its linked model-audit directories. Component summaries preserve their local build-stage wording; their historical pending fields are not the status of the complete research workflow.

{metadata}

## 6. Full-domain numerical results

The tables below use W=1,000 m and K=1, selected in the original protocol. Every value is a building-feature count. The full W/K grids for every variant are in each [variant directory](sensitivity-2026-11-01/variants/), with single effects, paired effects, exact groups/unions, source units/lengths and summary receipts. No result row is estimated from a sample.

{chr(10).join(numeric)}

![Healthy accessibility sensitivity](../figures/sensitivity-2026-11-02/sensitivity-healthy-access.svg)

![Maximum closure-loss sensitivity](../figures/sensitivity-2026-11-02/sensitivity-maximum-losses.svg)

The source-way row uses its own domain and must not be compared to source-segment rows as if the same number of equally sized failures had occurred. The [length-strata table](sensitivity-2026-11-01/length-strata.csv.gz) records every unit in bins [0,25), [25,50), [50,100), [100,250), [250,500), [500,1,000) and [1,000,infinity) metres, with loss distributions for every W/K/mode. These are descriptive length controls, not equal-total-length failure experiments and not evidence that segmentation effects are removed.

### Matched metro-loss comparisons

The following counts compare losses under exactly the same closure, at W=1,000 m, K=1. A higher loss relative to the full-layer healthy baseline does not contradict greater or equal full-layer accessibility after failure. The [complete comparison table](sensitivity-2026-11-01/metro-loss-comparisons.csv.gz) covers every W/K setting; the audit verifies nonnegative absolute post-failure metro benefit in every entry.

{metro_table}

## 7. Ranking stability and its limits

Spearman correlation is calculated over every aligned physical single unit or physical pair, using average ranks for ties. The paired vectors contain all 1,417,086 physical pairs in each common-domain comparison. Constant-vector correlations are undefined, rather than forced to zero or one. Added zeros are not extra independent observations and the resulting coefficients are descriptive agreement statistics; no p-values or confidence intervals are calculated.

Two top-set definitions are retained: fractions of the full domain, restricted to positive values; and fractions of the positive subset itself. Both include every cutoff tie. The available positive set can be smaller than the nominal full-domain size. Zero losses/interactions never enter a positive-criticality set. The table below uses the **positive-subset** 5% definition to describe high-loss rank agreement without filling the set with most or all positive units in a zero-heavy domain. Actual set sizes accompany every comparison. Empty-union Jaccard is undefined. The complete output also retains Spearman and sign agreement on the union of nonzero units to expose agreement dominated by shared zeros, as well as top-1/5/10% Jaccards for both definitions, every metric and every W/K/mode.

{rank_table}

![Ranking stability over every W/K setting, bus](../figures/sensitivity-2026-11-02/ranking-grid-bus.svg)

![Ranking stability over every W/K setting, bus and metro](../figures/sensitivity-2026-11-02/ranking-grid-bus_metro.svg)

The complete [ranking table](sensitivity-2026-11-01/ranking-stability.csv.gz) also compares all W/K settings within the primary model to W=1,000 m, K=1. Source-way single-loss rankings are compared with the maximum child-segment loss aggregated to those same 310 ways; a source-way rank is never correlated directly with an unaligned 1,684-segment vector.

## 8. Audit scope, reproducibility and publication

The [saved-output census](sensitivity-2026-11-01/sensitivity-audit.json) checks all 19 variants: each physical domain, group membership, feasible group-pair block, failed-set union, pair multiplicity, parameter/mode row, single-loss subtraction, deletion monotonicity, repeated-union agreement and every summary statistic. It verifies artifact hashes and the same ordered origin-ID digest across variants. The independent path replay verifies all requested certificate identities against the complete case-membership registry. No unrecorded sampling or runtime fallback is permitted.

The [execution receipt](sensitivity-2026-11-01/execution.json) retains the verified census start time, final output timestamp, snapshot identity, source-code and configuration identities, every variant-summary hash and the evaluated Python/package versions. It records the Windows execution environment without requiring byte-identical rebuilt SQLite files on every platform.

The complete compilation and full-node comparisons validate the primary model over every failed set. For sensitivity models, the same compiled recurrence is used with new exact walking metrics; the audits check every saved scenario and invariants, while the unit suite checks varied directed/zero-cost graphs and every reconstructed parent chain on those controls. We do not claim a second exhaustive full-node numerical census on all 19 sensitivity networks. Algebraic exactness and tested implementation equivalence should be distinguished from independent recomputation of every alternate-network distance.

The extended local unit suite passes **48 tests**, including complete parent-chain replay on 60 varied small directed/zero-cost controls, compact compilation comparisons, tie-aware ranking/positive-set definitions and the preceding solver/closure tests. Synthetic controls are algorithm tests and never enter the empirical Tehran results.

Reproduce from the extracted public archive and completed primary pipeline, using `requirements-validation.txt`:

| Code | Technical role |
| --- | --- |
| [extract_routes.py](../src/extract_routes.py) | Preserve recorded order by default; expose semantic-extension status selection and explicit geometric-order reconstruction with original member indices. |
| [build_connections.py](../src/build_connections.py) | Build complete split walking chains; optionally record coordinates, choose tied nearest ways, or change origin-point convention. Primary defaults retain their prior numerical meaning. |
| [prepare_sensitivity_models.py](../src/prepare_sensitivity_models.py) | Construct the six required models, run all-way audits, and retain normalized public build receipts and expanded-route stop/order tables. |
| [compiled_compact.py](../src/compiled_compact.py) | Float64 compiled exact walking-metric recurrence; no fastmath or distance approximation. |
| [audit_compact_compilation.py](../src/audit_compact_compilation.py) | Complete primary-domain compilation comparison and all single-loss bitsets. |
| [decompose_interactions.py](../src/decompose_interactions.py) | Exact origin-set inclusion-exclusion for every pair/mode/parameter; deterministic registry of every tied extreme and negative-benefit case. |
| [path_witnesses.py](../src/path_witnesses.py) | Full-node predecessor forests, complete origin requests in registered cases, and replayable edge/boarding/target certificates. |
| [audit_path_witnesses.py](../src/audit_path_witnesses.py) | Independently replay every saved witness; reconcile every case's membership with published losses and check every primary geometric edge/connector. |
| [sensitivity_runs.py](../src/sensitivity_runs.py) | Exact per-variant incidence/signature/union census on the full declared physical domains, with deletion/mode/budget invariants. |
| [audit_sensitivity.py](../src/audit_sensitivity.py) | Enumerate all saved domains/effect rows, reconcile every summary, expand physical-unit/pair comparisons and calculate exact ranking/top-set agreement and length strata. |
| [make_path_figures.py](../src/make_path_figures.py), [make_sensitivity_report.py](../src/make_sensitivity_report.py) | Generate all new vector figures, source manifests, result tables and this English technical record. |
| [verify_sensitivity_evidence.py](../src/verify_sensitivity_evidence.py) | Verify frozen hashes, full variant coverage, all 4,284 packed masks and vector integrity without repeating the long census. |
| [write_sensitivity_execution.py](../src/write_sensitivity_execution.py) | Bind the actually recorded UTC launch time, evaluated engine/environment and every finished variant receipt. |

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

Model/output constructors refuse accidental overwrite. To inventory existing six models after checking their complete audits, use `prepare_sensitivity_models --reuse-verified`. Dated sensitivity output directories are experiment IDs inherited from registration on 1 November; this completion record is dated 2 November. Ignored local logs and temporary runs are not public evidence. Raw generated network databases are reproducible from the public snapshot and configurations and remain ignored. Hash receipts identify the evaluated versions.

The command sequence is for a clean evidence workspace. In a checkout containing the published frozen result folder, preserve that folder before regenerating it; use the final verification command alone to check the distributed evidence. Keep the public frozen outputs available for comparison with any regenerated version. The optional `audit_sensitivity --wait-for-complete` mode waits for each full variant receipt and never substitutes partial rows.

All figures are standalone SVGs with editable text and no embedded raster data. Exact source hashes and SVG hashes are in the [path figure manifest](../figures/sensitivity-2026-11-02/path-manifest.json) and [sensitivity figure manifest](../figures/sensitivity-2026-11-02/sensitivity-manifest.json). Maps use only supplied OSM geometries and reconstructed metric coordinates.

## 9. What can be concluded at this point

### Quantitative synthesis for claim selection

At W=1,000 m, K=1, changing local arc deletion to whole-relation deletion leaves healthy access unchanged but increases the maximum bus-only joint loss from 439 to 648 building features, and the full-layer maximum from 351 to 427. Thus failure semantics matter to reported loss magnitudes. Under the independent-bus mechanism control, every single and pair loss is zero, as required by the construction; this is a verification control rather than an empirical discovery.

Reducing the connector limit to 25 m changes full-layer healthy access from 29,105 to 18,589 building features; increasing it to 250 m yields 29,461. These changes also alter the exposed origin/target/stop sets. The comparison therefore concerns the connector contract as a whole, not only the building snap distance. The full 65,677-feature denominator is fixed throughout.

The semantic-extension model has 30,604 full-layer healthy accessible origins at this setting, compared with 29,105 in the primary model. The separate derived-order hypothesis has {derived_main['bus_metro']['baseline_accessible']:,}. Neither number establishes which reconstruction matches real operation. Their complete common-exposure loss and ranking comparisons are reported rather than used to select a preferred model after seeing results.

Destination meaning is consequential: under the emergency-tag target subset, full-layer single-loss rank correlation with the primary is {fmt(target_rank['spearman'])}, and positive-subset top-5% Jaccard is {fmt(target_rank['positive_top_5pct_jaccard'])}. A single universal priority list would conceal this dependence. This target subset measures recorded tags rather than verified emergency capability.

The negative-DeltaM result is also representation-dependent. The primary has 98 physical single segments with higher loss relative to the full-layer baseline; the derived-order route model has {int(derived_higher):,} at W=1,000 m, K=1. The certified primary paths establish the mechanism in that observed subnetwork. They do not establish that its prevalence survives every route reconstruction, and the article must retain that distinction.

Across every W/K setting, exact equality of the encoded baseline/single/pair tables holds for: {', '.join(identical) if identical else 'no non-reference variant'}. The check requires identical group, connection and physical-unit indexing, identical complete single/pair effect files and identical result grids, rather than inferring equality from a rounded correlation or a few extrema. Changed outcomes occur for: {', '.join(unequal)}. Equal outcomes within these selected alternatives are finite-model robustness evidence, not proof of correct entrances, correct routing outside the extract or invariance to all model choices.

{invariants}

The finite observed model supports exact separation of joint-only losses and shared single losses, and the certified paths explain the negative metro-benefit change as exposure of additional baseline opportunities through a bus last-mile dependency. These mechanisms have concrete inspectable evidence. The 19-variant tables quantify where accessibility, losses and rankings depend on connector, target, route, boundary and failure assumptions. Assumption variation is not real-world uncertainty calibration, and the strongest effects should be reported alongside their actual sensitivity rather than summarized as a universally stable citywide ranking.

The dataset still does not establish complete operating transit service, verified entrances, population weights, emergency capacity, waiting/transfer timing or ambulance response. The primary route eligibility decisions are unchanged. The article should frame its results as a structural dependency study on a screened mapped subnetwork, with OAT sensitivity of the reported quantities. Broad claims about all Tehran passengers or hospitals would exceed this evidence.

## 10. Coverage against the original roadmap

The original roadmap contains broader analyses than the completed closure censuses. A checklist label such as “RQ1 complete” must not be interpreted as completion of every originally proposed benchmark. The current coverage is:

| Roadmap item | Actual status |
| --- | --- |
| Frozen data, route eligibility, walking graph, connectors and dependency construction | Complete within the declared mapped-data/geometric contract; real-world completeness is not certified. |
| Primary solver and preservation controls | Complete full-domain controls, documented in the preceding validation record. |
| Healthy access, every single closure and every pair in the registered primary domain | Complete for all W/K settings and both mode sets. |
| Primary pair-set mechanisms, selected-case path explanations and metro/ranking sensitivity | Complete on the explicitly registered case and OAT domains in this report. |
| Connector/target/context/failure/route OAT variants and source-way aggregation | All 19 registered variants complete; not a Cartesian product of assumptions or an equal-length-budget experiment. |
| Road-class, number-of-dependent-routes and weighted street-betweenness comparisons | Not executed. The original RQ1 comparative-benchmark clause remains open; exhaustive closure evaluation alone does not complete it. |
| Remaining network/component/route-overlap summaries, district-level loss/coverage summaries and number of reachable target groups | Not completed as the full descriptive suite originally proposed. Existing baseline/coverage figures do not substitute for those outputs. |
| Distance/shared-route correlates of pair interaction | Not executed as a separate association analysis. Exact interaction counts and case mechanisms are complete. |
| Riding-length diagnostics | Complete for every successful registered-case witness; not an all-city itinerary census or a riding-cap sensitivity experiment. |
| Combined-assumption sensitivity, equal-length failure budgets and larger multi-segment stress curves | Not executed. These are distinct extensions; the present OAT and length strata do not claim to replace them. |
| Conference claim/figure selection, literature comparison, manuscript and submission review | Pending. The SVGs here are inspectable research evidence, not a finalized conference layout. |

**Next stage:** complete or explicitly scope the still-open structural benchmarks and descriptive outputs before freezing the manuscript's claims; then consolidate conference figures and write/review the paper. The optional larger-failure/combined-assumption extensions require their own declared domains. This record completes path explanation and registered OAT/ranking analysis, without silently marking the broader roadmap as finished.
'''
    target=ROOT/'research/reports/path-sensitivity.en.md';target.write_text(text,encoding='utf-8',newline='\n')
    progress=ROOT/'research/reports/research-progress.en.md';current=progress.read_text(encoding='utf-8')
    current=current.replace('The current suite has 44 tests','The validation milestone used 44 tests')
    current=current.replace('the validation extension now contains 44, as detailed in Section 13','the validation milestone used 44; the completed path/sensitivity extension has 48, as detailed in Section 15')
    current=current.replace('The 100 m convention needs testing.','The 25/50/100/250 m connector contracts are now evaluated in Section 15; actual entrances and barriers remain unverified.')
    current=current.replace('External destinations are permitted within the available context, whose routing sufficiency has not been established by convergence tests.','External destinations are permitted within the available context. The complete registered output tables agree under the 1/3/5/10 km context restrictions (Section 15); routes outside the source extract remain untested.')
    current=current.replace('Sensitivity and interpretation are still required before using these numbers as the final evidence of a conference paper. The current implementation checks justify proceeding to the next analysis stage within the stated model; they do not guarantee a perfect dataset.','The registered path/sensitivity stage is now completed (Section 15). The broader structural comparators and descriptive outputs listed in its coverage ledger remain open before final manuscript claims. Completed finite-model checks do not certify a perfect real-world dataset.')
    if '## 14. Completed follow-up:' in current:
        first=current.index('## 14. Completed follow-up:');second=current.find('## 14. Completed follow-up:',first+1)
        if second>=0:current=current[:second]
    marker='## 15.'
    if marker in current:current=current[:current.index(marker)]
    current+='''## 15. Completed: path explanations and exhaustive sensitivity

The [technical path/sensitivity record](path-sensitivity.en.md) adds the exact origin-set mechanism decomposition for all physical pairs and all W/K/mode combinations; every tied extreme pair case and every negative-DeltaM case; 7,155 origin/state certificates with independent graph replay; all 18 common-domain OAT variants and the separate 310-way aggregation; exact ranking agreement on every physical unit/pair; full model length audits and editable SVG figures. No primary published result changes. The report explicitly separates complete finite-domain computation from uncertainty in the mapped data and assumptions.

The original roadmap also proposed structural comparators (road class, dependent-route counts and weighted street betweenness), broader component/district/target-count summaries and pair-feature association analyses. These have not been completed and are now explicitly open in the coverage ledger of the new report and the TODO. The earlier RQ1 checklist label referred too broadly to the completed closure census; it must not be read as completion of those comparative analyses. Next, complete or explicitly scope those items before the final claim/manuscript stage. Optional larger multi-segment stress curves remain a separate, unexecuted extension. Operational service validation and new external data are outside this experiment.
'''
    progress.write_text(current,encoding='utf-8',newline='\n')
    return target


if __name__=='__main__':run()
