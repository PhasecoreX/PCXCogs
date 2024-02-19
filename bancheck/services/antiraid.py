"""Ban lookup for Antiraid."""

import aiohttp
from redbot.core import __version__ as redbot_version

from .dto.lookup_result import LookupResult

user_agent = (
    f"Red-DiscordBot/{redbot_version} BanCheck (https://github.com/PhasecoreX/PCXCogs)"
)


class Antiraid:
    """Ban lookup for Antiraid."""

    SERVICE_NAME = "Antiraid"
    SERVICE_API_KEY_REQUIRED = False
    SERVICE_URL = "https://banapi.derpystown.com/"
    SERVICE_HINT = None
    BASE_URL = "https://banapi.derpystown.com"

    @staticmethod
    async def lookup(user_id: int, _api_key: str) -> LookupResult:
        """Perform user lookup on Antiraid."""
        try:
            async with aiohttp.ClientSession() as session, session.get(
                f"{Antiraid.BASE_URL}/bans/{user_id}",
                headers={
                    "user-agent": user_agent,
                },
            ) as resp:
                # Response 200 examples:
                # {
                #     "banned": true,
                #     "usertag": "PhasecoreX#0000",
                #     "userid": "140926691442359926",
                #     "caseid": "1",
                #     "reason": "Being too cool",
                #     "proof": "https://www.youtube.com/watch?v=I7Tps0M-l64",
                #     "bandate": "11-08-2022 11:31 AM"
                # }
                #
                # {
                #     "banned": false
                # }
                data = await resp.json()
                if "banned" in data:
                    # "banned" will always be in a successful lookup
                    if data["banned"]:
                        return LookupResult(
                            Antiraid.SERVICE_NAME,
                            "ban",
                            reason=data["reason"],
                            proof_url=data.get("proof", None),
                        )
                    return LookupResult(Antiraid.SERVICE_NAME, "clear")
                # Otherwise, failed lookup
                return LookupResult(Antiraid.SERVICE_NAME, "error")

        except aiohttp.ClientConnectionError:
            return LookupResult(
                Antiraid.SERVICE_NAME,
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
            Antiraid.SERVICE_NAME,
            "error",
            reason="Response data malformed",
        )
