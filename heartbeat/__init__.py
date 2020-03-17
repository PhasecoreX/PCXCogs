"""Package for Heartbeat cog."""
from .heartbeat import Heartbeat


def setup(bot):
    """Load Heartbeat cog."""
    bot.add_cog(Heartbeat(bot))
