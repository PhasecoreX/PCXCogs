"""Package for RemindMe cog."""
from .remindme import RemindMe


def setup(bot):
    """Load RemindMe cog."""
    bot.add_cog(RemindMe(bot))
