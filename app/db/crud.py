from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from typing import List, Tuple, Optional
from app.models.db_models import Requirement, TestCaseModel, Mapping


def create_requirement(db: Session, title: str, description: str = None):
    """
    Create a new requirement in the database
    Uses upsert logic - if a requirement with the same title exists, update it
    """
    # Check if requirement with this title already exists
    existing = db.query(Requirement).filter(Requirement.title == title).first()
    
    if existing:
        # Update existing requirement
        if description:
            existing.description = description
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Create new requirement
        try:
            requirement = Requirement(title=title, description=description)
            db.add(requirement)
            db.commit()
            db.refresh(requirement)
            return requirement
        except IntegrityError:
            # Handle race condition where another transaction created the same record
            db.rollback()
            existing = db.query(Requirement).filter(Requirement.title == title).first()
            if existing and description:
                existing.description = description
                db.commit()
                db.refresh(existing)
            return existing


def get_requirements(db: Session, skip: int = 0, limit: int = 100, with_mappings: bool = False):
    """Retrieve all requirements from the database with optional eager loading"""
    query = db.query(Requirement)
    if with_mappings:
        query = query.options(selectinload(Requirement.mappings))
    return query.offset(skip).limit(limit).all()


def get_requirement_by_id(db: Session, requirement_id: int):
    """Retrieve a specific requirement by ID"""
    return db.query(Requirement).filter(Requirement.id == requirement_id).first()


def create_testcase(db: Session, name: str, steps: str = None):
    """
    Create a new test case in the database
    Uses upsert logic - if a test case with the same name exists, update it
    """
    # Check if test case with this name already exists
    existing = db.query(TestCaseModel).filter(TestCaseModel.name == name).first()
    
    if existing:
        # Update existing test case
        if steps:
            existing.steps = steps
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Create new test case
        try:
            testcase = TestCaseModel(name=name, steps=steps)
            db.add(testcase)
            db.commit()
            db.refresh(testcase)
            return testcase
        except IntegrityError:
            # Handle race condition where another transaction created the same record
            db.rollback()
            existing = db.query(TestCaseModel).filter(TestCaseModel.name == name).first()
            if existing and steps:
                existing.steps = steps
                db.commit()
                db.refresh(existing)
            return existing


def get_testcases(db: Session, skip: int = 0, limit: int = 100, with_mappings: bool = False):
    """Retrieve all test cases from the database with optional eager loading"""
    query = db.query(TestCaseModel)
    if with_mappings:
        query = query.options(selectinload(TestCaseModel.mappings))
    return query.offset(skip).limit(limit).all()


def get_testcase_by_id(db: Session, testcase_id: int):
    """Retrieve a specific test case by ID"""
    return db.query(TestCaseModel).filter(TestCaseModel.id == testcase_id).first()


def create_mapping(db: Session, requirement_id: int, testcase_id: int):
    """
    Create a mapping between a requirement and test case
    Uses upsert logic - if mapping exists, return it
    """
    # Check if mapping already exists
    existing = db.query(Mapping).filter(
        Mapping.requirement_id == requirement_id,
        Mapping.testcase_id == testcase_id
    ).first()
    
    if existing:
        return existing
    
    # Create new mapping
    try:
        mapping = Mapping(requirement_id=requirement_id, testcase_id=testcase_id)
        db.add(mapping)
        db.commit()
        db.refresh(mapping)
        return mapping
    except IntegrityError:
        # Handle race condition
        db.rollback()
        existing = db.query(Mapping).filter(
            Mapping.requirement_id == requirement_id,
            Mapping.testcase_id == testcase_id
        ).first()
        return existing


def get_mappings(db: Session, skip: int = 0, limit: int = 100, requirement_id: int = None, testcase_id: int = None):
    """
    Retrieve mappings from the database with optional filtering
    
    Args:
        db: Database session
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        requirement_id: Optional filter by requirement ID
        testcase_id: Optional filter by test case ID
        
    Returns:
        List of mappings matching the filters
    """
    query = db.query(Mapping)
    
    # Apply filters if provided
    if requirement_id is not None:
        query = query.filter(Mapping.requirement_id == requirement_id)
    
    if testcase_id is not None:
        query = query.filter(Mapping.testcase_id == testcase_id)
    
    return query.offset(skip).limit(limit).all()


def get_mappings_by_requirement(db: Session, requirement_id: int):
    """Get all mappings for a specific requirement"""
    return db.query(Mapping).filter(Mapping.requirement_id == requirement_id).all()


def get_mappings_by_testcase(db: Session, testcase_id: int):
    """Get all mappings for a specific test case"""
    return db.query(Mapping).filter(Mapping.testcase_id == testcase_id).all()


def bulk_create_requirements(db: Session, requirements: List[Tuple[str, Optional[str]]]) -> List[Requirement]:
    """
    Bulk create requirements for better performance.
    
    Args:
        db: Database session
        requirements: List of tuples (title, description)
        
    Returns:
        List of created Requirement objects
    """
    created = []
    for title, description in requirements:
        existing = db.query(Requirement).filter(Requirement.title == title).first()
        if not existing:
            req = Requirement(title=title, description=description)
            created.append(req)
    
    if created:
        db.bulk_save_objects(created, return_defaults=True)
        db.commit()
    
    return created


def bulk_create_testcases(db: Session, testcases: List[Tuple[str, Optional[str]]]) -> List[TestCaseModel]:
    """
    Bulk create test cases for better performance.
    
    Args:
        db: Database session
        testcases: List of tuples (name, steps)
        
    Returns:
        List of created TestCaseModel objects
    """
    created = []
    for name, steps in testcases:
        existing = db.query(TestCaseModel).filter(TestCaseModel.name == name).first()
        if not existing:
            tc = TestCaseModel(name=name, steps=steps)
            created.append(tc)
    
    if created:
        db.bulk_save_objects(created, return_defaults=True)
        db.commit()
    
    return created


def bulk_create_mappings(db: Session, mappings: List[Tuple[int, int]]) -> int:
    """
    Bulk create mappings for better performance.
    
    Args:
        db: Database session
        mappings: List of tuples (requirement_id, testcase_id)
        
    Returns:
        Number of mappings created
    """
    # Get existing mappings to avoid duplicates
    existing_mappings = db.query(
        Mapping.requirement_id,
        Mapping.testcase_id
    ).all()
    existing_set = set(existing_mappings)
    
    # Filter out duplicates
    new_mappings = [
        Mapping(requirement_id=req_id, testcase_id=tc_id)
        for req_id, tc_id in mappings
        if (req_id, tc_id) not in existing_set
    ]
    
    if new_mappings:
        db.bulk_save_objects(new_mappings)
        db.commit()
    
    return len(new_mappings)


def get_requirements_with_coverage(db: Session, skip: int = 0, limit: int = 100):
    """
    Get requirements with their mappings eagerly loaded in a single query.
    Optimized for coverage reporting.
    """
    return (
        db.query(Requirement)
        .options(selectinload(Requirement.mappings).selectinload(Mapping.testcase))
        .offset(skip)
        .limit(limit)
        .all()
    )
