"""Package for DecodeBinary cog."""
from .decodebinary import DecodeBinary


def setup(bot):
    """Load DecodeBinary cog."""
    cog = DecodeBinary(bot)
    bot.add_cog(cog)
