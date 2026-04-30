import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.db_models import Requirement, TestCaseModel, Mapping
from app.db.crud import create_requirement, create_testcase
from app.services.trace_service import (
    map_requirements_to_testcases,
    calculate_text_similarity,
    combine_text_fields,
    get_mappings_for_requirement,
    get_mappings_for_testcase
)

# Setup test database
TEST_DATABASE_URL = "sqlite:///./test_trace.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test and drop after"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class TestTextSimilarity:
    """Test text similarity functions"""
    
    def test_calculate_text_similarity_identical(self):
        """Test similarity of identical texts"""
        text = "User login functionality with authentication"
        similarity = calculate_text_similarity(text, text)
        assert similarity == 1.0
    
    def test_calculate_text_similarity_similar(self):
        """Test similarity of similar texts"""
        text1 = "User login with email and password"
        text2 = "Login functionality for users with email password authentication"
        similarity = calculate_text_similarity(text1, text2)
        assert similarity > 0.3  # Should have some similarity
    
    def test_calculate_text_similarity_different(self):
        """Test similarity of different texts"""
        text1 = "User login functionality"
        text2 = "Export PDF reports"
        similarity = calculate_text_similarity(text1, text2)
        assert similarity < 0.3  # Should have low similarity
    
    def test_calculate_text_similarity_empty(self):
        """Test similarity with empty text"""
        similarity = calculate_text_similarity("", "some text")
        assert similarity == 0.0
    
    def test_combine_text_fields(self):
        """Test combining text fields"""
        result = combine_text_fields("Title", "Description here")
        assert result == "Title Description here"
        
        result = combine_text_fields("Title", None)
        assert result == "Title"


class TestMappingCreation:
    """Test requirement to test case mapping"""
    
    def test_map_requirements_to_testcases_success(self):
        """Test successful mapping creation"""
        db = TestingSessionLocal()
        
        # Create requirements
        req1 = create_requirement(db, "User Login", "Authenticate users with email and password")
        req2 = create_requirement(db, "Dashboard View", "Display user analytics and metrics")
        
        # Create test cases
        tc1 = create_testcase(db, "TC001 - Login Test", "Test user login with valid credentials")
        tc2 = create_testcase(db, "TC002 - Dashboard Test", "Verify dashboard displays correctly")
        
        # Map requirements to test cases
        result = map_requirements_to_testcases(db, similarity_threshold=0.2)
        
        # Assert results
        assert result["total_requirements"] == 2
        assert result["total_testcases"] == 2
        assert result["mappings_created"] > 0
        
        # Verify mappings exist
        mappings = db.query(Mapping).all()
        assert len(mappings) > 0
        
        db.close()
    
    def test_map_requirements_to_testcases_with_threshold(self):
        """Test mapping with high similarity threshold"""
        db = TestingSessionLocal()
        
        # Create requirements and test cases with low similarity
        req1 = create_requirement(db, "User Login", "Authentication functionality")
        tc1 = create_testcase(db, "TC001 - Export PDF", "Test PDF export feature")
        
        # Map with high threshold (should create no mappings)
        result = map_requirements_to_testcases(db, similarity_threshold=0.8)
        
        assert result["mappings_created"] == 0
        
        db.close()
    
    def test_map_requirements_to_testcases_empty_database(self):
        """Test mapping with empty database"""
        db = TestingSessionLocal()
        
        result = map_requirements_to_testcases(db)
        
        assert result["total_requirements"] == 0
        assert result["total_testcases"] == 0
        assert result["mappings_created"] == 0
        
        db.close()
    
    def test_get_mappings_for_requirement(self):
        """Test retrieving mappings for a specific requirement"""
        db = TestingSessionLocal()
        
        # Create and map
        req = create_requirement(db, "Login Feature", "User authentication")
        tc = create_testcase(db, "TC001 - Login", "Test login functionality")
        
        map_requirements_to_testcases(db, similarity_threshold=0.1)
        
        # Get mappings for requirement
        mappings = get_mappings_for_requirement(db, req.id)
        
        assert len(mappings) > 0
        assert mappings[0].requirement_id == req.id
        
        db.close()
    
    def test_get_mappings_for_testcase(self):
        """Test retrieving mappings for a specific test case"""
        db = TestingSessionLocal()
        
        # Create and map
        req = create_requirement(db, "Dashboard", "User dashboard view")
        tc = create_testcase(db, "TC002 - Dashboard", "Verify dashboard loads")
        
        map_requirements_to_testcases(db, similarity_threshold=0.1)
        
        # Get mappings for test case
        mappings = get_mappings_for_testcase(db, tc.id)
        
        assert len(mappings) > 0
        assert mappings[0].testcase_id == tc.id
        
        db.close()
    
    def test_max_mappings_per_requirement(self):
        """Test limiting maximum mappings per requirement"""
        db = TestingSessionLocal()
        
        # Create one requirement
        req = create_requirement(db, "Login", "User login feature")
        
        # Create multiple similar test cases
        for i in range(10):
            create_testcase(db, f"TC{i:03d} - Login Test {i}", "Test login functionality")
        
        # Map with limit of 3
        result = map_requirements_to_testcases(
            db, 
            similarity_threshold=0.1, 
            max_mappings_per_requirement=3
        )
        
        # Should create at most 3 mappings for the requirement
        mappings = get_mappings_for_requirement(db, req.id)
        assert len(mappings) <= 3
        
        db.close()


class TestMappingDuplicates:
    """Test duplicate mapping prevention"""
    
    def test_no_duplicate_mappings(self):
        """Test that duplicate mappings are not created"""
        db = TestingSessionLocal()
        
        req = create_requirement(db, "Feature A", "Description A")
        tc = create_testcase(db, "TC001", "Test for feature A")
        
        # Map twice
        map_requirements_to_testcases(db, similarity_threshold=0.1)
        map_requirements_to_testcases(db, similarity_threshold=0.1)
        
        # Should only have unique mappings
        mappings = db.query(Mapping).filter(
            Mapping.requirement_id == req.id,
            Mapping.testcase_id == tc.id
        ).all()
        
        assert len(mappings) == 1
        
        db.close()
