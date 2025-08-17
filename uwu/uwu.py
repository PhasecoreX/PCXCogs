"""UwU cog for Red-DiscordBot by PhasecoreX + UwU channel webhook feature."""

import random
from contextlib import suppress
from typing import ClassVar

import discord
from redbot.core import commands, Config
from .pcx_lib import type_message  # keep your type_message utility


class UwU(commands.Cog):
    """UwU."""

    __author__ = "PhasecoreX + Didi"
    __version__ = "2.4.0"

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
        " uguu.. ",
        "-.-",
    ]

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        self.config.register_guild(auto_channels=[])

    #
    # Red methods
    #

    def format_help_for_context(self, ctx: commands.Context) -> str:
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\nCog Version: {self.__version__}"

    async def red_delete_data_for_user(self, *, _requester: str, _user_id: int) -> None:
        return

    #
    # Setup commands
    #

    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.group(invoke_without_command=True)
    async def uwuset(self, ctx: commands.Context):
        """Setup UwU features."""
        await ctx.send_help()

    @uwuset.command(name="addchannel")
    async def uwuset_addchannel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Add a channel for automatic UwU messages."""
        async with self.config.guild(ctx.guild).auto_channels() as channels:
            if channel.id not in channels:
                channels.append(channel.id)
        await ctx.send(f"Added {channel.mention} to UwU auto channels.")

    @uwuset.command(name="removechannel")
    async def uwuset_removechannel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Remove a channel from automatic UwU messages."""
        async with self.config.guild(ctx.guild).auto_channels() as channels:
            if channel.id in channels:
                channels.remove(channel.id)
        await ctx.send(f"Removed {channel.mention} from UwU auto channels.")

    @uwuset.command(name="listchannels")
    async def uwuset_listchannels(self, ctx: commands.Context):
        """List all channels set for automatic UwU messages."""
        channels = await self.config.guild(ctx.guild).auto_channels()
        if not channels:
            await ctx.send("No channels are set for automatic UwU messages.")
            return
        mentions = []
        for cid in channels:
            ch = ctx.guild.get_channel(cid)
            if ch:
                mentions.append(ch.mention)
        await ctx.send("Automatic UwU channels: " + ", ".join(mentions))

    #
    # Command methods
    #

    @commands.command(aliases=["owo"])
    async def uwu(self, ctx: commands.Context, *, text: str | None = None) -> None:
        """Uwuize the replied to message, previous message, or your own text."""
        if not text:
            if hasattr(ctx.message, "reference") and ctx.message.reference:
                with suppress(discord.Forbidden, discord.NotFound, discord.HTTPException):
                    message_id = ctx.message.reference.message_id
                    if message_id:
                        text = (await ctx.fetch_message(message_id)).content
            if not text:
                messages = [message async for message in ctx.channel.history(limit=2)]
                text = messages[1].content or "I can't translate that!"
        await type_message(
            ctx.channel,
            self.uwuize_string(text),
            allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False),
        )

    #
    # Listener for auto-UwU webhook replacement using type_message
    #

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        """Automatically uwu-ize messages in configured channels using webhook."""
        if message.author.bot or not message.guild:
            return

        auto_channels = await self.config.guild(message.guild).auto_channels()
        if message.channel.id not in auto_channels:
            return
        if not message.content:
            return

        uwu_text = self.uwuize_string(message.content)

        # Delete original message
        with suppress(discord.Forbidden, discord.NotFound):
            await message.delete()

        # Find or create webhook
        webhook = discord.utils.get(await message.channel.webhooks(), name="UwU Webhook")
        if webhook is None:
            webhook = await message.channel.create_webhook(name="UwU Webhook")

        # Use type_message to match ?uwu formatting exactly
        await type_message(
            message.channel,
            uwu_text,
            allowed_mentions=discord.AllowedMentions.none(),
            webhook=webhook,
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
            attachments=message.attachments,
            embeds=message.embeds,
        )

    #
    # UwUize methods
    #

    def uwuize_string(self, string: str) -> str:
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
        word = word.lower()
        uwu = word.rstrip(".?!,")
        punctuations = word[len(uwu):]
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

        exceptions = {
            "you're": "ur",
            "youre": "ur",
            "fuck": "fwickk",
            "shit": "poopoo",
            "bitch": "meanie",
            "asshole": "b-butthole",
            "dick": "peenie",
            "penis": "peenie",
            "cum": "cummies",
            "semen": "cummies",
            "ass": "b-butt",
            "dad": "daddy",
            "father": "daddy",
        }
        if uwu in exceptions:
            uwu = exceptions[uwu]
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

        if len(uwu) > 2 and uwu[0].isalpha() and "-" not in uwu and not random.randint(0, 6):
            uwu = f"{uwu[0]}-{uwu}"

        return uwu + extra_punctuation + final_punctuation
