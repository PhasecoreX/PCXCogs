"""AutoRoom cog for Red-DiscordBot by PhasecoreX."""
import asyncio
import datetime
from typing import List, Union

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
        "admin_access": True,
        "mod_access": False,
    }
    default_channel_settings = {
        "owner": None,
        "member_roles": [],
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
        channel_dict = await self.config.all_channels()
        for channel_id in channel_dict:
            if not self.bot.get_channel(channel_id):
                await self.config.channel_from_id(channel_id).clear()

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def autoroomset(self, ctx: commands.Context):
        """Configure the AutoRoom cog."""

    @autoroomset.command()
    async def settings(self, ctx: commands.Context):
        """Display current settings."""
        guild_section = SettingDisplay("Guild Settings")
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
                    if "member_roles" in avc_settings:
                        roles = []
                        for member_role_id in avc_settings["member_roles"]:
                            member_role = ctx.guild.get_role(member_role_id)
                            if member_role:
                                roles.append(member_role.name)
                        if roles:
                            autoroom_section.add(
                                "Member Roles" if len(roles) > 1 else "Member Role",
                                ", ".join(roles),
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

    @autoroomset.group(aliases=["enable", "add"])
    async def create(self, ctx: commands.Context):
        """Create an AutoRoom Source.

        Anyone joining an AutoRoom Source will automatically have a new
        voice channel (AutoRoom) created in the destination category,
        and then be moved into it.
        """

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
                "**{}** is now an AutoRoom Source, and will create new {} voice channels in the **{}** category. "
                "Check out `[p]autoroomset modify` if you'd like to configure this further.".format(
                    source_voice_channel.mention,
                    room_type,
                    dest_category.mention,
                )
            )
        )

    @autoroomset.command(aliases=["disable", "delete", "del"])
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
                "**{}** is no longer an AutoRoom Source channel.".format(
                    autoroom_source.mention
                )
            )
        )

    @autoroomset.group(aliased=["edit"])
    async def modify(self, ctx: commands.Context):
        """Modify an existing AutoRoom Source."""

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
                        "**{}** is not an AutoRoom Source channel.".format(
                            autoroom_source.mention
                        )
                    )
                )
            else:
                await ctx.send(
                    checkmark(
                        "New AutoRooms created by **{}** will be {}.".format(
                            autoroom_source.mention, room_type
                        )
                    )
                )

    @modify.group()
    async def memberrole(self, ctx: commands.Context):
        """Limit AutoRoom visibility to certain member roles.

        When set, only users with the specified role(s) can see AutoRooms.
        """

    @memberrole.command(name="add")
    async def add_memberrole(
        self,
        ctx: commands.Context,
        role: discord.Role,
        autoroom_source: discord.VoiceChannel,
    ):
        """Add a role to the list of member roles allowed to see these AutoRooms."""
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            try:
                if "member_roles" not in avcs[str(autoroom_source.id)]:
                    avcs[str(autoroom_source.id)]["member_roles"] = [role.id]
                elif role.id not in avcs[str(autoroom_source.id)]["member_roles"]:
                    avcs[str(autoroom_source.id)]["member_roles"].append(role.id)
            except KeyError:
                await ctx.send(
                    error(
                        "**{}** is not an AutoRoom Source channel.".format(
                            autoroom_source.mention
                        )
                    )
                )
                return
        await self._send_memberrole_message(ctx, autoroom_source, "Added!")

    @memberrole.command(name="remove")
    async def remove_memberrole(
        self,
        ctx: commands.Context,
        role: discord.Role,
        autoroom_source: discord.VoiceChannel,
    ):
        """Remove a role from the list of member roles allowed to see these AutoRooms."""
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            try:
                if (
                    "member_roles" in avcs[str(autoroom_source.id)]
                    and role.id in avcs[str(autoroom_source.id)]["member_roles"]
                ):
                    avcs[str(autoroom_source.id)]["member_roles"].remove(role.id)
                    if not avcs[str(autoroom_source.id)]["member_roles"]:
                        del avcs[str(autoroom_source.id)]["member_roles"]
            except KeyError:
                await ctx.send(
                    error(
                        "**{}** is not an AutoRoom Source channel.".format(
                            autoroom_source.mention
                        )
                    )
                )
                return
        await self._send_memberrole_message(ctx, autoroom_source, "Removed!")

    async def _send_memberrole_message(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel, action: str
    ):
        """Send a message showing the current member roles."""
        member_roles = await self._get_member_roles_for_source(autoroom_source)
        if member_roles:
            await ctx.send(
                checkmark(
                    "{}\nNew AutoRooms created by **{}** will be visible by users with any of the following roles:\n{}".format(
                        action,
                        autoroom_source.mention,
                        ", ".join([role.mention for role in member_roles]),
                    )
                )
            )
        else:
            await ctx.send(
                checkmark(
                    "{}\nNew AutoRooms created by **{}** will be visible by all users.".format(
                        action, autoroom_source.mention
                    )
                )
            )

    @modify.group()
    async def name(self, ctx: commands.Context):
        """Set the default name format of an AutoRoom."""

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
                        "**{}** is not an AutoRoom Source channel.".format(
                            autoroom_source.mention
                        )
                    )
                )
            else:
                await ctx.send(
                    checkmark(
                        "New AutoRooms created by **{}** will use the **{}** format.".format(
                            autoroom_source.mention, room_type.capitalize()
                        )
                    )
                )

    @modify.command()
    async def bitrate(
        self,
        ctx: commands.Context,
        bitrate_kbps: Union[int, str],
        autoroom_source: discord.VoiceChannel,
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
                        "**{}** is not an AutoRoom Source channel.".format(
                            autoroom_source.mention
                        )
                    )
                )
                return
            if bitrate_kbps in ("default", 0):
                try:
                    del settings["bitrate"]
                except KeyError:
                    pass
                await ctx.send(
                    checkmark(
                        "New AutoRooms created by **{}** will have the default bitrate.".format(
                            autoroom_source.mention
                        )
                    )
                )
            elif bitrate_kbps == "max":
                settings["bitrate"] = "max"
                await ctx.send(
                    checkmark(
                        "New AutoRooms created by **{}** will have the max bitrate allowed by the guild.".format(
                            autoroom_source.mention
                        )
                    )
                )
            elif isinstance(bitrate_kbps, int):
                bitrate_kbps = self.normalize_bitrate(bitrate_kbps * 1000, ctx.guild)
                settings["bitrate"] = int(bitrate_kbps)
                await ctx.send(
                    checkmark(
                        "New AutoRooms created by **{}** will have a bitrate of {}kbps.".format(
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
        user_limit: int,
        autoroom_source: discord.VoiceChannel,
    ):
        """Set the default user limit of an AutoRoom, or 0 for no limit (default)."""
        user_limit = self.normalize_user_limit(user_limit)
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            try:
                settings = avcs[str(autoroom_source.id)]
            except KeyError:
                await ctx.send(
                    error(
                        "**{}** is not an AutoRoom Source channel.".format(
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
                        "New AutoRooms created by **{}** will not have a user limit.".format(
                            autoroom_source.mention
                        )
                    )
                )
            else:
                settings["user_limit"] = user_limit
                await ctx.send(
                    checkmark(
                        "New AutoRooms created by **{}** will have a user limit of {}.".format(
                            autoroom_source.mention, user_limit
                        )
                    )
                )

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
                error(
                    "{}, you are not in an AutoRoom.".format(ctx.message.author.mention)
                )
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
            if not channel:
                return
            for member in channel.members:
                if not member.permissions_in(channel).connect:
                    try:
                        await member.move_to(None, reason="AutoRoom: Deny user")
                    except discord.Forbidden:
                        pass  # Shouldn't happen unless someone screws with channel permissions.

    async def _process_allow_deny(
        self,
        ctx: commands.Context,
        allow: bool,
        *,
        member_or_role: Union[discord.Role, discord.Member] = None
    ) -> bool:
        """Actually do channel edit for allow/deny."""
        channel = self._get_current_voice_channel(ctx.message.author)
        autoroom_info = await self._get_autoroom_info(channel)
        if not autoroom_info:
            hint = await ctx.send(
                error(
                    "{}, you are not in an AutoRoom.".format(ctx.message.author.mention)
                )
            )
            await delete(ctx.message, delay=5)
            await delete(hint, delay=5)
            return False
        if ctx.message.author != autoroom_info["owner"]:
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
                denied_message = "I don't know if you know this, but that's the guild owner... I can't deny them from entering your AutoRoom."
            elif await self._is_admin_or_admin_role(member_or_role):
                denied_message = "that's an admin{}, so I can't deny them from entering your AutoRoom.".format(
                    " role" if isinstance(member_or_role, discord.Role) else ""
                )
            elif await self._is_mod_or_mod_role(member_or_role):
                denied_message = "that's a moderator{}, so I can't deny them from entering your AutoRoom.".format(
                    " role" if isinstance(member_or_role, discord.Role) else ""
                )
        if denied_message:
            hint = await ctx.send(
                error("{}, {}".format(ctx.message.author.mention, denied_message))
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

    async def _get_member_roles_for_source(
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
            except KeyError:
                pass
        return roles

    async def _is_admin_or_admin_role(self, who: Union[discord.Role, discord.Member]):
        """Check if a member (or role) is an admin (role).

        Also takes into account if the setting is enabled.
        """
        if await self.config.guild(who.guild).admin_access():
            if isinstance(who, discord.Role):
                return who in await self.bot.get_admin_roles(who.guild)
            if isinstance(who, discord.Member):
                return await self.bot.is_admin(who)
        return False

    async def _is_mod_or_mod_role(self, who: Union[discord.Role, discord.Member]):
        """Check if a member (or role) is a mod (role).

        Also takes into account if the setting is enabled.
        """
        if await self.config.guild(who.guild).mod_access():
            if isinstance(who, discord.Role):
                return who in await self.bot.get_mod_roles(who.guild)
            if isinstance(who, discord.Member):
                return await self.bot.is_mod(who)
        return False

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
                    member_roles = await self._get_member_roles_for_source(
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
                    await self.config.channel(new_channel).owner.set(member.id)
                    if member_roles:
                        await self.config.channel(new_channel).member_roles.set(
                            [member_role.id for member_role in member_roles]
                        )
                    await asyncio.sleep(2)

    async def _process_autoroom_delete(self, guild, auto_voice_channels):
        """Delete all empty voice channels in categories."""
        category_ids = set()
        for avc_settings in auto_voice_channels.values():
            category_ids.add(avc_settings["dest_category_id"])
        for category_id in category_ids:
            category = guild.get_channel(category_id)
            if category:
                for voice_channel in category.voice_channels:
                    if (
                        str(voice_channel.id) not in auto_voice_channels
                        and not voice_channel.members
                    ):
                        try:
                            await voice_channel.delete(
                                reason="AutoRoom: Channel empty."
                            )
                            await self.config.channel(voice_channel).clear()
                        except discord.Forbidden:
                            pass  # Shouldn't happen unless someone screws with channel permissions.

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Clean up config if a user manually deletes their AutoRoom."""
        await self.config.channel(channel).clear()

    def normalize_bitrate(self, bitrate: int, guild: discord.Guild):
        """Return a normalized bitrate value."""
        return min(max(bitrate, self.bitrate_min_kbps * 1000), guild.bitrate_limit)

    def normalize_user_limit(self, users: int):
        """Return a normalized user limit value."""
        return min(max(users, 0), self.user_limit_max)
