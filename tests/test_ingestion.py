import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock
import json

from app.main import app
from app.db.database import Base, get_db
from app.models.db_models import Requirement, TestCaseModel

# Setup test database
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test and drop after"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class TestJiraIngestion:
    """Test Jira ingestion endpoint"""
    
    def test_jira_ingestion_success(self):
        """Test successful Jira ingestion"""
        # Load sample data
        with open("data/jira_sample.json", "r") as f:
            mock_issues = json.load(f)
        
        # Mock the fetch_jira_issues function
        with patch("app.services.ingestion_service.fetch_jira_issues") as mock_fetch:
            mock_fetch.return_value = mock_issues
            
            # Make API request
            response = client.post(
                "/ingest/jira",
                json={
                    "jira_url": "https://test.atlassian.net",
                    "username": "test@example.com",
                    "api_token": "test_token",
                    "jql": "project = TEST"
                }
            )
            
            # Assert response
            assert response.status_code == 200
            data = response.json()
            assert data["total_fetched"] == 3
            assert data["ingested"] == 3
            assert data["failed"] == 0
            assert "Successfully ingested 3 Jira issues" in data["message"]
            
            # Verify database
            db = TestingSessionLocal()
            requirements = db.query(Requirement).all()
            assert len(requirements) == 3
            assert requirements[0].title == "PROJ-101: User login functionality"
            db.close()
    
    def test_jira_ingestion_empty_response(self):
        """Test Jira ingestion with empty response"""
        with patch("app.services.ingestion_service.fetch_jira_issues") as mock_fetch:
            mock_fetch.return_value = []
            
            response = client.post(
                "/ingest/jira",
                json={
                    "jira_url": "https://test.atlassian.net",
                    "username": "test@example.com",
                    "api_token": "test_token"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_fetched"] == 0
            assert data["ingested"] == 0
    
    def test_jira_ingestion_api_error(self):
        """Test Jira ingestion with API error"""
        with patch("app.services.ingestion_service.fetch_jira_issues") as mock_fetch:
            mock_fetch.side_effect = Exception("API connection failed")
            
            response = client.post(
                "/ingest/jira",
                json={
                    "jira_url": "https://test.atlassian.net",
                    "username": "test@example.com",
                    "api_token": "test_token"
                }
            )
            
            assert response.status_code == 500


class TestConfluenceIngestion:
    """Test Confluence ingestion endpoint"""
    
    def test_confluence_ingestion_success(self):
        """Test successful Confluence ingestion"""
        # Load sample data
        with open("data/confluence_sample.json", "r") as f:
            mock_pages = json.load(f)
        
        # Mock the fetch_confluence_pages function
        with patch("app.services.ingestion_service.fetch_confluence_pages") as mock_fetch:
            mock_fetch.return_value = mock_pages
            
            # Make API request
            response = client.post(
                "/ingest/confluence",
                json={
                    "confluence_url": "https://test.atlassian.net/wiki",
                    "username": "test@example.com",
                    "api_token": "test_token",
                    "space_key": "TEST"
                }
            )
            
            # Assert response
            assert response.status_code == 200
            data = response.json()
            assert data["total_fetched"] == 2
            assert data["ingested"] == 2
            assert data["failed"] == 0
            assert "Successfully ingested 2 Confluence pages" in data["message"]
            
            # Verify database
            db = TestingSessionLocal()
            requirements = db.query(Requirement).all()
            assert len(requirements) == 2
            assert requirements[0].title == "API Documentation"
            db.close()
    
    def test_confluence_ingestion_empty_response(self):
        """Test Confluence ingestion with empty response"""
        with patch("app.services.ingestion_service.fetch_confluence_pages") as mock_fetch:
            mock_fetch.return_value = []
            
            response = client.post(
                "/ingest/confluence",
                json={
                    "confluence_url": "https://test.atlassian.net/wiki",
                    "username": "test@example.com",
                    "api_token": "test_token"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_fetched"] == 0
            assert data["ingested"] == 0


class TestTestCasesIngestion:
    """Test test cases ingestion endpoint"""
    
    def test_testcases_ingestion_success(self):
        """Test successful test cases ingestion from CSV"""
        response = client.post(
            "/ingest/testcases",
            json={
                "file_path": "data/test_cases.csv"
            }
        )
        
        # Assert response
        assert response.status_code == 200
        data = response.json()
        assert data["total_fetched"] == 3
        assert data["ingested"] == 3
        assert data["failed"] == 0
        assert "Successfully ingested 3 test cases" in data["message"]
        
        # Verify database
        db = TestingSessionLocal()
        testcases = db.query(TestCaseModel).all()
        assert len(testcases) == 3
        assert "TC001 - Login Test" in testcases[0].name
        db.close()
    
    def test_testcases_ingestion_invalid_file(self):
        """Test test cases ingestion with invalid file path"""
        response = client.post(
            "/ingest/testcases",
            json={
                "file_path": "data/nonexistent.csv"
            }
        )
        
        assert response.status_code == 500


class TestDatabaseIntegrity:
    """Test database operations and integrity"""
    
    def test_duplicate_requirements(self):
        """Test handling of duplicate requirements"""
        with open("data/jira_sample.json", "r") as f:
            mock_issues = json.load(f)
        
        with patch("app.services.ingestion_service.fetch_jira_issues") as mock_fetch:
            mock_fetch.return_value = mock_issues
            
            # Ingest first time
            response1 = client.post(
                "/ingest/jira",
                json={"jira_url": "https://test.atlassian.net", "username": "test@example.com", "api_token": "test_token"}
            )
            assert response1.status_code == 200
            
            # Ingest second time (same data)
            response2 = client.post(
                "/ingest/jira",
                json={"jira_url": "https://test.atlassian.net", "username": "test@example.com", "api_token": "test_token"}
            )
            assert response2.status_code == 200
            
            # Check for duplicates - should only have 3 records due to unique constraint
            db = TestingSessionLocal()
            requirements = db.query(Requirement).all()
            assert len(requirements) == 3  # No duplicates should be created
            db.close()
    
    def test_database_rollback_on_error(self):
        """Test that database rolls back on error during ingestion"""
        # This test ensures partial failures don't corrupt the database
        pass  # TODO: Implement when error handling is improved
