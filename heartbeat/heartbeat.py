"""Heartbeat cog for Red-DiscordBot by PhasecoreX."""
import asyncio
import datetime
import logging
from datetime import timedelta

import aiohttp
from redbot.core import Config
from redbot.core import __version__ as redbot_version
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import error, humanize_timedelta

from .pcx_lib import SettingDisplay, checkmark, delete

user_agent = (
    f"Red-DiscordBot/{redbot_version} Heartbeat (https://github.com/PhasecoreX/PCXCogs)"
)
log = logging.getLogger("red.pcxcogs.heartbeat")


class Heartbeat(commands.Cog):
    """Monitor the uptime of your bot.

    The bot owner can specify a URL that the bot will ping (send a GET request)
    at a configurable frequency. Using this with an uptime tracking service can
    warn you when your bot isn't connected to the internet (and thus usually
    not connected to Discord).
    """

    __author__ = "PhasecoreX"
    __version__ = "1.3.0"

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
        self.current_error = None
        self.next_heartbeat = datetime.datetime.now(datetime.timezone.utc)
        self.bg_loop_task = None

    #
    # Red methods
    #

    def cog_unload(self):
        """Clean up when cog shuts down."""
        if self.bg_loop_task:
            self.bg_loop_task.cancel()
        asyncio.create_task(self.session.close())

    def format_help_for_context(self, ctx: commands.Context) -> str:
        """Show version in help."""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\nCog Version: {self.__version__}"

    async def red_delete_data_for_user(
        self, **kwargs
    ):  # pylint: disable=unused-argument
        """Nothing to delete."""
        return

    #
    # Initialization methods
    #

    async def initialize(self):
        """Perform setup actions before loading cog."""
        self.enable_bg_loop()

    #
    # Background loop methods
    #

    def enable_bg_loop(self, skip_first=False):
        """Set up the background loop task."""

        def error_handler(fut: asyncio.Future):
            try:
                fut.result()
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # pylint: disable=broad-except
                log.exception(
                    "Unexpected exception occurred in background loop of Heartbeat: ",
                    exc_info=exc,
                )
                asyncio.create_task(
                    self.bot.send_to_owners(
                        "An unexpected exception occurred in the background loop of Heartbeat:\n"
                        f"```{str(exc)}```"
                        "Heartbeat pings will not be sent until Heartbeat is reloaded.\n"
                        "Check your console or logs for more details, and consider opening a bug report for this."
                    )
                )

        if self.bg_loop_task:
            self.bg_loop_task.cancel()
        self.bg_loop_task = self.bot.loop.create_task(self.bg_loop(skip_first))
        self.bg_loop_task.add_done_callback(error_handler)

    async def bg_loop(self, skip_first):
        """Background loop."""
        await self.bot.wait_until_ready()
        url = await self.config.url()
        if not url:
            return
        frequency = await self.config.frequency()
        if frequency < 60:
            frequency = 60.0
        if not skip_first:
            self.current_error = await self.send_heartbeat(url)
        while True:
            self.next_heartbeat = datetime.datetime.now(
                datetime.timezone.utc
            ) + datetime.timedelta(0, frequency)
            await asyncio.sleep(frequency)
            self.current_error = await self.send_heartbeat(url)

    async def send_heartbeat(self, url):
        """Send a heartbeat ping.

        Returns error message if error, None otherwise
        """
        if not url:
            return "No URL supplied"
        last_exception = None
        retries = 3
        while retries > 0:
            try:
                await self.session.get(
                    url,
                    headers={"user-agent": user_agent},
                )
                return
            except (
                aiohttp.ClientConnectionError,
                asyncio.TimeoutError,
            ) as exc:
                last_exception = exc
            retries -= 1
        return str(last_exception)

    #
    # Command methods: heartbeat
    #

    @commands.group()
    @checks.is_owner()
    async def heartbeat(self, ctx: commands.Context):
        """Manage Heartbeat settings."""

    @heartbeat.command()
    async def settings(self, ctx: commands.Context):
        """Display current settings."""
        global_section = SettingDisplay("Global Settings")
        heartbeat_status = "Disabled (no URL set)"
        if self.bg_loop_task and not self.bg_loop_task.done():
            heartbeat_status = "Enabled"
        elif await self.config.url():
            heartbeat_status = "Disabled (faulty URL)"
        global_section.add("Heartbeat", heartbeat_status)
        global_section.add(
            "Frequency", humanize_timedelta(seconds=await self.config.frequency())
        )
        if self.bg_loop_task and not self.bg_loop_task.done():
            global_section.add(
                "Next heartbeat in",
                humanize_timedelta(
                    timedelta=self.next_heartbeat
                    - datetime.datetime.now(datetime.timezone.utc)
                )
                or "0 seconds",
            )
        if self.current_error:
            global_section.add("Current error", self.current_error)
        await ctx.send(str(global_section))

    @heartbeat.command()
    async def url(self, ctx: commands.Context, url: str):
        """Set the URL Heartbeat will send pings to."""
        await delete(ctx.message)
        try:
            error_message = await self.send_heartbeat(url)
            if not error_message:
                await self.config.url.set(url)
                self.enable_bg_loop(skip_first=True)
                await ctx.send(checkmark("Heartbeat URL has been set and enabled."))
                return
        except Exception as ex:
            error_message = str(ex)
        previous_url_text = (
            "I will continue to use the previous URL instead."
            if await self.config.url()
            else ""
        )
        await ctx.send(
            error(
                f"Something seems to be wrong with that URL, I am not able to connect to it:\n```{error_message}```{previous_url_text}"
            )
        )

    @heartbeat.command()
    async def disable(self, ctx: commands.Context):
        """Remove the set URL and disable Heartbeat pings."""
        await self.config.url.clear()
        self.enable_bg_loop()
        await ctx.send(checkmark("Heartbeat has been disabled."))

    @heartbeat.command()
    async def frequency(
        self,
        ctx: commands.Context,
        frequency: commands.TimedeltaConverter(
            minimum=timedelta(seconds=60),
            maximum=timedelta(days=30),
            default_unit="seconds",  # noqa: F821
        ),
    ):
        """Set the frequency Heartbeat will send pings."""
        await self.config.frequency.set(frequency.total_seconds())
        await ctx.send(
            checkmark(
                f"Heartbeat frequency has been set to {humanize_timedelta(timedelta=frequency)}."
            )
        )
        self.enable_bg_loop()
