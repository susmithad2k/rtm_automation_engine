"""
Comprehensive API tests for impact analysis endpoints.

This module tests the impact analysis API with various input combinations,
edge cases, and error conditions.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.models.db_models import Base
from app.db.database import get_db
from app.db import crud


# Test database setup - Use file-based SQLite for better session sharing
TEST_DATABASE_URL = "sqlite:///./test_impact_api.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Create and tear down test database for each test"""
    # Create tables
    Base.metadata.create_all(bind=engine)
    yield
    # Drop tables
    Base.metadata.drop_all(bind=engine)
    # Close all connections
    engine.dispose()
    # Delete the test database file with retry
    import os
    import time
    max_retries = 3
    for i in range(max_retries):
        try:
            if os.path.exists("./test_impact_api.db"):
                os.remove("./test_impact_api.db")
            break
        except PermissionError:
            if i < max_retries - 1:
                time.sleep(0.1)
            # If still fails on last retry, just pass
            pass


@pytest.fixture
def sample_data():
    """Create comprehensive sample data for testing"""
    db = TestingSessionLocal()
    
    # Create diverse requirements
    req1 = crud.create_requirement(db, "REQ-001: User Authentication", "Core authentication system")
    req2 = crud.create_requirement(db, "REQ-002: Password Security", "Password validation and reset")
    req3 = crud.create_requirement(db, "REQ-003: Session Management", "User session handling")
    req4 = crud.create_requirement(db, "REQ-004: Account Lockout", "Security lockout mechanism")
    req5 = crud.create_requirement(db, "REQ-005: Isolated Feature", "Feature with no test coverage")
    
    # Create diverse test cases
    tc1 = crud.create_testcase(db, "TC-001: Login Test", "Test valid login flow")
    tc2 = crud.create_testcase(db, "TC-002: Logout Test", "Test logout functionality")
    tc3 = crud.create_testcase(db, "TC-003: Password Change", "Test password change")
    tc4 = crud.create_testcase(db, "TC-004: Failed Login", "Test failed login attempts")
    tc5 = crud.create_testcase(db, "TC-005: Session Timeout", "Test session expiration")
    tc6 = crud.create_testcase(db, "TC-006: Account Lock", "Test account lockout")
    tc7 = crud.create_testcase(db, "TC-007: Unlock Account", "Test account unlock")
    
    # Store IDs before closing the session
    req_data = [
        {'id': req1.id, 'title': req1.title},
        {'id': req2.id, 'title': req2.title},
        {'id': req3.id, 'title': req3.title},
        {'id': req4.id, 'title': req4.title},
        {'id': req5.id, 'title': req5.title}
    ]
    
    tc_data = [
        {'id': tc1.id, 'name': tc1.name},
        {'id': tc2.id, 'name': tc2.name},
        {'id': tc3.id, 'name': tc3.name},
        {'id': tc4.id, 'name': tc4.name},
        {'id': tc5.id, 'name': tc5.name},
        {'id': tc6.id, 'name': tc6.name},
        {'id': tc7.id, 'name': tc7.name}
    ]
    
    # Create complex mapping structure
    # REQ-001 (Auth) -> TC-001, TC-002, TC-004 (3 test cases)
    crud.create_mapping(db, req1.id, tc1.id)
    crud.create_mapping(db, req1.id, tc2.id)
    crud.create_mapping(db, req1.id, tc4.id)
    
    # REQ-002 (Password) -> TC-003, TC-004 (2 test cases, shares TC-004)
    crud.create_mapping(db, req2.id, tc3.id)
    crud.create_mapping(db, req2.id, tc4.id)
    
    # REQ-003 (Session) -> TC-002, TC-005 (2 test cases, shares TC-002)
    crud.create_mapping(db, req3.id, tc2.id)
    crud.create_mapping(db, req3.id, tc5.id)
    
    # REQ-004 (Lockout) -> TC-004, TC-006, TC-007 (3 test cases, shares TC-004)
    crud.create_mapping(db, req4.id, tc4.id)
    crud.create_mapping(db, req4.id, tc6.id)
    crud.create_mapping(db, req4.id, tc7.id)
    
    # REQ-005 has no mappings (isolated requirement)
    
    db.close()
    
    return {
        'requirements': req_data,
        'testcases': tc_data
    }


