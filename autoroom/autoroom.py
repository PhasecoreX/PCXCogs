"""AutoRoom cog for Red-DiscordBot by PhasecoreX."""
import asyncio
from typing import List, Union

import discord
from redbot.core import Config, commands

from .abc import CompositeMetaClass
from .commands import Commands
from .commands.autoroomset import channel_name_template
from .pcx_template import Template

__author__ = "PhasecoreX"


class AutoRoom(Commands, commands.Cog, metaclass=CompositeMetaClass):
    """Automatic voice channel management.

    This cog facilitates automatic voice channel creation.
    When a member joins an AutoRoom Source (voice channel),
    this cog will move them to a brand new AutoRoom that they have control over.
    Once everyone leaves the AutoRoom, it is automatically deleted.

    For a quick rundown on how to get started with this cog,
    check out [the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/autoroom/README.md)
    """

    default_global_settings = {"schema_version": 0}
    default_guild_settings = {
        "admin_access": True,
        "mod_access": False,
    }
    default_autoroom_source_settings = {
        "dest_category_id": None,
        "room_type": "public",
        "text_channel": False,
        "text_channel_hint": None,
        "channel_name_type": "username",
        "channel_name_format": "",
        "member_roles": [],
    }
    default_channel_settings = {
        "owner": None,
        "member_roles": [],
        "associated_text_channel": None,
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
        self.config.init_custom("AUTOROOM_SOURCE", 2)
        self.config.register_custom(
            "AUTOROOM_SOURCE", **self.default_autoroom_source_settings
        )
        self.config.register_channel(**self.default_channel_settings)
        self.autoroom_create_lock: asyncio.Lock = asyncio.Lock()
        self.template = Template()

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

        if schema_version < 2:
            # Migrate member_role -> per auto_voice_channel member_roles
            guild_dict = await self.config.all_guilds()
            for guild_id, guild_info in guild_dict.items():
                member_role = guild_info.get("member_role", False)
                if member_role:
                    avcs = await self.config.guild_from_id(guild_id).get_raw(
                        "auto_voice_channels", default={}
                    )
                    if avcs:
                        for avc_settings in avcs.values():
                            avc_settings["member_roles"] = [member_role]
                        await self.config.guild_from_id(guild_id).set_raw(
                            "auto_voice_channels", value=avcs
                        )
                    await self.config.guild_from_id(guild_id).clear_raw("member_role")
            await self.config.schema_version.set(2)

        if schema_version < 4:
            # Migrate to AUTOROOM_SOURCE custom config group
            guild_dict = await self.config.all_guilds()
            for guild_id, guild_info in guild_dict.items():
                avcs = await self.config.guild_from_id(guild_id).get_raw(
                    "auto_voice_channels", default={}
                )
                for avc_id, avc_settings in avcs.items():
                    new_dict = {
                        "dest_category_id": avc_settings["dest_category_id"],
                        "room_type": avc_settings["room_type"],
                    }
                    # The rest of these were optional
                    if "text_channel" in avc_settings:
                        new_dict["text_channel"] = avc_settings["text_channel"]
                    if "channel_name_type" in avc_settings:
                        new_dict["channel_name_type"] = avc_settings[
                            "channel_name_type"
                        ]
                    if "member_roles" in avc_settings:
                        new_dict["member_roles"] = avc_settings["member_roles"]
                    await self.config.custom("AUTOROOM_SOURCE", guild_id, avc_id).set(
                        new_dict
                    )
                await self.config.guild_from_id(guild_id).clear_raw(
                    "auto_voice_channels"
                )
            await self.config.schema_version.set(4)

        if schema_version < 5:
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
                        else:
                            # Show numbers > 1, custom format
                            if "increment_format" in autoroom_source_config:
                                new_template += (
                                    "{% if dupenum > 1 %}"
                                    + autoroom_source_config[
                                        "increment_format"
                                    ].replace("{number}", "{{dupenum}}")
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

    async def _cleanup_autorooms(self):
        """Remove non-existent AutoRooms from the config."""
        await self.bot.wait_until_ready()
        voice_channel_dict = await self.config.all_channels()
        for voice_channel_id, voice_channel_settings in voice_channel_dict.items():
            voice_channel = self.bot.get_channel(voice_channel_id)
            if voice_channel:
                await self._process_autoroom_delete(voice_channel)
            else:
                text_channel = self.bot.get_channel(
                    voice_channel_settings["associated_text_channel"]
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
        # Get autoroom source config for before and after channels (if they exists)
        before_channel_config = await self.get_autoroom_source_config(before.channel)
        after_channel_config = await self.get_autoroom_source_config(after.channel)
        # If user left a voice channel that isn't an AutoRoom Source, do cleanup
        if before.channel and not before_channel_config:
            if not await self._process_autoroom_delete(before.channel):
                # AutoRoom wasn't deleted, so update text channel perms
                await self._process_autoroom_text_perms(before.channel)
        # If user entered a voice channel...
        if after.channel:
            # If user entered an AutoRoom Source channel, create new AutoRoom
            if after_channel_config:
                await self._process_autoroom_create(after.channel, after_channel_config)
            # If user entered an AutoRoom, allow them into the associated text channel
            else:
                await self._process_autoroom_text_perms(after.channel)

    async def _process_autoroom_create(self, autoroom_source, autoroom_source_config):
        """Create a voice channel for each member in an AutoRoom Source channel."""
        guild = autoroom_source.guild
        if not await self.check_required_perms(guild):
            return
        additional_allowed_roles = []
        if await self.config.guild(guild).mod_access():
            # Add mod roles to be allowed
            additional_allowed_roles += await self.bot.get_mod_roles(guild)
        if await self.config.guild(guild).admin_access():
            # Add admin roles to be allowed
            additional_allowed_roles += await self.bot.get_admin_roles(guild)
        async with self.autoroom_create_lock:
            if not autoroom_source.members:
                return
            dest_category = guild.get_channel(
                autoroom_source_config["dest_category_id"]
            )
            if not dest_category:
                return
            taken_channel_names = [
                voice_channel.name for voice_channel in dest_category.voice_channels
            ]

            # Gather settings from source channel
            options = {
                "bitrate": autoroom_source.bitrate,
                "user_limit": autoroom_source.user_limit,
            }
            common_overwrites = {
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    manage_channels=True,
                    move_members=True,
                )
            }
            if (
                autoroom_source.overwrites
                and guild.default_role in autoroom_source.overwrites
            ):
                enough_perms = True
                for testing_overwrite in autoroom_source.overwrites[guild.default_role]:
                    if testing_overwrite[1] is not None and not getattr(
                        guild.me.guild_permissions, testing_overwrite[0]
                    ):
                        enough_perms = False
                        break
                if not enough_perms:
                    return
                common_overwrites[guild.default_role] = autoroom_source.overwrites[
                    guild.default_role
                ]
            member_roles = await self.get_member_roles_for_source(autoroom_source)
            for member_role in member_roles or [guild.default_role]:
                if member_role not in common_overwrites:
                    common_overwrites[member_role] = discord.PermissionOverwrite()
                common_overwrites[member_role].update(
                    view_channel=autoroom_source_config["room_type"] == "public",
                    connect=autoroom_source_config["room_type"] == "public",
                )
            if member_roles:
                # We have a member role, deny @everyone
                if guild.default_role not in common_overwrites:
                    common_overwrites[
                        guild.default_role
                    ] = discord.PermissionOverwrite()
                common_overwrites[guild.default_role].update(
                    view_channel=False, connect=False
                )
            for role in additional_allowed_roles:
                # Add all the mod/admin roles, if required
                common_overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, connect=True
                )

            for member in autoroom_source.members:
                # Generate overwrites
                overwrites = {
                    member: discord.PermissionOverwrite(
                        view_channel=True,
                        connect=True,
                        manage_channels=True,
                    )
                }
                overwrites.update(common_overwrites)
                # Create channel name
                new_channel_name = self._generate_channel_name(
                    autoroom_source_config, member, taken_channel_names
                )
                taken_channel_names.append(new_channel_name)
                # Create new AutoRoom
                new_voice_channel = await guild.create_voice_channel(
                    name=new_channel_name,
                    category=dest_category,
                    reason="AutoRoom: New AutoRoom needed.",
                    overwrites=overwrites,
                    **options,
                )
                await self.config.channel(new_voice_channel).owner.set(member.id)
                if member_roles:
                    await self.config.channel(new_voice_channel).member_roles.set(
                        [member_role.id for member_role in member_roles]
                    )
                await member.move_to(
                    new_voice_channel, reason="AutoRoom: Move user to new AutoRoom."
                )

                if autoroom_source_config["text_channel"]:
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(
                            read_messages=False
                        ),
                        guild.me: discord.PermissionOverwrite(
                            read_messages=True,
                            manage_channels=True,
                            manage_messages=True,
                        ),
                        member: discord.PermissionOverwrite(
                            read_messages=True,
                            manage_channels=True,
                            manage_messages=True,
                        ),
                    }
                    new_text_channel = await guild.create_text_channel(
                        name=new_channel_name.replace("'s ", " "),
                        category=dest_category,
                        reason="AutoRoom: New text channel needed.",
                        overwrites=overwrites,
                    )
                    await self.config.channel(
                        new_voice_channel
                    ).associated_text_channel.set(new_text_channel.id)
                    if autoroom_source_config["text_channel_hint"]:
                        try:
                            hint = self.template.render(
                                autoroom_source_config["text_channel_hint"],
                                self.get_template_data(member),
                            )
                            if hint:
                                await new_text_channel.send(hint)
                        except RuntimeError:
                            pass  # User manually screwed with the template

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

    def _generate_channel_name(
        self,
        autoroom_source_config: dict,
        member: discord.Member,
        taken_channel_names: list,
    ):
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
        try:
            new_channel_name = self.format_template_room_name(template, data, attempt)
        except RuntimeError:
            pass

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

    @staticmethod
    def get_template_data(member: discord.Member):
        """Return a dict of template data based on a member."""
        data = {"username": member.display_name}
        for activity in member.activities:
            if activity.type.value == 0:
                data["game"] = activity.name
                break
        return data

    def format_template_room_name(self, template: str, data: dict, num: int = 1):
        """Return a formatted channel name, taking into account the 100 character channel name limit."""
        nums = {"dupenum": num}
        return self.template.render(
            template=template,
            data={**nums, **data},
        )[:100].strip()

    async def get_member_roles_for_source(
        self, autoroom_source: discord.VoiceChannel
    ) -> List[discord.Role]:
        """Return a list of member roles for an AutoRoom Source, cleaning up nonexistent roles."""
        roles = []
        async with self.config.custom(
            "AUTOROOM_SOURCE", autoroom_source.guild.id, autoroom_source.id
        ).member_roles() as member_roles:
            del_roles = []
            for member_role_id in member_roles:
                member_role = autoroom_source.guild.get_role(member_role_id)
                if member_role:
                    roles.append(member_role)
                else:
                    del_roles.append(member_role_id)
            for del_role in del_roles:
                member_roles.remove(del_role)
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

    async def check_required_perms(
        self, guild: discord.guild, also_check_autorooms: bool = False
    ):
        result = (
            guild.me.guild_permissions.view_channel
            and guild.me.guild_permissions.manage_channels
            and guild.me.guild_permissions.manage_roles
            and guild.me.guild_permissions.connect
            and guild.me.guild_permissions.move_members
        )
        if also_check_autorooms:
            avcs = await self.get_all_autoroom_source_configs(guild)
            for avc_id in avcs.keys():
                source_channel = guild.get_channel(avc_id)
                if (
                    source_channel
                    and source_channel.overwrites
                    and guild.default_role in source_channel.overwrites
                ):
                    for testing_overwrite in source_channel.overwrites[
                        guild.default_role
                    ]:
                        if testing_overwrite[1] is not None and not getattr(
                            guild.me.guild_permissions, testing_overwrite[0]
                        ):
                            return False
        return result

    async def get_all_autoroom_source_configs(self, guild: discord.guild):
        """Return a dict of all autoroom source configs, cleaning up any invalid ones."""
        unsorted_list_of_configs = []
        configs = await self.config.custom(
            "AUTOROOM_SOURCE", guild.id
        ).all()  # Does NOT return default values
        for channel_id in configs.keys():
            channel = guild.get_channel(int(channel_id))
            config = await self.get_autoroom_source_config(channel)
            if config:
                unsorted_list_of_configs.append((channel.position, channel_id, config))
            else:
                await self.config.custom(
                    "AUTOROOM_SOURCE", guild.id, channel_id
                ).clear()
        result = {}
        for _, channel_id, config in sorted(
            unsorted_list_of_configs, key=lambda source_config: source_config[0]
        ):
            result[int(channel_id)] = config
        return result

    async def get_autoroom_source_config(self, autoroom_source: discord.VoiceChannel):
        """Return the config for an autoroom source, or None if not set up yet."""
        if not autoroom_source:
            return None
        config = await self.config.custom(
            "AUTOROOM_SOURCE", autoroom_source.guild.id, autoroom_source.id
        ).all()  # Returns default values
        if not config["dest_category_id"]:
            return None
        return config
