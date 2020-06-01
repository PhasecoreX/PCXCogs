"""Package for UpdateNotify cog."""
from .updatenotify import UpdateNotify


async def setup(bot):
    """Load UpdateNotify cog."""
    cog = UpdateNotify(bot)
    await cog.initialize()
    bot.add_cog(cog)