class TestImpactAPIEndpoints:
    """Test the /api/impact endpoints with various inputs"""
    
    def test_get_impacted_nodes_basic(self, sample_data):
        """Test basic /api/impact/impact endpoint"""
        req1 = sample_data['requirements'][0]
        
        response = client.get(f"/api/impact/impact?requirement_id={req1['id']}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['requirement_id'] == req1['id']
        assert data['requirement_title'] == req1['title']
        assert 'impacted_nodes' in data
        assert 'test_cases' in data['impacted_nodes']
        assert 'requirements' in data['impacted_nodes']
        assert data['impacted_nodes']['total_test_cases'] == 3  # TC-001, TC-002, TC-004
    
    def test_analyze_requirement_impact_with_defaults(self, sample_data):
        """Test /api/impact/{id} with default parameters"""
        req1 = sample_data['requirements'][0]
        
        response = client.get(f"/api/impact/{req1['id']}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'source_requirement' in data
        assert data['source_requirement']['id'] == req1['id']
        assert 'impacted_testcases' in data
        assert 'impacted_requirements' in data
        assert 'impact_summary' in data
        assert 'risk_assessment' in data
    
    def test_analyze_impact_depth_variations(self, sample_data):
        """Test impact analysis with different max_depth values"""
        req1 = sample_data['requirements'][0]
        
        # Test depth=1 (only direct impacts)
        response1 = client.get(f"/api/impact/{req1['id']}?max_depth=1")
        assert response1.status_code == 200
        data1 = response1.json()
        direct_only = data1['total_impacted_nodes']
        
        # Test depth=2 (direct + related requirements + indirect TCs)
        response2 = client.get(f"/api/impact/{req1['id']}?max_depth=2")
        assert response2.status_code == 200
        data2 = response2.json()
        with_indirect = data2['total_impacted_nodes']
        
        # Test depth=3 (includes cascading impacts)
        response3 = client.get(f"/api/impact/{req1['id']}?max_depth=3")
        assert response3.status_code == 200
        data3 = response3.json()
        with_cascading = data3['total_impacted_nodes']
        
        # Deeper depth should find equal or more impacts
        assert with_indirect >= direct_only
        assert with_cascading >= with_indirect
        
        # Verify depth=1 only has direct test cases
        assert all(
            tc['impact_type'] == 'direct' 
            for tc in data1['impacted_testcases']
        )
    
    def test_analyze_impact_without_risk(self, sample_data):
        """Test impact analysis with risk assessment disabled"""
        req1 = sample_data['requirements'][0]
        
        response = client.get(f"/api/impact/{req1['id']}?include_risk=false")
        
        assert response.status_code == 200
        data = response.json()
        
        # Risk assessment should be present but empty
        assert 'risk_assessment' in data
        assert data['risk_assessment'] == {}
    
    def test_analyze_impact_with_risk(self, sample_data):
        """Test impact analysis with risk assessment enabled"""
        req1 = sample_data['requirements'][0]
        
        response = client.get(f"/api/impact/{req1['id']}?include_risk=true")
        
        assert response.status_code == 200
        data = response.json()
        
        # Risk assessment should have required fields
        assert 'risk_assessment' in data
        risk = data['risk_assessment']
        assert 'risk_score' in risk
        assert 'risk_category' in risk
        assert 'recommended_actions' in risk
        assert 0 <= risk['risk_score'] <= 100
        assert risk['risk_category'] in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        assert isinstance(risk['recommended_actions'], list)
    
    def test_analyze_impact_max_depth_boundaries(self, sample_data):
        """Test max_depth boundary values"""
        req1 = sample_data['requirements'][0]
        
        # Test minimum depth (1)
        response1 = client.get(f"/api/impact/{req1['id']}?max_depth=1")
        assert response1.status_code == 200
        
        # Test maximum depth (5)
        response5 = client.get(f"/api/impact/{req1['id']}?max_depth=5")
        assert response5.status_code == 200
        
        # Test below minimum (should fail validation)
        response0 = client.get(f"/api/impact/{req1['id']}?max_depth=0")
        assert response0.status_code == 422  # Validation error
        
        # Test above maximum (should fail validation)
        response6 = client.get(f"/api/impact/{req1['id']}?max_depth=6")
        assert response6.status_code == 422  # Validation error
    
    def test_analyze_isolated_requirement(self, sample_data):
        """Test requirement with no test case mappings"""
        req5 = sample_data['requirements'][4]  # Isolated requirement
        
        response = client.get(f"/api/impact/{req5['id']}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have zero impacts
        assert data['total_impacted_nodes'] == 0
        assert len(data['impacted_testcases']) == 0
        assert len(data['impacted_requirements']) == 0
        
        # Risk should be low
        assert data['risk_assessment']['risk_category'] == 'LOW'
    
    def test_analyze_high_impact_requirement(self, sample_data):
        """Test requirement with many shared test cases"""
        req1 = sample_data['requirements'][0]  # Has 3 test cases, shares with others
        
        response = client.get(f"/api/impact/{req1['id']}?max_depth=3")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have multiple impacts
        assert data['total_impacted_nodes'] > 3
        
        # Should include related requirements
        assert len(data['impacted_requirements']) > 0
        
        # Risk should be medium or higher
        assert data['risk_assessment']['risk_category'] in ['MEDIUM', 'HIGH', 'CRITICAL']
    
    def test_invalid_requirement_id(self):
        """Test with non-existent requirement ID"""
        response = client.get("/api/impact/99999")
        
        assert response.status_code == 404
        assert 'detail' in response.json()
    
    def test_negative_requirement_id(self):
        """Test with negative requirement ID"""
        response = client.get("/api/impact/-1")
        
        assert response.status_code == 404
    
    def test_bulk_impact_analysis(self, sample_data):
        """Test bulk impact analysis endpoint"""
        req_ids = [req['id'] for req in sample_data['requirements'][:3]]
        
        response = client.post(
            "/api/impact/bulk",
            params={"max_depth": 2},
            json=req_ids
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have results key and total_analyzed
        assert 'results' in data
        assert 'total_analyzed' in data
        assert data['total_analyzed'] == 3
        
        # Check results contain all requirement IDs
        for req_id in req_ids:
            assert str(req_id) in data['results']
    
    def test_bulk_impact_empty_list(self):
        """Test bulk analysis with empty requirement list"""
        response = client.post(
            "/api/impact/bulk",
            params={"max_depth": 2},
            json=[]
        )
        
        assert response.status_code == 400
        assert 'cannot be empty' in response.json()['detail']
    
    def test_bulk_impact_too_many_requirements(self, sample_data):
        """Test bulk analysis with too many requirements"""
        # Create list of 51 requirement IDs (over the limit of 50)
        req_ids = list(range(1, 52))
        
        response = client.post(
            "/api/impact/bulk",
            params={"max_depth": 2},
            json=req_ids
        )
        
        assert response.status_code == 400
        assert '50' in response.json()['detail']


class TestImpactAnalysisVariations:
    """Test impact analysis with different graph structures"""
    
    def test_linear_dependency_chain(self):
        """Test linear dependency: REQ1 -> TC1 -> REQ2 -> TC2"""
        db = TestingSessionLocal()
        
        req1 = crud.create_requirement(db, "REQ-A", "First requirement")
        req2 = crud.create_requirement(db, "REQ-B", "Second requirement")
        tc1 = crud.create_testcase(db, "TC-A", "First test")
        tc2 = crud.create_testcase(db, "TC-B", "Second test")
        
        req1_id = req1.id
        req2_id = req2.id
        tc2_id = tc2.id
        
        crud.create_mapping(db, req1.id, tc1.id)
        crud.create_mapping(db, req2.id, tc1.id)
        crud.create_mapping(db, req2.id, tc2.id)
        
        db.close()
        
        response = client.get(f"/api/impact/{req1_id}?max_depth=3")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should detect REQ2 as related (shares TC1)
        req_ids = [req['id'] for req in data['impacted_requirements']]
        assert req2_id in req_ids
        
        # Should detect TC2 as indirect impact
        tc_ids = [tc['id'] for tc in data['impacted_testcases']]
        assert tc2_id in tc_ids
    
    def test_star_topology(self):
        """Test star topology: Multiple REQs all map to one TC"""
        db = TestingSessionLocal()
        
        tc_central = crud.create_testcase(db, "TC-Central", "Shared test")
        reqs = [
            crud.create_requirement(db, f"REQ-{i}", f"Requirement {i}")
            for i in range(5)
        ]
        
        req0_id = reqs[0].id
        
        # All requirements map to the same test case
        for req in reqs:
            crud.create_mapping(db, req.id, tc_central.id)
        
        db.close()
        
        response = client.get(f"/api/impact/{req0_id}?max_depth=2")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should detect all other requirements as related
        assert len(data['impacted_requirements']) == 4  # Other 4 requirements
        
        # Test case should show high shared dependencies
        tc_data = data['impacted_testcases'][0]
        assert tc_data['shared_dependencies'] == 5
    
    def test_fully_connected_graph(self):
        """Test fully connected: All REQs share all TCs"""
        db = TestingSessionLocal()
        
        reqs = [
            crud.create_requirement(db, f"REQ-{i}", f"Requirement {i}")
            for i in range(3)
        ]
        tcs = [
            crud.create_testcase(db, f"TC-{i}", f"Test {i}")
            for i in range(3)
        ]
        
        req0_id = reqs[0].id
        
        # Create full mesh of mappings
        for req in reqs:
            for tc in tcs:
                crud.create_mapping(db, req.id, tc.id)
        
        db.close()
        
        response = client.get(f"/api/impact/{req0_id}?max_depth=3")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should detect all other requirements
        assert len(data['impacted_requirements']) == 2
        
        # Risk should be high due to extensive connectivity
        assert data['risk_assessment']['risk_category'] in ['HIGH', 'CRITICAL']


class TestImpactAnalysisDetailedOutput:
    """Test detailed structure of impact analysis output"""
    
    def test_testcase_output_structure(self, sample_data):
        """Test that test case output has all required fields"""
        req1 = sample_data['requirements'][0]
        
        response = client.get(f"/api/impact/{req1['id']}?max_depth=3")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify test case structure
        for tc in data['impacted_testcases']:
            assert 'id' in tc
            assert 'name' in tc
            assert 'impact_type' in tc
            assert 'impact_level' in tc
            assert 'distance' in tc
            assert 'path_count' in tc
            assert 'shared_dependencies' in tc
            assert 'metadata' in tc
            
            # Validate enum values
            assert tc['impact_type'] in ['direct', 'indirect', 'cascading', 'bidirectional']
            assert tc['impact_level'] in ['critical', 'high', 'medium', 'low']
            
            # Validate numeric ranges
            assert tc['distance'] >= 1
            assert tc['path_count'] >= 1
            assert tc['shared_dependencies'] >= 1
    
    def test_requirement_output_structure(self, sample_data):
        """Test that requirement output has all required fields"""
        req1 = sample_data['requirements'][0]
        
        response = client.get(f"/api/impact/{req1['id']}?max_depth=3")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify requirement structure
        for req in data['impacted_requirements']:
            assert 'id' in req
            assert 'title' in req
            assert 'impact_type' in req
            assert 'impact_level' in req
            assert 'distance' in req
            assert 'shared_dependencies' in req
            assert 'metadata' in req
    
    def test_impact_summary_structure(self, sample_data):
        """Test impact summary has all expected statistics"""
        req1 = sample_data['requirements'][0]
        
        response = client.get(f"/api/impact/{req1['id']}?max_depth=3")
        
        assert response.status_code == 200
        data = response.json()
        
        summary = data['impact_summary']
        
        assert 'total_impacted_testcases' in summary
        assert 'total_impacted_requirements' in summary
        assert 'testcases_by_impact_type' in summary
        assert 'testcases_by_impact_level' in summary
        assert 'requirements_by_impact_level' in summary
        assert 'max_distance' in summary
        assert 'total_impact_paths' in summary
        
        # Verify counts match
        assert summary['total_impacted_testcases'] == len(data['impacted_testcases'])
        assert summary['total_impacted_requirements'] == len(data['impacted_requirements'])
    
    def test_risk_assessment_structure(self, sample_data):
        """Test risk assessment has all expected fields"""
        req1 = sample_data['requirements'][0]
        
        response = client.get(f"/api/impact/{req1['id']}?include_risk=true")
        
        assert response.status_code == 200
        data = response.json()
        
        risk = data['risk_assessment']
        
        assert 'risk_score' in risk
        assert 'risk_category' in risk
        assert 'critical_impact_count' in risk
        assert 'high_impact_count' in risk
        assert 'critical_testcases_count' in risk
        assert 'critical_testcases' in risk
        assert 'recommended_actions' in risk
        
        # Verify risk score is reasonable
        assert isinstance(risk['risk_score'], (int, float))
        assert 0 <= risk['risk_score'] <= 100
        
        # Verify recommendations exist
        assert len(risk['recommended_actions']) > 0


class TestImpactAPIPerformance:
    """Test API performance with various data sizes"""
    
    def test_performance_with_large_dataset(self):
        """Test impact analysis with larger dataset"""
        db = TestingSessionLocal()
        
        # Create 20 requirements and 30 test cases
        reqs = [
            crud.create_requirement(db, f"REQ-{i:03d}", f"Requirement {i}")
            for i in range(20)
        ]
        tcs = [
            crud.create_testcase(db, f"TC-{i:03d}", f"Test case {i}")
            for i in range(30)
        ]
        
        req0_id = reqs[0].id
        
        # Create random mappings (average 3 TCs per REQ)
        import random
        random.seed(42)
        for req in reqs:
            selected_tcs = random.sample(tcs, k=random.randint(2, 5))
            for tc in selected_tcs:
                crud.create_mapping(db, req.id, tc.id)
        
        db.close()
        
        # Test should complete in reasonable time
        response = client.get(f"/api/impact/{req0_id}?max_depth=3")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have detected some impacts
        assert data['total_impacted_nodes'] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
