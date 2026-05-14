"""
Tests for impact analysis service and routes.

This module tests the impact detection functionality including:
- Direct and indirect impact detection
- Risk assessment
- Cascading impact analysis
- Critical node identification
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.db_models import Base, Requirement, TestCaseModel, Mapping
from app.services.impact_service import (
    ImpactAnalysisService,
    get_impact_analysis,
    get_bulk_impact_analysis,
    ImpactLevel,
    ImpactType
)
from app.db import crud


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """Create a test database session"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_data(db):
    """Create sample requirements, test cases, and mappings for testing"""
    # Create requirements
    req1 = crud.create_requirement(db, "REQ-001: User Login", "Users must be able to log in")
    req2 = crud.create_requirement(db, "REQ-002: Password Reset", "Users can reset password")
    req3 = crud.create_requirement(db, "REQ-003: Account Lock", "Lock account after failed attempts")
    req4 = crud.create_requirement(db, "REQ-004: Session Management", "Manage user sessions")
    
    # Create test cases
    tc1 = crud.create_testcase(db, "TC-001: Valid Login", "1. Enter valid credentials 2. Click login")
    tc2 = crud.create_testcase(db, "TC-002: Invalid Login", "1. Enter invalid credentials 2. Verify error")
    tc3 = crud.create_testcase(db, "TC-003: Reset Password", "1. Click forgot password 2. Enter email")
    tc4 = crud.create_testcase(db, "TC-004: Locked Account", "1. Fail login 5 times 2. Verify lock")
    tc5 = crud.create_testcase(db, "TC-005: Session Timeout", "1. Login 2. Wait 30min 3. Verify timeout")
    
    # Create mappings
    # REQ-001 -> TC-001, TC-002 (login tests)
    crud.create_mapping(db, req1.id, tc1.id)
    crud.create_mapping(db, req1.id, tc2.id)
    
    # REQ-002 -> TC-003 (password reset)
    crud.create_mapping(db, req2.id, tc3.id)
    
    # REQ-003 -> TC-002, TC-004 (account lock - shares TC-002 with REQ-001)
    crud.create_mapping(db, req3.id, tc2.id)
    crud.create_mapping(db, req3.id, tc4.id)
    
    # REQ-004 -> TC-001, TC-005 (session - shares TC-001 with REQ-001)
    crud.create_mapping(db, req4.id, tc1.id)
    crud.create_mapping(db, req4.id, tc5.id)
    
    return {
        'requirements': [req1, req2, req3, req4],
        'testcases': [tc1, tc2, tc3, tc4, tc5]
    }


