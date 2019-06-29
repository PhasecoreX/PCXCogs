"""A user lookup result."""
import re

MASS_MENTION_RE = re.compile(
    r"(@)(?=everyone|here)"
)  # This only matches the @ for sanitizing


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
        self.result = result
        self.http_status = http_status
        self.reason = MASS_MENTION_RE.sub("@\u200b", reason)
        self.proof_url = proof_url
