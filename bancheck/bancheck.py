"""
BanCheck cog for Red-DiscordBot ported and enhanced by PhasecoreX
"""
import aiohttp
import discord
from redbot.core import checks, Config, commands
from redbot.core.utils.chat_formatting import box


__author__ = "PhasecoreX"
BaseCog = getattr(commands, "Cog", object)


class BanCheck(BaseCog):
    """Look up users on various ban lists."""

    base_url = "https://discord.services/api"
    default_guild_settings = {
        "channel": None
    }

    def __init__(self, bot):
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
    async def channel(self, ctx: commands.Context, channel: discord.TextChannel=None):
        """Set the channel you want new user ban check notices to go to."""
        if channel is None:
            channel = ctx.message.channel
        await self.config.guild(ctx.message.guild).channel.set(channel.id)

        channel = self.bot.get_channel(await self.config.guild(ctx.message.guild).channel())
        try:
            embed = self.embed_maker(None, discord.Colour.green(),
                                     ":white_check_mark: " +
                                     "**I will send all ban check notices here.**",
                                     avatar=self.bot.user.avatar_url)
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

    @bancheck.command()
    async def search(self, ctx: commands.Context, member: discord.Member=None):
        """Check if user is on a ban list."""
        if not member:
            member = ctx.message.author
        await self.user_lookup(ctx.channel, member)

    async def on_member_join(self, member: discord.Member):
        """If enabled, will check users against ban lists when joining the guild."""
        channel_id = await self.config.guild(member.guild).channel()
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            await self.user_lookup(channel, member)

    async def user_lookup(self, channel: discord.TextChannel, member: discord.Member):
        """Helper method that does the user lookup, and sends results to a specific channel"""
        response = await self.lookup(member.id)

        if "ban" in response:
            name = response["ban"]["name"]
            userid = response["ban"]["id"]
            reason = response["ban"]["reason"]
            proof = response["ban"]["proof"]
            niceurl = "[Click Here]({})".format(proof)

            description = (
                """**Name:** {}\n**ID:** {}\n**Reason:** {}\n**Proof:** {}""".format(
                    name, userid, reason, niceurl))

            await channel.send(embed=self.embed_maker("Ban Found", discord.Colour.red(),
                                                      description, member.avatar_url))

        else:
            await channel.send(embed=self.embed_maker("No ban found for **{}**".format(member.name),
                                                      discord.Colour.green(), None,
                                                      member.avatar_url))

    async def lookup(self, user):
        """Helper method to do the lookup."""
        conn = aiohttp.TCPConnector()
        async with aiohttp.ClientSession(connector=conn) as session:
            async with session.get(self.base_url + "/ban/" + str(user)) as response:
                result = await response.json()
        return result

    @staticmethod
    def embed_maker(title, color, description, avatar):
        """Creates a nice embed."""
        embed = discord.Embed(title=title, color=color, description=description)
        if avatar:
            embed.set_thumbnail(url=avatar)
        return embed
