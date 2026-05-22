"""
Report API routes.

This module provides REST API endpoints for generating comprehensive reports
combining coverage and risk analysis.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.coverage_service import calculate_coverage
from app.services.risk_service import detect_risk
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("/")
def get_report(
    days_threshold: int = Query(default=30, description="Days to consider for recently changed items"),
    skip: int = Query(default=0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db)
):
    """
    Generate a comprehensive report combining coverage metrics and risk analysis.
    
    This endpoint provides a unified view of:
    - Test coverage metrics for all requirements
    - Risk analysis including uncovered requirements
    - Overall health score of the traceability matrix
    
    Args:
        days_threshold: Number of days to consider for "recently changed" items (default: 30)
        skip: Number of records to skip for pagination (default: 0)
        limit: Maximum number of records to return (default: 100, max: 1000)
        db: Database session
        
    Returns:
        Dictionary containing:
            - coverage: Coverage metrics (total, covered, uncovered, percentage)
            - risk: Risk analysis (uncovered requirements, risk score, summary)
            - timestamp: Report generation timestamp
    """
    from datetime import datetime
    
    logger.info("Generating comprehensive coverage and risk report")
    
    # Get coverage metrics
    coverage_data = calculate_coverage(db)
    logger.info(f"Coverage calculated: {coverage_data['coverage_percentage']}%")
    
    # Get risk analysis
    risk_data = detect_risk(db, days_threshold=days_threshold, skip=skip, limit=limit)
    logger.info(f"Risk score calculated: {risk_data['risk_score']}")
    
    # Combine into comprehensive report
    report = {
        "coverage": coverage_data,
        "risk": risk_data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return report
