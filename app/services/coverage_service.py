from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from app.models.db_models import Requirement, TestCaseModel, Mapping


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


def get_requirement_coverage_details(db: Session, requirement_id: int) -> dict:
    """
    Get detailed coverage information for a specific requirement.
    
    Args:
        db: Database session
        requirement_id: ID of the requirement
        
    Returns:
        dict: Detailed coverage information including:
            - requirement: The requirement object
            - test_count: Number of test cases mapped to this requirement
            - test_cases: List of test cases mapped to this requirement
            - is_covered: Boolean indicating if requirement has any test coverage
    """
    requirement = db.query(Requirement).filter(Requirement.id == requirement_id).first()
    
    if not requirement:
        return None
    
    # Get all mappings for this requirement
    mappings = db.query(Mapping).filter(Mapping.requirement_id == requirement_id).all()
    
    # Get the actual test cases
    test_cases = []
    for mapping in mappings:
        test_case = db.query(TestCaseModel).filter(TestCaseModel.id == mapping.testcase_id).first()
        if test_case:
            test_cases.append({
                "id": test_case.id,
                "name": test_case.name,
                "steps": test_case.steps
            })
    
    return {
        "requirement": {
            "id": requirement.id,
            "title": requirement.title,
            "description": requirement.description
        },
        "test_count": len(test_cases),
        "test_cases": test_cases,
        "is_covered": len(test_cases) > 0
    }
