"""
Impact analysis service for requirement change impact detection.

This module provides impact analysis functionality to identify which test cases,
requirements, and other nodes are affected when a requirement changes.
"""

from sqlalchemy.orm import Session
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from enum import Enum

from app.models.db_models import Requirement, TestCaseModel, Mapping
from app.db.crud import (
    get_requirement_by_id,
    get_testcase_by_id,
    get_requirements,
    get_testcases
)
from app.graph.traversal import TraceabilityGraph
from app.graph.graph_builder import RTMGraphBuilder
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ImpactLevel(str, Enum):
    """Enumeration of impact severity levels."""
    CRITICAL = "critical"     # Direct dependencies
    HIGH = "high"             # Immediate related items
    MEDIUM = "medium"         # Secondary dependencies
    LOW = "low"              # Distant relationships


class ImpactType(str, Enum):
    """Type of impact relationship."""
    DIRECT = "direct"                    # Directly mapped test cases
    INDIRECT = "indirect"                # Test cases via related requirements
    CASCADING = "cascading"              # Multiple hops away
    BIDIRECTIONAL = "bidirectional"      # Shared test cases


@dataclass
class ImpactedNode:
    """Represents a node impacted by a change."""
    node_id: int
    node_type: str  # 'requirement' or 'testcase'
    title: str
    impact_type: ImpactType
    impact_level: ImpactLevel
    distance: int  # Graph distance from source
    path_count: int  # Number of paths to this node
    shared_dependencies: int  # Number of shared dependencies
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ImpactAnalysisResult:
    """Complete impact analysis result."""
    source_requirement_id: int
    source_requirement_title: str
    total_impacted_nodes: int
    impacted_testcases: List[ImpactedNode]
    impacted_requirements: List[ImpactedNode]
    impact_summary: Dict[str, Any]
    risk_assessment: Dict[str, Any]


