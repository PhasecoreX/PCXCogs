"""Package for Wikipedia cog."""
from .wikipedia import Wikipedia


def setup(bot):
    """Load Wikipedia cog."""
    cog = Wikipedia()
    bot.add_cog(cog)
