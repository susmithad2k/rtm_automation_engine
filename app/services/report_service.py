"""
Report Service.

This module provides report generation and export functionality,
including CSV export for coverage and risk analysis.
"""

# Standard library imports
import csv
import io
from datetime import datetime, timezone
from typing import Dict, List

# Third-party imports
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session, selectinload

# Local imports
from app.models.db_models import Mapping, Requirement, TestCaseModel
from app.services.coverage_service import calculate_coverage
from app.services.risk_service import detect_risk
from app.utils.logger import get_logger

logger = get_logger(__name__)


def generate_comprehensive_report(
    db: Session,
    days_threshold: int = 30,
    skip: int = 0,
    limit: int = 100
) -> Dict:
    """
    Generate a comprehensive report combining coverage metrics and risk analysis.
    
    Args:
        db: Database session
        days_threshold: Number of days to consider for recently changed items
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        
    Returns:
        Dictionary containing coverage, risk, and timestamp information
    """
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
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return report


def export_coverage_report_csv(db: Session) -> str:
    """
    Export coverage report data to CSV format.
    
    This generates a detailed CSV with one row per requirement,
    showing coverage status and mapped test cases.
    
    Args:
        db: Database session
        
    Returns:
        CSV string containing the coverage report
    """
    logger.info("Generating CSV coverage report")
    
    # Create in-memory CSV file
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Requirement ID",
        "Requirement Title",
        "Requirement Description",
        "Coverage Status",
        "Test Case Count",
        "Mapped Test Cases"
    ])
    
    # Get all requirements with mappings eagerly loaded (eliminates N+1 queries)
    requirements = (
        db.query(Requirement)
        .options(selectinload(Requirement.mappings).selectinload(Mapping.testcase))
        .all()
    )
    
    for req in requirements:
        # Access pre-loaded mappings (no additional query)
        test_case_count = len(req.mappings)
        coverage_status = "Covered" if test_case_count > 0 else "Uncovered"
        
        # Get test case names from pre-loaded relationships
        if req.mappings:
            test_case_names = "; ".join([m.testcase.name for m in req.mappings])
        else:
            test_case_names = "None"
        
        writer.writerow([
            req.id,
            req.title,
            req.description or "",
            coverage_status,
            test_case_count,
            test_case_names
        ])
    
    csv_content = output.getvalue()
    output.close()
    
    logger.info(f"CSV report generated with {len(requirements)} requirements")
    return csv_content


def export_risk_report_csv(db: Session, days_threshold: int = 30) -> str:
    """
    Export risk analysis report to CSV format.
    
    This generates a CSV focused on uncovered requirements and risk areas.
    
    Args:
        db: Database session
        days_threshold: Number of days to consider for recently changed items
        
    Returns:
        CSV string containing the risk report
    """
    logger.info("Generating CSV risk report")
    
    # Create in-memory CSV file
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Requirement ID",
        "Requirement Title",
        "Requirement Description",
        "Risk Level",
        "Test Case Count"
    ])
    
    # Get uncovered requirements (high risk)
    covered_ids = db.query(Mapping.requirement_id).distinct().subquery()
    uncovered_reqs = db.query(Requirement).filter(
        ~Requirement.id.in_(covered_ids)
    ).all()
    
    # Write uncovered requirements
    for req in uncovered_reqs:
        writer.writerow([
            req.id,
            req.title,
            req.description or "",
            "High",
            0
        ])
    
    # Get covered requirements with mappings eagerly loaded (low risk)
    covered_reqs = (
        db.query(Requirement)
        .filter(Requirement.id.in_(covered_ids))
        .options(selectinload(Requirement.mappings))
        .all()
    )
    
    for req in covered_reqs:
        # Use pre-loaded mappings instead of separate query
        test_count = len(req.mappings)
        
        writer.writerow([
            req.id,
            req.title,
            req.description or "",
            "Low",
            test_count
        ])
    
    csv_content = output.getvalue()
    output.close()
    
    logger.info(f"CSV risk report generated with {len(uncovered_reqs)} high-risk items")
    return csv_content


def export_traceability_matrix_csv(db: Session) -> str:
    """
    Export full traceability matrix to CSV format.
    
    This generates a CSV showing all requirement-to-testcase mappings.
    
    Args:
        db: Database session
        
    Returns:
        CSV string containing the full traceability matrix
    """
    logger.info("Generating CSV traceability matrix")
    
    # Create in-memory CSV file
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Mapping ID",
        "Requirement ID",
        "Requirement Title",
        "Test Case ID",
        "Test Case Name",
        "Test Case Steps"
    ])
    
    # Get all mappings with related data
    mappings = db.query(Mapping).all()
    
    for mapping in mappings:
        requirement = db.query(Requirement).filter(
            Requirement.id == mapping.requirement_id
        ).first()
        
        test_case = db.query(TestCaseModel).filter(
            TestCaseModel.id == mapping.testcase_id
        ).first()
        
        if requirement and test_case:
            writer.writerow([
                mapping.id,
                requirement.id,
                requirement.title,
                test_case.id,
                test_case.name,
                test_case.steps or ""
            ])
    
    csv_content = output.getvalue()
    output.close()
    
    logger.info(f"CSV traceability matrix generated with {len(mappings)} mappings")
    return csv_content


def export_summary_report_csv(db: Session, days_threshold: int = 30) -> str:
    """
    Export summary report with key metrics to CSV format.
    
    Args:
        db: Database session
        days_threshold: Number of days to consider for recently changed items
        
    Returns:
        CSV string containing the summary report
    """
    logger.info("Generating CSV summary report")
    
    # Get metrics
    coverage_data = calculate_coverage(db)
    risk_data = detect_risk(db, days_threshold=days_threshold)
    
    # Create in-memory CSV file
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write report metadata
    writer.writerow(["RTM Automation Engine - Summary Report"])
    writer.writerow(["Generated At", datetime.now(timezone.utc).isoformat()])
    writer.writerow([])
    
    # Write coverage metrics
    writer.writerow(["Coverage Metrics"])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Requirements", coverage_data["total_requirements"]])
    writer.writerow(["Covered Requirements", coverage_data["covered_requirements"]])
    writer.writerow(["Uncovered Requirements", coverage_data["uncovered_requirements"]])
    writer.writerow(["Coverage Percentage", f"{coverage_data['coverage_percentage']}%"])
    writer.writerow(["Total Test Cases", coverage_data["total_testcases"]])
    writer.writerow(["Total Mappings", coverage_data["total_mappings"]])
    writer.writerow([])
    
    # Write risk metrics
    writer.writerow(["Risk Analysis"])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Risk Score", f"{risk_data['risk_score']}%"])
    writer.writerow(["Uncovered Count", risk_data["uncovered_count"]])
    writer.writerow(["Risk Summary", risk_data["summary"]])
    writer.writerow([])
    
    # Write top uncovered requirements
    if risk_data["uncovered_requirements"]:
        writer.writerow(["Top Uncovered Requirements (High Risk)"])
        writer.writerow(["ID", "Title", "Description"])
        for req in risk_data["uncovered_requirements"][:10]:  # Top 10
            writer.writerow([
                req["id"],
                req["title"],
                req["description"]
            ])
    
    csv_content = output.getvalue()
    output.close()
    
    logger.info("CSV summary report generated")
    return csv_content
