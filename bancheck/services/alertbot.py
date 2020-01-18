"""Ban lookup for Alertbot."""
import aiohttp
from redbot.core import __version__ as redbot_version

from ..dto.lookup_result import LookupResult


class alertbot:
    """Ban lookup for Alertbot."""

    SERVICE_NAME = "Alertbot"
    SERVICE_API_KEY_REQUIRED = True
    SERVICE_URL = "https://api.alertbot.services"

    @staticmethod
    async def lookup(user_id, api_key=None):
        """Perform user lookup on Alertbot."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    "https://api.alertbot.services/v1/?action=bancheck&userid={}".format(
                        user_id
                    ),
                    headers={
                        "AuthKey": api_key,
                        "user-agent": "Red-DiscordBot/" + redbot_version,
                    },
                ) as resp:
                    if resp.status != 200:
                        return LookupError(resp.status)
                    data = await resp.json()
                    if not data:
                        return LookupError(resp.status, "No data returned")
                    if "code" not in data:
                        return LookupError(resp.status, "Data malformed")
                    if int(data["code"]) != 200:
                        return LookupError(resp.status, data["desc"])
                    if "data" not in data or "result" not in data["data"] or "banned" not in data["data"]["result"]:
                        return LookupError(resp.status, "Data malformed")
                    if data["data"]["result"]["banned"]:
                        return LookupResult(
                            alertbot.SERVICE_NAME,
                            resp.status,
                            "ban",
                            reason=data["data"]["result"]["reason"],
                            proof_url=data["data"]["result"]["proof"],
                        )
                    return LookupResult(
                        alertbot.SERVICE_NAME, resp.status, "clear"
                    )
            except aiohttp.client_exceptions.ClientConnectorError:
                return LookupError(0, "Connection refused")

    @staticmethod
    def LookupError(status: int, reason: str = ""):
        """Generate a LookupResult error."""
        return LookupResult(
            alertbot.SERVICE_NAME,
            status,
            "error",
            reason=reason,
        )
