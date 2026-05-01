from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Dict, Tuple, Set
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re

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


def extract_keywords(text: str, min_length: int = 3) -> Set[str]:
    """
    Extract keywords from text
    
    Args:
        text: Text to extract keywords from
        min_length: Minimum length of keywords to extract
        
    Returns:
        Set of keywords (lowercase)
    """
    if not text:
        return set()
    
    # Common stop words to exclude
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
        'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their', 'what',
        'which', 'who', 'when', 'where', 'why', 'how'
    }
    
    # Convert to lowercase and extract words
    text_lower = text.lower()
    
    # Extract alphanumeric words (including hyphenated words and numbers)
    words = re.findall(r'\b[a-z0-9]+(?:-[a-z0-9]+)*\b', text_lower)
    
    # Filter by length and stop words
    keywords = {
        word for word in words 
        if len(word) >= min_length and word not in stop_words
    }
    
    return keywords


def calculate_keyword_match_score(keywords1: Set[str], keywords2: Set[str]) -> float:
    """
    Calculate keyword match score using Jaccard similarity
    
    Args:
        keywords1: Set of keywords from first text
        keywords2: Set of keywords from second text
        
    Returns:
        Jaccard similarity score between 0 and 1
    """
    if not keywords1 or not keywords2:
        return 0.0
    
    # Calculate intersection and union
    intersection = keywords1.intersection(keywords2)
    union = keywords1.union(keywords2)
    
    if not union:
        return 0.0
    
    # Jaccard similarity
    return len(intersection) / len(union)


def calculate_hybrid_similarity(
    text1: str, 
    text2: str, 
    keyword_weight: float = 0.4,
    tfidf_weight: float = 0.6
) -> Dict[str, float]:
    """
    Calculate hybrid similarity combining keyword matching and TF-IDF
    
    Args:
        text1: First text to compare
        text2: Second text to compare
        keyword_weight: Weight for keyword matching (0.0 to 1.0)
        tfidf_weight: Weight for TF-IDF similarity (0.0 to 1.0)
        
    Returns:
        Dictionary with keyword_score, tfidf_score, and combined_score
    """
    # Extract keywords
    keywords1 = extract_keywords(text1)
    keywords2 = extract_keywords(text2)
    
    # Calculate keyword match score
    keyword_score = calculate_keyword_match_score(keywords1, keywords2)
    
    # Calculate TF-IDF similarity
    tfidf_score = calculate_text_similarity(text1, text2)
    
    # Normalize weights
    total_weight = keyword_weight + tfidf_weight
    if total_weight > 0:
        keyword_weight = keyword_weight / total_weight
        tfidf_weight = tfidf_weight / total_weight
    
    # Calculate combined score
    combined_score = (keyword_score * keyword_weight) + (tfidf_score * tfidf_weight)
    
    return {
        "keyword_score": float(keyword_score),
        "tfidf_score": float(tfidf_score),
        "combined_score": float(combined_score),
        "matched_keywords": list(keywords1.intersection(keywords2))
    }


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
    max_mappings_per_requirement: int = 5,
    use_keyword_matching: bool = True,
    keyword_weight: float = 0.4,
    tfidf_weight: float = 0.6
) -> Dict[str, any]:
    """
    Map requirements to test cases based on hybrid text similarity
    
    Args:
        db: Database session
        similarity_threshold: Minimum similarity score to create a mapping (0.0 to 1.0)
        max_mappings_per_requirement: Maximum number of test cases to map per requirement
        use_keyword_matching: Whether to use hybrid keyword + TF-IDF matching
        keyword_weight: Weight for keyword matching in hybrid score
        tfidf_weight: Weight for TF-IDF in hybrid score
        
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
        similarities: List[Tuple[int, float, Dict]] = []
        
        for testcase in testcases:
            # Combine test case text fields
            tc_text = combine_text_fields(testcase.name, testcase.steps)
            
            # Calculate similarity
            if use_keyword_matching:
                # Use hybrid similarity
                similarity_result = calculate_hybrid_similarity(
                    req_text, tc_text, keyword_weight, tfidf_weight
                )
                similarity_score = similarity_result["combined_score"]
                match_details = similarity_result
            else:
                # Use only TF-IDF
                similarity_score = calculate_text_similarity(req_text, tc_text)
                match_details = {"tfidf_score": similarity_score}
            
            if similarity_score >= similarity_threshold:
                similarities.append((testcase.id, similarity_score, match_details))
        
        # Sort by similarity score (descending) and take top N
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_matches = similarities[:max_mappings_per_requirement]
        
        # Create mappings for top matches
        for testcase_id, score, details in top_matches:
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
        "use_keyword_matching": use_keyword_matching,
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
