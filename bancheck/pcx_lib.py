"""Shared code across multiple cogs."""
import asyncio
from typing import List

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


async def embed_splitter(
    embed: discord.Embed, destination: discord.abc.Messageable = None
) -> List[discord.Embed]:
    """Take an embed and split it so that each embed has at most 20 fields and a length of 5900.

    If supplied with a destination, will also send those embeds to the destination.
    """
    embed_dict = embed.to_dict()
    # Short circuit
    if len(embed) < 5901 and (
        "fields" not in embed_dict or len(embed_dict["fields"]) < 21
    ):
        if destination:
            await destination.send(embed=embed)
        return [embed]

    # Nah we really doing this
    split_embeds: List[discord.Embed] = []
    fields = embed_dict["fields"]
    embed_dict["fields"] = []

    for field in fields:
        embed_dict["fields"].append(field)
        current_embed = discord.Embed.from_dict(embed_dict)
        if len(current_embed) > 5900 or len(embed_dict["fields"]) > 20:
            embed_dict["fields"].pop()
            current_embed = discord.Embed.from_dict(embed_dict)
            split_embeds.append(current_embed.copy())
            embed_dict["fields"] = [field]

    current_embed = discord.Embed.from_dict(embed_dict)
    split_embeds.append(current_embed.copy())

    print(split_embeds)

    if destination:
        for split_embed in split_embeds:
            await destination.send(embed=split_embed)
    return split_embeds
