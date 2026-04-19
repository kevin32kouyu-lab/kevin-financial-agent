"""Custom exceptions for Financial Agent."""

from typing import Any


class FinancialAgentError(Exception):
    """Base exception for all Financial Agent errors.

    This class provides a foundation for all custom exceptions in the
    application, allowing for structured error handling and user-friendly messages.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        """Initialize the exception.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses.

        Returns:
            Dictionary with error information
        """
        return {
            "error": self.message,
            "error_type": self.__class__.__name__,
            "details": self.details,
        }


class DataFetchError(FinancialAgentError):
    """Exception raised when data fetching fails.

    Used for errors related to:
    - External API calls (Yahoo Finance, Alpha Vantage, etc.)
    - Database queries
    - File I/O operations
    """

    def __init__(
        self,
        message: str,
        source: str | None = None,
        ticker: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize data fetch error.

        Args:
            message: Error message
            source: Data source name (e.g., "Yahoo Finance", "Alpha Vantage")
            ticker: Related ticker symbol if applicable
            details: Additional error context
        """
        all_details = details or {}
        if source:
            all_details["source"] = source
        if ticker:
            all_details["ticker"] = ticker
        super().__init__(message, all_details)


class ValidationError(FinancialAgentError):
    """Exception raised when data validation fails.

    Used for errors related to:
    - Input validation
    - Schema violations
    - Business rule violations
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize validation error.

        Args:
            message: Error message
            field: Field name that failed validation
            value: Invalid value that caused the error
            details: Additional error context
        """
        all_details = details or {}
        if field:
            all_details["field"] = field
        if value is not None:
            all_details["value"] = str(value)
        super().__init__(message, all_details)


class ScoringError(FinancialAgentError):
    """Exception raised when scoring calculations fail.

    Used for errors related to:
    - Financial metric calculations
    - Score composition
 Computations
    """

    def __init__(
        self,
        message: str,
        ticker: str | None = None,
        score_type: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize scoring error.

        Args:
            message: Error message
            ticker: Related ticker symbol if applicable
            score_type: Type of score that failed (e.g., "valuation", "quality")
            details: Additional error context
        """
        all_details = details or {}
        if ticker:
            all_details["ticker"] = ticker
        if score_type:
            all_details["score_type"] = score_type
        super().__init__(message, all_details)


class BacktestError(FinancialAgentError):
    """Exception raised when backtest operations fail.

    Used for errors related to:
    - Price data loading
    - Portfolio construction
    - Performance calculations
    """

    def __init__(
        self,
        message: str,
        backtest_id: str | None = None,
        run_id: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize backtest error.

        Args:
            message: Error message
            backtest_id: Backtest ID if applicable
            run_id: Source run ID if applicable
            details: Additional error context
        """
        all_details = details or {}
        if backtest_id:
            all_details["backtest_id"] = backtest_id
        if run_id:
            all_details["run_id"] = run_id
        super().__init__(message, all_details)


class ConfigurationError(FinancialAgentError):
    """Exception raised when configuration is invalid or missing.

    Used for errors related to:
    - Missing environment variables
    - Invalid configuration values
    - Configuration file parsing errors
    """

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize configuration error.

        Args:
            message: Error message
            config_key: Configuration key that is invalid or missing
            details: Additional error context
        """
        all_details = details or {}
        if config_key:
            all_details["config_key"] = config_key
        super().__init__(message, all_details)
