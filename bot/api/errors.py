"""
API Errors - Custom exception classes for API operations
"""

from typing import Optional, Dict, Any


class APIError(Exception):
    """Base API error"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        super().__init__(self.message)

    @property
    def user_message(self) -> str:
        """Get user-friendly error message"""
        return self.get_user_message(self.status_code, self.message, self.response_data)

    @staticmethod
    def get_user_message(
        status_code: Optional[int],
        message: str,
        response_data: Dict[str, Any]
    ) -> str:
        """
        Translate API error to user-friendly message

        Args:
            status_code: HTTP status code
            message: Error message from API
            response_data: Full response data

        Returns:
            User-friendly error message
        """
        # Extract detail from API response
        detail = response_data.get("detail", message)

        # Status code specific messages
        if status_code == 400:
            return f"Invalid input: {detail}"
        elif status_code == 401:
            return "Authentication failed. Please contact support."
        elif status_code == 403:
            return "You don't have permission to perform this action."
        elif status_code == 404:
            return "Resource not found."
        elif status_code == 409:
            return f"Conflict: {detail}"
        elif status_code == 429:
            retry_after = response_data.get("retry_after", "60")
            return f"Rate limit exceeded. Try again in {retry_after} seconds."
        elif status_code and status_code >= 500:
            # For wallet-specific errors, show the detail message
            # Check if it's a wallet-related error by looking for specific keywords
            if any(keyword in detail.lower() for keyword in ["wallet", "private key", "decrypt", "error code:"]):
                return detail  # Show the specific error message
            else:
                return "Server error. Our team has been notified. Please try again later."
        else:
            return f"An error occurred: {detail}"


class AuthenticationError(APIError):
    """Authentication failed"""
    pass


class PermissionError(APIError):
    """Insufficient permissions"""
    pass


class NotFoundError(APIError):
    """Resource not found"""
    pass


class RateLimitError(APIError):
    """Rate limit exceeded"""

    def __init__(self, message: str, retry_after: int = 60, **kwargs):
        super().__init__(message, status_code=429, **kwargs)
        self.retry_after = retry_after


class ValidationError(APIError):
    """Input validation failed"""
    pass


class ServerError(APIError):
    """Server-side error"""
    pass
