"""Shared code across multiple cogs."""
import asyncio

import discord
from redbot.core import __version__ as redbot_version
from redbot.core.utils import common_filters

headers = {"user-agent": "Red-DiscordBot/" + redbot_version}


def checkmark(text: str) -> str:
    """Get text prefixed with a checkmark emoji."""
    return "\N{WHITE HEAVY CHECK MARK} {}".format(text)


async def delete(message: discord.Message) -> bool:
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


async def type_message(
    destination: discord.abc.Messageable, content: str, **kwargs
) -> discord.Message:
    """Simulate typing and sending a message to a destination.

    Will send a typing indicator, wait a variable amount of time based on the length
    of the text (to simulate typing speed), then send the message.
    """
    content = common_filters.filter_mass_mentions(content)
    content = common_filters.filter_urls(content)
    content = common_filters.filter_various_mentions(content)
    try:
        async with destination.typing():
            await asyncio.sleep(len(content) * 0.01)
            return await destination.send(content=content, **kwargs)
    except discord.HTTPException:
        pass  # Not allowed to send messages to this destination (or, sending the message failed)
