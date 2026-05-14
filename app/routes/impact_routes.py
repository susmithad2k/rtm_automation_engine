"""
Impact analysis API routes.

This module provides REST API endpoints for analyzing the impact of requirement changes.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.services import impact_service
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/impact", tags=["impact"])


@router.get("/{requirement_id}")
def analyze_requirement_impact(
    requirement_id: int,
    max_depth: int = Query(
        default=3,
        ge=1,
        le=5,
        description="Maximum graph traversal depth (1-5)"
    ),
    include_risk: bool = Query(
        default=True,
        description="Include risk assessment in the response"
    ),
    db: Session = Depends(get_db)
):
    """
    Analyze the impact of changes to a specific requirement.
    
    This endpoint identifies all test cases and requirements that would be affected
    by changes to the specified requirement, categorizes the impact severity,
    and provides risk assessment.
    
    **Impact Types:**
    - **direct**: Test cases directly mapped to the requirement
    - **indirect**: Test cases affected through related requirements
    - **cascading**: Test cases multiple hops away in the graph
    - **bidirectional**: Requirements sharing test cases
    
    **Impact Levels:**
    - **critical**: Direct dependencies requiring immediate attention
    - **high**: Immediate related items with significant impact
    - **medium**: Secondary dependencies with moderate impact
    - **low**: Distant relationships with minimal impact
    
    Args:
        requirement_id: The requirement ID to analyze
        max_depth: Maximum graph traversal depth for cascade detection (1-5)
        include_risk: Whether to include risk assessment
        db: Database session
        
    Returns:
        Comprehensive impact analysis including:
        - Source requirement information
        - Lists of impacted test cases and requirements
        - Impact summary statistics
        - Risk assessment and recommendations
        
    Raises:
        HTTPException: If requirement not found or analysis fails
    """
    try:
        logger.info(
            f"Impact analysis requested for requirement {requirement_id} "
            f"(depth={max_depth}, include_risk={include_risk})"
        )
        
        result = impact_service.get_impact_analysis(
            db=db,
            requirement_id=requirement_id,
            max_depth=max_depth,
            include_risk=include_risk
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Requirement not found: {requirement_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error analyzing impact for requirement {requirement_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Impact analysis failed: {str(e)}")


@router.post("/bulk")
def analyze_bulk_impact(
    requirement_ids: List[int],
    max_depth: int = Query(
        default=2,
        ge=1,
        le=4,
        description="Maximum graph traversal depth (1-4)"
    ),
    db: Session = Depends(get_db)
):
    """
    Analyze the impact of changes to multiple requirements.
    
    This endpoint performs impact analysis for multiple requirements in a single request.
    Risk assessment is excluded for performance reasons in bulk operations.
    
    Args:
        requirement_ids: List of requirement IDs to analyze
        max_depth: Maximum graph traversal depth (1-4, lower for bulk operations)
        db: Database session
        
    Returns:
        Dictionary mapping requirement IDs to their impact analysis summaries
        
    Raises:
        HTTPException: If bulk analysis fails
    """
    try:
        if not requirement_ids:
            raise HTTPException(
                status_code=400,
                detail="requirement_ids list cannot be empty"
            )
        
        if len(requirement_ids) > 50:
            raise HTTPException(
                status_code=400,
                detail="Maximum 50 requirements allowed per bulk request"
            )
        
        logger.info(
            f"Bulk impact analysis requested for {len(requirement_ids)} requirements"
        )
        
        results = impact_service.get_bulk_impact_analysis(
            db=db,
            requirement_ids=requirement_ids,
            max_depth=max_depth
        )
        
        return {
            'total_analyzed': len(requirement_ids),
            'results': results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk impact analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bulk analysis failed: {str(e)}")


@router.get("/summary/statistics")
def get_impact_statistics(db: Session = Depends(get_db)):
    """
    Get overall impact statistics across the traceability matrix.
    
    This endpoint provides high-level statistics about the complexity and
    interconnectedness of the requirements traceability matrix, which can
    help assess overall change impact risk.
    
    Args:
        db: Database session
        
    Returns:
        Dictionary containing impact-related statistics:
        - Total requirements and test cases
        - Average connections per node
        - Highly connected nodes
        - Potential high-impact requirements
        
    Raises:
        HTTPException: If statistics calculation fails
    """
    try:
        from app.graph.traversal import TraceabilityGraph
        from app.db.crud import get_requirements, get_testcases
        
        graph = TraceabilityGraph(db)
        coverage_stats = graph.get_coverage_statistics()
        
        # Find requirements with many direct test cases (high impact potential)
        all_requirements = get_requirements(db, skip=0, limit=10000)
        high_impact_reqs = []
        
        for req in all_requirements:
            tc_count = len(graph.get_testcases_for_requirement(req.id))
            if tc_count >= 5:  # Threshold for high impact
                high_impact_reqs.append({
                    'id': req.id,
                    'title': req.title,
                    'direct_testcase_count': tc_count
                })
        
        # Sort by testcase count
        high_impact_reqs.sort(key=lambda x: x['direct_testcase_count'], reverse=True)
        
        # Find critical test cases (covering many requirements)
        all_testcases = get_testcases(db, skip=0, limit=10000)
        critical_testcases = []
        
        for tc in all_testcases:
            req_count = len(graph.get_requirements_for_testcase(tc.id))
            if req_count >= 3:  # Threshold for critical
                critical_testcases.append({
                    'id': tc.id,
                    'name': tc.name,
                    'requirement_coverage': req_count
                })
        
        # Sort by requirement coverage
        critical_testcases.sort(key=lambda x: x['requirement_coverage'], reverse=True)
        
        return {
            'coverage_statistics': coverage_stats,
            'high_impact_requirements': {
                'count': len(high_impact_reqs),
                'top_10': high_impact_reqs[:10]
            },
            'critical_testcases': {
                'count': len(critical_testcases),
                'top_10': critical_testcases[:10]
            },
            'network_complexity': {
                'avg_testcases_per_requirement': coverage_stats['avg_testcases_per_requirement'],
                'avg_requirements_per_testcase': coverage_stats['avg_requirements_per_testcase'],
                'total_connections': coverage_stats['total_mappings']
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating impact statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Statistics calculation failed: {str(e)}"
        )


@router.get("/critical/testcases")
def get_critical_testcases(
    min_coverage: int = Query(
        default=3,
        ge=2,
        description="Minimum number of requirements to be considered critical"
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return"
    ),
    db: Session = Depends(get_db)
):
    """
    Get list of critical test cases that cover multiple requirements.
    
    Critical test cases are those that cover many requirements, making them
    high-risk from an impact perspective. Changes to these test cases or their
    covered requirements require careful consideration.
    
    Args:
        min_coverage: Minimum number of requirements to be considered critical
        limit: Maximum number of results to return
        db: Database session
        
    Returns:
        List of critical test cases with coverage information
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        from app.graph.traversal import TraceabilityGraph
        from app.db.crud import get_testcases
        
        graph = TraceabilityGraph(db)
        all_testcases = get_testcases(db, skip=0, limit=10000)
        
        critical_testcases = []
        for tc in all_testcases:
            req_ids = graph.get_requirements_for_testcase(tc.id)
            req_count = len(req_ids)
            
            if req_count >= min_coverage:
                critical_testcases.append({
                    'id': tc.id,
                    'name': tc.name,
                    'steps': tc.steps,
                    'requirement_coverage': req_count,
                    'covered_requirement_ids': list(req_ids),
                    'criticality_score': req_count  # Simple score for now
                })
        
        # Sort by criticality score descending
        critical_testcases.sort(key=lambda x: x['criticality_score'], reverse=True)
        
        return {
            'total_critical_testcases': len(critical_testcases),
            'criteria': {
                'min_coverage': min_coverage
            },
            'critical_testcases': critical_testcases[:limit]
        }
        
    except Exception as e:
        logger.error(f"Error retrieving critical test cases: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Retrieval failed: {str(e)}"
        )


