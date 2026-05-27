"""
Tests for Report Service CSV Export functionality.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import csv
import io

from app.db.database import Base
from app.models.db_models import Requirement, TestCaseModel, Mapping
from app.services.report_service import (
    export_coverage_report_csv,
    export_risk_report_csv,
    export_traceability_matrix_csv,
    export_summary_report_csv,
    generate_comprehensive_report
)


# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_data(db):
    """Create sample data for testing."""
    # Create requirements
    req1 = Requirement(id=1, title="User Login", description="User should be able to login")
    req2 = Requirement(id=2, title="User Registration", description="User should be able to register")
    req3 = Requirement(id=3, title="Password Reset", description="User should be able to reset password")
    
    db.add_all([req1, req2, req3])
    
    # Create test cases
    tc1 = TestCaseModel(id=1, name="TC001: Login Test", steps="Step 1: Enter credentials")
    tc2 = TestCaseModel(id=2, name="TC002: Registration Test", steps="Step 1: Fill form")
    
    db.add_all([tc1, tc2])
    
    # Create mappings (req3 will be uncovered)
    mapping1 = Mapping(id=1, requirement_id=1, testcase_id=1)
    mapping2 = Mapping(id=2, requirement_id=2, testcase_id=2)
    
    db.add_all([mapping1, mapping2])
    db.commit()
    
    return {
        "requirements": [req1, req2, req3],
        "test_cases": [tc1, tc2],
        "mappings": [mapping1, mapping2]
    }


def test_export_coverage_report_csv(db, sample_data):
    """Test coverage report CSV export."""
    csv_content = export_coverage_report_csv(db)
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)
    
    # Should have 3 requirements
    assert len(rows) == 3
    
    # Check headers
    assert "Requirement ID" in reader.fieldnames
    assert "Coverage Status" in reader.fieldnames
    assert "Test Case Count" in reader.fieldnames
    
    # Check covered requirement
    req1_row = [r for r in rows if r["Requirement ID"] == "1"][0]
    assert req1_row["Coverage Status"] == "Covered"
    assert int(req1_row["Test Case Count"]) > 0
    
    # Check uncovered requirement
    req3_row = [r for r in rows if r["Requirement ID"] == "3"][0]
    assert req3_row["Coverage Status"] == "Uncovered"
    assert int(req3_row["Test Case Count"]) == 0


def test_export_risk_report_csv(db, sample_data):
    """Test risk report CSV export."""
    csv_content = export_risk_report_csv(db)
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)
    
    # Should have 3 requirements
    assert len(rows) == 3
    
    # Check headers
    assert "Risk Level" in reader.fieldnames
    
    # Check high risk (uncovered) requirements
    high_risk_rows = [r for r in rows if r["Risk Level"] == "High"]
    assert len(high_risk_rows) == 1
    assert high_risk_rows[0]["Requirement ID"] == "3"
    
    # Check low risk (covered) requirements
    low_risk_rows = [r for r in rows if r["Risk Level"] == "Low"]
    assert len(low_risk_rows) == 2


def test_export_traceability_matrix_csv(db, sample_data):
    """Test traceability matrix CSV export."""
    csv_content = export_traceability_matrix_csv(db)
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)
    
    # Should have 2 mappings
    assert len(rows) == 2
    
    # Check headers
    assert "Mapping ID" in reader.fieldnames
    assert "Requirement ID" in reader.fieldnames
    assert "Test Case ID" in reader.fieldnames
    
    # Verify mapping content
    mapping1_row = [r for r in rows if r["Mapping ID"] == "1"][0]
    assert mapping1_row["Requirement ID"] == "1"
    assert mapping1_row["Test Case ID"] == "1"
    assert "Login" in mapping1_row["Requirement Title"]


def test_export_summary_report_csv(db, sample_data):
    """Test summary report CSV export."""
    csv_content = export_summary_report_csv(db)
    
    # Check that CSV contains key sections
    assert "RTM Automation Engine - Summary Report" in csv_content
    assert "Coverage Metrics" in csv_content
    assert "Risk Analysis" in csv_content
    assert "Total Requirements" in csv_content
    assert "Coverage Percentage" in csv_content
    
    # Parse to verify structure
    lines = csv_content.split('\n')
    assert len(lines) > 10  # Should have multiple sections


def test_generate_comprehensive_report(db, sample_data):
    """Test comprehensive report generation."""
    report = generate_comprehensive_report(db)
    
    # Check structure
    assert "coverage" in report
    assert "risk" in report
    assert "timestamp" in report
    
    # Check coverage data
    assert report["coverage"]["total_requirements"] == 3
    assert report["coverage"]["covered_requirements"] == 2
    assert report["coverage"]["uncovered_requirements"] == 1
    
    # Check risk data
    assert report["risk"]["uncovered_count"] == 1
    assert 0 <= report["risk"]["risk_score"] <= 100


def test_csv_export_with_empty_database(db):
    """Test CSV export with no data."""
    csv_content = export_coverage_report_csv(db)
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)
    
    # Should have headers but no data rows
    assert len(rows) == 0
    assert "Requirement ID" in reader.fieldnames


def test_csv_export_special_characters(db):
    """Test CSV export handles special characters properly."""
    # Create requirement with special characters
    req = Requirement(
        id=1,
        title='Test "Quotes" and, Commas',
        description="Multi-line\ndescription\nwith newlines"
    )
    db.add(req)
    db.commit()
    
    csv_content = export_coverage_report_csv(db)
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)
    
    # Should properly handle special characters
    assert len(rows) == 1
    assert 'Quotes' in rows[0]["Requirement Title"]
