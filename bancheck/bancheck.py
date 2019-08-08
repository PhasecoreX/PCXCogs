"""BanCheck cog for Red-DiscordBot ported and enhanced by PhasecoreX."""
from typing import Any, Dict

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import box, error, info

from .services.globan import globan
from .services.ksoftsi import ksoftsi

__author__ = "PhasecoreX"
__version__ = "1.0.0"


class BanCheck(commands.Cog):
    """Look up users on various ban lists."""

    default_global_settings: Any = {"services": {}}
    default_guild_settings = {
        "notify_channel": None,
        "auto_ban": False,
        "disabled_services": [],
        "disabled_auto_ban_services": [],
    }
    supported_services = {"globan": globan, "ksoftsi": ksoftsi}

    def __init__(self, bot):
        """Set up the plugin."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1224364860)
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)

    async def initialize(self):
        """Perform setup actions before loading cog."""
        await self._maybe_update_config()

    async def _maybe_update_config(self):
        """Perform some configuration migrations."""
        if await self.config.version():
            return
        guild_dict = await self.config.all_guilds()
        # Migrate channel -> notify_channel
        for guild_id, info in guild_dict.items():
            channel = info.get("channel", False)
            if channel:
                await self.config.guild(discord.Object(id=guild_id)).notify_channel.set(
                    channel
                )
                await self.config.guild(discord.Object(id=guild_id)).clear_raw(
                    "channel"
                )
        # Migrate guild services to global services
        for guild_id, info in guild_dict.items():
            services = info.get("services")
            if services:
                for service_id, info in services.items():
                    global_services = await self.config.services()
                    update = True
                    if service_id not in global_services:
                        global_services[service_id] = {}
                        global_services[service_id]["api_key"] = info["api_key"]
                        await self.config.services.set(global_services)
                await self.config.guild(discord.Object(id=guild_id)).clear_raw(
                    "services"
                )
        await self.config.version.set(__version__)

    @commands.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def bancheckset(self, ctx: commands.Context):
        """Configure BanCheck."""
        if not ctx.invoked_subcommand:
            msg = ""
            msg += await self.get_channel_message(ctx)
            msg += await self.get_auto_ban_message(ctx)
            msg += "Ban checking services:"
            msg += await self.get_available_services(ctx)
            await ctx.send(box(msg))

    @bancheckset.group()
    @checks.is_owner()
    async def api(self, ctx: commands.Context):
        """Globally set up BanCheck services."""
        if not ctx.invoked_subcommand:
            msg = "Supported services:"
            msg += await self.get_supported_services()
            try:
                embed = self.embed_maker(None, discord.Colour.green(), msg)
                await ctx.send(embed=embed)
            except (discord.errors.Forbidden):
                await ctx.send(msg)  # Embeds not allowed, send ugly message instead.

    @api.command(name="enable")
    async def api_enable(self, ctx: commands.Context, service: str, api: str):
        """Enable a service globally by specifying it's API key."""
        if service not in self.supported_services:
            msg = "The only services we support so far are:"
            msg += await self.get_supported_services()
            try:
                embed = self.embed_maker(None, discord.Colour.red(), msg)
                await ctx.send(embed=embed)
            except (discord.errors.Forbidden):
                await ctx.send(msg)  # Embeds not allowed, send ugly message instead.
            return
        services = await self.config.services()
        update = True
        if service not in services:
            services[service] = {}
            update = False
        services[service]["api_key"] = api
        await self.config.services.set(services)
        if update:
            await ctx.send(
                checkmark(
                    "Successfully updated the {} API key!".format(
                        self.get_nice_service_name(service)
                    )
                )
            )
        else:
            await ctx.send(
                checkmark(
                    "Ban checking with {} has now been enabled globally!".format(
                        self.get_nice_service_name(service)
                    )
                )
            )

    @api.command(name="disable")
    async def api_disable(self, ctx: commands.Context, service: str):
        """Disable a service globally by removing it's API key."""
        services = await self.config.services()
        if services.pop(service, None):
            await self.config.services.set(services)
            await ctx.send(
                checkmark(
                    "Ban checking with {} has now been disabled globally!".format(
                        self.get_nice_service_name(service)
                    )
                )
            )
        else:
            await ctx.send(
                error(
                    "`{}` is not an enabled service.".format(
                        self.get_nice_service_name(service)
                    )
                )
            )

    @bancheckset.group()
    @commands.guild_only()
    async def service(self, ctx: commands.Context):
        """Manage the services BanCheck will use to lookup users."""
        if not ctx.invoked_subcommand:
            msg = "Available services:"
            msg += await self.get_available_services(ctx)
            await ctx.send(box(msg))

    @service.command(name="enable")
    async def service_enable(self, ctx: commands.Context, service: str):
        """Enable a service."""
        disabled_services = await self.config.guild(
            ctx.message.guild
        ).disabled_services()
        if service in self.supported_services:
            try:
                disabled_services.remove(service)
                await self.config.guild(ctx.message.guild).disabled_services.set(
                    disabled_services
                )
                await ctx.send(
                    checkmark(
                        "Ban checking with {} has now been enabled for this guild!".format(
                            self.get_nice_service_name(service)
                        )
                    )
                )
            except ValueError:
                await ctx.send(
                    info(
                        "{} is already enabled for this guild.".format(
                            self.get_nice_service_name(service)
                        )
                    )
                )
        else:
            await ctx.send(
                error(
                    "`{}` is not a valid service name.".format(
                        self.get_nice_service_name(service)
                    )
                )
            )

    @service.command(name="disable")
    async def service_disable(self, ctx: commands.Context, service: str):
        """Disable a service."""
        disabled_services = await self.config.guild(
            ctx.message.guild
        ).disabled_services()
        if service in self.supported_services and service in disabled_services:
            await ctx.send(
                info(
                    "{} is already disabled for this guild.".format(
                        self.get_nice_service_name(service)
                    )
                )
            )
        elif service in self.supported_services:
            disabled_services.append(service)
            await self.config.guild(ctx.message.guild).disabled_services.set(
                disabled_services
            )
            await ctx.send(
                checkmark(
                    "Ban checking with {} has now been disabled for this guild!".format(
                        self.get_nice_service_name(service)
                    )
                )
            )
        else:
            await ctx.send(
                error(
                    "`{}` is not a valid service name.".format(
                        self.get_nice_service_name(service)
                    )
                )
            )

    @bancheckset.group()
    @commands.guild_only()
    async def autoban(self, ctx: commands.Context):
        """Manage which services are allowed to ban users automatically."""
        if not ctx.invoked_subcommand:
            msg = await self.get_auto_ban_message(ctx, False)
            if await self.config.guild(ctx.message.guild).auto_ban():
                disabled_auto_ban_services = await self.config.guild(
                    ctx.message.guild
                ).disabled_auto_ban_services()
                if disabled_auto_ban_services:
                    disabled_service_string = ""
                    for service in disabled_auto_ban_services:
                        if service in self.supported_services:
                            disabled_service_string += "\n  - {}".format(
                                self.get_nice_service_name(service)
                            )
                    if disabled_service_string:
                        msg += "\nIt is manually disabled for these services:"
                        msg += disabled_service_string
                else:
                    msg += " for all services"
            await ctx.send(box(msg))

    @autoban.command(name="enable")
    async def autoban_service_enable(self, ctx: commands.Context, service: str):
        """Allow a service to automatically ban new users."""
        disabled_auto_ban_services = await self.config.guild(
            ctx.message.guild
        ).disabled_auto_ban_services()
        if service in self.supported_services:
            try:
                disabled_auto_ban_services.remove(service)
                await self.config.guild(
                    ctx.message.guild
                ).disabled_auto_ban_services.set(disabled_auto_ban_services)
                await ctx.send(
                    checkmark(
                        "Automatic banning with {} has now been enabled for this guild!".format(
                            self.get_nice_service_name(service)
                        )
                    )
                )
            except ValueError:
                await ctx.send(
                    info(
                        "Automatic banning with {} is already enabled for this guild.".format(
                            self.get_nice_service_name(service)
                        )
                    )
                )
        else:
            await ctx.send(
                error(
                    "`{}` is not a valid service name.".format(
                        self.get_nice_service_name(service)
                    )
                )
            )

    @autoban.command(name="disable")
    async def autoban_service_disable(self, ctx: commands.Context, service: str):
        """Disallow a service to automatically ban new users."""
        disabled_auto_ban_services = await self.config.guild(
            ctx.message.guild
        ).disabled_auto_ban_services()
        if service in self.supported_services and service in disabled_auto_ban_services:
            await ctx.send(
                info(
                    "Automatic banning with {} is already disabled for this guild.".format(
                        self.get_nice_service_name(service)
                    )
                )
            )
        elif service in self.supported_services:
            disabled_auto_ban_services.append(service)
            await self.config.guild(ctx.message.guild).disabled_auto_ban_services.set(
                disabled_auto_ban_services
            )
            await ctx.send(
                checkmark(
                    "Automatic banning with {} has now been disabled for this guild!".format(
                        self.get_nice_service_name(service)
                    )
                )
            )
        else:
            await ctx.send(
                error(
                    "`{}` is not a valid service name.".format(
                        self.get_nice_service_name(service)
                    )
                )
            )

    @autoban.command(name="on")
    async def autoban_on(self, ctx: commands.Context):
        """Enable auto ban functionality guild wide."""
        if not await self.config.guild(ctx.message.guild).auto_ban():
            await self.config.guild(ctx.message.guild).auto_ban.set(True)
            await ctx.send(checkmark("Auto Ban has been enabled for this guild!"))
        else:
            await ctx.send(info("Auto Ban is already enabled for this guild."))

    @autoban.command(name="off")
    async def autoban_off(self, ctx: commands.Context):
        """Disable auto ban functionality guild wide."""
        if await self.config.guild(ctx.message.guild).auto_ban():
            await self.config.guild(ctx.message.guild).auto_ban.set(False)
            await ctx.send(checkmark("Auto Ban has been disabled for this guild!"))
        else:
            await ctx.send(info("Auto Ban is already disabled for this guild."))

    @bancheckset.group()
    @commands.guild_only()
    async def channel(self, ctx: commands.Context):
        """Manage the channel used for BanCheck notices."""
        if not ctx.invoked_subcommand:
            msg = await self.get_channel_message(ctx)
            await ctx.send(box(msg))

    @channel.command(name="set")
    async def set_channel(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Set the channel you want new user BanCheck notices to go to."""
        if channel is None:
            channel = ctx.message.channel
        await self.config.guild(ctx.message.guild).notify_channel.set(channel.id)

        try:
            embed = self.embed_maker(
                None,
                discord.Colour.green(),
                checkmark("**I will send all BanCheck notices here.**"),
                self.bot.user.avatar_url,
            )
            await channel.send(embed=embed)
        except (discord.errors.Forbidden, discord.errors.NotFound):
            await channel.send(error("**I'm not allowed to send embeds here.**"))

    @channel.command(name="disable")
    async def disable_channel(self, ctx: commands.Context):
        """Disable automatically checking new users against ban lists."""
        if await self.config.guild(ctx.message.guild).notify_channel() is None:
            await ctx.send(info("Automatic BanCheck is already disabled."))
        else:
            await self.config.guild(ctx.message.guild).notify_channel.set(None)
            await ctx.send(checkmark("Automatic BanCheck is now disabled."))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
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
            auto_ban = await self.config.guild(member.guild).auto_ban()
            await self.user_lookup(channel, member, auto_ban)

    async def user_lookup(
        self, channel: discord.TextChannel, member: discord.Member, auto_ban: bool
    ):
        """Perform user lookup, and send results to a specific channel."""
        services = await self.config.services()
        banned_services = ""
        auto_banned = False
        is_error = False
        checked = []
        description = "**Name:** {}\n**ID:** {}\n\n".format(member.name, member.id)

        # Get results
        for name, config in services.items():
            try:
                service_class = self.supported_services[name]
            except KeyError:
                continue
            if name in await self.config.guild(channel.guild).disabled_services():
                continue
            response = await service_class().lookup(member.id, config["api_key"])
            checked.append(service_class().SERVICE_NAME)

            if response.result == "ban":
                if banned_services:
                    banned_services += ", "
                banned_services += service_class().SERVICE_NAME
                if (
                    auto_ban
                    and name
                    not in await self.config.guild(
                        channel.guild
                    ).disabled_auto_ban_services()
                ):
                    auto_banned = True

                proof = " (no proof provided)"
                if response.proof_url:
                    proof = " ([proof]({}))".format(response.proof_url)

                description += "**{}:** {}{}\n".format(
                    service_class().SERVICE_NAME, response.reason, proof
                )

            elif response.result == "clear":
                description += "**{}:** (No ban found)\n".format(
                    service_class().SERVICE_NAME
                )

            elif response.result == "error":
                is_error = True
                if response.reason:
                    description += "**{}:** Error - {}\n".format(
                        service_class().SERVICE_NAME, response.reason
                    )
                else:
                    description += "**{}:** Connection Error - Server responded with the HTTP code `{}`\n".format(
                        service_class().SERVICE_NAME, response.http_status
                    )

            else:
                is_error = True
                description += "**{}:** Fatal Error - You should probably let PhasecoreX know about this -> `{}`.\n".format(
                    service_class().SERVICE_NAME, response.result
                )
        # Display result
        if banned_services:
            title = "Ban Found"
            if auto_banned:
                try:
                    await member.send(
                        "Hello! Since you are currently on a global ban list ({}), you have automatically been banned from this guild.".format(
                            banned_services
                        )
                    )
                except (discord.Forbidden, discord.NotFound):
                    pass  # Couldn't message user for some reason...
                try:
                    await channel.guild.ban(
                        member,
                        reason="Automatic ban from BanCheck lookup on {}".format(
                            banned_services
                        ),
                        delete_message_days=1,
                    )
                    title += " - Auto Banned"
                except discord.Forbidden:
                    title += " - Not allowed to Auto Ban"
            await channel.send(
                embed=self.embed_maker(
                    title, discord.Colour.red(), description, member.avatar_url
                )
            )
        elif is_error:
            await channel.send(
                embed=self.embed_maker(
                    "Error (but no ban found otherwise)",
                    discord.Colour.red(),
                    description,
                    member.avatar_url,
                )
            )
        else:
            await channel.send(
                embed=self.embed_maker(
                    "No ban found for **{}**".format(member.name),
                    discord.Colour.green(),
                    "Checked: {}".format(", ".join(checked)),
                    member.avatar_url,
                )
            )

    async def get_supported_services(self):
        """Get the currently supported BanCheck services."""
        result = ""
        for service, clazz in self.supported_services.items():
            result += "\n- `{}` ([{}]({}))".format(
                service, clazz.SERVICE_NAME, clazz.SERVICE_URL
            )
        return result

    async def get_available_services(self, ctx: commands.Context):
        """Get the message for BanCheck available services."""
        max_length = 0
        for service in self.supported_services:
            max_length = max(max_length, len(self.get_nice_service_name(service)))
        max_length += 1

        msg = ""
        enabled_services = await self.config.services()
        for service in self.supported_services:
            msg += "\n  {}".format(self.get_nice_service_name(service))
            msg += " " * (max_length - len(self.get_nice_service_name(service)))
            if service in enabled_services:
                try:
                    if (
                        service
                        in await self.config.guild(
                            ctx.message.guild
                        ).disabled_services()
                    ):
                        msg += "- Disabled"
                    elif (
                        service
                        in await self.config.guild(
                            ctx.message.guild
                        ).disabled_auto_ban_services()
                    ):
                        msg += "- Enabled (Auto Ban manually disabled)"
                    else:
                        msg += "- Enabled"
                except AttributeError:  # This is in a DM
                    msg += "- Enabled Globally"
            else:
                msg += "- Disabled (Bot owner hasn't set an API key)"
        return msg

    async def get_channel_message(self, ctx: commands.Context):
        """Get the message for BanCheck notices channel."""
        try:
            channel_name = "Disabled"
            channel_id = await self.config.guild(ctx.message.guild).notify_channel()
            if channel_id:
                channel_name = self.bot.get_channel(channel_id)
            return "BanCheck notices channel: {}\n".format(channel_name)
        except AttributeError:
            return ""  # This is in a DM

    async def get_auto_ban_message(
        self, ctx: commands.Context, trailing_newline: bool = True
    ):
        """Get the message for BanCheck auto ban status."""
        try:
            if not await self.config.guild(ctx.message.guild).notify_channel():
                return "Auto Ban is currently disabled (set BanCheck notices channel first){}".format(
                    "\n" if trailing_newline else ""
                )
            auto_ban_enabled = await self.config.guild(ctx.message.guild).auto_ban()
            return "Auto Ban is currently {}{}".format(
                "enabled" if auto_ban_enabled else "disabled",
                "\n" if trailing_newline else "",
            )
        except AttributeError:
            return ""  # This is in a DM

    def get_nice_service_name(self, service: str):
        """Get the nice name for a service."""
        nice_name = service
        try:
            nice_name = self.supported_services[service].SERVICE_NAME
        except KeyError:
            pass
        return nice_name

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
