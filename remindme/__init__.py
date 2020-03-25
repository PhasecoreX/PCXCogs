"""Package for RemindMe cog."""
from .remindme import RemindMe


def setup(bot):
    """Load RemindMe cog."""
    cog = RemindMe(bot)
    bot.add_cog(cog)
