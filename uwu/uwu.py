"""UwU cog for Red-DiscordBot by PhasecoreX."""
import random

import discord
from redbot.core import commands

from .pcx_lib import type_message

__author__ = "PhasecoreX"


class UwU(commands.Cog):
    """UwU."""

    KAOMOJI_JOY = [
        " (\\* ^ ω ^)",
        " (o^▽^o)",
        " (≧◡≦)",
        ' ☆⌒ヽ(\\*"､^\\*)chu',
        " ( ˘⌣˘)♡(˘⌣˘ )",
        " xD",
    ]
    KAOMOJI_EMBARRASSED = [
        " (⁄ ⁄>⁄ ▽ ⁄<⁄ ⁄)..",
        " (\\*^.^\\*)..,",
        "..,",
        ",,,",
        "... ",
        ".. ",
        " mmm..",
        "O.o",
    ]
    KAOMOJI_CONFUSE = [" (o_O)?", " (°ロ°) !?", " (ーー;)?", " owo?"]
    KAOMOJI_SPARKLES = [" \\*:･ﾟ✧\\*:･ﾟ✧ ", " ☆\\*:・ﾟ ", "〜☆ ", " uguu.., ", "-.-"]

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    @commands.command(aliases=["owo"])
    async def uwu(self, ctx: commands.Context, *, text: str = None):
        """Uwuize the replied to message, previous message, or your own text."""
        if not text:
            if hasattr(ctx.message, "reference") and ctx.message.reference:
                try:
                    text = (
                        await ctx.fetch_message(ctx.message.reference.message_id)
                    ).content
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    pass
            if not text:
                text = (await ctx.channel.history(limit=2).flatten())[
                    1
                ].content or "I can't translate that!"
        await type_message(
            ctx.channel,
            self.uwuize_string(text),
            allowed_mentions=discord.AllowedMentions(
                everyone=False, users=False, roles=False
            ),
        )

    def uwuize_string(self, string: str):
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

    def uwuize_word(self, word: str):
        """Uwuize and return a word.

        Thank you to the following for inspiration:
        https://github.com/senguyen1011/UwUinator
        """
        word = word.lower()
        uwu = word.rstrip(".?!,")
        punctuations = word[len(uwu) :]
        final_punctuation = punctuations[-1] if punctuations else ""
        extra_punctuation = punctuations[:-1] if punctuations else ""

        # Process punctuation
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

        # Full word exceptions
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
            uwu = "boi pussy"
        elif uwu in ("dad", "father"):
            uwu = "daddy"
        # Normal word conversion
        else:
            # Protect specific word endings from changes
            protected = ""
            if (
                uwu.endswith("le")
                or uwu.endswith("ll")
                or uwu.endswith("er")
                or uwu.endswith("re")
            ):
                protected = uwu[-2:]
                uwu = uwu[:-2]
            elif (
                uwu.endswith("les")
                or uwu.endswith("lls")
                or uwu.endswith("ers")
                or uwu.endswith("res")
            ):
                protected = uwu[-3:]
                uwu = uwu[:-3]
            # l -> w, r -> w, n<vowel> -> ny<vowel>, ove -> uv
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

        # Add back punctuations
        uwu += extra_punctuation + final_punctuation

        # Add occasional stutter
        if (
            len(uwu) > 2
            and uwu[0].isalpha()
            and "-" not in uwu
            and not random.randint(0, 6)
        ):
            uwu = f"{uwu[0]}-{uwu}"

        return uwu
