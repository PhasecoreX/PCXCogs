"""Ban lookup for discord.services."""
import aiohttp
from redbot.core import __version__ as redbot_version

from ..dto.lookup_result import LookupResult

user_agent = "Red-DiscordBot/{} BanCheck (https://github.com/PhasecoreX/PCXCogs)".format(
    redbot_version
)


class DiscordServices:
    """Ban lookup for discord.services."""

    SERVICE_NAME = "discord.services"
    SERVICE_API_KEY_REQUIRED = False
    SERVICE_URL = "https://discord.services"

    @staticmethod
    async def lookup(user_id: int, api_key: str = None):
        """Perform user lookup on discord.services."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://discord.services/api/ban/" + str(user_id),
                    headers={"user-agent": user_agent},
                ) as resp:
                    if resp.status != 200:
                        return LookupResult(
                            DiscordServices.SERVICE_NAME, resp.status, "error"
                        )
                    try:
                        data = await resp.json()
                    except aiohttp.ContentTypeError:
                        return LookupResult(
                            DiscordServices.SERVICE_NAME,
                            resp.status,
                            "error",
                            reason="Lookup data malformed",
                        )
                    if not data:
                        return LookupResult(
                            DiscordServices.SERVICE_NAME,
                            resp.status,
                            "error",
                            reason="No data returned",
                        )
                    if "ban" in data:
                        return LookupResult(
                            DiscordServices.SERVICE_NAME,
                            resp.status,
                            "ban",
                            reason=data["ban"]["reason"],
                            proof_url=data["ban"]["proof"],
                        )
                    return LookupResult(
                        DiscordServices.SERVICE_NAME, resp.status, "clear"
                    )
        except aiohttp.ClientConnectionError:
            return LookupResult(
                DiscordServices.SERVICE_NAME, 0, "error", reason="Connection error",
            )
