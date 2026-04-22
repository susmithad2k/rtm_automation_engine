from fastapi import FastAPI
from app.db.database import Base, engine

app = FastAPI(title="RTM Automation Engine")


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"message": "RTM Automation Engine API"}
