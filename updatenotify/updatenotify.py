"""UpdateNotify cog for Red-DiscordBot by PhasecoreX."""
import asyncio
import datetime
import logging
import os

import aiohttp
from redbot.core import (
    Config,
    VersionInfo,
    checks,
    commands,
    version_info as redbot_version,
)
from redbot.core.utils.chat_formatting import box, humanize_timedelta

from .pcx_lib import SettingDisplay, checkmark

__author__ = "PhasecoreX"
log = logging.getLogger("red.pcxcogs.updatenotify")


class UpdateNotify(commands.Cog):
    """Get notifications when your bot needs updating.

    This cog checks for updates to Red-DiscordBot. If you are also running the
    phasecorex/red-discordbot Docker image, it can also notify you of any image updates.
    """

    default_global_settings = {
        "schema_version": 0,
        "frequency": 3600,
        "check_red_discordbot": True,
        "check_pcx_docker": True,
        "pcx_docker_feature_only": False,
    }

    def __init__(self, bot):
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)

        self.docker_commit = os.environ.get("PCX_DISCORDBOT_COMMIT")
        self.notified_docker_commit = self.docker_commit
        self.docker_build = os.environ.get("PCX_DISCORDBOT_BUILD")
        self.notified_docker_build = self.docker_build
        self.notified_version = redbot_version

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

        def error_handler(fut: asyncio.Future):
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

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    @commands.group()
    @checks.is_owner()
    async def updatenotify(self, ctx: commands.Context):
        """Manage UpdateNotify settings."""
        pass

    @updatenotify.command()
    async def settings(self, ctx: commands.Context):
        """Display current settings."""
        global_section = SettingDisplay("Global Settings")
        global_section.add(
            "Update check interval",
            humanize_timedelta(seconds=await self.config.frequency()),
        )
        global_section.add(
            "Next check in",
            humanize_timedelta(timedelta=self.next_check - datetime.datetime.now()),
        )
        global_section.add(
            "Check Red-DiscordBot update",
            "Enabled" if await self.config.check_red_discordbot() else "Disabled",
        )
        if self.docker_commit:
            global_section.add(
                "Check Docker image update",
                "Enabled" if await self.config.check_pcx_docker() else "Disabled",
            )
            global_section.add(
                "Docker image check type",
                "New features only"
                if await self.config.pcx_docker_feature_only()
                else "All updates",
            )
        await ctx.send(str(global_section))

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
                f"Update check frequency has been set to {humanize_timedelta(timedelta=frequency)}."
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
                f"Red-DiscordBot version checking is now {'enabled' if state else 'disabled'}."
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
                f"Docker image version checking is now {'enabled' if state else 'disabled'}."
            )
        )

    @docker.command(name="type")
    async def docker_type(self, ctx: commands.Context):
        """Toggle checking for feature updates or all updates."""
        state = await self.config.pcx_docker_feature_only()
        state = not state
        await self.config.pcx_docker_feature_only.set(state)
        if state:
            await ctx.send(
                checkmark(
                    "UpdateNotify will now only check for Docker image updates "
                    "that were caused by the codebase being updated (new features/bugfixes)."
                )
            )
        else:
            await ctx.send(
                checkmark(
                    "UpdateNotify will now check for any Docker image updates, "
                    "including ones caused by the base image being updated (potential security updates)."
                )
            )

    @docker.command()
    async def debug(self, ctx: commands.Context):
        """Print out debug version numbers."""
        if not self.docker_commit:
            await ctx.send(
                "This debug option is only really useful if you're using the phasecorex/red-discordbot Docker image."
            )
        else:
            build = await self.get_latest_github_actions_build()
            setting_display = SettingDisplay()
            setting_display.add("Local Docker commit hash", self.docker_commit[:7])
            setting_display.add("Latest Docker commit hash", build["sha"][:7])
            setting_display.add("Local Docker build number", self.docker_build)
            setting_display.add("Latest Docker build number", build["id"])
            if await self.config.pcx_docker_feature_only():
                setting_display.add(
                    "Local Docker Status (based on hash)",
                    "Up to date"
                    if build["sha"] == self.docker_commit
                    else "Update available",
                )
            else:
                setting_display.add(
                    "Local Docker Status (based on build num)",
                    "Up to date"
                    if build["id"] == self.docker_build
                    else "Update available",
                )
            setting_display.add("Latest Docker commit message", build["message"])
            await ctx.send(str(setting_display))

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
                    return VersionInfo.from_str(data["info"]["version"])
            except aiohttp.ServerConnectionError:
                log.warning(
                    "PyPI seems to be having some issues at the moment while checking for the latest Red-DiscordBot "
                    "update. If this keeps happening, and PyPI is indeed up, consider opening a bug report for this."
                )

    @staticmethod
    async def get_latest_github_actions_build():
        """Check GitHub for the latest update to phasecorex/red-discordbot."""
        url = "https://api.github.com/repos/phasecorex/docker-red-discordbot/actions/runs?branch=master&status=success"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise aiohttp.ServerConnectionError
                    data = await resp.json()
                    for run in data["workflow_runs"]:
                        if (
                            run["event"] in ("push", "repository_dispatch")
                            and run["name"] == "build"
                        ):
                            build_id = str(run["id"])
                            commit_sha = run["head_commit"]["id"]
                            commit_message = run["head_commit"]["message"]
                            return {
                                "sha": commit_sha,
                                "id": build_id,
                                "message": commit_message,
                            }
            except aiohttp.ServerConnectionError:
                log.warning(
                    "GitHub seems to be having some issues at the moment while checking for the latest Docker commit. "
                    "If this keeps happening, and GitHub is indeed up, consider opening a bug report for this."
                )

    async def update_check(self, manual: bool = False):
        """Check for all updates."""
        if manual:
            self.notified_version = redbot_version
            self.notified_docker_commit = self.docker_commit
            self.notified_docker_build = self.docker_build

        latest_redbot_version = None
        if await self.config.check_red_discordbot():
            latest_redbot_version = await self.get_latest_redbot_version()
        update_redbot = (
            latest_redbot_version and self.notified_version < latest_redbot_version
        )
        running_newer_redbot = (
            latest_redbot_version and self.notified_version > latest_redbot_version
        )

        update_docker_commit = False
        update_docker_build = False
        latest_docker_build = None
        if self.docker_commit and await self.config.check_pcx_docker():
            latest_docker_build = await self.get_latest_github_actions_build()
            if latest_docker_build:
                update_docker_commit = (
                    self.notified_docker_commit != latest_docker_build["sha"]
                )
                update_docker_build = (
                    self.notified_docker_build != latest_docker_build["id"]
                )

        message = ""

        feature_only = await self.config.pcx_docker_feature_only()
        update_docker = update_docker_commit or (
            update_docker_build and not feature_only
        )
        if update_docker:
            self.notified_docker_commit = latest_docker_build["sha"]
            self.notified_docker_build = latest_docker_build["id"]
            message += (
                "There is a newer version of the `phasecorex/red-discordbot` Docker image available!\n"
                "You will need to use Docker to manually stop, pull, and restart the new image.\n\n"
            )
            if update_docker_commit:
                message += (
                    "This update was caused by new code being pushed, with a commit message of:\n"
                    f"{box(latest_docker_build['message'])}\n"
                )
            else:
                message += (
                    "This update was caused by the image being rebuilt due to the base image being updated.\n"
                    "If you don't want to be bothered with these types of updates, "
                    "consider using `[p]updatenotify docker type`\n\n"
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
            elif self.docker_commit:
                message += (
                    "It looks like you're using the `phasecorex/red-discordbot` Docker image!\n"
                    "Simply issue the `[p]restart` command to have me "
                    "restart and update automatically."
                )

        if manual and not message:
            if await self.config.check_red_discordbot():
                if running_newer_redbot:
                    message += (
                        f"You are running a newer version of Red-DiscordBot ({self.notified_version}) "
                        f"than what is available on PyPI ({latest_redbot_version})"
                    )
                else:
                    message += f"You are already running the latest version of Red-DiscordBot ({self.notified_version})"
            if self.docker_commit and await self.config.check_pcx_docker():
                message += (
                    "\nThe `phasecorex/red-discordbot` Docker image is {}up-to-date."
                ).format("also " if message else "")
            if not message:
                message += "You do not have Red-DiscordBot update checking enabled."
        if message and not manual:
            message = "Hello! " + message
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
