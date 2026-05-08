"""
Text processing and similarity calculation utilities for traceability analysis.
"""

from typing import Set, Dict, List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re


class SimilarityCalculator:
    """
    Handles various text similarity calculations for requirement-test case matching.
    
    This class provides multiple similarity metrics:
    - TF-IDF based cosine similarity
    - Keyword-based Jaccard similarity
    - Hybrid weighted combination
    """
    
    STOP_WORDS = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
        'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their', 'what',
        'which', 'who', 'when', 'where', 'why', 'how'
    }
    
    def __init__(self, min_keyword_length: int = 3):
        """
        Initialize the similarity calculator.
        
        Args:
            min_keyword_length: Minimum length for keyword extraction
        """
        self.min_keyword_length = min_keyword_length
    
    def calculate_tfidf_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts using TF-IDF and cosine similarity.
        
        Args:
            text1: First text to compare
            text2: Second text to compare
            
        Returns:
            Similarity score between 0 and 1
        """
        if not text1 or not text2:
            return 0.0
        
        vectorizer = TfidfVectorizer(stop_words='english', lowercase=True)
        
        try:
            tfidf_matrix = vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(similarity)
        except Exception:
            # If vectorization fails (e.g., empty vocabulary), return 0
            return 0.0
    
    def extract_keywords(self, text: str) -> Set[str]:
        """
        Extract keywords from text by filtering stop words and short words.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            Set of keywords (lowercase)
        """
        if not text:
            return set()
        
        text_lower = text.lower()
        
        # Extract alphanumeric words (including hyphenated words and numbers)
        words = re.findall(r'\b[a-z0-9]+(?:-[a-z0-9]+)*\b', text_lower)
        
        # Filter by length and stop words
        keywords = {
            word for word in words 
            if len(word) >= self.min_keyword_length and word not in self.STOP_WORDS
        }
        
        return keywords
    
    def calculate_keyword_similarity(self, keywords1: Set[str], keywords2: Set[str]) -> float:
        """
        Calculate keyword match score using Jaccard similarity.
        
        Args:
            keywords1: Set of keywords from first text
            keywords2: Set of keywords from second text
            
        Returns:
            Jaccard similarity score between 0 and 1
        """
        if not keywords1 or not keywords2:
            return 0.0
        
        intersection = keywords1.intersection(keywords2)
        union = keywords1.union(keywords2)
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def calculate_hybrid_similarity(
        self,
        text1: str,
        text2: str,
        keyword_weight: float = 0.4,
        tfidf_weight: float = 0.6
    ) -> Dict[str, any]:
        """
        Calculate hybrid similarity combining keyword matching and TF-IDF.
        
        Args:
            text1: First text to compare
            text2: Second text to compare
            keyword_weight: Weight for keyword matching (0.0 to 1.0)
            tfidf_weight: Weight for TF-IDF similarity (0.0 to 1.0)
            
        Returns:
            Dictionary with keyword_score, tfidf_score, combined_score, and matched_keywords
        """
        # Extract keywords
        keywords1 = self.extract_keywords(text1)
        keywords2 = self.extract_keywords(text2)
        
        # Calculate individual scores
        keyword_score = self.calculate_keyword_similarity(keywords1, keywords2)
        tfidf_score = self.calculate_tfidf_similarity(text1, text2)
        
        # Normalize weights
        total_weight = keyword_weight + tfidf_weight
        if total_weight > 0:
            normalized_keyword_weight = keyword_weight / total_weight
            normalized_tfidf_weight = tfidf_weight / total_weight
        else:
            normalized_keyword_weight = 0.5
            normalized_tfidf_weight = 0.5
        
        # Calculate combined score
        combined_score = (
            keyword_score * normalized_keyword_weight +
            tfidf_score * normalized_tfidf_weight
        )
        
        return {
            "keyword_score": float(keyword_score),
            "tfidf_score": float(tfidf_score),
            "combined_score": float(combined_score),
            "matched_keywords": sorted(list(keywords1.intersection(keywords2)))
        }


def combine_text_fields(title: str, description: str = None) -> str:
    """
    Combine title and description into a single text for comparison.
    
    Args:
        title: Title or name of the entity
        description: Description or steps (optional)
        
    Returns:
        Combined text
    """
    if description:
        return f"{title} {description}"
    return title
