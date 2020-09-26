"""AutoRoom cog for Red-DiscordBot by PhasecoreX."""
import asyncio
import datetime

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import error, humanize_timedelta

from .pcx_lib import SettingDisplay, checkmark, delete

__author__ = "PhasecoreX"


class AutoRoom(commands.Cog):
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
        "member_role": None,
        "admin_access": True,
        "mod_access": False,
    }

    def __init__(self, bot):
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)
        self.autoroom_create_lock: asyncio.Lock = asyncio.Lock()

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def autoroomset(self, ctx: commands.Context):
        """Configure the AutoRoom cog."""
        pass

    @autoroomset.command()
    async def settings(self, ctx: commands.Context):
        """Display current settings."""
        guild_section = SettingDisplay("Guild Settings")
        member_role = None
        member_role_id = await self.config.guild(ctx.message.guild).member_role()
        if member_role_id:
            member_role = ctx.message.guild.get_role(member_role_id)
        guild_section.add("Member Role", member_role.name if member_role else "Not set")
        guild_section.add(
            "Admin private channel access",
            await self.config.guild(ctx.message.guild).admin_access(),
        )
        guild_section.add(
            "Moderator private channel access",
            await self.config.guild(ctx.message.guild).mod_access(),
        )

        autoroom_sections = []
        async with self.config.guild(ctx.message.guild).auto_voice_channels() as avcs:
            for avc_id, avc_settings in avcs.items():
                source_channel = ctx.message.guild.get_channel(int(avc_id))
                if source_channel:
                    dest_category = ctx.message.guild.get_channel(
                        avc_settings["dest_category_id"]
                    )
                    autoroom_section = SettingDisplay(
                        "AutoRoom - {}".format(source_channel.name)
                    )
                    autoroom_section.add(
                        "Room type",
                        "Private" if avc_settings["private"] else "Public",
                    )
                    autoroom_section.add(
                        "Destination category",
                        "#{}".format(dest_category.name)
                        if dest_category
                        else "INVALID CATEGORY",
                    )
                    autoroom_section.add(
                        "Room name format",
                        avc_settings["channel_name_type"].capitalize()
                        if "channel_name_type" in avc_settings
                        else "Username",
                    )
                    autoroom_sections.append(autoroom_section)

        await ctx.send(guild_section.display(*autoroom_sections))

    @autoroomset.group()
    async def access(self, ctx: commands.Context):
        """Control access to all AutoRooms."""
        pass

    @access.command()
    async def memberrole(
        self,
        ctx: commands.Context,
        role: discord.Role = None,
    ):
        """Limit AutoRoom visibility to a member role.

        When set, only users with the specified role can see AutoRooms. Leave `role` empty to disable.
        """
        await self.config.guild(ctx.message.guild).member_role.set(
            role.id if role else None
        )
        if role:
            await ctx.send(
                checkmark(
                    "New AutoRooms will only be available to users with the {} role.".format(
                        role
                    )
                )
            )
        else:
            await ctx.send(checkmark("New AutoRooms can be used by any user."))

    @access.command()
    async def admin(self, ctx: commands.Context):
        """Allow Admins to join private channels."""
        admin_access = not await self.config.guild(ctx.message.guild).admin_access()
        await self.config.guild(ctx.message.guild).admin_access.set(admin_access)
        await ctx.send(
            checkmark(
                "Admins are {} able to join (new) private AutoRooms.".format(
                    "now" if admin_access else "no longer"
                )
            )
        )

    @access.command()
    async def mod(self, ctx: commands.Context):
        """Allow Moderators to join private channels."""
        mod_access = not await self.config.guild(ctx.message.guild).mod_access()
        await self.config.guild(ctx.message.guild).mod_access.set(mod_access)
        await ctx.send(
            checkmark(
                "Moderators are {} able to join (new) private AutoRooms.".format(
                    "now" if mod_access else "no longer"
                )
            )
        )

    @autoroomset.command(aliases=["enable"])
    async def create(
        self,
        ctx: commands.Context,
        source_voice_channel: discord.VoiceChannel,
        dest_category: discord.CategoryChannel,
        private: bool = False,
    ):
        """Create an AutoRoom Source.

        Anyone joining the `source_voice_channel` will automatically have a new voice channel
        (AutoRoom) created in the `dest_category`, and then be moved into it.

        If `private` is true, the created channel will be private, where the user can modify
        the permissions of their channel to allow others in.
        """
        async with self.config.guild(ctx.message.guild).auto_voice_channels() as avcs:
            vc_id = str(source_voice_channel.id)
            avcs[vc_id] = {}
            avcs[vc_id]["dest_category_id"] = dest_category.id
            avcs[vc_id]["private"] = private
        await ctx.send(
            checkmark(
                "{} is now an AutoRoom Source, and will create new {} voice channels in the {} category. "
                "Check out `[p]autoroomset modify` if you'd like to configure this further.".format(
                    source_voice_channel.mention,
                    "private" if private else "public",
                    dest_category.mention,
                )
            )
        )

    @autoroomset.command(aliases=["disable"])
    async def remove(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
    ):
        """Remove an AutoRoom Source."""
        async with self.config.guild(ctx.message.guild).auto_voice_channels() as avcs:
            try:
                del avcs[str(autoroom_source.id)]
            except KeyError:
                pass
        await ctx.send(
            checkmark(
                "{} is no longer an AutoRoom Source channel.".format(
                    autoroom_source.mention
                )
            )
        )

    @autoroomset.group(aliased=["edit"])
    async def modify(self, ctx: commands.Context):
        """Modify an existing AutoRoom Source."""
        pass

    @modify.command(name="public")
    async def modify_public(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """Set an AutoRoom Source to create public AutoRooms."""
        await self._save_public_private(ctx, autoroom_source, False)

    @modify.command(name="private")
    async def modify_private(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """Set an AutoRoom Source to create private AutoRooms."""
        await self._save_public_private(ctx, autoroom_source, True)

    async def _save_public_private(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        private: bool,
    ):
        """Save the public/private setting."""
        async with self.config.guild(ctx.message.guild).auto_voice_channels() as avcs:
            try:
                avcs[str(autoroom_source.id)]["private"] = private
            except KeyError:
                await ctx.send(
                    error(
                        "{} is not an AutoRoom Source channel.".format(
                            autoroom_source.mention
                        )
                    )
                )
            else:
                await ctx.send(
                    checkmark(
                        "New AutoRooms created by {} will be {}.".format(
                            autoroom_source.mention, "private" if private else "public"
                        )
                    )
                )

    @modify.group()
    async def name(self, ctx: commands.Context):
        """Choose the default name format of an AutoRoom."""
        pass

    @name.command()
    async def username(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """Default format: PhasecoreX's Room."""
        await self._save_room_name(ctx, autoroom_source, "username")

    @name.command()
    async def game(self, ctx: commands.Context, autoroom_source: discord.VoiceChannel):
        """The users current playing game, otherwise the username format."""
        await self._save_room_name(ctx, autoroom_source, "game")

    async def _save_room_name(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        room_type: str,
    ):
        """Save the room name type."""
        async with self.config.guild(ctx.message.guild).auto_voice_channels() as avcs:
            try:
                avcs[str(autoroom_source.id)]["channel_name_type"] = room_type
            except KeyError:
                await ctx.send(
                    error(
                        "{} is not an AutoRoom Source channel.".format(
                            autoroom_source.mention
                        )
                    )
                )
            else:
                await ctx.send(
                    checkmark(
                        "New AutoRooms created by {} will use the {} format.".format(
                            autoroom_source.mention, room_type.capitalize()
                        )
                    )
                )

    @commands.group()
    @commands.guild_only()
    async def autoroom(self, ctx: commands.Context):
        """Manage your AutoRoom."""
        pass

    @autoroom.command(name="settings", aliases=["info"])
    async def autoroom_settings(self, ctx: commands.Context):
        """Display current settings."""
        member_channel = self._get_current_voice_channel(ctx.message.author)
        if not member_channel or not await self._is_autoroom(member_channel):
            hint = await ctx.send(
                error(
                    "{}, you are not in an AutoRoom.".format(ctx.message.author.mention)
                )
            )
            await delete(ctx.message, delay=5)
            await delete(hint, delay=5)
            return

        room_owners = await self._get_room_owners(member_channel)
        room_settings = SettingDisplay("Room Settings")
        room_settings.add(
            "Owner" if len(room_owners) == 1 else "Owners",
            ", ".join([owner.name for owner in room_owners]),
        )

        base_member_role = await self._get_base_member_role(ctx.guild)
        mode = "???"
        if base_member_role in member_channel.overwrites:
            mode = (
                "Public"
                if member_channel.overwrites[base_member_role].connect
                else "Private"
            )
        room_settings.add("Mode", mode)

        room_settings.add("Bitrate", "{}kbps".format(member_channel.bitrate // 1000))
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
    async def allow(self, ctx: commands.Context, member: discord.Member):
        """Allow a user into your AutoRoom."""
        await self._process_allow_deny(ctx, True, member=member)

    @autoroom.command(aliases=["ban"])
    async def deny(self, ctx: commands.Context, member: discord.Member):
        """Deny a user from accessing your AutoRoom.

        If they are already in your AutoRoom, they will be disconnected.
        """
        if await self._process_allow_deny(ctx, False, member=member):
            try:
                if member in ctx.message.author.voice.channel.members:
                    await member.move_to(None, reason="AutoRoom: Deny user")
            except AttributeError:
                pass
            except discord.Forbidden:
                pass  # Shouldn't happen unless someone screws with channel permissions.

    async def _get_base_member_role(self, guild: discord.Guild) -> discord.Role:
        """Return the base member role (could be @everyone, or whatever the member role is)."""
        member_role_id = await self.config.guild(guild).member_role()
        if member_role_id:
            return guild.get_role(member_role_id) or guild.default_role
        return guild.default_role

    async def _process_allow_deny(
        self, ctx: commands.Context, allow: bool, *, member: discord.Member = None
    ) -> bool:
        """Actually do channel edit for allow/deny."""
        channel = self._get_current_voice_channel(ctx.message.author)
        if not channel or not await self._is_autoroom(channel):
            hint = await ctx.send(
                error(
                    "{}, you are not in an AutoRoom.".format(ctx.message.author.mention)
                )
            )
            await delete(ctx.message, delay=5)
            await delete(hint, delay=5)
            return False
        if not await self._is_autoroom_owner(
            ctx.message.author, channel, skip_autoroom_check=True
        ):
            hint = await ctx.send(
                error(
                    "{}, you are not the owner of this AutoRoom.".format(
                        ctx.message.author.mention
                    )
                )
            )
            await delete(ctx.message, delay=5)
            await delete(hint, delay=5)
            return False

        denied_message = ""
        if not member:
            member = await self._get_base_member_role(ctx.guild)
        elif not allow:
            if member == ctx.guild.me:
                denied_message = "why would I deny myself from entering your AutoRoom?"
            elif member == ctx.message.author:
                denied_message = "don't be so hard on yourself! This is your AutoRoom!"
            elif member == ctx.guild.owner:
                denied_message = "I don't know if you know this, but that's the guild owner... I can't deny them from entering your AutoRoom."
            elif await self.config.guild(
                ctx.guild
            ).admin_access() and await self.bot.is_admin(member):
                denied_message = (
                    "that's an admin, so I can't deny them from entering your AutoRoom."
                )
            elif await self.config.guild(
                ctx.guild
            ).mod_access() and await self.bot.is_mod(member):
                denied_message = "that's a moderator, so I can't deny them from entering your AutoRoom."
        if denied_message:
            hint = await ctx.send(
                error("{}, {}".format(ctx.message.author.mention, denied_message))
            )
            await delete(ctx.message, delay=10)
            await delete(hint, delay=10)
            return False

        overwrites = dict(channel.overwrites)
        do_edit = False
        if member in overwrites:
            if overwrites[member].connect != allow:
                overwrites[member].update(connect=allow)
                do_edit = True
        else:
            overwrites[member] = discord.PermissionOverwrite(connect=allow)
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

    async def _get_room_owners(self, channel: discord.VoiceChannel):
        """Return list of users with an overwrite of manage_channels True."""
        return [
            owner
            for owner, perms in channel.overwrites.items()
            if isinstance(owner, discord.Member)
            and perms.manage_channels
            and owner != channel.guild.me
        ]

    async def _is_autoroom(self, channel: discord.VoiceChannel):
        """Check if a Voice Channel is actually an AutoRoom."""
        auto_voice_channels = await self.config.guild(
            channel.guild
        ).auto_voice_channels()
        if str(channel.id) in auto_voice_channels:
            # AutoRoom Source channel
            return False
        for avc_settings in auto_voice_channels.values():
            if channel.category_id == avc_settings["dest_category_id"]:
                return True
        return False

    async def _is_autoroom_owner(
        self,
        member: discord.Member,
        channel: discord.VoiceChannel,
        *,
        skip_autoroom_check: bool = False
    ):
        """Check if a member is the owner of an AutoRoom."""
        if not channel:
            # Not in a voice channel
            return False
        if member not in await self._get_room_owners(channel):
            return False
        return skip_autoroom_check or await self._is_autoroom(channel)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Do voice channel stuff when users move about channels."""
        if await self.bot.cog_disabled_in_guild(self, member.guild):
            return
        auto_voice_channels = await self.config.guild(
            member.guild
        ).auto_voice_channels()
        # Nonexistant (deleted) source channel cleanup
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
        if not before.channel or str(before.channel.id) not in auto_voice_channels:
            await self._process_autoroom_delete(member.guild, auto_voice_channels)
        # If user entered an AutoRoom Source channel, create new AutoRoom
        if after.channel and str(after.channel.id) in auto_voice_channels:
            await self._process_autoroom_create(member.guild, auto_voice_channels)

    async def _process_autoroom_create(self, guild, auto_voice_channels):
        """Create a voice channel for each member in an AutoRoom Source channel."""
        if not guild.me.guild_permissions.manage_channels:
            return
        base_member_role = await self._get_base_member_role(guild)
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
                        base_member_role: discord.PermissionOverwrite(
                            view_channel=True, connect=not avc_settings["private"]
                        ),
                    }
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
                        new_channel_name = "{}'s Room".format(member.name)
                    new_channel = await guild.create_voice_channel(
                        name=new_channel_name,
                        category=dest_category,
                        reason="AutoRoom: New channel needed.",
                        overwrites=overwrites,
                    )
                    await member.move_to(
                        new_channel, reason="AutoRoom: Move user to new channel."
                    )
                    await asyncio.sleep(2)

    async def _process_autoroom_delete(self, guild, auto_voice_channels):
        """Delete all empty voice channels in categories."""
        if not guild.me.guild_permissions.manage_channels:
            return
        category_ids = set()
        for avc_id, avc_settings in auto_voice_channels.items():
            category_ids.add(avc_settings["dest_category_id"])
        for category_id in category_ids:
            category = guild.get_channel(category_id)
            if category:
                for vc in category.voice_channels:
                    if str(vc.id) not in auto_voice_channels and not vc.members:
                        await vc.delete(reason="AutoRoom: Channel empty.")
