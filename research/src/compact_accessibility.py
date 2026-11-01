"""Exact stop-metric contraction of the cumulative-walking model.

Walking shortest paths are precomputed without transit. No approximate distance,
rounding, float32 conversion, or change in boarding semantics is introduced.
"""
import heapq

import numpy as np

from .accessibility import relax_walking


def reverse_riding(values,reverse):
    result=np.array(values,copy=True);heap=[(x,i) for i,x in enumerate(result) if np.isfinite(x)]
    heapq.heapify(heap)
    while heap:
        value,node=heapq.heappop(heap)
        if value!=result[node]:continue
        for other in reverse[node]:
            if value<result[other]:
                result[other]=value;heapq.heappush(heap,(value,other))
    return result


class CompactModel:
    def __init__(self,adjacency,stops,targets,origin_anchors,origin_access,cutoff):
        self.stops=stops;self.cutoff=cutoff
        self.origin_access=np.asarray(origin_access,dtype=float)
        anchors=np.asarray(origin_anchors,dtype=int)
        zero=relax_walking(adjacency,np.full(len(adjacency),np.inf),targets,cutoff)
        self.walking=zero[anchors]+self.origin_access
        self.walking[self.walking>cutoff]=np.inf
        size=len(stops);self.transfers=np.full((size,size),np.inf)
        self.target_cost=np.full(size,np.inf)
        self.access=np.array([s.access_m for s in stops])
        stop_anchors=np.array([s.anchor for s in stops]);valid=stop_anchors>=0
        edges=[]
        # One Dijkstra per unique anchor; repeated route occurrences share it.
        for number,anchor in enumerate(sorted(set(stop_anchors[valid])),1):
            distances=relax_walking(adjacency,np.full(len(adjacency),np.inf),[(int(anchor),0)],cutoff)
            same=np.flatnonzero(stop_anchors==anchor)
            for index in same:
                self.transfers[index,valid]=self.access[index]+distances[stop_anchors[valid]]+self.access[valid]
                self.target_cost[index]=self.access[index]+zero[anchor]
                costs=self.origin_access+distances[anchors]+self.access[index]
                selected=np.flatnonzero(costs<=cutoff)
                edges.extend((int(i),int(index),float(costs[i])) for i in selected)
            if number%50==0:print('Walking metric anchors',number,flush=True)
        edges.sort()
        # CSR-like origin grouping for vectorized minimum reductions.
        self.edge_origin=np.array([e[0] for e in edges],dtype=int)
        self.edge_stop=np.array([e[1] for e in edges],dtype=int)
        self.edge_cost=np.array([e[2] for e in edges])
        if edges:
            self.starts=np.r_[0,np.flatnonzero(np.diff(self.edge_origin))+1]
            self.origins=self.edge_origin[self.starts]
        else:self.starts=np.array([],dtype=int);self.origins=np.array([],dtype=int)
        print('Compact walking incidences',len(edges),flush=True)

    def costs(self,rides,max_boardings,active=None):
        if not self.stops:return [self.walking.copy() for _ in range(max_boardings+1)]
        active=np.ones(len(self.stops),dtype=bool) if active is None else np.asarray(active,dtype=bool)
        board=np.array([s.board for s in self.stops])&active
        alight=np.array([s.alight for s in self.stops])&active
        reverse=[[] for _ in self.stops]
        for a,b in rides:reverse[b].append(a)
        target=np.where(alight,self.target_cost,np.inf)
        transfer=np.where(alight[:,None]&board[None,:],self.transfers,np.inf)
        layers=[self.walking.copy()];previous=None
        for _ in range(max_boardings):
            finish=target.copy()
            if previous is not None:
                finish=np.minimum(finish,np.min(transfer+previous[None,:],axis=1))
            onboard=reverse_riding(finish,reverse)
            allowed=np.where(board,onboard,np.inf)
            current=self.walking.copy()
            if len(self.starts):
                minimum=np.minimum.reduceat(self.edge_cost+allowed[self.edge_stop],self.starts)
                current[self.origins]=np.minimum(current[self.origins],minimum)
            # Retaining previous origin costs makes the at-most convention explicit.
            current=np.minimum(current,layers[-1]);current[current>self.cutoff]=np.inf
            layers.append(current);previous=onboard
        return layers
