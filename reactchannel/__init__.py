"""Package for ReactChannel cog."""
from .reactchannel import ReactChannel


async def setup(bot):
    """Load ReactChannel cog."""
    cog = ReactChannel(bot)
    await cog.initialize()
    bot.add_cog(cog)
