"""Package for Heartbeat cog."""
from .heartbeat import Heartbeat


async def setup(bot):
    """Load Heartbeat cog."""
    cog = Heartbeat(bot)
    await cog.initialize()
    bot.add_cog(cog)
