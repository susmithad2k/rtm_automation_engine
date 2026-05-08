"""
Trace routes for traceability matrix operations.

This module provides REST API endpoints for accessing and analyzing
requirement-to-test-case traceability mappings.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.db.crud import get_mappings
from app.models.response_models import TraceResponse, MappingItem
from app.services.trace_service import TraceabilityService
from app.graph.traversal import TraceabilityGraph

router = APIRouter(prefix="/trace", tags=["trace"])


@router.get("", response_model=TraceResponse)
def get_trace_mappings(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    requirement_id: Optional[int] = Query(None, description="Filter by requirement ID"),
    testcase_id: Optional[int] = Query(None, description="Filter by test case ID"),
    db: Session = Depends(get_db)
):
    """
    Get requirement-to-testcase mappings (traceability matrix) with optional filtering.
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        requirement_id: Optional filter by requirement ID
        testcase_id: Optional filter by test case ID
        db: Database session
        
    Returns:
        TraceResponse containing filtered mappings
    """
    try:
        mappings = get_mappings(
            db, 
            skip=skip, 
            limit=limit, 
            requirement_id=requirement_id, 
            testcase_id=testcase_id
        )
        
        mapping_items = [
            MappingItem(
                id=mapping.id,
                requirement_id=mapping.requirement_id,
                testcase_id=mapping.testcase_id
            )
            for mapping in mappings
        ]
        
        return TraceResponse(
            total=len(mapping_items),
            mappings=mapping_items
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/coverage/requirement/{requirement_id}")
def get_requirement_coverage(
    requirement_id: int,
    db: Session = Depends(get_db)
):
    """
    Get test case coverage for a specific requirement.
    
    Args:
        requirement_id: The requirement ID to check coverage for
        db: Database session
        
    Returns:
        Coverage information for the requirement
    """
    try:
        service = TraceabilityService()
        return service.get_requirement_coverage(db, requirement_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/coverage/testcase/{testcase_id}")
def get_testcase_coverage(
    testcase_id: int,
    db: Session = Depends(get_db)
):
    """
    Get requirement coverage for a specific test case.
    
    Args:
        testcase_id: The test case ID to check coverage for
        db: Database session
        
    Returns:
        Coverage information for the test case
    """
    try:
        service = TraceabilityService()
        return service.get_testcase_coverage(db, testcase_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
def get_coverage_statistics(db: Session = Depends(get_db)):
    """
    Get overall traceability coverage statistics.
    
    Args:
        db: Database session
        
    Returns:
        Dictionary with various coverage metrics
    """
    try:
        graph = TraceabilityGraph(db)
        return graph.get_coverage_statistics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orphaned")
def get_orphaned_items(db: Session = Depends(get_db)):
    """
    Find requirements without test cases and test cases without requirements.
    
    Args:
        db: Database session
        
    Returns:
        Dictionary with lists of orphaned requirements and test cases
    """
    try:
        graph = TraceabilityGraph(db)
        return graph.find_orphaned_items()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/impact/{requirement_id}")
def get_impact_analysis(
    requirement_id: int,
    db: Session = Depends(get_db)
):
    """
    Analyze the impact of changes to a requirement.
    
    Args:
        requirement_id: The requirement ID to analyze
        db: Database session
        
    Returns:
        Impact analysis showing affected test cases and related requirements
    """
    try:
        graph = TraceabilityGraph(db)
        return graph.get_impact_analysis(requirement_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph")
def get_graph_data(db: Session = Depends(get_db)):
    """
    Export traceability graph data for visualization.
    
    Args:
        db: Database session
        
    Returns:
        Graph data with nodes and edges suitable for visualization tools
    """
    try:
        graph = TraceabilityGraph(db)
        return graph.export_graph_data()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/related/requirement/{requirement_id}")
def get_related_testcases(
    requirement_id: int,
    depth: int = Query(2, ge=1, le=5, description="Traversal depth"),
    db: Session = Depends(get_db)
):
    """
    Find test cases related to a requirement through shared mappings.
    
    Args:
        requirement_id: Starting requirement ID
        depth: Maximum traversal depth (1-5)
        db: Database session
        
    Returns:
        Dictionary of related test case IDs with their distances
    """
    try:
        graph = TraceabilityGraph(db)
        related = graph.get_related_testcases(requirement_id, depth)
        return {
            "requirement_id": requirement_id,
            "depth": depth,
            "related_testcases": related,
            "count": len(related)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
