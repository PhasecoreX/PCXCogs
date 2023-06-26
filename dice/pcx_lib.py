"""Shared code across multiple cogs."""
import asyncio
from collections.abc import Mapping
from contextlib import suppress
from typing import Any

import discord
from redbot.core import __version__ as redbot_version
from redbot.core import commands
from redbot.core.utils import common_filters
from redbot.core.utils.chat_formatting import box

headers = {"user-agent": "Red-DiscordBot/" + redbot_version}

MAX_EMBED_SIZE = 5900
MAX_EMBED_FIELDS = 20
MAX_EMBED_FIELD_SIZE = 1024


async def delete(message: discord.Message, *, delay: float | None = None) -> bool:
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
    ctx: commands.Context, content: str | None = None, **kwargs: Any  # noqa: ANN401
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
    destination: discord.abc.Messageable, content: str, **kwargs: Any  # noqa: ANN401
) -> discord.Message | None:
    """Simulate typing and sending a message to a destination.

    Will send a typing indicator, wait a variable amount of time based on the length
    of the text (to simulate typing speed), then send the message.
    """
    content = common_filters.filter_urls(content)
    with suppress(discord.HTTPException):
        async with destination.typing():
            await asyncio.sleep(max(0.25, min(2.5, len(content) * 0.01)))
        return await destination.send(content=content, **kwargs)


async def embed_splitter(
    embed: discord.Embed, destination: discord.abc.Messageable | None = None
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
            if len(field["value"]) > MAX_EMBED_FIELD_SIZE:
                field["value"] = field["value"][: MAX_EMBED_FIELD_SIZE - 3] + "..."
                modified = True
    if modified:
        embed = discord.Embed.from_dict(embed_dict)

    # Short circuit
    if len(embed) <= MAX_EMBED_SIZE and (
        "fields" not in embed_dict or len(embed_dict["fields"]) <= MAX_EMBED_FIELDS
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
        if (
            len(current_embed) > MAX_EMBED_SIZE
            or len(embed_dict["fields"]) > MAX_EMBED_FIELDS
        ):
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

    def __init__(self, header: str | None = None) -> None:
        """Init."""
        self.header = header
        self._length = 0
        self._settings: list[tuple] = []

    def add(self, setting: str, value: Any) -> None:  # noqa: ANN401
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

    def display(self, *additional) -> str:  # noqa: ANN002 (Self)
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

    def __len__(self) -> int:
        """Count of how many settings there are to display."""
        return len(self._settings)


class Perms:
    """Helper class for dealing with a dictionary of discord.PermissionOverwrite."""

    def __init__(
        self,
        overwrites: dict[
            discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite
        ]
        | None = None,
    ) -> None:
        """Init."""
        self.__overwrites: dict[
            discord.Role | discord.Member,
            discord.PermissionOverwrite,
        ] = {}
        self.__original: dict[
            discord.Role | discord.Member,
            discord.PermissionOverwrite,
        ] = {}
        if overwrites:
            for key, value in overwrites.items():
                if isinstance(key, discord.Role | discord.Member):
                    pair = value.pair()
                    self.__overwrites[key] = discord.PermissionOverwrite().from_pair(
                        *pair
                    )
                    self.__original[key] = discord.PermissionOverwrite().from_pair(
                        *pair
                    )

    def overwrite(
        self,
        target: discord.Role | discord.Member | discord.Object,
        permission_overwrite: Mapping[str, bool | None] | discord.PermissionOverwrite,
    ) -> None:
        """Set the permissions for a target."""
        if not isinstance(target, discord.Role | discord.Member):
            return
        if isinstance(permission_overwrite, discord.PermissionOverwrite):
            if permission_overwrite.is_empty():
                self.__overwrites[target] = discord.PermissionOverwrite()
                return
            self.__overwrites[target] = discord.PermissionOverwrite().from_pair(
                *permission_overwrite.pair()
            )
        else:
            self.__overwrites[target] = discord.PermissionOverwrite()
            self.update(target, permission_overwrite)

    def update(
        self,
        target: discord.Role | discord.Member,
        perm: Mapping[str, bool | None],
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
    ) -> dict[discord.Role | discord.Member, discord.PermissionOverwrite] | None:
        """Get current overwrites."""
        return self.__overwrites
