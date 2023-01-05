"""Package for RemindMe cog."""
import json
from pathlib import Path

from redbot.core.bot import Red

from .remindme import RemindMe

with open(Path(__file__).parent / "info.json") as fp:
    __red_end_user_data_statement__ = json.load(fp)["end_user_data_statement"]


async def setup(bot: Red) -> None:
    """Load RemindMe cog."""
    cog = RemindMe(bot)
    await cog.initialize()
    r = bot.add_cog(cog)
    if r is not None:
        await r
