"""BanCheck cog for Red-DiscordBot ported and enhanced by PhasecoreX."""
from typing import Any, Dict

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import error, info

from .services.alertbot import alertbot
from .services.globan import globan
from .services.ksoftsi import ksoftsi

__author__ = "PhasecoreX"
__version__ = "1.2.0"


class BanCheck(commands.Cog):
    """Look up users on various ban lists."""

    default_guild_settings: Any = {"notify_channel": None, "services": {}}
    supported_global_services = {"globan": globan, "ksoftsi": ksoftsi}
    supported_guild_services = {"alertbot": alertbot}
    all_supported_services = {**supported_global_services, **supported_guild_services}

    def __init__(self, bot):
        """Set up the plugin."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1224364860)
        self.config.register_guild(**self.default_guild_settings)

    async def initialize(self):
        """Perform setup actions before loading cog."""
        await self._maybe_update_config()

    async def _maybe_update_config(self):
        """Perform some configuration migrations."""
        if await self.config.version() == __version__:
            return
        guild_dict = await self.config.all_guilds()
        for guild_id, guild_info in guild_dict.items():
            # Migrate channel -> notify_channel
            channel = guild_info.get("channel", False)
            if channel:
                await self.config.guild(discord.Object(id=guild_id)).notify_channel.set(
                    channel
                )
                await self.config.guild(discord.Object(id=guild_id)).clear_raw(
                    "channel"
                )
            # Migrate enabled/disabled global services per guild
            auto_ban = guild_info.get("auto_ban", False)
            disabled_services = guild_info.get("disabled_services", [])
            disabled_auto_ban_services = guild_info.get(
                "disabled_auto_ban_services", []
            )
            config_services = await self.config.guild(
                discord.Object(id=guild_id)
            ).services()
            for service in self.supported_global_services:
                if service in config_services:
                    continue
                config_services[service] = {}
                config_services[service]["autoban"] = (
                    auto_ban and service not in disabled_auto_ban_services
                )
                config_services[service]["enabled"] = service not in disabled_services
            await self.config.guild(discord.Object(id=guild_id)).services.set(
                config_services
            )
            # Delete old config keys
            await self.config.guild(discord.Object(id=guild_id)).clear_raw("auto_ban")
            await self.config.guild(discord.Object(id=guild_id)).clear_raw(
                "disabled_services"
            )
            await self.config.guild(discord.Object(id=guild_id)).clear_raw(
                "disabled_auto_ban_services"
            )
        # Migrate global API keys to Red core
        services_dict = await self.config.services()
        if services_dict:
            for service_id, service_info in services_dict.items():
                api_key = service_info.get("api_key", False)
                service_keys = await self.bot.get_shared_api_tokens(service_id)
                if api_key and not service_keys.get("api_key", False):
                    await self.bot.set_shared_api_tokens(service_id, api_key=api_key)
            await self.config.clear_raw("services")
        await self.config.version.set(__version__)

    @commands.group()
    @checks.is_owner()
    async def banchecksetglobal(self, ctx: commands.Context):
        """Configure BanCheck."""
        if ctx.invoked_subcommand:
            return
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
        if not total_bans:
            total_bans = 0
        users = "user" if total_bans == 1 else "users"
        total_guilds = len(self.bot.guilds)
        guilds = "guild" if total_guilds == 1 else "guilds"
        embed.set_footer(
            text="AutoBanned a total of {} {} across {} {}".format(
                total_bans, users, total_guilds, guilds
            )
        )
        enabled_services = ""
        disabled_services = ""
        for service_name in self.supported_global_services:
            if await self.get_api_key(service_name):
                enabled_services += "{}\n".format(
                    await self.format_service_name_url(service_name)
                )
            else:
                disabled_services += "{}\n".format(
                    await self.format_service_name_url(service_name, True)
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
            try:
                await ctx.message.delete()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                pass
        if service in self.supported_guild_services:
            await ctx.send(
                info(
                    "{} is not a global service, and should be set up per guild ".format(
                        self.get_nice_service_name(service)
                    )
                    + "using the command:\n\n"
                    + "`[p]bancheckset service api {} <your_api_key_here>`".format(
                        service
                    )
                )
            )
            return
        if service not in self.supported_global_services:
            await ctx.send(
                error(
                    "{} is not a valid service name.".format(
                        self.get_nice_service_name(service)
                    )
                )
            )
            return
        await ctx.send(
            info(
                "Global API keys are no longer set here. You should run this command instead:\n\n"
                + "`[p]set api {} api_key <your_api_key_here>`".format(service)
            )
        )

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def bancheckset(self, ctx: commands.Context):
        """Configure BanCheck."""
        if ctx.invoked_subcommand:
            return
        embed = discord.Embed(title="BanCheck Settings", color=await ctx.embed_color())
        embed.set_thumbnail(
            url=ctx.guild.icon_url
            if ctx.guild.icon_url
            else "https://cdn.discordapp.com/embed/avatars/1.png"
        )
        total_bans = await self.config.total_bans()
        if not total_bans:
            total_bans = 0
        users = "user" if total_bans == 1 else "users"
        embed.set_footer(text="AutoBanned a total of {} {}".format(total_bans, users))
        # Get info
        any_enabled = False
        autoban_services = 0
        config_services = await self.config.guild(ctx.message.guild).services()
        for service_name, service_config in config_services.items():
            if (
                service_name in self.all_supported_services
                and service_config.get("enabled", False)
                and await self.get_api_key(service_name, config_services)
            ):
                any_enabled = True
                if service_config.get("autoban", False):
                    autoban_services += 1
        # AutoCheck status
        notify_channel = None
        notify_channel_id = await self.config.guild(ctx.message.guild).notify_channel()
        if notify_channel_id:
            notify_channel = self.bot.get_channel(notify_channel_id)
        if notify_channel and any_enabled:
            embed.add_field(
                name=checkmark("AutoCheck"), value="**Enabled**\n(On join)",
            )
        elif not notify_channel:
            embed.add_field(
                name=error("AutoCheck"),
                value="**Disabled**\n(AutoCheck notification channel not set)",
            )
        else:
            embed.add_field(
                name=error("AutoCheck"),
                value="**Disabled**\n(No services are enabled)",
            )
        # AutoCheck Channel status
        if notify_channel:
            embed.add_field(
                name=checkmark("AutoCheck Channel"),
                value="<#{}>".format(notify_channel.id),
            )
        else:
            embed.add_field(name=error("AutoCheck Channel"), value="**Not set**")
        # AutoBan status
        if not notify_channel:
            embed.add_field(
                name=error("AutoBan"), value="**Disabled**\n(AutoCheck not enabled)",
            )
        elif not autoban_services:
            embed.add_field(
                name=error("AutoBan"),
                value="**Disabled**\n(no BanCheck services are set to AutoBan)",
            )
        elif not ctx.guild.me.guild_permissions.ban_members:
            embed.add_field(
                name=error("AutoBan"),
                value="**Disabled**\n(Bot lacks Ban Members permission)",
            )
        else:
            embed.add_field(
                name=checkmark("AutoBan"),
                value="**Enabled**\n({} {})".format(
                    autoban_services, "service" if autoban_services == 1 else "services"
                ),
            )
        # Service status
        enabled_services = ""
        disabled_services = ""
        for service_name in self.all_supported_services:
            if config_services.get(service_name, {}).get(
                "enabled", False
            ) and await self.get_api_key(service_name, config_services):
                enabled_services += "**{}**".format(
                    self.get_nice_service_name(service_name)
                )
                if config_services.get(service_name, {}).get("autoban", False):
                    enabled_services += " (AutoBan enabled)"
                enabled_services += "\n"
            else:
                disabled_services += "**{}**".format(
                    self.get_nice_service_name(service_name)
                )
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

    @bancheckset.group()
    async def service(self, ctx: commands.Context):
        """Manage the services BanCheck will use to lookup users."""
        if ctx.invoked_subcommand:
            return
        embed = discord.Embed(
            title="BanCheck Service Settings", color=await ctx.embed_color(),
        )
        embed.set_thumbnail(
            url=ctx.guild.icon_url
            if ctx.guild.icon_url
            else "https://cdn.discordapp.com/embed/avatars/1.png"
        )
        config_services = await self.config.guild(ctx.message.guild).services()
        enabled_services = ""
        disabled_services = ""
        for service_name in self.all_supported_services:
            api_key = await self.get_api_key(service_name, config_services)
            if api_key and config_services.get(service_name, {}).get("enabled", False):
                enabled_services += "{}\n".format(
                    await self.format_service_name_url(service_name)
                )
            else:
                reason = ""
                if not api_key:
                    if service_name in self.supported_global_services:
                        reason = "(Global API key not set)"
                    else:
                        reason = "(API key not set)"
                disabled_services += "{}\n".format(
                    await self.format_service_name_url(service_name, True, reason)
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
        message_guild = ctx.message.guild
        # Try deleting the command as fast as possible, so that others can't see the API key
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass
        if service not in self.all_supported_services:
            await ctx.send(
                error(
                    "{} is not a valid service name.".format(
                        self.get_nice_service_name(service)
                    )
                )
            )
            return
        if (
            service in self.supported_global_services
            and not self.supported_global_services[service].SERVICE_API_KEY_REQUIRED
        ):
            await ctx.send(
                checkmark(
                    "{} does not require an API key.".format(
                        self.get_nice_service_name(service)
                    )
                )
            )
            return
        if service in self.supported_global_services:
            if await ctx.bot.is_owner(ctx.author):
                await ctx.send(
                    info(
                        "The API key for {} can only be set up globally. See `[p]banchecksetglobal` for more information.".format(
                            self.get_nice_service_name(service)
                        )
                    )
                )
            else:
                await ctx.send(
                    error(
                        "The API key for {} can only be set up by the bot owner.".format(
                            self.get_nice_service_name(service)
                        )
                    )
                )
            return
        config_services = await self.config.guild(message_guild).services()
        if service not in config_services:
            config_services[service] = {}
        config_services[service]["api_key"] = api_key
        await self.config.guild(message_guild).services.set(config_services)
        action = "set"
        if not api_key:
            action = "removed"
        response = "API key for the {} BanCheck service has been {}.".format(
            self.get_nice_service_name(service), action
        )
        await ctx.send(checkmark(response))

    @service.command(name="enable")
    async def service_enable(self, ctx: commands.Context, service: str):
        """Enable a service."""
        if service not in self.all_supported_services:
            await ctx.send(
                error(
                    "{} is not a valid service name.".format(
                        self.get_nice_service_name(service)
                    )
                )
            )
            return
        config_services = await self.config.guild(ctx.message.guild).services()
        if service not in config_services:
            config_services[service] = {}
        config_services[service]["enabled"] = True
        await self.config.guild(ctx.message.guild).services.set(config_services)
        response = "Enabled the {} BanCheck service.".format(
            self.get_nice_service_name(service)
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
        config_services = await self.config.guild(ctx.message.guild).services()
        if not config_services.get(service, {}).get("enabled", False):
            await ctx.send(
                info(
                    "{} is not an enabled service.".format(
                        self.get_nice_service_name(service)
                    )
                )
            )
            return
        config_services[service]["enabled"] = False
        await self.config.guild(ctx.message.guild).services.set(config_services)
        response = "Disabled the {} BanCheck service.".format(
            self.get_nice_service_name(service)
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
                    "{} is not a valid service name.".format(
                        self.get_nice_service_name(service)
                    )
                )
            )
            return
        config_services = await self.config.guild(ctx.message.guild).services()
        if service not in config_services:
            config_services[service] = {}
        config_services[service]["autoban"] = True
        config_services[service]["enabled"] = True
        await self.config.guild(ctx.message.guild).services.set(config_services)
        response = "Automatic banning with {} has now been enabled.".format(
            self.get_nice_service_name(service)
        )
        if not await self.config.guild(ctx.message.guild).notify_channel():
            response += (
                "\nYou will need to set up AutoCheck in order for this to take effect."
            )
        if not await self.get_api_key(service, config_services):
            response += "\nAn API key is needed in order for this to take effect."
        if not ctx.message.guild.me.guild_permissions.ban_members:
            response += "\nI will need to be granted the Ban Members permission for this to take effect."
        await ctx.send(checkmark(response))

    @autoban.command(name="disable")
    async def autoban_disable(self, ctx: commands.Context, service: str):
        """Disable a service from banning users automatically."""
        config_services = await self.config.guild(ctx.message.guild).services()
        if not config_services.get(service, {}).get("autoban", False):
            await ctx.send(
                info(
                    "Automatic banning with {} is already disabled.".format(
                        self.get_nice_service_name(service)
                    )
                )
            )
            return
        config_services[service]["autoban"] = False
        await self.config.guild(ctx.message.guild).services.set(config_services)
        response = "Automatic banning with {} has now been disabled.".format(
            self.get_nice_service_name(service)
        )
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
            await self.config.guild(ctx.message.guild).notify_channel.set(channel.id)

    @autocheck.command(name="disable")
    async def disable_autocheck(self, ctx: commands.Context):
        """Disable automatically checking new users against ban lists."""
        if await self.config.guild(ctx.message.guild).notify_channel() is None:
            await ctx.send(info("AutoCheck is already disabled."))
        else:
            await self.config.guild(ctx.message.guild).notify_channel.set(None)
            await ctx.send(checkmark("AutoCheck is now disabled."))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(ban_members=True)
    async def bancheck(self, ctx: commands.Context, member: discord.Member = None):
        """Check if user is on a ban list."""
        if not member:
            member = ctx.message.author
        async with ctx.channel.typing():
            await self.user_lookup(ctx.channel, member, False)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """If enabled, will check users against ban lists when joining the guild."""
        channel_id = await self.config.guild(member.guild).notify_channel()
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await self.user_lookup(channel, member, True)

    async def user_lookup(
        self, channel: discord.TextChannel, member: discord.Member, on_member_join: bool
    ):
        """Perform user lookup, and send results to a specific channel."""
        config_services = await self.config.guild(channel.guild).services()
        banned_services: Dict[str, str] = {}
        auto_banned = False
        is_error = False
        checked = []
        description = "**Name:** {}\n**ID:** {}\n\n".format(member.name, member.id)

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
            response = await service_class().lookup(member.id, api_key)
            checked.append(response.service)

            if response.result == "ban":
                banned_services[response.service] = response.reason
                if on_member_join and autoban:
                    auto_banned = True

                proof = " (No proof provided)"
                if response.proof_url:
                    proof = " ([proof]({}))".format(response.proof_url)

                description += "**{}:** {}{}\n".format(
                    response.service, response.reason, proof
                )

            elif response.result == "clear":
                description += "**{}:** (No ban found)\n".format(response.service)

            elif response.result == "error":
                is_error = True
                if response.reason:
                    description += "**{}:** Error - {}\n".format(
                        response.service, response.reason
                    )
                else:
                    description += "**{}:** Connection Error - Server responded with the HTTP code `{}`\n".format(
                        response.service, response.http_status
                    )

            else:
                is_error = True
                description += "**{}:** Fatal Error - You should probably let PhasecoreX know about this -> `{}`.\n".format(
                    response.service, response.result
                )

        # Display result
        if banned_services:
            title = "Ban Found"
            if auto_banned and channel.guild.me.guild_permissions.ban_members:
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
                        reasons.append("{} ({})".format(name, reason))
                    await channel.guild.ban(
                        member,
                        reason="BanCheck auto ban: {}".format(", ".join(reasons)),
                        delete_message_days=1,
                    )
                    # Update guild ban totals
                    total_bans = await self.config.guild(channel.guild).total_bans()
                    if not total_bans:
                        total_bans = 0
                    await self.config.guild(channel.guild).total_bans.set(
                        total_bans + 1
                    )
                    # Update global ban totals
                    global_total_bans = await self.config.total_bans()
                    if not global_total_bans:
                        global_total_bans = 0
                    await self.config.total_bans.set(global_total_bans + 1)
                    title += " - Auto Banned"
                except (discord.Forbidden, discord.HTTPException):
                    title += " - Not allowed to Auto Ban"
            await self.send_embed(
                channel,
                self.embed_maker(
                    title, discord.Colour.red(), description, member.avatar_url
                ),
            )
        elif is_error:
            await self.send_embed(
                channel,
                self.embed_maker(
                    "Error (but no ban found otherwise)",
                    discord.Colour.red(),
                    description,
                    member.avatar_url,
                ),
            )
        elif not checked and on_member_join:
            pass  # No services have been enabled when auto checking
        elif not checked:
            await self.send_embed(
                channel,
                self.embed_maker(
                    "Error",
                    discord.Colour.red(),
                    "No services have been set up. Please check `[p]bancheckset` for more details.",
                    member.avatar_url,
                ),
            )
        else:
            await self.send_embed(
                channel,
                self.embed_maker(
                    "No ban found for **{}**".format(member.name),
                    discord.Colour.green(),
                    "Checked: {}".format(", ".join(checked)),
                    member.avatar_url,
                ),
            )

    async def format_service_name_url(self, service_name, show_help=False, reason=""):
        """Format BanCheck services."""
        service_class = self.all_supported_services.get(service_name, False)
        if not service_class:
            return "`{}`".format(service_name)
        result = " `{}` - [{}]({})".format(
            service_name, service_class.SERVICE_NAME, service_class.SERVICE_URL
        )
        if reason:
            result += " {}".format(reason)
        if show_help:
            try:
                result += " ({})".format(service_class.SERVICE_HINT)
            except AttributeError:
                pass  # No hint for this service
        return result

    async def get_api_key(self, service_name: str, guild_service_config={}):
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
        return "`{}`".format(service)

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


def checkmark(text: str) -> str:
    """Get text prefixed with a checkmark emoji."""
    return "\N{WHITE HEAVY CHECK MARK} {}".format(text)
