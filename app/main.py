import uuid
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from app.db.database import Base, engine
from app.routes import ingest_routes, trace_routes, impact_routes, report_routes
from app.utils.logger import configure_root_logger, get_logger, set_correlation_id, clear_context

# Configure logging at application startup
configure_root_logger()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create database tables
    logger.info("Application startup: Initializing database")
    Base.metadata.create_all(bind=engine)
    logger.info("Application startup complete")
    yield
    # Shutdown: Clean up resources if needed
    logger.info("Application shutdown")


app = FastAPI(title="RTM Automation Engine", lifespan=lifespan)


# Request logging middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Middleware to log all HTTP requests with correlation ID tracking."""
    # Set correlation ID from header or generate new one
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    set_correlation_id(correlation_id)
    
    # Log request
    logger.info(f"Request started: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        
        # Log response
        logger.info(
            f"Request completed: {request.method} {request.url.path} - "
            f"Status: {response.status_code}"
        )
        
        # Add correlation ID to response headers for client tracking
        response.headers["X-Correlation-ID"] = correlation_id
        
        return response
    except Exception as e:
        logger.error(
            f"Request failed: {request.method} {request.url.path} - "
            f"Error: {str(e)}",
            exc_info=True
        )
        raise
    finally:
        # Clear context after request
        clear_context()

# Include routers
app.include_router(ingest_routes.router)
app.include_router(trace_routes.router)
app.include_router(impact_routes.router)
app.include_router(report_routes.router)


@app.get("/")
def root():
    return {"message": "RTM Automation Engine API"}
