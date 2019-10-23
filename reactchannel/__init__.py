"""Package for ReactChannel cog."""
from .reactchannel import ReactChannel


def setup(bot):
    """Load ReactChannel cog."""
    bot.add_cog(ReactChannel(bot))
