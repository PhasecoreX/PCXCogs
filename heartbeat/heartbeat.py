"""Heartbeat cog for Red-DiscordBot by PhasecoreX."""

import asyncio
import datetime
import logging
import math
from contextlib import suppress
from datetime import timedelta
from typing import Any, ClassVar
from urllib.parse import urlparse

import aiohttp
from redbot.core import Config, checks, commands
from redbot.core import __version__ as redbot_version
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import error, humanize_timedelta, success

from .pcx_lib import SettingDisplay, delete

user_agent = (
    f"Red-DiscordBot/{redbot_version} Heartbeat (https://github.com/PhasecoreX/PCXCogs)"
)
log = logging.getLogger("red.pcxcogs.heartbeat")

MIN_HEARTBEAT_SECONDS = 60


class Heartbeat(commands.Cog):
    """Monitor the uptime of your bot.

    The bot owner can specify a URL that the bot will ping (send a GET request)
    at a configurable frequency. Using this with an uptime tracking service can
    warn you when your bot isn't connected to the internet (and thus usually
    not connected to Discord).
    """

    __author__ = "PhasecoreX"
    __version__ = "2.0.0"

    default_global_settings: ClassVar[dict[str, int]] = {
        "schema_version": 0,
        "frequency": MIN_HEARTBEAT_SECONDS,
    }

    default_endpoint_settings: ClassVar[dict[str, bool | str]] = {
        "url": "",
        "ssl_verify": True,
    }

    def __init__(self, bot: Red) -> None:
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)
        self.config.init_custom("ENDPOINT", 1)
        self.config.register_custom("ENDPOINT", **self.default_endpoint_settings)
        self.session = aiohttp.ClientSession()
        self.current_errors: dict[str, str] = {}
        self.next_heartbeat = datetime.datetime.now(datetime.UTC)
        self.bg_loop_task = None
        self.background_tasks = set()

    #
    # Red methods
    #

    def cog_unload(self) -> None:
        """Clean up when cog shuts down."""
        if self.bg_loop_task:
            self.bg_loop_task.cancel()
        task = asyncio.create_task(self.session.close())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    def format_help_for_context(self, ctx: commands.Context) -> str:
        """Show version in help."""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\nCog Version: {self.__version__}"

    async def red_delete_data_for_user(self, *, _requester: str, _user_id: int) -> None:
        """Nothing to delete."""
        return

    #
    # Initialization methods
    #

    async def initialize(self) -> None:
        """Perform setup actions before loading cog."""
        await self._migrate_config()
        self.enable_bg_loop()

    async def _migrate_config(self) -> None:
        """Perform some configuration migrations."""
        schema_version = await self.config.schema_version()

        if schema_version < 1:
            # Support multiple URLs
            url = await self.config.get_raw("url", default="")
            if url:
                await self.config.custom(
                    "ENDPOINT",
                    await self.get_new_endpoint_id(url),
                ).set({"url": url})
            await self.config.clear_raw("url")
            await self.config.schema_version.set(1)

    #
    # Background loop methods
    #

    def enable_bg_loop(self) -> None:
        """Set up the background loop task."""

        def error_handler(fut: asyncio.Future) -> None:
            try:
                fut.result()
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                log.exception(
                    "Unexpected exception occurred in background loop of Heartbeat: ",
                    exc_info=exc,
                )
                task = asyncio.create_task(
                    self.bot.send_to_owners(
                        "An unexpected exception occurred in the background loop of Heartbeat:\n"
                        f"```{exc!s}```"
                        "Heartbeat pings will not be sent until Heartbeat is reloaded.\n"
                        "Check your console or logs for more details, and consider opening a bug report for this."
                    )
                )
                self.background_tasks.add(task)
                task.add_done_callback(self.background_tasks.discard)

        if self.bg_loop_task:
            self.bg_loop_task.cancel()
        self.bg_loop_task = self.bot.loop.create_task(self.bg_loop())
        self.bg_loop_task.add_done_callback(error_handler)

    async def bg_loop(self) -> None:
        """Background loop."""
        await self.bot.wait_until_ready()
        endpoints_raw = await self.config.custom(
            "ENDPOINT"
        ).all()  # Does NOT return default values
        if not endpoints_raw:
            return
        endpoints = {}
        for endpoint in endpoints_raw:
            endpoints[endpoint] = await self.config.custom(
                "ENDPOINT", endpoint
            ).all()  # Returns default values
        frequency = await self.config.frequency()
        frequency = float(max(frequency, MIN_HEARTBEAT_SECONDS))
        while True:
            self.next_heartbeat = datetime.datetime.now(
                datetime.UTC
            ) + datetime.timedelta(0, frequency)
            await asyncio.sleep(frequency)
            errors: dict[str, str] = {}
            for endpoint_id, config in endpoints.items():
                error = await self.send_heartbeat(config)
                if error:
                    errors[endpoint_id] = error
            self.current_errors = errors

    async def send_heartbeat(self, config: dict) -> str | None:
        """Send a heartbeat ping.

        Returns error message if error, None otherwise
        """
        if not config["url"]:
            return "No URL supplied"
        url = config["url"]
        if "{{ping}}" in url:
            ping: float = self.bot.latency
            if ping is None or math.isnan(ping):
                ping = 0
            url = url.replace("{{ping}}", f"{ping*1000:.2f}")
        last_exception = None
        retries = 3
        while retries > 0:
            try:
                await self.session.get(
                    url,
                    headers={"user-agent": user_agent},
                    ssl=config["ssl_verify"],
                )
            except (TimeoutError, aiohttp.ClientConnectionError) as exc:
                last_exception = exc
            else:
                return None
            retries -= 1
        if last_exception:
            return str(last_exception)
        return None

    #
    # Command methods: heartbeat
    #

    @commands.group()
    @checks.is_owner()
    async def heartbeat(self, ctx: commands.Context) -> None:
        """Manage Heartbeat settings."""

    @heartbeat.command()
    async def settings(self, ctx: commands.Context) -> None:
        """Display current settings."""
        endpoints = await self.config.custom("ENDPOINT").all()
        global_section = SettingDisplay("Global Settings")
        heartbeat_status = "Disabled (no URLs set)"
        if self.bg_loop_task and not self.bg_loop_task.done():
            heartbeat_status = "Enabled"
        elif endpoints:
            heartbeat_status = "Disabled (error occured)"
        global_section.add("Heartbeat", heartbeat_status)
        global_section.add(
            "Frequency", humanize_timedelta(seconds=await self.config.frequency())
        )
        if self.bg_loop_task and not self.bg_loop_task.done():
            global_section.add(
                "Next heartbeat in",
                humanize_timedelta(
                    timedelta=self.next_heartbeat - datetime.datetime.now(datetime.UTC)
                )
                or "<1 second",
            )
        status = SettingDisplay("Heartbeat Status")
        for endpoint in endpoints:
            status.add(endpoint, self.current_errors.get(endpoint, "OK"))
        await ctx.send(global_section.display(status))

    @heartbeat.command()
    async def add(self, ctx: commands.Context, url: str) -> None:
        """Add a new endpoint to send pings to."""
        await delete(ctx.message)
        endpoint_id = await self.get_new_endpoint_id(url)
        await self.config.custom(
            "ENDPOINT",
            endpoint_id,
        ).set({"url": url})
        self.enable_bg_loop()
        await ctx.send(
            success(f"Endpoint `{endpoint_id}` has been added to Heartbeat.")
        )

    @heartbeat.command()
    async def remove(self, ctx: commands.Context, endpoint_id: str) -> None:
        """Remove and disable Heartbeat pings for a given endpoint ID."""
        await self.config.custom("ENDPOINT", endpoint_id).clear()
        self.enable_bg_loop()
        await ctx.send(
            success(f"Endpoint `{endpoint_id}` has been removed from Heartbeat.")
        )

    @heartbeat.group()
    async def modify(self, ctx: commands.Context) -> None:
        """Modify configuration for a given endpoint."""

    @modify.command(name="ssl_verify")
    async def modify_ssl_verify(
        self, ctx: commands.Context, endpoint_id: str, *, true_false: bool
    ) -> None:
        """Configure if we should verify SSL when performing ping."""
        endpoint = await self.get_endpoint_config(endpoint_id)
        if not endpoint:
            await ctx.send(
                error(
                    f"Could not find endpoint ID `{endpoint_id}`. Check `[p]heartbeat settings` for a list of valid endpoint IDs."
                )
            )
            return
        await self.config.custom("ENDPOINT", endpoint_id).ssl_verify.set(true_false)
        self.enable_bg_loop()
        await ctx.send(
            success(
                f"Endpoint `{endpoint_id}` will {'now' if true_false else 'no longer'} verify SSL."
            )
        )

    @heartbeat.command()
    async def rename(
        self, ctx: commands.Context, endpoint_id: str, new_endpoint_id: str
    ) -> None:
        """Rename an endpoint ID."""
        current_config = await self.config.custom("ENDPOINT").all()
        if endpoint_id in current_config:
            await self.config.custom("ENDPOINT", new_endpoint_id).set(
                current_config[endpoint_id]
            )
            await self.config.custom("ENDPOINT", endpoint_id).clear()
            self.enable_bg_loop()
            await ctx.send(
                success(
                    f"Endpoint `{endpoint_id}` has been renamed to `{new_endpoint_id}`."
                )
            )
        else:
            await ctx.send(
                error(
                    f"Could not find endpoint ID `{endpoint_id}`. Check `[p]heartbeat settings` for a list of valid endpoint IDs."
                )
            )

    @heartbeat.command()
    async def reset(self, ctx: commands.Context) -> None:
        """Remove all endpoints and disable Heartbeat pings."""
        await self.config.custom("ENDPOINT").clear()
        self.enable_bg_loop()
        await ctx.send(success("Heartbeat has been disabled completely."))

    @heartbeat.command()
    async def frequency(
        self,
        ctx: commands.Context,
        frequency: commands.TimedeltaConverter(
            minimum=timedelta(seconds=60),
            maximum=timedelta(days=30),
            default_unit="seconds",
        ),
    ) -> None:
        """Set the frequency Heartbeat will send pings."""
        await self.config.frequency.set(frequency.total_seconds())
        await ctx.send(
            success(
                f"Heartbeat frequency has been set to {humanize_timedelta(timedelta=frequency)}."
            )
        )
        self.enable_bg_loop()

    #
    # Private methods
    #

    async def get_new_endpoint_id(self, url: str) -> str:
        """Generate an ID from a given URL."""
        endpoint_id = "default"
        with suppress(Exception):
            endpoint_id = urlparse(url).netloc or endpoint_id
        endpoint_id_result = endpoint_id
        config_check = await self.config.custom(
            "ENDPOINT", endpoint_id_result
        ).all()  # Returns default values
        count = 1
        while config_check["url"]:
            count += 1
            endpoint_id_result = f"{endpoint_id}_{count}"
            config_check = await self.config.custom(
                "ENDPOINT", endpoint_id_result
            ).all()  # Returns default values
        return endpoint_id_result

    async def get_endpoint_config(self, endpoint_id: str) -> dict[str, Any] | None:
        """Get an endpoint config from the DB, ignoring invalid ones."""
        endpoint = await self.config.custom("ENDPOINT", endpoint_id).all()
        if not endpoint["url"]:
            return None
        return endpoint

    #
    # Public methods
    #
