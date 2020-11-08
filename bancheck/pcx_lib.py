"""Shared code across multiple cogs."""
import asyncio
from typing import List, Tuple

import discord
from redbot.core import __version__ as redbot_version
from redbot.core.utils import common_filters
from redbot.core.utils.chat_formatting import box

headers = {"user-agent": "Red-DiscordBot/" + redbot_version}


def checkmark(text: str) -> str:
    """Get text prefixed with a checkmark emoji."""
    return f"\N{WHITE HEAVY CHECK MARK} {text}"


async def delete(message: discord.Message, *, delay=None) -> bool:
    """Attempt to delete a message.

    Returns True if successful, False otherwise.
    """
    try:
        await message.delete(delay=delay)
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
    content = common_filters.filter_urls(content)
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

    if destination:
        for split_embed in split_embeds:
            await destination.send(embed=split_embed)
    return split_embeds


class SettingDisplay:
    """A formattable list of settings."""

    def __init__(self, header: str = None):
        """Init."""
        self.header = header
        self._length = 0
        self._settings: List[Tuple] = []

    def add(self, setting: str, value):
        """Add a setting."""
        setting_colon = setting + ":"
        self._settings.append((setting_colon, value))
        self._length = max(len(setting_colon), self._length)

    def raw(self) -> str:
        """Generate the raw text of this SettingDisplay, to be monospace (ini) formatted later."""
        msg = ""
        if not self._settings:
            return msg
        if self.header:
            msg += f"--- {self.header} ---\n"
        for setting in self._settings:
            msg += f"{setting[0].ljust(self._length, ' ')} [{setting[1]}]\n"
        return msg.strip()

    def display(self, *additional) -> str:
        """Generate a ready-to-send formatted box of settings.

        If additional SettingDisplays are provided, merges their output into one.
        """
        msg = self.raw()
        for section in additional:
            msg += "\n\n" + section.raw()
        return box(msg, lang="ini")

    def __str__(self) -> str:
        """Generate a ready-to-send formatted box of settings."""
        return self.display()
