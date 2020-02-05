"""A user lookup result."""
from redbot.core.utils.chat_formatting import escape


class LookupResult:
    """A user lookup result."""

    def __init__(
        self,
        service: str,
        http_status: int,
        result: str,
        username: str = "",
        userid: int = 0,
        reason: str = "",
        proof_url: str = "",
    ):
        """Create the base lookup result."""
        self.service = service
        self.http_status = http_status
        self.result = result
        self.reason = escape(reason, mass_mentions=True)
        self.proof_url = proof_url
