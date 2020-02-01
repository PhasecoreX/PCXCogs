"""Dice cog for Red-DiscordBot by PhasecoreX."""
import asyncio
import random
from io import BytesIO
from tokenize import NAME, NUMBER, OP, tokenize
from typing import List, Union

from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import box, error, question, warning
from redbot.core.utils.predicates import MessagePredicate

from .evaluate import eval_expr

__author__ = "PhasecoreX"


class Dice(commands.Cog):
    """Perform complex dice rolling."""

    default_global_settings = {"max_dice_rolls": 10000, "max_die_sides": 1000}

    def __init__(self, bot):
        """Set up the plugin."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, 1224364860)
        self.config.register_global(**self.default_global_settings)

    @commands.group()
    @checks.is_owner()
    async def diceset(self, ctx: commands.Context):
        """Manage Dice settings."""
        if not ctx.invoked_subcommand:
            msg = (
                "Maximum number of dice to roll at once: {}\n"
                "Maximum sides per die:                  {}"
                "".format(
                    await self.config.max_dice_rolls(),
                    await self.config.max_die_sides(),
                )
            )
            await ctx.send(box(msg))

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
        force = False
        if maximum == await self.config.max_dice_rolls():
            pass
        elif maximum > 1000000:
            pred = MessagePredicate.yes_or_no(ctx)
            await ctx.send(
                question(
                    "Are you **sure** you want to set the maximum rolls to {}? (yes/no)\n"
                    "Setting this over one million will allow other users to "
                    "slow down/freeze/crash your bot!".format(maximum)
                )
            )
            try:
                await ctx.bot.wait_for("message", check=pred, timeout=30)
            except asyncio.TimeoutError:
                pass
            if pred.result:
                await self.config.max_dice_rolls.set(maximum)
                action = "is now set to"
                force = True
            else:
                await ctx.send(
                    error(
                        "Maximum dice rolls per user has been left at {}".format(
                            await self.config.max_dice_rolls()
                        )
                    )
                )
                return
        else:
            await self.config.max_dice_rolls.set(maximum)
            action = "is now set to"

        await self.confirm(
            ctx.message,
            "Maximum dice rolls per user {} {}".format(
                action, await self.config.max_dice_rolls()
            ),
            force=force,
        )

    @diceset.command()
    async def sides(self, ctx: commands.Context, maximum: int):
        """Set the maximum number of sides a die can have.

        Python seems to be pretty good at generating huge random numbers and doing math on them.
        There should be sufficient safety checks in place to mitigate anything getting too crazy.
        But be honest, do you really need to roll multiple five trillion sided dice at once?
        """
        await self.config.max_die_sides.set(maximum)
        await self.confirm(
            ctx.message,
            "Maximum die sides is now set to {}".format(
                await self.config.max_die_sides()
            ),
        )

    @commands.command()
    async def dice(self, ctx: commands.Context, *, roll: str):
        """Perform die roll."""
        try:
            # Pass 1: Tokenize and convert #d# into die objects
            roll_pass1 = self.get_equation_tokens(
                roll,
                await self.config.max_dice_rolls(),
                await self.config.max_die_sides(),
            )
            # Pass 2: Roll dice and build math string to evaluate
            roll_log = ""
            roll_pass2 = ""
            roll_friendly = ""
            for token in roll_pass1:
                if isinstance(token, Die):
                    token.roll()
                    roll_pass2 += str(token.total)
                    roll_log += "\nRolling {}: {} = {}".format(
                        str(token), str(token.rolls), str(token.total)
                    )
                else:
                    roll_pass2 += str(token)
                roll_friendly += str(token)
            # Pass 3: Evaluate results
            if roll_log:
                result = str(eval_expr(roll_pass2))
                roll_pass2 = roll_pass2.replace("*", "×")
                roll_friendly = roll_friendly.replace("*", "×")
                roll_log = "\n*Roll Log:" + roll_log
                if len(roll_pass1) > 1:
                    roll_log += "\nResulting equation: {} = {}".format(
                        roll_pass2, result
                    )
                roll_log += "*"
                if len(roll_log) > 1500:
                    roll_log = "\n*(Log too long to display)*"
                await ctx.send(
                    "\N{GAME DIE} {} rolled {} and got **{}**{}".format(
                        ctx.message.author.mention, roll_friendly, result, roll_log
                    )
                )
            else:
                await ctx.send(
                    warning(
                        "{}, that notation doesn't have any dice for me to roll.".format(
                            ctx.message.author.mention
                        )
                    )
                )
        except TooManySides as exception:
            await ctx.send(
                error(
                    "{}, I don't own a {} sided die to perform that roll.".format(
                        ctx.message.author.mention, exception.value
                    )
                )
            )
        except TooManyDice:
            await ctx.send(
                error(
                    "{}, I don't have that many dice to roll...".format(
                        ctx.message.author.mention
                    )
                )
            )
        except KeyError:
            await ctx.send(
                error(
                    "{}, that is too complex for me to roll.".format(
                        ctx.message.author.mention
                    )
                )
            )
        except (ValueError, SyntaxError, TypeError):
            await ctx.send(
                error(
                    "{}, that doesn't seem like a proper dice equation.".format(
                        ctx.message.author.mention
                    )
                )
            )

    @staticmethod
    def get_equation_tokens(roll: str, max_dice: int, max_sides: int):
        """Tokenize roll string and parse #d# dice."""
        result: List[Union[int, str, Die]] = []
        previous_number = None
        for toktype, tokval, _, _, _ in tokenize(
            BytesIO(roll.encode("utf-8")).readline
        ):
            if toktype == NUMBER:
                previous_number = int(tokval)
            elif toktype == NAME:
                if tokval[:1] == "d":
                    sides = int(tokval[1:])
                    if sides > max_sides:
                        raise TooManySides(sides)
                    if not previous_number:
                        previous_number = 1
                    if previous_number > max_dice:
                        raise TooManyDice
                    max_dice -= previous_number
                    result.append(Die(previous_number, sides))
                    previous_number = None
                else:
                    # Doesn't start with a "d"
                    raise ValueError
            elif toktype == OP:
                if previous_number:
                    result.append(previous_number)
                    previous_number = None
                result.append(tokval)
        if previous_number:
            result.append(previous_number)
        return result

    async def confirm(self, message, text: str, force: bool = False):
        """Add a checkmark emoji to the specified message.

        If the bot is not allowed to add reactions, responds with text instead.
        You can also force the display of the message, regardless of react permissions.
        """
        if (
            not force
            and message.channel.permissions_for(message.guild.me).add_reactions
        ):
            await message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        else:
            await message.channel.send("\N{WHITE HEAVY CHECK MARK} {}".format(text))


class Die:
    """A die roll."""

    def __init__(self, amount, sides):
        """Create a representation of a set of dice."""
        self.amount = amount
        self.sides = sides
        self.rolls = []
        self.total = 0

    def __str__(self):
        """Return the string representation of a dice roll, e.g. 3d6."""
        return str(self.amount) + "d" + str(self.sides)

    def __repr__(self):
        """Return the string representation of a dice roll, e.g. 3d6."""
        return self.__str__()

    def roll(self):
        """Roll the dice and store the results."""
        self.rolls = []
        self.total = 0
        rolled = 0
        for _ in range(self.amount):
            roll_result = random.randint(1, self.sides)  # nosec (not cryptographic)
            if rolled < 750:
                # If we've rolled over 750 dice, we won't log them (they won't show up anyway)
                self.rolls.append(roll_result)
            self.total += roll_result
            rolled += 1


class TooManyDice(ValueError):
    """Too many dice to roll."""


class TooManySides(ValueError):
    """Too many sides on this die."""

    def __init__(self, value):
        """Set the value that is too many sides."""
        super().__init__()
        self.value = value
