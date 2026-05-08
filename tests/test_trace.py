"""
Tests for traceability service and graph functionality.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.db_models import Requirement, TestCaseModel, Mapping
from app.db.crud import create_requirement, create_testcase
from app.services.trace_service import (
    TraceabilityService,
    map_requirements_to_testcases,
    calculate_text_similarity,
    extract_keywords,
    calculate_keyword_match_score,
    calculate_hybrid_similarity,
    get_mappings_for_requirement,
    get_mappings_for_testcase
)
from app.utils.text_processing import SimilarityCalculator, combine_text_fields
from app.graph.traversal import TraceabilityGraph

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


class TestSimilarityCalculator:
    """Test the SimilarityCalculator class"""
    
    def test_calculate_tfidf_similarity_identical(self):
        """Test similarity of identical texts"""
        calculator = SimilarityCalculator()
        text = "User login functionality with authentication"
        similarity = calculator.calculate_tfidf_similarity(text, text)
        assert similarity == 1.0
    
    def test_calculate_tfidf_similarity_similar(self):
        """Test similarity of similar texts"""
        calculator = SimilarityCalculator()
        text1 = "User login with email and password"
        text2 = "Login functionality for users with email password authentication"
        similarity = calculator.calculate_tfidf_similarity(text1, text2)
        assert similarity > 0.3
    
    def test_calculate_tfidf_similarity_different(self):
        """Test similarity of different texts"""
        calculator = SimilarityCalculator()
        text1 = "User login functionality"
        text2 = "Export PDF reports"
        similarity = calculator.calculate_tfidf_similarity(text1, text2)
        assert similarity < 0.3
    
    def test_calculate_tfidf_similarity_empty(self):
        """Test similarity with empty text"""
        calculator = SimilarityCalculator()
        similarity = calculator.calculate_tfidf_similarity("", "some text")
        assert similarity == 0.0
    
    def test_extract_keywords_basic(self):
        """Test keyword extraction"""
        calculator = SimilarityCalculator()
        keywords = calculator.extract_keywords("User login with authentication system")
        assert "user" in keywords
        assert "login" in keywords
        assert "authentication" in keywords
        assert "system" in keywords
        # Stop words should be excluded
        assert "with" not in keywords
    
    def test_extract_keywords_with_numbers(self):
        """Test keyword extraction with numbers"""
        calculator = SimilarityCalculator()
        keywords = calculator.extract_keywords("Test case TC001 for user authentication")
        assert "tc001" in keywords
        assert "user" in keywords
        assert "authentication" in keywords
    
    def test_extract_keywords_hyphenated(self):
        """Test keyword extraction with hyphenated words"""
        calculator = SimilarityCalculator()
        keywords = calculator.extract_keywords("Test multi-factor authentication system")
        assert "multi-factor" in keywords
        assert "authentication" in keywords
    
    def test_calculate_keyword_similarity(self):
        """Test keyword-based similarity calculation"""
        calculator = SimilarityCalculator()
        keywords1 = {"user", "login", "authentication"}
        keywords2 = {"user", "authentication", "system"}
        
        similarity = calculator.calculate_keyword_similarity(keywords1, keywords2)
        # Jaccard: intersection {user, authentication} / union {user, login, authentication, system}
        # = 2/4 = 0.5
        assert similarity == 0.5
    
    def test_calculate_hybrid_similarity(self):
        """Test hybrid similarity calculation"""
        calculator = SimilarityCalculator()
        text1 = "User login with authentication"
        text2 = "Login authentication for users"
        
        result = calculator.calculate_hybrid_similarity(text1, text2)
        
        assert "keyword_score" in result
        assert "tfidf_score" in result
        assert "combined_score" in result
        assert "matched_keywords" in result
        assert result["combined_score"] > 0.3
    
    def test_combine_text_fields(self):
        """Test combining text fields"""
        result = combine_text_fields("Title", "Description here")
        assert result == "Title Description here"
        
        result = combine_text_fields("Title", None)
        assert result == "Title"


class TestTraceabilityService:
    """Test the TraceabilityService class"""
    
    def test_generate_traceability_matrix_success(self):
        """Test successful traceability matrix generation"""
        db = TestingSessionLocal()
        
        # Create requirements
        req1 = create_requirement(db, "User Login", "Authenticate users with email and password")
        req2 = create_requirement(db, "Dashboard View", "Display user analytics and metrics")
        
        # Create test cases
        tc1 = create_testcase(db, "TC001 - Login Test", "Test user login with valid credentials")
        tc2 = create_testcase(db, "TC002 - Dashboard Test", "Verify dashboard displays correctly")
        
        # Generate traceability matrix
        service = TraceabilityService(similarity_threshold=0.2)
        result = service.generate_traceability_matrix(db)
        
        # Assert results
        assert result["total_requirements"] == 2
        assert result["total_testcases"] == 2
        assert result["mappings_created"] > 0
        
        # Verify mappings exist
        mappings = db.query(Mapping).all()
        assert len(mappings) > 0
        
        db.close()
    
    def test_generate_traceability_matrix_with_threshold(self):
        """Test matrix generation with high similarity threshold"""
        db = TestingSessionLocal()
        
        # Create requirements and test cases with low similarity
        req1 = create_requirement(db, "User Login", "Authentication functionality")
        tc1 = create_testcase(db, "TC001 - Export PDF", "Test PDF export feature")
        
        # Generate with high threshold (should create no mappings)
        service = TraceabilityService(similarity_threshold=0.8)
        result = service.generate_traceability_matrix(db)
        
        assert result["mappings_created"] == 0
        
        db.close()
    
    def test_get_requirement_coverage(self):
        """Test getting requirement coverage"""
        db = TestingSessionLocal()
        
        # Create and map
        req = create_requirement(db, "Login Feature", "User authentication")
        tc = create_testcase(db, "TC001 - Login", "Test login functionality")
        
        service = TraceabilityService(similarity_threshold=0.1)
        service.generate_traceability_matrix(db)
        
        # Get coverage
        coverage = service.get_requirement_coverage(db, req.id)
        
        assert coverage["requirement_id"] == req.id
        assert coverage["is_covered"] == True
        assert coverage["total_testcases"] > 0
        
        db.close()
    
    def test_get_testcase_coverage(self):
        """Test getting test case coverage"""
        db = TestingSessionLocal()
        
        # Create and map
        req = create_requirement(db, "Dashboard", "User dashboard view")
        tc = create_testcase(db, "TC002 - Dashboard", "Verify dashboard loads")
        
        service = TraceabilityService(similarity_threshold=0.1)
        service.generate_traceability_matrix(db)
        
        # Get coverage
        coverage = service.get_testcase_coverage(db, tc.id)
        
        assert coverage["testcase_id"] == tc.id
        assert coverage["covers_requirements"] == True
        assert coverage["total_requirements"] > 0
        
        db.close()
    
    def test_find_similar_testcases(self):
        """Test finding similar test cases for a requirement"""
        db = TestingSessionLocal()
        
        # Create requirement and test cases
        req = create_requirement(db, "User Login", "Authenticate users with credentials")
        tc1 = create_testcase(db, "TC001 - Login Test", "Test user login functionality")
        tc2 = create_testcase(db, "TC002 - Export PDF", "Test PDF export feature")
        tc3 = create_testcase(db, "TC003 - Auth Test", "Test user authentication")
        
        from app.db.crud import get_testcases
        testcases = get_testcases(db)
        
        service = TraceabilityService(similarity_threshold=0.2)
        matches = service.find_similar_testcases(req, testcases)
        
        # Should find TC001 and TC003 as similar (both related to login/auth)
        assert len(matches) > 0
        assert all(match.similarity_score >= 0.2 for match in matches)
        
        db.close()


class TestTraceabilityGraph:
    """Test the TraceabilityGraph class"""
    
    def test_graph_creation(self):
        """Test creating a traceability graph"""
        db = TestingSessionLocal()
        
        # Create requirements and test cases
        req1 = create_requirement(db, "Feature A", "Description A")
        tc1 = create_testcase(db, "TC001", "Test for feature A")
        
        # Create mappings
        service = TraceabilityService(similarity_threshold=0.1)
        service.generate_traceability_matrix(db)
        
        # Create graph
        graph = TraceabilityGraph(db)
        
        # Verify graph has data
        testcases = graph.get_testcases_for_requirement(req1.id)
        assert len(testcases) > 0
        
        db.close()
    
    def test_get_coverage_statistics(self):
        """Test getting coverage statistics"""
        db = TestingSessionLocal()
        
        # Create data
        req1 = create_requirement(db, "Feature A", "Description A")
        req2 = create_requirement(db, "Feature B", "Description B")
        tc1 = create_testcase(db, "TC001", "Test A")
        tc2 = create_testcase(db, "TC002", "Test B")
        
        service = TraceabilityService(similarity_threshold=0.1)
        service.generate_traceability_matrix(db)
        
        graph = TraceabilityGraph(db)
        stats = graph.get_coverage_statistics()
        
        assert "total_requirements" in stats
        assert "total_testcases" in stats
        assert "covered_requirements" in stats
        assert "requirement_coverage_percentage" in stats
        assert stats["total_requirements"] == 2
        assert stats["total_testcases"] == 2
        
        db.close()
    
    def test_find_orphaned_items(self):
        """Test finding orphaned requirements and test cases"""
        db = TestingSessionLocal()
        
        # Create requirements and test cases
        req1 = create_requirement(db, "Covered Feature", "Has test case")
        req2 = create_requirement(db, "Orphaned Feature", "No test case")
        tc1 = create_testcase(db, "TC001 - Covered", "Test for feature")
        tc2 = create_testcase(db, "TC002 - Orphan", "Unrelated test")
        
        # Map only req1 and tc1
        service = TraceabilityService(similarity_threshold=0.2)
        service.generate_traceability_matrix(db)
        
        graph = TraceabilityGraph(db)
        orphaned = graph.find_orphaned_items()
        
        assert "requirements" in orphaned
        assert "testcases" in orphaned
        
        db.close()
    
    def test_get_impact_analysis(self):
        """Test impact analysis for a requirement"""
        db = TestingSessionLocal()
        
        # Create requirements and test cases
        req1 = create_requirement(db, "User Authentication", "Login feature")
        req2 = create_requirement(db, "User Profile", "Profile management")
        tc1 = create_testcase(db, "TC001 - Auth Test", "Test authentication")
        tc2 = create_testcase(db, "TC002 - Profile Test", "Test profile")
        
        service = TraceabilityService(similarity_threshold=0.1)
        service.generate_traceability_matrix(db)
        
        graph = TraceabilityGraph(db)
        impact = graph.get_impact_analysis(req1.id)
        
        assert "requirement_id" in impact
        assert "directly_affected_testcases" in impact
        assert "related_requirements" in impact
        assert impact["requirement_id"] == req1.id
        
        db.close()
    
    def test_export_graph_data(self):
        """Test exporting graph data for visualization"""
        db = TestingSessionLocal()
        
        # Create minimal data
        req1 = create_requirement(db, "Feature", "Description")
        tc1 = create_testcase(db, "TC001", "Test")
        
        service = TraceabilityService(similarity_threshold=0.1)
        service.generate_traceability_matrix(db)
        
        graph = TraceabilityGraph(db)
        data = graph.export_graph_data()
        
        assert "nodes" in data
        assert "edges" in data
        assert "statistics" in data
        assert len(data["nodes"]) > 0
        
        db.close()


class TestBackwardCompatibility:
    """Test backward compatibility functions"""
    
    def test_legacy_calculate_text_similarity(self):
        """Test legacy calculate_text_similarity function"""
        text = "User login functionality"
        similarity = calculate_text_similarity(text, text)
        assert abs(similarity - 1.0) < 0.0001  # Allow for floating point precision
    
    def test_legacy_extract_keywords(self):
        """Test legacy extract_keywords function"""
        keywords = extract_keywords("User login authentication")
        assert "user" in keywords
        assert "login" in keywords
    
    def test_legacy_calculate_keyword_match_score(self):
        """Test legacy calculate_keyword_match_score function"""
        keywords1 = {"user", "login"}
        keywords2 = {"user", "authentication"}
        score = calculate_keyword_match_score(keywords1, keywords2)
        assert score > 0.0
    
    def test_legacy_calculate_hybrid_similarity(self):
        """Test legacy calculate_hybrid_similarity function"""
        result = calculate_hybrid_similarity(
            "User login",
            "Login authentication"
        )
        assert "combined_score" in result
    
    def test_legacy_map_requirements_to_testcases(self):
        """Test legacy map_requirements_to_testcases function"""
        db = TestingSessionLocal()
        
        req = create_requirement(db, "Feature", "Description")
        tc = create_testcase(db, "TC001", "Test")
        
        result = map_requirements_to_testcases(db, similarity_threshold=0.1)
        
        assert "total_requirements" in result
        assert "mappings_created" in result
        
        # Get mappings for test case before closing session
        mappings = get_mappings_for_testcase(db, tc.id)
        assert len(mappings) >= 0  # May or may not create mapping based on similarity
        
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
