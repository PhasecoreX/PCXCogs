"""BanCheck cog for Red-DiscordBot ported and enhanced by PhasecoreX."""
import asyncio
import time
from typing import Any, Dict, Union

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import error, info, question, warning
from redbot.core.utils.predicates import MessagePredicate

from .pcx_lib import checkmark, delete
from .services.alertbot import Alertbot
from .services.globan import Globan
from .services.imgur import Imgur
from .services.ksoftsi import KSoftSi

__author__ = "PhasecoreX"


class BanCheck(commands.Cog):
    """Look up users on various ban lists.

    Admins can lookup users on all supported and enabled global banning
    services at the same time. Admins can also have all new users
    automatically checked when they join the guild, and optionally
    banned if they are found on a list.
    """

    default_global_settings = {"schema_version": 0, "total_bans": 0}
    default_guild_settings: Any = {
        "notify_channel": None,
        "total_bans": 0,
        "services": {},
    }
    supported_global_services = {"ksoftsi": KSoftSi}
    supported_guild_services = {"alertbot": Alertbot, "globan": Globan}
    all_supported_services = {**supported_global_services, **supported_guild_services}

    def __init__(self, bot):
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)
        self.member_join_cache: Dict[int, int] = {}

    async def initialize(self):
        """Perform setup actions before loading cog."""
        await self._migrate_config()

    async def _migrate_config(self):
        """Perform some configuration migrations."""
        if not await self.config.schema_version():
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

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    @commands.group()
    @checks.is_owner()
    async def banchecksetglobal(self, ctx: commands.Context):
        """Configure global BanCheck settings."""
        pass

    @banchecksetglobal.command(name="settings")
    async def global_settings(self, ctx: commands.Context):
        """Display current settings."""
        embed = discord.Embed(
            title="BanCheck Global Settings",
            description=(
                "Setting an API key globally will allow any guild this bot is in to use that service for ban checking. "
                "These services require the bot itself to go through an approval process, and "
                "only allow one API key per bot."
            ),
            color=await ctx.embed_color(),
        )
        total_bans = await self.config.total_bans()
        users = "user" if total_bans == 1 else "users"
        total_guilds = len(self.bot.guilds)
        guilds = "guild" if total_guilds == 1 else "guilds"
        embed.set_footer(
            text=f"AutoBanned a total of {total_bans} {users} across {total_guilds} {guilds}"
        )
        enabled_services = ""
        disabled_services = ""
        for service_name in self.supported_global_services:
            if await self.get_api_key(service_name):
                enabled_services += (
                    f"{await self.format_service_name_url(service_name)}\n"
                )
            else:
                disabled_services += (
                    f"{await self.format_service_name_url(service_name, True)}\n"
                )
        if enabled_services:
            embed.add_field(
                name=checkmark("API Keys Set"), value=enabled_services, inline=False
            )
        if disabled_services:
            embed.add_field(
                name=error("API Keys Not Set"), value=disabled_services, inline=False
            )
        await self.send_embed(ctx, embed)

    @banchecksetglobal.command(name="api")
    async def global_api(
        self, ctx: commands.Context, service: str, api_key: str = None
    ):
        """Get information on setting an API key for a global service."""
        if api_key:
            # Try deleting the command as fast as possible, so that others can't see the API key
            await delete(ctx.message)
        if service in self.supported_guild_services:
            await ctx.send(
                info(
                    f"{self.get_nice_service_name(service)} is not a global service, "
                    "and should be set up per guild using the command:\n\n"
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
        await ctx.send(
            info(
                "Global API keys are no longer set here. You should run this command instead:\n\n"
                f"`[p]set api {service} api_key <your_api_key_here>`"
            )
        )

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def bancheckset(self, ctx: commands.Context):
        """Configure BanCheck for this guild."""
        pass

    @bancheckset.command()
    async def settings(self, ctx: commands.Context):
        """Display current settings."""
        embed = discord.Embed(title="BanCheck Settings", color=await ctx.embed_color())
        embed.set_thumbnail(
            url=ctx.guild.icon_url
            if ctx.guild.icon_url
            else "https://cdn.discordapp.com/embed/avatars/1.png"
        )
        total_bans = await self.config.guild(ctx.guild).total_bans()
        users = "user" if total_bans == 1 else "users"
        embed.set_footer(
            text=f"AutoBanned a total of {total_bans} {users} in this guild"
        )
        # Get info
        any_enabled = False
        autoban_services = 0
        config_services = await self.config.guild(ctx.guild).services()
        for service_name, service_config in config_services.items():
            if (
                service_name in self.all_supported_services
                and service_config.get("enabled", False)
                and await self.get_api_key(service_name, config_services)
            ):
                any_enabled = True
                if service_config.get("autoban", False):
                    autoban_services += 1
        notify_channel = None
        notify_channel_id = await self.config.guild(ctx.guild).notify_channel()
        if notify_channel_id:
            notify_channel = self.bot.get_channel(notify_channel_id)
        self._get_autocheck_status(embed, notify_channel, any_enabled)
        self._get_autoban_status(
            embed,
            notify_channel,
            autoban_services,
            ctx.guild.me.guild_permissions.ban_members,
        )
        # Service status
        enabled_services = ""
        disabled_services = ""
        for service_name in self.all_supported_services:
            if config_services.get(service_name, {}).get(
                "enabled", False
            ) and await self.get_api_key(service_name, config_services):
                enabled_services += f"**{self.get_nice_service_name(service_name)}**"
                if config_services.get(service_name, {}).get("autoban", False):
                    enabled_services += " (AutoBan enabled)"
                enabled_services += "\n"
            else:
                disabled_services += f"**{self.get_nice_service_name(service_name)}**"
                if not await self.get_api_key(service_name, config_services):
                    if service_name in self.supported_global_services:
                        disabled_services += " (Global API key not set)"
                    else:
                        disabled_services += " (API key not set)"
                disabled_services += "\n"
        if enabled_services:
            embed.add_field(
                name=checkmark("Enabled Services"), value=enabled_services, inline=False
            )
        if disabled_services:
            embed.add_field(
                name=error("Disabled Services"), value=disabled_services, inline=False
            )
        await self.send_embed(ctx, embed)

    @staticmethod
    def _get_autocheck_status(embed, notify_channel, any_enabled):
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
                name=checkmark("AutoCheck"),
                value="**Enabled**\n(On join)",
            )
        # AutoCheck Channel status
        if notify_channel:
            embed.add_field(
                name=checkmark("AutoCheck Channel"),
                value=notify_channel.mention,
            )
        else:
            embed.add_field(name=error("AutoCheck Channel"), value="**Not set**")

    @staticmethod
    def _get_autoban_status(
        embed, notify_channel, autoban_services, ban_members_permission
    ):
        """Add AutoBan information to the embed."""
        if not notify_channel:
            embed.add_field(
                name=error("AutoBan"),
                value="**Disabled**\n(AutoCheck not enabled)",
            )
        elif not autoban_services:
            embed.add_field(
                name=error("AutoBan"),
                value="**Disabled**\n(no BanCheck services are set to AutoBan)",
            )
        elif not ban_members_permission:
            embed.add_field(
                name=error("AutoBan"),
                value="**Disabled**\n(Bot lacks Ban Members permission)",
            )
        else:
            embed.add_field(
                name=checkmark("AutoBan"),
                value=f"**Enabled**\n({autoban_services} {'service' if autoban_services == 1 else 'services'})",
            )

    @bancheckset.group()
    async def service(self, ctx: commands.Context):
        """Manage the services BanCheck will use to lookup users."""
        pass

    @service.command(name="settings")
    async def service_settings(self, ctx: commands.Context):
        """Display current settings."""
        embed = discord.Embed(
            title="BanCheck Service Settings",
            color=await ctx.embed_color(),
        )
        embed.set_thumbnail(
            url=ctx.guild.icon_url
            if ctx.guild.icon_url
            else "https://cdn.discordapp.com/embed/avatars/1.png"
        )
        config_services = await self.config.guild(ctx.guild).services()
        enabled_services = ""
        disabled_services = ""
        for service_name in self.all_supported_services:
            api_key = await self.get_api_key(service_name, config_services)
            if api_key and config_services.get(service_name, {}).get("enabled", False):
                enabled_services += (
                    f"{await self.format_service_name_url(service_name)}\n"
                )
            else:
                reason = ""
                if not api_key:
                    if service_name in self.supported_global_services:
                        reason = "(Global API key not set)"
                    else:
                        reason = "(API key not set)"
                disabled_services += "{}\n".format(
                    await self.format_service_name_url(
                        service_name,
                        True
                        if service_name in self.supported_guild_services
                        else False,
                        reason,
                    )
                )
        if enabled_services:
            embed.add_field(
                name=checkmark("Enabled Services"), value=enabled_services, inline=False
            )
        if disabled_services:
            embed.add_field(
                name=error("Disabled Services"), value=disabled_services, inline=False
            )
        await self.send_embed(ctx, embed)

    @service.command(name="api")
    async def service_api(
        self, ctx: commands.Context, service: str, api_key: str = None
    ):
        """Set (or delete) an API key for a service."""
        # Try deleting the command as fast as possible, so that others can't see the API key
        await delete(ctx.message)
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
                checkmark(
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
        await ctx.send(checkmark(response))

    @service.command(name="enable")
    async def service_enable(self, ctx: commands.Context, service: str):
        """Enable a service."""
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
            await ctx.send(checkmark(response))

    @service.command(name="disable")
    async def service_disable(self, ctx: commands.Context, service: str):
        """Disable a service."""
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
        await ctx.send(checkmark(response))

    @bancheckset.group()
    async def autoban(self, ctx: commands.Context):
        """Manage which services are allowed to ban users automatically."""

    @autoban.command(name="enable")
    async def autoban_enable(self, ctx: commands.Context, service: str):
        """Enable a service to ban users automatically."""
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
            await ctx.send(checkmark(response))

    @autoban.command(name="disable")
    async def autoban_disable(self, ctx: commands.Context, service: str):
        """Disable a service from banning users automatically."""
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
        await ctx.send(checkmark(response))

    @bancheckset.group()
    async def autocheck(self, ctx: commands.Context):
        """Automatically perform BanChecks on new users."""

    @autocheck.command(name="set")
    async def set_autocheck(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Set the channel you want AutoCheck notifications to go to."""
        if channel is None:
            channel = ctx.message.channel
        if await self.send_embed(
            channel,
            self.embed_maker(
                None,
                discord.Colour.green(),
                "\N{WHITE HEAVY CHECK MARK} **I will send all AutoCheck notifications here.**",
                self.bot.user.avatar_url,
            ),
        ):
            await self.config.guild(ctx.guild).notify_channel.set(channel.id)

    @autocheck.command(name="disable")
    async def disable_autocheck(self, ctx: commands.Context):
        """Disable automatically checking new users against ban lists."""
        if await self.config.guild(ctx.guild).notify_channel() is None:
            await ctx.send(info("AutoCheck is already disabled."))
        else:
            await self.config.guild(ctx.guild).notify_channel.set(None)
            await ctx.send(checkmark("AutoCheck is now disabled."))

    @commands.command()
    @commands.guild_only()
    # Only the owner for now, until I do some research on who to open it up to
    @checks.is_owner()
    # @checks.admin_or_permissions(ban_members=True)
    async def banreport(
        self,
        ctx: commands.Context,
        member: Union[discord.Member, int],
        *,
        ban_message: str,
    ):
        """Send a ban report to all enabled global ban lists.

        This command can only be run as a comment on an uploaded image (ban proof).
        """
        if not ctx.message.attachments or not ctx.message.attachments[0].height:
            await ctx.send_help()
            return
        proof_image_url = ctx.message.attachments[0].url
        await self._user_report(ctx, proof_image_url, True, member, ban_message)

    @commands.command()
    @commands.guild_only()
    # Only the owner for now, until I do some research on who to open it up to
    @checks.is_owner()
    # @checks.admin_or_permissions(ban_members=True)
    async def banreportmanual(
        self,
        ctx: commands.Context,
        member: Union[discord.Member, int],
        proof_image_url: str,
        *,
        ban_message: str,
    ):
        """Send a ban report to all enabled global ban lists.

        This command requires an uploaded image URL (ban proof).
        If you want to upload an image via Discord,
        use the [p]banreport command instead.
        """
        await self._user_report(ctx, proof_image_url, False, member, ban_message)

    async def _user_report(
        self,
        ctx: commands.Context,
        image_proof_url: str,
        do_imgur_upload: bool,
        member: Union[discord.Member, int],
        ban_message: str,
    ):
        """Perform user report."""
        description = ""
        sent = []
        is_error = False
        config_services = await self.config.guild(ctx.guild).services()
        if isinstance(member, discord.Member):
            member_id = member.id
            member_avatar_url = member.avatar_url
        else:
            member_id = member
            member_avatar_url = None

        # Gather services that can have reports sent to them
        report_services = []
        for service_name, service_config in config_services.items():
            if not service_config.get("enabled", False):
                continue  # This service is not enabled
            service_class = self.all_supported_services.get(service_name, False)
            if not service_class:
                continue  # This service is not supported
            try:
                service_class().report
            except AttributeError:
                continue  # This service does not support reporting
            api_key = await self.get_api_key(service_name, config_services)
            if not api_key:
                continue  # This service needs an API key set to work
            report_services.append(service_class())

        # Send error if there are no services to send to
        if not report_services:
            await self.send_embed(
                ctx.channel,
                self.embed_maker(
                    "Error",
                    discord.Colour.red(),
                    "No services have been set up. Please check `[p]bancheckset` for more details.",
                    member_avatar_url,
                ),
            )
            return

        # Upload to Imgur if needed
        if do_imgur_upload:
            service_keys = await self.bot.get_shared_api_tokens("imgur")
            imgur_client_id = service_keys.get("client_id", False)
            if not imgur_client_id:
                await ctx.send(
                    error(
                        "This command requires that you have an Imgur Client ID. Please set one with `.imgurcreds`."
                    )
                )
                return
            image_proof_url = await Imgur.upload(image_proof_url, imgur_client_id)
            if not image_proof_url:
                await ctx.send(
                    error(
                        "Uploading image to Imgur failed. Ban report has not been sent."
                    )
                )
                return

        # Ask if the user really wants to do this
        pred = MessagePredicate.yes_or_no(ctx)
        await ctx.send(
            question(
                f"Are you **sure** you want to send this ban report for **{member}**? (yes/no)"
            )
        )
        try:
            await ctx.bot.wait_for("message", check=pred, timeout=30)
        except asyncio.TimeoutError:
            pass
        if pred.result:
            pass
        else:
            await ctx.send(error("Sending ban report has been canceled."))
            return

        # Send report to services
        for report_service in report_services:
            response = await report_service.report(
                member_id, api_key, ctx.author.id, ban_message, image_proof_url
            )
            sent.append(response.service)
            if response.result and response.reason:
                description += checkmark(
                    f"**{response.service}:** Sent ({response.reason})\n"
                )
            elif response.result:
                description += checkmark(f"**{response.service}:** Sent\n")
            else:
                is_error = True
                description += error(
                    f"**{response.service}:** Failure ({response.reason if response.reason else 'No reason given'})\n"
                )

        # Generate results
        if is_error:
            await self.send_embed(
                ctx.channel,
                self.embed_maker(
                    f"Errors occured while sending reports for **{member}**",
                    discord.Colour.red(),
                    description,
                    member_avatar_url,
                ),
            )
        else:
            await self.send_embed(
                ctx.channel,
                self.embed_maker(
                    f"Reports sent for **{member}**",
                    discord.Colour.green(),
                    f"Services: {', '.join(sent)}",
                    member_avatar_url,
                ),
            )

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(ban_members=True)
    async def bancheck(
        self, ctx: commands.Context, member: Union[discord.Member, int] = None
    ):
        """Check if user is on a ban list."""
        if not member:
            member = ctx.message.author
        async with ctx.channel.typing():
            await self._user_lookup(ctx.channel, member, False)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """If enabled, will check users against ban lists when joining the guild."""
        if await self.bot.cog_disabled_in_guild(self, member.guild):
            return
        channel_id = await self.config.guild(member.guild).notify_channel()
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                # Only do auto lookup if the user isn't repeatedly leaving and joining the server
                current_time = int(time.time())
                past_time = current_time - 300  # 5 minutes ago
                if (
                    member.id not in self.member_join_cache
                    or self.member_join_cache[member.id] < past_time
                ):
                    await self._user_lookup(channel, member, True)
                self.member_join_cache[member.id] = current_time
                # Clear old entries out of the cache
                cache_clear = []
                for user_id, join_time in self.member_join_cache.items():
                    if join_time < past_time:
                        cache_clear.append(user_id)
                for user_id in cache_clear:
                    del self.member_join_cache[user_id]

    async def _user_lookup(
        self,
        channel: discord.TextChannel,
        member: Union[discord.Member, int],
        on_member_join: bool,
    ):
        """Perform user lookup, and send results to a specific channel."""
        config_services = await self.config.guild(channel.guild).services()
        banned_services: Dict[str, str] = {}
        auto_banned = False
        is_error = False
        checked = []
        if isinstance(member, discord.Member):
            description = f"**Name:** {member.name}\n**ID:** {member.id}\n\n"
            member_id = member.id
            member_avatar_url = member.avatar_url
        else:
            description = f"**ID:** {member}\n\n"
            member_id = member
            member_avatar_url = None

        # Get results
        for service_name, service_config in config_services.items():
            if not service_config.get("enabled", False):
                continue
            autoban = service_config.get("autoban", False)
            service_class = self.all_supported_services.get(service_name, False)
            if not service_class:
                continue
            api_key = await self.get_api_key(service_name, config_services)
            if not api_key:
                continue
            try:
                service_class().lookup
            except AttributeError:
                continue  # This service does not support lookup
            response = await service_class().lookup(member_id, api_key)
            checked.append(response.service)

            if response.result == "ban":
                banned_services[response.service] = response.reason
                if on_member_join and autoban:
                    auto_banned = True

                proof = " (No proof provided)"
                if response.proof_url:
                    proof = f" ([proof]({response.proof_url}))"

                description += error(
                    f"**{response.service}:** {response.reason}{proof}\n"
                )

            elif response.result == "clear":
                description += checkmark(f"**{response.service}:** No ban found\n")

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
                and channel.guild.me.guild_permissions.ban_members
            ):
                try:
                    await member.send(
                        "Hello! Since you are currently on {} ({}), you have automatically been banned from {}.".format(
                            "a global ban list"
                            if len(banned_services) == 1
                            else "multiple global ban lists",
                            ", ".join(banned_services),
                            member.guild,
                        )
                    )
                except (discord.Forbidden, discord.NotFound):
                    pass  # Couldn't message user for some reason...
                try:
                    reasons = []
                    for name, reason in banned_services.items():
                        reasons.append(f"{name} ({reason})")
                    await channel.guild.ban(
                        member,
                        reason=f"BanCheck auto ban: {', '.join(reasons)}",
                        delete_message_days=1,
                    )
                    # Update guild ban totals
                    total_bans = await self.config.guild(channel.guild).total_bans()
                    await self.config.guild(channel.guild).total_bans.set(
                        total_bans + 1
                    )
                    # Update global ban totals
                    global_total_bans = await self.config.total_bans()
                    await self.config.total_bans.set(global_total_bans + 1)
                    title += " - Auto Banned"
                except (discord.Forbidden, discord.HTTPException):
                    title += " - Not allowed to Auto Ban"
            await self.send_embed(
                channel,
                self.embed_maker(
                    title, discord.Colour.red(), description, member_avatar_url
                ),
            )
        elif is_error:
            await self.send_embed(
                channel,
                self.embed_maker(
                    "Error (but no ban found otherwise)",
                    discord.Colour.gold(),
                    description,
                    member_avatar_url,
                ),
            )
        elif not checked and on_member_join:
            pass  # No services have been enabled when auto checking
        elif not checked:
            await self.send_embed(
                channel,
                self.embed_maker(
                    "Error",
                    discord.Colour.gold(),
                    "No services have been set up. Please check `[p]bancheckset` for more details.",
                    member_avatar_url,
                ),
            )
        else:
            await self.send_embed(
                channel,
                self.embed_maker(
                    f"No ban found for **{member}**",
                    discord.Colour.green(),
                    f"Checked: {', '.join(checked)}",
                    member_avatar_url,
                ),
            )

    async def format_service_name_url(self, service_name, show_help=False, reason=""):
        """Format BanCheck services."""
        service_class = self.all_supported_services.get(service_name, False)
        if not service_class:
            return f"`{service_name}`"
        result = f" `{service_name}` - [{service_class.SERVICE_NAME}]({service_class.SERVICE_URL})"
        if reason:
            result += f" {reason}"
        if show_help:
            try:
                result += f" ({service_class.SERVICE_HINT})"
            except AttributeError:
                pass  # No hint for this service
        return result

    async def get_api_key(self, service_name: str, guild_service_config=None):
        """Get the API key for this service.

        Returns the first:
        - False if this isn't a valid service
        - The global API key if defined
        - The guild level API key if defined
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
        # API not required
        service_class = self.all_supported_services.get(service_name, False)
        if service_class and not service_class().SERVICE_API_KEY_REQUIRED:
            return True
        # Fail
        return False

    def get_nice_service_name(self, service: str):
        """Get the nice name for a service."""
        result = self.all_supported_services.get(service, False)
        if result:
            return result.SERVICE_NAME
        return f"`{service}`"

    @staticmethod
    async def send_embed(ctx, embed):
        """Send an embed. If the bot can't send it, complains about permissions."""
        try:
            await ctx.send(embed=embed)
            return True
        except discord.HTTPException:
            await ctx.send(
                error("I need the `Embed links` permission to function properly")
            )
            return False

    @staticmethod
    def embed_maker(title, color, description, avatar=None):
        """Create a nice embed."""
        embed = discord.Embed(title=title, color=color, description=description)
        if avatar:
            embed.set_thumbnail(url=avatar)
        return embed
