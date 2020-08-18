"""UwU cog for Red-DiscordBot by PhasecoreX."""
from redbot.core import commands

from .pcx_lib import type_message

__author__ = "PhasecoreX"


class UwU(commands.Cog):
    """UwU."""

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    @commands.command(aliases=["owo"])
    async def uwu(self, ctx: commands.Context):
        """Uwuize the pwevious comment."""
        message = (await ctx.channel.history(limit=2).flatten())[1].content
        if not message:
            message = "I can't translate that!"
        await type_message(ctx.channel, self.uwuize_string(message))

    @staticmethod
    def uwuize_string(string: str):
        """Uwuize and wetuwn a stwing."""
        converted = ""

        def uwuize_word(string: str):
            """Uwuize and wetuwn a wowd."""
            # Whowe wowds
            if string.lower().startswith("this") or string.lower().startswith("that"):
                dee = "D" if string[0].isupper() else "d"
                string = dee + string[2:]
            else:
                # Genewic wepwacements
                if (
                    string.lower().startswith("m")
                    and len(string) > 1
                    and string.lower() != "me"
                ):
                    doubleyou = "W" if string[1].isupper() else "w"
                    string = string[0] + doubleyou + string[1:]
                string = string.replace("r", "w").replace("R", "W")
                string = string.replace("l", "w").replace("L", "W")
            # Suffixes
            if string.endswith("?"):
                string = string + "? UwU"
            if string.endswith("!"):
                string = string + "! OwO"
            return string

        current_word = ""
        for letter in string:
            if letter.isprintable() and not letter.isspace():
                current_word += letter
            elif current_word:
                converted += uwuize_word(current_word) + letter
                current_word = ""
            else:
                converted += letter
        if current_word:
            converted += uwuize_word(current_word)
        return converted
