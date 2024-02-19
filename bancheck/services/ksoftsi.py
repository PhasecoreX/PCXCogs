"""Ban lookup for KSoft.Si (via Ravy)."""

import aiohttp
from redbot.core import __version__ as redbot_version

from .dto.lookup_result import LookupResult

user_agent = (
    f"Red-DiscordBot/{redbot_version} BanCheck (https://github.com/PhasecoreX/PCXCogs)"
)


class KSoftSi:
    """Ban lookup for KSoft.Si (via Ravy)."""

    SERVICE_NAME = "KSoft.Si Bans (via Ravy)"
    SERVICE_API_KEY_REQUIRED = True
    SERVICE_URL = "https://ravy.org/api"
    SERVICE_HINT = "You can't get this API key anymore, use Ravy instead."
    BASE_URL = "https://ravy.org/api/v1/ksoft/bans"
    HIDDEN = True

    @staticmethod
    async def lookup(user_id: int, api_key: str) -> LookupResult:
        """Perform user lookup on KSoft.Si (via Ravy)."""
        try:
            async with aiohttp.ClientSession() as session, session.get(
                f"{KSoftSi.BASE_URL}/{user_id}",
                headers={
                    "Authorization": "KSoft " + api_key,
                    "user-agent": user_agent,
                },
            ) as resp:
                # Response 200 example:
                # {
                #     "id": "140926691442359926",
                #     "tag": "PhasecoreX 󠂪#0000",
                #     "reason": "Being too cool",
                #     "proof": "https://www.youtube.com/watch?v=I7Tps0M-l64",
                #     "moderator": "141866639703756037",
                #     "severe": true,
                #     "timestamp": "2018-09-21T23:58:32.743477",
                #     "found": true
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
                #     "error": "Not Found",
                #     "details": "The user you queried is not banned",
                #     "found": false
                # }
                data = await resp.json()
                if "found" in data:
                    # "found" will always be in a successful lookup
                    if data["found"]:
                        return LookupResult(
                            KSoftSi.SERVICE_NAME,
                            "ban",
                            reason=data["reason"],
                            proof_url=data.get("proof", None),
                        )
                    LookupResult(KSoftSi.SERVICE_NAME, "clear")
                # Otherwise, failed lookup
                reason = ""
                if "details" in data:
                    reason = data["details"]
                return LookupResult(KSoftSi.SERVICE_NAME, "error", reason=reason)

        except aiohttp.ClientConnectionError:
            return LookupResult(
                KSoftSi.SERVICE_NAME,
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
            KSoftSi.SERVICE_NAME,
            "error",
            reason="Response data malformed",
        )
