"""Ban lookup for KSoft.Si."""
import aiohttp
from redbot.core import __version__ as redbot_version

from ..dto.lookup_result import LookupResult


class ksoftsi:
    """Ban lookup for KSoft.Si."""

    SERVICE_NAME = "KSoft.Si"
    SERVICE_BASE_URL = "https://api.ksoft.si/bans"

    @staticmethod
    async def lookup(user_id, api_key):
        """Perform user lookup on KSoft.Si."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                ksoftsi.SERVICE_BASE_URL + "/check",
                params={"user": str(user_id)},
                headers={
                    "Authorization": "NANI " + api_key,
                    "user-agent": "Red-DiscordBot/" + redbot_version,
                },
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
                            ksoftsi.SERVICE_NAME,
                            resp.status,
                            "error",
                            reason=data["detail"],
                        )
                    except aiohttp.client_exceptions.ContentTypeError:
                        pass  # Drop down to !=200 logic
                if resp.status != 200:
                    return LookupResult(ksoftsi.SERVICE_NAME, resp.status, "error")
                data = await resp.json()
                if not data["is_banned"]:
                    return LookupResult(ksoftsi.SERVICE_NAME, resp.status, "clear")

        async with aiohttp.ClientSession() as session:
            async with session.get(
                ksoftsi.SERVICE_BASE_URL + "/info",
                params={"user": str(user_id)},
                headers={
                    "Authorization": "NANI " + api_key,
                    "user-agent": "Red-DiscordBot/" + redbot_version,
                },
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
                            ksoftsi.SERVICE_NAME,
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
                            ksoftsi.SERVICE_NAME,
                            resp.status,
                            "error",
                            reason=data["message"],
                        )
                    except aiohttp.client_exceptions.ContentTypeError:
                        pass  # Drop down to !=200 logic
                if resp.status != 200:
                    return LookupResult(ksoftsi.SERVICE_NAME, resp.status, "error")
                data = await resp.json()
                return LookupResult(
                    ksoftsi.SERVICE_NAME,
                    resp.status,
                    "ban",
                    reason=data["reason"],
                    proof_url=data["proof"],
                )
