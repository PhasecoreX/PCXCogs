"""Package for UpdateNotify cog."""
from .updatenotify import UpdateNotify


def setup(bot):
    """Load UpdateNotify cog."""
    bot.add_cog(UpdateNotify(bot))
