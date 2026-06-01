"""
NetworkX graph builder for Requirements Traceability Matrix.

This module provides NetworkX-based graph construction and analysis
for the relationship network between requirements and test cases.
"""

# Standard library imports
import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

# Third-party imports
import networkx as nx
from sqlalchemy.orm import Session

# Local imports
from app.db.crud import get_mappings, get_requirements, get_testcases
from app.models.db_models import Mapping, Requirement, TestCaseModel
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
        
    def build_graph(
        self, 
        include_orphans: bool = True,
        add_requirement_relationships: bool = True,
        add_testcase_relationships: bool = True,
        add_similarity_edges: bool = True,
        similarity_threshold: float = 0.6
    ) -> nx.DiGraph:
        """
        Build the complete RTM graph from database with enhanced relationships.
        
        Args:
            include_orphans: If True, include requirements/testcases with no mappings
            add_requirement_relationships: Add requirement-to-requirement edges
            add_testcase_relationships: Add testcase-to-testcase edges
            add_similarity_edges: Add similarity-based edges
            similarity_threshold: Minimum similarity score (0.0-1.0) for similarity edges
            
        Returns:
            NetworkX DiGraph representing the RTM
        """
        logger.info("Building enhanced RTM graph from database")
        
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
        
        # Add primary mapping edges (requirement -> testcase)
        mappings = get_mappings(self.db, skip=0, limit=100000)
        for mapping in mappings:
            self._add_mapping_edge(mapping)
        
        # Add enhanced relationships
        if add_requirement_relationships:
            self._add_requirement_relationships()
        
        if add_testcase_relationships:
            self._add_testcase_relationships()
        
        if add_similarity_edges:
            self._add_similarity_edges(requirements, testcases, similarity_threshold)
        
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
                edge_type='maps_to',
                weight=1.0
            )
    
    def _add_requirement_relationships(self) -> None:
        """
        Add requirement-to-requirement edges based on various relationships.
        
        This includes:
        - Hierarchical relationships (parent-child based on naming)
        - Shared test coverage relationships
        """
        logger.info("Adding requirement-to-requirement relationships")
        
        req_nodes = self.get_requirement_nodes()
        
        # 1. Add hierarchical relationships based on title patterns
        # E.g., "REQ-1" -> "REQ-1.1", "US-100" -> "US-100.1"
        req_titles = {}
        for node in req_nodes:
            title = self.graph.nodes[node]['title']
            req_titles[node] = title
        
        for child_node, child_title in req_titles.items():
            # Look for potential parent patterns
            parent_pattern = self._extract_parent_id(child_title)
            if parent_pattern:
                for parent_node, parent_title in req_titles.items():
                    if parent_node != child_node and parent_title == parent_pattern:
                        self.graph.add_edge(
                            parent_node,
                            child_node,
                            edge_type='parent_of',
                            weight=1.0,
                            relationship='hierarchical'
                        )
                        logger.debug(f"Added parent-child: {parent_title} -> {child_title}")
        
        # 2. Add shared test coverage relationships
        for i, req1 in enumerate(req_nodes):
            tests1 = set(self.graph.successors(req1))
            if not tests1:
                continue
            
            for req2 in req_nodes[i+1:]:
                tests2 = set(self.graph.successors(req2))
                if not tests2:
                    continue
                
                # Calculate Jaccard similarity of test coverage
                shared_tests = tests1 & tests2
                if shared_tests:
                    jaccard = len(shared_tests) / len(tests1 | tests2)
                    if jaccard > 0.3:  # At least 30% overlap
                        self.graph.add_edge(
                            req1,
                            req2,
                            edge_type='related_via_tests',
                            weight=jaccard,
                            shared_tests=len(shared_tests),
                            relationship='shared_coverage'
                        )
                        logger.debug(
                            f"Added shared coverage: {req1} <-> {req2} "
                            f"(jaccard={jaccard:.2f})"
                        )
    
    def _add_testcase_relationships(self) -> None:
        """
        Add testcase-to-testcase edges based on shared requirement coverage.
        """
        logger.info("Adding testcase-to-testcase relationships")
        
        tc_nodes = self.get_testcase_nodes()
        
        # Add shared requirement coverage relationships
        for i, tc1 in enumerate(tc_nodes):
            reqs1 = set(self.graph.predecessors(tc1))
            if not reqs1:
                continue
            
            for tc2 in tc_nodes[i+1:]:
                reqs2 = set(self.graph.predecessors(tc2))
                if not reqs2:
                    continue
                
                # Calculate Jaccard similarity of requirement coverage
                shared_reqs = reqs1 & reqs2
                if shared_reqs:
                    jaccard = len(shared_reqs) / len(reqs1 | reqs2)
                    if jaccard > 0.3:  # At least 30% overlap
                        # Add bidirectional edges
                        self.graph.add_edge(
                            tc1,
                            tc2,
                            edge_type='related_via_requirements',
                            weight=jaccard,
                            shared_requirements=len(shared_reqs),
                            relationship='shared_requirements'
                        )
                        logger.debug(
                            f"Added shared requirements: {tc1} <-> {tc2} "
                            f"(jaccard={jaccard:.2f})"
                        )
    
    def _add_similarity_edges(
        self,
        requirements: List[Requirement],
        testcases: List[TestCaseModel],
        threshold: float = 0.6
    ) -> None:
        """
        Add similarity-based edges using text comparison.
        
        Args:
            requirements: List of requirement objects
            testcases: List of testcase objects
            threshold: Minimum similarity score (0.0-1.0)
        """
        logger.info(f"Adding similarity edges (threshold={threshold})")
        
        # Requirement similarity
        req_map = {f"REQ_{req.id}": req for req in requirements}
        req_nodes = list(req_map.keys())
        
        for i, req1_id in enumerate(req_nodes):
            req1 = req_map[req1_id]
            text1 = f"{req1.title} {req1.description or ''}"
            
            for req2_id in req_nodes[i+1:]:
                req2 = req_map[req2_id]
                text2 = f"{req2.title} {req2.description or ''}"
                
                similarity = self._calculate_text_similarity(text1, text2)
                if similarity >= threshold:
                    self.graph.add_edge(
                        req1_id,
                        req2_id,
                        edge_type='similar_to',
                        weight=similarity,
                        relationship='text_similarity'
                    )
                    logger.debug(
                        f"Added similarity: {req1.title} <-> {req2.title} "
                        f"(similarity={similarity:.2f})"
                    )
        
        # TestCase similarity
        tc_map = {f"TC_{tc.id}": tc for tc in testcases}
        tc_nodes = list(tc_map.keys())
        
        for i, tc1_id in enumerate(tc_nodes):
            tc1 = tc_map[tc1_id]
            text1 = f"{tc1.name} {tc1.steps or ''}"
            
            for tc2_id in tc_nodes[i+1:]:
                tc2 = tc_map[tc2_id]
                text2 = f"{tc2.name} {tc2.steps or ''}"
                
                similarity = self._calculate_text_similarity(text1, text2)
                if similarity >= threshold:
                    self.graph.add_edge(
                        tc1_id,
                        tc2_id,
                        edge_type='similar_to',
                        weight=similarity,
                        relationship='text_similarity'
                    )
                    logger.debug(
                        f"Added similarity: {tc1.name} <-> {tc2.name} "
                        f"(similarity={similarity:.2f})"
                    )
    
    def _extract_parent_id(self, title: str) -> Optional[str]:
        """
        Extract potential parent ID from a hierarchical title.
        
        Examples:
        - "REQ-1.1" -> "REQ-1"
        - "US-100.2" -> "US-100"
        - "FEAT-5.3.1" -> "FEAT-5.3"
        
        Args:
            title: Requirement title
            
        Returns:
            Parent title pattern or None
        """
        # Pattern: PREFIX-NUMBER.SUBNUMBER
        pattern = r'^([A-Z]+-\d+(?:\.\d+)*)\.\d+$'
        match = re.match(pattern, title)
        if match:
            return match.group(1)
        return None
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two text strings.
        
        Uses SequenceMatcher for character-level similarity.
        
        Args:
            text1: First text string
            text2: Second text string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not text1 or not text2:
            return 0.0
        
        # Normalize text
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        # Calculate similarity
        return SequenceMatcher(None, text1, text2).ratio()
    
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
        Get comprehensive graph summary statistics with edge type breakdown.
        
        Returns:
            Dictionary with various graph metrics
        """
        req_nodes = self.get_requirement_nodes()
        tc_nodes = self.get_testcase_nodes()
        
        # Count edges by type
        edge_types = defaultdict(int)
        for u, v, data in self.graph.edges(data=True):
            edge_type = data.get('edge_type', 'unknown')
            edge_types[edge_type] += 1
        
        # Basic counts
        summary = {
            'nodes': {
                'total': self.graph.number_of_nodes(),
                'requirements': len(req_nodes),
                'testcases': len(tc_nodes)
            },
            'edges': {
                'total': self.graph.number_of_edges(),
                'by_type': dict(edge_types)
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
    
    def get_requirement_hierarchy(self) -> Dict[str, List[str]]:
        """
        Get the hierarchical structure of requirements based on parent_of edges.
        
        Returns:
            Dictionary mapping parent requirement IDs to list of child IDs
        """
        hierarchy = defaultdict(list)
        
        for u, v, data in self.graph.edges(data=True):
            if data.get('edge_type') == 'parent_of':
                parent_title = self.graph.nodes[u]['title']
                child_title = self.graph.nodes[v]['title']
                hierarchy[parent_title].append(child_title)
        
        return dict(hierarchy)
    
    def find_transitive_coverage(
        self,
        requirement_id: int,
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """
        Find all test cases that transitively cover a requirement.
        
        Includes:
        - Direct test cases
        - Test cases covering child requirements
        - Test cases covering related requirements
        
        Args:
            requirement_id: Starting requirement ID
            max_depth: Maximum traversal depth
            
        Returns:
            Dictionary with coverage information
        """
        start_node = f"REQ_{requirement_id}"
        if start_node not in self.graph:
            return {'direct': [], 'transitive': [], 'depth_map': {}}
        
        # Direct test cases
        direct_tcs = list(self.graph.successors(start_node))
        direct_tc_data = [
            {
                'id': self.graph.nodes[tc]['db_id'],
                'name': self.graph.nodes[tc]['name']
            }
            for tc in direct_tcs
            if self.graph.nodes[tc]['type'] == 'testcase'
        ]
        
        # Transitive test cases via related requirements
        transitive_tcs = set()
        depth_map = {}
        visited = {start_node}
        queue = [(start_node, 0)]
        
        while queue:
            current_node, depth = queue.pop(0)
            
            if depth >= max_depth:
                continue
            
            # Get all outgoing edges
            for neighbor in self.graph.successors(current_node):
                neighbor_type = self.graph.nodes[neighbor]['type']
                
                if neighbor_type == 'testcase':
                    if neighbor not in direct_tcs:
                        transitive_tcs.add(neighbor)
                        depth_map[neighbor] = depth + 1
                
                elif neighbor_type == 'requirement' and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))
                    # Get test cases for this related requirement
                    for tc in self.graph.successors(neighbor):
                        if self.graph.nodes[tc]['type'] == 'testcase':
                            if tc not in direct_tcs:
                                transitive_tcs.add(tc)
                                if tc not in depth_map:
                                    depth_map[tc] = depth + 1
        
        transitive_tc_data = [
            {
                'id': self.graph.nodes[tc]['db_id'],
                'name': self.graph.nodes[tc]['name'],
                'depth': depth_map.get(tc, 0)
            }
            for tc in transitive_tcs
        ]
        
        return {
            'direct': direct_tc_data,
            'transitive': transitive_tc_data,
            'total_coverage': len(direct_tc_data) + len(transitive_tc_data)
        }
    
    def find_similar_requirements(
        self,
        requirement_id: int,
        min_similarity: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Find requirements similar to a given requirement.
        
        Args:
            requirement_id: Target requirement ID
            min_similarity: Minimum similarity score
            
        Returns:
            List of similar requirements with similarity scores
        """
        source_node = f"REQ_{requirement_id}"
        if source_node not in self.graph:
            return []
        
        similar = []
        for successor in self.graph.successors(source_node):
            edge_data = self.graph.edges[source_node, successor]
            if edge_data.get('edge_type') == 'similar_to':
                similarity = edge_data.get('weight', 0.0)
                if similarity >= min_similarity:
                    req_data = self.graph.nodes[successor]
                    similar.append({
                        'id': req_data['db_id'],
                        'title': req_data['title'],
                        'similarity_score': round(similarity, 3)
                    })
        
        # Also check incoming edges (bidirectional similarity)
        for predecessor in self.graph.predecessors(source_node):
            edge_data = self.graph.edges[predecessor, source_node]
            if edge_data.get('edge_type') == 'similar_to':
                similarity = edge_data.get('weight', 0.0)
                if similarity >= min_similarity:
                    req_data = self.graph.nodes[predecessor]
                    similar.append({
                        'id': req_data['db_id'],
                        'title': req_data['title'],
                        'similarity_score': round(similarity, 3)
                    })
        
        # Sort by similarity descending
        similar.sort(key=lambda x: x['similarity_score'], reverse=True)
        return similar
    
    def get_edge_types_summary(self) -> Dict[str, Any]:
        """
        Get detailed summary of all edge types in the graph.
        
        Returns:
            Dictionary with edge type statistics
        """
        edge_stats = defaultdict(lambda: {
            'count': 0,
            'avg_weight': 0.0,
            'weights': []
        })
        
        for u, v, data in self.graph.edges(data=True):
            edge_type = data.get('edge_type', 'unknown')
            weight = data.get('weight', 1.0)
            
            edge_stats[edge_type]['count'] += 1
            edge_stats[edge_type]['weights'].append(weight)
        
        # Calculate averages
        for edge_type, stats in edge_stats.items():
            if stats['weights']:
                stats['avg_weight'] = round(
                    sum(stats['weights']) / len(stats['weights']), 3
                )
                stats['min_weight'] = round(min(stats['weights']), 3)
                stats['max_weight'] = round(max(stats['weights']), 3)
            del stats['weights']  # Remove raw weights from output
        
        return dict(edge_stats)
