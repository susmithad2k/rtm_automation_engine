from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/rtm_db")

# Create engine with connection pooling for better performance
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,  # Number of permanent connections
    max_overflow=20,  # Number of additional connections when pool is full
    pool_pre_ping=True,  # Verify connections before using them
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False  # Set to True for SQL debugging
)

# Enable query result caching for read-heavy workloads
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Keep objects usable after commit
)

Base = declarative_base()


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

