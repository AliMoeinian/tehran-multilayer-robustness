"""Float64 JIT implementation of the exact compact walking-budget recurrence."""
import heapq

import numba
import numpy as np


@numba.njit(cache=True,nogil=True)
def costs(walking,transfers,target,edge_stop,edge_cost,starts,origins,
          board,alight,ride_start,ride_end,max_boardings,cutoff):
    size=len(board)
    ptr=np.zeros(size+1,dtype=np.int64)
    for end in ride_end:ptr[end+1]+=1
    for i in range(size):ptr[i+1]+=ptr[i]
    reverse=np.empty(len(ride_start),dtype=np.int64);cursor=ptr.copy()
    for i in range(len(ride_start)):
        end=ride_end[i];reverse[cursor[end]]=ride_start[i];cursor[end]+=1
    result=np.empty((max_boardings+1,len(walking)))
    result[0]=walking
    previous=np.full(size,np.inf)
    for b in range(1,max_boardings+1):
        aboard=np.full(size,np.inf)
        heap=[(np.float64(0),np.int64(0))];heap.pop()
        for i in range(size):
            if not alight[i]:continue
            value=target[i]
            if b>1:
                for j in range(size):
                    if board[j]:value=min(value,transfers[i,j]+previous[j])
            aboard[i]=value
            if np.isfinite(value):heapq.heappush(heap,(value,np.int64(i)))
        while heap:
            value,node=heapq.heappop(heap)
            if value!=aboard[node]:continue
            for edge in range(ptr[node],ptr[node+1]):
                other=reverse[edge]
                if value<aboard[other]:
                    aboard[other]=value;heapq.heappush(heap,(value,other))
        result[b]=result[b-1]
        for group in range(len(starts)):
            end=starts[group+1] if group+1<len(starts) else len(edge_stop)
            origin=origins[group];value=walking[origin]
            for edge in range(starts[group],end):
                stop=edge_stop[edge]
                if board[stop]:value=min(value,edge_cost[edge]+aboard[stop])
            value=min(value,result[b-1,origin])
            result[b,origin]=value if value<=cutoff else np.inf
        previous=aboard
    return result


def evaluate(model,stops,rides,max_boardings,cutoff,active=None):
    active=np.ones(len(stops),dtype=bool) if active is None else np.asarray(active,dtype=bool)
    board=np.array([s.board for s in stops])&active;alight=np.array([s.alight for s in stops])&active
    start=np.array([a for a,b in rides],dtype=np.int64);end=np.array([b for a,b in rides],dtype=np.int64)
    return costs(model.walking,model.transfers,model.target_cost,model.edge_stop,model.edge_cost,
                 model.starts,model.origins,board,alight,start,end,max_boardings,cutoff)
