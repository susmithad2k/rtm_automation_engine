"""
Graph metrics calculation module for analyzing node relationships and importance.
"""
from typing import Dict, Any, List
from collections import defaultdict


def calculate_node_degree(graph: Dict[str, List[str]]) -> Dict[str, int]:
    """
    Calculate the degree (number of connections) for each node in the graph.
    
    Args:
        graph: Dictionary mapping node IDs to lists of connected node IDs
        
    Returns:
        Dictionary mapping node IDs to their degree counts
    """
    degree = defaultdict(int)
    
    for node, connections in graph.items():
        degree[node] += len(connections)
        # Count incoming edges for directed graphs
        for connected_node in connections:
            degree[connected_node] += 0  # Ensure all nodes are in the result
    
    return dict(degree)


def calculate_centrality(graph: Dict[str, List[str]], metric: str = "degree") -> Dict[str, float]:
    """
    Calculate centrality metrics for nodes in the graph.
    
    Args:
        graph: Dictionary mapping node IDs to lists of connected node IDs
        metric: Type of centrality to calculate ("degree", "closeness", "betweenness")
        
    Returns:
        Dictionary mapping node IDs to their centrality scores
    """
    if metric == "degree":
        return _calculate_degree_centrality(graph)
    elif metric == "closeness":
        return _calculate_closeness_centrality(graph)
    elif metric == "betweenness":
        return _calculate_betweenness_centrality(graph)
    else:
        raise ValueError(f"Unknown centrality metric: {metric}")


def _calculate_degree_centrality(graph: Dict[str, List[str]]) -> Dict[str, float]:
    """Calculate degree centrality (normalized by number of nodes)."""
    degrees = calculate_node_degree(graph)
    num_nodes = len(graph)
    
    if num_nodes <= 1:
        return {node: 0.0 for node in graph}
    
    # Normalize by (n-1) where n is the number of nodes
    return {node: degree / (num_nodes - 1) for node, degree in degrees.items()}


def _calculate_closeness_centrality(graph: Dict[str, List[str]]) -> Dict[str, float]:
    """Calculate closeness centrality based on shortest paths."""
    centrality = {}
    
    for node in graph:
        distances = _bfs_distances(graph, node)
        if not distances:
            centrality[node] = 0.0
        else:
            total_distance = sum(distances.values())
            if total_distance > 0:
                centrality[node] = len(distances) / total_distance
            else:
                centrality[node] = 0.0
    
    return centrality


def _calculate_betweenness_centrality(graph: Dict[str, List[str]]) -> Dict[str, float]:
    """Calculate betweenness centrality (simplified version)."""
    betweenness = {node: 0.0 for node in graph}
    
    # For each pair of nodes, find shortest paths and count how many pass through each node
    nodes = list(graph.keys())
    for source in nodes:
        paths = _bfs_paths(graph, source)
        for target in nodes:
            if source != target and target in paths:
                for path in paths[target]:
                    for node in path[1:-1]:  # Exclude source and target
                        betweenness[node] += 1.0
    
    # Normalize
    num_nodes = len(nodes)
    if num_nodes > 2:
        normalization = (num_nodes - 1) * (num_nodes - 2)
        betweenness = {node: score / normalization for node, score in betweenness.items()}
    
    return betweenness


def _bfs_distances(graph: Dict[str, List[str]], start: str) -> Dict[str, int]:
    """Breadth-first search to find shortest distances from start node."""
    distances = {}
    visited = {start}
    queue = [(start, 0)]
    
    while queue:
        node, dist = queue.pop(0)
        
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                distances[neighbor] = dist + 1
                queue.append((neighbor, dist + 1))
    
    return distances


def _bfs_paths(graph: Dict[str, List[str]], start: str) -> Dict[str, List[List[str]]]:
    """Breadth-first search to find all shortest paths from start node."""
    paths = defaultdict(list)
    queue = [(start, [start])]
    visited = {start: 0}
    
    while queue:
        node, path = queue.pop(0)
        
        for neighbor in graph.get(node, []):
            new_path = path + [neighbor]
            
            if neighbor not in visited:
                visited[neighbor] = len(new_path) - 1
                paths[neighbor].append(new_path)
                queue.append((neighbor, new_path))
            elif visited[neighbor] == len(new_path) - 1:
                # Found another shortest path of the same length
                paths[neighbor].append(new_path)
    
    return paths
