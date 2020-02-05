"""Ban lookup for KSoft.Si."""
import aiohttp
from redbot.core import __version__ as redbot_version

from ..dto.lookup_result import LookupResult
from ..dto.report_result import ReportResult

user_agent = "Red-DiscordBot/{} BanCheck (https://github.com/PhasecoreX/PCXCogs)".format(
    redbot_version
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
        async with aiohttp.ClientSession() as session:
            async with session.get(
                KSoftSi.BASE_URL + "/check",
                params={"user": str(user_id)},
                headers={"Authorization": "NANI " + api_key, "user-agent": user_agent},
            ) as resp:
                """ Response 200 example:
                {
                    "is_banned": true
                }
                """
                if resp.status == 401:
                    try:
                        data = await resp.json()
                        return LookupResult(
                            KSoftSi.SERVICE_NAME,
                            resp.status,
                            "error",
                            reason=data["detail"],
                        )
                    except aiohttp.client_exceptions.ContentTypeError:
                        pass  # Drop down to !=200 logic
                if resp.status != 200:
                    return LookupResult(KSoftSi.SERVICE_NAME, resp.status, "error")
                data = await resp.json()
                if not data:
                    return LookupResult(
                        KSoftSi.SERVICE_NAME,
                        resp.status,
                        "error",
                        reason="No data returned",
                    )
                if not data["is_banned"]:
                    return LookupResult(KSoftSi.SERVICE_NAME, resp.status, "clear")

            async with session.get(
                KSoftSi.BASE_URL + "/info",
                params={"user": user_id},
                headers={"Authorization": "NANI " + api_key, "user-agent": user_agent},
            ) as resp:
                """ Response 200 example:
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
                if resp.status == 401:
                    try:
                        data = await resp.json()
                        return LookupResult(
                            KSoftSi.SERVICE_NAME,
                            resp.status,
                            "error",
                            reason=data["detail"],
                        )
                    except aiohttp.client_exceptions.ContentTypeError:
                        pass  # Drop down to !=200 logic
                if resp.status == 404:
                    try:
                        data = await resp.json()
                        return LookupResult(
                            KSoftSi.SERVICE_NAME,
                            resp.status,
                            "error",
                            reason=data["message"],
                        )
                    except aiohttp.client_exceptions.ContentTypeError:
                        pass  # Drop down to !=200 logic
                if resp.status != 200:
                    return LookupResult(KSoftSi.SERVICE_NAME, resp.status, "error")
                data = await resp.json()
                if not data:
                    return LookupResult(
                        KSoftSi.SERVICE_NAME,
                        resp.status,
                        "error",
                        reason="No data returned",
                    )
                return LookupResult(
                    KSoftSi.SERVICE_NAME,
                    resp.status,
                    "ban",
                    reason=data["reason"],
                    proof_url=data["proof"],
                )

    @staticmethod
    async def report(user_id: int, api_key: str, mod_id: int, reason: str, proof: str):
        """Perform ban report on KSoft.Si."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    KSoftSi.BASE_URL + "/add",
                    params={
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
                    if resp.status == 401:
                        try:
                            data = await resp.json()
                            return ReportResult(
                                KSoftSi.SERVICE_NAME,
                                resp.status,
                                False,
                                reason=data["detail"],
                            )
                        except aiohttp.client_exceptions.ContentTypeError:
                            pass  # Drop down to !=200 logic
                    if resp.status == 409:
                        data = await resp.json()
                        return ReportResult(
                            KSoftSi.SERVICE_NAME,
                            resp.status,
                            True,
                            reason=data["message"],
                        )
                    if resp.status == 400:
                        data = await resp.json()
                        return ReportResult(
                            KSoftSi.SERVICE_NAME,
                            resp.status,
                            False,
                            reason=data["message"],
                        )
                    if resp.status != 200:
                        return ReportResult(KSoftSi.SERVICE_NAME, resp.status, False)
                    return ReportResult(KSoftSi.SERVICE_NAME, resp.status, True)
        except aiohttp.client_exceptions.ClientError:
            pass
