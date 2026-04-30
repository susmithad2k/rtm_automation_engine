from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Dict, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from app.models.db_models import Requirement, TestCaseModel, Mapping
from app.db.crud import get_requirements, get_testcases


def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two texts using TF-IDF and cosine similarity
    
    Args:
        text1: First text to compare
        text2: Second text to compare
        
    Returns:
        Similarity score between 0 and 1
    """
    if not text1 or not text2:
        return 0.0
    
    # Create TF-IDF vectorizer
    vectorizer = TfidfVectorizer(stop_words='english', lowercase=True)
    
    try:
        # Fit and transform both texts
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        
        # Calculate cosine similarity
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        
        return float(similarity)
    except:
        # If vectorization fails (e.g., empty vocabulary), return 0
        return 0.0


def combine_text_fields(title: str, description: str = None) -> str:
    """
    Combine title and description into a single text for comparison
    
    Args:
        title: Title or name of the entity
        description: Description or steps (optional)
        
    Returns:
        Combined text
    """
    if description:
        return f"{title} {description}"
    return title


def create_mapping(db: Session, requirement_id: int, testcase_id: int) -> Mapping:
    """
    Create a mapping between a requirement and a test case
    
    Args:
        db: Database session
        requirement_id: ID of the requirement
        testcase_id: ID of the test case
        
    Returns:
        Created or existing mapping
    """
    # Check if mapping already exists
    existing = db.query(Mapping).filter(
        Mapping.requirement_id == requirement_id,
        Mapping.testcase_id == testcase_id
    ).first()
    
    if existing:
        return existing
    
    # Create new mapping
    try:
        mapping = Mapping(requirement_id=requirement_id, testcase_id=testcase_id)
        db.add(mapping)
        db.commit()
        db.refresh(mapping)
        return mapping
    except IntegrityError:
        # Handle race condition
        db.rollback()
        existing = db.query(Mapping).filter(
            Mapping.requirement_id == requirement_id,
            Mapping.testcase_id == testcase_id
        ).first()
        return existing


def map_requirements_to_testcases(
    db: Session,
    similarity_threshold: float = 0.3,
    max_mappings_per_requirement: int = 5
) -> Dict[str, any]:
    """
    Map requirements to test cases based on text similarity
    
    Args:
        db: Database session
        similarity_threshold: Minimum similarity score to create a mapping (0.0 to 1.0)
        max_mappings_per_requirement: Maximum number of test cases to map per requirement
        
    Returns:
        Dictionary with mapping statistics
    """
    # Fetch all requirements and test cases
    requirements = get_requirements(db, skip=0, limit=10000)
    testcases = get_testcases(db, skip=0, limit=10000)
    
    if not requirements or not testcases:
        return {
            "total_requirements": len(requirements) if requirements else 0,
            "total_testcases": len(testcases) if testcases else 0,
            "mappings_created": 0,
            "message": "No requirements or test cases found"
        }
    
    mappings_created = 0
    mappings_skipped = 0
    
    # Iterate through each requirement
    for requirement in requirements:
        # Combine requirement text fields
        req_text = combine_text_fields(requirement.title, requirement.description)
        
        # Calculate similarity with each test case
        similarities: List[Tuple[int, float]] = []
        
        for testcase in testcases:
            # Combine test case text fields
            tc_text = combine_text_fields(testcase.name, testcase.steps)
            
            # Calculate similarity
            similarity_score = calculate_text_similarity(req_text, tc_text)
            
            if similarity_score >= similarity_threshold:
                similarities.append((testcase.id, similarity_score))
        
        # Sort by similarity score (descending) and take top N
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_matches = similarities[:max_mappings_per_requirement]
        
        # Create mappings for top matches
        for testcase_id, score in top_matches:
            try:
                create_mapping(db, requirement.id, testcase_id)
                mappings_created += 1
            except Exception as e:
                mappings_skipped += 1
                print(f"Failed to create mapping: {str(e)}")
    
    return {
        "total_requirements": len(requirements),
        "total_testcases": len(testcases),
        "mappings_created": mappings_created,
        "mappings_skipped": mappings_skipped,
        "similarity_threshold": similarity_threshold,
        "message": f"Successfully created {mappings_created} mappings"
    }


def get_mappings_for_requirement(db: Session, requirement_id: int) -> List[Mapping]:
    """
    Get all mappings for a specific requirement
    
    Args:
        db: Database session
        requirement_id: ID of the requirement
        
    Returns:
        List of mappings
    """
    return db.query(Mapping).filter(Mapping.requirement_id == requirement_id).all()


def get_mappings_for_testcase(db: Session, testcase_id: int) -> List[Mapping]:
    """
    Get all mappings for a specific test case
    
    Args:
        db: Database session
        testcase_id: ID of the test case
        
    Returns:
        List of mappings
    """
    return db.query(Mapping).filter(Mapping.testcase_id == testcase_id).all()
