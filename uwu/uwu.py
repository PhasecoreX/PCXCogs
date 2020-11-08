"""UwU cog for Red-DiscordBot by PhasecoreX."""
import random

import discord
from redbot.core import commands

from .pcx_lib import type_message

__author__ = "PhasecoreX"


class UwU(commands.Cog):
    """UwU."""

    KAOMOJI_JOY = [
        " (* ^ ω ^)",
        " (o^▽^o)",
        " (≧◡≦)",
        ' ☆⌒ヽ(*"､^*)chu',
        " ( ˘⌣˘)♡(˘⌣˘ )",
        " xD",
    ]
    KAOMOJI_EMBARRASSED = [
        " (⁄ ⁄>⁄ ▽ ⁄<⁄ ⁄)..",
        " (*^.^*)..,",
        "..,",
        ",,,",
        "... ",
        ".. ",
        " mmm..",
        "O.o",
    ]
    KAOMOJI_CONFUSE = [" (o_O)?", " (°ロ°) !?", " (ーー;)?", " owo?"]
    KAOMOJI_SPARKLES = [" *:･ﾟ✧*:･ﾟ✧ ", " ☆*:・ﾟ ", "〜☆ ", " uguu.., ", "-.-"]

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    @commands.command(aliases=["owo"])
    async def uwu(self, ctx: commands.Context, *, text: str = None):
        """Uwuize the pwevious message, ow youw own text."""
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
        """Uwuize and wetuwn a stwing."""
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
        """Uwuize and wetuwn a wowd.

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

        # L -> W and R -> W
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
        uwu = uwu.replace("l", "w").replace("r", "w") + protected

        # Full words
        uwu = uwu.replace("you're", "ur")
        uwu = uwu.replace("youre", "ur")
        uwu = uwu.replace("fuck", "fwickk")
        uwu = uwu.replace("shit", "poopoo")
        uwu = uwu.replace("bitch", "meanie")
        uwu = uwu.replace("asshole", "b-butthole")
        uwu = uwu.replace("dick", "peenie")
        uwu = uwu.replace("penis", "peenie")
        uwu = "cummies" if uwu in ("cum", "semen") else uwu
        uwu = "boi pussy" if uwu == "ass" else uwu
        uwu = "daddy" if uwu in ("dad", "father") else uwu

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
