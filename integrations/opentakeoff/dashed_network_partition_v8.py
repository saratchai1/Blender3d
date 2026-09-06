from __future__ import annotations

import heapq
from collections import defaultdict
from typing import Any

import collinear_gap_bridge_v8 as base_bridge


def _component_maps(components: list[dict[str, Any]]) -> tuple[dict[int, dict[str, Any]], dict[int, int]]:
    by_id={int(c['id']):c for c in components}
    by_segment={int(i):int(c['id']) for c in components for i in c['segment_indexes']}
    return by_id,by_segment


def _seed_classes(tags:list[dict[str,Any]],component_by_segment:dict[int,int]) -> tuple[dict[int,set[tuple[str,str]]],dict[tuple[str,str],dict[str,Any]]]:
    by_component:dict[int,set[tuple[str,str]]]=defaultdict(set)
    meta:dict[tuple[str,str],dict[str,Any]]={}
    for tag in tags:
        index=tag.get('nearest_segment')
        if index is None or not tag.get('system') or not tag.get('diameter_key'):
            continue
        try:
            cid=int(tag.get('component_id')) if tag.get('component_id') is not None else int(component_by_segment[int(index)])
        except (KeyError,TypeError,ValueError):
            continue
        cls=(str(tag['system']),str(tag['diameter_key']))
        by_component[cid].add(cls)
        meta.setdefault(cls,{
            'system':tag['system'],'diameter_key':tag['diameter_key'],'dn':tag.get('dn'),
            'diameter_mm':tag.get('diameter_mm'),'diameter_in':tag.get('diameter_in'),
        })
    return by_component,meta


