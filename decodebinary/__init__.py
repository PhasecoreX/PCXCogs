"""Package for DecodeBinary cog."""
from .decodebinary import DecodeBinary


def setup(bot):
    """Load DecodeBinary cog."""
    bot.add_cog(DecodeBinary(bot))
