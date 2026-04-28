from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.request_models import (
    JiraIngestRequest,
    ConfluenceIngestRequest,
    TestCasesIngestRequest
)
from app.models.response_models import IngestionResponse
from app.services.ingestion_service import (
    ingest_jira_data,
    ingest_confluence_data,
    ingest_testcases_data
)

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/jira", response_model=IngestionResponse)
def ingest_jira(
    request: JiraIngestRequest,
    db: Session = Depends(get_db)
):
    """
    Ingest Jira issues as requirements
    
    Args:
        request: Jira ingestion parameters
        db: Database session
        
    Returns:
        Ingestion statistics
    """
    try:
        result = ingest_jira_data(
            db=db,
            jira_url=request.jira_url,
            username=request.username,
            api_token=request.api_token,
            jql=request.jql
        )
        
        return IngestionResponse(
            total_fetched=result["total_fetched"],
            ingested=result["ingested"],
            failed=result["failed"],
            message=f"Successfully ingested {result['ingested']} Jira issues"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confluence", response_model=IngestionResponse)
def ingest_confluence(
    request: ConfluenceIngestRequest,
    db: Session = Depends(get_db)
):
    """
    Ingest Confluence pages as requirements
    
    Args:
        request: Confluence ingestion parameters
        db: Database session
        
    Returns:
        Ingestion statistics
    """
    try:
        result = ingest_confluence_data(
            db=db,
            confluence_url=request.confluence_url,
            username=request.username,
            api_token=request.api_token,
            space_key=request.space_key
        )
        
        return IngestionResponse(
            total_fetched=result["total_fetched"],
            ingested=result["ingested"],
            failed=result["failed"],
            message=f"Successfully ingested {result['ingested']} Confluence pages"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/testcases", response_model=IngestionResponse)
def ingest_testcases(
    request: TestCasesIngestRequest,
    db: Session = Depends(get_db)
):
    """
    Ingest test cases from CSV file
    
    Args:
        request: Test cases ingestion parameters
        db: Database session
        
    Returns:
        Ingestion statistics
    """
    try:
        result = ingest_testcases_data(
            db=db,
            file_path=request.file_path
        )
        
        return IngestionResponse(
            total_fetched=result["total_fetched"],
            ingested=result["ingested"],
            failed=result["failed"],
            message=f"Successfully ingested {result['ingested']} test cases"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
