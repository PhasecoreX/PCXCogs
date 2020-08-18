"""Package for Dice cog."""
from .dice import Dice

__red_end_user_data_statement__ = (
    "This cog does not persistently store data or metadata about users."
)


def setup(bot):
    """Load Dice cog."""
    cog = Dice(bot)
    bot.add_cog(cog)
