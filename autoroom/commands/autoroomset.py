"""The autoroomset command."""
from abc import ABC
from typing import Union

import discord
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import error

from ..abc import CompositeMetaClass, MixinMeta
from ..pcx_lib import SettingDisplay, checkmark


class AutoRoomSetCommands(MixinMeta, ABC, metaclass=CompositeMetaClass):
    """The autoroomset command."""

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
                        f"AutoRoom - {source_channel.name}"
                    )
                    autoroom_section.add(
                        "Room type",
                        avc_settings["room_type"].capitalize(),
                    )
                    autoroom_section.add(
                        "Destination category",
                        f"#{dest_category.name}"
                        if dest_category
                        else "INVALID CATEGORY",
                    )
                    if "text_channel" in avc_settings and avc_settings["text_channel"]:
                        autoroom_section.add(
                            "Text Channel",
                            "True",
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
                            bitrate_string = f"Guild maximum ({int(ctx.guild.bitrate_limit // 1000)}kbps)"
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
                f"Admins are {'now' if admin_access else 'no longer'} able to join (new) private AutoRooms."
            )
        )

    @access.command()
    async def mod(self, ctx: commands.Context):
        """Allow Moderators to join private channels."""
        mod_access = not await self.config.guild(ctx.guild).mod_access()
        await self.config.guild(ctx.guild).mod_access.set(mod_access)
        await ctx.send(
            checkmark(
                f"Moderators are {'now' if mod_access else 'no longer'} able to join (new) private AutoRooms."
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
                f"**{autoroom_source.mention}** is no longer an AutoRoom Source channel."
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
                        f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                    )
                )
            else:
                await ctx.send(
                    checkmark(
                        f"New AutoRooms created by **{autoroom_source.mention}** will be {room_type}."
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
                        f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
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
                        f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                    )
                )
                return
        await self._send_memberrole_message(ctx, autoroom_source, "Removed!")

    async def _send_memberrole_message(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel, action: str
    ):
        """Send a message showing the current member roles."""
        member_roles = await self.get_member_roles_for_source(autoroom_source)
        if member_roles:
            await ctx.send(
                checkmark(
                    f"{action}\n"
                    f"New AutoRooms created by **{autoroom_source.mention}** will be visible by users "
                    "with any of the following roles:\n"
                    f"{', '.join([role.mention for role in member_roles])}"
                )
            )
        else:
            await ctx.send(
                checkmark(
                    f"{action}\n"
                    f"New AutoRooms created by **{autoroom_source.mention}** will be visible by all users."
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
                        f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                    )
                )
            else:
                await ctx.send(
                    checkmark(
                        f"New AutoRooms created by **{autoroom_source.mention}** "
                        f"will use the **{room_type.capitalize()}** format."
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
                        f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
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
                        f"New AutoRooms created by **{autoroom_source.mention}** will have the default bitrate."
                    )
                )
            elif bitrate_kbps == "max":
                settings["bitrate"] = "max"
                await ctx.send(
                    checkmark(
                        f"New AutoRooms created by **{autoroom_source.mention}** "
                        "will have the max bitrate allowed by the guild."
                    )
                )
            elif isinstance(bitrate_kbps, int):
                bitrate_kbps = self.normalize_bitrate(bitrate_kbps * 1000, ctx.guild)
                settings["bitrate"] = int(bitrate_kbps)
                await ctx.send(
                    checkmark(
                        f"New AutoRooms created by **{autoroom_source.mention}** "
                        f"will have a bitrate of {int(bitrate_kbps) // 1000}kbps."
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
                        f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
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
                        f"New AutoRooms created by **{autoroom_source.mention}** will not have a user limit."
                    )
                )
            else:
                settings["user_limit"] = user_limit
                await ctx.send(
                    checkmark(
                        f"New AutoRooms created by **{autoroom_source.mention}** "
                        f"will have a user limit of {user_limit}."
                    )
                )

    @modify.command()
    async def text(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
    ):
        """Toggle if a text channel should be created as well."""
        async with self.config.guild(ctx.guild).auto_voice_channels() as avcs:
            try:
                settings = avcs[str(autoroom_source.id)]
            except KeyError:
                await ctx.send(
                    error(
                        f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                    )
                )
                return
            if "text_channel" in settings and settings["text_channel"]:
                del settings["text_channel"]
            else:
                settings["text_channel"] = True
            await ctx.send(
                checkmark(
                    f"New AutoRooms created by **{autoroom_source.mention}** will "
                    f"{'now' if 'text_channel' in settings else 'no longer'} get their own text channel."
                )
            )
