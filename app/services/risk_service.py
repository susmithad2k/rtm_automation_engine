from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from app.models.db_models import Requirement, TestCaseModel, Mapping
from typing import Dict, List, Optional
from datetime import datetime, timedelta


def detect_risk(
    db: Session,
    days_threshold: int = 30,
    skip: int = 0,
    limit: int = 100
) -> Dict:
    """
    Detect risk areas in the requirements and test coverage.
    
    This function identifies:
    1. Requirements without test cases (uncovered requirements)
    2. Recently changed items (requires updated_at field in models)
    
    Args:
        db: Database session
        days_threshold: Number of days to consider for "recently changed" items
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        
    Returns:
        dict: Risk analysis containing:
            - uncovered_requirements: List of requirements without test cases
            - uncovered_count: Total count of uncovered requirements
            - recently_changed: List of recently changed items (placeholder)
            - risk_score: Overall risk score (0-100)
            - summary: Human-readable risk summary
    """
    # Identify requirements without test cases
    uncovered_reqs = get_uncovered_requirements(db, skip, limit)
    
    # Get total count of uncovered requirements
    covered_ids = db.query(Mapping.requirement_id).distinct().subquery()
    uncovered_count = db.query(func.count(Requirement.id)).filter(
        ~Requirement.id.in_(covered_ids)
    ).scalar()
    
    # Get total requirements count
    total_requirements = db.query(func.count(Requirement.id)).scalar()
    
    # Calculate risk score (0-100)
    # Higher percentage of uncovered requirements = higher risk
    if total_requirements > 0:
        risk_score = round((uncovered_count / total_requirements) * 100, 2)
    else:
        risk_score = 0.0
    
    # Identify recently changed items (placeholder - requires timestamp fields)
    recently_changed = get_recently_changed_items(db, days_threshold)
    
    # Generate risk summary
    summary = generate_risk_summary(
        uncovered_count=uncovered_count,
        total_requirements=total_requirements,
        recently_changed_count=len(recently_changed),
        risk_score=risk_score
    )
    
    return {
        "uncovered_requirements": [
            {
                "id": req.id,
                "title": req.title,
                "description": req.description
            }
            for req in uncovered_reqs
        ],
        "uncovered_count": uncovered_count,
        "recently_changed": recently_changed,
        "risk_score": risk_score,
        "summary": summary,
        "total_requirements": total_requirements
    }


def get_uncovered_requirements(db: Session, skip: int = 0, limit: int = 100) -> List[Requirement]:
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


def get_recently_changed_items(
    db: Session,
    days_threshold: int = 30
) -> List[Dict]:
    """
    Get items that have been recently changed.
    
    Note: This is a placeholder function. To fully implement this feature,
    the database models (Requirement, TestCaseModel, Mapping) need to be
    updated to include timestamp fields (created_at, updated_at).
    
    Args:
        db: Database session
        days_threshold: Number of days to consider for "recently changed"
        
    Returns:
        List of recently changed items with their details
    """
    # TODO: Implement once timestamp fields are added to models
    # Example implementation (requires model updates):
    # 
    # cutoff_date = datetime.utcnow() - timedelta(days=days_threshold)
    # 
    # recent_reqs = db.query(Requirement).filter(
    #     Requirement.updated_at >= cutoff_date
    # ).all()
    # 
    # recent_testcases = db.query(TestCaseModel).filter(
    #     TestCaseModel.updated_at >= cutoff_date
    # ).all()
    # 
    # return [
    #     {
    #         "type": "requirement",
    #         "id": req.id,
    #         "title": req.title,
    #         "updated_at": req.updated_at.isoformat()
    #     }
    #     for req in recent_reqs
    # ] + [
    #     {
    #         "type": "testcase",
    #         "id": tc.id,
    #         "name": tc.name,
    #         "updated_at": tc.updated_at.isoformat()
    #     }
    #     for tc in recent_testcases
    # ]
    
    # Placeholder return
    return []


def get_high_risk_requirements(db: Session, limit: int = 10) -> List[Dict]:
    """
    Identify high-risk requirements based on multiple criteria.
    
    High-risk requirements are those that:
    1. Have no test case coverage
    2. Have been recently changed (when timestamp support is added)
    
    Args:
        db: Database session
        limit: Maximum number of high-risk requirements to return
        
    Returns:
        List of high-risk requirements with risk factors
    """
    uncovered = get_uncovered_requirements(db, skip=0, limit=limit)
    
    high_risk = []
    for req in uncovered:
        risk_factors = ["No test coverage"]
        
        # Additional risk factors can be added here
        # Example: if recently changed, add that factor
        
        high_risk.append({
            "id": req.id,
            "title": req.title,
            "description": req.description,
            "risk_factors": risk_factors,
            "risk_level": "HIGH" if len(risk_factors) >= 1 else "MEDIUM"
        })
    
    return high_risk


def generate_risk_summary(
    uncovered_count: int,
    total_requirements: int,
    recently_changed_count: int,
    risk_score: float
) -> str:
    """
    Generate a human-readable risk summary.
    
    Args:
        uncovered_count: Number of uncovered requirements
        total_requirements: Total number of requirements
        recently_changed_count: Number of recently changed items
        risk_score: Calculated risk score (0-100)
        
    Returns:
        Human-readable risk summary string
    """
    if total_requirements == 0:
        return "No requirements found in the system."
    
    if risk_score >= 75:
        severity = "CRITICAL"
        recommendation = "Immediate action required to add test coverage."
    elif risk_score >= 50:
        severity = "HIGH"
        recommendation = "Prioritize adding test coverage for uncovered requirements."
    elif risk_score >= 25:
        severity = "MEDIUM"
        recommendation = "Consider adding test coverage to improve quality assurance."
    else:
        severity = "LOW"
        recommendation = "Maintain current test coverage levels."
    
    summary = (
        f"Risk Level: {severity}\n"
        f"Risk Score: {risk_score}%\n"
        f"Uncovered Requirements: {uncovered_count} out of {total_requirements}\n"
        f"Recommendation: {recommendation}"
    )
    
    if recently_changed_count > 0:
        summary += f"\nRecently Changed Items: {recently_changed_count}"
    
    return summary


def calculate_requirement_risk_score(
    db: Session,
    requirement_id: int
) -> Dict:
    """
    Calculate risk score for a specific requirement.
    
    Args:
        db: Database session
        requirement_id: ID of the requirement
        
    Returns:
        dict: Risk assessment for the specific requirement
    """
    requirement = db.query(Requirement).filter(Requirement.id == requirement_id).first()
    
    if not requirement:
        return {"error": "Requirement not found"}
    
    # Check if requirement has any test coverage
    mapping_count = db.query(func.count(Mapping.id)).filter(
        Mapping.requirement_id == requirement_id
    ).scalar()
    
    has_coverage = mapping_count > 0
    
    # Calculate risk factors
    risk_factors = []
    if not has_coverage:
        risk_factors.append("No test coverage")
    
    # Determine risk level
    if not has_coverage:
        risk_level = "HIGH"
        risk_score = 100
    else:
        risk_level = "LOW"
        risk_score = 0
    
    return {
        "requirement_id": requirement_id,
        "title": requirement.title,
        "description": requirement.description,
        "has_coverage": has_coverage,
        "test_count": mapping_count,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_factors": risk_factors
    }
