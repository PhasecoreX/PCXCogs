"""The autoroomset command."""
import asyncio
from abc import ABC
from contextlib import suppress

import discord
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import error, info, success, warning
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.predicates import MessagePredicate

from .abc import MixinMeta
from .pcx_lib import SettingDisplay

channel_name_template = {
    "username": "{{username}}'s Room{% if dupenum > 1 %} ({{dupenum}}){% endif %}",
    "game": "{{game}}{% if not game %}{{username}}'s Room{% endif %}{% if dupenum > 1 %} ({{dupenum}}){% endif %}",
}


class AutoRoomSetCommands(MixinMeta, ABC):
    """The autoroomset command."""

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def autoroomset(self, ctx: commands.Context) -> None:
        """Configure the AutoRoom cog.

        For a quick rundown on how to get started with this cog,
        check out [the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/autoroom/README.md)
        """

    @autoroomset.command()
    async def settings(self, ctx: commands.Context) -> None:
        """Display current settings."""
        if not ctx.guild:
            return
        server_section = SettingDisplay("Server Settings")
        server_section.add(
            "Admin access all AutoRooms",
            await self.config.guild(ctx.guild).admin_access(),
        )
        server_section.add(
            "Moderator access all AutoRooms",
            await self.config.guild(ctx.guild).mod_access(),
        )
        bot_roles = ", ".join(
            [role.name for role in await self.get_bot_roles(ctx.guild)]
        )
        if bot_roles:
            server_section.add("Bot roles allowed in all AutoRooms", bot_roles)

        autoroom_sections = []
        avcs = await self.get_all_autoroom_source_configs(ctx.guild)
        for avc_id, avc_settings in avcs.items():
            source_channel = ctx.guild.get_channel(avc_id)
            if not isinstance(source_channel, discord.VoiceChannel):
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
            if avc_settings["legacy_text_channel"]:
                autoroom_section.add(
                    "Legacy Text Channel",
                    "True",
                )
            member_roles = self.get_member_roles(source_channel)
            if member_roles:
                autoroom_section.add(
                    "Member Roles" if len(member_roles) > 1 else "Member Role",
                    ", ".join(role.name for role in member_roles),
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

        message = server_section.display(*autoroom_sections)
        required_check, optional_check, _ = await self._check_all_perms(ctx.guild)
        if not required_check:
            message += "\n" + error(
                "It looks like I am missing one or more required permissions. "
                "Until I have them, the AutoRoom cog may not function properly "
                "for all AutoRoom Sources. "
                "Check `[p]autoroomset permissions` for more information."
            )
        elif not optional_check:
            message += "\n" + warning(
                "All AutoRooms will work correctly, as I have all of the required permissions. "
                "However, it looks like I am missing one or more optional permissions "
                "for one or more AutoRooms. "
                "Check `[p]autoroomset permissions` for more information."
            )
        await ctx.send(message)

    @autoroomset.command(aliases=["perms"])
    async def permissions(self, ctx: commands.Context) -> None:
        """Check that the bot has all needed permissions."""
        if not ctx.guild:
            return
        required_check, optional_check, details_list = await self._check_all_perms(
            ctx.guild, detailed=True
        )
        if not details_list:
            await ctx.send(
                info(
                    "You don't have any AutoRoom Sources set up! "
                    "Set one up with `[p]autoroomset create` first, "
                    "then I can check what permissions I need for it."
                )
            )
            return

        if (
            len(details_list) > 1
            and not ctx.channel.permissions_for(ctx.guild.me).add_reactions
        ):
            await ctx.send(
                error(
                    "Since you have multiple AutoRoom Sources, "
                    'I need the "Add Reactions" permission to display permission information.'
                )
            )
            return

        if not required_check:
            await ctx.send(
                error(
                    "It looks like I am missing one or more required permissions. "
                    "Until I have them, the AutoRoom Source(s) in question will not function properly."
                    "\n\n"
                    "The easiest way of fixing this is just giving me these permissions as part of my server role, "
                    "otherwise you will need to give me these permissions on the AutoRoom Source and destination "
                    "category, as specified below."
                )
            )
        elif not optional_check:
            await ctx.send(
                warning(
                    "It looks like I am missing one or more optional permissions. "
                    "All AutoRooms will work, however some extra features may not work. "
                    "\n\n"
                    "The easiest way of fixing this is just giving me these permissions as part of my server role, "
                    "otherwise you will need to give me these permissions on the destination category, "
                    "as specified below."
                    "\n\n"
                    "In the case of optional permissions, any permission on the AutoRoom Source will be copied to "
                    "the created AutoRoom, as if we were cloning the AutoRoom Source. In order for this to work, "
                    "I need each permission to be allowed in the destination category (or server). "
                    "If it isn't allowed, I will skip copying that permission over."
                )
            )
        else:
            await ctx.send(success("Everything looks good here!"))

        if len(details_list) > 1:
            if (
                ctx.channel.permissions_for(ctx.guild.me).add_reactions
                and ctx.channel.permissions_for(ctx.guild.me).read_message_history
            ):
                await menu(ctx, details_list, DEFAULT_CONTROLS, timeout=60.0)
            else:
                for details in details_list:
                    await ctx.send(details)
        else:
            await ctx.send(details_list[0])

    @autoroomset.group()
    async def access(self, ctx: commands.Context) -> None:
        """Control access to all AutoRooms.

        Roles that are considered "admin" or "moderator" are
        set up with the commands `[p]set addadminrole`
        and `[p]set addmodrole` (plus the remove commands too)
        """

    @access.command(name="admin")
    async def access_admin(self, ctx: commands.Context) -> None:
        """Allow Admins to join locked/private AutoRooms."""
        if not ctx.guild:
            return
        admin_access = not await self.config.guild(ctx.guild).admin_access()
        await self.config.guild(ctx.guild).admin_access.set(admin_access)
        await ctx.send(
            success(
                f"Admins are {'now' if admin_access else 'no longer'} able to join (new) locked/private AutoRooms."
            )
        )

    @access.command(name="mod")
    async def access_mod(self, ctx: commands.Context) -> None:
        """Allow Moderators to join locked/private AutoRooms."""
        if not ctx.guild:
            return
        mod_access = not await self.config.guild(ctx.guild).mod_access()
        await self.config.guild(ctx.guild).mod_access.set(mod_access)
        await ctx.send(
            success(
                f"Moderators are {'now' if mod_access else 'no longer'} able to join (new) locked/private AutoRooms."
            )
        )

    @access.group(name="bot")
    async def access_bot(self, ctx: commands.Context) -> None:
        """Automatically allow bots into AutoRooms.

        The AutoRoom Owner is able to freely allow or deny these roles as they see fit.
        """

    @access_bot.command(name="add")
    async def access_bot_add(self, ctx: commands.Context, role: discord.Role) -> None:
        """Allow a bot role into every AutoRoom."""
        if not ctx.guild:
            return
        bot_role_ids = await self.config.guild(ctx.guild).bot_access()
        if role.id not in bot_role_ids:
            bot_role_ids.append(role.id)
            await self.config.guild(ctx.guild).bot_access.set(bot_role_ids)

        role_list = "\n".join(
            [role.name for role in await self.get_bot_roles(ctx.guild)]
        )
        await ctx.send(
            success(
                f"AutoRooms will now allow the following bot roles in by default:\n\n{role_list}"
            )
        )

    @access_bot.command(name="remove", aliases=["delete", "del"])
    async def access_bot_remove(
        self, ctx: commands.Context, role: discord.Role
    ) -> None:
        """Disallow a bot role from joining every AutoRoom."""
        if not ctx.guild:
            return
        bot_role_ids = await self.config.guild(ctx.guild).bot_access()
        if role.id in bot_role_ids:
            bot_role_ids.remove(role.id)
            await self.config.guild(ctx.guild).bot_access.set(bot_role_ids)

        if bot_role_ids:
            role_list = "\n".join(
                [role.name for role in await self.get_bot_roles(ctx.guild)]
            )
            await ctx.send(
                success(
                    f"AutoRooms will now allow the following bot roles in by default:\n\n{role_list}"
                )
            )
        else:
            await ctx.send(
                success("New AutoRooms will not allow any extra bot roles in.")
            )

    @autoroomset.command(aliases=["enable", "add"])
    async def create(
        self,
        ctx: commands.Context,
        source_voice_channel: discord.VoiceChannel,
        dest_category: discord.CategoryChannel,
    ) -> None:
        """Create an AutoRoom Source.

        Anyone joining an AutoRoom Source will automatically have a new
        voice channel (AutoRoom) created in the destination category,
        and then be moved into it.
        """
        if not ctx.guild:
            return
        perms_required, perms_optional, details = self.check_perms_source_dest(
            source_voice_channel, dest_category, detailed=True
        )
        if not perms_required or not perms_optional:
            await ctx.send(
                error(
                    "I am missing a permission that the AutoRoom cog requires me to have. "
                    "Check below for the permissions I require in both the AutoRoom Source "
                    "and the destination category. "
                    "Try creating the AutoRoom Source again once I have these permissions."
                    "\n"
                    f"{details}"
                    "\n"
                    "The easiest way of doing this is just giving me these permissions as part of my server role, "
                    "otherwise you will need to give me these permissions on the source channel and destination "
                    "category, as specified above."
                )
            )
            return
        new_source: dict[str, str | int] = {"dest_category_id": dest_category.id}

        # Room type
        options = ["public", "locked", "private", "server"]
        pred = MessagePredicate.lower_contained_in(options, ctx)
        await ctx.send(
            "**Welcome to the setup wizard for creating an AutoRoom Source!**"
            "\n"
            f"Users joining the {source_voice_channel.mention} AutoRoom Source will have an AutoRoom "
            f"created in the {dest_category.mention} category and be moved into it."
            "\n\n"
            "**AutoRoom Type**"
            "\n"
            "AutoRooms can be one of the following types when created:"
            "\n"
            "`public ` - Visible and joinable by other users. The AutoRoom Owner can kick/ban users out of them."
            "\n"
            "`locked ` - Visible, but not joinable by other users. The AutoRoom Owner must allow users into their room."
            "\n"
            "`private` - Not visible or joinable by other users. The AutoRoom Owner must allow users into their room."
            "\n"
            "`server ` - Same as a public AutoRoom, but with no AutoRoom Owner. "
            "No modifications can be made to the generated AutoRoom."
            "\n\n"
            "What would you like these created AutoRooms to be by default? (`public`/`locked`/`private`/`server`)"
        )
        answer = None
        with suppress(asyncio.TimeoutError):
            await ctx.bot.wait_for("message", check=pred, timeout=60)
            answer = pred.result
        if answer is not None:
            new_source["room_type"] = options[answer]
        else:
            await ctx.send("No valid answer was received, canceling setup process.")
            return

        # Check perms room type
        perms_required, perms_optional, details = self.check_perms_source_dest(
            source_voice_channel,
            dest_category,
            with_manage_roles_guild=new_source["room_type"] != "server",
            detailed=True,
        )
        if not perms_required or not perms_optional:
            await ctx.send(
                error(
                    f"Since you want to have this AutoRoom Source create {new_source['room_type']} AutoRooms, "
                    "I will need a few extra permissions. "
                    "Try creating the AutoRoom Source again once I have these permissions."
                    "\n"
                    f"{details}"
                )
            )
            return

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
        answer = None
        with suppress(asyncio.TimeoutError):
            await ctx.bot.wait_for("message", check=pred, timeout=60)
            answer = pred.result
        if answer is not None:
            new_source["channel_name_type"] = options[answer]
        else:
            await ctx.send("No valid answer was received, canceling setup process.")
            return

        # Save new source
        await self.config.custom(
            "AUTOROOM_SOURCE", str(ctx.guild.id), str(source_voice_channel.id)
        ).set(new_source)
        await ctx.send(
            success(
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
    ) -> None:
        """Remove an AutoRoom Source."""
        if not ctx.guild:
            return
        await self.config.custom(
            "AUTOROOM_SOURCE", str(ctx.guild.id), str(autoroom_source.id)
        ).clear()
        await ctx.send(
            success(
                f"**{autoroom_source.mention}** is no longer an AutoRoom Source channel."
            )
        )

    @autoroomset.group(aliases=["edit"])
    async def modify(self, ctx: commands.Context) -> None:
        """Modify an existing AutoRoom Source."""

    @modify.command(name="category")
    async def modify_category(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        dest_category: discord.CategoryChannel,
    ) -> None:
        """Set the category that AutoRooms will be created in."""
        if not ctx.guild:
            return
        if await self.get_autoroom_source_config(autoroom_source):
            await self.config.custom(
                "AUTOROOM_SOURCE", str(ctx.guild.id), str(autoroom_source.id)
            ).dest_category_id.set(dest_category.id)
            perms_required, perms_optional, details = self.check_perms_source_dest(
                autoroom_source, dest_category, detailed=True
            )
            message = f"**{autoroom_source.mention}** will now create new AutoRooms in the **{dest_category.mention}** category."
            if perms_required and perms_optional:
                await ctx.send(success(message))
            else:
                await ctx.send(
                    warning(
                        f"{message}"
                        "\n"
                        "Do note, this new category does not have sufficient permissions for me to make AutoRooms. "
                        "Until you fix this, the AutoRoom Source will not work."
                        "\n"
                        f"{details}"
                    )
                )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify.group(name="type")
    async def modify_type(self, ctx: commands.Context) -> None:
        """Choose what type of AutoRoom is created."""

    @modify_type.command(name="public")
    async def modify_type_public(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ) -> None:
        """Rooms will be open to all. AutoRoom Owner has control over room."""
        await self._save_public_private(ctx, autoroom_source, "public")

    @modify_type.command(name="locked")
    async def modify_type_locked(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ) -> None:
        """Rooms will be visible to all, but not joinable. AutoRoom Owner can allow users in."""
        await self._save_public_private(ctx, autoroom_source, "locked")

    @modify_type.command(name="private")
    async def modify_type_private(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ) -> None:
        """Rooms will be hidden. AutoRoom Owner can allow users in."""
        await self._save_public_private(ctx, autoroom_source, "private")

    @modify_type.command(name="server")
    async def modify_type_server(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ) -> None:
        """Rooms will be open to all, but the server owns the AutoRoom (so they can't be modified)."""
        await self._save_public_private(ctx, autoroom_source, "server")

    async def _save_public_private(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        room_type: str,
    ) -> None:
        """Save the public/private setting."""
        if not ctx.guild:
            return
        if await self.get_autoroom_source_config(autoroom_source):
            await self.config.custom(
                "AUTOROOM_SOURCE", str(ctx.guild.id), str(autoroom_source.id)
            ).room_type.set(room_type)
            await ctx.send(
                success(
                    f"**{autoroom_source.mention}** will now create `{room_type}` AutoRooms."
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify.group(name="name")
    async def modify_name(self, ctx: commands.Context) -> None:
        """Set the default name format of an AutoRoom."""

    @modify_name.command(name="username")
    async def modify_name_username(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ) -> None:
        """Default format: PhasecoreX's Room.

        Custom format example:
        `{{username}}'s Room{% if dupenum > 1 %} ({{dupenum}}){% endif %}`
        """  # noqa: D401
        await self._save_room_name(ctx, autoroom_source, "username")

    @modify_name.command(name="game")
    async def modify_name_game(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ) -> None:
        """The users current playing game, otherwise the username format.

        Custom format example:
        `{{game}}{% if not game %}{{username}}'s Room{% endif %}{% if dupenum > 1 %} ({{dupenum}}){% endif %}`
        """  # noqa: D401
        await self._save_room_name(ctx, autoroom_source, "game")

    @modify_name.command(name="custom")
    async def modify_name_custom(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        *,
        template: str,
    ) -> None:
        """A custom channel name.

        Use `{{ expressions }}` to print variables and `{% statements %}` to do basic evaluations on variables.

        Variables supported:
        - `username` - AutoRoom Owner's username
        - `game    ` - AutoRoom Owner's game
        - `dupenum ` - An incrementing number that starts at 1, useful for un-duplicating channel names

        Statements supported:
        - `if/elif/else/endif`
        - Example: `{% if dupenum > 1 %}DupeNum is {{dupenum}}, which is greater than 1{% endif %}`
        - Another example: `{% if not game %}User isn't playing a game!{% endif %}`

        It's kinda like Jinja2, but way simpler. Check out [the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/autoroom/README.md) for more info.
        """  # noqa: D401
        await self._save_room_name(ctx, autoroom_source, "custom", template)

    async def _save_room_name(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        room_type: str,
        template: str | None = None,
    ) -> None:
        """Save the room name type."""
        if not ctx.guild:
            return
        if await self.get_autoroom_source_config(autoroom_source):
            data = self.get_template_data(ctx.author)
            if template:
                template = template.replace("\n", " ")
                try:
                    # Validate template
                    self.format_template_room_name(template, data)
                except RuntimeError as rte:
                    await ctx.send(
                        error(
                            "Hmm... that doesn't seem to be a valid template:"
                            "\n\n"
                            f"`{rte!s}`"
                            "\n\n"
                            "If you need some help, take a look at "
                            "[the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/autoroom/README.md)."
                        )
                    )
                    return
                await self.config.custom(
                    "AUTOROOM_SOURCE", str(ctx.guild.id), str(autoroom_source.id)
                ).channel_name_format.set(template)
            else:
                await self.config.custom(
                    "AUTOROOM_SOURCE", str(ctx.guild.id), str(autoroom_source.id)
                ).channel_name_format.clear()
            await self.config.custom(
                "AUTOROOM_SOURCE", str(ctx.guild.id), str(autoroom_source.id)
            ).channel_name_type.set(room_type)
            message = (
                f"New AutoRooms created by **{autoroom_source.mention}** "
                f"will use the **{room_type.capitalize()}** format"
            )
            if template:
                message += f":\n`{template}`"
            else:
                # Load preset template for display purposes
                template = channel_name_template[room_type]
                message += "."
            if "game" not in data:
                data["game"] = "Example Game"
            message += "\n\nExample room names:"
            for room_num in range(1, 4):
                message += (
                    f"\n{self.format_template_room_name(template, data, room_num)}"
                )
            await ctx.send(success(message))
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify.group(name="text")
    async def modify_text(
        self,
        ctx: commands.Context,
    ) -> None:
        """Configure sending an introductory message to the AutoRoom text channel."""

    @modify_text.command(name="set")
    async def modify_text_set(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        *,
        hint_text: str,
    ) -> None:
        """Send a message to the newly generated AutoRoom text channel.

        This can have template variables and statements, which you can learn more
        about by looking at `[p]autoroomset modify name custom`, or by looking at
        [the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/autoroom/README.md).

        The only additional variable that may be useful here is the `mention` variable,
        which will insert the users mention (pinging them).

        - Example:
        `Hello {{mention}}! Welcome to your new AutoRoom!`
        """
        if not ctx.guild:
            return
        if await self.get_autoroom_source_config(autoroom_source):
            data = self.get_template_data(ctx.author)
            try:
                # Validate template
                hint_text_formatted = self.template.render(hint_text, data)
            except RuntimeError as rte:
                await ctx.send(
                    error(
                        "Hmm... that doesn't seem to be a valid template:"
                        "\n\n"
                        f"`{rte!s}`"
                        "\n\n"
                        "If you need some help, take a look at "
                        "[the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/autoroom/README.md)."
                    )
                )
                return

            await self.config.custom(
                "AUTOROOM_SOURCE", str(ctx.guild.id), str(autoroom_source.id)
            ).text_channel_hint.set(hint_text)

            await ctx.send(
                success(
                    f"New AutoRooms created by **{autoroom_source.mention}** will have the following message sent in them:"
                    "\n\n"
                    f"{hint_text_formatted}"
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify_text.command(name="disable")
    async def modify_text_disable(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
    ) -> None:
        """Disable sending a message to the newly generated AutoRoom text channel."""
        if not ctx.guild:
            return
        if await self.get_autoroom_source_config(autoroom_source):
            await self.config.custom(
                "AUTOROOM_SOURCE", str(ctx.guild.id), str(autoroom_source.id)
            ).text_channel_hint.clear()
            await ctx.send(
                success(
                    f"New AutoRooms created by **{autoroom_source.mention}** will no longer have a message sent in them."
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify.group(name="legacytextchannel")
    async def modify_legacytext(
        self,
        ctx: commands.Context,
    ) -> None:
        """Manage if a legacy text channel should be created as well."""

    @modify_legacytext.command(name="enable")
    async def modify_legacytext_enable(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
    ) -> None:
        """Enable creating a legacy text channel with the AutoRoom."""
        if not ctx.guild:
            return
        if await self.get_autoroom_source_config(autoroom_source):
            await self.config.custom(
                "AUTOROOM_SOURCE", str(ctx.guild.id), str(autoroom_source.id)
            ).legacy_text_channel.set(value=True)
            await ctx.send(
                success(
                    f"New AutoRooms created by **{autoroom_source.mention}** will now get their own legacy text channel."
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify_legacytext.command(name="disable")
    async def modify_legacytext_disable(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
    ) -> None:
        """Disable creating a legacy text channel with the AutoRoom."""
        if not ctx.guild:
            return
        if await self.get_autoroom_source_config(autoroom_source):
            await self.config.custom(
                "AUTOROOM_SOURCE", str(ctx.guild.id), str(autoroom_source.id)
            ).legacy_text_channel.clear()
            await ctx.send(
                success(
                    f"New AutoRooms created by **{autoroom_source.mention}** will no longer get their own legacy text channel."
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify_legacytext.group(name="topic")
    async def modify_legacytext_topic(
        self,
        ctx: commands.Context,
    ) -> None:
        """Manage the legacy text channel topic."""

    @modify_legacytext_topic.command(name="set")
    async def modify_legacytext_topic_set(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        *,
        topic_text: str,
    ) -> None:
        """Set the legacy text channel topic.

        - Example:
        `This channel is only visible to members of your voice channel, and admins of this server. It will be deleted when everyone leaves. `
        """
        if not ctx.guild:
            return
        if await self.get_autoroom_source_config(autoroom_source):
            data = self.get_template_data(ctx.author)
            try:
                # Validate template
                topic_text_formatted = self.template.render(topic_text, data)
            except RuntimeError as rte:
                await ctx.send(
                    error(
                        "Hmm... that doesn't seem to be a valid template:"
                        "\n\n"
                        f"`{rte!s}`"
                        "\n\n"
                        "If you need some help, take a look at "
                        "[the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/autoroom/README.md)."
                    )
                )
                return

            await self.config.custom(
                "AUTOROOM_SOURCE", str(ctx.guild.id), str(autoroom_source.id)
            ).text_channel_topic.set(topic_text)

            await ctx.send(
                success(
                    f"New AutoRooms created by **{autoroom_source.mention}** will have the following message topic set:"
                    "\n\n"
                    f"{topic_text_formatted}"
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify_legacytext_topic.command(name="disable")
    async def modify_legacytext_topic_disable(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
    ) -> None:
        """Disable setting a legacy text channel topic."""
        if not ctx.guild:
            return
        if await self.get_autoroom_source_config(autoroom_source):
            await self.config.custom(
                "AUTOROOM_SOURCE", str(ctx.guild.id), str(autoroom_source.id)
            ).text_channel_topic.clear()
            await ctx.send(
                success(
                    f"New AutoRooms created by **{autoroom_source.mention}** will no longer have a topic set."
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify.command(
        name="defaults", aliases=["bitrate", "memberrole", "other", "perms", "users"]
    )
    async def modify_defaults(self, ctx: commands.Context) -> None:
        """Learn how AutoRoom defaults are set."""
        await ctx.send(
            info(
                "**Bitrate/User Limit**"
                "\n"
                "Default bitrate and user limit settings are copied from the AutoRoom Source to the resulting AutoRoom."
                "\n\n"
                "**Member Roles**"
                "\n"
                "Only members that can view and join an AutoRoom Source will be able to join its resulting AutoRooms. "
                "If you would like to limit AutoRooms to only allow certain members, simply deny the everyone role "
                "from viewing/connecting to the AutoRoom Source and allow your member roles to view/connect to it."
                "\n\n"
                "**Permissions**"
                "\n"
                "All permission overwrites (except for Manage Roles) will be copied from the AutoRoom Source "
                "to the resulting AutoRoom. Every permission overwrite you want copied over, regardless if it is "
                "allowed or denied, must be allowed for the bot. It can either be allowed for the bot in the "
                "destination category or server-wide with the roles it has. `[p]autoroomset permissions` will "
                "show what permissions will be copied over."
            )
        )

    async def _check_all_perms(
        self, guild: discord.Guild, *, detailed: bool = False
    ) -> tuple[bool, bool, list[str]]:
        """Check all permissions for all AutoRooms in a guild."""
        result_required = True
        result_optional = True
        result_list = []
        avcs = await self.get_all_autoroom_source_configs(guild)
        for avc_id, avc_settings in avcs.items():
            autoroom_source = guild.get_channel(avc_id)
            category_dest = guild.get_channel(avc_settings["dest_category_id"])
            if isinstance(autoroom_source, discord.VoiceChannel) and isinstance(
                category_dest, discord.CategoryChannel
            ):
                (
                    required_check,
                    optional_check,
                    detail,
                ) = self.check_perms_source_dest(
                    autoroom_source,
                    category_dest,
                    with_manage_roles_guild=avc_settings["room_type"] != "server",
                    with_legacy_text_channel=avc_settings["legacy_text_channel"],
                    with_optional_clone_perms=True,
                    detailed=detailed,
                )
                result_required = result_required and required_check
                result_optional = result_optional and optional_check
                if detailed:
                    result_list.append(detail)
                elif not result_required and not result_optional:
                    break
        return result_required, result_optional, result_list
