"""Shared code across multiple cogs."""
import asyncio
from contextlib import suppress
from typing import Any, Mapping, Optional, Union

import discord
from redbot.core import __version__ as redbot_version
from redbot.core import commands
from redbot.core.utils import common_filters
from redbot.core.utils.chat_formatting import box

headers = {"user-agent": "Red-DiscordBot/" + redbot_version}


def checkmark(text: str) -> str:
    """Get text prefixed with a checkmark emoji."""
    return f"\N{WHITE HEAVY CHECK MARK} {text}"


async def delete(message: discord.Message, *, delay: Optional[float] = None) -> bool:
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


async def reply(
    ctx: commands.Context, content: Optional[str] = None, **kwargs: Any
) -> None:
    """Safely reply to a command message.

    If the command is in a guild, will reply, otherwise will send a message like normal.
    Pre discord.py 1.6, replies are just messages sent with the users mention prepended.
    """
    if ctx.guild:
        if (
            hasattr(ctx, "reply")
            and ctx.channel.permissions_for(ctx.guild.me).read_message_history
        ):
            mention_author = kwargs.pop("mention_author", False)
            kwargs.update(mention_author=mention_author)
            with suppress(discord.HTTPException):
                await ctx.reply(content=content, **kwargs)
                return
        allowed_mentions = kwargs.pop(
            "allowed_mentions",
            discord.AllowedMentions(users=False),
        )
        kwargs.update(allowed_mentions=allowed_mentions)
        await ctx.send(content=f"{ctx.message.author.mention} {content}", **kwargs)
    else:
        await ctx.send(content=content, **kwargs)


async def type_message(
    destination: discord.abc.Messageable, content: str, **kwargs: Any
) -> Optional[discord.Message]:
    """Simulate typing and sending a message to a destination.

    Will send a typing indicator, wait a variable amount of time based on the length
    of the text (to simulate typing speed), then send the message.
    """
    content = common_filters.filter_urls(content)
    with suppress(discord.HTTPException):
        async with destination.typing():
            await asyncio.sleep(max(0.25, min(2.5, len(content) * 0.01)))
        return await destination.send(content=content, **kwargs)


async def message_splitter(
    message: str, destination: Optional[discord.abc.Messageable] = None
) -> list[str]:
    r"""Take a message string and split it so that each message in the resulting list is no greater than 1900.

    Splits on double newlines (\n\n), and if there are none, just trims the strings down to 1900.

    If supplied with a destination, will also send those messages to the destination.
    """
    max_length = 1900
    if len(message) <= max_length:
        if destination:
            await destination.send(message)
        return [message]

    split_messages: list[str] = []
    message_buffer = ""
    for message_chunk in message.split("\n\n"):
        test_message = (message_buffer + "\n\n" + message_chunk).strip()
        if len(test_message) <= max_length:
            message_buffer = test_message
        else:
            if message_buffer:
                split_messages.append(message_buffer)
                message_buffer = ""
            if len(message_chunk) <= max_length:
                message_buffer = message_chunk
            else:
                split_messages.append(message_chunk[: max_length - 3] + "...")

    if destination:
        for split_message in split_messages:
            await destination.send(split_message)
    return split_messages


async def embed_splitter(
    embed: discord.Embed, destination: Optional[discord.abc.Messageable] = None
) -> list[discord.Embed]:
    """Take an embed and split it so that each embed has at most 20 fields and a length of 5900.

    Each field value will also be checked to have a length no greater than 1024.

    If supplied with a destination, will also send those embeds to the destination.
    """
    embed_dict = embed.to_dict()

    # Check and fix field value lengths
    modified = False
    if "fields" in embed_dict:
        for field in embed_dict["fields"]:
            if len(field["value"]) > 1024:
                field["value"] = field["value"][:1021] + "..."
                modified = True
    if modified:
        embed = discord.Embed.from_dict(embed_dict)

    # Short circuit
    if len(embed) < 5901 and (
        "fields" not in embed_dict or len(embed_dict["fields"]) < 21
    ):
        if destination:
            await destination.send(embed=embed)
        return [embed]

    # Nah, we're really doing this
    split_embeds: list[discord.Embed] = []
    fields = embed_dict["fields"] if "fields" in embed_dict else []
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
    """A formatted list of settings."""

    def __init__(self, header: Optional[str] = None) -> None:
        """Init."""
        self.header = header
        self._length = 0
        self._settings: list[tuple] = []

    def add(self, setting: str, value: Any) -> None:
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


class Perms:
    """Helper class for dealing with a dictionary of discord.PermissionOverwrite."""

    def __init__(
        self,
        overwrites: Optional[
            dict[
                Union[discord.Role, discord.Member, discord.Object],
                discord.PermissionOverwrite,
            ]
        ] = None,
    ) -> None:
        """Init."""
        self.__overwrites = {}
        self.__original = {}
        if overwrites:
            for key, value in overwrites.items():
                pair = value.pair()
                self.__overwrites[key] = discord.PermissionOverwrite().from_pair(*pair)
                self.__original[key] = discord.PermissionOverwrite().from_pair(*pair)

    def set(
        self,
        target: Union[discord.Role, discord.Member, discord.Object],
        permission_overwrite: discord.PermissionOverwrite,
    ) -> None:
        """Set the permissions for a target."""
        if not permission_overwrite.is_empty():
            self.__overwrites[target] = discord.PermissionOverwrite().from_pair(
                *permission_overwrite.pair()
            )

    def update(
        self,
        target: Union[discord.Role, discord.Member],
        perm: Mapping[str, Optional[bool]],
    ) -> None:
        """Update the permissions for a target."""
        if target not in self.__overwrites:
            self.__overwrites[target] = discord.PermissionOverwrite()
        self.__overwrites[target].update(**perm)
        if self.__overwrites[target].is_empty():
            del self.__overwrites[target]

    @property
    def modified(self) -> bool:
        """Check if current overwrites are different from when this object was first initialized."""
        return self.__overwrites != self.__original

    @property
    def overwrites(
        self,
    ) -> Optional[
        dict[
            Union[discord.Role, discord.Member, discord.Object],
            discord.PermissionOverwrite,
        ]
    ]:
        """Get current overwrites."""
        return self.__overwrites
