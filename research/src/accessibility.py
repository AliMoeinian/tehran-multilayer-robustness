"""Exact minimum cumulative walking with an at-most boarding budget.

Reverse dynamic programming alternates a zero-walking-cost transit propagation
and an incremental multi-source walking Dijkstra. No travel times are estimated.
"""
import argparse
import collections
import csv
from dataclasses import dataclass
import hashlib
import heapq
import json
import math
from types import SimpleNamespace
from pathlib import Path
import sqlite3

import numpy as np

ROOT=Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Stop:
    anchor: int
    access_m: float
    board: bool=True
    alight: bool=True


def relax_walking(adjacency, initial, seeds, cutoff):
    distances=np.array(initial,dtype=float,copy=True)
    heap=[]
    for node,cost in seeds:
        if cost<=cutoff and cost<distances[node]:
            distances[node]=cost
            heapq.heappush(heap,(cost,node))
    while heap:
        cost,node=heapq.heappop(heap)
        if cost!=distances[node]:continue
        for other,length in adjacency[node]:
            candidate=cost+length
            if candidate<=cutoff and candidate<distances[other]:
                distances[other]=candidate
                heapq.heappush(heap,(candidate,other))
    return distances


def solve(adjacency,stops,rides,targets,max_boardings,cutoff,walking=None):
    """Return vectors for 0..max_boardings. Stops are distinct route occurrences.

    Every new boarding consumes one unit, including reboarding the same route.
    The first boarding corresponds to zero line changes. Off-vehicle movement
    always uses walking edges and stop access lengths. Direction and entry/exit
    constraints are respected, including passing an entry-only stop on board.
    Infinity means no path within cutoff, not necessarily disconnected globally.
    """
    if max_boardings<0 or not math.isfinite(cutoff) or cutoff<0:
        raise ValueError('Invalid search budget')
    for neighbors in adjacency:
        for _,length in neighbors:
            if not math.isfinite(length) or length<0:raise ValueError('Invalid walk cost')
    if any(not math.isfinite(s.access_m) or s.access_m<0 for s in stops):
        raise ValueError('Invalid stop access cost')
    if any((s.board or s.alight) and not 0<=s.anchor<len(adjacency) for s in stops):
        raise ValueError('Active stop requires a walking anchor')
    if any(not math.isfinite(cost) or cost<0 for _,cost in targets):
        raise ValueError('Invalid target access cost')
    zero=(relax_walking(adjacency,np.full(len(adjacency),np.inf),targets,cutoff)
          if walking is None else np.array(walking,copy=True))
    reverse=[[] for _ in stops]
    for start,end in rides:reverse[end].append(start)
    layers=[zero]
    for _ in range(max_boardings):
        previous=layers[-1]
        aboard=np.full(len(stops),np.inf)
        heap=[]
        for i,s in enumerate(stops):
            if not s.alight:continue
            cost=s.access_m+previous[s.anchor]
            if cost<=cutoff:
                aboard[i]=cost;heapq.heappush(heap,(cost,i))
        while heap:
            cost,node=heapq.heappop(heap)
            if cost!=aboard[node]:continue
            for other in reverse[node]:
                if cost<aboard[other]:
                    aboard[other]=cost;heapq.heappush(heap,(cost,other))
        seeds=[(s.anchor,s.access_m+aboard[i]) for i,s in enumerate(stops) if s.board]
        layers.append(relax_walking(adjacency,previous,seeds,cutoff))
    return layers


def load_model(network,config):
    cfg=json.loads(config.read_text())
    db=sqlite3.connect(network.resolve().as_uri()+'?mode=ro',uri=True)
    config_hash=hashlib.sha256(config.read_bytes()).hexdigest()
    model_config=db.execute("select value from metadata where key='config_sha256'").fetchone()
    if model_config is None or model_config[0]!=config_hash:
        db.close()
        raise ValueError('Network and solver configurations do not match')
    with network.open('rb') as f:network_hash=hashlib.file_digest(f,'sha256').hexdigest()
    node_ids={};adjacency=[]
    def node(key):
        if key not in node_ids:
            node_ids[key]=len(adjacency);adjacency.append([])
        return node_ids[key]
    for u,v,length in db.execute('select u,v,length_m from walk_edges'):
        a,b=node(u),node(v)
        adjacency[a].append((b,length));adjacency[b].append((a,length))
    connectors={r[0]:r for r in db.execute('select entity,kind,group_id,anchor,length_m,status,board_allowed,alight_allowed from connectors')}
    targets=[(node_ids[r[3]],r[4]) for r in connectors.values() if r[1]=='hospital' and r[5]=='geometric_candidate']
    if not targets:raise ValueError('No connected target candidates')
    ride_rows=list(db.execute('select connection_id,from_stop,to_stop,mode from transit_connections'))
    rides=[(a,b,mode) for _,a,b,mode in ride_rows]
    stop_modes={s:mode for a,b,mode in rides for s in (a,b)}
    # Keep onboard occurrences even when walking access is rejected: a train or
    # bus may pass through without a boarding/alighting connector.
    stop_keys=[key for key,r in connectors.items() if r[1]=='stop']
    stop_ids={key:i for i,key in enumerate(stop_keys)}
    stops=[Stop(node_ids.get(connectors[k][3],-1),connectors[k][4],
                bool(connectors[k][6]) and connectors[k][5]=='geometric_candidate',
                bool(connectors[k][7]) and connectors[k][5]=='geometric_candidate') for k in stop_keys]
    db.close()
    return SimpleNamespace(cfg=cfg,config_hash=config_hash,network_hash=network_hash,node_ids=node_ids,adjacency=adjacency,connectors=connectors,targets=targets,rides=rides,ride_rows=ride_rows,stop_modes=stop_modes,stop_keys=stop_keys,stop_ids=stop_ids,stops=stops)


