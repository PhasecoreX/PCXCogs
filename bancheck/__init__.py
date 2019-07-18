"""Package for BanCheck cog."""
from .bancheck import BanCheck


async def setup(bot):
    """Load BanCheck cog."""
    cog = BanCheck(bot)
    await cog.initialize()
    bot.add_cog(cog)
