from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from app.models.db_models import Requirement, TestCaseModel, Mapping
from datetime import datetime
from typing import Dict


def calculate_coverage(db: Session) -> dict:
    """
    Calculate test coverage metrics for requirements.
    
    Coverage is defined as the percentage of requirements that have at least
    one test case mapped to them.
    
    Args:
        db: Database session
        
    Returns:
        dict: Coverage metrics containing:
            - total_requirements: Total number of requirements
            - covered_requirements: Number of requirements with at least one test case
            - uncovered_requirements: Number of requirements without any test cases
            - coverage_percentage: Percentage of requirements covered by tests
            - total_testcases: Total number of test cases
            - total_mappings: Total number of requirement-testcase mappings
    """
    # Count total requirements
    total_requirements = db.query(func.count(Requirement.id)).scalar()
    
    # Count requirements that have at least one mapping
    covered_requirements = db.query(func.count(distinct(Mapping.requirement_id))).scalar()
    
    # Calculate uncovered requirements
    uncovered_requirements = total_requirements - covered_requirements
    
    # Calculate coverage percentage
    if total_requirements > 0:
        coverage_percentage = (covered_requirements / total_requirements) * 100
    else:
        coverage_percentage = 0.0
    
    # Additional metrics
    total_testcases = db.query(func.count(TestCaseModel.id)).scalar()
    total_mappings = db.query(func.count(Mapping.id)).scalar()
    
    return {
        "total_requirements": total_requirements,
        "covered_requirements": covered_requirements,
        "uncovered_requirements": uncovered_requirements,
        "coverage_percentage": round(coverage_percentage, 2),
        "total_testcases": total_testcases,
        "total_mappings": total_mappings
    }


def get_uncovered_requirements(db: Session, skip: int = 0, limit: int = 100):
    """
    Get all requirements that don't have any test case mappings.
    
    Args:
        db: Database session
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        
    Returns:
        List of requirements without test case coverage
    """
    # Subquery to get all requirement IDs that have mappings
    covered_ids = db.query(Mapping.requirement_id).distinct().subquery()
    
    # Query requirements that are NOT in the covered IDs
    uncovered = db.query(Requirement).filter(
        ~Requirement.id.in_(covered_ids)
    ).offset(skip).limit(limit).all()
    
    return uncovered


def get_combined_coverage_and_risk(
    db: Session,
    days_threshold: int = 30,
    skip: int = 0,
    limit: int = 100
) -> Dict:
    """
    Get combined coverage metrics and risk analysis in a single unified response.
    
    This function merges coverage statistics with risk assessment, providing
    a comprehensive view of the requirements traceability health.
    
    Args:
        db: Database session
        days_threshold: Number of days to consider for "recently changed" items
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        
    Returns:
        dict: Combined metrics containing:
            - total_requirements: Total number of requirements
            - covered_requirements: Number of requirements with test coverage
            - uncovered_requirements: Count of requirements without tests
            - coverage_percentage: Percentage of requirements covered
            - total_testcases: Total number of test cases
            - total_mappings: Total number of requirement-testcase mappings
            - risk_score: Overall risk score (0-100)
            - risk_level: Risk severity level (LOW, MEDIUM, HIGH, CRITICAL)
            - risk_summary: Human-readable risk assessment
            - uncovered_requirement_list: List of uncovered requirements
            - recently_changed_count: Count of recently changed items
            - timestamp: Report generation timestamp
    """
    # Calculate coverage metrics
    total_requirements = db.query(func.count(Requirement.id)).scalar()
    covered_requirements = db.query(func.count(distinct(Mapping.requirement_id))).scalar()
    uncovered_requirements = total_requirements - covered_requirements
    
    if total_requirements > 0:
        coverage_percentage = (covered_requirements / total_requirements) * 100
    else:
        coverage_percentage = 0.0
    
    total_testcases = db.query(func.count(TestCaseModel.id)).scalar()
    total_mappings = db.query(func.count(Mapping.id)).scalar()
    
    # Calculate risk metrics
    if total_requirements > 0:
        risk_score = round((uncovered_requirements / total_requirements) * 100, 2)
    else:
        risk_score = 0.0
    
    # Determine risk level
    if risk_score >= 75:
        risk_level = "CRITICAL"
        recommendation = "Immediate action required to add test coverage."
    elif risk_score >= 50:
        risk_level = "HIGH"
        recommendation = "Prioritize adding test coverage for uncovered requirements."
    elif risk_score >= 25:
        risk_level = "MEDIUM"
        recommendation = "Consider adding test coverage to improve quality assurance."
    else:
        risk_level = "LOW"
        recommendation = "Maintain current test coverage levels."
    
    # Get uncovered requirements list
    covered_ids = db.query(Mapping.requirement_id).distinct().subquery()
    uncovered_reqs = db.query(Requirement).filter(
        ~Requirement.id.in_(covered_ids)
    ).offset(skip).limit(limit).all()
    
    uncovered_requirement_list = [
        {
            "id": req.id,
            "title": req.title,
            "description": req.description
        }
        for req in uncovered_reqs
    ]
    
    # Generate risk summary
    risk_summary = (
        f"Risk Level: {risk_level}\\n"
        f"Risk Score: {risk_score}%\\n"
        f"Uncovered Requirements: {uncovered_requirements} out of {total_requirements}\\n"
        f"Recommendation: {recommendation}"
    )
    
    # Placeholder for recently changed count (requires timestamp fields in models)
    recently_changed_count = 0
    
    return {
        "total_requirements": total_requirements,
        "covered_requirements": covered_requirements,
        "uncovered_requirements": uncovered_requirements,
        "coverage_percentage": round(coverage_percentage, 2),
        "total_testcases": total_testcases,
        "total_mappings": total_mappings,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_summary": risk_summary,
        "uncovered_requirement_list": uncovered_requirement_list,
        "recently_changed_count": recently_changed_count,
        "timestamp": datetime.utcnow().isoformat()
    }
