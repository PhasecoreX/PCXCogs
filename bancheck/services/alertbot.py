"""Ban lookup for Alertbot."""
import aiohttp
from redbot.core import __version__ as redbot_version

from ..dto.lookup_result import LookupResult

user_agent = (
    f"Red-DiscordBot/{redbot_version} BanCheck (https://github.com/PhasecoreX/PCXCogs)"
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
                    f"https://api.alertbot.services/v1/?action=bancheck&userid={user_id}",
                    headers={"AuthKey": api_key, "user-agent": user_agent},
                ) as resp:
                    data = await resp.json()
                    if int(data["code"]) != 200:
                        return LookupResult(
                            Alertbot.SERVICE_NAME,
                            "error",
                            reason=data["desc"],
                        )
                    if data["data"]["result"]["banned"]:
                        return LookupResult(
                            Alertbot.SERVICE_NAME,
                            "ban",
                            reason=data["data"]["result"]["reason"],
                            proof_url=data["data"]["result"]["proof"]
                            if "proof" in data["data"]["result"]
                            else None,
                        )
                    return LookupResult(Alertbot.SERVICE_NAME, "clear")
        except aiohttp.ClientConnectionError:
            return LookupResult(
                Alertbot.SERVICE_NAME,
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
            Alertbot.SERVICE_NAME,
            "error",
            reason="Response data malformed",
        )
