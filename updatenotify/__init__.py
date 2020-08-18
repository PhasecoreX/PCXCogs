"""Package for UpdateNotify cog."""
from .updatenotify import UpdateNotify

__red_end_user_data_statement__ = (
    "This cog does not persistently store data or metadata about users."
)


async def setup(bot):
    """Load UpdateNotify cog."""
    cog = UpdateNotify(bot)
    await cog.initialize()
    bot.add_cog(cog)
