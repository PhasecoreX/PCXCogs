"""ReactChannel cog for Red-DiscordBot by PhasecoreX."""
import datetime
from typing import Union

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import error

from .pcx_lib import checkmark, delete

__author__ = "PhasecoreX"
__version__ = "1.1.0"


class ReactChannel(commands.Cog):
    """Per-channel auto reaction tools."""

    default_guild_settings = {
        "channels": {},
        "upvote": None,
        "downvote": None,
    }
    default_member_settings = {"karma": 0, "created_at": 0}

    def __init__(self, bot):
        """Set up the plugin."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, 1224364860)
        self.config.register_guild(**self.default_guild_settings)
        self.config.register_member(**self.default_member_settings)
        self.emoji_cache = {}

    async def initialize(self):
        """Perform setup actions before loading cog."""
        await self._maybe_update_config()

    async def _maybe_update_config(self):
        """Perform some configuration migrations."""
        if await self.config.version() == __version__:
            return
        guild_dict = await self.config.all_guilds()
        for guild_id, guild_info in guild_dict.items():
            # If guild had a vote channel, set up default upvote and downvote emojis
            channels = guild_info.get("channels", {})
            if channels:
                for channel_id, channel_type in channels.items():
                    if channel_type == "vote":
                        await self.config.guild(discord.Object(id=guild_id)).upvote.set(
                            "\ud83d\udd3c"
                        )
                        await self.config.guild(
                            discord.Object(id=guild_id)
                        ).downvote.set("\ud83d\udd3d")
                        break
        await self.config.version.set(__version__)

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
            checkmark(
                "<#{}> is now a {} ReactChannel.".format(str(channel.id), channel_type)
            )
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
                "ReactChannel functionality has been disabled on <#{}>.".format(
                    str(channel.id)
                )
            )
        )

    @reactchannelset.group()
    async def emoji(self, ctx: commands.Context):
        """Manage emojis used for ReactChannels."""
        upvote = await self._get_emoji(ctx.message.guild, "upvote")
        downvote = await self._get_emoji(ctx.message.guild, "downvote")
        message = "Upvote emoji: {}\n".format(upvote if upvote else "None")
        message += "Downvote emoji: {}".format(downvote if downvote else "None")
        await ctx.send(message)

    @emoji.command(name="upvote")
    async def set_upvote(self, ctx: commands.Context, emoji: Union[str, int]):
        """Set the upvote emoji used. Use "none" to remove the emoji and disable upvotes."""
        await self._save_emoji(ctx, emoji, "upvote")

    @emoji.command(name="downvote")
    async def set_downvote(self, ctx: commands.Context, emoji: Union[str, int]):
        """Set the downvote emoji used. Use "none" to remove the emoji and disable downvotes."""
        await self._save_emoji(ctx, emoji, "downvote")

    async def _save_emoji(
        self, ctx: commands.Context, emoji: Union[str, int], emoji_type: str
    ):
        """Actually save the emoji."""
        if emoji == "none":
            setting = getattr(self.config.guild(ctx.guild), emoji_type)
            await setting.set(None)
            await ctx.send(
                checkmark(
                    "{} emoji for this guild has been disabled".format(
                        emoji_type.capitalize()
                    )
                )
            )
            await self._get_emoji(ctx.guild, emoji_type, refresh=True)
            return
        try:
            await ctx.message.add_reaction(emoji)
            await ctx.message.remove_reaction(emoji, self.bot.user)
            save = emoji
            if isinstance(emoji, discord.PartialEmoji):
                raise discord.HTTPException
            if isinstance(emoji, discord.Emoji):
                save = emoji.id
            setting = getattr(self.config.guild(ctx.guild), emoji_type)
            await setting.set(save)
            await ctx.send(
                checkmark(
                    "{} emoji for this guild has been set to {}".format(
                        emoji_type.capitalize(), emoji
                    )
                )
            )
            await self._get_emoji(ctx.guild, emoji_type, refresh=True)
        except discord.HTTPException:
            await ctx.send(error("That is not a valid emoji I can use!"))

    @commands.command()
    @commands.guild_only()
    async def karma(self, ctx: commands.Context):
        """View your total karma for upvoted messages in this guild."""
        member = self.config.member(ctx.message.author)
        total_karma = await member.karma()
        await ctx.send(
            "{}, you have **{}** message karma".format(
                ctx.message.author.mention, total_karma
            )
        )

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        """Watch for messages in enabled react channels to add reactions."""
        if message.guild is None or message.channel is None:
            return
        channels = await self.config.guild(message.guild).channels()
        if str(message.channel.id) not in channels:
            return
        can_react = message.channel.permissions_for(message.guild.me).add_reactions
        if not can_react:
            return
        channel_type = channels.get(str(message.channel.id))
        if channel_type == "checklist":
            await message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        elif channel_type == "vote" and not message.author.bot:
            for emoji_type in ["upvote", "downvote"]:
                emoji = await self._get_emoji(message.guild, emoji_type)
                if emoji:
                    await message.add_reaction(emoji)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Watch for reactions added to messages in react channels (or all channels for karma) and perform actions on them."""
        guild = self.bot.get_guild(payload.guild_id)
        channel = self.bot.get_channel(payload.channel_id)
        user = self.bot.get_user(payload.user_id)  # User who added a reaction
        if not guild or not channel or not user or not payload.message_id:
            return
        if user.bot:
            return
        channels = await self.config.guild(guild).channels()
        channel_type = channels.get(str(payload.channel_id))
        message = await channel.fetch_message(payload.message_id)
        if not message:
            return
        # Checklist
        if (
            str(payload.emoji) == "\N{WHITE HEAVY CHECK MARK}"
            and channel_type == "checklist"
        ):
            await delete(message)
            return
        # Vote
        upvote = await self._get_emoji(guild, "upvote")
        downvote = await self._get_emoji(guild, "downvote")
        karma = 0
        if upvote and str(payload.emoji) == upvote:
            karma = 1
            opposite_emoji = downvote
        elif downvote and str(payload.emoji) == downvote:
            karma = -1
            opposite_emoji = upvote
        if karma:
            if opposite_emoji:
                try:
                    opposite_reactions = next(
                        reaction
                        for reaction in message.reactions
                        if str(reaction.emoji) == opposite_emoji
                    )
                    try:
                        await opposite_reactions.remove(user)
                    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                        pass
                except StopIteration:
                    pass  # This message doesn't have an opposite reaction on it

            if message.author.bot or user == message.author:
                # Bots can't get karma, users can't upvote themselves
                return
            await self._increment_karma(message.author, karma)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Watch for reactions removed from messages in react channels (or all channels for karma) and perform actions on them."""
        guild = self.bot.get_guild(payload.guild_id)
        channel = self.bot.get_channel(payload.channel_id)
        user = self.bot.get_user(payload.user_id)  # User whose reaction was removed
        if not guild or not channel or not user or not payload.message_id:
            return
        # channels = await self.config.guild(guild).channels()
        # channel_type = channels.get(str(payload.channel_id))
        message = await channel.fetch_message(payload.message_id)
        if not message:
            return
        upvote = await self._get_emoji(guild, "upvote")
        downvote = await self._get_emoji(guild, "downvote")
        karma = 0
        if upvote and str(payload.emoji) == upvote:
            karma = -1
        elif downvote and str(payload.emoji) == downvote:
            karma = 1
        if karma:
            if message.author.bot or user == message.author:
                # Bots can't get karma, users can't upvote themselves
                return
            await self._increment_karma(message.author, karma)

    async def _get_emoji(self, guild, emoji_type: str, refresh=False):
        """Get an emoji, ready for sending/reacting."""
        if guild.id not in self.emoji_cache:
            self.emoji_cache[guild.id] = {}
        if emoji_type in self.emoji_cache[guild.id] and not refresh:
            return self.emoji_cache[guild.id][emoji_type]
        emoji = await getattr(self.config.guild(guild), emoji_type)()
        if isinstance(emoji, int):
            emoji = self.bot.get_emoji(emoji)
        self.emoji_cache[guild.id][emoji_type] = emoji
        return emoji

    async def _increment_karma(self, member, delta: int):
        """Increment a users karma."""
        async with self.config.member(member).karma.get_lock():
            member = self.config.member(member)
            total_karma = await member.karma()
            total_karma += delta
            await member.karma.set(total_karma)
            if await member.created_at() == 0:
                time = int(datetime.datetime.utcnow().timestamp())
                await member.created_at.set(time)