class ImpactAnalysisService:
    """
    Service for analyzing the impact of requirement changes.
    
    This service identifies all nodes (test cases and requirements) that would be
    affected by changes to a given requirement, categorizes the impact, and provides
    risk assessment.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the impact analysis service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.graph = TraceabilityGraph(db)
        self.nx_graph_builder = RTMGraphBuilder(db)
    
    def detect_impacted_nodes(
        self,
        requirement_id: int,
        max_depth: int = 3,
        include_risk_assessment: bool = True
    ) -> ImpactAnalysisResult:
        """
        Detect all nodes impacted by changes to a requirement.
        
        This performs a comprehensive impact analysis including:
        - Directly mapped test cases
        - Related requirements (sharing test cases)
        - Indirectly affected test cases
        - Cascading impacts through the graph
        
        Args:
            requirement_id: The requirement ID to analyze
            max_depth: Maximum graph traversal depth for cascade detection
            include_risk_assessment: Whether to include risk assessment
            
        Returns:
            ImpactAnalysisResult containing detailed impact information
        """
        logger.info(f"Detecting impacted nodes for requirement {requirement_id}")
        
        # Get source requirement
        source_req = get_requirement_by_id(self.db, requirement_id)
        if not source_req:
            raise ValueError(f"Requirement {requirement_id} not found")
        
        # Detect directly impacted test cases
        directly_impacted_tcs = self._detect_direct_testcases(requirement_id)
        
        # Initialize empty lists for deeper analysis
        related_requirements = []
        indirectly_impacted_tcs = []
        cascading_impacts = {'testcases': [], 'requirements': []}
        
        # Only detect indirect impacts if max_depth > 1
        if max_depth > 1:
            # Detect related requirements (sharing test cases)
            related_requirements = self._detect_related_requirements(
                requirement_id,
                directly_impacted_tcs
            )
            
            # Detect indirectly impacted test cases
            indirectly_impacted_tcs = self._detect_indirect_testcases(
                related_requirements,
                directly_impacted_tcs
            )
            
            # Detect cascading impacts only if max_depth > 2
            if max_depth > 2:
                cascading_impacts = self._detect_cascading_impacts(
                    requirement_id,
                    max_depth
                )
        
        # Combine all impacted nodes
        all_impacted_tcs = self._merge_impacted_testcases(
            directly_impacted_tcs,
            indirectly_impacted_tcs,
            cascading_impacts.get('testcases', [])
        )
        
        all_impacted_reqs = self._merge_impacted_requirements(
            related_requirements,
            cascading_impacts.get('requirements', [])
        )
        
        # Generate impact summary
        impact_summary = self._generate_impact_summary(
            all_impacted_tcs,
            all_impacted_reqs
        )
        
        # Perform risk assessment
        risk_assessment = {}
        if include_risk_assessment:
            risk_assessment = self._assess_impact_risk(
                requirement_id,
                all_impacted_tcs,
                all_impacted_reqs
            )
        
        result = ImpactAnalysisResult(
            source_requirement_id=requirement_id,
            source_requirement_title=source_req.title,
            total_impacted_nodes=len(all_impacted_tcs) + len(all_impacted_reqs),
            impacted_testcases=all_impacted_tcs,
            impacted_requirements=all_impacted_reqs,
            impact_summary=impact_summary,
            risk_assessment=risk_assessment
        )
        
        logger.info(
            f"Impact analysis complete: {result.total_impacted_nodes} nodes impacted"
        )
        
        return result
    
    def _detect_direct_testcases(
        self,
        requirement_id: int
    ) -> List[ImpactedNode]:
        """
        Detect test cases directly mapped to a requirement.
        
        Args:
            requirement_id: The requirement ID
            
        Returns:
            List of directly impacted test case nodes
        """
        tc_ids = self.graph.get_testcases_for_requirement(requirement_id)
        impacted_nodes = []
        
        for tc_id in tc_ids:
            testcase = get_testcase_by_id(self.db, tc_id)
            if testcase:
                # Count how many requirements this test case covers
                req_count = len(self.graph.get_requirements_for_testcase(tc_id))
                
                impacted_nodes.append(ImpactedNode(
                    node_id=tc_id,
                    node_type='testcase',
                    title=testcase.name,
                    impact_type=ImpactType.DIRECT,
                    impact_level=ImpactLevel.CRITICAL,
                    distance=1,
                    path_count=1,
                    shared_dependencies=req_count,
                    metadata={
                        'steps': testcase.steps,
                        'covers_multiple_requirements': req_count > 1
                    }
                ))
        
        return impacted_nodes
    
    def _detect_related_requirements(
        self,
        requirement_id: int,
        directly_impacted_tcs: List[ImpactedNode]
    ) -> List[ImpactedNode]:
        """
        Detect requirements related through shared test cases.
        
        Args:
            requirement_id: The source requirement ID
            directly_impacted_tcs: Directly impacted test cases
            
        Returns:
            List of related requirement nodes
        """
        related_req_ids: Set[int] = set()
        req_impact_count: Dict[int, int] = {}
        
        # Find requirements sharing test cases
        for tc_node in directly_impacted_tcs:
            req_ids = self.graph.get_requirements_for_testcase(tc_node.node_id)
            for req_id in req_ids:
                if req_id != requirement_id:
                    related_req_ids.add(req_id)
                    req_impact_count[req_id] = req_impact_count.get(req_id, 0) + 1
        
        impacted_nodes = []
        for req_id in related_req_ids:
            requirement = get_requirement_by_id(self.db, req_id)
            if requirement:
                shared_count = req_impact_count[req_id]
                total_tc_count = len(self.graph.get_testcases_for_requirement(req_id))
                
                # Determine impact level based on shared test case percentage
                if total_tc_count > 0:
                    shared_percentage = (shared_count / total_tc_count) * 100
                    if shared_percentage >= 50:
                        impact_level = ImpactLevel.HIGH
                    elif shared_percentage >= 25:
                        impact_level = ImpactLevel.MEDIUM
                    else:
                        impact_level = ImpactLevel.LOW
                else:
                    impact_level = ImpactLevel.LOW
                
                impacted_nodes.append(ImpactedNode(
                    node_id=req_id,
                    node_type='requirement',
                    title=requirement.title,
                    impact_type=ImpactType.BIDIRECTIONAL,
                    impact_level=impact_level,
                    distance=2,
                    path_count=shared_count,
                    shared_dependencies=shared_count,
                    metadata={
                        'description': requirement.description,
                        'shared_testcase_percentage': round(
                            (shared_count / total_tc_count * 100) if total_tc_count > 0 else 0,
                            2
                        )
                    }
                ))
        
        return impacted_nodes
    
    def _detect_indirect_testcases(
        self,
        related_requirements: List[ImpactedNode],
        directly_impacted_tcs: List[ImpactedNode]
    ) -> List[ImpactedNode]:
        """
        Detect test cases indirectly affected through related requirements.
        
        Args:
            related_requirements: Related requirement nodes
            directly_impacted_tcs: Directly impacted test case nodes
            
        Returns:
            List of indirectly impacted test case nodes
        """
        direct_tc_ids = {node.node_id for node in directly_impacted_tcs}
        indirect_tc_map: Dict[int, int] = {}  # tc_id -> path_count
        
        for req_node in related_requirements:
            tc_ids = self.graph.get_testcases_for_requirement(req_node.node_id)
            for tc_id in tc_ids:
                if tc_id not in direct_tc_ids:
                    indirect_tc_map[tc_id] = indirect_tc_map.get(tc_id, 0) + 1
        
        impacted_nodes = []
        for tc_id, path_count in indirect_tc_map.items():
            testcase = get_testcase_by_id(self.db, tc_id)
            if testcase:
                # Determine impact level based on number of paths
                if path_count >= 3:
                    impact_level = ImpactLevel.HIGH
                elif path_count >= 2:
                    impact_level = ImpactLevel.MEDIUM
                else:
                    impact_level = ImpactLevel.LOW
                
                impacted_nodes.append(ImpactedNode(
                    node_id=tc_id,
                    node_type='testcase',
                    title=testcase.name,
                    impact_type=ImpactType.INDIRECT,
                    impact_level=impact_level,
                    distance=3,
                    path_count=path_count,
                    shared_dependencies=len(
                        self.graph.get_requirements_for_testcase(tc_id)
                    ),
                    metadata={
                        'steps': testcase.steps,
                        'impact_paths': path_count
                    }
                ))
        
        return impacted_nodes
    
    def _detect_cascading_impacts(
        self,
        requirement_id: int,
        max_depth: int
    ) -> Dict[str, List[ImpactedNode]]:
        """
        Detect cascading impacts through multi-hop graph traversal.
        
        Args:
            requirement_id: The source requirement ID
            max_depth: Maximum traversal depth
            
        Returns:
            Dictionary with 'testcases' and 'requirements' lists
        """
        related_testcases = self.graph.get_related_testcases(
            requirement_id,
            depth=max_depth
        )
        
        cascading_tcs = []
        for tc_id, distance in related_testcases.items():
            if distance > 1:  # Beyond direct impact
                testcase = get_testcase_by_id(self.db, tc_id)
                if testcase:
                    # Calculate impact level based on distance
                    if distance == 2:
                        impact_level = ImpactLevel.MEDIUM
                    else:
                        impact_level = ImpactLevel.LOW
                    
                    cascading_tcs.append(ImpactedNode(
                        node_id=tc_id,
                        node_type='testcase',
                        title=testcase.name,
                        impact_type=ImpactType.CASCADING,
                        impact_level=impact_level,
                        distance=distance,
                        path_count=1,
                        shared_dependencies=len(
                            self.graph.get_requirements_for_testcase(tc_id)
                        ),
                        metadata={'graph_distance': distance}
                    ))
        
        return {
            'testcases': cascading_tcs,
            'requirements': []
        }
    
    def _merge_impacted_testcases(
        self,
        *testcase_lists: List[ImpactedNode]
    ) -> List[ImpactedNode]:
        """
        Merge multiple lists of impacted test cases, keeping highest impact.
        
        Args:
            testcase_lists: Variable number of test case node lists
            
        Returns:
            Merged and deduplicated list of test case nodes
        """
        tc_map: Dict[int, ImpactedNode] = {}
        impact_priority = {
            ImpactLevel.CRITICAL: 4,
            ImpactLevel.HIGH: 3,
            ImpactLevel.MEDIUM: 2,
            ImpactLevel.LOW: 1
        }
        
        for tc_list in testcase_lists:
            for tc_node in tc_list:
                existing = tc_map.get(tc_node.node_id)
                if existing:
                    # Keep the node with higher impact level
                    if impact_priority[tc_node.impact_level] > impact_priority[existing.impact_level]:
                        tc_map[tc_node.node_id] = tc_node
                    else:
                        # Update path count and distance
                        existing.path_count += tc_node.path_count
                        existing.distance = min(existing.distance, tc_node.distance)
                else:
                    tc_map[tc_node.node_id] = tc_node
        
        # Sort by impact level (critical first) then by title
        sorted_tcs = sorted(
            tc_map.values(),
            key=lambda x: (impact_priority[x.impact_level], x.title),
            reverse=True
        )
        
        return sorted_tcs
    
    def _merge_impacted_requirements(
        self,
        *requirement_lists: List[ImpactedNode]
    ) -> List[ImpactedNode]:
        """
        Merge multiple lists of impacted requirements, keeping highest impact.
        
        Args:
            requirement_lists: Variable number of requirement node lists
            
        Returns:
            Merged and deduplicated list of requirement nodes
        """
        req_map: Dict[int, ImpactedNode] = {}
        impact_priority = {
            ImpactLevel.CRITICAL: 4,
            ImpactLevel.HIGH: 3,
            ImpactLevel.MEDIUM: 2,
            ImpactLevel.LOW: 1
        }
        
        for req_list in requirement_lists:
            for req_node in req_list:
                existing = req_map.get(req_node.node_id)
                if existing:
                    if impact_priority[req_node.impact_level] > impact_priority[existing.impact_level]:
                        req_map[req_node.node_id] = req_node
                    else:
                        existing.path_count += req_node.path_count
                        existing.distance = min(existing.distance, req_node.distance)
                else:
                    req_map[req_node.node_id] = req_node
        
        # Sort by impact level then by title
        sorted_reqs = sorted(
            req_map.values(),
            key=lambda x: (impact_priority[x.impact_level], x.title),
            reverse=True
        )
        
        return sorted_reqs
    
    def _generate_impact_summary(
        self,
        impacted_testcases: List[ImpactedNode],
        impacted_requirements: List[ImpactedNode]
    ) -> Dict[str, Any]:
        """
        Generate a summary of the impact analysis.
        
        Args:
            impacted_testcases: List of impacted test case nodes
            impacted_requirements: List of impacted requirement nodes
            
        Returns:
            Dictionary containing impact summary statistics
        """
        # Count by impact type
        tc_by_type = {}
        for tc in impacted_testcases:
            tc_by_type[tc.impact_type.value] = tc_by_type.get(tc.impact_type.value, 0) + 1
        
        # Count by impact level
        tc_by_level = {}
        for tc in impacted_testcases:
            tc_by_level[tc.impact_level.value] = tc_by_level.get(tc.impact_level.value, 0) + 1
        
        req_by_level = {}
        for req in impacted_requirements:
            req_by_level[req.impact_level.value] = req_by_level.get(req.impact_level.value, 0) + 1
        
        return {
            'total_impacted_testcases': len(impacted_testcases),
            'total_impacted_requirements': len(impacted_requirements),
            'testcases_by_impact_type': tc_by_type,
            'testcases_by_impact_level': tc_by_level,
            'requirements_by_impact_level': req_by_level,
            'max_distance': max(
                [tc.distance for tc in impacted_testcases] +
                [req.distance for req in impacted_requirements],
                default=0
            ),
            'total_impact_paths': sum(tc.path_count for tc in impacted_testcases)
        }
    
    def _assess_impact_risk(
        self,
        requirement_id: int,
        impacted_testcases: List[ImpactedNode],
        impacted_requirements: List[ImpactedNode]
    ) -> Dict[str, Any]:
        """
        Assess the risk associated with changes to this requirement.
        
        Args:
            requirement_id: The source requirement ID
            impacted_testcases: List of impacted test case nodes
            impacted_requirements: List of impacted requirement nodes
            
        Returns:
            Dictionary containing risk assessment information
        """
        # Count critical and high impact nodes
        critical_count = sum(
            1 for node in impacted_testcases + impacted_requirements
            if node.impact_level == ImpactLevel.CRITICAL
        )
        
        high_count = sum(
            1 for node in impacted_testcases + impacted_requirements
            if node.impact_level == ImpactLevel.HIGH
        )
        
        # Count test cases covering multiple requirements (critical test cases)
        critical_testcases = [
            tc for tc in impacted_testcases
            if tc.shared_dependencies >= 3
        ]
        
        # Calculate overall risk score (0-100)
        risk_score = 0
        risk_score += min(critical_count * 10, 40)  # Up to 40 for critical impacts
        risk_score += min(high_count * 5, 30)       # Up to 30 for high impacts
        risk_score += min(len(impacted_testcases) * 2, 20)  # Up to 20 for total TCs
        risk_score += min(len(critical_testcases) * 5, 10)  # Up to 10 for critical TCs
        
        # Determine risk category
        if risk_score >= 70:
            risk_category = "CRITICAL"
        elif risk_score >= 50:
            risk_category = "HIGH"
        elif risk_score >= 30:
            risk_category = "MEDIUM"
        else:
            risk_category = "LOW"
        
        return {
            'risk_score': min(risk_score, 100),
            'risk_category': risk_category,
            'critical_impact_count': critical_count,
            'high_impact_count': high_count,
            'critical_testcases_count': len(critical_testcases),
            'critical_testcases': [
                {'id': tc.node_id, 'name': tc.title, 'dependencies': tc.shared_dependencies}
                for tc in critical_testcases[:5]  # Top 5 only
            ],
            'recommended_actions': self._generate_recommendations(
                risk_category,
                critical_count,
                len(critical_testcases)
            )
        }
    
    def _generate_recommendations(
        self,
        risk_category: str,
        critical_count: int,
        critical_tc_count: int
    ) -> List[str]:
        """
        Generate recommended actions based on risk assessment.
        
        Args:
            risk_category: Risk category (CRITICAL, HIGH, MEDIUM, LOW)
            critical_count: Number of critical impact nodes
            critical_tc_count: Number of critical test cases
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        if risk_category == "CRITICAL":
            recommendations.append(
                "CRITICAL RISK: Extensive impact detected. Require approval from stakeholders."
            )
            recommendations.append(
                "Execute comprehensive regression testing on all impacted test cases."
            )
            recommendations.append(
                "Consider breaking changes into smaller, incremental updates."
            )
        elif risk_category == "HIGH":
            recommendations.append(
                "HIGH RISK: Significant impact detected. Review with team before proceeding."
            )
            recommendations.append(
                "Execute targeted regression testing on high and critical impact test cases."
            )
        elif risk_category == "MEDIUM":
            recommendations.append(
                "MEDIUM RISK: Moderate impact detected. Review impacted areas."
            )
            recommendations.append(
                "Execute smoke testing on directly impacted test cases."
            )
        else:
            recommendations.append(
                "LOW RISK: Limited impact detected. Standard review process applies."
            )
        
        if critical_count > 0:
            recommendations.append(
                f"Review {critical_count} critical impact nodes before implementation."
            )
        
        if critical_tc_count > 0:
            recommendations.append(
                f"Pay special attention to {critical_tc_count} test case(s) covering multiple requirements."
            )
        
        return recommendations


