from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db.database import Base, engine
from app.routes import ingest_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create database tables
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown: Clean up resources if needed


app = FastAPI(title="RTM Automation Engine", lifespan=lifespan)

# Include routers
app.include_router(ingest_routes.router)


@app.get("/")
def root():
    return {"message": "RTM Automation Engine API"}
