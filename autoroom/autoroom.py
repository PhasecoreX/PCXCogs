"""AutoRoom cog for Red-DiscordBot by PhasecoreX."""
import asyncio
import datetime
from typing import Union

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
        self.autoroom_create_lock: asyncio.Lock = asyncio.Lock()

    async def initialize(self):
        """Perform setup actions before loading cog."""
        await self._migrate_config()

    async def _migrate_config(self):
        """Perform some configuration migrations."""
        if not await self.config.schema_version():
            guild_dict = await self.config.all_guilds()
            for guild_id, guild_info in guild_dict.items():
                # Migrate private -> room_type
                async with self.config.guild_from_id(
                    guild_id
                ).auto_voice_channels() as avcs:
                    for avc_id, avc_settings in avcs.items():
                        avc_settings["room_type"] = (
                            "private" if avc_settings["private"] else "public"
                        )
                        del avc_settings["private"]
            await self.config.schema_version.set(1)

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
        member_role_id = await self.config.guild(ctx.guild).member_role()
        if member_role_id:
            member_role = ctx.guild.get_role(member_role_id)
        guild_section.add("Member Role", member_role.name if member_role else "Not set")
        guild_section.add(
            "Admin private channel access",
            await self.config.guild(ctx.guild).admin_access(),
        )
        guild_section.add(
            "Moderator private channel access",
            await self.config.guild(ctx.guild).mod_access(),
        )

        autoroom_sections = []
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            for avc_id, avc_settings in avcs.items():
                source_channel = ctx.guild.get_channel(int(avc_id))
                if source_channel:
                    dest_category = ctx.guild.get_channel(
                        avc_settings["dest_category_id"]
                    )
                    autoroom_section = SettingDisplay(
                        "AutoRoom - {}".format(source_channel.name)
                    )
                    autoroom_section.add(
                        "Room type",
                        avc_settings["room_type"].capitalize(),
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
                    bitrate_string = ""
                    if "bitrate" in avc_settings:
                        if avc_settings["bitrate"] == "max":
                            bitrate_string = "Guild maximum ({}kbps)".format(
                                int(ctx.guild.bitrate_limit // 1000)
                            )
                        else:
                            bitrate_string = "{}kbps".format(
                                self.normalize_bitrate(
                                    avc_settings["bitrate"], ctx.guild
                                )
                                // 1000
                            )
                    if bitrate_string:
                        autoroom_section.add("Bitrate", bitrate_string)
                    if "user_limit" in avc_settings:
                        autoroom_section.add(
                            "User Limit",
                            self.normalize_user_limit(avc_settings["user_limit"]),
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
        await self.config.guild(ctx.guild).member_role.set(role.id if role else None)
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
        admin_access = not await self.config.guild(ctx.guild).admin_access()
        await self.config.guild(ctx.guild).admin_access.set(admin_access)
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
        mod_access = not await self.config.guild(ctx.guild).mod_access()
        await self.config.guild(ctx.guild).mod_access.set(mod_access)
        await ctx.send(
            checkmark(
                "Moderators are {} able to join (new) private AutoRooms.".format(
                    "now" if mod_access else "no longer"
                )
            )
        )

    @autoroomset.group(aliases=["enable"])
    async def create(self, ctx: commands.Context):
        """Create an AutoRoom Source.

        Anyone joining an AutoRoom Source will automatically have a new
        voice channel (AutoRoom) created in the destination category,
        and then be moved into it.
        """
        pass

    @create.command(name="public")
    async def create_public(
        self,
        ctx: commands.Context,
        source_voice_channel: discord.VoiceChannel,
        dest_category: discord.CategoryChannel,
    ):
        """Create an AutoRoom Source that creates public AutoRooms.

        The created AutoRooms will allow anyone to join. The AutoRoom owner can
        block specific members from joining their room, or can switch the room to
        private mode to selectively allow members instead.
        """
        await self._create_new_public_private_room(
            ctx, source_voice_channel, dest_category, "public"
        )

    @create.command(name="private")
    async def create_private(
        self,
        ctx: commands.Context,
        source_voice_channel: discord.VoiceChannel,
        dest_category: discord.CategoryChannel,
    ):
        """Create an AutoRoom Source that creates private AutoRooms.

        The created AutoRooms will not allow anyone to join. The AutoRoom owner will
        need to allow specific members to join their room, or can switch the room to
        public mode to selectively block members instead.
        """
        await self._create_new_public_private_room(
            ctx, source_voice_channel, dest_category, "private"
        )

    async def _create_new_public_private_room(
        self,
        ctx: commands.Context,
        source_voice_channel: discord.VoiceChannel,
        dest_category: discord.CategoryChannel,
        room_type: str,
    ):
        """Save the new room settings."""
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            vc_id = str(source_voice_channel.id)
            avcs[vc_id] = {}
            avcs[vc_id]["room_type"] = room_type
            avcs[vc_id]["dest_category_id"] = dest_category.id
        await ctx.send(
            checkmark(
                "{} is now an AutoRoom Source, and will create new {} voice channels in the {} category. "
                "Check out `[p]autoroomset modify` if you'd like to configure this further.".format(
                    source_voice_channel.mention,
                    room_type,
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
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
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
        await self._save_public_private(ctx, autoroom_source, "public")

    @modify.command(name="private")
    async def modify_private(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """Set an AutoRoom Source to create private AutoRooms."""
        await self._save_public_private(ctx, autoroom_source, "private")

    async def _save_public_private(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        room_type: str,
    ):
        """Save the public/private setting."""
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            try:
                avcs[str(autoroom_source.id)]["room_type"] = room_type
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
                            autoroom_source.mention, room_type
                        )
                    )
                )

    @modify.group()
    async def name(self, ctx: commands.Context):
        """Set the default name format of an AutoRoom."""
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
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
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

    @modify.command()
    async def bitrate(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        bitrate_kbps: Union[int, str],
    ):
        """Set the default bitrate of an AutoRoom.

        `bitrate_kbps` can either be a number of kilobits per second, or:
        - `default` - The default bitrate of Discord (usually 64kbps)
        - `max` - The maximum allowed bitrate for the guild
        """
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            try:
                settings = avcs[str(autoroom_source.id)]
            except KeyError:
                await ctx.send(
                    error(
                        "{} is not an AutoRoom Source channel.".format(
                            autoroom_source.mention
                        )
                    )
                )
                return
            if bitrate_kbps == "default" or bitrate_kbps == 0:
                try:
                    del settings["bitrate"]
                except KeyError:
                    pass
                await ctx.send(
                    checkmark(
                        "New AutoRooms created by {} will have the default bitrate.".format(
                            autoroom_source.mention
                        )
                    )
                )
            elif bitrate_kbps == "max":
                settings["bitrate"] = "max"
                await ctx.send(
                    checkmark(
                        "New AutoRooms created by {} will have the max bitrate allowed by the guild.".format(
                            autoroom_source.mention
                        )
                    )
                )
            elif isinstance(bitrate_kbps, int):
                bitrate_kbps = self.normalize_bitrate(bitrate_kbps * 1000, ctx.guild)
                settings["bitrate"] = int(bitrate_kbps)
                await ctx.send(
                    checkmark(
                        "New AutoRooms created by {} will have a bitrate of {}kbps.".format(
                            autoroom_source.mention, int(bitrate_kbps) // 1000
                        )
                    )
                )
            else:
                await ctx.send(
                    error(
                        "`bitrate_kbps` needs to be a number of kilobits per second, "
                        "or either of the strings `default` or `max`"
                    )
                )

    @modify.command()
    async def users(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        user_limit: int,
    ):
        """Set the default user limit of an AutoRoom, or 0 for no limit (default)."""
        user_limit = self.normalize_user_limit(user_limit)
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            try:
                settings = avcs[str(autoroom_source.id)]
            except KeyError:
                await ctx.send(
                    error(
                        "{} is not an AutoRoom Source channel.".format(
                            autoroom_source.mention
                        )
                    )
                )
                return
            if user_limit == 0:
                try:
                    del settings["user_limit"]
                except KeyError:
                    pass
                await ctx.send(
                    checkmark(
                        "New AutoRooms created by {} will not have a user limit.".format(
                            autoroom_source.mention
                        )
                    )
                )
            else:
                settings["user_limit"] = user_limit
                await ctx.send(
                    checkmark(
                        "New AutoRooms created by {} will have a user limit of {}.".format(
                            autoroom_source.mention, user_limit
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
            ", ".join([owner.display_name for owner in room_owners]),
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
                            view_channel=True,
                            connect=avc_settings["room_type"] == "public",
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
                        new_channel_name = "{}'s Room".format(member.display_name)
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
                    new_channel = await guild.create_voice_channel(
                        name=new_channel_name,
                        category=dest_category,
                        reason="AutoRoom: New channel needed.",
                        overwrites=overwrites,
                        **options,
                    )
                    await member.move_to(
                        new_channel, reason="AutoRoom: Move user to new channel."
                    )
                    await asyncio.sleep(2)

    async def _process_autoroom_delete(self, guild, auto_voice_channels):
        """Delete all empty voice channels in categories."""
        category_ids = set()
        for avc_id, avc_settings in auto_voice_channels.items():
            category_ids.add(avc_settings["dest_category_id"])
        for category_id in category_ids:
            category = guild.get_channel(category_id)
            if category:
                for vc in category.voice_channels:
                    if str(vc.id) not in auto_voice_channels and not vc.members:
                        try:
                            await vc.delete(reason="AutoRoom: Channel empty.")
                        except discord.Forbidden:
                            pass  # Shouldn't happen unless someone screws with channel permissions.

    def normalize_bitrate(self, bitrate: int, guild: discord.Guild):
        """Return a normalized bitrate value."""
        return min(max(bitrate, self.bitrate_min_kbps * 1000), guild.bitrate_limit)

    def normalize_user_limit(self, users: int):
        """Return a normalized user limit value."""
        return min(max(users, 0), self.user_limit_max)
