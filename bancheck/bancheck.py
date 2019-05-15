"""BanCheck cog for Red-DiscordBot ported and enhanced by PhasecoreX."""
import aiohttp
import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import box

__author__ = "PhasecoreX"


class BanCheck(commands.Cog):
    """Look up users on various ban lists."""

    default_guild_settings = {"channel": None}

    def __init__(self, bot):
        """Set up the plugin."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1224364860)
        self.config.register_guild(**self.default_guild_settings)

    @commands.group()
    @commands.guild_only()
    async def bancheck(self, ctx: commands.Context):
        """Check new users against a ban list."""
        if not ctx.invoked_subcommand:
            channel_name = "Disabled"
            channel_id = await self.config.guild(ctx.message.guild).channel()
            if channel_id:
                channel_name = self.bot.get_channel(channel_id).name
            msg = "BanCheck notices channel: {}".format(channel_name)
            await ctx.send(box(msg))

    @bancheck.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
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

    @bancheck.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def disable(self, ctx: commands.Context):
        """Disable automatically checking new users against ban lists."""
        if await self.config.guild(ctx.message.guild).channel() is None:
            await ctx.send("Automatic ban check is already disabled.")
        else:
            await self.config.guild(ctx.message.guild).channel.set(None)
            await ctx.send("Automatic ban check is now disabled.")

    @bancheck.command(aliases=["search"])
    async def check(self, ctx: commands.Context, member: discord.Member = None):
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
        response = await self.lookup_discord_services(member.id)

        if response.result == "ban":
            niceurl = "[Click Here]({})".format(response.proof)

            description = """**Name:** {}\n**ID:** {}\n**Reason:** {}\n**Proof:** {}""".format(
                response.username, response.userid, response.reason, niceurl
            )

            await channel.send(
                embed=self.embed_maker(
                    "Ban Found", discord.Colour.red(), description, member.avatar_url
                )
            )

        elif response.result == "clear":
            await channel.send(
                embed=self.embed_maker(
                    "No ban found for **{}**".format(member.name),
                    discord.Colour.green(),
                    None,
                    member.avatar_url,
                )
            )

        elif response.result == "error":
            await channel.send(
                embed=self.embed_maker(
                    "Error looking up ban info for **{}**".format(member.name),
                    discord.Colour.red(),
                    (
                        "When attempting to connect to `{}`, "
                        "the server responded with the HTTP code `{}`."
                    ).format(response.service, response.reason),
                    member.avatar_url,
                )
            )

        else:
            await channel.send(
                embed=self.embed_maker(
                    "Something is broken...",
                    discord.Colour.red(),
                    "You should probably let PhasecoreX know about this -> `{}`.".format(
                        response.result
                    ),
                    self.bot.user.avatar_url,
                )
            )

    async def lookup_discord_services(self, user):
        """Perform user lookup on discord.services."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://discord.services/api/ban/" + str(user)
            ) as resp:
                if resp.status != 200:
                    result = Lookup("discord.services", "error")
                    result.reason = resp.status
                    return result
                data = await resp.json()
                if "ban" in data:
                    result = Lookup("discord.services", "ban")
                    result.username = data["ban"]["name"]
                    result.userid = data["ban"]["id"]
                    result.reason = data["ban"]["reason"]
                    result.proof = data["ban"]["proof"]
                    return result
                return Lookup("discord.services", "clear")

    @staticmethod
    def embed_maker(title, color, description, avatar):
        """Create a nice embed."""
        embed = discord.Embed(title=title, color=color, description=description)
        embed.set_thumbnail(url=avatar)
        return embed


class Lookup:
    """A user lookup result."""

    def __init__(self, service: str, result: str):
        """Create the base lookup result."""
        self.service = service
        self.result = result
        self.username = ""
        self.userid = 0
        self.reason = "(none specified)"
        self.proof = ""
