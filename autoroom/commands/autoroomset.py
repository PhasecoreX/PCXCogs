"""The autoroomset command."""
import asyncio
from abc import ABC

import discord
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import error, info
from redbot.core.utils.predicates import MessagePredicate

from ..abc import CompositeMetaClass, MixinMeta
from ..pcx_lib import SettingDisplay, checkmark

channel_name_template = {"username": "{username}'s Room", "game": "{game}"}


class AutoRoomSetCommands(MixinMeta, ABC, metaclass=CompositeMetaClass):
    """The autoroomset command."""

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def autoroomset(self, ctx: commands.Context):
        """Configure the AutoRoom cog.

        For a quick rundown on how to get started with this cog,
        check out [the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/autoroom/README.md)
        """

    @autoroomset.command()
    async def settings(self, ctx: commands.Context):
        """Display current settings."""
        server_section = SettingDisplay("Server Settings")
        server_section.add(
            "Admin private channel access",
            await self.config.guild(ctx.guild).admin_access(),
        )
        server_section.add(
            "Moderator private channel access",
            await self.config.guild(ctx.guild).mod_access(),
        )

        autoroom_sections = []
        avcs = await self.get_all_autoroom_source_configs(ctx.guild)
        for avc_id, avc_settings in avcs.items():
            source_channel = ctx.guild.get_channel(avc_id)
            if not source_channel:
                continue
            dest_category = ctx.guild.get_channel(avc_settings["dest_category_id"])
            autoroom_section = SettingDisplay(f"AutoRoom - {source_channel.name}")
            autoroom_section.add(
                "Room type",
                avc_settings["room_type"].capitalize(),
            )
            autoroom_section.add(
                "Destination category",
                f"#{dest_category.name}" if dest_category else "INVALID CATEGORY",
            )
            if avc_settings["text_channel"]:
                autoroom_section.add(
                    "Text Channel",
                    "True",
                )
            member_roles = []
            for member_role_id in avc_settings["member_roles"]:
                member_role = ctx.guild.get_role(member_role_id)
                if member_role:
                    member_roles.append(member_role.name)
            if member_roles:
                autoroom_section.add(
                    "Member Roles" if len(member_roles) > 1 else "Member Role",
                    ", ".join(member_roles),
                )
            room_name_format = "Username"
            if avc_settings["channel_name_type"] in channel_name_template:
                room_name_format = avc_settings["channel_name_type"].capitalize()
            elif (
                avc_settings["channel_name_type"] == "custom"
                and avc_settings["channel_name_format"]
            ):
                room_name_format = f'Custom: "{avc_settings["channel_name_format"]}"'
            autoroom_section.add("Room name format", room_name_format)
            autoroom_sections.append(autoroom_section)

        await ctx.send(server_section.display(*autoroom_sections))

        if not await self.check_required_perms(ctx.guild, also_check_autorooms=True):
            await ctx.send(
                error(
                    "It looks like I am missing one or more required server permissions. "
                    "Until I have them, the AutoRoom cog may not function properly. "
                    "Check `[p]autoroomset permissions` for more information."
                )
            )
            return

    @autoroomset.command(aliases=["perms"])
    async def permissions(self, ctx: commands.Context):
        """Check that the bot has all needed permissions."""
        has_all_perms = await self.check_required_perms(ctx.guild)

        permission_section = SettingDisplay("Permission Check")
        permission_section.add(
            "View channels", ctx.guild.me.guild_permissions.view_channel
        )
        permission_section.add(
            "Manage channels", ctx.guild.me.guild_permissions.manage_channels
        )
        permission_section.add(
            "Manage roles", ctx.guild.me.guild_permissions.manage_roles
        )
        permission_section.add("Connect", ctx.guild.me.guild_permissions.connect)
        permission_section.add(
            "Move members", ctx.guild.me.guild_permissions.move_members
        )

        autoroom_sections = []
        avcs = await self.get_all_autoroom_source_configs(ctx.guild)
        for avc_id in avcs.keys():
            source_channel = ctx.guild.get_channel(avc_id)
            if not source_channel:
                continue
            autoroom_section = SettingDisplay(f"AutoRoom - {source_channel.name}")
            overwritten_perms = False
            if (
                source_channel.overwrites
                and ctx.guild.default_role in source_channel.overwrites
            ):
                for testing_overwrite in source_channel.overwrites[
                    ctx.guild.default_role
                ]:
                    if testing_overwrite[1] is not None:
                        perm = getattr(
                            ctx.guild.me.guild_permissions, testing_overwrite[0]
                        )
                        has_all_perms = has_all_perms and perm
                        autoroom_section.add(
                            testing_overwrite[0],
                            perm,
                        )
                        overwritten_perms = True
                if overwritten_perms:
                    autoroom_sections.append(autoroom_section)

        await ctx.send(permission_section.display(*autoroom_sections))

        if not has_all_perms:
            await ctx.send(
                error(
                    "It looks like I am missing one or more required server permissions. "
                    "Until I have them, the AutoRoom cog may not function properly.\n\n"
                    "In the case of missing AutoRoom Source specific permissions, only those channels "
                    "will not work. This can be fixed by either removing `@everyone` permission overrides "
                    "in the AutoRoom Source, or by giving me those permissions server-wide."
                )
            )
            return

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

    @autoroomset.command(aliases=["enable", "add"])
    async def create(
        self,
        ctx: commands.Context,
        source_voice_channel: discord.VoiceChannel,
        dest_category: discord.CategoryChannel,
    ):
        """Create an AutoRoom Source.

        Anyone joining an AutoRoom Source will automatically have a new
        voice channel (AutoRoom) created in the destination category,
        and then be moved into it.
        """
        if not await self.check_required_perms(ctx.guild):
            await ctx.send(
                error(
                    "I am missing a permission that the AutoRoom cog requires me to have. "
                    "Check `[p]autoroomset permissions` for more details. "
                    "Try creating the AutoRoom Source again once I have these permissions."
                )
            )
            return
        new_source = {"dest_category_id": dest_category.id}

        # Public or private
        options = ["public", "private"]
        pred = MessagePredicate.lower_contained_in(options, ctx)
        await ctx.send(
            "**Welcome to the setup wizard for creating an AutoRoom Source!**"
            "\n"
            f"Users joining the {source_voice_channel.mention} AutoRoom Source will have an AutoRoom "
            f"created in the {dest_category.mention} category and be moved into it."
            "\n\n"
            "**Public/Private**"
            "\n"
            "AutoRooms can either be public or private. Public AutoRooms are visible to other users, "
            "where the AutoRoom Owner can kick/ban users out of them. Private AutoRooms are only visible to the "
            "AutoRoom Owner, where they can allow users into their room."
            "\n\n"
            "Would you like these created AutoRooms to be public or private to other users by default? (`public`/`private`)"
        )
        try:
            await ctx.bot.wait_for("message", check=pred, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send("No valid answer was received, canceling setup process.")
            return
        new_source["room_type"] = options[pred.result]

        # Text channel
        pred = MessagePredicate.yes_or_no(ctx)
        await ctx.send(
            "**Text Channel**"
            "\n"
            "AutoRooms can optionally have a text channel created with them, where only the AutoRoom members can"
            "see and message in it. This is useful to keep AutoRoom specific chat out of your other channels."
            "\n\n"
            "Would you like these created AutoRooms to also have a created text channel? (`yes`/`no`)"
        )
        try:
            await ctx.bot.wait_for("message", check=pred, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send("No valid answer was received, canceling setup process.")
            return
        new_source["text_channel"] = pred.result

        # Channel name
        options = ["username", "game"]
        pred = MessagePredicate.lower_contained_in(options, ctx)
        await ctx.send(
            "**Channel Name**"
            "\n"
            "When an AutoRoom is created, a name will be generated for it. How would you like that name to be generated?"
            "\n\n"
            f'`username` - Shows up as "{ctx.author.display_name}\'s Room"\n'
            "`game    ` - AutoRoom Owner's playing game, otherwise `username`"
        )
        try:
            await ctx.bot.wait_for("message", check=pred, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send("No valid answer was received, canceling setup process.")
            return
        new_source["channel_name_type"] = options[pred.result]

        # Member role ask
        pred = MessagePredicate.yes_or_no(ctx)
        await ctx.send(
            "**Member Role**"
            "\n"
            "By default, Public AutoRooms are visible to the whole server. Some servers have member roles for limiting "
            "what unverified members can see and do."
            "\n\n"
            "Would you like these created AutoRooms to only be visible to a certain member role? (`yes`/`no`)"
        )
        try:
            await ctx.bot.wait_for("message", check=pred, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send("No valid answer was received, canceling setup process.")
            return
        if pred.result:
            # Member role get
            pred = MessagePredicate.valid_role(ctx)
            await ctx.send(
                "What role is your member role? Only provide one; if you have multiple, you can add more after the "
                "setup process."
            )
            try:
                await ctx.bot.wait_for("message", check=pred, timeout=60)
            except asyncio.TimeoutError:
                pass
            if pred.result:
                new_source["member_roles"] = [pred.result.id]
            else:
                await ctx.send("No valid answer was received, canceling setup process.")
                return

        # Save new source
        await self.config.custom(
            "AUTOROOM_SOURCE", ctx.guild.id, source_voice_channel.id
        ).set(new_source)
        await ctx.send(
            checkmark(
                "Settings saved successfully!\n"
                "Check out `[p]autoroomset modify` for even more AutoRoom Source settings, "
                "or to make modifications to your above answers."
            )
        )

    @autoroomset.command(aliases=["disable", "delete", "del"])
    async def remove(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
    ):
        """Remove an AutoRoom Source."""
        await self.config.custom(
            "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
        ).clear()
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
        """Set an AutoRoom Source to create public AutoRooms by default."""
        await self._save_public_private(ctx, autoroom_source, "public")

    @modify.command(name="private")
    async def modify_private(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """Set an AutoRoom Source to create private AutoRooms by default."""
        await self._save_public_private(ctx, autoroom_source, "private")

    async def _save_public_private(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        room_type: str,
    ):
        """Save the public/private setting."""
        if await self.get_autoroom_source_config(autoroom_source):
            await self.config.custom(
                "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
            ).room_type.set(room_type)
            await ctx.send(
                checkmark(
                    f"New AutoRooms created by **{autoroom_source.mention}** will be {room_type}."
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
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
        if await self.get_autoroom_source_config(autoroom_source):
            member_roles = await self.config.custom(
                "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
            ).member_roles()
            if role.id not in member_roles:
                member_roles.append(role.id)
                await self.config.custom(
                    "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
                ).member_roles.set(member_roles)
            await self._send_memberrole_message(ctx, autoroom_source, "Added!")
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @memberrole.command(name="remove")
    async def remove_memberrole(
        self,
        ctx: commands.Context,
        role: discord.Role,
        autoroom_source: discord.VoiceChannel,
    ):
        """Remove a role from the list of member roles allowed to see these AutoRooms."""
        if await self.get_autoroom_source_config(autoroom_source):
            member_roles = await self.config.custom(
                "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
            ).member_roles()
            if role.id in member_roles:
                member_roles.remove(role.id)
                await self.config.custom(
                    "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
                ).member_roles.set(member_roles)
            await self._send_memberrole_message(ctx, autoroom_source, "Removed!")
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

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
        """Default format: PhasecoreX's Room.

        Custom format example: `{username}'s Room`
        """
        await self._save_room_name(ctx, autoroom_source, "username")

    @name.command()
    async def game(self, ctx: commands.Context, autoroom_source: discord.VoiceChannel):
        """The users current playing game, otherwise the username format.

        Custom format example: `{game}`
        """
        await self._save_room_name(ctx, autoroom_source, "game")

    @name.command(name="custom")
    async def name_custom(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        *,
        format_string: str,
    ):
        """A custom channel name.

        Template variables supported:
        - `{username}` - AutoRoom Owner's username
        - `{game}    ` - AutoRoom Owner's game

        If any of the template variables you use fail to be formatted
        (e.g. `{game}` when the user isn't playing a game), the room
        name will be the same as the default `username` format.
        """
        await self._save_room_name(ctx, autoroom_source, "custom", format_string)

    async def _save_room_name(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        room_type: str,
        room_format: str = None,
    ):
        """Save the room name type."""
        if await self.get_autoroom_source_config(autoroom_source):
            await self.config.custom(
                "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
            ).channel_name_type.set(room_type)
            if room_format:
                await self.config.custom(
                    "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
                ).channel_name_format.set(room_format)
            else:
                await self.config.custom(
                    "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
                ).channel_name_format.clear()
            message = (
                f"New AutoRooms created by **{autoroom_source.mention}** "
                f"will use the **{room_type.capitalize()}** format"
            )
            if room_format:
                message += f":\n`{room_format}`."
            else:
                message += "."
            await ctx.send(checkmark(message))
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify.group()
    async def increment(self, ctx: commands.Context):
        """Set the default increment format of an AutoRoom.

        When there would be a duplicate AutoRoom name,
        an incrementing number is appended to the name
        to make it unique.
        """

    @increment.command()
    async def custom(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        format_string: str,
    ):
        """Set a custom increment format of an AutoRoom.

        Your `format_string` must include `{number}`, which will
        be replaced with the incrementing number when generating
        an AutoRoom name.

        For reference, the `default` format is ` ({number})`
        (which looks like "Room Name (2)")
        """
        if "{number}" not in format_string:
            await ctx.send(
                error(
                    "`format_string` must contain `{number}` in it for incrementing to work properly."
                )
            )
            return
        format_string_clean = f" {format_string.strip()}"
        if await self.get_autoroom_source_config(autoroom_source):
            await self.config.custom(
                "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
            ).increment_format.set(format_string_clean)
            await ctx.send(
                checkmark(
                    f"Channel name increment format for **{autoroom_source.mention}** is now `{format_string_clean}`."
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @increment.command()
    async def default(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """Reset the increment format back to default.

        The default format, for those curious, is ` ({number})`
        (which looks like "Room Name (2)")
        """
        if await self.get_autoroom_source_config(autoroom_source):
            await self.config.custom(
                "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
            ).increment_format.clear()
            await ctx.send(
                checkmark(
                    f"Channel name increment format for **{autoroom_source.mention}** has been reset to default."
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @increment.command()
    async def always(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """Toggle whether or not we always append the increment number.

        Normally the first AutoRoom is the original name, and subsequent
        ones get the increment added to it (example with custom room name):

        `Table`
        `Table (2)`
        `Table (3)`

        Enabling this appends the increment to the first AutoRoom as well:

        `Table (1)`
        `Table (2)`
        `Table (3)`
        """
        if await self.get_autoroom_source_config(autoroom_source):
            increment_always = await self.config.custom(
                "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
            ).increment_always()
            if increment_always:
                await self.config.custom(
                    "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
                ).increment_always.clear()
            else:
                await self.config.custom(
                    "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
                ).increment_always.set(True)
            await ctx.send(
                checkmark(
                    f"{'All' if not increment_always else 'Only duplicate named'} "
                    f"new AutoRooms created by **{autoroom_source.mention}** will "
                    f"have an incrementing number added to them."
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify.command()
    async def text(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
    ):
        """Toggle if a text channel should be created as well."""
        if await self.get_autoroom_source_config(autoroom_source):
            text_channel = await self.config.custom(
                "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
            ).text_channel()
            if text_channel:
                await self.config.custom(
                    "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
                ).text_channel.clear()
            else:
                await self.config.custom(
                    "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
                ).text_channel.set(True)
            await ctx.send(
                checkmark(
                    f"New AutoRooms created by **{autoroom_source.mention}** will "
                    f"{'now' if not text_channel else 'no longer'} get their own text channel."
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify.command()
    async def perms(self, ctx: commands.Context):
        """Learn how to modify default permissions."""
        await ctx.send(
            info(
                "Any permissions set for the `@everyone` role on an AutoRoom Source will be copied to the "
                "resulting AutoRoom. Regardless if the permission in the AutoRoom Source is allowed or denied, "
                "the bot itself will need to have this permission allowed server-wide (with the roles it has). "
                "The only two permissions that will be overwritten are **View Channel** "
                "and **Connect**, which depend on the AutoRoom Sources public/private setting, as well as "
                "any member roles enabled for it."
                "\n\n"
                "Do note that you don't need to set any permissions on the AutoRoom Source channel for this "
                "cog to work correctly. This functionality is for the advanced user with a complex server "
                "structure, or for users that want to selectively enable/disable certain functionality "
                "(e.g. video, voice activity/PTT, invites) in AutoRooms."
            )
        )

    @modify.command(aliases=["bitrate", "users"])
    async def other(self, ctx: commands.Context):
        """Learn how to modify default bitrate and user limits."""
        await ctx.send(
            info(
                "Default bitrate and user limit settings are now copied from the AutoRoom Source."
            )
        )
