"""Package for Dice cog."""
from .dice import Dice


def setup(bot):
    """Load Dice cog."""
    bot.add_cog(Dice(bot))
