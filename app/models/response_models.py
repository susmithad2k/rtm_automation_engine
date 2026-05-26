from pydantic import BaseModel
from typing import List, Optional


class IngestionResponse(BaseModel):
    """Response model for ingestion operations"""
    total_fetched: int
    ingested: int
    failed: int
    message: str


class MappingItem(BaseModel):
    """Response model for a single mapping"""
    id: int
    requirement_id: int
    testcase_id: int
    
    class Config:
        from_attributes = True


class TraceResponse(BaseModel):
    """Response model for trace/mapping operations"""
    total: int
    mappings: List[MappingItem]


class UncoveredRequirement(BaseModel):
    """Model for an uncovered requirement"""
    id: int
    title: str
    description: Optional[str] = None


class CombinedMetricsResponse(BaseModel):
    """Combined coverage and risk metrics in a single response"""
    # Coverage metrics
    total_requirements: int
    covered_requirements: int
    uncovered_requirements: int
    coverage_percentage: float
    total_testcases: int
    total_mappings: int
    
    # Risk metrics
    risk_score: float
    risk_level: str
    risk_summary: str
    
    # Combined data
    uncovered_requirement_list: List[UncoveredRequirement]
    recently_changed_count: int
    
    # Metadata
    timestamp: str
