"""Package for ReactChannel cog."""
from .reactchannel import ReactChannel

__red_end_user_data_statement__ = (
    "This cog stores Discord IDs along with a karma value based on total upvotes and downvotes on the users messages. "
    "Users may reset/remove their own karma total by making a data removal request."
)


async def setup(bot):
    """Load ReactChannel cog."""
    cog = ReactChannel(bot)
    await cog.initialize()
    bot.add_cog(cog)
