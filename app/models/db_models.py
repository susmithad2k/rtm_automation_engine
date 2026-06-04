from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.db.database import Base


class Requirement(Base):
    __tablename__ = "requirements"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, unique=True)  # Make title unique to prevent duplicates
    description = Column(Text)
    
    # Relationships for eager loading
    mappings = relationship("Mapping", back_populates="requirement", lazy="select", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_requirements_title', 'title'),
    )


class TestCaseModel(Base):
    __tablename__ = "test_cases"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)  # Make name unique to prevent duplicates
    steps = Column(Text)
    
    # Relationships for eager loading
    mappings = relationship("Mapping", back_populates="testcase", lazy="select", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_test_cases_name', 'name'),
    )


class Mapping(Base):
    __tablename__ = "mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    requirement_id = Column(Integer, ForeignKey("requirements.id"), nullable=False)
    testcase_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False)
    
    # Relationships for eager loading
    requirement = relationship("Requirement", back_populates="mappings")
    testcase = relationship("TestCaseModel", back_populates="mappings")
    
    __table_args__ = (
        UniqueConstraint('requirement_id', 'testcase_id', name='uq_requirement_testcase'),
        Index('ix_mappings_requirement', 'requirement_id'),
        Index('ix_mappings_testcase', 'testcase_id'),
        # Composite index for common join patterns
        Index('ix_mappings_composite', 'requirement_id', 'testcase_id'),
    )
