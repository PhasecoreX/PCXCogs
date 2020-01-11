"""ReactChannel cog for Red-DiscordBot by PhasecoreX."""
import datetime

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import error

__author__ = "PhasecoreX"


class ReactChannel(commands.Cog):
    """Per-channel auto reaction tools."""

    default_guild_settings = {"channels": {}}
    default_member_settings = {"karma": 0, "created_at": 0}

    def __init__(self, bot):
        """Set up the plugin."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, 1224364860)
        self.config.register_guild(**self.default_guild_settings)
        self.config.register_member(**self.default_member_settings)

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def reactchannelset(self, ctx: commands.Context):
        """Manage ReactChannel settings."""
        if not ctx.invoked_subcommand:
            message = ""
            channels = await self.config.guild(ctx.message.guild).channels()
            for channel_id, channel_type in channels.items():
                message += "\n  - <#{}>: {}".format(channel_id, channel_type)
            if not message:
                message = " None"
            message = "ReactChannels configured:" + message
            await ctx.send(message)

    @reactchannelset.command()
    async def enable(
        self,
        ctx: commands.Context,
        channel_type: str,
        channel: discord.TextChannel = None,
    ):
        """Enable ReactChannel functionality in a channel.

        `channel_type` can be any of:
        - `checklist`: All messages will have a checkmark. Clicking it will delete the message.
        - `vote`: All messages will have an up and down arrow.
        """
        if channel is None:
            channel = ctx.message.channel
        if channel_type not in ["checklist", "vote"]:
            await ctx.send(
                error("`{}` is not a supported channel type.".format(channel_type))
            )
            return

        channels = await self.config.guild(ctx.message.guild).channels()
        channels[str(channel.id)] = channel_type
        await self.config.guild(ctx.message.guild).channels.set(channels)
        await ctx.send(
            checkmark("{} is now a {} ReactChannel.".format(channel, channel_type))
        )

    @reactchannelset.command()
    async def disable(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Disable ReactChannel functionality in a channel."""
        if channel is None:
            channel = ctx.message.channel

        channels = await self.config.guild(ctx.message.guild).channels()
        try:
            del channels[str(channel.id)]
        except KeyError:
            pass
        await self.config.guild(ctx.message.guild).channels.set(channels)
        await ctx.send(
            checkmark(
                "ReactChannel functionality has been disabled on {}.".format(channel)
            )
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Watch for messages in enabled react channels to add reactions."""
        if message.guild is None or message.channel is None:
            return
        channels = await self.config.guild(message.guild).channels()
        if str(message.channel.id) not in channels:
            return
        can_react = message.channel.permissions_for(message.guild.me).add_reactions
        if not can_react:
            return
        channel_type = channels[str(message.channel.id)]
        if channel_type == "checklist":
            await message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        elif channel_type == "vote":
            await message.add_reaction("\N{UP-POINTING SMALL RED TRIANGLE}")
            await message.add_reaction("\N{DOWN-POINTING SMALL RED TRIANGLE}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawMessageUpdateEvent):
        """Watch for reactions on messages in react channels and perform actions on them."""
        guild = self.bot.get_guild(payload.guild_id)
        channel = self.bot.get_channel(payload.channel_id)
        user = self.bot.get_user(payload.user_id)
        if not guild or not channel or not user or not payload.message_id:
            return
        if user.bot:
            return
        channels = await self.config.guild(guild).channels()
        if str(payload.channel_id) not in channels:
            return
        channel_type = channels[str(payload.channel_id)]
        message = await channel.fetch_message(payload.message_id)
        if not message:
            return
        # Checklist
        if (
            str(payload.emoji) == "\N{WHITE HEAVY CHECK MARK}"
            and channel_type == "checklist"
        ):
            try:
                await message.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass
        # Vote
        elif (
            str(payload.emoji) == "\N{UP-POINTING SMALL RED TRIANGLE}"
            or str(payload.emoji) == "\N{DOWN-POINTING SMALL RED TRIANGLE}"
        ) and channel_type == "vote":
            karma, opposite_emoji = (
                (1, "\N{DOWN-POINTING SMALL RED TRIANGLE}")
                if str(payload.emoji) == "\N{UP-POINTING SMALL RED TRIANGLE}"
                else (-1, "\N{UP-POINTING SMALL RED TRIANGLE}")
            )
            opposite_reactions = next(
                reaction
                for reaction in message.reactions
                if str(reaction.emoji) == opposite_emoji
            )
            try:
                await opposite_reactions.remove(user)
            except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                pass

            member = self.config.member(message.author)
            total_karma = await member.karma()
            total_karma += karma
            await member.karma.set(total_karma)
            if await member.created_at() == 0:
                time = int(datetime.datetime.utcnow().timestamp())
                await member.created_at.set(time)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawMessageUpdateEvent):
        """Watch for reactions removed on messages in react channels and perform actions on them."""
        guild = self.bot.get_guild(payload.guild_id)
        channel = self.bot.get_channel(payload.channel_id)
        if not guild or not channel or not payload.message_id:
            return
        channels = await self.config.guild(guild).channels()
        if str(payload.channel_id) not in channels:
            return
        channel_type = channels[str(payload.channel_id)]
        message = await channel.fetch_message(payload.message_id)
        if not message:
            return
        if (
            str(payload.emoji) == "\N{UP-POINTING SMALL RED TRIANGLE}"
            or str(payload.emoji) == "\N{DOWN-POINTING SMALL RED TRIANGLE}"
        ) and channel_type == "vote":
            karma = 1 if str(payload.emoji) == "\N{DOWN-POINTING SMALL RED TRIANGLE}" else -1
            member = self.config.member(message.author)
            total_karma = await member.karma()
            total_karma += karma
            await member.karma.set(total_karma)
            if await member.created_at() == 0:
                time = int(datetime.datetime.utcnow().timestamp())
                await member.created_at.set(time)


def checkmark(text: str) -> str:
    """Get text prefixed with a checkmark emoji."""
    return "\N{WHITE HEAVY CHECK MARK} {}".format(text)
