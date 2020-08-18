"""Package for DecodeBinary cog."""
from .decodebinary import DecodeBinary

__red_end_user_data_statement__ = (
    "This cog does not persistently store data or metadata about users."
)


def setup(bot):
    """Load DecodeBinary cog."""
    cog = DecodeBinary(bot)
    bot.add_cog(cog)
