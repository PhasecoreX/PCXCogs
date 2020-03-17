"""Heartbeat cog for Red-DiscordBot by PhasecoreX."""
import asyncio
from datetime import timedelta

import aiohttp
import discord
from redbot.core import Config
from redbot.core import __version__ as redbot_version
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box, humanize_timedelta

__author__ = "PhasecoreX"
user_agent = "Red-DiscordBot/{} Heartbeat (https://github.com/PhasecoreX/PCXCogs)".format(
    redbot_version
)


class Heartbeat(commands.Cog):
    """Monitor your bots uptime."""

    default_global_settings = {"url": "", "frequency": 60}

    def __init__(self, bot):
        """Set up the plugin."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, 1224364860)
        self.config.register_global(**self.default_global_settings)
        self.task = self.bot.loop.create_task(self.send_heartbeat())

    def cog_unload(self):
        """Clean up when cog shuts down."""
        if self.task:
            self.task.cancel()

    @commands.group()
    @checks.is_owner()
    async def heartbeatset(self, ctx: commands.Context):
        """Manage Heartbeat settings."""
        if not ctx.invoked_subcommand:
            msg = ("Heartbeat: {}\n" "Frequency: {}").format(
                "Enabled" if await self.config.url() else "Disabled (no URL set)",
                humanize_timedelta(seconds=await self.config.frequency()),
            )
            await ctx.send(box(msg))

    @heartbeatset.command()
    async def url(self, ctx: commands.Context, url: str):
        """Set the URL Heartbeat will send pings to."""
        await delete(ctx.message)
        await self.config.url.set(url)
        await ctx.send(checkmark("Heartbeat URL has been set and enabled."))
        if self.task:
            self.task.cancel()
        self.task = self.bot.loop.create_task(self.send_heartbeat())

    @heartbeatset.command()
    async def frequency(
        self,
        ctx: commands.Context,
        frequency: commands.TimedeltaConverter(
            minimum=timedelta(seconds=60),
            maximum=timedelta(days=30),
            default_unit="seconds",
        ),
    ):
        """Set the frequency Heartbeat will send pings."""
        await self.config.frequency.set(frequency.total_seconds())
        await ctx.send(
            checkmark(
                "Heartbeat frequency has been set to {}.".format(
                    humanize_timedelta(timedelta=frequency)
                )
            )
        )
        if self.task:
            self.task.cancel()
        self.task = self.bot.loop.create_task(self.send_heartbeat())

    async def send_heartbeat(self):
        """Loop task that sends heartbeat pings."""
        await self.bot.wait_until_ready()
        while self.bot.get_cog("Heartbeat") == self:
            url = await self.config.url()
            frequency = await self.config.frequency()
            if url:
                async with aiohttp.ClientSession() as session:
                    await session.get(
                        url, headers={"user-agent": user_agent},
                    )
            if not frequency:
                frequency = 60.0
            await asyncio.sleep(frequency)


async def delete(message: discord.Message):
    """Attempt to delete a message.

    Returns True if successful, False otherwise.
    """
    try:
        await message.delete()
    except discord.NotFound:
        return True  # Already deleted
    except (discord.HTTPException):
        return False
    return True


def checkmark(text: str) -> str:
    """Get text prefixed with a checkmark emoji."""
    return "\N{WHITE HEAVY CHECK MARK} {}".format(text)
