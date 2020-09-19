"""A user Report result."""
from redbot.core.utils.chat_formatting import escape


class ReportResult:
    """A user Report result."""

    def __init__(
        self,
        service: str,
        result: bool,
        *,
        reason: str = "",
    ):
        """Create the base Report result."""
        self.service = service
        self.result = result
        self.reason = reason
