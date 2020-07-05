"""Ban lookup for Globan."""
import aiohttp
from redbot.core import __version__ as redbot_version

from ..dto.lookup_result import LookupResult

user_agent = "Red-DiscordBot/{} BanCheck (https://github.com/PhasecoreX/PCXCogs)".format(
    redbot_version
)


class Globan:
    """Ban lookup for Globan."""

    SERVICE_NAME = "Globan"
    SERVICE_API_KEY_REQUIRED = True
    SERVICE_URL = "https://www.globan.xyz"
    SERVICE_HINT = "This service isn't actually in open beta yet"

    @staticmethod
    async def lookup(user_id: int, api_key: str):
        """Perform user lookup on Globan."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.globan.xyz/API?REV=1&TOKEN="
                + api_key
                + "&TYPE=BANCHECK&VALUE="
                + str(user_id),
                headers={"user-agent": user_agent},
            ) as resp:
                if resp.status != 200:
                    return LookupResult(Globan.SERVICE_NAME, resp.status, "error")
                try:
                    data = await resp.json()
                except aiohttp.ContentTypeError:
                    return LookupResult(
                        Globan.SERVICE_NAME,
                        resp.status,
                        "error",
                        reason="Lookup data malformed",
                    )
                if not data:
                    return LookupResult(
                        Globan.SERVICE_NAME,
                        resp.status,
                        "error",
                        reason="No data returned",
                    )
                if "error" in data:
                    """
                    {
                        "error": "INVAILID TOKEN"
                    }
                    """
                    return LookupResult(
                        Globan.SERVICE_NAME, resp.status, "error", reason=data["error"]
                    )
                if data["banned"] == "true":
                    """
                    {
                        "banned": "true",
                        "reason": "DM advertisements",
                        "time": "1552405088"
                    }
                    """
                    return LookupResult(
                        Globan.SERVICE_NAME, resp.status, "ban", reason=data["reason"]
                    )
                return LookupResult(Globan.SERVICE_NAME, resp.status, "clear")
