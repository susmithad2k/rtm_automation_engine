"""
Database query optimization utilities.

This module provides optimized query functions and utilities
to reduce database round-trips and improve performance.
"""

from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, distinct, and_
from typing import List, Dict, Optional, Tuple
from app.models.db_models import Requirement, TestCaseModel, Mapping


class QueryOptimizer:
    """
    Utility class for optimized database queries.
    
    Provides methods that use eager loading, batch operations,
    and optimized query patterns to minimize database round-trips.
    """
    
    @staticmethod
    def get_coverage_metrics_optimized(db: Session) -> Dict:
        """
        Get all coverage metrics in a single optimized query.
        
        Uses CTEs and window functions to calculate multiple metrics
        in one database round-trip instead of multiple separate queries.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with all coverage metrics
        """
        # Single query to get all counts
        result = db.query(
            func.count(distinct(Requirement.id)).label('total_requirements'),
            func.count(distinct(Mapping.requirement_id)).label('covered_requirements'),
            func.count(distinct(TestCaseModel.id)).label('total_testcases'),
            func.count(Mapping.id).label('total_mappings')
        ).outerjoin(
            Mapping, Requirement.id == Mapping.requirement_id
        ).outerjoin(
            TestCaseModel, True  # Cross join for total count
        ).first()
        
        total_requirements = result.total_requirements if result else 0
        covered_requirements = result.covered_requirements if result else 0
        uncovered_requirements = total_requirements - covered_requirements
        
        if total_requirements > 0:
            coverage_percentage = (covered_requirements / total_requirements) * 100
        else:
            coverage_percentage = 0.0
        
        return {
            "total_requirements": total_requirements,
            "covered_requirements": covered_requirements,
            "uncovered_requirements": uncovered_requirements,
            "coverage_percentage": round(coverage_percentage, 2),
            "total_testcases": result.total_testcases if result else 0,
            "total_mappings": result.total_mappings if result else 0
        }
    
    @staticmethod
    def get_requirements_with_test_counts(
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[Tuple]:
        """
        Get requirements with their test case counts in a single query.
        
        Uses a LEFT JOIN with aggregation to get counts efficiently
        without N+1 query problem.
        
        Args:
            db: Database session
            skip: Pagination skip
            limit: Pagination limit
            
        Returns:
            List of tuples (Requirement, test_count)
        """
        results = (
            db.query(
                Requirement,
                func.count(Mapping.id).label('test_count')
            )
            .outerjoin(Mapping, Requirement.id == Mapping.requirement_id)
            .group_by(Requirement.id)
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        return results
    
    @staticmethod
    def get_requirements_with_full_details(
        db: Session,
        requirement_ids: Optional[List[int]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Requirement]:
        """
        Get requirements with all related data eagerly loaded.
        
        Uses selectinload to fetch requirements, their mappings,
        and associated test cases in just 2-3 queries instead of N+1.
        
        Args:
            db: Database session
            requirement_ids: Optional list of specific requirement IDs
            skip: Pagination skip
            limit: Pagination limit
            
        Returns:
            List of Requirement objects with eagerly loaded relationships
        """
        query = db.query(Requirement).options(
            selectinload(Requirement.mappings).selectinload(Mapping.testcase)
        )
        
        if requirement_ids:
            query = query.filter(Requirement.id.in_(requirement_ids))
        
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def get_testcases_with_full_details(
        db: Session,
        testcase_ids: Optional[List[int]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[TestCaseModel]:
        """
        Get test cases with all related data eagerly loaded.
        
        Uses selectinload to fetch test cases, their mappings,
        and associated requirements in just 2-3 queries instead of N+1.
        
        Args:
            db: Database session
            testcase_ids: Optional list of specific test case IDs
            skip: Pagination skip
            limit: Pagination limit
            
        Returns:
            List of TestCaseModel objects with eagerly loaded relationships
        """
        query = db.query(TestCaseModel).options(
            selectinload(TestCaseModel.mappings).selectinload(Mapping.requirement)
        )
        
        if testcase_ids:
            query = query.filter(TestCaseModel.id.in_(testcase_ids))
        
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def get_mapping_statistics(db: Session) -> Dict:
        """
        Get comprehensive mapping statistics in a single query.
        
        Returns statistics about mappings including distribution metrics.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with mapping statistics
        """
        # Get requirements with their mapping counts
        req_stats = (
            db.query(
                func.count(Requirement.id).label('total_reqs'),
                func.avg(func.count(Mapping.id)).label('avg_mappings'),
                func.max(func.count(Mapping.id)).label('max_mappings'),
                func.min(func.count(Mapping.id)).label('min_mappings')
            )
            .outerjoin(Mapping, Requirement.id == Mapping.requirement_id)
            .group_by(Requirement.id)
            .first()
        )
        
        return {
            "total_requirements": req_stats.total_reqs if req_stats else 0,
            "avg_mappings_per_requirement": round(float(req_stats.avg_mappings or 0), 2),
            "max_mappings_per_requirement": req_stats.max_mappings if req_stats else 0,
            "min_mappings_per_requirement": req_stats.min_mappings if req_stats else 0
        }
    
    @staticmethod
    def batch_get_by_ids(
        db: Session,
        model_class,
        ids: List[int],
        eager_load_relationships: bool = False
    ) -> List:
        """
        Efficiently fetch multiple records by IDs in a single query.
        
        Args:
            db: Database session
            model_class: The model class to query
            ids: List of IDs to fetch
            eager_load_relationships: Whether to eager load relationships
            
        Returns:
            List of model instances
        """
        if not ids:
            return []
        
        query = db.query(model_class).filter(model_class.id.in_(ids))
        
        if eager_load_relationships and model_class == Requirement:
            query = query.options(
                selectinload(Requirement.mappings).selectinload(Mapping.testcase)
            )
        elif eager_load_relationships and model_class == TestCaseModel:
            query = query.options(
                selectinload(TestCaseModel.mappings).selectinload(Mapping.requirement)
            )
        
        return query.all()
    
    @staticmethod
    def get_uncovered_requirements_optimized(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        columns_only: bool = False
    ):
        """
        Get uncovered requirements with optimized query.
        
        Args:
            db: Database session
            skip: Pagination skip
            limit: Pagination limit
            columns_only: If True, only select id, title, description (more efficient)
            
        Returns:
            List of uncovered requirements or tuples
        """
        # Use NOT EXISTS for better performance on large datasets
        if columns_only:
            query = db.query(
                Requirement.id,
                Requirement.title,
                Requirement.description
            )
        else:
            query = db.query(Requirement)
        
        # NOT EXISTS can be more efficient than NOT IN for some databases
        uncovered = query.filter(
            ~db.query(Mapping).filter(
                Mapping.requirement_id == Requirement.id
            ).exists()
        ).offset(skip).limit(limit).all()
        
        return uncovered


# Singleton instance for easy access
query_optimizer = QueryOptimizer()
