"""Package for UwU cog."""
from .uwu import UwU


def setup(bot):
    """Load UwU cog."""
    cog = UwU()
    bot.add_cog(cog)
