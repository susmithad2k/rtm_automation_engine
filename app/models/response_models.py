from pydantic import BaseModel
from typing import List


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
