"""A user Report result."""
from redbot.core.utils.chat_formatting import escape


class ReportResult:
    """A user Report result."""

    def __init__(
        self, service: str, http_status: int, result: bool, reason: str = "",
    ):
        """Create the base Report result."""
        self.service = service
        self.http_status = http_status
        self.result = result
        self.reason = escape(reason, mass_mentions=True)
