"""
Lineage walker module.
Fetches and walks the downstream lineage graph from a source entity.
"""

from typing import List, Dict, Any, Tuple
from pydantic import BaseModel
from collections import deque
from lineageguard.client import OpenMetadataClient


class DownstreamEntity(BaseModel):
    """Represents an entity found downstream from the source."""
    fqn: str
    name: str
    entity_type: str
    entity_id: str
    depth: int


def get_plural_entity_type(entity_type: str) -> str:
    """Helper to pluralize entity types consistently for OpenMetadata API."""
    if entity_type == "table":
        return "tables"
    if entity_type == "dashboard":
        return "dashboards"
    if entity_type == "pipeline":
        return "pipelines"
    
    raise ValueError(f"get_plural_entity_type(): Unsupported entity_type '{entity_type}'")


def walk_downstream(
    client: OpenMetadataClient, 
    entity_fqn: str, 
    entity_type: str = "table", 
    max_depth: int = 5
) -> List[DownstreamEntity]:
    """
    Walks the downstream lineage graph starting from a specific entity FQN.
    
    Args:
        client: An authenticated OpenMetadataClient.
        entity_fqn: The Fully Qualified Name of the source entity.
        entity_type: "table", "dashboard", or "pipeline". Defaults to "table".
        max_depth: Maximum hops to search downwards.
        
    Returns:
        List of DownstreamEntity objects, sorted by depth (ascending) and fqn (alphabetically), deduplicated.
    """
    
    plural_type = get_plural_entity_type(entity_type)
    
    # 1. Fetch source entity to get UUID
    try:
        source_entity = client.get_entity_by_fqn(plural_type, entity_fqn)
    except RuntimeError as e:
        raise RuntimeError(f"[ERROR] walk_downstream(): Could not find source entity '{entity_fqn}'. Did you run seed.py? Inner error: {e}")
        
    source_id = source_entity.get("id")
    if not source_id:
        raise RuntimeError(f"[ERROR] walk_downstream(): Source entity '{entity_fqn}' did not return an 'id'.")

    # 2. Call lineage API
    # OpenMetadata 1.9.1 restricts the downstreamDepth query param to a maximum of 3
    api_depth = min(max_depth, 3)
    if max_depth > 3:
        print("[WARN] OpenMetadata restricts single lineage fetches to depth 3. Capping API parameter to 3.")
        
    raw_lineage = client.get_lineage(entity_type, source_id, upstream_depth=0, downstream_depth=api_depth)
    
    if "entity" not in raw_lineage or "nodes" not in raw_lineage:
        # Unexpected response shape
        keys = list(raw_lineage.keys())
        raise RuntimeError(
            f"[ERROR] walk_downstream(): Lineage endpoint returned unexpected shape. "
            f"Keys found: {keys}. OpenMetadata version may have changed."
        )

    # 3. Defensive edge extraction
    # edges could be under "edges" or "downstreamEdges"
    edge_list = raw_lineage.get("downstreamEdges", [])
    if not edge_list:
        edge_list = raw_lineage.get("edges", [])
        
    # Normalize edges to (from_uuid, to_uuid) tuples
    normalized_edges: List[Tuple[str, str]] = []
    
    for edge in edge_list:
        from_entity = edge.get("fromEntity")
        to_entity = edge.get("toEntity")
        
        # Depending on OM version it might be a dict {"id": "..."} or a raw string
        if isinstance(from_entity, dict):
            from_uuid = from_entity.get("id")
        else:
            from_uuid = str(from_entity)
            
        if isinstance(to_entity, dict):
            to_uuid = to_entity.get("id")
        else:
            to_uuid = str(to_entity)
            
        if from_uuid and to_uuid:
            normalized_edges.append((from_uuid, to_uuid))

    # 4. Build graph dict `from_uuid -> list[to_uuid]`
    graph: Dict[str, List[str]] = {}
    for from_u, to_u in normalized_edges:
        if from_u not in graph:
            graph[from_u] = []
        graph[from_u].append(to_u)
        
    # Map node info for easy lookup
    nodes: Dict[str, Dict[str, Any]] = {}
    for n in raw_lineage.get("nodes", []):
        n_id = n.get("id")
        if n_id:
            nodes[n_id] = n

    # 5. BFS from the source UUID, tracking depth
    distances: Dict[str, int] = {}
    distances[source_id] = 0
    
    queue = deque([source_id])
    
    while len(queue) > 0:
        current_id = queue.popleft()
        current_depth = distances[current_id]
        
        if current_depth >= max_depth:
            continue
            
        neighbors = graph.get(current_id, [])
        for neighbor_id in neighbors:
            is_unvisited = neighbor_id not in distances
            # Allow updating shorter paths (dedupe)
            is_shorter_path = neighbor_id in distances and current_depth + 1 < distances[neighbor_id]
            
            if is_unvisited or is_shorter_path:
                distances[neighbor_id] = current_depth + 1
                queue.append(neighbor_id)
                
    # 6 & 7. Build list of DownstreamEntity objects
    results: List[DownstreamEntity] = []
    
    for visited_id, depth in distances.items():
        if visited_id == source_id:
            continue
            
        # check if it's in our nodes map
        node_info = nodes.get(visited_id)
        if not node_info:
            print(f"[WARN] UUID '{visited_id}' appeared in edges but not in nodes list. Skipping.")
            continue
            
        fqn = node_info.get("fullyQualifiedName", "")
        name = node_info.get("name", "")
        n_type = node_info.get("type", "unknown")
        
        entity = DownstreamEntity(
            fqn=fqn,
            name=name,
            entity_type=n_type,
            entity_id=visited_id,
            depth=depth
        )
        results.append(entity)
        
    # Sort first by depth, then by fqn alphabetically
    results.sort(key=lambda x: (x.depth, x.fqn))
    
    return results


if __name__ == "__main__":
    try:
        with OpenMetadataClient() as client:
            source_fqn = "Stripe.stripe_db.public.raw_stripe_data"
            results = walk_downstream(client, source_fqn, entity_type="table", max_depth=5)
            
            print(f"[OK] Walked {len(results)} downstream entities from raw_stripe_data")
            print(f"{'Depth':<5} | {'Type':<10} | FQN")
            print("------+------------+------------------------------------------")
            
            for r in results:
                print(f"{str(r.depth):<5} | {r.entity_type:<10} | {r.fqn}")
                
    except RuntimeError as err:
        print(err)
        exit(1)
