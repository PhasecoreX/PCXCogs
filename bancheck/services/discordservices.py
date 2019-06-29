"""Ban lookup for discord.services."""
import aiohttp

from ..dto.lookup_result import LookupResult


class discordservices:
    """Ban lookup for discord.services."""

    SERVICE_NAME = "discord.services"

    @staticmethod
    async def lookup(user_id, api_key=None):
        """Perform user lookup on discord.services."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    "https://discord.services/api/ban/" + str(user_id)
                ) as resp:
                    if resp.status != 200:
                        return LookupResult(
                            discordservices.SERVICE_NAME, resp.status, "error"
                        )
                    data = await resp.json()
                    if "ban" in data:
                        return LookupResult(
                            discordservices.SERVICE_NAME,
                            resp.status,
                            "ban",
                            reason=data["ban"]["reason"],
                            proof_url=data["ban"]["proof"],
                        )
                    return LookupResult(
                        discordservices.SERVICE_NAME, resp.status, "clear"
                    )
            except aiohttp.client_exceptions.ClientConnectorError:
                return LookupResult(
                    discordservices.SERVICE_NAME,
                    0,
                    "error",
                    reason="Connection refused",
                )
