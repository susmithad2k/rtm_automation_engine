"""
Report API routes.

This module provides REST API endpoints for generating comprehensive reports
combining coverage and risk analysis.
"""

# Standard library imports
import io

# Third-party imports
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

# Local imports
from app.db.database import get_db
from app.services.coverage_service import calculate_coverage
from app.services.report_service import (
    export_coverage_report_csv,
    export_risk_report_csv,
    export_summary_report_csv,
    export_traceability_matrix_csv,
    generate_comprehensive_report,
)
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
    logger.info("Generating comprehensive coverage and risk report")
    return generate_comprehensive_report(db, days_threshold, skip, limit)


@router.get("/export/coverage")
def export_coverage_csv(db: Session = Depends(get_db)):
    """
    Export coverage report to CSV format.
    
    This endpoint generates a downloadable CSV file containing detailed coverage
    information for all requirements, including:
    - Requirement details (ID, title, description)
    - Coverage status (covered/uncovered)
    - Number of mapped test cases
    - Names of mapped test cases
    
    Returns:
        StreamingResponse with CSV file attachment
    """
    logger.info("Exporting coverage report to CSV")
    
    csv_content = export_coverage_report_csv(db)
    
    # Create streaming response
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=coverage_report.csv"}
    )


@router.get("/export/risk")
def export_risk_csv(
    days_threshold: int = Query(default=30, description="Days to consider for recently changed items"),
    db: Session = Depends(get_db)
):
    """
    Export risk analysis report to CSV format.
    
    This endpoint generates a downloadable CSV file focused on risk areas:
    - Uncovered requirements (high risk)
    - Covered requirements (low risk)
    - Risk level classification
    - Test case counts
    
    Args:
        days_threshold: Number of days to consider for recently changed items (default: 30)
        db: Database session
    
    Returns:
        StreamingResponse with CSV file attachment
    """
    logger.info("Exporting risk report to CSV")
    
    csv_content = export_risk_report_csv(db, days_threshold)
    
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=risk_report.csv"}
    )


@router.get("/export/traceability")
def export_traceability_matrix_csv(db: Session = Depends(get_db)):
    """
    Export full traceability matrix to CSV format.
    
    This endpoint generates a downloadable CSV file containing all
    requirement-to-testcase mappings with complete details:
    - Mapping ID
    - Requirement details (ID, title)
    - Test case details (ID, name, steps)
    
    Returns:
        StreamingResponse with CSV file attachment
    """
    logger.info("Exporting traceability matrix to CSV")
    
    csv_content = export_traceability_matrix_csv(db)
    
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=traceability_matrix.csv"}
    )


@router.get("/export/summary")
def export_summary_csv(
    days_threshold: int = Query(default=30, description="Days to consider for recently changed items"),
    db: Session = Depends(get_db)
):
    """
    Export summary report with key metrics to CSV format.
    
    This endpoint generates a downloadable CSV file containing:
    - Coverage metrics summary
    - Risk analysis summary
    - Top uncovered requirements
    - Overall health indicators
    
    Args:
        days_threshold: Number of days to consider for recently changed items (default: 30)
        db: Database session
    
    Returns:
        StreamingResponse with CSV file attachment
    """
    logger.info("Exporting summary report to CSV")
    
    csv_content = export_summary_report_csv(db, days_threshold)
    
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=summary_report.csv"}
    )
