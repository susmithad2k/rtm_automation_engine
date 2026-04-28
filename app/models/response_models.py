from pydantic import BaseModel


class IngestionResponse(BaseModel):
    """Response model for ingestion operations"""
    total_fetched: int
    ingested: int
    failed: int
    message: str
