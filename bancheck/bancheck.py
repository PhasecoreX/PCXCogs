"""BanCheck cog for Red-DiscordBot ported and enhanced by PhasecoreX."""

from contextlib import suppress
from typing import Any, ClassVar

import discord
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import error, info, success, warning

from .pcx_lib import delete
from .services.antiraid import Antiraid


class BanCheck(commands.Cog):
    """Look up users on various ban lists.

    This cog allows server admins to check their members against multiple external ban lists.
    It can also automatically check new members that join the server,
    and optionally ban them if they appear in a list.

    For a quick rundown on how to get started with this cog,
    check out [the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/bancheck/README.md)
    """

    __author__ = "PhasecoreX"
    __version__ = "2.6.1"

    default_global_settings: ClassVar[dict[str, int]] = {
        "schema_version": 0,
        "total_bans": 0,
    }
    default_guild_settings: ClassVar[
        dict[str, int | dict[str, dict[str, bool | str]] | None]
    ] = {
        "notify_channel": None,
        "total_bans": 0,
        "services": {},
    }
    supported_global_services: ClassVar[dict] = {
        "antiraid": Antiraid,
    }
    supported_guild_services: ClassVar[dict] = {}
    all_supported_services: ClassVar[dict] = {
        **supported_global_services,
        **supported_guild_services,
    }

    def __init__(self, bot: Red) -> None:
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)
        self.bucket_member_join_cache = commands.CooldownMapping.from_cooldown(
            1, 300, lambda member: member
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

    async def _migrate_config(self) -> None:
        """Perform some configuration migrations."""
        schema_version = await self.config.schema_version()

        if schema_version < 1:
            guild_dict = await self.config.all_guilds()
            for guild_id, guild_info in guild_dict.items():
                # Migrate channel -> notify_channel
                channel = guild_info.get("channel", False)
                if channel:
                    await self.config.guild_from_id(guild_id).notify_channel.set(
                        channel
                    )
                    await self.config.guild_from_id(guild_id).clear_raw("channel")
                # Migrate enabled/disabled global services per guild
                auto_ban = guild_info.get("auto_ban", False)
                disabled_services = guild_info.get("disabled_services", [])
                disabled_auto_ban_services = guild_info.get(
                    "disabled_auto_ban_services", []
                )
                async with self.config.guild_from_id(
                    guild_id
                ).services() as config_services:
                    for service in self.supported_global_services:
                        if service in config_services:
                            continue  # Already migrated
                        config_services[service] = {}
                        config_services[service]["autoban"] = (
                            auto_ban and service not in disabled_auto_ban_services
                        )
                        config_services[service]["enabled"] = (
                            service not in disabled_services
                        )
                # Delete old config keys
                await self.config.guild_from_id(guild_id).clear_raw("auto_ban")
                await self.config.guild_from_id(guild_id).clear_raw("disabled_services")
                await self.config.guild_from_id(guild_id).clear_raw(
                    "disabled_auto_ban_services"
                )
            # Migrate global API keys to Red core
            services_dict = await self.config.get_raw("services", default=False)
            if services_dict:
                for service_id, service_info in services_dict.items():
                    api_key = service_info.get("api_key", False)
                    service_keys = await self.bot.get_shared_api_tokens(service_id)
                    if api_key and not service_keys.get("api_key", False):
                        await self.bot.set_shared_api_tokens(
                            service_id, api_key=api_key
                        )
                await self.config.clear_raw("services")
            await self.config.clear_raw("version")
            await self.config.schema_version.set(1)

    #
    # Command methods: banchecksetglobal
    #

    @commands.group()
    @checks.is_owner()
    async def banchecksetglobal(self, ctx: commands.Context) -> None:
        """Configure global BanCheck settings.

        For a quick rundown on how to get started with this cog,
        check out [the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/bancheck/README.md)
        """

    @banchecksetglobal.command(name="settings")
    async def global_settings(self, ctx: commands.Context) -> None:
        """Display current settings."""
        embed = discord.Embed(
            title="BanCheck Global Settings",
            description=(
                "Setting an API key globally will allow any server this bot is in to use that service "
                "for ban checking. These services require the bot itself to go through an approval process, "
                "and only allow one API key per bot. Thus, only you, the bot owner, can set these API keys."
            ),
            color=await ctx.embed_color(),
        )
        total_bans = await self.config.total_bans()
        users = "user" if total_bans == 1 else "users"
        total_servers = len(self.bot.guilds)
        servers = "server" if total_servers == 1 else "servers"
        embed.set_footer(
            text=f"AutoBanned a total of {total_bans} {users} across {total_servers} {servers}"
        )
        enabled_services = ""
        disabled_services = ""
        for service_name, service_class in self.supported_global_services.items():
            if await self.get_api_key(service_name):
                enabled_services += (
                    f"{await self.format_service_name_url(service_name)}\n"
                )
            else:
                with suppress(AttributeError):
                    if service_class().HIDDEN:
                        continue
                    # Otherwise, this service is not hidden
                disabled_services += f"{await self.format_service_name_url(service_name, show_help=True)}\n"
        if enabled_services:
            embed.add_field(
                name=success("API Keys Set"), value=enabled_services, inline=False
            )
        if disabled_services:
            embed.add_field(
                name=error("API Keys Not Set"), value=disabled_services, inline=False
            )
        await self.send_embed(ctx, embed)

    @banchecksetglobal.command(name="api")
    async def global_api(
        self, ctx: commands.Context, service: str, api_key: str | None = None
    ) -> None:
        """Set (or delete) an API key for a global service.

        Behind the scenes, this is the same as `[p]set api <service> api_key <your_api_key_here>`
        """
        if api_key:
            # Try deleting the command as fast as possible, so that others can't see the API key
            await delete(ctx.message)
        if service in self.supported_guild_services:
            await ctx.send(
                info(
                    f"{self.get_nice_service_name(service)} is not a global service, "
                    "and should be set up per server using the command:\n\n"
                    f"`[p]bancheckset service api {service} <your_api_key_here>`"
                )
            )
            return
        if service not in self.supported_global_services:
            await ctx.send(
                error(
                    f"{self.get_nice_service_name(service)} is not a valid service name."
                )
            )
            return
        action = "set"
        if api_key:
            await ctx.bot.set_shared_api_tokens(service, api_key=api_key)
        else:
            await ctx.bot.remove_shared_api_tokens(service, "api_key")
            action = "removed"
        response = f"API key for the {self.get_nice_service_name(service)} BanCheck service has been {action}."
        await ctx.send(success(response))

    #
    # Command methods: bancheckset
    #

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def bancheckset(self, ctx: commands.Context) -> None:
        """Configure BanCheck for this server.

        For a quick rundown on how to get started with this cog,
        check out [the readme](https://github.com/PhasecoreX/PCXCogs/tree/master/bancheck/README.md)
        """

    @bancheckset.command()
    async def settings(self, ctx: commands.Context) -> None:
        """Display current settings."""
        if not ctx.guild:
            return

        embed = discord.Embed(title="BanCheck Settings", color=await ctx.embed_color())
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        total_bans = await self.config.guild(ctx.guild).total_bans()
        users = "user" if total_bans == 1 else "users"
        embed.set_footer(
            text=f"AutoBanned a total of {total_bans} {users} in this server"
        )
        # Get info
        any_enabled = False
        autoban_service_count = 0
        config_services = await self.config.guild(ctx.guild).services()
        for service_name, service_config in config_services.items():
            if (
                service_name in self.all_supported_services
                and service_config.get("enabled", False)
                and await self.get_api_key(service_name, config_services)
            ):
                any_enabled = True
                if service_config.get("autoban", False):
                    autoban_service_count += 1
        notify_channel = None
        notify_channel_id = await self.config.guild(ctx.guild).notify_channel()
        if notify_channel_id:
            notify_channel = ctx.guild.get_channel(notify_channel_id)
        self._get_autocheck_status(embed, notify_channel, any_enabled=any_enabled)
        self._get_autoban_status(
            embed,
            notify_channel,
            autoban_service_count,
            ban_members_permission=ctx.guild.me.guild_permissions.ban_members,
        )
        # Service status
        enabled_services = ""
        for service_name in self.all_supported_services:
            if config_services.get(service_name, {}).get(
                "enabled", False
            ) and await self.get_api_key(service_name, config_services):
                enabled_services += f"**{self.get_nice_service_name(service_name)}**"
                if config_services.get(service_name, {}).get("autoban", False):
                    enabled_services += " (AutoBan enabled)"
                enabled_services += "\n"
        if enabled_services:
            embed.add_field(
                name=success("Enabled Services"), value=enabled_services, inline=False
            )
        else:
            embed.add_field(
                name=error("Enabled Services"),
                value="No services are enabled!\nCheck out `[p]bancheckset service settings` for more information.",
                inline=False,
            )
        await self.send_embed(ctx, embed)

    @staticmethod
    def _get_autocheck_status(
        embed: discord.Embed,
        notify_channel: discord.abc.GuildChannel | None,
        *,
        any_enabled: bool,
    ) -> None:
        """Add AutoCheck information to the embed."""
        # AutoCheck status
        if not notify_channel:
            embed.add_field(
                name=error("AutoCheck"),
                value="**Disabled**\n(AutoCheck notification channel not set)",
            )
        elif not any_enabled:
            embed.add_field(
                name=error("AutoCheck"),
                value="**Disabled**\n(No services are enabled)",
            )
        else:
            embed.add_field(
                name=success("AutoCheck"),
                value="**Enabled**\n(On join)",
            )
        # AutoCheck Channel status
        if notify_channel:
            embed.add_field(
                name=success("AutoCheck Channel"),
                value=notify_channel.mention,
            )
        else:
            embed.add_field(name=error("AutoCheck Channel"), value="**Not set**")

    @staticmethod
    def _get_autoban_status(
        embed: discord.Embed,
        notify_channel: discord.abc.GuildChannel | None,
        autoban_service_count: int,
        *,
        ban_members_permission: bool,
    ) -> None:
        """Add AutoBan information to the embed."""
        if not notify_channel:
            embed.add_field(
                name=error("AutoBan"),
                value="**Disabled**\n(AutoCheck not enabled)",
            )
        elif not autoban_service_count:
            embed.add_field(
                name=error("AutoBan"),
                value="**Disabled**\n(No BanCheck services are set to AutoBan)",
            )
        elif not ban_members_permission:
            embed.add_field(
                name=error("AutoBan"),
                value="**Disabled**\n(Bot lacks Ban Members permission)",
            )
        else:
            embed.add_field(
                name=success("AutoBan"),
                value=f"**Enabled**\n({autoban_service_count} {'service' if autoban_service_count == 1 else 'services'})",
            )

    @bancheckset.group()
    async def service(self, ctx: commands.Context) -> None:
        """Manage the services BanCheck will use to lookup users."""

    @service.command(name="settings")
    async def service_settings(self, ctx: commands.Context) -> None:
        """Display current settings."""
        if not ctx.guild:
            return

        embed = discord.Embed(
            title="BanCheck Service Settings",
            color=await ctx.embed_color(),
        )
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        config_services = await self.config.guild(ctx.guild).services()
        enabled_services = ""
        enabled_services_api = ""
        enabled_services_global_api = ""
        disabled_services = ""
        disabled_services_api = ""
        disabled_services_global_api = ""
        for service_name, service_class in self.all_supported_services.items():
            api_key = await self.get_api_key(service_name, config_services)
            enabled = config_services.get(service_name, {}).get("enabled", False)
            show_help = service_name in self.supported_guild_services and not api_key
            service_name_formatted = f"{await self.format_service_name_url(service_name, show_help=show_help)}\n"
            if enabled and api_key:
                enabled_services += service_name_formatted
            elif enabled and service_name in self.supported_global_services:
                enabled_services_global_api += service_name_formatted
            elif enabled:
                enabled_services_api += service_name_formatted
            elif api_key:
                disabled_services += service_name_formatted
            else:
                with suppress(AttributeError):
                    if service_class().HIDDEN:
                        continue
                    # Otherwise, this service is not hidden
                if service_name in self.supported_global_services:
                    disabled_services_global_api += service_name_formatted
                else:
                    disabled_services_api += service_name_formatted
        if enabled_services:
            embed.add_field(
                name=success("Enabled Services"), value=enabled_services, inline=False
            )
        if enabled_services_api:
            embed.add_field(
                name=warning("Enabled Services (Missing API Key)"),
                value=enabled_services_api,
                inline=False,
            )
        if enabled_services_global_api:
            embed.add_field(
                name=warning("Enabled Services (Missing Global API Key)"),
                value=enabled_services_global_api,
                inline=False,
            )
        if disabled_services:
            embed.add_field(
                name=error("Disabled Services"),
                value=disabled_services,
                inline=False,
            )
        if disabled_services_api:
            embed.add_field(
                name=error("Disabled Services (Missing API Key)"),
                value=disabled_services_api,
                inline=False,
            )
        if disabled_services_global_api:
            embed.add_field(
                name=error("Disabled Services (Missing Global API Key)"),
                value=disabled_services_global_api,
                inline=False,
            )
        description = ""
        if enabled_services_api or disabled_services_api:
            description += "You can set missing API keys with\n`[p]bancheckset service api <service> [api_key]`.\n\n"
        if enabled_services_global_api or disabled_services_global_api:
            description += (
                "You must wait for the bot owner to set missing global API keys, at which point any "
                "service that uses global API keys that you have enabled will automatically begin working.\n"
            )
        if description:
            embed.description = description
        await self.send_embed(ctx, embed)

    @service.command(name="api")
    async def service_api(
        self, ctx: commands.Context, service: str, api_key: str | None = None
    ) -> None:
        """Set (or delete) an API key for a service."""
        # Try deleting the command as fast as possible, so that others can't see the API key
        await delete(ctx.message)
        if not ctx.guild:
            return
        if service not in self.all_supported_services:
            await ctx.send(
                error(
                    f"{self.get_nice_service_name(service)} is not a valid service name."
                )
            )
            return
        if (
            service in self.supported_global_services
            and not self.supported_global_services[service].SERVICE_API_KEY_REQUIRED
        ):
            await ctx.send(
                success(
                    f"{self.get_nice_service_name(service)} does not require an API key."
                )
            )
            return
        if service in self.supported_global_services:
            if await ctx.bot.is_owner(ctx.author):
                await ctx.send(
                    info(
                        f"The API key for {self.get_nice_service_name(service)} can only be set up globally. "
                        "See `[p]banchecksetglobal` for more information."
                    )
                )
            else:
                await ctx.send(
                    error(
                        f"The API key for {self.get_nice_service_name(service)} can only be set up by the bot owner."
                    )
                )
            return
        async with self.config.guild(ctx.guild).services() as config_services:
            if service not in config_services:
                config_services[service] = {}
            config_services[service]["api_key"] = api_key
        action = "set"
        if not api_key:
            action = "removed"
        response = f"API key for the {self.get_nice_service_name(service)} BanCheck service has been {action}."
        await ctx.send(success(response))

    @service.command(name="enable")
    async def service_enable(self, ctx: commands.Context, service: str) -> None:
        """Enable a service."""
        if not ctx.guild:
            return
        if service not in self.all_supported_services:
            await ctx.send(
                error(
                    f"{self.get_nice_service_name(service)} is not a valid service name."
                )
            )
            return
        async with self.config.guild(ctx.guild).services() as config_services:
            if service not in config_services:
                config_services[service] = {}
            config_services[service]["enabled"] = True
            response = (
                f"Enabled the {self.get_nice_service_name(service)} BanCheck service."
            )
            if not await self.get_api_key(service, config_services):
                if service in self.supported_guild_services:
                    response += "\nYou will need to set an API key for this service in order for it to be used."
                else:
                    response += (
                        "\nThe bot owner has not set this service up yet, so it will not be used. "
                        "If in the future the bot owner supplies an API key, this service will automatically be used."
                    )
            await ctx.send(success(response))

    @service.command(name="disable")
    async def service_disable(self, ctx: commands.Context, service: str) -> None:
        """Disable a service."""
        if not ctx.guild:
            return
        async with self.config.guild(ctx.guild).services() as config_services:
            if not config_services.get(service, {}).get("enabled", False):
                await ctx.send(
                    info(
                        f"{self.get_nice_service_name(service)} is not an enabled service."
                    )
                )
                return
            config_services[service]["enabled"] = False
        response = (
            f"Disabled the {self.get_nice_service_name(service)} BanCheck service."
        )
        await ctx.send(success(response))

    @bancheckset.group()
    async def autoban(self, ctx: commands.Context) -> None:
        """Manage which services are allowed to ban users automatically."""

    @autoban.command(name="enable")
    async def autoban_enable(self, ctx: commands.Context, service: str) -> None:
        """Enable a service to ban users automatically."""
        if not ctx.guild:
            return
        if service not in self.all_supported_services:
            await ctx.send(
                error(
                    f"{self.get_nice_service_name(service)} is not a valid service name."
                )
            )
            return
        async with self.config.guild(ctx.guild).services() as config_services:
            if service not in config_services:
                config_services[service] = {}
            config_services[service]["autoban"] = True
            config_services[service]["enabled"] = True
            response = f"Automatic banning with {self.get_nice_service_name(service)} has now been enabled."
            if not await self.config.guild(ctx.guild).notify_channel():
                response += "\nYou will need to set up AutoCheck in order for this to take effect."
            if not await self.get_api_key(service, config_services):
                response += "\nAn API key is needed in order for this to take effect."
            if not ctx.guild.me.guild_permissions.ban_members:
                response += "\nI will need to be granted the Ban Members permission for this to take effect."
            await ctx.send(success(response))

    @autoban.command(name="disable")
    async def autoban_disable(self, ctx: commands.Context, service: str) -> None:
        """Disable a service from banning users automatically."""
        if not ctx.guild:
            return
        async with self.config.guild(ctx.guild).services() as config_services:
            if not config_services.get(service, {}).get("autoban", False):
                await ctx.send(
                    info(
                        f"Automatic banning with {self.get_nice_service_name(service)} is already disabled."
                    )
                )
                return
            config_services[service]["autoban"] = False
        response = f"Automatic banning with {self.get_nice_service_name(service)} has now been disabled."
        await ctx.send(success(response))

    @bancheckset.group()
    async def autocheck(self, ctx: commands.Context) -> None:
        """Automatically perform BanChecks on new users."""

    @autocheck.command(name="set")
    async def set_autocheck(
        self, ctx: commands.Context, channel: discord.TextChannel | None = None
    ) -> None:
        """Set the channel you want AutoCheck notifications to go to."""
        if not ctx.guild:
            return
        if channel is None:
            if isinstance(ctx.channel, discord.TextChannel):
                channel = ctx.channel
            else:
                return
        if await self.send_embed(
            channel,
            self.embed_maker(
                None,
                discord.Colour.green(),
                "\N{WHITE HEAVY CHECK MARK} **I will send all AutoCheck notifications here.**",
                ctx.guild.me.display_avatar.url,
            ),
        ):
            await self.config.guild(ctx.guild).notify_channel.set(channel.id)

    @autocheck.command(name="disable")
    async def disable_autocheck(self, ctx: commands.Context) -> None:
        """Disable automatically checking new users against ban lists."""
        if not ctx.guild:
            return
        if await self.config.guild(ctx.guild).notify_channel() is None:
            await ctx.send(info("AutoCheck is already disabled."))
        else:
            await self.config.guild(ctx.guild).notify_channel.set(None)
            await ctx.send(success("AutoCheck is now disabled."))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(ban_members=True)
    async def bancheck(
        self,
        ctx: commands.Context,
        member: discord.Member | discord.User | int | None = None,
    ) -> None:
        """Check if user is on a ban list."""
        if not ctx.guild:
            return
        if not member:
            member = ctx.message.author
        async with ctx.channel.typing():
            embed = await self._user_lookup(ctx.guild, member)
        if embed:
            await self.send_embed(ctx, embed)

    #
    # Listener methods
    #

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """If enabled, will check users against ban lists when joining the guild."""
        if await self.bot.cog_disabled_in_guild(self, member.guild):
            return
        channel_id = await self.config.guild(member.guild).notify_channel()
        if channel_id:
            channel = member.guild.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                # Only do auto lookup if the user isn't repeatedly leaving and joining the server
                bucket = self.bucket_member_join_cache.get_bucket(member)
                if bucket:
                    repeatedly_joining = bucket.update_rate_limit()
                    if not repeatedly_joining:
                        embed = await self._user_lookup(
                            member.guild, member, do_ban=True
                        )
                        if embed:
                            await self.send_embed(channel, embed)

    async def _user_lookup(
        self,
        guild: discord.Guild,
        member: discord.Member | discord.User | int,
        *,
        do_ban: bool = False,
    ) -> discord.Embed | None:
        """Perform user lookup and return results embed. Optionally ban user too."""
        config_services = await self.config.guild(guild).services()
        banned_services: dict[str, str] = {}
        auto_banned = False
        is_error = False
        checked = []
        if isinstance(member, discord.Member | discord.User):
            description = f"**Name:** {member.name}\n**ID:** {member.id}\n\n"
            member_id = member.id
            member_avatar_url = member.display_avatar.url
        else:
            description = f"**ID:** {member}\n\n"
            member_id = member
            member_avatar_url = None

        # Get results
        for service_name, service_config in config_services.items():
            if not service_config.get("enabled", False):
                continue
            autoban = service_config.get("autoban", False)
            service_class = self.all_supported_services.get(service_name, None)
            if not service_class:
                continue
            api_key = await self.get_api_key(service_name, config_services)
            if not api_key:
                continue
            if not hasattr(service_class(), "lookup"):
                continue  # This service does not support lookup

            responses = await service_class().lookup(member_id, api_key)
            if not isinstance(responses, list):
                responses = [responses]
            for response in responses:
                checked.append(response.service)

                if response.result == "ban":
                    banned_services[response.service] = response.reason
                    if do_ban and autoban:
                        auto_banned = True

                    proof = " (No proof provided)"
                    if response.proof_url:
                        proof = f" ([proof]({response.proof_url}))"

                    description += error(
                        f"**{response.service}:** {response.reason}{proof}\n"
                    )

                elif response.result == "clear":
                    description += success(f"**{response.service}:** No ban found\n")

                elif response.result == "error":
                    is_error = True
                    description += warning(
                        f"**{response.service}:** Error - {response.reason if response.reason else 'No reason given'}\n"
                    )

                else:
                    is_error = True
                    description += warning(
                        f"**{response.service}:** Fatal Error - "
                        f"You should probably let PhasecoreX know about this -> `{response.result}`.\n"
                    )

        # Display result
        if banned_services:
            title = "Ban Found"
            if (
                auto_banned
                and isinstance(member, discord.Member)
                and guild.me.guild_permissions.ban_members
            ):
                with suppress(discord.Forbidden, discord.NotFound):
                    singular_or_plural = (
                        "a global ban list"
                        if len(banned_services) == 1
                        else "multiple global ban lists"
                    )
                    list_of_banned_services = ", ".join(banned_services)
                    await member.send(
                        f"Hello! Since you are currently on {singular_or_plural} ({list_of_banned_services}), "
                        f"you have automatically been banned from {member.guild}."
                    )
                try:
                    reasons = [
                        f"{name} ({reason})" for name, reason in banned_services.items()
                    ]
                    await guild.ban(
                        member,
                        reason=f"BanCheck auto ban: {', '.join(reasons)}",
                        delete_message_days=1,
                    )
                    # Update guild ban totals
                    total_bans = await self.config.guild(guild).total_bans()
                    await self.config.guild(guild).total_bans.set(total_bans + 1)
                    # Update global ban totals
                    global_total_bans = await self.config.total_bans()
                    await self.config.total_bans.set(global_total_bans + 1)
                    title += " - Auto Banned"
                except (discord.Forbidden, discord.HTTPException):
                    title += " - Not allowed to Auto Ban"
            return self.embed_maker(
                title, discord.Colour.red(), description, member_avatar_url
            )
        if is_error:
            return self.embed_maker(
                "Error (but no ban found otherwise)",
                discord.Colour.gold(),
                description,
                member_avatar_url,
            )
        if not checked and do_ban:
            return None  # No services have been enabled when auto checking
        if not checked:
            return self.embed_maker(
                "Error",
                discord.Colour.gold(),
                "No services have been set up. Please check `[p]bancheckset` for more details.",
                member_avatar_url,
            )
        return self.embed_maker(
            f"No ban found for **{member}**",
            discord.Colour.green(),
            f"Checked: {', '.join(checked)}",
            member_avatar_url,
        )

    #
    # Public methods
    #

    async def format_service_name_url(
        self, service_name: str, *, show_help: bool = False
    ) -> str:
        """Format BanCheck services."""
        service_class = self.all_supported_services.get(service_name, None)
        if not service_class:
            return f"`{service_name}`"
        result = f" `{service_name}` - [{service_class.SERVICE_NAME}]({service_class.SERVICE_URL})"
        if show_help:
            with suppress(AttributeError):
                result += f" ({service_class.SERVICE_HINT})"
            # Otherwise, no hint for this service
        return result

    async def get_api_key(
        self, service_name: str, guild_service_config: dict[str, Any] | None = None
    ) -> bool | str:
        """Get the API key for this service.

        Returns the first:
        - False if this isn't a valid service
        - The global API key if defined
        - The guild API key if defined
        - True if no API key is required for this
        - False otherwise
        """
        # Global
        if service_name in self.supported_global_services:
            service_keys = await self.bot.get_shared_api_tokens(service_name)
            api_key = service_keys.get("api_key", False)
            if api_key:
                return api_key
        else:
            # Guild
            if not guild_service_config:
                guild_service_config = {}
            api_key = guild_service_config.get(service_name, {}).get("api_key", False)
            if api_key:
                return api_key
        # API not required, otherwise fail
        service_class = self.all_supported_services.get(service_name, None)
        return service_class and not service_class().SERVICE_API_KEY_REQUIRED

    def get_nice_service_name(self, service: str) -> str:
        """Get the nice name for a service."""
        result = self.all_supported_services.get(service, None)
        if result:
            return result.SERVICE_NAME
        return f"`{service}`"

    @staticmethod
    async def send_embed(
        channel_or_ctx: commands.Context | discord.TextChannel,
        embed: discord.Embed,
    ) -> bool:
        """Send an embed. If the bot can't send it, complains about permissions."""
        destination = (
            channel_or_ctx.channel
            if isinstance(channel_or_ctx, commands.Context)
            else channel_or_ctx
        )
        if (
            hasattr(destination, "guild")
            and destination.guild
            and not destination.permissions_for(destination.guild.me).embed_links
        ):
            await destination.send(
                error("I need the `Embed links` permission to function properly")
            )
            return False
        await destination.send(embed=embed)
        return True

    @staticmethod
    def embed_maker(
        title: str | None,
        color: discord.Colour | None,
        description: str | None,
        avatar: str | None = None,
    ) -> discord.Embed:
        """Create a nice embed."""
        embed = discord.Embed(title=title, color=color, description=description)
        if avatar:
            embed.set_thumbnail(url=avatar)
        return embed
