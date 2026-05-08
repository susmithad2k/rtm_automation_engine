"""
Traceability service for mapping requirements to test cases.

This module provides the core business logic for creating and managing
requirement-to-test-case traceability mappings based on text similarity analysis.
"""

from sqlalchemy.orm import Session
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from app.models.db_models import Requirement, TestCaseModel, Mapping
from app.db.crud import (
    get_requirements, 
    get_testcases, 
    create_mapping as crud_create_mapping,
    get_mappings_by_requirement,
    get_mappings_by_testcase
)
from app.utils.text_processing import SimilarityCalculator, combine_text_fields
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SimilarityMatch:
    """Represents a similarity match between a requirement and test case."""
    testcase_id: int
    similarity_score: float
    keyword_score: float
    tfidf_score: float
    matched_keywords: List[str]


class TraceabilityService:
    """
    Service for creating and managing requirement-to-test-case traceability mappings.
    
    This service uses text similarity analysis to automatically identify potential
    relationships between requirements and test cases.
    """
    
    def __init__(
        self,
        similarity_calculator: Optional[SimilarityCalculator] = None,
        similarity_threshold: float = 0.3,
        max_mappings_per_requirement: int = 5,
        keyword_weight: float = 0.4,
        tfidf_weight: float = 0.6
    ):
        """
        Initialize the traceability service.
        
        Args:
            similarity_calculator: Calculator for text similarity (uses default if None)
            similarity_threshold: Minimum similarity score to create a mapping (0.0 to 1.0)
            max_mappings_per_requirement: Maximum number of test cases to map per requirement
            keyword_weight: Weight for keyword matching in hybrid score
            tfidf_weight: Weight for TF-IDF in hybrid score
        """
        self.similarity_calculator = similarity_calculator or SimilarityCalculator()
        self.similarity_threshold = similarity_threshold
        self.max_mappings_per_requirement = max_mappings_per_requirement
        self.keyword_weight = keyword_weight
        self.tfidf_weight = tfidf_weight
    
    def find_similar_testcases(
        self,
        requirement: Requirement,
        testcases: List[TestCaseModel],
        use_hybrid: bool = True
    ) -> List[SimilarityMatch]:
        """
        Find test cases similar to a given requirement.
        
        Args:
            requirement: The requirement to match
            testcases: List of test cases to search
            use_hybrid: Whether to use hybrid (keyword + TF-IDF) or TF-IDF only
            
        Returns:
            List of SimilarityMatch objects, sorted by similarity score (descending)
        """
        req_text = combine_text_fields(requirement.title, requirement.description)
        matches: List[SimilarityMatch] = []
        
        for testcase in testcases:
            tc_text = combine_text_fields(testcase.name, testcase.steps)
            
            if use_hybrid:
                result = self.similarity_calculator.calculate_hybrid_similarity(
                    req_text, tc_text, 
                    self.keyword_weight, 
                    self.tfidf_weight
                )
                similarity_score = result["combined_score"]
                keyword_score = result["keyword_score"]
                tfidf_score = result["tfidf_score"]
                matched_keywords = result["matched_keywords"]
            else:
                tfidf_score = self.similarity_calculator.calculate_tfidf_similarity(
                    req_text, tc_text
                )
                similarity_score = tfidf_score
                keyword_score = 0.0
                matched_keywords = []
            
            if similarity_score >= self.similarity_threshold:
                matches.append(SimilarityMatch(
                    testcase_id=testcase.id,
                    similarity_score=similarity_score,
                    keyword_score=keyword_score,
                    tfidf_score=tfidf_score,
                    matched_keywords=matched_keywords
                ))
        
        # Sort by similarity score (descending)
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        
        return matches[:self.max_mappings_per_requirement]
    
    def create_mappings_for_requirement(
        self,
        db: Session,
        requirement: Requirement,
        testcases: List[TestCaseModel],
        use_hybrid: bool = True
    ) -> List[Mapping]:
        """
        Create mappings for a single requirement.
        
        Args:
            db: Database session
            requirement: The requirement to create mappings for
            testcases: List of test cases to match against
            use_hybrid: Whether to use hybrid similarity matching
            
        Returns:
            List of created Mapping objects
        """
        matches = self.find_similar_testcases(requirement, testcases, use_hybrid)
        created_mappings = []
        
        for match in matches:
            try:
                mapping = crud_create_mapping(db, requirement.id, match.testcase_id)
                created_mappings.append(mapping)
                logger.info(
                    f"Created mapping: Req {requirement.id} -> TC {match.testcase_id} "
                    f"(score: {match.similarity_score:.3f})"
                )
            except Exception as e:
                logger.error(f"Failed to create mapping: {str(e)}")
        
        return created_mappings
    
    def generate_traceability_matrix(
        self,
        db: Session,
        use_hybrid: bool = True
    ) -> Dict[str, any]:
        """
        Generate complete traceability matrix for all requirements and test cases.
        
        Args:
            db: Database session
            use_hybrid: Whether to use hybrid (keyword + TF-IDF) or TF-IDF only
            
        Returns:
            Dictionary with mapping statistics and results
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
        
        logger.info(
            f"Generating traceability matrix for {len(requirements)} requirements "
            f"and {len(testcases)} test cases"
        )
        
        total_mappings_created = 0
        
        # Process each requirement
        for requirement in requirements:
            mappings = self.create_mappings_for_requirement(
                db, requirement, testcases, use_hybrid
            )
            total_mappings_created += len(mappings)
        
        return {
            "total_requirements": len(requirements),
            "total_testcases": len(testcases),
            "mappings_created": total_mappings_created,
            "similarity_threshold": self.similarity_threshold,
            "use_hybrid": use_hybrid,
            "message": f"Successfully created {total_mappings_created} mappings"
        }
    
    def get_requirement_coverage(
        self,
        db: Session,
        requirement_id: int
    ) -> Dict[str, any]:
        """
        Get test case coverage for a specific requirement.
        
        Args:
            db: Database session
            requirement_id: ID of the requirement
            
        Returns:
            Dictionary with requirement coverage information
        """
        mappings = get_mappings_by_requirement(db, requirement_id)
        
        return {
            "requirement_id": requirement_id,
            "total_testcases": len(mappings),
            "testcase_ids": [m.testcase_id for m in mappings],
            "is_covered": len(mappings) > 0
        }
    
    def get_testcase_coverage(
        self,
        db: Session,
        testcase_id: int
    ) -> Dict[str, any]:
        """
        Get requirement coverage for a specific test case.
        
        Args:
            db: Database session
            testcase_id: ID of the test case
            
        Returns:
            Dictionary with test case coverage information
        """
        mappings = get_mappings_by_testcase(db, testcase_id)
        
        return {
            "testcase_id": testcase_id,
            "total_requirements": len(mappings),
            "requirement_ids": [m.requirement_id for m in mappings],
            "covers_requirements": len(mappings) > 0
        }


# Backward compatibility functions
def calculate_text_similarity(text1: str, text2: str) -> float:
    """Legacy function for backward compatibility."""
    calculator = SimilarityCalculator()
    return calculator.calculate_tfidf_similarity(text1, text2)


def extract_keywords(text: str, min_length: int = 3):
    """Legacy function for backward compatibility."""
    calculator = SimilarityCalculator(min_keyword_length=min_length)
    return calculator.extract_keywords(text)


def calculate_keyword_match_score(keywords1, keywords2) -> float:
    """Legacy function for backward compatibility."""
    calculator = SimilarityCalculator()
    return calculator.calculate_keyword_similarity(keywords1, keywords2)


def calculate_hybrid_similarity(
    text1: str,
    text2: str,
    keyword_weight: float = 0.4,
    tfidf_weight: float = 0.6
) -> Dict[str, float]:
    """Legacy function for backward compatibility."""
    calculator = SimilarityCalculator()
    return calculator.calculate_hybrid_similarity(text1, text2, keyword_weight, tfidf_weight)


def map_requirements_to_testcases(
    db: Session,
    similarity_threshold: float = 0.3,
    max_mappings_per_requirement: int = 5,
    use_keyword_matching: bool = True,
    keyword_weight: float = 0.4,
    tfidf_weight: float = 0.6
) -> Dict[str, any]:
    """Legacy function for backward compatibility."""
    service = TraceabilityService(
        similarity_threshold=similarity_threshold,
        max_mappings_per_requirement=max_mappings_per_requirement,
        keyword_weight=keyword_weight,
        tfidf_weight=tfidf_weight
    )
    result = service.generate_traceability_matrix(db, use_hybrid=use_keyword_matching)
    # Add backward compatibility keys
    result["use_keyword_matching"] = use_keyword_matching
    return result


def get_mappings_for_requirement(db: Session, requirement_id: int) -> List[Mapping]:
    """Legacy function for backward compatibility."""
    return get_mappings_by_requirement(db, requirement_id)


def get_mappings_for_testcase(db: Session, testcase_id: int) -> List[Mapping]:
    """Legacy function for backward compatibility."""
    return get_mappings_by_testcase(db, testcase_id)
