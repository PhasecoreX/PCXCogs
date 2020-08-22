"""Package for AutoRoom cog."""
from .autoroom import AutoRoom

__red_end_user_data_statement__ = (
    "This cog does not persistently store data or metadata about users."
)


async def setup(bot):
    """Load AutoRoom cog."""
    cog = AutoRoom(bot)
    bot.add_cog(cog)
