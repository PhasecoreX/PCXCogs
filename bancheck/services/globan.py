"""Ban lookup for Globan."""
import json

import aiohttp
from redbot.core import __version__ as redbot_version

from ..dto.lookup_result import LookupResult


class globan:
    """Ban lookup for Globan."""

    SERVICE_NAME = "Globan"
    SERVICE_URL = "https://www.globan.xyz"
    SERVICE_HINT = "This service isn't actually in open beta yet"

    @staticmethod
    async def lookup(user_id, api_key):
        """Perform user lookup on Globan."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.globan.xyz/API?REV=1&TOKEN="
                + api_key
                + "&TYPE=BANCHECK&VALUE="
                + str(user_id),
                headers={"user-agent": "Red-DiscordBot/" + redbot_version},
            ) as resp:
                if resp.status != 200:
                    return LookupResult(globan.SERVICE_NAME, resp.status, "error")
                data = await resp.json()
                if "error" in data:
                    """
                    {
                        "error": "INVAILID TOKEN"
                    }
                    """
                    return LookupResult(
                        globan.SERVICE_NAME, resp.status, "error", reason=data["error"]
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
                        globan.SERVICE_NAME, resp.status, "ban", reason=data["reason"]
                    )
                return LookupResult(globan.SERVICE_NAME, resp.status, "clear")
