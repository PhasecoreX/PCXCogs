"""Ban lookup for Globan."""
import json

import aiohttp

from ..dto.lookup_result import LookupResult


class globan:
    """Ban lookup for Globan."""

    SERVICE_NAME = "Globan"

    @staticmethod
    async def lookup(user_id, api_key):
        """Perform user lookup on Globan."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.globan.xyz/API?TOKEN="
                + api_key
                + "&TYPE=BANCHECK&VALUE="
                + str(user_id)
            ) as resp:
                if resp.status != 200:
                    return LookupResult(globan.SERVICE_NAME, resp.status, "error")
                # Globan isn't configured to return application/json
                textdata = await resp.read()
                data = json.loads(textdata)
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
