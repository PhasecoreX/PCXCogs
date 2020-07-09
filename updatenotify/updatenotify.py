"""UpdateNotify cog for Red-DiscordBot by PhasecoreX."""
import asyncio
import datetime
import logging
import os

import aiohttp
from redbot.core import Config
from redbot.core import __version__ as redbot_version
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box, humanize_timedelta

from .pcx_lib import checkmark

__author__ = "PhasecoreX"
log = logging.getLogger("red.pcxcogs.updatenotify")


class UpdateNotify(commands.Cog):
    """Get notifications when your bot needs updating."""

    default_global_settings = {
        "schema_version": 0,
        "frequency": 3600,
        "check_red_discordbot": True,
        "check_pcx_docker": True,
    }

    def __init__(self, bot):
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)

        self.docker_version = os.environ.get("PCX_DISCORDBOT_COMMIT")
        self.docker_tag = os.environ.get("PCX_DISCORDBOT_TAG")
        if not self.docker_tag:
            self.docker_tag = "latest"

        self.notified_version = redbot_version
        self.notified_docker_version = self.docker_version

        self.next_check = datetime.datetime.now()
        self.bg_loop_task = None

    async def initialize(self):
        """Perform setup actions before loading cog."""
        await self._migrate_config()
        self.enable_bg_loop()

    async def _migrate_config(self):
        """Perform some configuration migrations."""
        if not await self.config.schema_version():
            # Migrate old update_check_interval (minutes) to frequency (seconds)
            update_check_interval = await self.config.get_raw(
                "update_check_interval", default=False
            )
            if update_check_interval:
                await self.config.frequency.set(update_check_interval * 60.0)
                await self.config.clear_raw("update_check_interval")
            await self.config.clear_raw("version")
            await self.config.schema_version.set(1)

    def enable_bg_loop(self):
        """Set up the background loop task."""

        def error_handler(self, fut: asyncio.Future):
            try:
                fut.result()
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                log.exception(
                    "Unexpected exception occurred in background loop of UpdateNotify: ",
                    exc_info=exc,
                )
                asyncio.create_task(
                    self.bot.send_to_owners(
                        "An unexpected exception occurred in the background loop of UpdateNotify.\n"
                        "Updates will not be checked until UpdateNotify is reloaded.\n"
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

    @commands.group()
    @checks.is_owner()
    async def updatenotify(self, ctx: commands.Context):
        """Manage UpdateNotify settings."""
        if not ctx.invoked_subcommand:
            msg = (
                "Update check interval:       {}\n"
                "Next check in:               {}\n"
                "Check Red-DiscordBot update: {}"
            ).format(
                humanize_timedelta(seconds=await self.config.frequency()),
                humanize_timedelta(
                    seconds=(self.next_check - datetime.datetime.now()).total_seconds()
                ),
                "Enabled" if await self.config.check_red_discordbot() else "Disabled",
            )
            if self.docker_version:
                msg += "\nCheck Docker image update:   {}".format(
                    "Enabled" if await self.config.check_pcx_docker() else "Disabled"
                )
            await ctx.send(box(msg))

    @updatenotify.command()
    async def frequency(
        self,
        ctx: commands.Context,
        frequency: commands.TimedeltaConverter(
            minimum=datetime.timedelta(minutes=5),
            maximum=datetime.timedelta(days=30),
            default_unit="minutes",
        ),
    ):
        """Set the frequency that UpdateNotify should check for updates."""
        await self.config.frequency.set(frequency.total_seconds())
        await ctx.send(
            checkmark(
                "Update check frequency has been set to {}.".format(
                    humanize_timedelta(timedelta=frequency)
                )
            )
        )
        self.enable_bg_loop()

    @updatenotify.command()
    async def check(self, ctx: commands.Context):
        """Perform a manual update check."""
        async with ctx.typing():
            message = await self.update_check(manual=True)
            await ctx.send(message)

    @updatenotify.command(name="toggle")
    async def redbot_toggle(self, ctx: commands.Context):
        """Toggle checking for Red-DiscordBot updates.

        Useful if you only want to check for Docker image updates.
        """
        state = await self.config.check_red_discordbot()
        state = not state
        await self.config.check_red_discordbot.set(state)
        await ctx.send(
            checkmark(
                "Red-DiscordBot version checking is now {}.".format(
                    "enabled" if state else "disabled"
                )
            )
        )

    @updatenotify.group()
    async def docker(self, ctx: commands.Context):
        """Options for checking for phasecorex/red-discordbot Docker image updates."""
        pass

    @docker.command(name="toggle")
    async def docker_toggle(self, ctx: commands.Context):
        """Toggle checking for phasecorex/red-discordbot Docker image updates."""
        state = await self.config.check_pcx_docker()
        state = not state
        await self.config.check_pcx_docker.set(state)
        await ctx.send(
            checkmark(
                "Docker image version checking is now {}.".format(
                    "enabled" if state else "disabled"
                )
            )
        )

    @docker.command()
    async def debug(self, ctx: commands.Context):
        """Print out debug version numbers."""
        if not self.docker_version:
            msg = "This debug option is only really useful if you're using the phasecorex/red-discordbot Docker image."
        else:
            commit = await self.get_latest_docker_commit()
            build = await self.get_latest_docker_build_date(self.docker_tag)
            status = "Up to date"
            if commit[0] != self.docker_version:
                status = "Update available"
            if build < commit[1]:
                status = "Waiting for build"
            msg = (
                "Local Docker tag:          {}\n"
                "Local Docker version:      {}\n"
                "Latest Docker commit:      {}\n"
                "Latest Docker commit date: {}\n"
                "Latest Docker build date:  {}\n"
                "Local Docker Status:       {}"
            ).format(
                self.docker_tag,
                self.docker_version,
                commit[0],
                commit[1],
                build,
                status,
            )
        await ctx.send(box(msg))

    @staticmethod
    async def get_latest_redbot_version():
        """Check PyPI for the latest update to Red-DiscordBot."""
        url = "https://pypi.org/pypi/Red-DiscordBot/json"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise aiohttp.ServerConnectionError
                    data = await resp.json()
                    return data["info"]["version"]
            except aiohttp.ServerConnectionError:
                log.warning(
                    "PyPI seems to be having some issues at the moment while checking for the latest Red-DiscordBot update. "
                    "If this keeps happening, and PyPI is indeed up, consider opening a bug report for this."
                )

    @staticmethod
    async def get_latest_docker_commit():
        """Check GitHub for the latest update to phasecorex/red-discordbot."""
        url = "https://api.github.com/repos/phasecorex/docker-red-discordbot/branches/master"
        async with aiohttp.ClientSession() as session:
            try:
                on_master = True
                while url:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            raise aiohttp.ServerConnectionError
                        data = await resp.json()
                        if on_master:
                            # That first url has the actual commit data nested.
                            data = data["commit"]
                            on_master = False
                        if "[ci skip]" in data["commit"]["message"]:
                            url = data["parents"][0]["url"]
                            continue
                        sha = data["sha"]
                        commit_date_string = data["commit"]["committer"]["date"].rstrip(
                            "Z"
                        )
                        commit_date = datetime.datetime.fromisoformat(
                            commit_date_string
                        )
                        return (sha, commit_date)
            except aiohttp.ServerConnectionError:
                log.warning(
                    "GitHub seems to be having some issues at the moment while checking for the latest Docker commit. "
                    "If this keeps happening, and GitHub is indeed up, consider opening a bug report for this."
                )

    @staticmethod
    async def get_latest_docker_build_date(tag: str):
        """Check Docker for the latest update to phasecorex/red-discordbot:latest."""
        url = (
            "https://hub.docker.com/v2/repositories/"
            "phasecorex/red-discordbot/tags/?page=1&page_size=25"
        )
        async with aiohttp.ClientSession() as session:
            try:
                while url:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            raise aiohttp.ServerConnectionError
                        data = await resp.json()
                        for docker_image in data["results"]:
                            if docker_image["name"] == tag:
                                return datetime.datetime.fromisoformat(
                                    docker_image["last_updated"][:19]
                                )
                        url = data["next"]
            except aiohttp.ServerConnectionError:
                log.warning(
                    "Docker Hub seems to be having some issues at the moment while checking for the latest update. "
                    "If this keeps happening, and Docker Hub is indeed up, consider opening a bug report for this."
                )

    async def update_check(self, manual: bool = False):
        """Check for all updates."""
        if manual:
            self.notified_version = redbot_version
            self.notified_docker_version = self.docker_version

        latest_redbot_version = None
        if await self.config.check_red_discordbot():
            latest_redbot_version = await self.get_latest_redbot_version()
        update_redbot = (
            latest_redbot_version and self.notified_version != latest_redbot_version
        )

        update_docker = False
        if self.docker_version and await self.config.check_pcx_docker():
            latest_docker_version = await self.get_latest_docker_commit()
            if (
                latest_docker_version
                and self.notified_docker_version != latest_docker_version[0]
            ):
                # If the commit hash differs, we know there is an update.
                # However, we will need to check if the build has been updated yet.
                latest_docker_build = await self.get_latest_docker_build_date(
                    self.docker_tag
                )
                if (
                    latest_docker_build
                    and latest_docker_build > latest_docker_version[1]
                ):
                    update_docker = True

        message = ""

        if update_docker:
            self.notified_docker_version = latest_docker_version[0]
            message += (
                "There is a newer version of the `phasecorex/red-discordbot` Docker image "
                "available!\n"
                "You will need to use Docker to manually stop, pull, and restart the new image.\n\n"
            )

        if update_redbot:
            self.notified_version = latest_redbot_version
            also_insert = "also " if update_docker else ""
            message += (
                "There is {}a newer version of Red-DiscordBot available!\n"
                "Your version: {}\nLatest version: {}\n\n"
            ).format(also_insert, redbot_version, latest_redbot_version)

            if update_docker:
                message += (
                    "When you stop, pull, and restart the new image, I will also "
                    "update myself automatically as I start up."
                )
            elif self.docker_version:
                message += (
                    "It looks like you're using the `phasecorex/red-discordbot` Docker image!\n"
                    "Simply issue the `[p]restart` command to have me "
                    "restart and update automatically."
                )

        if manual and not message:
            if await self.config.check_red_discordbot():
                message += "You are already running the latest version ({})".format(
                    self.notified_version
                )
            if self.docker_version and await self.config.check_pcx_docker():
                message += (
                    "\nThe `phasecorex/red-discordbot` Docker image is {}up-to-date."
                ).format("also " if message else "")
            if not message:
                message += "You do not have Red-DiscordBot update checking enabled."
        if message and not manual:
            message = "Hello!\n\n" + message
        return message.strip()

    async def bg_loop(self):
        """Background loop."""
        await self.bot.wait_until_ready()
        frequency = await self.config.frequency()
        if not frequency or frequency < 300.0:
            frequency = 300.0
        while True:
            await self.check_for_updates()
            self.next_check = datetime.datetime.now() + datetime.timedelta(0, frequency)
            await asyncio.sleep(frequency)

    async def check_for_updates(self):
        """Check for updates and notify the bot owner."""
        try:
            message = await self.update_check()
            if message:
                await self.bot.send_to_owners(message)
        except aiohttp.ClientConnectionError:
            pass
