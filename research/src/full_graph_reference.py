"""Compiled full-node implementation of the original reverse-budget solver.

Every walking-node distance is computed. There is no walking-metric contraction.
Compilation disables fastmath; arrays retain float64 costs. Only the returned
origin vectors are restricted to origins, after full graph relaxation.
"""
import heapq

import numba
import numpy as np


@numba.njit(cache=True,nogil=True)
def relax(indptr,indices,lengths,initial,seed_nodes,seed_costs,cutoff):
    distances=initial.copy()
    heap=[(np.float64(0),np.int64(0))];heap.pop()
    for i in range(len(seed_nodes)):
        node=seed_nodes[i];cost=seed_costs[i]
        if cost<=cutoff and cost<distances[node]:
            distances[node]=cost;heapq.heappush(heap,(cost,node))
    while heap:
        cost,node=heapq.heappop(heap)
        if cost!=distances[node]:continue
        for edge in range(indptr[node],indptr[node+1]):
            other=indices[edge];candidate=cost+lengths[edge]
            if candidate<=cutoff and candidate<distances[other]:
                distances[other]=candidate;heapq.heappush(heap,(candidate,other))
    return distances


@numba.njit(cache=True,nogil=True)
def solve_full(indptr,indices,lengths,stop_anchor,stop_access,board,alight,
               ride_start,ride_end,walking,max_boardings,cutoff,origins,origin_access):
    stop_count=len(stop_anchor)
    counts=np.zeros(stop_count+1,dtype=np.int64)
    for end in ride_end:counts[end+1]+=1
    for i in range(stop_count):counts[i+1]+=counts[i]
    reverse=np.empty(len(ride_start),dtype=np.int64);cursor=counts.copy()
    for i in range(len(ride_start)):
        end=ride_end[i];reverse[cursor[end]]=ride_start[i];cursor[end]+=1
    previous=walking.copy();result=np.full((max_boardings+1,len(origins)),np.inf)
    for j in range(len(origins)):
        value=previous[origins[j]]+origin_access[j]
        if value<=cutoff:result[0,j]=value
    for budget in range(1,max_boardings+1):
        aboard=np.full(stop_count,np.inf)
        heap=[(np.float64(0),np.int64(0))];heap.pop()
        for i in range(stop_count):
            if alight[i]:
                value=stop_access[i]+previous[stop_anchor[i]]
                if value<=cutoff:
                    aboard[i]=value;heapq.heappush(heap,(value,np.int64(i)))
        while heap:
            cost,node=heapq.heappop(heap)
            if cost!=aboard[node]:continue
            for edge in range(counts[node],counts[node+1]):
                other=reverse[edge]
                if cost<aboard[other]:
                    aboard[other]=cost;heapq.heappush(heap,(cost,other))
        seeds=np.empty(stop_count,dtype=np.int64);costs=np.empty(stop_count);n=0
        for i in range(stop_count):
            if board[i]:
                seeds[n]=stop_anchor[i];costs[n]=stop_access[i]+aboard[i];n+=1
        previous=relax(indptr,indices,lengths,previous,seeds[:n],costs[:n],cutoff)
        for j in range(len(origins)):
            value=previous[origins[j]]+origin_access[j]
            if value<=cutoff:result[budget,j]=value
    return result


def walking_csr(adjacency):
    indptr=np.r_[0,np.cumsum([len(row) for row in adjacency])].astype(np.int64)
    indices=np.fromiter((node for row in adjacency for node,length in row),dtype=np.int64)
    lengths=np.fromiter((length for row in adjacency for node,length in row),dtype=np.float64)
    return indptr,indices,lengths
