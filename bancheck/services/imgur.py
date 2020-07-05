"""Imgur uploader."""
import aiohttp
from redbot.core import __version__ as redbot_version

user_agent = "Red-DiscordBot/{} BanCheck (https://github.com/PhasecoreX/PCXCogs)".format(
    redbot_version
)


class Imgur:
    """Imgur uploader."""

    @staticmethod
    async def upload(url: str, client_id: str):
        """Upload an image to Imgur anonymously."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.imgur.com/3/upload",
                    data={"image": url},
                    headers={
                        "Authorization": "Client-ID " + client_id,
                        "user-agent": user_agent,
                    },
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and data["success"]:
                            return data["data"]["link"]
        except aiohttp.ClientConnectionError:
            pass
        return None
