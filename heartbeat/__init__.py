"""Package for Heartbeat cog."""
from .heartbeat import Heartbeat


def setup(bot):
    """Load Heartbeat cog."""
    cog = Heartbeat(bot)
    bot.add_cog(cog)
    cog.enable_bg_loop()
