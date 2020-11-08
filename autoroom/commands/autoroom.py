"""The autoroom command."""
import datetime
from abc import ABC
from typing import Union

import discord
from redbot.core import commands
from redbot.core.utils.chat_formatting import error, humanize_timedelta

from ..abc import CompositeMetaClass, MixinMeta
from ..pcx_lib import SettingDisplay, delete


class AutoRoomCommands(MixinMeta, ABC, metaclass=CompositeMetaClass):
    """The autoroom command."""

    @commands.group()
    @commands.guild_only()
    async def autoroom(self, ctx: commands.Context):
        """Manage your AutoRoom."""

    @autoroom.command(name="settings", aliases=["info"])
    async def autoroom_settings(self, ctx: commands.Context):
        """Display current settings."""
        member_channel = self._get_current_voice_channel(ctx.message.author)
        autoroom_info = await self._get_autoroom_info(member_channel)
        if not autoroom_info:
            hint = await ctx.send(
                error(f"{ctx.message.author.mention}, you are not in an AutoRoom.")
            )
            await delete(ctx.message, delay=5)
            await delete(hint, delay=5)
            return

        room_settings = SettingDisplay("Room Settings")
        room_settings.add(
            "Owner",
            autoroom_info["owner"].display_name if autoroom_info["owner"] else "???",
        )

        mode = "???"
        for member_role in autoroom_info["member_roles"]:
            if member_role in member_channel.overwrites:
                mode = (
                    "Public"
                    if member_channel.overwrites[member_role].connect
                    else "Private"
                )
                break
        room_settings.add("Mode", mode)

        room_settings.add("Bitrate", f"{member_channel.bitrate // 1000}kbps")
        room_settings.add(
            "Channel Age",
            humanize_timedelta(
                timedelta=datetime.datetime.utcnow() - member_channel.created_at
            ),
        )

        await ctx.send(room_settings)

    @autoroom.command()
    async def public(self, ctx: commands.Context):
        """Make your AutoRoom public."""
        await self._process_allow_deny(ctx, True)

    @autoroom.command()
    async def private(self, ctx: commands.Context):
        """Make your AutoRoom private."""
        await self._process_allow_deny(ctx, False)

    @autoroom.command(aliases=["add"])
    async def allow(
        self, ctx: commands.Context, member_or_role: Union[discord.Role, discord.Member]
    ):
        """Allow a user (or role) into your AutoRoom."""
        await self._process_allow_deny(ctx, True, member_or_role=member_or_role)

    @autoroom.command(aliases=["ban"])
    async def deny(
        self, ctx: commands.Context, member_or_role: Union[discord.Role, discord.Member]
    ):
        """Deny a user (or role) from accessing your AutoRoom.

        If the user is already in your AutoRoom, they will be disconnected.

        If a user is no longer able to access the room due to denying a role,
        they too will be disconnected. Keep in mind that if the guild is using
        member roles, denying roles will probably not work as expected.
        """
        if await self._process_allow_deny(ctx, False, member_or_role=member_or_role):
            channel = self._get_current_voice_channel(ctx.message.author)
            if not channel or not ctx.guild.me.permissions_in(channel).move_members:
                return
            for member in channel.members:
                if not member.permissions_in(channel).connect:
                    await member.move_to(None, reason="AutoRoom: Deny user")

    async def _process_allow_deny(
        self,
        ctx: commands.Context,
        allow: bool,
        *,
        member_or_role: Union[discord.Role, discord.Member] = None,
    ) -> bool:
        """Actually do channel edit for allow/deny."""
        channel = self._get_current_voice_channel(ctx.message.author)
        autoroom_info = await self._get_autoroom_info(channel)
        if not autoroom_info:
            hint = await ctx.send(
                error(f"{ctx.message.author.mention}, you are not in an AutoRoom.")
            )
            await delete(ctx.message, delay=5)
            await delete(hint, delay=5)
            return False
        if ctx.message.author != autoroom_info["owner"]:
            hint = await ctx.send(
                error(
                    f"{ctx.message.author.mention}, you are not the owner of this AutoRoom."
                )
            )
            await delete(ctx.message, delay=5)
            await delete(hint, delay=5)
            return False

        denied_message = ""
        if not member_or_role:
            # public/private command
            member_or_role = autoroom_info["member_roles"]
        elif (
            allow
            and member_or_role == ctx.guild.default_role
            and [member_or_role] != autoroom_info["member_roles"]
        ):
            denied_message = "this AutoRoom is using member roles, so the default role must remain denied."
        elif member_or_role in autoroom_info["member_roles"]:
            # allow/deny a member role -> modify all member roles
            member_or_role = autoroom_info["member_roles"]
        elif not allow:
            if member_or_role == ctx.guild.me:
                denied_message = "why would I deny myself from entering your AutoRoom?"
            elif member_or_role == ctx.message.author:
                denied_message = "don't be so hard on yourself! This is your AutoRoom!"
            elif member_or_role == ctx.guild.owner:
                denied_message = (
                    "I don't know if you know this, but that's the guild owner... "
                    "I can't deny them from entering your AutoRoom."
                )
            elif await self.is_admin_or_admin_role(member_or_role):
                denied_message = "that's an admin{}, so I can't deny them from entering your AutoRoom.".format(
                    " role" if isinstance(member_or_role, discord.Role) else ""
                )
            elif await self.is_mod_or_mod_role(member_or_role):
                denied_message = "that's a moderator{}, so I can't deny them from entering your AutoRoom.".format(
                    " role" if isinstance(member_or_role, discord.Role) else ""
                )
        if denied_message:
            hint = await ctx.send(
                error(f"{ctx.message.author.mention}, {denied_message}")
            )
            await delete(ctx.message, delay=10)
            await delete(hint, delay=10)
            return False

        overwrites = dict(channel.overwrites)
        do_edit = False
        if not isinstance(member_or_role, list):
            member_or_role = [member_or_role]
        for target in member_or_role:
            if target in overwrites:
                if overwrites[target].view_channel != allow:
                    overwrites[target].update(view_channel=allow)
                    do_edit = True
                if overwrites[target].connect != allow:
                    overwrites[target].update(connect=allow)
                    do_edit = True
            else:
                overwrites[target] = discord.PermissionOverwrite(
                    view_channel=allow, connect=allow
                )
                do_edit = True
        if do_edit:
            await channel.edit(
                overwrites=overwrites,
                reason="AutoRoom: Permission change",
            )
        await ctx.tick()
        await delete(ctx.message, delay=5)
        return True

    @staticmethod
    def _get_current_voice_channel(member: discord.Member):
        """Get the members current voice channel, or None if not in a voice channel."""
        if member.voice:
            return member.voice.channel
        return None

    async def _get_autoroom_info(self, autoroom: discord.VoiceChannel):
        """Get info for an AutoRoom, or None if the voice channel isn't an AutoRoom."""
        if not autoroom:
            return None
        owner_id = await self.config.channel(autoroom).owner()
        if not owner_id:
            return None
        owner = autoroom.guild.get_member(owner_id)
        member_roles = []
        for member_role_id in await self.config.channel(autoroom).member_roles():
            member_role = autoroom.guild.get_role(member_role_id)
            if member_role:
                member_roles.append(member_role)
        if not member_roles:
            member_roles = [autoroom.guild.default_role]
        return {
            "owner": owner,
            "member_roles": member_roles,
        }
