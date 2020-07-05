"""Ban lookup for Alertbot."""
import aiohttp
from redbot.core import __version__ as redbot_version

from ..dto.lookup_result import LookupResult

user_agent = "Red-DiscordBot/{} BanCheck (https://github.com/PhasecoreX/PCXCogs)".format(
    redbot_version
)


class Alertbot:
    """Ban lookup for Alertbot."""

    SERVICE_NAME = "Alertbot"
    SERVICE_API_KEY_REQUIRED = True
    SERVICE_URL = "https://api.alertbot.services"

    @staticmethod
    async def lookup(user_id: int, api_key: str):
        """Perform user lookup on Alertbot."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.alertbot.services/v1/?action=bancheck&userid={}".format(
                        user_id
                    ),
                    headers={"AuthKey": api_key, "user-agent": user_agent},
                ) as resp:
                    if resp.status != 200:
                        return Alertbot._lookup_error(resp.status)
                    try:
                        data = await resp.json()
                    except aiohttp.ContentTypeError:
                        return Alertbot._lookup_error(
                            resp.status, "Lookup data malformed"
                        )
                    if not data:
                        return Alertbot._lookup_error(resp.status, "No data returned")
                    if "code" not in data:
                        return Alertbot._lookup_error(resp.status, "Data malformed")
                    if int(data["code"]) != 200:
                        return Alertbot._lookup_error(resp.status, data["desc"])
                    if (
                        "data" not in data
                        or "result" not in data["data"]
                        or "banned" not in data["data"]["result"]
                    ):
                        return Alertbot._lookup_error(resp.status, "Data malformed")
                    if data["data"]["result"]["banned"]:
                        return LookupResult(
                            Alertbot.SERVICE_NAME,
                            resp.status,
                            "ban",
                            reason=data["data"]["result"]["reason"],
                            proof_url=data["data"]["result"]["proof"],
                        )
                    return LookupResult(Alertbot.SERVICE_NAME, resp.status, "clear")
        except aiohttp.ClientConnectionError:
            return Alertbot._lookup_error(0, "Connection error")

    @staticmethod
    def _lookup_error(status: int, reason: str = ""):
        """Generate a LookupResult error."""
        return LookupResult(Alertbot.SERVICE_NAME, status, "error", reason=reason,)
