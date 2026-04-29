from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
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


def get_requirements(db: Session, skip: int = 0, limit: int = 100):
    """Retrieve all requirements from the database"""
    return db.query(Requirement).offset(skip).limit(limit).all()


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


def get_testcases(db: Session, skip: int = 0, limit: int = 100):
    """Retrieve all test cases from the database"""
    return db.query(TestCaseModel).offset(skip).limit(limit).all()
