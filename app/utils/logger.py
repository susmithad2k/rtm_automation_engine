"""
Logging utilities for the application.

This module provides enhanced logging capabilities including:
- Configurable log levels via environment variables
- File logging with rotation
- JSON formatting for structured logging
- Colored console output for development
- Correlation ID tracking for request tracing
- Performance timing utilities
"""

import logging
import sys
import os
import json
from typing import Optional, Any, Dict
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from contextlib import contextmanager
from time import perf_counter
from pathlib import Path


# ANSI color codes for console output
class LogColors:
    """ANSI color codes for colored console output."""
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    GRAY = '\033[90m'


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colored output for console."""
    
    COLORS = {
        'DEBUG': LogColors.GRAY,
        'INFO': LogColors.GREEN,
        'WARNING': LogColors.YELLOW,
        'ERROR': LogColors.RED,
        'CRITICAL': LogColors.MAGENTA,
    }
    
    def format(self, record):
        """Format log record with colors."""
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{LogColors.RESET}"
        
        # Add color to logger name
        record.name = f"{LogColors.CYAN}{record.name}{LogColors.RESET}"
        
        return super().format(record)


class JsonFormatter(logging.Formatter):
    """Custom formatter for JSON output."""
    
    def format(self, record):
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, 'correlation_id'):
            log_data['correlation_id'] = record.correlation_id
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
            
        return json.dumps(log_data)


class ContextFilter(logging.Filter):
    """Filter to add contextual information to log records."""
    
    def __init__(self):
        super().__init__()
        self.correlation_id = None
        self.user_id = None
    
    def filter(self, record):
        """Add context to log record."""
        if self.correlation_id:
            record.correlation_id = self.correlation_id
        if self.user_id:
            record.user_id = self.user_id
        return True


# Global context filter instance
_context_filter = ContextFilter()


def get_log_level() -> int:
    """
    Get log level from environment variable.
    
    Returns:
        Log level integer
    """
    level_name = os.getenv('LOG_LEVEL', 'INFO').upper()
    return getattr(logging, level_name, logging.INFO)


def get_log_format() -> str:
    """
    Get log format preference from environment.
    
    Returns:
        'json' or 'text'
    """
    return os.getenv('LOG_FORMAT', 'text').lower()


def setup_file_handler(logger: logging.Logger, log_dir: str = 'logs') -> None:
    """
    Add rotating file handler to logger.
    
    Args:
        logger: Logger instance to add handler to
        log_dir: Directory to store log files
    """
    # Create log directory if it doesn't exist
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Create rotating file handler (10MB max, 5 backup files)
    log_file = Path(log_dir) / 'app.log'
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # Capture all levels to file
    
    # Use JSON format for file logs
    json_formatter = JsonFormatter()
    file_handler.setFormatter(json_formatter)
    file_handler.addFilter(_context_filter)
    
    logger.addHandler(file_handler)


def get_logger(name: str, enable_file_logging: bool = None) -> logging.Logger:
    """
    Get or create a logger with the specified name.
    
    Args:
        name: Name of the logger (typically __name__)
        enable_file_logging: Whether to enable file logging (None = use env var)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        log_level = get_log_level()
        logger.setLevel(log_level)
        
        # Prevent propagation to root logger
        logger.propagate = False
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.addFilter(_context_filter)
        
        # Choose formatter based on environment
        log_format = get_log_format()
        if log_format == 'json':
            formatter = JsonFormatter()
        else:
            # Use colored formatter for better readability in development
            formatter_string = (
                '%(asctime)s - %(name)s - %(levelname)s - '
                '%(message)s [%(filename)s:%(lineno)d]'
            )
            if os.getenv('LOG_COLOR', 'true').lower() == 'true':
                formatter = ColoredFormatter(formatter_string)
            else:
                formatter = logging.Formatter(formatter_string)
        
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Add file handler if enabled
        if enable_file_logging is None:
            enable_file_logging = os.getenv('LOG_FILE_ENABLED', 'false').lower() == 'true'
        
        if enable_file_logging:
            try:
                setup_file_handler(logger)
            except Exception as e:
                logger.error(f"Failed to setup file logging: {e}")
    
    return logger


def set_correlation_id(correlation_id: str) -> None:
    """
    Set correlation ID for request tracking.
    
    Args:
        correlation_id: Unique identifier for request correlation
    """
    _context_filter.correlation_id = correlation_id


def set_user_id(user_id: str) -> None:
    """
    Set user ID for user-specific logging.
    
    Args:
        user_id: User identifier
    """
    _context_filter.user_id = user_id


def clear_context() -> None:
    """Clear all contextual logging information."""
    _context_filter.correlation_id = None
    _context_filter.user_id = None


@contextmanager
def log_execution_time(logger: logging.Logger, operation: str, level: int = logging.INFO):
    """
    Context manager to log execution time of an operation.
    
    Args:
        logger: Logger instance
        operation: Description of the operation
        level: Log level for the timing message
        
    Example:
        with log_execution_time(logger, "database query"):
            perform_query()
    """
    start_time = perf_counter()
    logger.log(level, f"Starting: {operation}")
    
    try:
        yield
    finally:
        duration_ms = (perf_counter() - start_time) * 1000
        logger.log(level, f"Completed: {operation}", extra={'duration_ms': duration_ms})
        logger.log(level, f"{operation} took {duration_ms:.2f}ms")


def log_function_call(logger: logging.Logger, level: int = logging.DEBUG):
    """
    Decorator to log function calls with arguments and execution time.
    
    Args:
        logger: Logger instance
        level: Log level for the messages
        
    Example:
        @log_function_call(logger)
        def my_function(arg1, arg2):
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            logger.log(level, f"Calling {func_name} with args={args}, kwargs={kwargs}")
            
            start_time = perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (perf_counter() - start_time) * 1000
                logger.log(
                    level, 
                    f"{func_name} completed in {duration_ms:.2f}ms",
                    extra={'duration_ms': duration_ms}
                )
                return result
            except Exception as e:
                duration_ms = (perf_counter() - start_time) * 1000
                logger.error(
                    f"{func_name} failed after {duration_ms:.2f}ms: {str(e)}",
                    exc_info=True,
                    extra={'duration_ms': duration_ms}
                )
                raise
        
        return wrapper
    return decorator


def configure_root_logger() -> None:
    """
    Configure the root logger for the application.
    Should be called once at application startup.
    """
    root_logger = logging.getLogger()
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Set level
    root_logger.setLevel(get_log_level())
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(get_log_level())
    
    # Format
    log_format = get_log_format()
    if log_format == 'json':
        formatter = JsonFormatter()
    else:
        formatter_string = (
            '%(asctime)s - %(name)s - %(levelname)s - '
            '%(message)s [%(filename)s:%(lineno)d]'
        )
        formatter = logging.Formatter(formatter_string)
    
    console_handler.setFormatter(formatter)
    console_handler.addFilter(_context_filter)
    root_logger.addHandler(console_handler)
    
    # Suppress noisy loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
