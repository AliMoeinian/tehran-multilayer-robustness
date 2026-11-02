"""Build the complete validation record and all-case stop-order SVG."""
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from .accessibility import ROOT


def main():
    source=ROOT/'research/reports/validation-2026-11-01'
    lengths=json.loads((source/'all-lengths.json').read_text())
    solvers=json.loads((source/'all-solvers.json').read_text())
    routes=json.loads((source/'route-dispositions.json').read_text())
    completeness=json.loads((source/'completeness.json').read_text())
    assert lengths['status']==solvers['status']=='passed' and routes['relations_reviewed']==28
    assert completeness['status']=='passed'
    traces=json.loads((ROOT/'research/model/m1-v1/traces.json').read_text())
    with (ROOT/'research/model/m1-v1/stops.csv').open(newline='') as stream:stops=list(csv.DictReader(stream))
    figure=ROOT/'research/figures/validation-2026-11-01';figure.mkdir(exist_ok=True)
    preview=ROOT/'research/runs/validation-figure-preview';preview.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':7,'svg.fonttype':'none','svg.hashsalt':'tehran-validation-v1',
        'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#89919C','axes.linewidth':.5})
    paths=[]
    for part,cases in enumerate([routes['cases'][:14],routes['cases'][14:]],1):
        fig,axes=plt.subplots(7,2,figsize=(7.1,9.4),sharey=True)
        for ax,case in zip(axes.flat,cases):
            rid=str(case['relation_id']);rows=[s for s in stops if s['route_relation_id']==rid]
            xy=np.asarray(traces[rid]['xy_m']);total=np.linalg.norm(np.diff(xy,axis=0),axis=1).sum()
            progress=np.array([float(s['trace_progress_m']) for s in rows]);values=progress/total*100
            ax.plot(range(len(rows)),values,color='#0072B2',marker='o',ms=1.6,lw=.8)
            for i in range(len(rows)-1):
                if progress[i+1]<progress[i]-1:ax.plot([i,i+1],values[i:i+2],color='#D55E00',lw=1)
            for i,s in enumerate(rows):
                if int(s['osm_id']) in case['far_stop_ids']:ax.scatter([i],[values[i]],facecolors='none',edgecolors='#202936',s=18,lw=.8,zorder=4)
            ax.set_title(f"{rid} · ref {case['ref']}",fontsize=9,pad=3)
            ax.set(ylim=(-3,103),yticks=[0,50,100],xticks=[0,len(rows)-1],xlim=(-.5,len(rows)-.5))
            ax.grid(axis='y',color='#E5E7EB',lw=.4);ax.tick_params(labelsize=7.5,length=2)
        handles=[Line2D([],[],color='#0072B2',lw=1,label='Recorded stop order'),Line2D([],[],color='#D55E00',lw=1,label='Backward progress > 1 m'),Line2D([],[],ls='',marker='o',mfc='none',mec='#202936',label='Stop offset > 100 m')]
        fig.legend(handles=handles,loc='upper center',ncol=3,frameon=False,fontsize=8)
        fig.supxlabel('Recorded source stop-sequence index (0-based)',fontsize=9,y=.012)
        fig.supylabel('Progress along the oriented trace (% of total trace length)',fontsize=9,x=.012)
        fig.tight_layout(rect=(.035,.035,1,.96),h_pad=1.3,w_pad=.6)
        path=figure/f'all-28-route-orders-part{part}.svg';fig.savefig(path,bbox_inches='tight',metadata={'Date':None})
        path.write_bytes(b'\n'.join(line.rstrip() for line in path.read_bytes().splitlines())+b'\n')
        fig.savefig(preview/f'all-28-route-orders-part{part}.png',bbox_inches='tight',dpi=170);plt.close(fig)
        paths.append(path)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    (figure/'manifest.json').write_text(json.dumps({'source_code_sha256':sha(Path(__file__)),
        'sources':{p.name:sha(p) for p in [source/'route-dispositions.json',ROOT/'research/model/m1-v1/stops.csv',ROOT/'research/model/m1-v1/traces.json']},
        'svg_sha256':{p.name:sha(p) for p in paths}},indent=2)+'\n',encoding='utf-8',newline='\n')
    def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])
    route_table=table(['Relation','Ref','Stops','Backward steps','Largest backward step (m)','Max offset (m)','Reverse-trace order','Disposition'],
        [[c['relation_id'],c['ref'],c['stop_count'],len(c['backward_transitions']),f"{max(-b['progress_change_m'] for b in c['backward_transitions']):,.2f}",f"{c['maximum_stop_distance_m']:.2f}",c['reversed_trace_order'],'Order + distance exclusion' if c['far_stop_ids'] else 'Order exclusion'] for c in routes['cases']])
    text=f'''# Closing the earlier validation tasks

**Date:** 1 November 2026. This report supersedes the earlier 20-way length spot check and selected scenario comparison. It records a complete finite-domain validation, and an explicit disposition for every previously excluded strict bus relation. It adds no external transport records.

## 1. Result and effect on the published experiment

**The stored graph and primary route subset were not changed. All published baseline, single-closure and exhaustive paired-closure threshold counts matched the full-walking-node reference.** The existing experiment tables and main figures therefore remain numerically valid; they are not regenerated with invented or silently reordered routes. The validation evidence and explanatory documentation are updated.

The route review closes eligibility decisions for the frozen primary model. It does not claim to repair the source or verify service: all 28 relations remain explicitly excluded under the recorded-order contract, with evidence for each. A geometrically reordered model would introduce a different reconstruction assumption and must be labeled and evaluated separately.

## 2. Complete way, segment and split-edge preservation

The read-only audit examined all {lengths['source_road_rows_examined']:,} source road rows and checked every eligible walking way against its source geometry. Source lengths were recomputed in EPSG:32639. Stored split chains were replayed from each original node to the next, verifying their endpoint IDs, interior anchor sequence, nonnegative lengths, and source-segment sum. This detects cancellation that a way-total-only comparison could miss.

- Walking ways checked: **{lengths['walking_ways_checked']:,}**.
- Source adjacent-node segments checked: **{lengths['source_segments_checked']:,}**.
- Stored split edges checked: **{lengths['stored_edges_checked']:,}**.
- Missing/extra chains or length discrepancies: **{lengths['failure_count']}**.
- Largest absolute way-total difference: **{lengths['maximum_way_difference_m']:.6g} m**.
- Largest absolute segment difference: **{lengths['maximum_segment_difference_m']:.6g} m**.
- Absolute audit tolerance: **{lengths['absolute_tolerance_m']:.6g} m**.

The source-way set and stored-edge set are reconciled in full. No way or edge was selected by sampling. Numerical differences are many orders below the audit tolerance; coordinates and lengths were not altered to make the audit pass. See [all-lengths.json](validation-2026-11-01/all-lengths.json) and the complete [per-way table](validation-2026-11-01/all-way-lengths.csv.gz).

## 3. Complete solver comparison

Every distinct failed-connection set from the baseline, all single signatures and all paired-closure unions was evaluated with both the compact walking-metric solver and a reference that relaxes the **full walking-node graph**. The reference uses the original reverse boarding-budget recurrence and is compiled with Numba for speed; `fastmath` is disabled and float64 costs are retained. It does not contract walking paths or use the compact transfer matrix.

- Distinct failed sets checked: **{solvers['distinct_failed_sets_checked']:,}**.
- Paired-failure unions covered: **{solvers['pair_unions_checked']:,}**; single signatures covered: **{solvers['single_signatures_checked']:,}**.
- Both mode sets and all **{solvers['boarding_layers']}** boarding layers were compared.
- Connected origins per layer: **{solvers['origins_checked_per_layer']:,}**. The other 1,511 building origins retain their common rejected-connector status and never enter either graph search.
- Origin/budget/mode/scenario cells compared: **{solvers['origin_budget_mode_scenario_cells_checked']:,}**.
- Largest finite absolute cost difference: **{solvers['maximum_absolute_difference_m']:.6g} m**.
- Numeric comparison tolerances: absolute **{solvers['absolute_tolerance_m']:.6g} m**, relative **{solvers['relative_tolerance']:.6g}**.
- Finite/infinite eligibility patterns matched, and **every published W/K threshold count matched exactly**.

There are eight failed sets beyond the paired-union domain: seven single-signature failures not generated by a distinct street pair and the intact case. This explains the scenario count. Shared failed graphs are evaluated once, which preserves every physical pair represented by the exhaustive mapping.

The compiled reference was additionally tested against the original Python solver on 30 generated small graphs at every graph node and boarding layer, and on the actual intact model's origin vectors. The exhaustive comparison is compact versus **compiled full-node reference**, not a claim that the Python interpreter separately ran every scenario. Compilation changes execution speed, not the full-node recurrence, graph, costs or budget semantics. All finite-domain scenario vectors are checked rather than only aggregate counts. Execution used {solvers['workers']} workers and took {solvers['elapsed_seconds']:.1f} seconds on the local machine.

See [all-solvers.json](validation-2026-11-01/all-solvers.json) and the [complete scenario/mode table](validation-2026-11-01/all-solver-scenarios.csv.gz). Input and source-code hashes identify the computation. The reference implementation is [full_graph_reference.py](../src/full_graph_reference.py); the census runner is [audit_all_solvers.py](../src/audit_all_solvers.py).

An independent [completeness receipt](validation-2026-11-01/completeness.json) reconciles every stored scenario/mode row against the exact baseline/single/pair domain. It also directly recomputes all three walking-only baseline counts: 7,944, 25,295 and 45,634 buildings at W=500, 1,000 and 2,000 m. All agree with the published baseline.

## 4. Disposition of all 28 excluded bus relations

For every relation, the review inspected frozen OSM relation tags and members, selected stop occurrences, original and reversed trace progress, open/closed topology, numbered ordering roles, alternative stop positions, source road-direction tags, explicit way-member direction roles, and shared stop-area membership at backward transitions.

All 28 traces are open. Every recorded stop sequence contains a backward transition greater than 1 m. Reversing the entire trace leaves 27 sequences mixed; one becomes monotone. No numbered stop-role order was available, and each relation had fewer than two alternative stop-position members. No backward transition was resolved as a shared mapped stop-area pair. One relation also has a stop offset greater than 100 m.

Of these relations, {sum(c['source_tags'].get('public_transport:version')=='2' for c in routes['cases'])} explicitly declare PTv2 and {sum('public_transport:version' not in c['source_tags'] for c in routes['cases'])} have no version tag. Exclusion under our stricter source-order contract does not establish that every legacy or unspecified relation violates a mandatory PTv2 rule. The registry preserves that distinction rather than calling all 28 relations invalid OSM records.

The reverse-monotone case is relation **21152060**, ref 201. Reversing its path would oppose 108 explicitly one-way source trace edges and 15 edges carried by an explicit direction-constraining member role. Reversing or geometrically sorting its platform list instead would change recorded stop order. That can form a derived-order hypothesis, but it does not verify the operational order. The distance-conflict case is **12107038**, refs 105;905, with a maximum offset of about 360.03 m. No route is called repaired merely by applying a preferred permutation.

{route_table}

![Source stop-order traces, cases 1–14](../figures/validation-2026-11-01/all-28-route-orders-part1.svg)

![Source stop-order traces, cases 15–28](../figures/validation-2026-11-01/all-28-route-orders-part2.svg)

**Figure 8a–b.** Every excluded relation, showing recorded stop-sequence index against progress along its existing oriented trace. Backward progress over 1 m is orange. An open marker flags an offset beyond 100 m. Progress is normalized by each trace's total metric length; the figure is not a geographic map or a service-activity claim. [SVG: cases 1–14](../figures/validation-2026-11-01/all-28-route-orders-part1.svg), [SVG: cases 15–28](../figures/validation-2026-11-01/all-28-route-orders-part2.svg).

The final registry contains **27 order-conflict exclusions and one order-plus-distance exclusion**. It includes source members, each conflicting transition, the geometric-sort candidate and the reason it was not silently substituted. This is a terminal **primary-model eligibility decision**, not a statement that the source is permanently irreparable or that the service does not operate. The quality limitation remains explicit: the primary model contains 11 bus and 14 rail relations.

OSM documentation supports treating stop ordering and direction as meaningful route information: [route relations](https://wiki.openstreetmap.org/wiki/Route_relation) and [bus mapping](https://wiki.openstreetmap.org/wiki/Buses). The [PT Assistant routing-helper documentation](https://wiki.openstreetmap.org/wiki/JOSM/Plugins/PT_Assistant/Routing_helper) also describes geometric stop sorting and warns about repeated traversals. Such a tool is an editing/reconstruction operation, not independent evidence of actual service. These references inform interpretation only; no external map records entered the model.

Full evidence: [route-dispositions.json](validation-2026-11-01/route-dispositions.json), [all consecutive-stop transitions](validation-2026-11-01/excluded-route-transitions.csv), and [review code](../src/resolve_route_exclusions.py).

## 5. Reproduction and next stage

After preparing the frozen model:

```bash
python -m pip install -r requirements-validation.txt
python -m unittest discover -s tests -v
python -m research.src.audit_all_lengths
python -m research.src.resolve_route_exclusions
python -m research.src.audit_all_solvers
python -m research.src.make_validation_report
```

The scripts read the frozen dataset and network without changing them. The solver census can take substantial time; it has no sampling or automatic runtime fallback. Validation outputs are separate from the dataset and main experiment outputs.

The previously open controls are now resolved within the frozen primary model: complete preservation audit, complete solver census, and documented final route exclusions. **Next-stage work remains path-level explanation and sensitivity analysis.** Real-world service completeness, legal boundary equivalence, verified entrances, population weights and clinical capabilities remain data/model limitations, not claims established by these checks.
'''
    if (ROOT/'research/reports/path-sensitivity.en.md').exists():
        text+='\n**Follow-up, 2 November 2026:** the path-level explanation and registered sensitivity stage is now [completed in its separate technical record](path-sensitivity.en.md). The next-stage wording above preserves this validation milestone’s original date.\n'
    (ROOT/'research/reports/validation-closure.en.md').write_text(text,encoding='utf-8',newline='\n')
    progress=ROOT/'research/reports/research-progress.en.md'
    current=progress.read_text(encoding='utf-8')
    current=current.replace('the paired-closure extension now contains 37','the validation extension now contains 44')
    current=current.replace('The current suite has 37 tests','The current suite has 44 tests')
    current=current.replace('Broader verification remains the next stage rather than an unreported claim of completeness.','The completed follow-up census is recorded in Section 14.')
    current=current.replace('The stored graph-length comparison is a sample of 20 source ways, not a full geometric survey.','The earlier 20-way length comparison is superseded by the complete source-geometry and split-chain census in Section 14.')
    current=current.replace('Stop-area reconciliation remains incomplete.','Route occurrences are not merged through stop-area labels; transfers use their geometric walking paths. This does not certify physical station entrances.')
    current=current.replace('28 were retained for review','28 were retained for review at that milestone and are now explicitly excluded after the complete case-by-case review')
    current=current.replace('**28** were retained for review:','**28** were retained for review at that milestone and now have explicit final primary-model exclusions (Section 14):')
    current=current.replace('20 sampled original way lengths agree with their split-edge sums',f"all {lengths['walking_ways_checked']:,} walking ways, {lengths['source_segments_checked']:,} source segments and {lengths['stored_edges_checked']:,} split edges pass the follow-up census")
    for marker in ['## 14. Next step:', '## 14. Completed follow-up:']:
        if marker in current:current=current[:current.index(marker)]
    # The validation generator owns section 14 only. Preserve later-stage
    # records when rerunning this earlier milestone's report generator.
    existing=progress.read_text(encoding='utf-8')
    later=existing[existing.index('## 15. Completed'): ] if '## 15. Completed' in existing else ''
    current+=f'''## 14. Completed follow-up: earlier validation tasks

The [complete validation report](validation-closure.en.md) closes the earlier length-preservation and solver-comparison controls. Every one of {lengths['walking_ways_checked']:,} walking ways and {lengths['stored_edges_checked']:,} stored edges was checked. The compact/full-node comparison covered {solvers['distinct_failed_sets_checked']:,} failed sets, both modes and all boarding layers: {solvers['origin_budget_mode_scenario_cells_checked']:,} origin-budget cells. Every published threshold count matched exactly, so the numerical experiment tables and main figures are unchanged.

All 28 previously excluded bus relations now have explicit case-by-case primary-model dispositions. They remain outside the frozen strict model because recorded order conflicts with the trace; one also fails the distance contract. Geometric reordering is a separate reconstruction hypothesis, not verified service. This resolves eligibility decisions without pretending to repair the source or make the operating bus network complete. See the complete registry and Figure 8 in the validation report.

## 15. Next step: path explanations and sensitivity

The earlier controls are closed within the frozen model. The next planned work is to trace origins and eligible paths for the positive/negative interaction cases and negative-DeltaM cases, then perform the declared sensitivity analyses. Verified entrances, operational completeness, clinical capability and population weights remain explicit data limitations. Final interpretation and ranking-stability claims remain pending.
'''
    if later:
        current=current[:current.index('## 15. Next step:')]+later
    progress.write_text(current,encoding='utf-8',newline='\n')
    paired=ROOT/'research/reports/paired-closures.en.md';current=paired.read_text(encoding='utf-8')
    current=current.replace('The suite contains **37 passing unit tests**','The suite now contains **44 passing unit tests**')
    current=current.replace('broader cross-solver and length-preservation verification belongs to the subsequent validation stage.','the [completed follow-up census](validation-closure.en.md) now supplies the full-node comparison for every failed set and the full source-length census.')
    current=current.replace('Next, complete the broader preservation/cross-solver checks, trace specific origins and paths','The broader preservation/cross-solver checks are [completed](validation-closure.en.md). Next, trace specific origins and paths')
    paired.write_text(current,encoding='utf-8',newline='\n')
    readme=ROOT/'README.md';current=readme.read_text(encoding='utf-8')
    if 'validation-closure.en.md' not in current:
        current=current.replace('## Start here','All-way length preservation, the exhaustive full-node solver comparison and final route-exclusion dispositions are documented in the [validation closure report](research/reports/validation-closure.en.md). Published experiment values are unchanged.\n\n## Start here')
    readme.write_text(current,encoding='utf-8',newline='\n')
    report_index=ROOT/'research/reports/README.md';current=report_index.read_text(encoding='utf-8')
    if 'validation-closure.en.md' not in current:
        current=current.replace('# Research reports','# Research reports\n\nThe [validation closure report](validation-closure.en.md) records the complete length/segment audit, every solver-scenario comparison, and final dispositions for all 28 excluded routes. It supersedes the earlier limited controls; primary experiment values did not change.')
    report_index.write_text(current,encoding='utf-8',newline='\n')
    print(json.dumps({'report':'research/reports/validation-closure.en.md','figure':str(path)}))


if __name__=='__main__':main()
