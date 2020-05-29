"""Package for Dice cog."""
from .dice import Dice


def setup(bot):
    """Load Dice cog."""
    cog = Dice(bot)
    bot.add_cog(cog)
