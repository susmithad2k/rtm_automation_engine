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
