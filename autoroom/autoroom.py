"""AutoRoom cog for Red-DiscordBot by PhasecoreX."""
import asyncio
from typing import List, Union

import discord
from redbot.core import Config, commands

from .abc import CompositeMetaClass
from .commands import Commands

__author__ = "PhasecoreX"


class AutoRoom(Commands, commands.Cog, metaclass=CompositeMetaClass):
    """Automatic voice channel management.

    This cog allows for admins to designate existing voice channels as
    AutoRoom Sources. When a user joins these channels, they will have
    a new voice channel created in a specified category and be moved
    into it. The user is now the owner of this created AutoRoom,
    and is free to modify it's settings. Once all users have left the
    created AutoRoom, it will be deleted automatically.
    """

    default_global_settings = {"schema_version": 0}
    default_guild_settings = {
        "auto_voice_channels": {},
        "admin_access": True,
        "mod_access": False,
    }
    default_channel_settings = {
        "owner": None,
        "member_roles": [],
        "associated_text_channel": None,
    }
    bitrate_min_kbps = 8
    user_limit_max = 99

    def __init__(self, bot):
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)
        self.config.register_channel(**self.default_channel_settings)
        self.autoroom_create_lock: asyncio.Lock = asyncio.Lock()

    async def initialize(self):
        """Perform setup actions before loading cog."""
        await self._migrate_config()
        self.bot.loop.create_task(self._cleanup_autorooms())

    async def _migrate_config(self):
        """Perform some configuration migrations."""
        schema_version = await self.config.schema_version()

        if schema_version < 1:
            # Migrate private -> room_type
            guild_dict = await self.config.all_guilds()
            for guild_id, guild_info in guild_dict.items():
                async with self.config.guild_from_id(
                    guild_id
                ).auto_voice_channels() as avcs:
                    for avc_settings in avcs.values():
                        avc_settings["room_type"] = (
                            "private" if avc_settings["private"] else "public"
                        )
                        del avc_settings["private"]
            await self.config.schema_version.set(1)

        if schema_version < 2:
            # Migrate member_role -> per auto_voice_channel member_roles
            guild_dict = await self.config.all_guilds()
            for guild_id, guild_info in guild_dict.items():
                member_role = guild_info.get("member_role", False)
                if member_role:
                    async with self.config.guild_from_id(
                        guild_id
                    ).auto_voice_channels() as avcs:
                        for avc_settings in avcs.values():
                            avc_settings["member_roles"] = [member_role]
                    await self.config.guild_from_id(guild_id).clear_raw("member_role")
            await self.config.schema_version.set(2)

    async def _cleanup_autorooms(self):
        """Remove non-existent AutoRooms from the config."""
        await self.bot.wait_until_ready()
        voice_channel_dict = await self.config.all_channels()
        for voice_channel_id, voice_channel_settings in voice_channel_dict.items():
            voice_channel = self.bot.get_channel(voice_channel_id)
            if voice_channel:
                await self._process_autoroom_delete(voice_channel)
            else:
                text_channel = (
                    self.bot.get_channel(
                        voice_channel_settings["associated_text_channel"]
                    )
                    if "associated_text_channel" in voice_channel_settings
                    else None
                )
                if (
                    text_channel
                    and text_channel.permissions_for(
                        text_channel.guild.me
                    ).manage_channels
                ):
                    await text_channel.delete(
                        reason="AutoRoom: Associated voice channel deleted."
                    )
                await self.config.channel_from_id(voice_channel_id).clear()

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, guild_channel: discord.abc.GuildChannel):
        """Clean up config when an AutoRoom is deleted (either by the bot or the user)."""
        if not isinstance(guild_channel, discord.VoiceChannel):
            return
        text_channel_id = await self.config.channel(
            guild_channel
        ).associated_text_channel()
        text_channel = (
            guild_channel.guild.get_channel(text_channel_id)
            if text_channel_id
            else None
        )
        if (
            text_channel
            and text_channel.permissions_for(text_channel.guild.me).manage_channels
        ):
            await text_channel.delete(
                reason="AutoRoom: Associated voice channel deleted."
            )
        await self.config.channel(guild_channel).clear()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Do voice channel stuff when users move about channels."""
        if await self.bot.cog_disabled_in_guild(self, member.guild):
            return
        auto_voice_channels = await self.config.guild(
            member.guild
        ).auto_voice_channels()
        # Nonexistent (deleted) source channel cleanup
        avc_delete = []
        for avc_id in auto_voice_channels:
            if not member.guild.get_channel(int(avc_id)):
                avc_delete.append(avc_id)
        if avc_delete:
            for avc_id in avc_delete:
                del auto_voice_channels[avc_id]
            await self.config.guild(member.guild).auto_voice_channels.set(
                auto_voice_channels
            )
        # If user left a voice channel that isn't an AutoRoom Source, do cleanup
        if before.channel and str(before.channel.id) not in auto_voice_channels:
            if not await self._process_autoroom_delete(before.channel):
                # AutoRoom wasn't deleted, so update text channel perms
                await self._process_autoroom_text_perms(before.channel)
        # If user entered a voice channel...
        if after.channel:
            # If user entered an AutoRoom Source channel, create new AutoRoom
            if str(after.channel.id) in auto_voice_channels:
                await self._process_autoroom_create(member.guild, auto_voice_channels)
            # If user entered an AutoRoom, allow them into the associated text channel
            else:
                await self._process_autoroom_text_perms(after.channel)

    async def _process_autoroom_create(self, guild, auto_voice_channels):
        """Create a voice channel for each member in an AutoRoom Source channel."""
        if (
            not guild.me.guild_permissions.manage_channels
            or not guild.me.guild_permissions.move_members
        ):
            return
        additional_allowed_roles = []
        if await self.config.guild(guild).mod_access():
            # Add mod roles to be allowed
            additional_allowed_roles += await self.bot.get_mod_roles(guild)
        if await self.config.guild(guild).admin_access():
            # Add admin roles to be allowed
            additional_allowed_roles += await self.bot.get_admin_roles(guild)
        async with self.autoroom_create_lock:
            for avc_id, avc_settings in auto_voice_channels.items():
                source_channel = guild.get_channel(int(avc_id))
                dest_category = guild.get_channel(avc_settings["dest_category_id"])
                if not source_channel or not dest_category:
                    continue
                members = source_channel.members
                for member in members:
                    overwrites = {
                        guild.me: discord.PermissionOverwrite(
                            view_channel=True,
                            connect=True,
                            manage_channels=True,
                            manage_roles=True,
                            move_members=True,
                        ),
                        member: discord.PermissionOverwrite(
                            view_channel=True,
                            connect=True,
                            manage_channels=True,
                        ),
                    }
                    member_roles = await self.get_member_roles_for_source(
                        source_channel
                    )
                    for member_role in member_roles or [guild.default_role]:
                        overwrites[member_role] = discord.PermissionOverwrite(
                            view_channel=avc_settings["room_type"] == "public",
                            connect=avc_settings["room_type"] == "public",
                        )
                    if guild.default_role not in overwrites:
                        # We have a member role, deny @everyone
                        overwrites[guild.default_role] = discord.PermissionOverwrite(
                            view_channel=False, connect=False
                        )
                    for role in additional_allowed_roles:
                        # Add all the mod/admin roles, if required
                        overwrites[role] = discord.PermissionOverwrite(
                            view_channel=True, connect=True
                        )
                    new_channel_name = ""
                    if "channel_name_type" in avc_settings:
                        if avc_settings["channel_name_type"] == "game":
                            for activity in member.activities:
                                if activity.type.value == 0:
                                    new_channel_name = activity.name
                                    break
                    if not new_channel_name:
                        new_channel_name = f"{member.display_name}'s Room"
                    options = {}
                    if "bitrate" in avc_settings:
                        if avc_settings["bitrate"] == "max":
                            options["bitrate"] = guild.bitrate_limit
                        else:
                            options["bitrate"] = self.normalize_bitrate(
                                avc_settings["bitrate"], guild
                            )
                    if "user_limit" in avc_settings:
                        options["user_limit"] = self.normalize_user_limit(
                            avc_settings["user_limit"]
                        )
                    new_voice_channel = await guild.create_voice_channel(
                        name=new_channel_name,
                        category=dest_category,
                        reason="AutoRoom: New AutoRoom needed.",
                        overwrites=overwrites,
                        **options,
                    )
                    await member.move_to(
                        new_voice_channel, reason="AutoRoom: Move user to new AutoRoom."
                    )
                    await self.config.channel(new_voice_channel).owner.set(member.id)
                    if member_roles:
                        await self.config.channel(new_voice_channel).member_roles.set(
                            [member_role.id for member_role in member_roles]
                        )

                    if "text_channel" in avc_settings and avc_settings["text_channel"]:
                        overwrites = {
                            guild.default_role: discord.PermissionOverwrite(
                                read_messages=False
                            ),
                            guild.me: discord.PermissionOverwrite(
                                read_messages=True,
                                manage_channels=True,
                                manage_roles=True,
                                manage_messages=True,
                            ),
                            member: discord.PermissionOverwrite(
                                read_messages=True,
                                manage_channels=True,
                                manage_messages=True,
                            ),
                        }
                        new_text_channel = await guild.create_text_channel(
                            name="AutoRoom Text Channel",
                            category=dest_category,
                            reason="AutoRoom: New text channel needed.",
                            overwrites=overwrites,
                        )
                        await new_text_channel.send(
                            f"{member.display_name}, "
                            "this is your own text channel that anyone in your AutoRoom can use."
                        )
                        await self.config.channel(
                            new_voice_channel
                        ).associated_text_channel.set(new_text_channel.id)

                    await asyncio.sleep(2)

    async def _process_autoroom_delete(self, voice_channel: discord.VoiceChannel):
        """Delete AutoRoom if empty."""
        if (
            not voice_channel.members
            and await self.config.channel(voice_channel).owner()
            and voice_channel.guild.me.permissions_in(voice_channel).manage_channels
        ):
            try:
                await voice_channel.delete(reason="AutoRoom: Channel empty.")
            except discord.NotFound:
                pass  # Sometimes this happens when the user manually deletes their channel
            return True
        return False

    async def _process_autoroom_text_perms(self, autoroom: discord.VoiceChannel):
        """Allow or deny a user access to the text channel associated to an AutoRoom."""
        text_channel_id = await self.config.channel(autoroom).associated_text_channel()
        text_channel = (
            autoroom.guild.get_channel(text_channel_id) if text_channel_id else None
        )
        if text_channel:
            do_edit = False
            overwrites = dict(text_channel.overwrites)
            to_delete = []
            # Remove read perms for users not in autoroom
            for member in overwrites:
                if (
                    isinstance(member, discord.Member)
                    and member not in autoroom.members
                    and member != autoroom.guild.me
                ):
                    overwrites[member].update(read_messages=None)
                    if overwrites[member].is_empty():
                        to_delete.append(member)
                    do_edit = True
            for member in to_delete:
                del overwrites[member]
            # Add read perms for users in autoroom
            for member in autoroom.members:
                if member in overwrites:
                    if not overwrites[member].read_messages:
                        overwrites[member].update(read_messages=True)
                        do_edit = True
                else:
                    overwrites[member] = discord.PermissionOverwrite(read_messages=True)
                    do_edit = True
            if do_edit:
                await text_channel.edit(
                    overwrites=overwrites,
                    reason="AutoRoom: Permission change",
                )

    async def get_member_roles_for_source(
        self, autoroom_source: discord.VoiceChannel
    ) -> List[discord.Role]:
        """Return a list of member roles for an AutoRoom Source."""
        roles = []
        async with self.config.guild(
            autoroom_source.guild
        ).auto_voice_channels() as avcs:
            try:
                del_roles = []
                for member_role_id in avcs[str(autoroom_source.id)]["member_roles"]:
                    member_role = autoroom_source.guild.get_role(member_role_id)
                    if member_role:
                        roles.append(member_role)
                    else:
                        del_roles.append(member_role_id)
                for del_role in del_roles:
                    avcs[str(autoroom_source.id)]["member_roles"].remove(del_role)
                if not avcs[str(autoroom_source.id)]["member_roles"]:
                    del avcs[str(autoroom_source.id)]["member_roles"]
            except KeyError:
                pass
        return roles

    async def is_admin_or_admin_role(self, who: Union[discord.Role, discord.Member]):
        """Check if a member (or role) is an admin (role).

        Also takes into account if the setting is enabled.
        """
        if await self.config.guild(who.guild).admin_access():
            if isinstance(who, discord.Role):
                return who in await self.bot.get_admin_roles(who.guild)
            if isinstance(who, discord.Member):
                return await self.bot.is_admin(who)
        return False

    async def is_mod_or_mod_role(self, who: Union[discord.Role, discord.Member]):
        """Check if a member (or role) is a mod (role).

        Also takes into account if the setting is enabled.
        """
        if await self.config.guild(who.guild).mod_access():
            if isinstance(who, discord.Role):
                return who in await self.bot.get_mod_roles(who.guild)
            if isinstance(who, discord.Member):
                return await self.bot.is_mod(who)
        return False

    def normalize_bitrate(self, bitrate: int, guild: discord.Guild):
        """Return a normalized bitrate value."""
        return min(max(bitrate, self.bitrate_min_kbps * 1000), guild.bitrate_limit)

    def normalize_user_limit(self, users: int):
        """Return a normalized user limit value."""
        return min(max(users, 0), self.user_limit_max)
