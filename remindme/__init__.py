"""Package for RemindMe cog."""
from .remindme import RemindMe

__red_end_user_data_statement__ = (
    "This cog stores data provided by users for the express purpose of re-displaying. "
    "It does not store user data which was not provided through a command. "
    "Users may delete their own data with or without making a data request."
)


async def setup(bot):
    """Load RemindMe cog."""
    cog = RemindMe(bot)
    await cog.initialize()
    bot.add_cog(cog)
