"""Package for RemindMe cog."""
from .remindme import RemindMe


async def setup(bot):
    """Load RemindMe cog."""
    cog = RemindMe(bot)
    await cog.initialize()
    bot.add_cog(cog)
