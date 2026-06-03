"""Custom exception classes for RTM Automation Engine."""


class RTMBaseException(Exception):
    """Base exception class for all RTM-related errors."""
    
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


# Database Exceptions
class DatabaseException(RTMBaseException):
    """Base exception for database-related errors."""
    pass


class DatabaseConnectionError(DatabaseException):
    """Raised when database connection fails."""
    pass


class RecordNotFoundException(DatabaseException):
    """Raised when a requested record is not found."""
    pass


class DuplicateRecordException(DatabaseException):
    """Raised when attempting to create a duplicate record."""
    pass


# Connector Exceptions
class ConnectorException(RTMBaseException):
    """Base exception for connector-related errors."""
    pass


class ConfluenceConnectionError(ConnectorException):
    """Raised when Confluence connection fails."""
    pass


class JiraConnectionError(ConnectorException):
    """Raised when Jira connection fails."""
    pass


class AuthenticationError(ConnectorException):
    """Raised when authentication fails for external services."""
    pass


class DataFetchError(ConnectorException):
    """Raised when fetching data from external sources fails."""
    pass


# Validation Exceptions
class ValidationException(RTMBaseException):
    """Base exception for validation errors."""
    pass


class InvalidDataFormatException(ValidationException):
    """Raised when data format is invalid."""
    pass


class MissingRequiredFieldException(ValidationException):
    """Raised when a required field is missing."""
    pass


class InvalidConfigurationException(ValidationException):
    """Raised when configuration is invalid."""
    pass


# Service Exceptions
class ServiceException(RTMBaseException):
    """Base exception for service-layer errors."""
    pass


class IngestionException(ServiceException):
    """Raised when data ingestion fails."""
    pass


class ImpactAnalysisException(ServiceException):
    """Raised when impact analysis fails."""
    pass


class TraceabilityException(ServiceException):
    """Raised when traceability operations fail."""
    pass


class CoverageCalculationException(ServiceException):
    """Raised when coverage calculation fails."""
    pass


class RiskAssessmentException(ServiceException):
    """Raised when risk assessment fails."""
    pass


class ReportGenerationException(ServiceException):
    """Raised when report generation fails."""
    pass


# Graph Exceptions
class GraphException(RTMBaseException):
    """Base exception for graph-related errors."""
    pass


class GraphBuildException(GraphException):
    """Raised when graph building fails."""
    pass


class GraphTraversalException(GraphException):
    """Raised when graph traversal fails."""
    pass


class NodeNotFoundException(GraphException):
    """Raised when a graph node is not found."""
    pass


class CyclicDependencyException(GraphException):
    """Raised when a cyclic dependency is detected."""
    pass


# File/IO Exceptions
class FileProcessingException(RTMBaseException):
    """Base exception for file processing errors."""
    pass


class CSVParseException(FileProcessingException):
    """Raised when CSV parsing fails."""
    pass


class JSONParseException(FileProcessingException):
    """Raised when JSON parsing fails."""
    pass


class FileNotFoundError(FileProcessingException):
    """Raised when a required file is not found."""
    pass


# NLP Exceptions
class NLPException(RTMBaseException):
    """Base exception for NLP-related errors."""
    pass


class TextProcessingException(NLPException):
    """Raised when text processing fails."""
    pass


class SimilarityCalculationException(NLPException):
    """Raised when similarity calculation fails."""
    pass
