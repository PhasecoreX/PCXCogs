"""Package for UwU cog."""
from .uwu import UwU


def setup(bot):
    """Load UwU cog."""
    bot.add_cog(UwU(bot))
