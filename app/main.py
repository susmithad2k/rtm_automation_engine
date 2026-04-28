from fastapi import FastAPI
from app.db.database import Base, engine
from app.routes import ingest_routes

app = FastAPI(title="RTM Automation Engine")

# Include routers
app.include_router(ingest_routes.router)


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"message": "RTM Automation Engine API"}
