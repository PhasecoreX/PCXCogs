"""Package for UwU cog."""
from .uwu import UwU

__red_end_user_data_statement__ = (
    "This cog does not persistently store data or metadata about users."
)


def setup(bot):
    """Load UwU cog."""
    cog = UwU()
    bot.add_cog(cog)
