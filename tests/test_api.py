"""
Integration tests for Report API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import csv
import io
from unittest.mock import patch

from app.main import app
from app.db.database import Base, get_db
from app.models.db_models import Requirement, TestCaseModel, Mapping


# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db(test_db):
    """Provide a database session for each test."""
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(test_db):
    """Create a test client with database dependency override."""
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    # Override the database dependency
    app.dependency_overrides[get_db] = override_get_db
    
    # Patch the engines used in the app to prevent connecting to PostgreSQL
    with patch('app.main.engine', test_engine), \
         patch('app.db.database.engine', test_engine):
        with TestClient(app) as test_client:
            yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_data(db):
    """Create sample data for testing."""
    # Create requirements
    req1 = Requirement(id=1, title="User Authentication", description="User should be able to authenticate")
    req2 = Requirement(id=2, title="Data Validation", description="System should validate input data")
    req3 = Requirement(id=3, title="Error Handling", description="System should handle errors gracefully")
    req4 = Requirement(id=4, title="API Documentation", description="API should be documented")
    
    db.add_all([req1, req2, req3, req4])
    
    # Create test cases
    tc1 = TestCaseModel(id=1, name="TC001: Login Test", steps="Step 1: Enter credentials\nStep 2: Submit")
    tc2 = TestCaseModel(id=2, name="TC002: Validation Test", steps="Step 1: Enter invalid data\nStep 2: Check error")
    tc3 = TestCaseModel(id=3, name="TC003: Auth Token Test", steps="Step 1: Request token\nStep 2: Verify")
    
    db.add_all([tc1, tc2, tc3])
    
    # Create mappings (req3 and req4 will be uncovered)
    mapping1 = Mapping(id=1, requirement_id=1, testcase_id=1)
    mapping2 = Mapping(id=2, requirement_id=1, testcase_id=3)  # req1 has 2 test cases
    mapping3 = Mapping(id=3, requirement_id=2, testcase_id=2)
    
    db.add_all([mapping1, mapping2, mapping3])
    db.commit()
    
    return {
        "requirements": [req1, req2, req3, req4],
        "test_cases": [tc1, tc2, tc3],
        "mappings": [mapping1, mapping2, mapping3]
    }


class TestReportAPI:
    """Test suite for Report API endpoints."""
    
    def test_get_comprehensive_report(self, client, sample_data):
        """Test GET /api/report/ - comprehensive report generation."""
        response = client.get("/api/report/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "coverage" in data
        assert "risk" in data
        assert "timestamp" in data
        
        # Check coverage data
        coverage = data["coverage"]
        assert coverage["total_requirements"] == 4
        assert coverage["covered_requirements"] == 2
        assert coverage["uncovered_requirements"] == 2
        assert coverage["coverage_percentage"] == 50.0
        
        # Check risk data
        risk = data["risk"]
        assert "uncovered_count" in risk
        assert "risk_score" in risk
        assert risk["uncovered_count"] == 2
        assert 0 <= risk["risk_score"] <= 100
    
    def test_get_comprehensive_report_with_pagination(self, client, sample_data):
        """Test report with pagination parameters."""
        response = client.get("/api/report/?skip=0&limit=2")
        
        assert response.status_code == 200
        data = response.json()
        
        # Coverage should still show all requirements
        assert data["coverage"]["total_requirements"] == 4
        
        # Risk data might be paginated
        assert "risk" in data
    
    def test_get_comprehensive_report_with_days_threshold(self, client, sample_data):
        """Test report with custom days threshold."""
        response = client.get("/api/report/?days_threshold=60")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "coverage" in data
        assert "risk" in data
    
    def test_export_coverage_csv(self, client, sample_data):
        """Test GET /api/report/export/coverage - CSV export."""
        response = client.get("/api/report/export/coverage")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "coverage_report.csv" in response.headers["content-disposition"]
        
        # Parse CSV content
        csv_content = response.text
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        # Should have 4 requirements
        assert len(rows) == 4
        
        # Check headers
        assert "Requirement ID" in reader.fieldnames
        assert "Title" in reader.fieldnames
        assert "Coverage Status" in reader.fieldnames
        assert "Test Case Count" in reader.fieldnames
        
        # Check covered requirement
        req1_row = [r for r in rows if r["Requirement ID"] == "1"][0]
        assert req1_row["Coverage Status"] == "Covered"
        assert int(req1_row["Test Case Count"]) == 2
        
        # Check uncovered requirement
        req3_row = [r for r in rows if r["Requirement ID"] == "3"][0]
        assert req3_row["Coverage Status"] == "Uncovered"
        assert int(req3_row["Test Case Count"]) == 0
    
    def test_export_risk_csv(self, client, sample_data):
        """Test GET /api/report/export/risk - risk CSV export."""
        response = client.get("/api/report/export/risk")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "risk_report.csv" in response.headers["content-disposition"]
        
        # Parse CSV content
        csv_content = response.text
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        # Should have 4 requirements
        assert len(rows) == 4
        
        # Check headers
        assert "Risk Level" in reader.fieldnames
        assert "Requirement ID" in reader.fieldnames
        
        # Check high risk (uncovered) requirements
        high_risk_rows = [r for r in rows if r["Risk Level"] == "High"]
        assert len(high_risk_rows) == 2
        
        # Check low risk (covered) requirements
        low_risk_rows = [r for r in rows if r["Risk Level"] == "Low"]
        assert len(low_risk_rows) == 2
    
    def test_export_risk_csv_with_days_threshold(self, client, sample_data):
        """Test risk CSV export with custom days threshold."""
        response = client.get("/api/report/export/risk?days_threshold=90")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        
        csv_content = response.text
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) == 4
    
    def test_export_traceability_matrix_csv(self, client, sample_data):
        """Test GET /api/report/export/traceability - traceability matrix CSV."""
        response = client.get("/api/report/export/traceability")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "traceability_matrix.csv" in response.headers["content-disposition"]
        
        # Parse CSV content
        csv_content = response.text
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        # Should have 3 mappings
        assert len(rows) == 3
        
        # Check headers
        assert "Mapping ID" in reader.fieldnames
        assert "Requirement ID" in reader.fieldnames
        assert "Test Case ID" in reader.fieldnames
        assert "Requirement Title" in reader.fieldnames
        assert "Test Case Name" in reader.fieldnames
        
        # Verify mapping content
        mapping1_row = [r for r in rows if r["Mapping ID"] == "1"][0]
        assert mapping1_row["Requirement ID"] == "1"
        assert mapping1_row["Test Case ID"] == "1"
        assert "Authentication" in mapping1_row["Requirement Title"]
        assert "TC001" in mapping1_row["Test Case Name"]
    
    def test_export_summary_csv(self, client, sample_data):
        """Test GET /api/report/export/summary - summary report CSV."""
        response = client.get("/api/report/export/summary")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "summary_report.csv" in response.headers["content-disposition"]
        
        # Check content contains key sections
        csv_content = response.text
        assert "RTM Automation Engine - Summary Report" in csv_content
        assert "Coverage Metrics" in csv_content
        assert "Risk Analysis" in csv_content
        assert "Total Requirements" in csv_content
        assert "Coverage Percentage" in csv_content
    
    def test_export_summary_csv_with_days_threshold(self, client, sample_data):
        """Test summary CSV export with custom days threshold."""
        response = client.get("/api/report/export/summary?days_threshold=45")
        
        assert response.status_code == 200
        assert "RTM Automation Engine" in response.text
    
    def test_all_endpoints_with_empty_database(self, client):
        """Test all report endpoints with empty database."""
        # Comprehensive report
        response = client.get("/api/report/")
        assert response.status_code == 200
        data = response.json()
        assert data["coverage"]["total_requirements"] == 0
        
        # Coverage CSV
        response = client.get("/api/report/export/coverage")
        assert response.status_code == 200
        
        # Risk CSV
        response = client.get("/api/report/export/risk")
        assert response.status_code == 200
        
        # Traceability CSV
        response = client.get("/api/report/export/traceability")
        assert response.status_code == 200
        
        # Summary CSV
        response = client.get("/api/report/export/summary")
        assert response.status_code == 200
    
    def test_pagination_validation(self, client, sample_data):
        """Test pagination parameter validation."""
        # Negative skip should fail
        response = client.get("/api/report/?skip=-1")
        assert response.status_code == 422
        
        # Zero skip should work
        response = client.get("/api/report/?skip=0")
        assert response.status_code == 200
        
        # Limit too high should fail
        response = client.get("/api/report/?limit=2000")
        assert response.status_code == 422
        
        # Valid limit should work
        response = client.get("/api/report/?limit=100")
        assert response.status_code == 200
    
    def test_days_threshold_validation(self, client, sample_data):
        """Test days_threshold parameter."""
        # Various valid thresholds
        for days in [1, 7, 30, 90, 365]:
            response = client.get(f"/api/report/?days_threshold={days}")
            assert response.status_code == 200
    
    def test_csv_content_type_and_headers(self, client, sample_data):
        """Test CSV responses have correct content type and headers."""
        endpoints = [
            "/api/report/export/coverage",
            "/api/report/export/risk",
            "/api/report/export/traceability",
            "/api/report/export/summary"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200
            assert "text/csv" in response.headers["content-type"]
            assert "attachment" in response.headers["content-disposition"]
            assert ".csv" in response.headers["content-disposition"]
