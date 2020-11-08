"""Ban lookup for discord.services."""
import aiohttp
from redbot.core import __version__ as redbot_version

from ..dto.lookup_result import LookupResult

user_agent = (
    f"Red-DiscordBot/{redbot_version} BanCheck (https://github.com/PhasecoreX/PCXCogs)"
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
                    data = await resp.json()
                    if "ban" in data:
                        return LookupResult(
                            DiscordServices.SERVICE_NAME,
                            "ban",
                            reason=data["ban"]["reason"],
                            proof_url=data["ban"]["proof"]
                            if "proof" in data["ban"]
                            else None,
                        )
                    return LookupResult(DiscordServices.SERVICE_NAME, "clear")
        except aiohttp.ClientConnectionError:
            return LookupResult(
                DiscordServices.SERVICE_NAME,
                "error",
                reason="Could not connect to host",
            )
        except aiohttp.ClientError:
            pass  # All non-ClientConnectionError aiohttp exceptions are treated as malformed data
        except TypeError:
            pass  # resp.json() is None (malformed data)
        except KeyError:
            pass  # json element does not exist (malformed data)
        return LookupResult(
            DiscordServices.SERVICE_NAME,
            "error",
            reason="Response data malformed",
        )
