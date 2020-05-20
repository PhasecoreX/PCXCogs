"""Shared code across multiple cogs."""
import discord
from redbot.core import __version__ as redbot_version

headers = {"user-agent": "Red-DiscordBot/" + redbot_version}


def checkmark(text: str) -> str:
    """Get text prefixed with a checkmark emoji."""
    return "\N{WHITE HEAVY CHECK MARK} {}".format(text)


async def delete(message: discord.Message):
    """Attempt to delete a message.

    Returns True if successful, False otherwise.
    """
    try:
        await message.delete()
    except discord.NotFound:
        return True  # Already deleted
    except discord.HTTPException:
        return False
    return True
