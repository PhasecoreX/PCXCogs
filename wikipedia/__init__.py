"""Package for Wikipedia cog."""
from .wikipedia import Wikipedia

__red_end_user_data_statement__ = (
    "This cog does not persistently store data or metadata about users."
)


def setup(bot):
    """Load Wikipedia cog."""
    cog = Wikipedia()
    bot.add_cog(cog)
