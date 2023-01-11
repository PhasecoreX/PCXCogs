"""A user lookup result."""


from typing import Optional


class LookupResult:
    """A user lookup result."""

    def __init__(
        self,
        service: str,
        result: str,
        *,
        reason: Optional[str] = None,
        proof_url: Optional[str] = None,
    ) -> None:
        """Create the base lookup result."""
        self.service = service
        self.result = result
        self.reason = reason
        self.proof_url = proof_url
