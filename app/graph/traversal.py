"""
Graph traversal utilities for traceability matrix navigation.

This module provides graph-based operations for navigating and analyzing
the relationship network between requirements and test cases.
"""

from typing import Set, List, Dict, Tuple, Optional
from collections import deque, defaultdict
from sqlalchemy.orm import Session

from app.models.db_models import Requirement, TestCaseModel, Mapping
from app.db.crud import (
    get_requirements,
    get_testcases,
    get_mappings_by_requirement,
    get_mappings_by_testcase,
    get_mappings
)


class TraceabilityGraph:
    """
    Represents the traceability matrix as a bidirectional graph.
    
    Nodes represent requirements and test cases, edges represent mappings.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the traceability graph from database.
        
        Args:
            db: Database session
        """
        self.db = db
        self._req_to_tc: Dict[int, Set[int]] = defaultdict(set)
        self._tc_to_req: Dict[int, Set[int]] = defaultdict(set)
        self._build_graph()
    
    def _build_graph(self):
        """Build the graph structure from database mappings."""
        mappings = get_mappings(self.db, skip=0, limit=100000)
        
        for mapping in mappings:
            self._req_to_tc[mapping.requirement_id].add(mapping.testcase_id)
            self._tc_to_req[mapping.testcase_id].add(mapping.requirement_id)
    
    def get_testcases_for_requirement(self, requirement_id: int) -> Set[int]:
        """
        Get all test case IDs mapped to a requirement.
        
        Args:
            requirement_id: The requirement ID
            
        Returns:
            Set of test case IDs
        """
        return self._req_to_tc.get(requirement_id, set())
    
    def get_requirements_for_testcase(self, testcase_id: int) -> Set[int]:
        """
        Get all requirement IDs mapped to a test case.
        
        Args:
            testcase_id: The test case ID
            
        Returns:
            Set of requirement IDs
        """
        return self._tc_to_req.get(testcase_id, set())
    
    def get_related_testcases(
        self,
        requirement_id: int,
        depth: int = 2
    ) -> Dict[int, int]:
        """
        Find test cases related to a requirement through shared mappings.
        
        This performs a breadth-first traversal to find test cases that are
        connected through other requirements (e.g., Req1 -> TC1 -> Req2 -> TC2).
        
        Args:
            requirement_id: Starting requirement ID
            depth: Maximum traversal depth
            
        Returns:
            Dictionary mapping test case ID to distance from source
        """
        related_testcases: Dict[int, int] = {}
        visited_reqs: Set[int] = set()
        queue: deque = deque([(requirement_id, 0)])
        
        while queue:
            current_req, current_depth = queue.popleft()
            
            if current_req in visited_reqs or current_depth > depth:
                continue
            
            visited_reqs.add(current_req)
            
            # Get directly mapped test cases
            testcases = self.get_testcases_for_requirement(current_req)
            for tc_id in testcases:
                if tc_id not in related_testcases:
                    related_testcases[tc_id] = current_depth
                
                # Traverse through test case to find related requirements
                if current_depth < depth:
                    related_reqs = self.get_requirements_for_testcase(tc_id)
                    for req_id in related_reqs:
                        if req_id not in visited_reqs:
                            queue.append((req_id, current_depth + 1))
        
        return related_testcases
    
    def get_coverage_statistics(self) -> Dict[str, any]:
        """
        Calculate coverage statistics for the traceability matrix.
        
        Returns:
            Dictionary with various coverage metrics
        """
        all_requirements = get_requirements(self.db, skip=0, limit=100000)
        all_testcases = get_testcases(self.db, skip=0, limit=100000)
        
        total_requirements = len(all_requirements)
        total_testcases = len(all_testcases)
        
        covered_requirements = len([
            req for req in all_requirements 
            if self.get_testcases_for_requirement(req.id)
        ])
        
        covered_testcases = len([
            tc for tc in all_testcases 
            if self.get_requirements_for_testcase(tc.id)
        ])
        
        total_mappings = sum(len(tcs) for tcs in self._req_to_tc.values())
        
        # Calculate average mappings
        avg_testcases_per_req = (
            total_mappings / total_requirements if total_requirements > 0 else 0
        )
        avg_reqs_per_testcase = (
            total_mappings / total_testcases if total_testcases > 0 else 0
        )
        
        return {
            "total_requirements": total_requirements,
            "total_testcases": total_testcases,
            "covered_requirements": covered_requirements,
            "covered_testcases": covered_testcases,
            "uncovered_requirements": total_requirements - covered_requirements,
            "uncovered_testcases": total_testcases - covered_testcases,
            "requirement_coverage_percentage": (
                (covered_requirements / total_requirements * 100) 
                if total_requirements > 0 else 0
            ),
            "testcase_utilization_percentage": (
                (covered_testcases / total_testcases * 100) 
                if total_testcases > 0 else 0
            ),
            "total_mappings": total_mappings,
            "avg_testcases_per_requirement": avg_testcases_per_req,
            "avg_requirements_per_testcase": avg_reqs_per_testcase
        }
    
    def find_uncovered_requirements(self) -> List[int]:
        """
        Find requirements that have no test case mappings.
        
        Returns:
            List of requirement IDs without test case coverage
        """
        all_requirements = get_requirements(self.db, skip=0, limit=100000)
        return [
            req.id for req in all_requirements 
            if not self.get_testcases_for_requirement(req.id)
        ]
    
    def find_unused_testcases(self) -> List[int]:
        """
        Find test cases that are not mapped to any requirements.
        
        Returns:
            List of test case IDs not mapped to any requirements
        """
        all_testcases = get_testcases(self.db, skip=0, limit=100000)
        return [
            tc.id for tc in all_testcases 
            if not self.get_requirements_for_testcase(tc.id)
        ]
    
    def find_orphaned_items(self) -> Dict[str, List[int]]:
        """
        Find both uncovered requirements and unused test cases.
        
        Returns:
            Dictionary with 'requirements' and 'testcases' lists
        """
        return {
            "requirements": self.find_uncovered_requirements(),
            "testcases": self.find_unused_testcases()
        }
    
    def get_impact_analysis(self, requirement_id: int) -> Dict[str, any]:
        """
        Analyze the impact of changes to a requirement.
        
        Args:
            requirement_id: The requirement ID to analyze
            
        Returns:
            Dictionary with impact analysis information
        """
        directly_affected_testcases = self.get_testcases_for_requirement(requirement_id)
        
        # Find requirements that share test cases (potentially related)
        related_requirements: Set[int] = set()
        for tc_id in directly_affected_testcases:
            related_reqs = self.get_requirements_for_testcase(tc_id)
            related_requirements.update(related_reqs)
        
        # Remove the original requirement from related set
        related_requirements.discard(requirement_id)
        
        # Find indirectly affected test cases through related requirements
        indirectly_affected_testcases: Set[int] = set()
        for rel_req_id in related_requirements:
            indirectly_affected_testcases.update(
                self.get_testcases_for_requirement(rel_req_id)
            )
        
        # Remove directly affected test cases from indirect set
        indirectly_affected_testcases -= directly_affected_testcases
        
        return {
            "requirement_id": requirement_id,
            "directly_affected_testcases": list(directly_affected_testcases),
            "directly_affected_count": len(directly_affected_testcases),
            "related_requirements": list(related_requirements),
            "related_requirements_count": len(related_requirements),
            "indirectly_affected_testcases": list(indirectly_affected_testcases),
            "indirectly_affected_count": len(indirectly_affected_testcases),
            "total_impact_testcases": len(directly_affected_testcases) + len(indirectly_affected_testcases)
        }
    
    def export_graph_data(self) -> Dict[str, any]:
        """
        Export graph data in a format suitable for visualization.
        
        Returns:
            Dictionary with nodes and edges for graph visualization
        """
        nodes = []
        edges = []
        
        # Add requirement nodes
        requirements = get_requirements(self.db, skip=0, limit=100000)
        for req in requirements:
            nodes.append({
                "id": f"REQ-{req.id}",
                "type": "requirement",
                "label": req.title,
                "data": {
                    "id": req.id,
                    "title": req.title,
                    "description": req.description
                }
            })
        
        # Add test case nodes
        testcases = get_testcases(self.db, skip=0, limit=100000)
        for tc in testcases:
            nodes.append({
                "id": f"TC-{tc.id}",
                "type": "testcase",
                "label": tc.name,
                "data": {
                    "id": tc.id,
                    "name": tc.name,
                    "steps": tc.steps
                }
            })
        
        # Add edges
        for req_id, tc_ids in self._req_to_tc.items():
            for tc_id in tc_ids:
                edges.append({
                    "source": f"REQ-{req_id}",
                    "target": f"TC-{tc_id}",
                    "type": "traces_to"
                })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "statistics": self.get_coverage_statistics()
        }
    
    def find_shortest_path(
        self,
        source_req_id: int,
        target_req_id: int
    ) -> Optional[List[Tuple[str, int]]]:
        """
        Find the shortest path between two requirements through test cases.
        
        Args:
            source_req_id: Source requirement ID
            target_req_id: Target requirement ID
            
        Returns:
            List of tuples (node_type, node_id) representing the path,
            or None if no path exists
        """
        if source_req_id == target_req_id:
            return [("requirement", source_req_id)]
        
        visited: Set[int] = set()
        queue: deque = deque([
            (source_req_id, [("requirement", source_req_id)])
        ])
        
        while queue:
            current_req, path = queue.popleft()
            
            if current_req in visited:
                continue
            
            visited.add(current_req)
            
            # Explore test cases connected to this requirement
            testcases = self.get_testcases_for_requirement(current_req)
            for tc_id in testcases:
                tc_path = path + [("testcase", tc_id)]
                
                # Check if any requirement connected to this test case is the target
                next_reqs = self.get_requirements_for_testcase(tc_id)
                for next_req_id in next_reqs:
                    if next_req_id == target_req_id:
                        return tc_path + [("requirement", target_req_id)]
                    
                    if next_req_id not in visited:
                        queue.append((next_req_id, tc_path + [("requirement", next_req_id)]))
        
        return None
    
    def find_all_paths(
        self,
        source_req_id: int,
        target_req_id: int,
        max_depth: int = 5
    ) -> List[List[Tuple[str, int]]]:
        """
        Find all paths between two requirements (limited by depth).
        
        Args:
            source_req_id: Source requirement ID
            target_req_id: Target requirement ID
            max_depth: Maximum path depth to explore
            
        Returns:
            List of paths, each path is a list of (node_type, node_id) tuples
        """
        if source_req_id == target_req_id:
            return [[("requirement", source_req_id)]]
        
        all_paths: List[List[Tuple[str, int]]] = []
        
        def dfs(
            current_req: int,
            current_path: List[Tuple[str, int]],
            visited_reqs: Set[int],
            depth: int
        ):
            if depth > max_depth:
                return
            
            if current_req == target_req_id:
                all_paths.append(current_path.copy())
                return
            
            # Explore test cases
            testcases = self.get_testcases_for_requirement(current_req)
            for tc_id in testcases:
                tc_path = current_path + [("testcase", tc_id)]
                
                # Explore requirements connected through this test case
                next_reqs = self.get_requirements_for_testcase(tc_id)
                for next_req_id in next_reqs:
                    if next_req_id not in visited_reqs:
                        new_visited = visited_reqs | {next_req_id}
                        dfs(
                            next_req_id,
                            tc_path + [("requirement", next_req_id)],
                            new_visited,
                            depth + 1
                        )
        
        dfs(source_req_id, [("requirement", source_req_id)], {source_req_id}, 0)
        return all_paths
    
    def detect_cycles(self) -> List[List[int]]:
        """
        Detect cycles in the requirement-testcase graph.
        
        A cycle exists when: Req1 -> TC1 -> Req2 -> TC2 -> Req1
        
        Returns:
            List of cycles, each cycle is a list of requirement IDs
        """
        cycles: List[List[int]] = []
        visited: Set[int] = set()
        recursion_stack: Set[int] = set()
        
        def dfs_cycle(req_id: int, path: List[int]) -> bool:
            visited.add(req_id)
            recursion_stack.add(req_id)
            
            # Explore through test cases
            testcases = self.get_testcases_for_requirement(req_id)
            for tc_id in testcases:
                next_reqs = self.get_requirements_for_testcase(tc_id)
                for next_req_id in next_reqs:
                    if next_req_id not in visited:
                        if dfs_cycle(next_req_id, path + [next_req_id]):
                            return True
                    elif next_req_id in recursion_stack:
                        # Found a cycle
                        cycle_start = path.index(next_req_id)
                        cycle = path[cycle_start:] + [next_req_id]
                        if cycle not in cycles:
                            cycles.append(cycle)
            
            recursion_stack.remove(req_id)
            return False
        
        # Check all requirements
        all_requirements = get_requirements(self.db, skip=0, limit=100000)
        for req in all_requirements:
            if req.id not in visited:
                dfs_cycle(req.id, [req.id])
        
        return cycles
    
    def get_connected_components(self) -> List[Dict[str, any]]:
        """
        Find connected components in the traceability graph.
        
        A connected component is a set of requirements and test cases
        that are all connected to each other directly or indirectly.
        
        Returns:
            List of components, each with requirements and test cases
        """
        visited_reqs: Set[int] = set()
        visited_tcs: Set[int] = set()
        components: List[Dict[str, any]] = []
        
        def bfs_component(start_req_id: int) -> Dict[str, any]:
            component_reqs: Set[int] = set()
            component_tcs: Set[int] = set()
            queue: deque = deque([("req", start_req_id)])
            
            while queue:
                node_type, node_id = queue.popleft()
                
                if node_type == "req":
                    if node_id in visited_reqs:
                        continue
                    visited_reqs.add(node_id)
                    component_reqs.add(node_id)
                    
                    # Add connected test cases to queue
                    for tc_id in self.get_testcases_for_requirement(node_id):
                        if tc_id not in visited_tcs:
                            queue.append(("tc", tc_id))
                
                else:  # testcase
                    if node_id in visited_tcs:
                        continue
                    visited_tcs.add(node_id)
                    component_tcs.add(node_id)
                    
                    # Add connected requirements to queue
                    for req_id in self.get_requirements_for_testcase(node_id):
                        if req_id not in visited_reqs:
                            queue.append(("req", req_id))
            
            return {
                "requirements": list(component_reqs),
                "testcases": list(component_tcs),
                "size": len(component_reqs) + len(component_tcs)
            }
        
        # Find all components
        all_requirements = get_requirements(self.db, skip=0, limit=100000)
        for req in all_requirements:
            if req.id not in visited_reqs:
                component = bfs_component(req.id)
                components.append(component)
        
        # Check for isolated test cases (not in any component yet)
        all_testcases = get_testcases(self.db, skip=0, limit=100000)
        isolated_tcs = [tc.id for tc in all_testcases if tc.id not in visited_tcs]
        
        if isolated_tcs:
            components.append({
                "requirements": [],
                "testcases": isolated_tcs,
                "size": len(isolated_tcs)
            })
        
        return components
    
    def get_node_centrality(self, limit: int = 10) -> Dict[str, List[Dict[str, any]]]:
        """
        Calculate centrality metrics for nodes in the graph.
        
        Centrality measures how "important" or "central" a node is in the network.
        Higher centrality means more connections and influence.
        
        Args:
            limit: Number of top nodes to return for each type
            
        Returns:
            Dictionary with top requirements and test cases by centrality
        """
        # Degree centrality: number of direct connections
        req_centrality: List[Tuple[int, int]] = [
            (req_id, len(tc_ids)) 
            for req_id, tc_ids in self._req_to_tc.items()
        ]
        
        tc_centrality: List[Tuple[int, int]] = [
            (tc_id, len(req_ids)) 
            for tc_id, req_ids in self._tc_to_req.items()
        ]
        
        # Sort by centrality (descending)
        req_centrality.sort(key=lambda x: x[1], reverse=True)
        tc_centrality.sort(key=lambda x: x[1], reverse=True)
        
        return {
            "top_requirements": [
                {"id": req_id, "connections": count}
                for req_id, count in req_centrality[:limit]
            ],
            "top_testcases": [
                {"id": tc_id, "connections": count}
                for tc_id, count in tc_centrality[:limit]
            ]
        }
    
    def get_subgraph(
        self,
        requirement_ids: Optional[List[int]] = None,
        testcase_ids: Optional[List[int]] = None,
        depth: int = 1
    ) -> Dict[str, any]:
        """
        Extract a subgraph around specified nodes.
        
        Args:
            requirement_ids: List of requirement IDs to include
            testcase_ids: List of test case IDs to include
            depth: How many hops to include from seed nodes
            
        Returns:
            Dictionary with subgraph nodes and edges
        """
        subgraph_reqs: Set[int] = set(requirement_ids or [])
        subgraph_tcs: Set[int] = set(testcase_ids or [])
        
        # Expand by depth
        for _ in range(depth):
            new_reqs: Set[int] = set()
            new_tcs: Set[int] = set()
            
            # Expand from requirements
            for req_id in subgraph_reqs:
                new_tcs.update(self.get_testcases_for_requirement(req_id))
            
            # Expand from test cases
            for tc_id in subgraph_tcs:
                new_reqs.update(self.get_requirements_for_testcase(tc_id))
            
            subgraph_reqs.update(new_reqs)
            subgraph_tcs.update(new_tcs)
        
        # Build edges in the subgraph
        edges = []
        for req_id in subgraph_reqs:
            for tc_id in self.get_testcases_for_requirement(req_id):
                if tc_id in subgraph_tcs:
                    edges.append({
                        "source": req_id,
                        "target": tc_id,
                        "type": "requirement_to_testcase"
                    })
        
        return {
            "requirements": list(subgraph_reqs),
            "testcases": list(subgraph_tcs),
            "edges": edges,
            "size": len(subgraph_reqs) + len(subgraph_tcs)
        }
    
    def get_reachable_nodes(
        self,
        requirement_id: int,
        max_distance: Optional[int] = None
    ) -> Dict[str, List[Dict[str, any]]]:
        """
        Get all nodes reachable from a requirement with their distances.
        
        Args:
            requirement_id: Starting requirement ID
            max_distance: Maximum distance to traverse (None for unlimited)
            
        Returns:
            Dictionary with reachable requirements and test cases with distances
        """
        reachable_reqs: Dict[int, int] = {}
        reachable_tcs: Dict[int, int] = {}
        queue: deque = deque([("req", requirement_id, 0)])
        visited: Set[Tuple[str, int]] = set()
        
        while queue:
            node_type, node_id, distance = queue.popleft()
            
            if (node_type, node_id) in visited:
                continue
            
            if max_distance is not None and distance > max_distance:
                continue
            
            visited.add((node_type, node_id))
            
            if node_type == "req":
                if node_id != requirement_id:  # Don't include source
                    reachable_reqs[node_id] = distance
                
                # Expand to test cases
                for tc_id in self.get_testcases_for_requirement(node_id):
                    queue.append(("tc", tc_id, distance))
            
            else:  # testcase
                reachable_tcs[node_id] = distance
                
                # Expand to requirements
                for req_id in self.get_requirements_for_testcase(node_id):
                    queue.append(("req", req_id, distance + 1))
        
        return {
            "requirements": [
                {"id": req_id, "distance": dist}
                for req_id, dist in sorted(reachable_reqs.items(), key=lambda x: x[1])
            ],
            "testcases": [
                {"id": tc_id, "distance": dist}
                for tc_id, dist in sorted(reachable_tcs.items(), key=lambda x: x[1])
            ]
        }
