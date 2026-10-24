class CRMError(Exception):
    """Base for everything the CRM layer raises."""


class ZohoTransientError(CRMError):
    """Timeouts, network failures, HTTP 429/5xx. Safe to retry."""


class ZohoAuthError(CRMError):
    """Token refresh failed or the token stayed invalid after a refresh."""


class ZohoPermanentError(CRMError):
    """4xx validation-type failure. Retrying will not help."""

    def __init__(self, message: str, code: str | None = None, existing_id: str | None = None):
        super().__init__(message)
        self.code = code
        self.existing_id = existing_id


class CRMUnavailable(CRMError):
    """Raised by CRMService after retries are exhausted (or auth is broken)."""
