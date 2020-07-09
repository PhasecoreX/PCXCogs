"""ReactChannel cog for Red-DiscordBot by PhasecoreX."""
import datetime
from typing import Union

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import error, info

from .pcx_lib import checkmark, delete

__author__ = "PhasecoreX"


class ReactChannel(commands.Cog):
    """Per-channel auto reaction tools."""

    default_global_settings = {"schema_version": 0}
    default_guild_settings = {
        "channels": {},
        "emojis": {"upvote": None, "downvote": None},
    }
    default_member_settings = {"karma": 0, "created_at": 0}

    def __init__(self, bot):
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)
        self.config.register_member(**self.default_member_settings)
        self.emoji_cache = {}

    async def initialize(self):
        """Perform setup actions before loading cog."""
        await self._migrate_config()

    async def _migrate_config(self):
        """Perform some configuration migrations."""
        if not await self.config.schema_version():
            # If guild had a vote channel, set up default upvote and downvote emojis
            guild_dict = await self.config.all_guilds()
            for guild_id, guild_info in guild_dict.items():
                channels = guild_info.get("channels", {})
                if channels:
                    for channel_id, channel_type in channels.items():
                        if channel_type == "vote":
                            await self.config.guild_from_id(guild_id).emojis.upvote.set(
                                guild_info.get("upvote", "\ud83d\udd3c")
                            )
                            await self.config.guild_from_id(
                                guild_id
                            ).emojis.downvote.set(
                                guild_info.get("downvote", "\ud83d\udd3d")
                            )
                            break
                await self.config.guild_from_id(guild_id).clear_raw("upvote")
                await self.config.guild_from_id(guild_id).clear_raw("downvote")
            await self.config.clear_raw("version")
            await self.config.schema_version.set(1)

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def reactchannelset(self, ctx: commands.Context):
        """Manage ReactChannel settings."""
        if not ctx.invoked_subcommand:
            message = ""
            channels = await self.config.guild(ctx.message.guild).channels()
            for channel_id, channel_type in channels.items():
                emojis = "???"
                if channel_type == "checklist":
                    emojis = "\N{WHITE HEAVY CHECK MARK}"
                if channel_type == "vote":
                    emojis = ""
                    upvote = await self._get_emoji(ctx.message.guild, "upvote")
                    downvote = await self._get_emoji(ctx.message.guild, "downvote")
                    if upvote:
                        emojis += upvote
                    if downvote:
                        if emojis:
                            emojis += " "
                        emojis += downvote
                    if not emojis:
                        emojis = "(disabled, see `[p]reactchannelset emoji`)"
                if isinstance(channel_type, list):
                    emojis = " ".join(channel_type)
                    channel_type = "custom"
                message += "\n  - <#{}>: {} - {}".format(
                    channel_id, channel_type.capitalize(), emojis
                )
            if not message:
                message = " None"
            message = "ReactChannels configured:" + message
            await ctx.send(message)

    @reactchannelset.group()
    async def enable(self, ctx: commands.Context):
        """Enable ReactChannel functionality in a channel."""
        pass

    @enable.command()
    async def checklist(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """All messages will have a checkmark. Clicking it will delete the message."""
        await self._save_channel(ctx, channel, "checklist")

    @enable.command()
    async def vote(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """All user messages will have an up and down arrow. Clicking them will affect a users karma total."""
        await self._save_channel(ctx, channel, "vote")

    @enable.command()
    async def custom(self, ctx: commands.Context, *, emojis: str):
        """All messages will have the specified emoji(s). When specifying multiple, make sure there's a space between each emoji."""
        await self._save_channel(ctx, None, list(dict.fromkeys(emojis.split())))

    async def _save_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        channel_type: Union[str, list],
    ):
        """Actually save the ReactChannel settings."""
        if channel is None:
            channel = ctx.message.channel
        if isinstance(channel_type, list):
            try:
                for emoji in channel_type:
                    await ctx.message.add_reaction(emoji)
                for emoji in channel_type:
                    await ctx.message.remove_reaction(emoji, self.bot.user)
            except discord.HTTPException:
                await ctx.send(
                    error(
                        "{} is not a valid emoji I can use!".format(
                            "That" if len(channel_type) == 1 else "One of those emojis"
                        )
                    )
                )
                return
        async with self.config.guild(ctx.message.guild).channels() as channels:
            channels[str(channel.id)] = channel_type
        channel_type_name = channel_type
        custom_emojis = ""
        if isinstance(channel_type_name, list):
            channel_type_name = "custom"
            custom_emojis = " ({})".format(", ".join(channel_type))
        await ctx.send(
            checkmark(
                "<#{}> is now a {} ReactChannel.{}".format(
                    str(channel.id), channel_type_name, custom_emojis
                )
            )
        )
        if (
            channel_type == "vote"
            and not await self._get_emoji(ctx.message.guild, "upvote")
            and not await self._get_emoji(ctx.message.guild, "downvote")
        ):
            await ctx.send(
                info(
                    "You do not have an upvote or downvote emoji set for this guild. "
                    "You will need at least one set in order for this ReactChannel to work. "
                    "Check `[p]reactchannelset emoji` for more information."
                )
            )

    @reactchannelset.command()
    async def disable(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Disable ReactChannel functionality in a channel."""
        if channel is None:
            channel = ctx.message.channel

        async with self.config.guild(ctx.message.guild).channels() as channels:
            try:
                del channels[str(channel.id)]
            except KeyError:
                pass
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
            setting = getattr(self.config.guild(ctx.guild).emojis, emoji_type)
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
            setting = getattr(self.config.guild(ctx.guild).emojis, emoji_type)
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

    @commands.command()
    @commands.guild_only()
    async def upvote(self, ctx: commands.Context):
        """View this guilds upvote reaction."""
        upvote = await self._get_emoji(ctx.message.guild, "upvote")
        if upvote:
            await ctx.send("This guilds upvote emoji is {}".format(upvote))
        else:
            await ctx.send("This guild does not have an upvote emoji set")

    @commands.command()
    @commands.guild_only()
    async def downvote(self, ctx: commands.Context):
        """View this guilds downvote reaction."""
        downvote = await self._get_emoji(ctx.message.guild, "downvote")
        if downvote:
            await ctx.send("This guilds downvote emoji is {}".format(downvote))
        else:
            await ctx.send("This guild does not have a downvote emoji set")

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
                    try:
                        await message.add_reaction(emoji)
                    except discord.HTTPException:
                        pass
        elif isinstance(channel_type, list):
            # Custom reactions
            for emoji in channel_type:
                try:
                    await message.add_reaction(emoji)
                except discord.HTTPException:
                    pass

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
        emoji = await getattr(self.config.guild(guild).emojis, emoji_type)()
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
