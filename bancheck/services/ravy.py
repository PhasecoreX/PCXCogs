"""Ban lookup for Ravi."""

import aiohttp
from redbot.core import __version__ as redbot_version

from .dto.lookup_result import LookupResult

user_agent = (
    f"Red-DiscordBot/{redbot_version} BanCheck (https://github.com/PhasecoreX/PCXCogs)"
)


class Ravy:
    """Ban lookup for Ravy."""

    SERVICE_NAME = "Ravy"
    SERVICE_API_KEY_REQUIRED = True
    SERVICE_URL = "https://ravy.org/api"
    SERVICE_HINT = "You will need the 'users.bans' permission node for your token."
    BASE_URL = "https://ravy.org/api/v1/users"

    @staticmethod
    async def lookup(user_id: int, api_key: str) -> LookupResult | list[LookupResult]:
        """Perform user lookup on Ravy."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{Ravy.BASE_URL}/{user_id}/bans",
                    headers={
                        "Authorization": "Ravy " + api_key,
                        "user-agent": user_agent,
                    },
                ) as resp:
                    # Response 200 example:
                    # {
                    #     "bans": [
                    #         {
                    #             "provider": "ksoft",
                    #             "reason": "Anarchy Raider",
                    #             "moderator": "141866639703756037"
                    #         }
                    #     ],
                    #     "trust": {
                    #         "level": 1,
                    #         "label": "very untrustworthy"
                    #     }
                    # }
                    #
                    # Response 401 examples:
                    # {
                    #     "error": "Unauthorized",
                    #     "details": "Invalid token"
                    # }
                    # {
                    #     "error": "Unauthorized",
                    #     "details": "Not authorized for this route"
                    # }
                    #
                    # Response 404 example:
                    # {
                    #     "bans": [],
                    #     "trust": {
                    #         "level": 3,
                    #         "label": "no data"
                    #     }
                    # }
                    data = await resp.json()
                    if "bans" in data:
                        # "bans" will always be in a successful lookup
                        if data["bans"]:
                            results = []
                            for ban in data["bans"]:
                                results.append(
                                    LookupResult(
                                        Ravy.SERVICE_NAME
                                        + " ("
                                        + ban["provider"]
                                        + ")",
                                        "ban",
                                        reason=ban["reason"],
                                    )
                                )
                            return results
                        return LookupResult(Ravy.SERVICE_NAME, "clear")
                    # Otherwise, failed lookup
                    reason = ""
                    if "details" in data:
                        reason = data["details"]
                    return LookupResult(Ravy.SERVICE_NAME, "error", reason=reason)

        except aiohttp.ClientConnectionError:
            return LookupResult(
                Ravy.SERVICE_NAME,
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
            Ravy.SERVICE_NAME,
            "error",
            reason="Response data malformed",
        )
