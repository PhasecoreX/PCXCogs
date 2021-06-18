"""The autoroomset command."""
import asyncio
from abc import ABC

import discord
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import error, info, warning
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.predicates import MessagePredicate

from ..abc import CompositeMetaClass, MixinMeta
from ..pcx_lib import SettingDisplay, checkmark

channel_name_template = {
    "username": "{{username}}'s Room{% if dupenum > 1 %} ({{dupenum}}){% endif %}",
    "game": "{{game}}{% if not game %}{{username}}'s Room{% endif %}{% if dupenum > 1 %} ({{dupenum}}){% endif %}",
}


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

        message = server_section.display(*autoroom_sections)
        if not await self._check_all_perms(ctx.guild):
            message += "\n" + error(
                "It looks like I am missing one or more permissions. "
                "Until I have them, the AutoRoom cog may not function properly "
                "for all AutoRoom Sources. "
                "Check `[p]autoroomset permissions` for more information."
            )
        await ctx.send(message)

    @autoroomset.command(aliases=["perms"])
    async def permissions(self, ctx: commands.Context):
        """Check that the bot has all needed permissions."""
        has_all_perms, details_list = await self._check_all_perms(
            ctx.guild, detailed=True
        )
        if len(details_list) > 1:
            if not ctx.channel.permissions_for(ctx.me).add_reactions:
                await ctx.send(
                    error(
                        "Since you have multiple AutoRoom Sources, "
                        'I need the "Add Reactions" permission to display permission information'
                    )
                )
                return
        if not has_all_perms:
            await ctx.send(
                error(
                    "It looks like I am missing one or more permissions. "
                    "Until I have them, the AutoRoom Source(s) in question may not function properly."
                    "\n\n"
                    "The easiest way of doing this is just giving me these permissions as part of my server role, "
                    "otherwise you will need to give me these permissions on the AutoRoom Source and destination "
                    "category, as specified below."
                    "\n\n"
                    "In the case of optional permissions, any permission on the AutoRoom Source will be copied to "
                    "the created AutoRoom, as if we were cloning the AutoRoom Source. In order for this to work, "
                    "I need each permission to be allowed in the destination category (or server). "
                    "If it isn't allowed, I will skip copying that permission over."
                )
            )
        else:
            await ctx.send(checkmark("Everything looks good here!"))
        if len(details_list) > 1:
            await menu(ctx, details_list, DEFAULT_CONTROLS, timeout=60.0)
        else:
            await ctx.send(details_list[0])

    @autoroomset.group()
    async def access(self, ctx: commands.Context):
        """Control access to all AutoRooms."""

    @access.command(name="admin")
    async def access_admin(self, ctx: commands.Context):
        """Allow Admins to join private channels."""
        admin_access = not await self.config.guild(ctx.guild).admin_access()
        await self.config.guild(ctx.guild).admin_access.set(admin_access)
        await ctx.send(
            checkmark(
                f"Admins are {'now' if admin_access else 'no longer'} able to join (new) private AutoRooms."
            )
        )

    @access.command(name="mod")
    async def access_mod(self, ctx: commands.Context):
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
        good_permissions, details = self.check_perms_source_dest_required(
            source_voice_channel, dest_category, detailed=True
        )
        if not good_permissions:
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
        new_source = {"dest_category_id": dest_category.id}

        # Room type
        options = ["public", "private", "server"]
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
            "`public ` - Visible to other users, and the AutoRoom Owner can kick/ban users out of them."
            "\n"
            "`private` - Only visible to the AutoRoom Owner, who can allow users into their room."
            "\n"
            "`server ` - Same as a public AutoRoom, but with no AutoRoom Owner. "
            "No modifications can be made to the generated AutoRoom."
            "\n\n"
            "What would you like these created AutoRooms to be by default? (`public`/`private`/`server`)"
        )
        try:
            await ctx.bot.wait_for("message", check=pred, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send("No valid answer was received, canceling setup process.")
            return
        new_source["room_type"] = options[pred.result]

        # Check perms room type
        good_permissions, details = self.check_perms_source_dest_required(
            source_voice_channel,
            dest_category,
            with_manage_roles_guild=new_source["room_type"] != "server",
            detailed=True,
        )
        if not good_permissions:
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

        # Check perms text channel
        good_permissions, details = self.check_perms_source_dest_required(
            source_voice_channel,
            dest_category,
            with_manage_roles_guild=new_source["room_type"] != "server",
            with_text_channel=new_source["text_channel"],
            detailed=True,
        )
        if not good_permissions:
            await ctx.send(
                warning(
                    f"Since you want to have this AutoRoom Source also create text channels, "
                    "I will need a few extra permissions. "
                    "Until I have these permissions, text channels will not be created."
                    "\n"
                    f"{details}"
                )
            )

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

    @autoroomset.group(aliases=["edit"])
    async def modify(self, ctx: commands.Context):
        """Modify an existing AutoRoom Source."""

    @modify.group(name="type")
    async def modify_type(self, ctx: commands.Context):
        """Choose what type of AutoRoom is created."""

    @modify_type.command(name="public")
    async def modify_type_public(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """Rooms will be open to all. AutoRoom Owner has control over room."""
        await self._save_public_private(ctx, autoroom_source, "public")

    @modify_type.command(name="private")
    async def modify_type_private(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """Rooms will be hidden. AutoRoom Owner can allow users in."""
        await self._save_public_private(ctx, autoroom_source, "private")

    @modify_type.command(name="server")
    async def modify_type_server(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """Rooms will be open to all, but the server owns the AutoRoom (so they can't be modified)."""
        await self._save_public_private(ctx, autoroom_source, "server")

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
                    f"**{autoroom_source.mention}** will now create `{room_type}` AutoRooms."
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify.group(name="memberrole")
    async def modify_memberrole(self, ctx: commands.Context):
        """Limit AutoRoom visibility to certain member roles.

        When set, only users with the specified role(s) can see AutoRooms.
        """

    @modify_memberrole.command(name="add")
    async def modify_memberrole_add(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        role: discord.Role,
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

    @modify_memberrole.command(name="remove")
    async def modify_memberrole_remove(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        role: discord.Role,
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

    @modify.group(name="name")
    async def modify_name(self, ctx: commands.Context):
        """Set the default name format of an AutoRoom."""

    @modify_name.command(name="username")
    async def modify_name_username(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """Default format: PhasecoreX's Room.

        Custom format example:
        `{{username}}'s Room{% if dupenum > 1 %} ({{dupenum}}){% endif %}`
        """
        await self._save_room_name(ctx, autoroom_source, "username")

    @modify_name.command(name="game")
    async def modify_name_game(
        self, ctx: commands.Context, autoroom_source: discord.VoiceChannel
    ):
        """The users current playing game, otherwise the username format.

        Custom format example:
        `{{game}}{% if not game %}{{username}}'s Room{% endif %}{% if dupenum > 1 %} ({{dupenum}}){% endif %}`
        """
        await self._save_room_name(ctx, autoroom_source, "game")

    @modify_name.command(name="custom")
    async def modify_name_custom(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        *,
        template: str,
    ):
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
        """
        await self._save_room_name(ctx, autoroom_source, "custom", template)

    async def _save_room_name(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        room_type: str,
        template: str = None,
    ):
        """Save the room name type."""
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
                            f"`{str(rte)}`"
                            "\n\n"
                            "If you need some help, take a look at "
                            "[the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/autoroom/README.md)."
                        )
                    )
                    return
                await self.config.custom(
                    "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
                ).channel_name_format.set(template)
            else:
                await self.config.custom(
                    "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
                ).channel_name_format.clear()
            await self.config.custom(
                "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
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
            await ctx.send(checkmark(message))
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
    ):
        """Manage if a text channel should be created as well."""

    @modify_text.command(name="enable")
    async def modify_text_enable(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
    ):
        """Enable creating a text channel with the AutoRoom."""
        if await self.get_autoroom_source_config(autoroom_source):
            await self.config.custom(
                "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
            ).text_channel.set(True)
            await ctx.send(
                checkmark(
                    f"New AutoRooms created by **{autoroom_source.mention}** will now get their own text channel."
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
    ):
        """Disable creating a text channel with the AutoRoom."""
        if await self.get_autoroom_source_config(autoroom_source):
            await self.config.custom(
                "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
            ).text_channel.clear()
            await ctx.send(
                checkmark(
                    f"New AutoRooms created by **{autoroom_source.mention}** will no longer get their own text channel."
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify_text.group(name="hint")
    async def modify_text_hint(
        self,
        ctx: commands.Context,
    ):
        """Configure sending an introductory message to the text channel."""

    @modify_text_hint.command(name="set")
    async def modify_text_hint_set(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
        *,
        hint_text: str,
    ):
        """Send a message to the newly generated text channel.

        This can have template variables and statements, which you can learn more
        about by looking at `[p]autoroomset modify name custom`, or by looking at
        [the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/autoroom/README.md).
        """
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
                        f"`{str(rte)}`"
                        "\n\n"
                        "If you need some help, take a look at "
                        "[the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/autoroom/README.md)."
                    )
                )
                return

            await self.config.custom(
                "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
            ).text_channel_hint.set(hint_text)

            await ctx.send(
                checkmark(
                    f"New AutoRooms created by **{autoroom_source.mention}** will have the following message sent to their text channel:"
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

    @modify_text_hint.command(name="disable")
    async def modify_text_hint_disable(
        self,
        ctx: commands.Context,
        autoroom_source: discord.VoiceChannel,
    ):
        """Disable sending a message to the newly generated text channel."""
        if await self.get_autoroom_source_config(autoroom_source):
            await self.config.custom(
                "AUTOROOM_SOURCE", ctx.guild.id, autoroom_source.id
            ).text_channel_hint.clear()
            await ctx.send(
                checkmark(
                    f"New AutoRooms created by **{autoroom_source.mention}** will no longer have a message sent to their text channel."
                )
            )
        else:
            await ctx.send(
                error(
                    f"**{autoroom_source.mention}** is not an AutoRoom Source channel."
                )
            )

    @modify.command(name="perms")
    async def modify_perms(self, ctx: commands.Context):
        """Learn how to modify default permissions."""
        await ctx.send(
            info(
                "Every permission overwrite on an AutoRoom Source will be copied to the resulting AutoRoom. "
                "Regardless if a permission in the AutoRoom Source is allowed or denied, "
                "the bot itself will need to have this permission allowed either in the destination category "
                "or server-wide with the roles it has. If the bot does not have the permission, it will not "
                "be copied over."
                "\n\n"
                "The only two permissions that will be overwritten are **View Channel** "
                "and **Connect**, which depend on the AutoRoom Sources public/private setting, as well as "
                "any member roles enabled for it. Additionally, the **Manage Roles** permission will always be ignored."
                "\n\n"
                "Do note that you don't need to set any permissions on the AutoRoom Source channel for this "
                "cog to work correctly. This functionality is for the advanced user with a complex server "
                "structure, or for users that want to selectively enable/disable certain functionality "
                "(e.g. video, voice activity/PTT, invites) in AutoRooms."
            )
        )

    @modify.command(name="other", aliases=["bitrate", "users"])
    async def modify_other(self, ctx: commands.Context):
        """Learn how to modify default bitrate and user limits."""
        await ctx.send(
            info(
                "Default bitrate and user limit settings are now copied from the AutoRoom Source."
            )
        )

    async def _check_all_perms(
        self, guild: discord.Guild, detailed=False, with_optional=False
    ):
        """Check all permissions for all AutoRooms in a guild."""
        result = True
        result_list = []
        avcs = await self.get_all_autoroom_source_configs(guild)
        for avc_id, avc_settings in avcs.items():
            autoroom_source = guild.get_channel(avc_id)
            category_dest = guild.get_channel(avc_settings["dest_category_id"])
            if autoroom_source and category_dest:
                if detailed:
                    check, detail = self.check_perms_source_dest_required(
                        autoroom_source,
                        category_dest,
                        with_manage_roles_guild=avc_settings["room_type"] != "server",
                        with_text_channel=avc_settings["text_channel"],
                        detailed=True,
                    )
                    result_list.append(detail)
                    result = result and check
                elif not self.check_perms_source_dest_required(
                    autoroom_source,
                    category_dest,
                    with_manage_roles_guild=avc_settings["room_type"] != "server",
                    with_text_channel=avc_settings["text_channel"],
                ):
                    return False
        if detailed:
            return result, result_list
        else:
            return True
