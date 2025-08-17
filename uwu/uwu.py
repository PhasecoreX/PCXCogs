"""UwU cog for Red-DiscordBot by PhasecoreX."""

# ruff: noqa: S311
import random
from contextlib import suppress
from typing import ClassVar

import discord
from redbot.core import Config, checks, commands

from .pcx_lib import type_message


class UwU(commands.Cog):
    """UwU."""

    __author__ = "PhasecoreX + Didi (For the channel feature)"
    __version__ = "2.3.1"

    KAOMOJI_JOY: ClassVar[list[str]] = [
        " (\\* ^ ω ^)",
        " (o^▽^o)",
        " (≧◡≦)",
        ' ☆⌒ヽ(\\*"､^\\*)chu',
        " ( ˘⌣˘)♡(˘⌣˘ )",
        " xD",
    ]
    KAOMOJI_EMBARRASSED: ClassVar[list[str]] = [
        " (/ />/ ▽ /</ /)..",
        " (\\*^.^\\*)..,",
        "..,",
        ",,,",
        "... ",
        ".. ",
        " mmm..",
        "O.o",
    ]
    KAOMOJI_CONFUSE: ClassVar[list[str]] = [
        " (o_O)?",
        " (°ロ°) !?",
        " (ーー;)?",
        " owo?",
    ]
    KAOMOJI_SPARKLES: ClassVar[list[str]] = [
        " \\*:･ﾟ✧\\*:･ﾟ✧ ",
        " ☆\\*:・ﾟ ",
        "〜☆ ",
        " uguu.., ",
        "-.-",
    ]

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        self.config.register_global(uwu_channels={})
        self._webhook_cache: dict[int, discord.Webhook] = {}

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
    # Command methods
    #

    @commands.group()
    @checks.is_owner()
    async def uwuset(self, ctx: commands.Context):
        """Setup UwU channel settings."""

    @uwuset.command(name="channel")
    async def uwuset_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Enable UwU auto-messages for a channel."""
        channels = await self.config.uwu_channels()
        channels[str(channel.id)] = True
        await self.config.uwu_channels.set(channels)
        await ctx.send(f"UwU channel set: {channel.mention}")

    @uwuset.command(name="remove")
    async def uwuset_remove(self, ctx: commands.Context, channel: discord.TextChannel):
        """Disable UwU auto-messages for a channel."""
        channels = await self.config.uwu_channels()
        channels.pop(str(channel.id), None)
        await self.config.uwu_channels.set(channels)
        self._webhook_cache.pop(channel.id, None)
        await ctx.send(f"UwU channel removed: {channel.mention}")

    @commands.command(aliases=["owo"])
    async def uwu(self, ctx: commands.Context, *, text: str | None = None) -> None:
        """Uwuize the replied to message, previous message, or your own text."""
        if not text:
            if hasattr(ctx.message, "reference") and ctx.message.reference:
                with suppress(
                    discord.Forbidden, discord.NotFound, discord.HTTPException
                ):
                    message_id = ctx.message.reference.message_id
                    if message_id:
                        text = (await ctx.fetch_message(message_id)).content
            if not text:
                messages = [message async for message in ctx.channel.history(limit=2)]
                text = messages[1].content or "I can't translate that!"
        await type_message(
            ctx.channel,
            self.uwuize_string(text),
            allowed_mentions=discord.AllowedMentions(
                everyone=False, users=False, roles=False
            ),
        )

    #
    # Event listener for auto-UwU channels
    #

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        uwu_channels = await self.config.uwu_channels()
        if str(message.channel.id) not in uwu_channels:
            return

        uwu_content = self.uwuize_string(message.content)

        # Delete original message
        with suppress(discord.Forbidden, discord.NotFound, discord.HTTPException):
            await message.delete()

        # Get or create webhook from cache
        webhook = self._webhook_cache.get(message.channel.id)
        if not webhook:
            webhooks = await message.channel.webhooks()
            for wh in webhooks:
                if wh.name == "UwU Bot":
                    webhook = wh
                    break
            if not webhook:
                webhook = await message.channel.create_webhook(name="UwU Bot")
            self._webhook_cache[message.channel.id] = webhook

        await webhook.send(
            uwu_content,
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    #
    # Public methods
    #

    def uwuize_string(self, string: str) -> str:
        """Uwuize and return a string."""
        converted = ""
        current_word = ""
        for letter in string:
            if letter.isprintable() and not letter.isspace():
                current_word += letter
            elif current_word:
                converted += self.uwuize_word(current_word) + letter
                current_word = ""
            else:
                converted += letter
        if current_word:
            converted += self.uwuize_word(current_word)
        return converted

    def uwuize_word(self, word: str) -> str:
        """Uwuize and return a word."""
        word = word.lower()
        uwu = word.rstrip(".?!,")
        punctuations = word[len(uwu) :]
        final_punctuation = punctuations[-1] if punctuations else ""
        extra_punctuation = punctuations[:-1] if punctuations else ""

        if final_punctuation == "." and not random.randint(0, 3):
            final_punctuation = random.choice(self.KAOMOJI_JOY)
        if final_punctuation == "?" and not random.randint(0, 2):
            final_punctuation = random.choice(self.KAOMOJI_CONFUSE)
        if final_punctuation == "!" and not random.randint(0, 2):
            final_punctuation = random.choice(self.KAOMOJI_JOY)
        if final_punctuation == "," and not random.randint(0, 3):
            final_punctuation = random.choice(self.KAOMOJI_EMBARRASSED)
        if final_punctuation and not random.randint(0, 4):
            final_punctuation = random.choice(self.KAOMOJI_SPARKLES)

        if uwu in ("you're", "youre"):
            uwu = "ur"
        elif uwu == "fuck":
            uwu = "fwickk"
        elif uwu == "shit":
            uwu = "poopoo"
        elif uwu == "bitch":
            uwu = "meanie"
        elif uwu == "asshole":
            uwu = "b-butthole"
        elif uwu in ("dick", "penis"):
            uwu = "peenie"
        elif uwu in ("cum", "semen"):
            uwu = "cummies"
        elif uwu == "ass":
            uwu = "b-butt"
        elif uwu in ("dad", "father"):
            uwu = "daddy"
        else:
            protected = ""
            if uwu.endswith(("le", "ll", "er", "re")):
                protected = uwu[-2:]
                uwu = uwu[:-2]
            elif uwu.endswith(("les", "lls", "ers", "res")):
                protected = uwu[-3:]
                uwu = uwu[:-3]

            uwu = (
                uwu.replace("l", "w")
                .replace("r", "w")
                .replace("na", "nya")
                .replace("ne", "nye")
                .replace("ni", "nyi")
                .replace("no", "nyo")
                .replace("nu", "nyu")
                .replace("ove", "uv")
                + protected
            )

        if (
            len(uwu) > 2
            and uwu[0].isalpha()
            and "-" not in uwu
            and not random.randint(0, 6)
        ):
            uwu = f"{uwu[0]}-{uwu}"

        return uwu + extra_punctuation + final_punctuation