def partition_diameter_tags(
    segments:list[dict[str,Any]],
    components:list[dict[str,Any]],
    tags:list[dict[str,Any]],
    *,
    max_gap_pt:float=9.0,
    max_angle_diff_deg:float=5.0,
    tie_tolerance_pt:float=0.5,
)->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    """Reconstruct tiny collinear CAD dash gaps and partition multi-size networks.

    First, single-class bridge groups use the conservative v8.8 policy. For a
    bridge-connected group containing multiple diameters, partitioning is allowed
    only when every seed belongs to the same pipe system (e.g. CW DN15/DN20).
    Multi-source Dijkstra then labels each previously unseeded component by the
    nearest seeded class on the reconstructed component graph. Equal-distance
    labels are withheld. The gap itself is evidence only and never adds length.
    """
    component_by_id,component_by_segment=_component_maps(components)
    seed_by_component,class_meta=_seed_classes(tags,component_by_segment)
    augmented,base_events=base_bridge.bridge_diameter_tags(
        segments,components,tags,max_gap_pt=max_gap_pt,max_angle_diff_deg=max_angle_diff_deg,
    )
    events=list(base_events)

    conflicts=[e for e in base_events if e.get('status')=='WITHHELD_BRIDGE_GROUP_CONFLICTING_DIAMETERS']
    for conflict in conflicts:
        members=[int(x) for x in conflict.get('component_ids',[])]
        classes={(str(c['system']),str(c['diameter_key'])) for c in conflict.get('classes',[])}
        systems={s for s,_ in classes}
        if len(systems)!=1:
            events.append({
                'status':'WITHHELD_DASH_PARTITION_MULTIPLE_SYSTEMS',
                'component_ids':members,
                'classes':[{'system':s,'diameter_key':d} for s,d in sorted(classes)],
            })
            continue

        adjacency:dict[int,list[tuple[int,float,dict[str,Any]]]]=defaultdict(list)
        for edge in conflict.get('bridge_edges',[]):
            a=int(edge['component_a']); b=int(edge['component_b'])
            if a not in component_by_id or b not in component_by_id:
                continue
            # Midpoint-to-midpoint traversal approximation: half each existing
            # component length plus the drafting gap. Gap cost affects nearest
            # evidence only; it is never counted as pipe quantity.
            weight=(float(component_by_id[a].get('length_pt',0.0))+float(component_by_id[b].get('length_pt',0.0)))/2.0+float(edge['gap_pt'])
            adjacency[a].append((b,weight,edge)); adjacency[b].append((a,weight,edge))

        best={cid:float('inf') for cid in members}
        labels={cid:set() for cid in members}
        sources:dict[tuple[int,tuple[str,str]],int]={}
        queue:list[tuple[float,int,str,str,int]]=[]
        for cid in members:
            for cls in seed_by_component.get(cid,set()):
                if cls not in classes:
                    continue
                sources[(cid,cls)]=cid
                heapq.heappush(queue,(0.0,cid,cls[0],cls[1],cid))

        source_sets:dict[int,set[int]]={cid:set() for cid in members}
        while queue:
            distance,cid,system,diameter_key,source_cid=heapq.heappop(queue)
            cls=(system,diameter_key)
            if distance>best[cid]+tie_tolerance_pt:
                continue
            if distance+tie_tolerance_pt<best[cid]:
                best[cid]=distance; labels[cid]={cls}; source_sets[cid]={source_cid}
            elif abs(distance-best[cid])<=tie_tolerance_pt:
                labels[cid].add(cls); source_sets[cid].add(source_cid)
            for neighbor,weight,_edge in adjacency.get(cid,[]):
                new_distance=distance+weight
                if new_distance<=best[neighbor]+tie_tolerance_pt:
                    heapq.heappush(queue,(new_distance,neighbor,system,diameter_key,source_cid))

        resolved=0; tied=0; unreachable=0
        for cid in members:
            if seed_by_component.get(cid):
                continue
            component=component_by_id[cid]
            component_labels=labels[cid]
            if len(component_labels)!=1:
                if len(component_labels)>1:
                    tied+=1
                    events.append({
                        'status':'WITHHELD_DASH_PARTITION_DISTANCE_TIE','component_id':cid,
                        'layer':component.get('layer'),'classes':[{'system':s,'diameter_key':d} for s,d in sorted(component_labels)],
                        'best_distance_pt':round(float(best[cid]),3),
                    })
                else:
                    unreachable+=1
                    events.append({'status':'WITHHELD_DASH_PARTITION_UNREACHABLE','component_id':cid,'layer':component.get('layer')})
                continue
            cls=next(iter(component_labels)); meta=class_meta[cls]
            touching=[]
            for neighbor,_weight,edge in adjacency.get(cid,[]):
                touching.append((float(edge['gap_pt']),float(edge['angle_diff_deg']),neighbor,edge))
            touching.sort(key=lambda x:(x[0],x[1],x[2]))
            if not touching:
                unreachable+=1
                continue
            edge=touching[0][3]
            seed_segment=int(edge['segment_a'] if cid==int(edge['component_a']) else edge['segment_b'])
            synthetic={
                'text':'DASHED_NETWORK_NEAREST_SEED',**meta,
                'nearest_segment':seed_segment,'component_id':cid,
                'expected_layer':component.get('layer'),'associated_layer':component.get('layer'),
                'association_basis':'DASHED_NETWORK_NEAREST_DIAMETER_SEED',
                'association_status':'ASSOCIATED_BY_DASHED_NETWORK_PARTITION',
                'evidence_role':'DIAMETER_SEED_ONLY_NO_GAP_LENGTH',
                'partition_distance_pt':round(float(best[cid]),3),
                'partition_source_components':sorted(source_sets[cid]),
                'bridge_group_components':sorted(members),
            }
            augmented.append(synthetic); resolved+=1
            events.append({
                **synthetic,'status':'ACCEPTED_DASHED_NETWORK_PARTITION_SEED',
                'component_length_pt':round(float(component.get('length_pt',0.0)),3),
            })
        events.append({
            'status':'DASHED_NETWORK_PARTITION_SUMMARY','system':next(iter(systems)),
            'classes':[{'system':s,'diameter_key':d} for s,d in sorted(classes)],
            'component_count':len(members),'resolved_unseeded_components':resolved,
            'tied_unseeded_components':tied,'unreachable_unseeded_components':unreachable,
        })
    return augmented,events