def run(network,output,config):
    cfg=json.loads(config.read_text())
    output=output.resolve()
    if not output.is_relative_to(ROOT/'research/runs'):
        raise ValueError('Output must stay in research/runs')
    if output.exists():raise FileExistsError(output)
    model=load_model(network,config)
    cfg=model.cfg
    config_hash=model.config_hash
    network_hash=model.network_hash
    node_ids=model.node_ids
    adjacency=model.adjacency
    connectors=model.connectors
    targets=model.targets
    rides=model.rides
    stop_modes=model.stop_modes
    stop_keys=model.stop_keys
    stop_ids=model.stop_ids
    stops=model.stops
    cutoff=max(cfg['walking_budgets_m']);boardings=max(cfg['max_line_changes'])+1
    print('Loaded',len(adjacency),'walking nodes;',len(stops),'stop occurrences',flush=True)
    walking=solve(adjacency,[],[],targets,0,cutoff)[0]
    vectors={'walk':[walking]}
    for name,modes in [('bus',{'bus'}),('bus_metro',{'bus','metro'})]:
        # Disable stops of removed modes as well as their riding arcs. Otherwise
        # boarding/alighting at a removed stop could form a spurious connection.
        active_stops=[Stop(s.anchor,s.access_m,s.board and stop_modes[k] in modes,
                           s.alight and stop_modes[k] in modes) for k,s in zip(stop_keys,stops)]
        active_rides=[(stop_ids[a],stop_ids[b]) for a,b,mode in rides if mode in modes and a in stop_ids and b in stop_ids]
        vectors[name]=solve(adjacency,active_stops,active_rides,targets,boardings,cutoff,walking)
        print('Solved',name,'with up to',boardings,'boardings',flush=True)
    buildings=[r for r in connectors.values() if r[1]=='building']
    eligible=sum(r[5]=='geometric_candidate' for r in buildings)
    values={}
    for mode,layers in vectors.items():
        for b,layer in enumerate(layers):
            values[mode,b]=np.array([layer[node_ids[r[3]]]+r[4] if r[5]=='geometric_candidate' else np.inf for r in buildings])
    records=[]
    for mode in vectors:
        for k in ([None] if mode=='walk' else cfg['max_line_changes']):
            b=0 if k is None else k+1
            costs=values[mode,b]
            for w in cfg['walking_budgets_m']:
                n=int(np.sum(costs<=w))
                records.append({'mode':mode,'max_line_changes':k,'walking_budget_m':w,
                    'accessible_buildings':n,'all_buildings':len(buildings),
                    'geometrically_connected_buildings':eligible,'share_all_buildings':n/len(buildings),
                    'share_connected_buildings':n/eligible if eligible else None})
    # Model invariants, not claimed as empirical discoveries.
    for mode,layers in vectors.items():
        for a,b in zip(layers,layers[1:]):assert np.all(b<=a)
    for b in range(boardings+1):assert np.all(vectors['bus_metro'][b]<=vectors['bus'][b])
    output.mkdir(parents=True)
    report={'stage':'m3-v1','network_sha256':network_hash,
        'config_sha256':config_hash,
        'search_cutoff_walking_m':cutoff,'walking_nodes':len(adjacency),'target_features':len(targets),
        'target_candidate_groups':len({r[2] for r in connectors.values() if r[1]=='hospital' and r[5]=='geometric_candidate'}),
        'boarding_convention':'at most K+1 boardings; every reboarding consumes one; no route-identity reset',
        'infinite_distance_meaning':'no path found within walking cutoff; not global disconnection',
        'results':records,'invariants':'nonincreasing cost with larger boarding budget and added metro: passed',
        'interpretation':'structural model on 11 bus and 14 rail relations; not time or population accessibility'}
    (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    with (output/'building_costs.csv').open('w',newline='') as f:
        writer=csv.writer(f);keys=list(values)
        writer.writerow(['building','connector_status']+[f'{m}_boardings_{b}' for m,b in keys])
        for i,r in enumerate(buildings):
            writer.writerow([r[0],r[5]]+[float(values[key][i]) if np.isfinite(values[key][i]) and values[key][i]<=cutoff else '' for key in keys])
    print(json.dumps(report,indent=2),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--network',type=Path,default=ROOT/'research/model/m2-v2/network.sqlite')
    p.add_argument('--output',type=Path,default=ROOT/'research/runs/m3-baseline-v1')
    p.add_argument('--config',type=Path,default=ROOT/'research/config/baseline.json')
    a=p.parse_args();run(a.network,a.output,a.config)
