"""
Unit tests for enhanced logging utilities.
"""

import pytest
import logging
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.utils.logger import (
    get_logger,
    set_correlation_id,
    set_user_id,
    clear_context,
    log_execution_time,
    log_function_call,
    configure_root_logger,
    ColoredFormatter,
    JsonFormatter,
    ContextFilter,
)


class TestGetLogger:
    """Test logger creation and configuration."""
    
    def test_get_logger_creates_logger(self):
        """Test that get_logger creates a logger instance."""
        logger = get_logger("test_logger")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"
    
    def test_get_logger_has_handlers(self):
        """Test that logger has handlers configured."""
        logger = get_logger("test_logger_handlers")
        assert len(logger.handlers) > 0
    
    def test_get_logger_idempotent(self):
        """Test that calling get_logger multiple times doesn't add duplicate handlers."""
        logger1 = get_logger("test_logger_idem")
        initial_handler_count = len(logger1.handlers)
        
        logger2 = get_logger("test_logger_idem")
        assert logger1 is logger2
        assert len(logger2.handlers) == initial_handler_count
    
    @patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"})
    def test_get_logger_respects_log_level_env(self):
        """Test that logger respects LOG_LEVEL environment variable."""
        logger = get_logger("test_logger_level")
        assert logger.level == logging.DEBUG


class TestContextFilter:
    """Test context filtering functionality."""
    
    def test_set_correlation_id(self):
        """Test setting correlation ID."""
        set_correlation_id("test-correlation-123")
        
        # Create a logger and log record
        logger = get_logger("test_context")
        
        # The correlation ID should be added by the filter
        # We can verify this by checking the filter
        for handler in logger.handlers:
            for filter_obj in handler.filters:
                if isinstance(filter_obj, ContextFilter):
                    assert filter_obj.correlation_id == "test-correlation-123"
    
    def test_set_user_id(self):
        """Test setting user ID."""
        set_user_id("user-456")
        
        logger = get_logger("test_user_context")
        
        for handler in logger.handlers:
            for filter_obj in handler.filters:
                if isinstance(filter_obj, ContextFilter):
                    assert filter_obj.user_id == "user-456"
    
    def test_clear_context(self):
        """Test clearing context."""
        set_correlation_id("test-123")
        set_user_id("user-456")
        clear_context()
        
        logger = get_logger("test_clear_context")
        
        for handler in logger.handlers:
            for filter_obj in handler.filters:
                if isinstance(filter_obj, ContextFilter):
                    assert filter_obj.correlation_id is None
                    assert filter_obj.user_id is None


class TestJsonFormatter:
    """Test JSON formatter."""
    
    def test_json_formatter_output(self):
        """Test that JSON formatter produces valid JSON."""
        formatter = JsonFormatter()
        
        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        
        # Should be valid JSON
        parsed = json.loads(output)
        assert parsed["message"] == "Test message"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"
        assert "timestamp" in parsed
    
    def test_json_formatter_with_extra_fields(self):
        """Test that JSON formatter includes extra fields."""
        formatter = JsonFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Add extra fields
        record.correlation_id = "test-123"
        record.user_id = "user-456"
        record.duration_ms = 123.45
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert parsed["correlation_id"] == "test-123"
        assert parsed["user_id"] == "user-456"
        assert parsed["duration_ms"] == 123.45


class TestLogExecutionTime:
    """Test execution time logging."""
    
    def test_log_execution_time_context_manager(self):
        """Test that log_execution_time context manager works."""
        logger = get_logger("test_timing")
        
        with log_execution_time(logger, "test operation"):
            # Simulate some work
            pass
        
        # If we get here without exception, the test passes
        assert True
    
    def test_log_execution_time_with_exception(self):
        """Test that log_execution_time works even if operation fails."""
        logger = get_logger("test_timing_error")
        
        with pytest.raises(ValueError):
            with log_execution_time(logger, "failing operation"):
                raise ValueError("Test error")


class TestLogFunctionCall:
    """Test function call logging decorator."""
    
    def test_log_function_call_decorator(self):
        """Test that function call decorator works."""
        logger = get_logger("test_decorator")
        
        @log_function_call(logger)
        def test_function(x, y):
            return x + y
        
        result = test_function(2, 3)
        assert result == 5
    
    def test_log_function_call_with_exception(self):
        """Test that decorator logs exceptions properly."""
        logger = get_logger("test_decorator_error")
        
        @log_function_call(logger)
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_function()


class TestFileLogging:
    """Test file logging functionality."""
    
    def test_file_logging_enabled(self, tmp_path):
        """Test that file logging can be enabled."""
        # Create a logger with file logging in temp directory
        logger = get_logger("test_file_logging", enable_file_logging=False)
        
        # Manually add file handler to temp location
        from app.utils.logger import setup_file_handler
        
        log_dir = tmp_path / "logs"
        setup_file_handler(logger, str(log_dir))
        
        # Log something
        logger.info("Test file logging")
        
        # Check that log file was created
        log_file = log_dir / "app.log"
        assert log_file.exists()
        
        # Read and verify content
        content = log_file.read_text()
        assert len(content) > 0
        
        # Should be JSON format
        lines = content.strip().split('\n')
        for line in lines:
            if line:
                parsed = json.loads(line)
                assert "message" in parsed
                assert "timestamp" in parsed


class TestColoredFormatter:
    """Test colored formatter."""
    
    def test_colored_formatter_adds_colors(self):
        """Test that colored formatter adds ANSI color codes."""
        formatter = ColoredFormatter(
            '%(levelname)s - %(name)s - %(message)s'
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        
        # Should contain ANSI color codes
        assert '\033[' in output


@patch.dict(os.environ, {
    "LOG_LEVEL": "DEBUG",
    "LOG_FORMAT": "json",
    "LOG_COLOR": "false"
})
def test_environment_variable_configuration():
    """Test that environment variables are respected."""
    from app.utils.logger import get_log_level, get_log_format
    
    assert get_log_level() == logging.DEBUG
    assert get_log_format() == "json"


def test_configure_root_logger():
    """Test root logger configuration."""
    configure_root_logger()
    
    root_logger = logging.getLogger()
    assert len(root_logger.handlers) > 0
    
    # Should suppress noisy loggers
    urllib3_logger = logging.getLogger('urllib3')
    assert urllib3_logger.level == logging.WARNING
