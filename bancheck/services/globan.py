"""Ban lookup for Globan."""
import aiohttp
from redbot.core import __version__ as redbot_version

from ..dto.lookup_result import LookupResult

user_agent = (
    f"Red-DiscordBot/{redbot_version} BanCheck (https://github.com/PhasecoreX/PCXCogs)"
)


class Globan:
    """Ban lookup for Globan."""

    SERVICE_NAME = "Globan"
    SERVICE_API_KEY_REQUIRED = True
    SERVICE_URL = "https://globan.xyz"
    SERVICE_HINT = "This service isn't actually in open beta yet"

    @staticmethod
    async def lookup(user_id: int, api_key: str):
        """Perform user lookup on Globan."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://globan.xyz/API?REV=1&TOKEN="
                    + api_key
                    + "&TYPE=BANCHECK&VALUE="
                    + str(user_id),
                    headers={"user-agent": user_agent},
                ) as resp:
                    data = await resp.json()
                    if "error" in data:
                        """
                        {
                            "error": "INVAILID TOKEN"
                        }
                        """
                        return LookupResult(
                            Globan.SERVICE_NAME,
                            "error",
                            reason=data["error"],
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
                            Globan.SERVICE_NAME,
                            "ban",
                            reason=data["reason"],
                        )
                    if data["banned"] == "false":
                        """
                        {
                            "banned": "false"
                        }
                        """
                        return LookupResult(Globan.SERVICE_NAME, "clear")
        except aiohttp.ClientConnectionError:
            return LookupResult(
                Globan.SERVICE_NAME,
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
            Globan.SERVICE_NAME,
            "error",
            reason="Response data malformed",
        )