@router.get("/high-risk/requirements")
def get_high_risk_requirements(
    min_testcases: int = Query(
        default=5,
        ge=3,
        description="Minimum number of test cases to be considered high-risk"
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return"
    ),
    db: Session = Depends(get_db)
):
    """
    Get list of high-risk requirements that impact many test cases.
    
    High-risk requirements are those with many direct test case mappings,
    meaning changes to these requirements will impact a large test suite.
    
    Args:
        min_testcases: Minimum number of test cases to be considered high-risk
        limit: Maximum number of results to return
        db: Database session
        
    Returns:
        List of high-risk requirements with impact information
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        from app.graph.traversal import TraceabilityGraph
        from app.db.crud import get_requirements
        
        graph = TraceabilityGraph(db)
        all_requirements = get_requirements(db, skip=0, limit=10000)
        
        high_risk_reqs = []
        for req in all_requirements:
            tc_ids = graph.get_testcases_for_requirement(req.id)
            tc_count = len(tc_ids)
            
            if tc_count >= min_testcases:
                # Quick impact analysis for connected requirements
                related_reqs = set()
                for tc_id in tc_ids:
                    related_reqs.update(graph.get_requirements_for_testcase(tc_id))
                related_reqs.discard(req.id)
                
                high_risk_reqs.append({
                    'id': req.id,
                    'title': req.title,
                    'description': req.description,
                    'direct_testcase_count': tc_count,
                    'related_requirements_count': len(related_reqs),
                    'risk_score': tc_count + (len(related_reqs) * 0.5)  # Weighted score
                })
        
        # Sort by risk score descending
        high_risk_reqs.sort(key=lambda x: x['risk_score'], reverse=True)
        
        return {
            'total_high_risk_requirements': len(high_risk_reqs),
            'criteria': {
                'min_testcases': min_testcases
            },
            'high_risk_requirements': high_risk_reqs[:limit]
        }
        
    except Exception as e:
        logger.error(f"Error retrieving high-risk requirements: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Retrieval failed: {str(e)}"
        )
