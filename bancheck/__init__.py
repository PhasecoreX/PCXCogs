"""Package for BanCheck cog."""
from .bancheck import BanCheck


def setup(bot):
    """Load BanCheck cog."""
    bot.add_cog(BanCheck(bot))
