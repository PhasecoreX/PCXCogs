"""Ban lookup for KSoft.Si."""
import aiohttp
from redbot.core import __version__ as redbot_version

from ..dto.lookup_result import LookupResult
from ..dto.report_result import ReportResult

user_agent = (
    f"Red-DiscordBot/{redbot_version} BanCheck (https://github.com/PhasecoreX/PCXCogs)"
)


class KSoftSi:
    """Ban lookup for KSoft.Si."""

    SERVICE_NAME = "KSoft.Si Bans"
    SERVICE_API_KEY_REQUIRED = True
    SERVICE_URL = "https://api.ksoft.si/#get-started"
    SERVICE_HINT = "You only need to do Step 1 in order to get an API key"
    BASE_URL = "https://api.ksoft.si/bans"

    @staticmethod
    async def lookup(user_id: int, api_key: str):
        """Perform user lookup on KSoft.Si."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    KSoftSi.BASE_URL + "/check",
                    params={"user": str(user_id)},
                    headers={
                        "Authorization": "NANI " + api_key,
                        "user-agent": user_agent,
                    },
                ) as resp:
                    """Response 200 example:
                    {
                        "is_banned": true
                    }
                    """
                    """ Response 401 example:
                    {
                        "detail": "Invalid token."
                    }
                    """
                    data = await resp.json()
                    if resp.status != 200:
                        reason = ""
                        if "detail" in data:
                            reason = data["detail"]
                        if "message" in data:
                            reason = data["message"]
                        return LookupResult(
                            KSoftSi.SERVICE_NAME, "error", reason=reason
                        )
                    # Successful lookup
                    if not data["is_banned"]:
                        return LookupResult(KSoftSi.SERVICE_NAME, "clear")

                async with session.get(
                    KSoftSi.BASE_URL + "/info",
                    params={"user": user_id},
                    headers={
                        "Authorization": "NANI " + api_key,
                        "user-agent": user_agent,
                    },
                ) as resp:
                    """Response 200 example:
                    {
                        "id": 492811511081861130,
                        "name": "󐂪 discord.gg/bYNTxCJ 󐂪",
                        "discriminator": "3334",
                        "moderator_id": 205680187394752512,
                        "reason": "Anarchy Raider",
                        "proof": "https://imgur.com/a/eiOgTjS",
                        "is_ban_active": true,
                        "can_be_appealed": false,
                        "timestamp": "2018-09-21T23:58:32.743",
                        "appeal_reason": "",
                        "appeal_date": null,
                        "requested_by": "205680187394752512",
                        "exists": true
                    }
                    """
                    """ Response 404 example:
                    {
                        "code": 404,
                        "error": true,
                        "exists": false,
                        "message": "specified user does not exist"
                    }
                    """
                    data = await resp.json()
                    if resp.status != 200:
                        reason = ""
                        if "detail" in data:
                            reason = data["detail"]
                        if "message" in data:
                            reason = data["message"]
                        return LookupResult(
                            KSoftSi.SERVICE_NAME, "error", reason=reason
                        )
                    # Successful lookup
                    return LookupResult(
                        KSoftSi.SERVICE_NAME,
                        "ban",
                        reason=data["reason"],
                        proof_url=data["proof"] if "proof" in data else None,
                    )
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

    @staticmethod
    async def report(user_id: int, api_key: str, mod_id: int, reason: str, proof: str):
        """Perform ban report on KSoft.Si."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    KSoftSi.BASE_URL + "/add",
                    data={
                        "user": user_id,
                        "mod": mod_id,
                        "reason": reason,
                        "proof": proof,
                    },
                    headers={
                        "Authorization": "NANI " + api_key,
                        "user-agent": user_agent,
                    },
                ) as resp:
                    data = await resp.json()
                    # User already banned
                    if resp.status == 409:
                        return ReportResult(
                            KSoftSi.SERVICE_NAME,
                            True,
                            reason=data["message"],
                        )
                    # Some other error
                    if resp.status != 200:
                        reason = ""
                        if "detail" in data:
                            reason = data["detail"]
                        if "message" in data:
                            reason = data["message"]
                        return ReportResult(KSoftSi.SERVICE_NAME, False, reason=reason)
                    # Successful report
                    return ReportResult(KSoftSi.SERVICE_NAME, True)
        except aiohttp.ClientConnectionError:
            return ReportResult(
                KSoftSi.SERVICE_NAME,
                False,
                reason="Could not connect to host",
            )
        except aiohttp.ClientError:
            pass  # All non-ClientConnectionError aiohttp exceptions are treated as malformed data
        except TypeError:
            pass  # resp.json() is None (malformed data)
        except KeyError:
            pass  # json element does not exist (malformed data)
        return ReportResult(
            KSoftSi.SERVICE_NAME,
            False,
            reason="Response data malformed",
        )
