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
    get_mappings_for_testcase,
    extract_keywords,
    calculate_keyword_match_score,
    calculate_hybrid_similarity
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


class TestKeywordExtraction:
    """Test keyword extraction functions"""
    
    def test_extract_keywords_basic(self):
        """Test basic keyword extraction"""
        text = "User login functionality with email and password authentication"
        keywords = extract_keywords(text)
        
        assert "user" in keywords
        assert "login" in keywords
        assert "functionality" in keywords
        assert "email" in keywords
        assert "password" in keywords
        assert "authentication" in keywords
        
        # Stop words should be excluded
        assert "with" not in keywords
        assert "and" not in keywords
    
    def test_extract_keywords_with_numbers(self):
        """Test keyword extraction with numbers"""
        text = "TC001 - Login Test for User Authentication"
        keywords = extract_keywords(text)
        
        assert "tc001" in keywords or "001" in keywords
        assert "login" in keywords
        assert "test" in keywords
    
    def test_extract_keywords_hyphenated(self):
        """Test keyword extraction with hyphenated words"""
        text = "Multi-factor authentication for end-users"
        keywords = extract_keywords(text)
        
        assert "multi-factor" in keywords or "multi" in keywords
        assert "authentication" in keywords
        assert "end-users" in keywords or "users" in keywords
    
    def test_extract_keywords_empty(self):
        """Test keyword extraction with empty text"""
        keywords = extract_keywords("")
        assert len(keywords) == 0
        
        keywords = extract_keywords(None)
        assert len(keywords) == 0
    
    def test_extract_keywords_min_length(self):
        """Test keyword extraction with minimum length"""
        text = "A user can login to the system"
        keywords = extract_keywords(text, min_length=3)
        
        # Short words should be excluded
        assert "user" in keywords
        assert "login" in keywords
        assert "system" in keywords


class TestKeywordMatching:
    """Test keyword matching functions"""
    
    def test_keyword_match_score_identical(self):
        """Test keyword match score for identical sets"""
        keywords1 = {"login", "user", "password", "authentication"}
        keywords2 = {"login", "user", "password", "authentication"}
        
        score = calculate_keyword_match_score(keywords1, keywords2)
        assert score == 1.0
    
    def test_keyword_match_score_partial(self):
        """Test keyword match score for partial overlap"""
        keywords1 = {"login", "user", "password"}
        keywords2 = {"login", "user", "email"}
        
        score = calculate_keyword_match_score(keywords1, keywords2)
        # Intersection: {login, user} = 2
        # Union: {login, user, password, email} = 4
        # Score: 2/4 = 0.5
        assert score == 0.5
    
    def test_keyword_match_score_no_overlap(self):
        """Test keyword match score for no overlap"""
        keywords1 = {"login", "user"}
        keywords2 = {"dashboard", "report"}
        
        score = calculate_keyword_match_score(keywords1, keywords2)
        assert score == 0.0
    
    def test_keyword_match_score_empty(self):
        """Test keyword match score with empty sets"""
        keywords1 = {"login", "user"}
        keywords2 = set()
        
        score = calculate_keyword_match_score(keywords1, keywords2)
        assert score == 0.0


class TestHybridSimilarity:
    """Test hybrid similarity combining keywords and TF-IDF"""
    
    def test_hybrid_similarity_basic(self):
        """Test basic hybrid similarity"""
        text1 = "User login with email and password"
        text2 = "Login functionality for users with email credentials"
        
        result = calculate_hybrid_similarity(text1, text2)
        
        assert "keyword_score" in result
        assert "tfidf_score" in result
        assert "combined_score" in result
        assert "matched_keywords" in result
        
        # Should have some matched keywords
        assert len(result["matched_keywords"]) > 0
        assert "login" in result["matched_keywords"]
        assert "email" in result["matched_keywords"]
    
    def test_hybrid_similarity_custom_weights(self):
        """Test hybrid similarity with custom weights"""
        text1 = "User authentication system"
        text2 = "User authentication process"
        
        # Test with keyword-heavy weighting
        result1 = calculate_hybrid_similarity(text1, text2, keyword_weight=0.8, tfidf_weight=0.2)
        
        # Test with TF-IDF-heavy weighting
        result2 = calculate_hybrid_similarity(text1, text2, keyword_weight=0.2, tfidf_weight=0.8)
        
        # Both should have valid scores
        assert 0 <= result1["combined_score"] <= 1
        assert 0 <= result2["combined_score"] <= 1
    
    def test_hybrid_similarity_different_texts(self):
        """Test hybrid similarity with very different texts"""
        text1 = "User login functionality"
        text2 = "Export PDF reports"
        
        result = calculate_hybrid_similarity(text1, text2)
        
        # Should have low similarity
        assert result["combined_score"] < 0.3
        assert len(result["matched_keywords"]) == 0


class TestKeywordBasedMapping:
    """Test mapping with keyword matching enabled"""
    
    def test_mapping_with_keyword_matching(self):
        """Test that keyword matching improves mapping accuracy"""
        db = TestingSessionLocal()
        
        # Create requirement with specific keywords
        req = create_requirement(
            db, 
            "User Authentication Feature",
            "Implement login functionality with email and password"
        )
        
        # Create test cases with varying keyword matches
        tc1 = create_testcase(
            db, 
            "TC001 - User Login Test",
            "Test login with email and password credentials"
        )
        tc2 = create_testcase(
            db,
            "TC002 - Dashboard View",
            "Verify dashboard displays user data"
        )
        
        # Map with keyword matching enabled
        result = map_requirements_to_testcases(
            db, 
            similarity_threshold=0.2,
            use_keyword_matching=True
        )
        
        assert result["use_keyword_matching"] is True
        assert result["mappings_created"] > 0
        
        # TC001 should be mapped (has matching keywords: login, email, password)
        mappings = get_mappings_for_requirement(db, req.id)
        assert len(mappings) > 0
        
        db.close()
    
    def test_mapping_without_keyword_matching(self):
        """Test mapping with keyword matching disabled (TF-IDF only)"""
        db = TestingSessionLocal()
        
        req = create_requirement(db, "Login Feature", "User authentication")
        tc = create_testcase(db, "TC001 - Login Test", "Test user login")
        
        # Map without keyword matching
        result = map_requirements_to_testcases(
            db,
            similarity_threshold=0.2,
            use_keyword_matching=False
        )
        
        assert result["use_keyword_matching"] is False
        
        db.close()
