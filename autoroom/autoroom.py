"""AutoRoom cog for Red-DiscordBot by PhasecoreX."""
from abc import ABC
from contextlib import suppress
from typing import Any, ClassVar

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import humanize_timedelta

from .c_autoroom import AutoRoomCommands
from .c_autoroomset import AutoRoomSetCommands, channel_name_template
from .pcx_lib import Perms, SettingDisplay
from .pcx_template import Template


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """Allows the metaclass used for proper type detection to coexist with discord.py's metaclass."""


class AutoRoom(
    AutoRoomCommands,
    AutoRoomSetCommands,
    commands.Cog,
    metaclass=CompositeMetaClass,
):
    """Automatic voice channel management.

    This cog facilitates automatic voice channel creation.
    When a member joins an AutoRoom Source (voice channel),
    this cog will move them to a brand new AutoRoom that they have control over.
    Once everyone leaves the AutoRoom, it is automatically deleted.

    For a quick rundown on how to get started with this cog,
    check out [the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/autoroom/README.md)
    """

    __author__ = "PhasecoreX"
    __version__ = "3.7.2"

    default_global_settings: ClassVar[dict[str, int]] = {"schema_version": 0}
    default_guild_settings: ClassVar[dict[str, bool | list[int]]] = {
        "admin_access": True,
        "mod_access": False,
        "bot_access": [],
    }
    default_autoroom_source_settings: ClassVar[dict[str, int | str | None]] = {
        "dest_category_id": None,
        "room_type": "public",
        "legacy_text_channel": False,
        "text_channel_hint": None,
        "text_channel_topic": "",
        "channel_name_type": "username",
        "channel_name_format": "",
    }
    default_channel_settings: ClassVar[dict[str, int | None]] = {
        "source_channel": None,
        "owner": None,
        "associated_text_channel": None,
    }
    extra_channel_name_change_delay = 4

    perms_public: ClassVar[dict[str, bool]] = {
        "view_channel": True,
        "connect": True,
        "send_messages": True,
    }
    perms_locked: ClassVar[dict[str, bool]] = {
        "view_channel": True,
        "connect": False,
        "send_messages": False,
    }
    perms_private: ClassVar[dict[str, bool]] = {
        "view_channel": False,
        "connect": False,
        "send_messages": False,
    }

    perms_bot_source: ClassVar[dict[str, bool]] = {
        "view_channel": True,
        "connect": True,
        "move_members": True,
    }
    perms_autoroom_owner: ClassVar[dict[str, bool]] = {
        **perms_public,
        "manage_channels": True,
        "manage_messages": True,
    }
    perms_bot_dest: ClassVar[dict[str, bool]] = {
        **perms_autoroom_owner,
        "move_members": True,
    }

    perms_legacy_text: ClassVar[list[str]] = ["read_message_history", "read_messages"]
    perms_legacy_text_allow: ClassVar[dict[str, bool]] = dict.fromkeys(
        perms_legacy_text, True
    )
    perms_legacy_text_deny: ClassVar[dict[str, bool]] = dict.fromkeys(
        perms_legacy_text, False
    )
    perms_legacy_text_reset: ClassVar[dict[str, None]] = dict.fromkeys(
        perms_legacy_text, None
    )
    perms_autoroom_owner_legacy_text: ClassVar[dict[str, bool]] = {
        **perms_legacy_text_allow,
        "manage_channels": True,
        "manage_messages": True,
    }
    perms_bot_dest_legacy_text = perms_autoroom_owner_legacy_text

    def __init__(self, bot: Red) -> None:
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)
        self.config.init_custom("AUTOROOM_SOURCE", 2)
        self.config.register_custom(
            "AUTOROOM_SOURCE", **self.default_autoroom_source_settings
        )
        self.config.register_channel(**self.default_channel_settings)
        self.template = Template()
        self.bucket_autoroom_create = commands.CooldownMapping.from_cooldown(
            2, 60, lambda member: member
        )
        self.bucket_autoroom_create_warn = commands.CooldownMapping.from_cooldown(
            1, 3600, lambda member: member
        )
        self.bucket_autoroom_name = commands.CooldownMapping.from_cooldown(
            2, 600 + self.extra_channel_name_change_delay, lambda channel: channel
        )
        self.bucket_autoroom_owner_claim = commands.CooldownMapping.from_cooldown(
            1, 120, lambda channel: channel
        )

    #
    # Red methods
    #

    def format_help_for_context(self, ctx: commands.Context) -> str:
        """Show version in help."""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\nCog Version: {self.__version__}"

    async def red_delete_data_for_user(self, *, _requester: str, _user_id: int) -> None:
        """Nothing to delete."""
        return

    #
    # Initialization methods
    #

    async def initialize(self) -> None:
        """Perform setup actions before loading cog."""
        await self._migrate_config()
        self.bot.loop.create_task(self._cleanup_autorooms())

    async def _migrate_config(self) -> None:
        """Perform some configuration migrations."""
        schema_version = await self.config.schema_version()

        if schema_version < 1:
            # Migrate private -> room_type
            guild_dict = await self.config.all_guilds()
            for guild_id in guild_dict:
                avcs = await self.config.guild_from_id(guild_id).get_raw(
                    "auto_voice_channels", default={}
                )
                if avcs:
                    for avc_settings in avcs.values():
                        if "private" in avc_settings:
                            avc_settings["room_type"] = (
                                "private" if avc_settings["private"] else "public"
                            )
                            del avc_settings["private"]
                    await self.config.guild_from_id(guild_id).set_raw(
                        "auto_voice_channels", value=avcs
                    )
            await self.config.schema_version.set(1)

        if schema_version < 2:  # noqa: PLR2004
            # Migrate member_role -> per auto_voice_channel member_roles
            guild_dict = await self.config.all_guilds()
            for guild_id in guild_dict:
                await self.config.guild_from_id(guild_id).clear_raw("member_role")
            await self.config.schema_version.set(2)

        if schema_version < 4:  # noqa: PLR2004
            # Migrate to AUTOROOM_SOURCE custom config group
            guild_dict = await self.config.all_guilds()
            for guild_id in guild_dict:
                avcs = await self.config.guild_from_id(guild_id).get_raw(
                    "auto_voice_channels", default={}
                )
                for avc_id, avc_settings in avcs.items():
                    new_dict = {
                        "dest_category_id": avc_settings["dest_category_id"],
                        "room_type": avc_settings["room_type"],
                    }
                    # The rest of these were optional
                    if "channel_name_type" in avc_settings:
                        new_dict["channel_name_type"] = avc_settings[
                            "channel_name_type"
                        ]
                    await self.config.custom("AUTOROOM_SOURCE", guild_id, avc_id).set(
                        new_dict
                    )
                await self.config.guild_from_id(guild_id).clear_raw(
                    "auto_voice_channels"
                )
            await self.config.schema_version.set(4)

        if schema_version < 5:  # noqa: PLR2004
            # Upgrade room templates
            all_autoroom_sources = await self.config.custom("AUTOROOM_SOURCE").all()
            for guild_id, guild_autoroom_sources in all_autoroom_sources.items():
                for (
                    avc_id,
                    autoroom_source_config,
                ) in guild_autoroom_sources.items():
                    if (
                        "channel_name_format" in autoroom_source_config
                        and autoroom_source_config["channel_name_format"]
                    ):
                        # Change username and game template variables
                        new_template = (
                            autoroom_source_config["channel_name_format"]
                            .replace("{username}", "{{username}}")
                            .replace("{game}", "{{game}}")
                        )
                        if (
                            "increment_always" in autoroom_source_config
                            and autoroom_source_config["increment_always"]
                        ):
                            if "increment_format" in autoroom_source_config:
                                # Always show number, custom format
                                new_template += autoroom_source_config[
                                    "increment_format"
                                ].replace("{number}", "{{dupenum}}")
                            else:
                                # Always show number, default format
                                new_template += " ({{dupenum}})"
                        elif "increment_format" in autoroom_source_config:
                            # Show numbers > 1, custom format
                            new_template += (
                                "{% if dupenum > 1 %}"
                                + autoroom_source_config["increment_format"].replace(
                                    "{number}", "{{dupenum}}"
                                )
                                + "{% endif %}"
                            )
                        else:
                            # Show numbers > 1, default format
                            new_template += (
                                "{% if dupenum > 1 %} ({{dupenum}}){% endif %}"
                            )
                        await self.config.custom(
                            "AUTOROOM_SOURCE", guild_id, avc_id
                        ).channel_name_format.set(new_template)
                        await self.config.custom(
                            "AUTOROOM_SOURCE", guild_id, avc_id
                        ).clear_raw("increment_always")
                        await self.config.custom(
                            "AUTOROOM_SOURCE", guild_id, avc_id
                        ).clear_raw("increment_format")
            await self.config.schema_version.set(5)

        if schema_version < 6:  # noqa: PLR2004
            # Remove member roles
            all_autoroom_sources = await self.config.custom("AUTOROOM_SOURCE").all()
            for guild_id, guild_autoroom_sources in all_autoroom_sources.items():
                for avc_id in guild_autoroom_sources:
                    await self.config.custom(
                        "AUTOROOM_SOURCE", guild_id, avc_id
                    ).clear_raw("member_roles")
            await self.config.schema_version.set(6)

        if schema_version < 7:  # noqa: PLR2004
            # Remove auto text channels
            guild_dict = await self.config.all_guilds()
            for guild_id in guild_dict:
                await self.config.guild_from_id(guild_id).clear_raw("admin_access_text")
                await self.config.guild_from_id(guild_id).clear_raw("mod_access_text")
            all_autoroom_sources = await self.config.custom("AUTOROOM_SOURCE").all()
            for guild_id, guild_autoroom_sources in all_autoroom_sources.items():
                for avc_id in guild_autoroom_sources:
                    await self.config.custom(
                        "AUTOROOM_SOURCE", guild_id, avc_id
                    ).clear_raw("text_channel")
            await self.config.schema_version.set(7)

    async def _cleanup_autorooms(self) -> None:
        """Remove non-existent AutoRooms from the config."""
        await self.bot.wait_until_ready()
        voice_channel_dict = await self.config.all_channels()
        for voice_channel_id in voice_channel_dict:
            voice_channel = self.bot.get_channel(voice_channel_id)
            if voice_channel:
                if isinstance(voice_channel, discord.VoiceChannel):
                    # Delete AutoRoom if it is empty
                    await self._process_autoroom_delete(voice_channel)
            else:
                # AutoRoom has already been deleted, clean up legacy text channel if it still exists
                legacy_text_channel = await self.get_autoroom_legacy_text_channel(
                    voice_channel
                )
                if legacy_text_channel:
                    await legacy_text_channel.delete(
                        reason="AutoRoom: Associated voice channel deleted."
                    )
                await self.config.channel_from_id(voice_channel_id).clear()

    #
    # Listener methods
    #

    @commands.Cog.listener()
    async def on_guild_channel_delete(
        self, guild_channel: discord.abc.GuildChannel
    ) -> None:
        """Clean up config when an AutoRoom (or Source) is deleted (either by the bot or the user)."""
        if not isinstance(guild_channel, discord.VoiceChannel):
            return
        if await self.get_autoroom_source_config(guild_channel):
            # AutoRoom Source was deleted, remove configuration
            await self.config.custom(
                "AUTOROOM_SOURCE", str(guild_channel.guild.id), str(guild_channel.id)
            ).clear()
        else:
            # AutoRoom was deleted, remove associated text channel if it exists
            legacy_text_channel = await self.get_autoroom_legacy_text_channel(
                guild_channel
            )
            if legacy_text_channel:
                await legacy_text_channel.delete(
                    reason="AutoRoom: Associated voice channel deleted."
                )
            await self.config.channel(guild_channel).clear()

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        leaving: discord.VoiceState,
        joining: discord.VoiceState,
    ) -> None:
        """Do voice channel stuff when users move about channels."""
        if await self.bot.cog_disabled_in_guild(self, member.guild):
            return

        # If user left an AutoRoom, do cleanup
        if isinstance(leaving.channel, discord.VoiceChannel):
            autoroom_info = await self.get_autoroom_info(leaving.channel)
            if autoroom_info:
                deleted = await self._process_autoroom_delete(leaving.channel)
                if not deleted:
                    # AutoRoom wasn't deleted, so update text channel perms
                    await self._process_autoroom_legacy_text_perms(leaving.channel)

                    if member.id == autoroom_info["owner"]:
                        # There are still users left and the AutoRoom Owner left.
                        # Start a countdown so that others can claim the AutoRoom.
                        bucket = self.bucket_autoroom_owner_claim.get_bucket(
                            leaving.channel
                        )
                        if bucket:
                            bucket.reset()
                            bucket.update_rate_limit()

        if isinstance(joining.channel, discord.VoiceChannel):
            # If user entered an AutoRoom Source channel, create new AutoRoom
            asc = await self.get_autoroom_source_config(joining.channel)
            if asc:
                await self._process_autoroom_create(joining.channel, asc, member)
            # If user entered an AutoRoom, allow them into the associated text channel
            if await self.get_autoroom_info(joining.channel):
                await self._process_autoroom_legacy_text_perms(joining.channel)

    #
    # Private methods
    #

    async def _process_autoroom_create(
        self,
        autoroom_source: discord.VoiceChannel,
        autoroom_source_config: dict[str, Any],
        member: discord.Member,
    ) -> None:
        """Create a voice channel for a member in an AutoRoom Source channel."""
        # Check perms for guild, source, and dest
        guild = autoroom_source.guild
        dest_category = guild.get_channel(autoroom_source_config["dest_category_id"])
        if not isinstance(dest_category, discord.CategoryChannel):
            return
        required_check, optional_check, _ = self.check_perms_source_dest(
            autoroom_source, dest_category
        )
        if not required_check or not optional_check:
            return

        # Check that user isn't spamming
        bucket = self.bucket_autoroom_create.get_bucket(member)
        if bucket:
            retry_after = bucket.update_rate_limit()
            if retry_after:
                warn_bucket = self.bucket_autoroom_create_warn.get_bucket(member)
                if warn_bucket:
                    if not warn_bucket.update_rate_limit():
                        with suppress(
                            discord.Forbidden,
                            discord.NotFound,
                            discord.HTTPException,
                        ):
                            await member.send(
                                "Hello there! It looks like you're trying to make an AutoRoom."
                                "\n"
                                f"Please note that you are only allowed to make **{bucket.rate}** AutoRooms "
                                f"every **{humanize_timedelta(seconds=bucket.per)}**."
                                "\n"
                                f"You can try again in **{humanize_timedelta(seconds=max(retry_after, 1))}**."
                            )
                    return

        # Generate channel name
        taken_channel_names = [
            voice_channel.name for voice_channel in dest_category.voice_channels
        ]
        new_channel_name = self._generate_channel_name(
            autoroom_source_config, member, taken_channel_names
        )

        # Generate overwrites
        perms = Perms()
        dest_perms = dest_category.permissions_for(dest_category.guild.me)
        source_overwrites = (
            autoroom_source.overwrites if autoroom_source.overwrites else {}
        )
        member_roles = self.get_member_roles(autoroom_source)
        for target, permissions in source_overwrites.items():
            # We can't put manage_roles in overwrites, so just get rid of it
            permissions.update(manage_roles=None)
            # Check each permission for each overwrite target to make sure the bot has it allowed in the dest category
            failed_checks = {}
            for name, value in permissions:
                if value is not None:
                    permission_check_result = getattr(dest_perms, name)
                    if not permission_check_result:
                        # If the bot doesn't have the permission allowed in the dest category, just ignore it. Too bad!
                        failed_checks[name] = None
            if failed_checks:
                permissions.update(**failed_checks)
            perms.overwrite(target, permissions)
            if member_roles and target in member_roles:
                # If we have member roles and this target is one, apply AutoRoom type permissions
                if autoroom_source_config["room_type"] == "private":
                    perms.update(target, self.perms_private)
                elif autoroom_source_config["room_type"] == "locked":
                    perms.update(target, self.perms_locked)
                else:
                    perms.update(target, self.perms_public)

        # Update overwrites for default role to account for AutoRoom type
        if member_roles or autoroom_source_config["room_type"] == "private":
            perms.update(guild.default_role, self.perms_private)
        elif autoroom_source_config["room_type"] == "locked":
            perms.update(guild.default_role, self.perms_locked)
        else:
            perms.update(guild.default_role, self.perms_public)

        # Bot overwrites
        perms.update(guild.me, self.perms_bot_dest)

        # AutoRoom Owner overwrites
        if autoroom_source_config["room_type"] != "server":
            perms.update(member, self.perms_autoroom_owner)

        # Admin/moderator/bot overwrites
        # Add bot roles to be allowed
        additional_allowed_roles = await self.get_bot_roles(guild)
        if await self.config.guild(guild).mod_access():
            # Add mod roles to be allowed
            additional_allowed_roles += await self.bot.get_mod_roles(guild)
        if await self.config.guild(guild).admin_access():
            # Add admin roles to be allowed
            additional_allowed_roles += await self.bot.get_admin_roles(guild)
        for role in additional_allowed_roles:
            # Add all the mod/admin roles, if required
            perms.update(role, self.perms_public)

        # Create new AutoRoom
        new_voice_channel = await guild.create_voice_channel(
            name=new_channel_name,
            category=dest_category,
            reason="AutoRoom: New AutoRoom needed.",
            overwrites=perms.overwrites if perms.overwrites else {},
            bitrate=min(autoroom_source.bitrate, int(guild.bitrate_limit)),
            user_limit=autoroom_source.user_limit,
        )
        await self.config.channel(new_voice_channel).source_channel.set(
            autoroom_source.id
        )
        if autoroom_source_config["room_type"] != "server":
            await self.config.channel(new_voice_channel).owner.set(member.id)
        try:
            await member.move_to(
                new_voice_channel, reason="AutoRoom: Move user to new AutoRoom."
            )
        except discord.HTTPException:
            await self._process_autoroom_delete(new_voice_channel)
            return

        # Create optional legacy text channel
        new_legacy_text_channel = None
        if autoroom_source_config["legacy_text_channel"]:
            # Sanity check on required permissions
            for perm_name in self.perms_bot_dest_legacy_text:
                if not getattr(dest_perms, perm_name):
                    return
            # Generate overwrites
            perms = Perms()
            perms.update(guild.me, self.perms_bot_dest_legacy_text)
            perms.update(guild.default_role, self.perms_legacy_text_deny)
            if autoroom_source_config["room_type"] != "server":
                perms.update(member, self.perms_autoroom_owner_legacy_text)
            else:
                perms.update(member, self.perms_legacy_text_allow)
            # Admin/moderator overwrites
            additional_allowed_roles_text = []
            if await self.config.guild(guild).mod_access():
                # Add mod roles to be allowed
                additional_allowed_roles_text += await self.bot.get_mod_roles(guild)
            if await self.config.guild(guild).admin_access():
                # Add admin roles to be allowed
                additional_allowed_roles_text += await self.bot.get_admin_roles(guild)
            for role in additional_allowed_roles_text:
                # Add all the mod/admin roles, if required
                perms.update(role, self.perms_legacy_text_allow)
            # Create text channel
            text_channel_topic = self.template.render(
                autoroom_source_config["text_channel_topic"],
                self.get_template_data(member),
            )
            new_legacy_text_channel = await guild.create_text_channel(
                name=new_channel_name.replace("'s ", " "),
                category=dest_category,
                topic=text_channel_topic,
                reason="AutoRoom: New legacy text channel needed.",
                overwrites=perms.overwrites if perms.overwrites else {},
            )

            await self.config.channel(new_voice_channel).associated_text_channel.set(
                new_legacy_text_channel.id
            )

        # Send text chat hint if enabled
        if autoroom_source_config["text_channel_hint"]:
            with suppress(RuntimeError):
                hint = self.template.render(
                    autoroom_source_config["text_channel_hint"],
                    self.get_template_data(member),
                )
                if hint:
                    if new_legacy_text_channel:
                        await new_legacy_text_channel.send(hint)
                    else:
                        await new_voice_channel.send(hint)

    @staticmethod
    async def _process_autoroom_delete(voice_channel: discord.VoiceChannel) -> bool:
        """Delete AutoRoom if empty."""
        if (
            not voice_channel.members
            and voice_channel.permissions_for(voice_channel.guild.me).manage_channels
        ):
            with suppress(
                discord.NotFound
            ):  # Sometimes this happens when the user manually deletes their channel
                await voice_channel.delete(reason="AutoRoom: Channel empty.")
                return True
        return False

    async def _process_autoroom_legacy_text_perms(
        self, autoroom: discord.VoiceChannel
    ) -> None:
        """Allow or deny a user access to the legacy text channel associated to an AutoRoom."""
        legacy_text_channel = await self.get_autoroom_legacy_text_channel(autoroom)
        if not legacy_text_channel:
            return

        overwrites = dict(legacy_text_channel.overwrites)
        perms = Perms(overwrites)
        # Remove read perms for users not in autoroom
        for member in overwrites:
            if (
                isinstance(member, discord.Member)
                and member not in autoroom.members
                and member != autoroom.guild.me
            ):
                perms.update(member, self.perms_legacy_text_reset)
        # Add read perms for users in autoroom
        for member in autoroom.members:
            perms.update(member, self.perms_legacy_text_allow)
        # Edit channel if overwrites were modified
        if perms.modified:
            await legacy_text_channel.edit(
                overwrites=perms.overwrites if perms.overwrites else {},
                reason="AutoRoom: Legacy text channel permission update",
            )

    def _generate_channel_name(
        self,
        autoroom_source_config: dict,
        member: discord.Member,
        taken_channel_names: list,
    ) -> str:
        """Return a channel name with an incrementing number appended to it, based on a formatting string."""
        template = None
        if autoroom_source_config["channel_name_type"] in channel_name_template:
            template = channel_name_template[
                autoroom_source_config["channel_name_type"]
            ]
        elif autoroom_source_config["channel_name_type"] == "custom":
            template = autoroom_source_config["channel_name_format"]
        template = template or channel_name_template["username"]

        data = self.get_template_data(member)
        new_channel_name = None
        attempt = 1
        with suppress(RuntimeError):
            new_channel_name = self.format_template_room_name(template, data, attempt)

        if not new_channel_name:
            # Either the user screwed with the template, or the template returned nothing. Use a default one instead.
            template = channel_name_template["username"]
            new_channel_name = self.format_template_room_name(template, data, attempt)

        # Check for duplicate names
        attempted_channel_names = []
        while (
            new_channel_name in taken_channel_names
            and new_channel_name not in attempted_channel_names
        ):
            attempt += 1
            attempted_channel_names.append(new_channel_name)
            new_channel_name = self.format_template_room_name(template, data, attempt)
        return new_channel_name

    #
    # Public methods
    #

    @staticmethod
    def get_template_data(member: discord.Member | discord.User) -> dict[str, str]:
        """Return a dict of template data based on a member."""
        data = {"username": member.display_name, "mention": member.mention}
        if isinstance(member, discord.Member):
            for activity in member.activities:
                if activity.type == discord.ActivityType.playing:
                    data["game"] = activity.name or ""
                    break
        return data

    def format_template_room_name(self, template: str, data: dict, num: int = 1) -> str:
        """Return a formatted channel name, taking into account the 100 character channel name limit."""
        nums = {"dupenum": num}
        return self.template.render(
            template=template,
            data={**nums, **data},
        )[:100].strip()

    async def is_admin_or_admin_role(self, who: discord.Role | discord.Member) -> bool:
        """Check if a member (or role) is an admin (role).

        Also takes into account if the setting is enabled.
        """
        if await self.config.guild(who.guild).admin_access():
            if isinstance(who, discord.Role):
                return who in await self.bot.get_admin_roles(who.guild)
            if isinstance(who, discord.Member):
                return await self.bot.is_admin(who)
        return False

    async def is_mod_or_mod_role(self, who: discord.Role | discord.Member) -> bool:
        """Check if a member (or role) is a mod (role).

        Also takes into account if the setting is enabled.
        """
        if await self.config.guild(who.guild).mod_access():
            if isinstance(who, discord.Role):
                return who in await self.bot.get_mod_roles(who.guild)
            if isinstance(who, discord.Member):
                return await self.bot.is_mod(who)
        return False

    def check_perms_source_dest(
        self,
        autoroom_source: discord.VoiceChannel,
        category_dest: discord.CategoryChannel,
        *,
        with_manage_roles_guild: bool = False,
        with_legacy_text_channel: bool = False,
        with_optional_clone_perms: bool = False,
        detailed: bool = False,
    ) -> tuple[bool, bool, str | None]:
        """Check if the permissions in an AutoRoom Source and a destination category are sufficient."""
        source = autoroom_source.permissions_for(autoroom_source.guild.me)
        dest = category_dest.permissions_for(category_dest.guild.me)
        result_required = True
        result_optional = True
        # Required
        for perm_name in self.perms_bot_source:
            result_required = result_required and bool(getattr(source, perm_name))
        for perm_name in self.perms_bot_dest:
            result_required = result_required and bool(getattr(dest, perm_name))
        if with_manage_roles_guild:
            result_required = (
                result_required
                and category_dest.guild.me.guild_permissions.manage_roles
            )
        # Optional
        if with_legacy_text_channel:
            for perm_name in self.perms_bot_dest_legacy_text:
                result_optional = result_optional and getattr(dest, perm_name)
        clone_section = None
        if with_optional_clone_perms:
            clone_result, clone_section = self._check_perms_source_dest_optional(
                autoroom_source, dest, detailed=detailed
            )
            result_optional = result_optional and clone_result
        result = result_required and result_optional
        if not detailed:
            return result_required, result_optional, None

        source_section = SettingDisplay("Required on Source Voice Channel")
        for perm_name in self.perms_bot_source:
            source_section.add(
                perm_name.capitalize().replace("_", " "), getattr(source, perm_name)
            )

        dest_section = SettingDisplay("Required on Destination Category")
        for perm_name in self.perms_bot_dest:
            dest_section.add(
                perm_name.capitalize().replace("_", " "), getattr(dest, perm_name)
            )
        autoroom_sections = [dest_section]

        if with_manage_roles_guild:
            guild_section = SettingDisplay("Required in Guild")
            guild_section.add(
                "Manage roles", category_dest.guild.me.guild_permissions.manage_roles
            )
            autoroom_sections.append(guild_section)

        if with_legacy_text_channel:
            text_section = SettingDisplay(
                "Optional on Destination Category (for legacy text channel)"
            )
            for perm_name in self.perms_bot_dest_legacy_text:
                text_section.add(
                    perm_name.capitalize().replace("_", " "), getattr(dest, perm_name)
                )
            autoroom_sections.append(text_section)

        if clone_section:
            autoroom_sections.append(clone_section)

        status_emoji = "\N{NO ENTRY SIGN}"
        if result:
            status_emoji = "\N{WHITE HEAVY CHECK MARK}"
        elif result_required:
            status_emoji = "\N{WARNING SIGN}\N{VARIATION SELECTOR-16}"
        result_str = (
            f"\n{status_emoji} Source VC: {autoroom_source.mention} -> Dest Category: {category_dest.mention}"
            "\n"
            f"{source_section.display(*autoroom_sections)}"
        )
        return result_required, result_optional, result_str

    @staticmethod
    def _check_perms_source_dest_optional(
        autoroom_source: discord.VoiceChannel,
        dest_perms: discord.Permissions,
        *,
        detailed: bool = False,
    ) -> tuple[bool, SettingDisplay | None]:
        result = True
        checked_perms = {}
        source_overwrites = (
            autoroom_source.overwrites if autoroom_source.overwrites else {}
        )
        for permissions in source_overwrites.values():
            # We can't put manage_roles in overwrites, so just get rid of it
            # Also get rid of view_channel, connect, and send_messages, as we will be controlling those
            permissions.update(
                connect=None, manage_roles=None, view_channel=None, send_messages=None
            )
            # Check each permission for each overwrite target to make sure the bot has it allowed in the dest category
            for name, value in permissions:
                if value is not None and name not in checked_perms:
                    check_result = bool(getattr(dest_perms, name))
                    if not detailed and not check_result:
                        return False, None
                    checked_perms[name] = check_result
                    result = result and check_result
        if not detailed:
            return True, None
        clone_section = SettingDisplay(
            "Optional on Destination Category (for source clone)"
        )
        if checked_perms:
            for name, value in checked_perms.items():
                clone_section.add(name.capitalize().replace("_", " "), value)
            return result, clone_section
        return result, None

    async def get_all_autoroom_source_configs(
        self, guild: discord.Guild
    ) -> dict[int, dict[str, Any]]:
        """Return a dict of all autoroom source configs, cleaning up any invalid ones."""
        unsorted_list_of_configs = []
        configs = await self.config.custom(
            "AUTOROOM_SOURCE", str(guild.id)
        ).all()  # Does NOT return default values
        for channel_id in configs:
            channel = guild.get_channel(int(channel_id))
            if not isinstance(channel, discord.VoiceChannel):
                continue
            config = await self.get_autoroom_source_config(channel)
            if config:
                unsorted_list_of_configs.append((channel.position, channel_id, config))
            else:
                await self.config.custom(
                    "AUTOROOM_SOURCE", str(guild.id), channel_id
                ).clear()
        result = {}
        for _, channel_id, config in sorted(
            unsorted_list_of_configs, key=lambda source_config: source_config[0]
        ):
            result[int(channel_id)] = config
        return result

    async def get_autoroom_source_config(
        self, autoroom_source: discord.VoiceChannel
    ) -> dict[str, Any] | None:
        """Return the config for an autoroom source, or None if not set up yet."""
        if not autoroom_source:
            return None
        config = await self.config.custom(
            "AUTOROOM_SOURCE", str(autoroom_source.guild.id), str(autoroom_source.id)
        ).all()  # Returns default values
        if not config["dest_category_id"]:
            return None
        return config

    async def get_autoroom_info(
        self, autoroom: discord.VoiceChannel | None
    ) -> dict[str, Any] | None:
        """Get info for an AutoRoom, or None if the voice channel isn't an AutoRoom."""
        if not autoroom:
            return None
        if not await self.config.channel(autoroom).source_channel():
            return None
        return await self.config.channel(autoroom).all()

    async def get_autoroom_legacy_text_channel(
        self, autoroom: discord.VoiceChannel
    ) -> discord.TextChannel | None:
        """Get the AutoRoom legacy test channel, if it exists and we have manage channels permission."""
        legacy_text_channel_id = await self.config.channel(
            autoroom
        ).associated_text_channel()
        legacy_text_channel = (
            autoroom.guild.get_channel(legacy_text_channel_id)
            if legacy_text_channel_id
            else None
        )
        if (
            isinstance(legacy_text_channel, discord.TextChannel)
            and legacy_text_channel.permissions_for(
                legacy_text_channel.guild.me
            ).manage_channels
        ):
            return legacy_text_channel
        return None

    @staticmethod
    def check_if_member_or_role_allowed(
        channel: discord.VoiceChannel,
        member_or_role: discord.Member | discord.Role,
    ) -> bool:
        """Check if a member/role is allowed to connect to a voice channel.

        Doesn't matter if they can't see it, it ONLY checks the connect permission.
        Mostly copied from https://github.com/Rapptz/discord.py/blob/master/discord/abc.py:GuildChannel.permissions_for()
        I needed the logic except the "if not base.read_messages:" part that removed all permissions.
        """
        if channel.guild.owner_id == member_or_role.id:
            return True

        default_role = channel.guild.default_role
        base = discord.Permissions(default_role.permissions.value)

        # Handle the role case first
        if isinstance(member_or_role, discord.Role):
            base.value |= member_or_role.permissions.value

            if base.administrator:
                return True

            # Apply @everyone allow/deny first since it's special
            with suppress(KeyError):
                default_allow, default_deny = channel.overwrites[default_role].pair()
                base.handle_overwrite(
                    allow=default_allow.value, deny=default_deny.value
                )

            if member_or_role.is_default():
                return base.connect

            with suppress(KeyError):
                role_allow, role_deny = channel.overwrites[member_or_role].pair()
                base.handle_overwrite(allow=role_allow.value, deny=role_deny.value)

            return base.connect

        member_roles = member_or_role.roles

        # Apply guild roles that the member has.
        for role in member_roles:
            base.value |= role.permissions.value

        # Guild-wide Administrator -> True for everything
        # Bypass all channel-specific overrides
        if base.administrator:
            return True

        # Apply @everyone allow/deny first since it's special
        with suppress(KeyError):
            default_allow, default_deny = channel.overwrites[default_role].pair()
            base.handle_overwrite(allow=default_allow.value, deny=default_deny.value)

        allows = 0
        denies = 0

        # Apply channel specific role permission overwrites
        for role, overwrite in channel.overwrites.items():
            if (
                isinstance(role, discord.Role)
                and role != default_role
                and role in member_roles
            ):
                allows |= overwrite.pair()[0].value
                denies |= overwrite.pair()[1].value

        base.handle_overwrite(allow=allows, deny=denies)

        # Apply member specific permission overwrites
        with suppress(KeyError):
            member_allow, member_deny = channel.overwrites[member_or_role].pair()
            base.handle_overwrite(allow=member_allow.value, deny=member_deny.value)

        if member_or_role.is_timed_out():
            # Timeout leads to every permission except VIEW_CHANNEL and READ_MESSAGE_HISTORY
            # being explicitly denied
            return False

        return base.connect

    def get_member_roles(
        self, autoroom_source: discord.VoiceChannel
    ) -> list[discord.Role]:
        """Get member roles set on an AutoRoom Source."""
        member_roles = []
        # If @everyone is allowed to connect to the source channel, there are no member roles
        if not self.check_if_member_or_role_allowed(
            autoroom_source,
            autoroom_source.guild.default_role,
        ):
            # If it isn't allowed, then member roles are being used
            member_roles.extend(
                role
                for role, overwrite in autoroom_source.overwrites.items()
                if isinstance(role, discord.Role)
                and role != autoroom_source.guild.default_role
                and overwrite.pair()[0].connect
            )
        return member_roles

    async def get_bot_roles(self, guild: discord.Guild) -> list[discord.Role]:
        """Get the additional bot roles that are added to each AutoRoom."""
        bot_roles = []
        bot_role_ids = []
        some_roles_were_not_found = False
        for bot_role_id in await self.config.guild(guild).bot_access():
            bot_role = guild.get_role(bot_role_id)
            if bot_role:
                bot_roles.append(bot_role)
                bot_role_ids.append(bot_role_id)
            else:
                some_roles_were_not_found = True
        if some_roles_were_not_found:
            # Update the bot role list to remove nonexistent roles
            await self.config.guild(guild).bot_access.set(bot_role_ids)
        return bot_roles
