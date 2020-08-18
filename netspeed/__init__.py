"""Package for NetSpeed cog."""
from .netspeed import NetSpeed

__red_end_user_data_statement__ = (
    "This cog does not persistently store data or metadata about users."
)


def setup(bot):
    """Load NetSpeed cog."""
    cog = NetSpeed()
    bot.add_cog(cog)
