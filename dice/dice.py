"""
Dice cog for Red-DiscordBot by PhasecoreX
"""
from io import BytesIO
import random
from tokenize import tokenize, NUMBER, NAME, OP
from redbot.core import checks, Config, commands
from redbot.core.utils.chat_formatting import box
from .evaluate import eval_expr


__author__ = "PhasecoreX"
BaseCog = getattr(commands, "Cog", object)


class Dice(BaseCog):
    """Perform complex dice rolling."""

    default_global_settings = {"max_dice_rolls": 10000, "max_die_sides": 1000}

    def __init__(self, bot):
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
        """Set the maximum number of dice a user can roll at one time."""
        await self.config.max_dice_rolls.set(maximum)
        await ctx.send(
            "Maximum dice rolls per user is now set to {}".format(
                await self.config.max_dice_rolls()
            )
        )

    @diceset.command()
    async def sides(self, ctx: commands.Context, maximum: int):
        """Set the maximum number of sides a die can have."""
        await self.config.max_die_sides.set(maximum)
        await ctx.send(
            "Maximum die sides is now set to {}".format(
                await self.config.max_die_sides()
            )
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
                    "{} rolled {} and got **{}**{}".format(
                        ctx.message.author.mention, roll_friendly, result, roll_log
                    )
                )
            else:
                await ctx.send(
                    "{}, that notation doesn't have any dice for me to roll.".format(
                        ctx.message.author.mention
                    )
                )
        except TooManySides as exception:
            await ctx.send(
                "{}, I don't own a {} sided die to perform that roll.".format(
                    ctx.message.author.mention, exception.value
                )
            )
        except TooManyDice:
            await ctx.send(
                "{}, I don't have that many dice to roll...".format(
                    ctx.message.author.mention
                )
            )
        except KeyError:
            await ctx.send(
                "{}, that is too complex for me to roll.".format(
                    ctx.message.author.mention
                )
            )
        except (ValueError, SyntaxError, TypeError):
            await ctx.send(
                "{}, that doesn't seem like a proper dice equation.".format(
                    ctx.message.author.mention
                )
            )

    @staticmethod
    def get_equation_tokens(roll: str, max_dice: int, max_sides: int):
        """Tokenize roll string and parse #d# dice."""
        result = []
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


class Die:
    """A die roll."""

    def __init__(self, amount, sides):
        self.amount = amount
        self.sides = sides
        self.rolls = []
        self.total = 0

    def __str__(self):
        return str(self.amount) + "d" + str(self.sides)

    def __repr__(self):
        return self.__str__()

    def roll(self):
        """Roll the dice and store the results."""
        for _ in range(self.amount):
            self.rolls.append(random.randint(1, self.sides))
        self.total = sum(self.rolls)


class TooManyDice(ValueError):
    """Too many dice to roll"""


class TooManySides(ValueError):
    """Too many sides on this die"""

    def __init__(self, value):
        super().__init__()
        self.value = value
