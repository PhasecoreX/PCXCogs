"""Heartbeat cog for Red-DiscordBot by PhasecoreX."""
import asyncio
import logging
from datetime import timedelta

import aiohttp
import discord
from redbot.core import Config
from redbot.core import __version__ as redbot_version
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box, humanize_timedelta

from .pcx_lib import checkmark, delete

__author__ = "PhasecoreX"
user_agent = "Red-DiscordBot/{} Heartbeat (https://github.com/PhasecoreX/PCXCogs)".format(
    redbot_version
)
log = logging.getLogger("red.pcxcogs.heartbeat")


class Heartbeat(commands.Cog):
    """Monitor your bots uptime."""

    default_global_settings = {"url": "", "frequency": 60}

    def __init__(self, bot):
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)
        self.session = aiohttp.ClientSession()
        self.bg_loop_task = None

    async def initialize(self):
        """Perform setup actions before loading cog."""
        self.enable_bg_loop()

    def enable_bg_loop(self):
        """Set up the background loop task."""

        def error_handler(self, fut: asyncio.Future):
            try:
                fut.result()
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                log.exception(
                    "Unexpected exception occurred in background loop of Heartbeat: ",
                    exc_info=exc,
                )
                asyncio.create_task(
                    self.bot.send_to_owners(
                        "An unexpected exception occurred in the background loop of Heartbeat.\n"
                        "Heartbeat pings will not be sent until Heartbeat is reloaded.\n"
                        "Check your console or logs for details, and consider opening a bug report for this."
                    )
                )

        if self.bg_loop_task:
            self.bg_loop_task.cancel()
        self.bg_loop_task = self.bot.loop.create_task(self.bg_loop())
        self.bg_loop_task.add_done_callback(error_handler)

    def cog_unload(self):
        """Clean up when cog shuts down."""
        if self.bg_loop_task:
            self.bg_loop_task.cancel()
        asyncio.create_task(self.session.close())

    @commands.group()
    @checks.is_owner()
    async def heartbeat(self, ctx: commands.Context):
        """Manage Heartbeat settings."""
        if not ctx.invoked_subcommand:
            msg = ("Heartbeat: {}\n" "Frequency: {}").format(
                "Enabled" if await self.config.url() else "Disabled (no URL set)",
                humanize_timedelta(seconds=await self.config.frequency()),
            )
            await ctx.send(box(msg))

    @heartbeat.command()
    async def url(self, ctx: commands.Context, url: str):
        """Set the URL Heartbeat will send pings to."""
        await delete(ctx.message)
        await self.config.url.set(url)
        await ctx.send(checkmark("Heartbeat URL has been set and enabled."))
        self.enable_bg_loop()

    @heartbeat.command()
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
        self.enable_bg_loop()

    async def bg_loop(self):
        """Background loop."""
        await self.bot.wait_until_ready()
        frequency = await self.config.frequency()
        if not frequency:
            frequency = 60.0
        while True:
            await self.send_heartbeat()
            await asyncio.sleep(frequency)

    async def send_heartbeat(self):
        """Send a heartbeat ping."""
        url = await self.config.url()
        if url:
            retries = 3
            while retries > 0:
                try:
                    await self.session.get(
                        url, headers={"user-agent": user_agent},
                    )
                    break
                except aiohttp.ClientConnectionError:
                    pass
                retries -= 1
