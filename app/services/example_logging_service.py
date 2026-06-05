"""
Example service demonstrating improved logging features.

This file shows how to use the enhanced logging capabilities:
- Basic logging
- Execution timing
- Function call logging
- Context tracking
- Error logging
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.utils.logger import (
    get_logger,
    log_execution_time,
    log_function_call,
    set_user_id,
)
from app.models.db_models import Requirement

# Get logger instance for this module
logger = get_logger(__name__)


class ExampleService:
    """Example service demonstrating logging best practices."""
    
    def __init__(self, db: Session):
        """Initialize the example service."""
        self.db = db
        logger.debug("ExampleService initialized")
    
    @log_function_call(logger)
    def process_with_auto_logging(self, item_id: int) -> Dict[str, Any]:
        """
        Example method with automatic function call logging.
        
        The decorator logs:
        - Function entry with arguments
        - Execution time
        - Exceptions if any occur
        """
        logger.info(f"Processing item {item_id}")
        
        # Simulate processing
        result = {
            "item_id": item_id,
            "status": "processed",
            "timestamp": "2026-06-05T10:30:00"
        }
        
        return result
    
    def process_with_timing(self, req_id: int) -> Requirement:
        """Example method with execution time logging."""
        # Log execution time for specific operations
        with log_execution_time(logger, f"fetch requirement {req_id}"):
            requirement = self.db.query(Requirement).filter(
                Requirement.id == req_id
            ).first()
        
        if not requirement:
            logger.warning(f"Requirement {req_id} not found")
            return None
        
        logger.info(f"Successfully fetched requirement: {requirement.title}")
        return requirement
    
    def process_batch_with_context(
        self, 
        requirement_ids: List[int], 
        user_id: str
    ) -> Dict[str, Any]:
        """
        Example method demonstrating context tracking.
        
        The user_id is automatically added to all log entries within this method.
        """
        # Set user context for all subsequent log entries
        set_user_id(user_id)
        
        logger.info(f"Starting batch processing for {len(requirement_ids)} requirements")
        
        results = {
            "processed": [],
            "failed": [],
            "total": len(requirement_ids)
        }
        
        for req_id in requirement_ids:
            try:
                with log_execution_time(logger, f"process requirement {req_id}"):
                    # Simulate processing
                    requirement = self.process_with_timing(req_id)
                    
                    if requirement:
                        results["processed"].append(req_id)
                        logger.debug(f"Requirement {req_id} processed successfully")
                    else:
                        results["failed"].append(req_id)
                        logger.warning(f"Requirement {req_id} not found")
                        
            except Exception as e:
                results["failed"].append(req_id)
                # Log exception with full stack trace
                logger.error(
                    f"Failed to process requirement {req_id}: {str(e)}",
                    exc_info=True
                )
        
        logger.info(
            f"Batch processing completed: "
            f"{len(results['processed'])} succeeded, "
            f"{len(results['failed'])} failed"
        )
        
        return results
    
    def complex_operation_with_nested_timing(self, data: Dict[str, Any]) -> bool:
        """Example with nested timing measurements."""
        logger.info("Starting complex operation")
        
        with log_execution_time(logger, "entire operation"):
            # Step 1: Validation
            with log_execution_time(logger, "data validation"):
                if not self._validate_data(data):
                    logger.error("Data validation failed")
                    return False
            
            # Step 2: Processing
            with log_execution_time(logger, "data processing"):
                processed_data = self._process_data(data)
            
            # Step 3: Persistence
            with log_execution_time(logger, "data persistence"):
                self._save_data(processed_data)
        
        logger.info("Complex operation completed successfully")
        return True
    
    def _validate_data(self, data: Dict[str, Any]) -> bool:
        """Internal validation method."""
        required_fields = ["id", "title", "description"]
        
        for field in required_fields:
            if field not in data:
                logger.warning(f"Missing required field: {field}")
                return False
        
        logger.debug("Data validation passed")
        return True
    
    def _process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Internal processing method."""
        logger.debug(f"Processing data for item: {data.get('id')}")
        
        # Simulate processing
        processed = {
            **data,
            "processed": True,
            "processed_at": "2026-06-05T10:30:00"
        }
        
        return processed
    
    def _save_data(self, data: Dict[str, Any]) -> None:
        """Internal persistence method."""
        logger.debug(f"Saving data for item: {data.get('id')}")
        # Simulate database save
        pass
    
    def demonstrate_log_levels(self):
        """Example showing different log levels."""
        # DEBUG: Detailed diagnostic information
        logger.debug("Debug information: variable values, state details")
        
        # INFO: General informational messages
        logger.info("Operation started, normal flow events")
        
        # WARNING: Potentially harmful situations
        logger.warning("Deprecated feature used, unusual but handled condition")
        
        # ERROR: Error events that might still allow the application to continue
        logger.error("Failed to process item, but will retry")
        
        # CRITICAL: Very severe error events
        logger.critical("System is in unstable state, immediate attention required")
    
    def demonstrate_error_logging(self, req_id: int):
        """Example showing proper error logging."""
        try:
            # Simulate operation that might fail
            requirement = self.db.query(Requirement).filter(
                Requirement.id == req_id
            ).first()
            
            if not requirement:
                raise ValueError(f"Requirement {req_id} not found")
            
            # Simulate processing error
            if requirement.title == "ERROR":
                raise RuntimeError("Simulated processing error")
            
            return requirement
            
        except ValueError as e:
            # Log specific errors with appropriate level
            logger.warning(f"Requirement not found: {e}")
            return None
            
        except RuntimeError as e:
            # Log serious errors with full stack trace
            logger.error(f"Processing error: {e}", exc_info=True)
            raise
            
        except Exception as e:
            # Catch-all for unexpected errors
            logger.exception(f"Unexpected error processing requirement {req_id}")
            raise
    
    def demonstrate_structured_logging(self, req_id: int, user_id: str):
        """
        Example of structured logging with extra fields.
        
        When LOG_FORMAT=json, these extra fields become top-level JSON keys.
        """
        # Set context that applies to all subsequent logs
        set_user_id(user_id)
        
        # Log with extra structured data
        logger.info(
            f"Analyzing requirement {req_id}",
            extra={
                "requirement_id": req_id,
                "analysis_type": "impact",
                "depth": 3,
            }
        )
        
        # This will include both correlation_id (from middleware) 
        # and user_id in the log output


# Example usage in a route handler:
"""
from app.services.example_logging_service import ExampleService
from app.utils.logger import set_correlation_id, clear_context
import uuid

@router.post("/example")
async def example_endpoint(
    req_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    # Correlation ID is set by middleware, but you can also set it manually
    # set_correlation_id(str(uuid.uuid4()))
    
    service = ExampleService(db)
    
    # All logs will include correlation_id and user_id
    result = service.process_batch_with_context([req_id], user_id)
    
    return result
"""
