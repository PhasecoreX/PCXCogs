"""Package for NetSpeed cog."""
from .netspeed import NetSpeed


def setup(bot):
    """Load NetSpeed cog."""
    cog = NetSpeed()
    bot.add_cog(cog)
