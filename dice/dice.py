"""Dice cog for Red-DiscordBot by PhasecoreX."""
import asyncio
import re

import pyhedrals
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import error, question
from redbot.core.utils.predicates import MessagePredicate

from .pcx_lib import SettingDisplay, checkmark

__author__ = "PhasecoreX"


class Dice(commands.Cog):
    """Perform complex dice rolling."""

    default_global_settings = {"max_dice_rolls": 10000, "max_die_sides": 10000}
    DROPPED_EXPLODED_RE = re.compile(r"-\*(\d+)\*-")
    EXPLODED_RE = re.compile(r"\*(\d+)\*")
    DROPPED_RE = re.compile(r"-(\d+)-")

    def __init__(self, bot):
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    @commands.group()
    @checks.is_owner()
    async def diceset(self, ctx: commands.Context):
        """Manage Dice settings."""
        pass

    @diceset.command()
    async def settings(self, ctx: commands.Context):
        """Display current settings."""
        global_section = SettingDisplay("Global Settings")
        global_section.add(
            "Maximum number of dice to roll at once", await self.config.max_dice_rolls()
        )
        global_section.add("Maximum sides per die", await self.config.max_die_sides())
        await ctx.send(global_section)

    @diceset.command()
    async def rolls(self, ctx: commands.Context, maximum: int):
        """Set the maximum number of dice a user can roll at one time.

        More formally, the maximum number of random numbers the bot will generate for any one dice calculation.
        WARNING:
        Setting this too high will allow other users to slow down/freeze/crash your bot!
        Generating random numbers is easily the most CPU consuming process here,
        so keep this number low (less than one million, and way less than that on a Pi)
        """
        action = "is already set at"
        if maximum == await self.config.max_dice_rolls():
            pass
        elif maximum > 1000000:
            pred = MessagePredicate.yes_or_no(ctx)
            await ctx.send(
                question(
                    f"Are you **sure** you want to set the maximum rolls to {maximum}? (yes/no)\n"
                    "Setting this over one million will allow other users to slow down/freeze/crash your bot!"
                )
            )
            try:
                await ctx.bot.wait_for("message", check=pred, timeout=30)
            except asyncio.TimeoutError:
                pass
            if pred.result:
                await self.config.max_dice_rolls.set(maximum)
                action = "is now set to"
            else:
                await ctx.send(
                    error(
                        f"Maximum dice rolls per user has been left at {await self.config.max_dice_rolls()}"
                    )
                )
                return
        else:
            await self.config.max_dice_rolls.set(maximum)
            action = "is now set to"

        await ctx.send(
            checkmark(
                f"Maximum dice rolls per user {action} {await self.config.max_dice_rolls()}"
            )
        )

    @diceset.command()
    async def sides(self, ctx: commands.Context, maximum: int):
        """Set the maximum number of sides a die can have.

        Python seems to be pretty good at generating huge random numbers and doing math on them.
        There should be sufficient safety checks in place to mitigate anything getting too crazy.
        But be honest, do you really need to roll multiple five trillion sided dice at once?
        """
        await self.config.max_die_sides.set(maximum)
        await ctx.send(
            checkmark(
                f"Maximum die sides is now set to {await self.config.max_die_sides()}"
            )
        )

    @commands.command()
    async def dice(self, ctx: commands.Context, *, roll: str):
        """Perform die roll based on a dice formula.

        The [PyHedrals](https://github.com/StarlitGhost/pyhedrals) library is used for dice formula parsing.
        Use the link above to learn the notation allowed. Below are a few examples:

        `2d20kh` - Roll 2d20, keep highest die (e.g. initiative advantage)
        `4d4!+2` - Roll 4d4, explode on any 4s, add 2 to result
        `4d6rdl` - Roll 4d6, reroll all 1s, then drop the lowest die
        `6d6c>4` - Roll 6d6, count all dice greater than 4 as successes
        `10d10r<=2kh6` - Roll 10d10, reroll all dice less than or equal to 2, then keep the highest 6 dice

        Modifier order does matter, and usually they allow for specifying a specific number or number ranges after them.
        """
        try:
            dr = pyhedrals.DiceRoller(
                maxDice=await self.config.max_dice_rolls(),
                maxSides=await self.config.max_die_sides(),
            )
            result = dr.parse(roll)
            roll_message = f"\N{GAME DIE} {ctx.message.author.mention} rolled {roll} and got **{result.result}**"
            if len(roll_message) > 2000:
                raise ValueError("resulting roll message is too big to send in Discord")
            roll_log = "\n".join(result.strings())
            roll_log = self.DROPPED_EXPLODED_RE.sub(r"~~**\1!**~~", roll_log)
            roll_log = self.EXPLODED_RE.sub(r"**\1!**", roll_log)
            roll_log = self.DROPPED_RE.sub(r"~~\1~~", roll_log)
            roll_log = roll_log.replace(",", ", ")
            if len(roll_message) + len(roll_log) > 2000:
                roll_log = "*(Roll log too long to display)*"
            await ctx.send(f"{roll_message}\n{roll_log}")
        except (
            ValueError,
            NotImplementedError,
            pyhedrals.InvalidOperandsException,
            pyhedrals.SyntaxErrorException,
            pyhedrals.UnknownCharacterException,
        ) as exception:
            await ctx.send(
                error(
                    f"{ctx.message.author.mention}, I couldn't parse your dice formula:\n`{str(exception)}`"
                )
            )
