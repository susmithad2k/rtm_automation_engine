from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.crud import get_mappings
from app.models.response_models import TraceResponse, MappingItem

router = APIRouter(prefix="/trace", tags=["trace"])


@router.get("", response_model=TraceResponse)
def get_trace_mappings(
    skip: int = 0,
    limit: int = 100,
    requirement_id: int = None,
    testcase_id: int = None,
    db: Session = Depends(get_db)
):
    """
    Get requirement-to-testcase mappings (traceability matrix) with optional filtering
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        requirement_id: Optional filter by requirement ID
        testcase_id: Optional filter by test case ID
        db: Database session
        
    Returns:
        TraceResponse containing filtered mappings
    """
    try:
        mappings = get_mappings(db, skip=skip, limit=limit, requirement_id=requirement_id, testcase_id=testcase_id)
        
        mapping_items = [
            MappingItem(
                id=mapping.id,
                requirement_id=mapping.requirement_id,
                testcase_id=mapping.testcase_id
            )
            for mapping in mappings
        ]
        
        return TraceResponse(
            total=len(mapping_items),
            mappings=mapping_items
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
