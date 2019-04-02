"""Package for Wikipedia cog."""
from .wikipedia import Wikipedia


def setup(bot):
    """Load Wikipedia cog."""
    bot.add_cog(Wikipedia())
