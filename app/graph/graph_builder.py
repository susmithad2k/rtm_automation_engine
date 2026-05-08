"""
NetworkX graph builder for Requirements Traceability Matrix.

This module provides NetworkX-based graph construction and analysis
for the relationship network between requirements and test cases.
"""

import networkx as nx
from typing import Dict, List, Set, Optional, Tuple, Any
from sqlalchemy.orm import Session
from collections import defaultdict

from app.models.db_models import Requirement, TestCaseModel, Mapping
from app.db.crud import (
    get_requirements,
    get_testcases,
    get_mappings
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RTMGraphBuilder:
    """
    Builds and manages a NetworkX graph representation of the RTM.
    
    The graph is a bipartite directed graph where:
    - Requirement nodes have type='requirement'
    - TestCase nodes have type='testcase'
    - Edges represent traceability mappings (requirement -> testcase)
    """
    
    def __init__(self, db: Session):
        """
        Initialize the graph builder.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.graph = nx.DiGraph()
        self._requirement_nodes: Set[str] = set()
        self._testcase_nodes: Set[str] = set()
        
    def build_graph(self, include_orphans: bool = True) -> nx.DiGraph:
        """
        Build the complete RTM graph from database.
        
        Args:
            include_orphans: If True, include requirements/testcases with no mappings
            
        Returns:
            NetworkX DiGraph representing the RTM
        """
        logger.info("Building RTM graph from database")
        
        # Clear existing graph
        self.graph.clear()
        self._requirement_nodes.clear()
        self._testcase_nodes.clear()
        
        # Add requirement nodes
        requirements = get_requirements(self.db, skip=0, limit=100000)
        for req in requirements:
            self._add_requirement_node(req)
        
        # Add test case nodes
        testcases = get_testcases(self.db, skip=0, limit=100000)
        for tc in testcases:
            self._add_testcase_node(tc)
        
        # Add mapping edges
        mappings = get_mappings(self.db, skip=0, limit=100000)
        for mapping in mappings:
            self._add_mapping_edge(mapping)
        
        # Remove orphans if requested
        if not include_orphans:
            self._remove_orphan_nodes()
        
        logger.info(
            f"Graph built: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges"
        )
        
        return self.graph
    
    def _add_requirement_node(self, requirement: Requirement) -> None:
        """
        Add a requirement node to the graph.
        
        Args:
            requirement: Requirement database model
        """
        node_id = f"REQ_{requirement.id}"
        self.graph.add_node(
            node_id,
            type='requirement',
            db_id=requirement.id,
            title=requirement.title,
            description=requirement.description or "",
            label=requirement.title[:50]  # Shortened for visualization
        )
        self._requirement_nodes.add(node_id)
    
    def _add_testcase_node(self, testcase: TestCaseModel) -> None:
        """
        Add a test case node to the graph.
        
        Args:
            testcase: TestCase database model
        """
        node_id = f"TC_{testcase.id}"
        self.graph.add_node(
            node_id,
            type='testcase',
            db_id=testcase.id,
            name=testcase.name,
            steps=testcase.steps or "",
            label=testcase.name[:50]  # Shortened for visualization
        )
        self._testcase_nodes.add(node_id)
    
    def _add_mapping_edge(self, mapping: Mapping) -> None:
        """
        Add a mapping edge to the graph.
        
        Args:
            mapping: Mapping database model
        """
        source = f"REQ_{mapping.requirement_id}"
        target = f"TC_{mapping.testcase_id}"
        
        if source in self.graph and target in self.graph:
            self.graph.add_edge(
                source,
                target,
                mapping_id=mapping.id,
                weight=1.0
            )
    
    def _remove_orphan_nodes(self) -> None:
        """Remove nodes with no edges (orphaned requirements/testcases)."""
        orphans = [node for node in self.graph.nodes() if self.graph.degree(node) == 0]
        self.graph.remove_nodes_from(orphans)
        logger.info(f"Removed {len(orphans)} orphan nodes")
    
    def get_requirement_nodes(self) -> List[str]:
        """Get list of all requirement node IDs."""
        return [n for n in self.graph.nodes() if self.graph.nodes[n]['type'] == 'requirement']
    
    def get_testcase_nodes(self) -> List[str]:
        """Get list of all test case node IDs."""
        return [n for n in self.graph.nodes() if self.graph.nodes[n]['type'] == 'testcase']
    
    def get_coverage_stats(self) -> Dict[str, Any]:
        """
        Calculate coverage statistics from the graph.
        
        Returns:
            Dictionary containing coverage metrics
        """
        req_nodes = self.get_requirement_nodes()
        tc_nodes = self.get_testcase_nodes()
        
        # Count requirements with at least one test case
        covered_reqs = sum(1 for req in req_nodes if self.graph.out_degree(req) > 0)
        
        # Count test cases covering at least one requirement
        active_tcs = sum(1 for tc in tc_nodes if self.graph.in_degree(tc) > 0)
        
        # Calculate coverage percentage
        coverage_pct = (covered_reqs / len(req_nodes) * 100) if req_nodes else 0.0
        
        return {
            'total_requirements': len(req_nodes),
            'total_testcases': len(tc_nodes),
            'covered_requirements': covered_reqs,
            'uncovered_requirements': len(req_nodes) - covered_reqs,
            'active_testcases': active_tcs,
            'unused_testcases': len(tc_nodes) - active_tcs,
            'coverage_percentage': round(coverage_pct, 2),
            'total_mappings': self.graph.number_of_edges()
        }
    
    def get_uncovered_requirements(self) -> List[Dict[str, Any]]:
        """
        Get list of requirements with no test case coverage.
        
        Returns:
            List of requirement details
        """
        uncovered = []
        for node in self.get_requirement_nodes():
            if self.graph.out_degree(node) == 0:
                node_data = self.graph.nodes[node]
                uncovered.append({
                    'id': node_data['db_id'],
                    'title': node_data['title'],
                    'description': node_data['description']
                })
        return uncovered
    
    def get_unused_testcases(self) -> List[Dict[str, Any]]:
        """
        Get list of test cases not covering any requirement.
        
        Returns:
            List of test case details
        """
        unused = []
        for node in self.get_testcase_nodes():
            if self.graph.in_degree(node) == 0:
                node_data = self.graph.nodes[node]
                unused.append({
                    'id': node_data['db_id'],
                    'name': node_data['name'],
                    'steps': node_data['steps']
                })
        return unused
    
    def get_testcases_for_requirement(self, requirement_id: int) -> List[Dict[str, Any]]:
        """
        Get all test cases mapped to a specific requirement.
        
        Args:
            requirement_id: Database ID of the requirement
            
        Returns:
            List of test case details
        """
        node_id = f"REQ_{requirement_id}"
        if node_id not in self.graph:
            return []
        
        testcases = []
        for successor in self.graph.successors(node_id):
            tc_data = self.graph.nodes[successor]
            testcases.append({
                'id': tc_data['db_id'],
                'name': tc_data['name'],
                'steps': tc_data['steps']
            })
        return testcases
    
    def get_requirements_for_testcase(self, testcase_id: int) -> List[Dict[str, Any]]:
        """
        Get all requirements covered by a specific test case.
        
        Args:
            testcase_id: Database ID of the test case
            
        Returns:
            List of requirement details
        """
        node_id = f"TC_{testcase_id}"
        if node_id not in self.graph:
            return []
        
        requirements = []
        for predecessor in self.graph.predecessors(node_id):
            req_data = self.graph.nodes[predecessor]
            requirements.append({
                'id': req_data['db_id'],
                'title': req_data['title'],
                'description': req_data['description']
            })
        return requirements
    
    def find_critical_testcases(self, min_coverage: int = 3) -> List[Dict[str, Any]]:
        """
        Find critical test cases that cover many requirements.
        
        Args:
            min_coverage: Minimum number of requirements to be considered critical
            
        Returns:
            List of critical test cases with their coverage count
        """
        critical = []
        for node in self.get_testcase_nodes():
            coverage_count = self.graph.in_degree(node)
            if coverage_count >= min_coverage:
                tc_data = self.graph.nodes[node]
                critical.append({
                    'id': tc_data['db_id'],
                    'name': tc_data['name'],
                    'coverage_count': coverage_count
                })
        
        # Sort by coverage count descending
        critical.sort(key=lambda x: x['coverage_count'], reverse=True)
        return critical
    
    def find_related_requirements(
        self,
        requirement_id: int,
        max_depth: int = 2
    ) -> Dict[int, int]:
        """
        Find requirements related through shared test cases.
        
        Uses BFS to find requirements connected through test cases
        (e.g., Req1 -> TC1 <- Req2).
        
        Args:
            requirement_id: Starting requirement ID
            max_depth: Maximum traversal depth
            
        Returns:
            Dictionary mapping requirement ID to distance
        """
        start_node = f"REQ_{requirement_id}"
        if start_node not in self.graph:
            return {}
        
        related = {}
        visited = {start_node}
        queue = [(start_node, 0)]
        
        while queue:
            current_node, depth = queue.pop(0)
            
            if depth >= max_depth:
                continue
            
            # Get test cases for this requirement
            for tc_node in self.graph.successors(current_node):
                # Get other requirements for these test cases
                for req_node in self.graph.predecessors(tc_node):
                    if req_node != start_node and req_node not in visited:
                        visited.add(req_node)
                        req_id = self.graph.nodes[req_node]['db_id']
                        related[req_id] = depth + 1
                        queue.append((req_node, depth + 1))
        
        return related
    
    def export_to_dict(self) -> Dict[str, Any]:
        """
        Export graph to dictionary format for serialization.
        
        Returns:
            Dictionary with nodes and edges
        """
        return {
            'nodes': [
                {
                    'id': node,
                    **self.graph.nodes[node]
                }
                for node in self.graph.nodes()
            ],
            'edges': [
                {
                    'source': u,
                    'target': v,
                    **self.graph.edges[u, v]
                }
                for u, v in self.graph.edges()
            ]
        }
    
    def get_bipartite_sets(self) -> Tuple[Set[str], Set[str]]:
        """
        Get the bipartite node sets (requirements and testcases).
        
        Returns:
            Tuple of (requirement_nodes, testcase_nodes)
        """
        return (self._requirement_nodes.copy(), self._testcase_nodes.copy())
    
    def calculate_centrality(self, centrality_type: str = 'degree') -> Dict[str, float]:
        """
        Calculate node centrality measures.
        
        Args:
            centrality_type: Type of centrality ('degree', 'betweenness', 'closeness')
            
        Returns:
            Dictionary mapping node IDs to centrality scores
        """
        if centrality_type == 'degree':
            return nx.degree_centrality(self.graph)
        elif centrality_type == 'betweenness':
            return nx.betweenness_centrality(self.graph)
        elif centrality_type == 'closeness':
            return nx.closeness_centrality(self.graph)
        else:
            raise ValueError(f"Unknown centrality type: {centrality_type}")
    
    def detect_communities(self) -> List[Set[str]]:
        """
        Detect communities/clusters in the graph using greedy modularity.
        
        Returns:
            List of node sets representing communities
        """
        # Convert to undirected for community detection
        undirected = self.graph.to_undirected()
        
        # Use greedy modularity communities
        from networkx.algorithms import community
        communities = community.greedy_modularity_communities(undirected)
        
        return [set(c) for c in communities]
    
    def get_graph_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive graph summary statistics.
        
        Returns:
            Dictionary with various graph metrics
        """
        req_nodes = self.get_requirement_nodes()
        tc_nodes = self.get_testcase_nodes()
        
        # Basic counts
        summary = {
            'nodes': {
                'total': self.graph.number_of_nodes(),
                'requirements': len(req_nodes),
                'testcases': len(tc_nodes)
            },
            'edges': {
                'total': self.graph.number_of_edges()
            }
        }
        
        # Degree statistics
        if req_nodes:
            req_out_degrees = [self.graph.out_degree(n) for n in req_nodes]
            summary['requirements_coverage'] = {
                'min': min(req_out_degrees),
                'max': max(req_out_degrees),
                'avg': round(sum(req_out_degrees) / len(req_out_degrees), 2)
            }
        
        if tc_nodes:
            tc_in_degrees = [self.graph.in_degree(n) for n in tc_nodes]
            summary['testcase_reuse'] = {
                'min': min(tc_in_degrees),
                'max': max(tc_in_degrees),
                'avg': round(sum(tc_in_degrees) / len(tc_in_degrees), 2)
            }
        
        # Connectivity
        summary['connectivity'] = {
            'is_weakly_connected': nx.is_weakly_connected(self.graph),
            'number_of_components': nx.number_weakly_connected_components(self.graph)
        }
        
        return summary
