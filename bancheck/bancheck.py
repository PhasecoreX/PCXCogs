"""BanCheck cog for Red-DiscordBot ported and enhanced by PhasecoreX."""
import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import box

from .services.globan import globan
from .services.ksoftsi import ksoftsi

__author__ = "PhasecoreX"


class BanCheck(commands.Cog):
    """Look up users on various ban lists."""

    default_guild_settings = {"channel": None, "services": {}}
    supported_services = {"globan": globan, "ksoftsi": ksoftsi}

    def __init__(self, bot):
        """Set up the plugin."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1224364860)
        self.config.register_guild(**self.default_guild_settings)

    @commands.group()
    @commands.guild_only()
    async def bancheckset(self, ctx: commands.Context):
        """Configure BanCheck."""
        if not ctx.invoked_subcommand:
            channel_name = "Disabled"
            channel_id = await self.config.guild(ctx.message.guild).channel()
            if channel_id:
                channel_name = self.bot.get_channel(channel_id).name
            services_list = ""
            services = await self.config.guild(ctx.message.guild).services()
            for service in services.copy():
                if service not in self.supported_services:
                    services.pop(service, None)
                    await self.config.guild(ctx.message.guild).services.set(services)
                    continue
                services_list += "\n  - {}".format(
                    self.supported_services[service].SERVICE_NAME
                )
            if not services_list:
                services_list = " None"
            msg = (
                "BanCheck notices channel: {}\nEnabled ban checking services:{}"
            ).format(channel_name, services_list)
            await ctx.send(box(msg))

    @bancheckset.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def enableservice(self, ctx: commands.Context, service: str, api: str):
        """Set a service api key in order to enable it."""
        if service not in self.supported_services:
            await ctx.send(
                "The only services we support so far are:{}".format(
                    "".join(["\n- `" + s + "`" for s in self.supported_services])
                )
            )
            return
        services = await self.config.guild(ctx.message.guild).services()
        update = True
        if service not in services:
            services[service] = {}
            update = False
        services[service]["api_key"] = api
        await self.config.guild(ctx.message.guild).services.set(services)
        if update:
            await ctx.send(
                "Successfully updated the {} API key!".format(
                    self.supported_services[service].SERVICE_NAME
                )
            )
        else:
            await ctx.send(
                "Ban checking with {} has now been enabled!".format(
                    self.supported_services[service].SERVICE_NAME
                )
            )

    @bancheckset.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def disableservice(self, ctx: commands.Context, service: str):
        """Delete a service api key in order to disable it."""
        services = await self.config.guild(ctx.message.guild).services()
        if services.pop(service, None):
            await self.config.guild(ctx.message.guild).services.set(services)
            niceName = service
            try:
                niceName = self.supported_services[service].SERVICE_NAME
            except KeyError:
                pass
            await ctx.send(
                "Ban checking with {} has now been disabled!".format(niceName)
            )
        else:
            await ctx.send("`{}` is not an enabled service.".format(service))

    @bancheckset.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def enablechannel(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Set the channel you want new user ban check notices to go to."""
        if channel is None:
            channel = ctx.message.channel
        await self.config.guild(ctx.message.guild).channel.set(channel.id)

        try:
            embed = self.embed_maker(
                None,
                discord.Colour.green(),
                ":white_check_mark: **I will send all ban check notices here.**",
                avatar=self.bot.user.avatar_url,
            )
            await channel.send(embed=embed)
        except (discord.errors.Forbidden, discord.errors.NotFound):
            await channel.send(":no_entry: **I'm not allowed to send embeds here.**")

    @bancheckset.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def disablechannel(self, ctx: commands.Context):
        """Disable automatically checking new users against ban lists."""
        if await self.config.guild(ctx.message.guild).channel() is None:
            await ctx.send("Automatic ban check is already disabled.")
        else:
            await self.config.guild(ctx.message.guild).channel.set(None)
            await ctx.send("Automatic ban check is now disabled.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def bancheck(self, ctx: commands.Context, member: discord.Member = None):
        """Check if user is on a ban list."""
        if not member:
            member = ctx.message.author
        async with ctx.channel.typing():
            await self.user_lookup(ctx.channel, member)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """If enabled, will check users against ban lists when joining the guild."""
        channel_id = await self.config.guild(member.guild).channel()
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            await self.user_lookup(channel, member)

    async def user_lookup(self, channel: discord.TextChannel, member: discord.Member):
        """Perform user lookup, and send results to a specific channel."""
        services = await self.config.guild(channel.guild).services()
        is_banned = False
        is_error = False
        checked = []
        description = "**Name:** {}\n**ID:** {}\n\n".format(member.name, member.id)

        # Get results
        for name, config in services.items():
            try:
                service_class = self.supported_services[name]
            except KeyError:
                continue
            response = await service_class().lookup(member.id, config["api_key"])
            checked.append(service_class().SERVICE_NAME)

            if response.result == "ban":
                is_banned = True

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
        if is_banned:
            await channel.send(
                embed=self.embed_maker(
                    "Ban Found", discord.Colour.red(), description, member.avatar_url
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

    @staticmethod
    def embed_maker(title, color, description, avatar):
        """Create a nice embed."""
        embed = discord.Embed(title=title, color=color, description=description)
        embed.set_thumbnail(url=avatar)
        return embed