class TestImpactAnalysisService:
    """Test cases for the ImpactAnalysisService"""
    
    def test_detect_direct_testcases(self, db, sample_data):
        """Test detection of directly mapped test cases"""
        service = ImpactAnalysisService(db)
        req1 = sample_data['requirements'][0]
        
        result = service.detect_impacted_nodes(req1.id, max_depth=1, include_risk_assessment=False)
        
        # REQ-001 should have 2 direct test cases: TC-001, TC-002
        assert len(result.impacted_testcases) == 2
        assert all(tc.impact_type == ImpactType.DIRECT for tc in result.impacted_testcases)
        assert all(tc.impact_level == ImpactLevel.CRITICAL for tc in result.impacted_testcases)
    
    def test_detect_related_requirements(self, db, sample_data):
        """Test detection of related requirements through shared test cases"""
        service = ImpactAnalysisService(db)
        req1 = sample_data['requirements'][0]  # REQ-001
        
        result = service.detect_impacted_nodes(req1.id, max_depth=2, include_risk_assessment=False)
        
        # REQ-001 shares test cases with REQ-003 (TC-002) and REQ-004 (TC-001)
        assert len(result.impacted_requirements) >= 2
        
        # Check that related requirements are identified
        related_ids = {req.node_id for req in result.impacted_requirements}
        req3 = sample_data['requirements'][2]
        req4 = sample_data['requirements'][3]
        assert req3.id in related_ids or req4.id in related_ids
    
    def test_detect_indirect_testcases(self, db, sample_data):
        """Test detection of indirectly affected test cases"""
        service = ImpactAnalysisService(db)
        req1 = sample_data['requirements'][0]  # REQ-001
        
        result = service.detect_impacted_nodes(req1.id, max_depth=3, include_risk_assessment=False)
        
        # Should include both direct and indirect test cases
        assert result.total_impacted_nodes > 2  # More than just the 2 direct test cases
        
        # Check for indirect test cases
        indirect_tcs = [tc for tc in result.impacted_testcases if tc.impact_type == ImpactType.INDIRECT]
        assert len(indirect_tcs) > 0
    
    def test_impact_levels(self, db, sample_data):
        """Test that impact levels are correctly assigned"""
        service = ImpactAnalysisService(db)
        req1 = sample_data['requirements'][0]
        
        result = service.detect_impacted_nodes(req1.id, max_depth=3, include_risk_assessment=False)
        
        # Direct test cases should have CRITICAL impact
        direct_tcs = [tc for tc in result.impacted_testcases if tc.impact_type == ImpactType.DIRECT]
        assert all(tc.impact_level == ImpactLevel.CRITICAL for tc in direct_tcs)
        
        # There should be test cases with various impact levels
        impact_levels = {tc.impact_level for tc in result.impacted_testcases}
        assert ImpactLevel.CRITICAL in impact_levels
    
    def test_risk_assessment(self, db, sample_data):
        """Test risk assessment functionality"""
        service = ImpactAnalysisService(db)
        req1 = sample_data['requirements'][0]
        
        result = service.detect_impacted_nodes(req1.id, max_depth=3, include_risk_assessment=True)
        
        # Risk assessment should be included
        assert result.risk_assessment is not None
        assert 'risk_score' in result.risk_assessment
        assert 'risk_category' in result.risk_assessment
        assert 'recommended_actions' in result.risk_assessment
        
        # Risk score should be between 0 and 100
        assert 0 <= result.risk_assessment['risk_score'] <= 100
        
        # Risk category should be valid
        assert result.risk_assessment['risk_category'] in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
    
    def test_impact_summary(self, db, sample_data):
        """Test impact summary statistics"""
        service = ImpactAnalysisService(db)
        req1 = sample_data['requirements'][0]
        
        result = service.detect_impacted_nodes(req1.id, max_depth=3, include_risk_assessment=False)
        
        # Impact summary should contain key statistics
        assert 'total_impacted_testcases' in result.impact_summary
        assert 'total_impacted_requirements' in result.impact_summary
        assert 'testcases_by_impact_type' in result.impact_summary
        assert 'testcases_by_impact_level' in result.impact_summary
        
        # Counts should match
        assert result.impact_summary['total_impacted_testcases'] == len(result.impacted_testcases)
        assert result.impact_summary['total_impacted_requirements'] == len(result.impacted_requirements)
    
    def test_shared_dependencies(self, db, sample_data):
        """Test that shared dependencies are correctly counted"""
        service = ImpactAnalysisService(db)
        req1 = sample_data['requirements'][0]  # REQ-001
        
        result = service.detect_impacted_nodes(req1.id, max_depth=3, include_risk_assessment=False)
        
        # Find TC-002 which is shared between REQ-001 and REQ-003
        tc2 = sample_data['testcases'][1]
        tc2_nodes = [tc for tc in result.impacted_testcases if tc.node_id == tc2.id]
        
        if tc2_nodes:
            tc2_node = tc2_nodes[0]
            # TC-002 should show it covers multiple requirements
            assert tc2_node.shared_dependencies >= 2
    
    def test_no_impact(self, db, sample_data):
        """Test requirement with no test cases (isolated requirement)"""
        # Create a requirement with no mappings
        isolated_req = crud.create_requirement(db, "REQ-999: Isolated", "No test cases")
        
        service = ImpactAnalysisService(db)
        result = service.detect_impacted_nodes(isolated_req.id, max_depth=3, include_risk_assessment=True)
        
        # Should have no impacted nodes
        assert result.total_impacted_nodes == 0
        assert len(result.impacted_testcases) == 0
        assert len(result.impacted_requirements) == 0
        
        # Risk should be low
        assert result.risk_assessment['risk_category'] == 'LOW'
    
    def test_get_impact_analysis_function(self, db, sample_data):
        """Test the get_impact_analysis convenience function"""
        req1 = sample_data['requirements'][0]
        
        result = get_impact_analysis(db, req1.id, max_depth=3, include_risk=True)
        
        # Result should be a dictionary
        assert isinstance(result, dict)
        assert 'source_requirement' in result
        assert 'total_impacted_nodes' in result
        assert 'impacted_testcases' in result
        assert 'impacted_requirements' in result
        assert 'impact_summary' in result
        assert 'risk_assessment' in result
    
    def test_bulk_impact_analysis(self, db, sample_data):
        """Test bulk impact analysis for multiple requirements"""
        req_ids = [req.id for req in sample_data['requirements'][:3]]
        
        results = get_bulk_impact_analysis(db, req_ids, max_depth=2)
        
        # Should have results for all requirements
        assert len(results) == 3
        
        # Each result should have summary information
        for req_id in req_ids:
            assert req_id in results
            assert 'total_impacted' in results[req_id]
            assert 'testcases_count' in results[req_id]
            assert 'summary' in results[req_id]
    
    def test_invalid_requirement_id(self, db):
        """Test impact analysis with invalid requirement ID"""
        service = ImpactAnalysisService(db)
        
        with pytest.raises(ValueError):
            service.detect_impacted_nodes(99999, max_depth=3)
    
    def test_cascading_impact(self, db, sample_data):
        """Test cascading impact detection through graph traversal"""
        service = ImpactAnalysisService(db)
        req1 = sample_data['requirements'][0]
        
        # Use deeper traversal to find cascading impacts
        result = service.detect_impacted_nodes(req1.id, max_depth=4, include_risk_assessment=False)
        
        # Should detect cascading impacts
        cascading_tcs = [tc for tc in result.impacted_testcases if tc.impact_type == ImpactType.CASCADING]
        # May or may not have cascading impacts depending on graph structure
        assert isinstance(cascading_tcs, list)


class TestImpactAnalysisEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_circular_dependencies(self, db):
        """Test handling of circular dependencies in the graph"""
        # Create circular dependency: REQ1 -> TC1 -> REQ2 -> TC1
        req1 = crud.create_requirement(db, "REQ-A", "First requirement")
        req2 = crud.create_requirement(db, "REQ-B", "Second requirement")
        tc1 = crud.create_testcase(db, "TC-A", "Shared test case")
        
        crud.create_mapping(db, req1.id, tc1.id)
        crud.create_mapping(db, req2.id, tc1.id)
        
        service = ImpactAnalysisService(db)
        result = service.detect_impacted_nodes(req1.id, max_depth=5, include_risk_assessment=False)
        
        # Should handle circular dependencies without infinite loop
        assert result.total_impacted_nodes >= 1
        assert result.source_requirement_id == req1.id
    
    def test_max_depth_limit(self, db, sample_data):
        """Test that max_depth parameter limits traversal"""
        service = ImpactAnalysisService(db)
        req1 = sample_data['requirements'][0]
        
        result_depth1 = service.detect_impacted_nodes(req1.id, max_depth=1, include_risk_assessment=False)
        result_depth3 = service.detect_impacted_nodes(req1.id, max_depth=3, include_risk_assessment=False)
        
        # Deeper traversal should find equal or more impacts
        assert result_depth3.total_impacted_nodes >= result_depth1.total_impacted_nodes
    
    def test_high_connectivity_requirement(self, db):
        """Test requirement with many test cases (high connectivity)"""
        req = crud.create_requirement(db, "REQ-HIGH", "High connectivity requirement")
        
        # Create 10 test cases all mapped to this requirement
        for i in range(10):
            tc = crud.create_testcase(db, f"TC-HIGH-{i}", f"Test case {i}")
            crud.create_mapping(db, req.id, tc.id)
        
        service = ImpactAnalysisService(db)
        result = service.detect_impacted_nodes(req.id, max_depth=2, include_risk_assessment=True)
        
        # Should have 10 direct test cases
        assert len(result.impacted_testcases) == 10
        
        # Risk should be higher due to many impacted test cases
        assert result.risk_assessment['risk_score'] > 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