def get_impact_analysis(
    db: Session,
    requirement_id: int,
    max_depth: int = 3,
    include_risk: bool = True
) -> Dict[str, Any]:
    """
    Get comprehensive impact analysis for a requirement.
    
    Args:
        db: Database session
        requirement_id: The requirement ID to analyze
        max_depth: Maximum graph traversal depth
        include_risk: Whether to include risk assessment
        
    Returns:
        Dictionary containing complete impact analysis
    """
    service = ImpactAnalysisService(db)
    result = service.detect_impacted_nodes(
        requirement_id,
        max_depth=max_depth,
        include_risk_assessment=include_risk
    )
    
    # Convert to dictionary format
    return {
        'source_requirement': {
            'id': result.source_requirement_id,
            'title': result.source_requirement_title
        },
        'total_impacted_nodes': result.total_impacted_nodes,
        'impacted_testcases': [
            {
                'id': tc.node_id,
                'name': tc.title,
                'impact_type': tc.impact_type.value,
                'impact_level': tc.impact_level.value,
                'distance': tc.distance,
                'path_count': tc.path_count,
                'shared_dependencies': tc.shared_dependencies,
                'metadata': tc.metadata
            }
            for tc in result.impacted_testcases
        ],
        'impacted_requirements': [
            {
                'id': req.node_id,
                'title': req.title,
                'impact_type': req.impact_type.value,
                'impact_level': req.impact_level.value,
                'distance': req.distance,
                'shared_dependencies': req.shared_dependencies,
                'metadata': req.metadata
            }
            for req in result.impacted_requirements
        ],
        'impact_summary': result.impact_summary,
        'risk_assessment': result.risk_assessment
    }


def get_bulk_impact_analysis(
    db: Session,
    requirement_ids: List[int],
    max_depth: int = 2
) -> Dict[int, Dict[str, Any]]:
    """
    Get impact analysis for multiple requirements.
    
    Args:
        db: Database session
        requirement_ids: List of requirement IDs to analyze
        max_depth: Maximum graph traversal depth
        
    Returns:
        Dictionary mapping requirement ID to impact analysis
    """
    service = ImpactAnalysisService(db)
    results = {}
    
    for req_id in requirement_ids:
        try:
            result = service.detect_impacted_nodes(
                req_id,
                max_depth=max_depth,
                include_risk_assessment=False  # Skip risk for bulk to improve performance
            )
            results[req_id] = {
                'total_impacted': result.total_impacted_nodes,
                'testcases_count': len(result.impacted_testcases),
                'requirements_count': len(result.impacted_requirements),
                'summary': result.impact_summary
            }
        except Exception as e:
            logger.error(f"Error analyzing requirement {req_id}: {str(e)}")
            results[req_id] = {'error': str(e)}
    
    return results
