"""Package for Heartbeat cog."""
from .heartbeat import Heartbeat

__red_end_user_data_statement__ = (
    "This cog does not persistently store data or metadata about users."
)


async def setup(bot):
    """Load Heartbeat cog."""
    cog = Heartbeat(bot)
    await cog.initialize()
    bot.add_cog(cog)
