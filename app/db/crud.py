from sqlalchemy.orm import Session
from app.models.db_models import Requirement, TestCase, Mapping


def create_requirement(db: Session, title: str, description: str = None):
    """Create a new requirement in the database"""
    requirement = Requirement(title=title, description=description)
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


def get_requirements(db: Session, skip: int = 0, limit: int = 100):
    """Retrieve all requirements from the database"""
    return db.query(Requirement).offset(skip).limit(limit).all()


def create_testcase(db: Session, name: str, steps: str = None):
    """Create a new test case in the database"""
    testcase = TestCase(name=name, steps=steps)
    db.add(testcase)
    db.commit()
    db.refresh(testcase)
    return testcase


def get_testcases(db: Session, skip: int = 0, limit: int = 100):
    """Retrieve all test cases from the database"""
    return db.query(TestCase).offset(skip).limit(limit).all()
