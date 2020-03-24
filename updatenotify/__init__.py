"""Package for UpdateNotify cog."""
from .updatenotify import UpdateNotify


async def setup(bot):
    """Load UpdateNotify cog."""
    cog = UpdateNotify(bot)
    await cog.config_migrate()
    bot.add_cog(cog)
    cog.enable_bg_loop()
