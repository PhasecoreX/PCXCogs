"""UpdateNotify cog for Red-DiscordBot by PhasecoreX."""
import asyncio
import datetime
import os

import aiohttp
from redbot.core import Config
from redbot.core import __version__ as redbot_version
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box

__author__ = "PhasecoreX"


class UpdateNotify(commands.Cog):
    """Get notifications when your bot needs updating."""

    default_global_settings = {"update_check_interval": 60, "check_pcx_docker": True}

    def __init__(self, bot):
        """Set up the plugin."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, 1224364860)
        self.config.register_global(**self.default_global_settings)

        self.docker_version = os.environ.get("PCX_DISCORDBOT_COMMIT")
        self.docker_tag = os.environ.get("PCX_DISCORDBOT_TAG")
        if not self.docker_tag:
            self.docker_tag = "latest"

        self.notified_version = redbot_version
        self.notified_docker_version = self.docker_version

        self.next_check = datetime.datetime.now()
        self.task = self.bot.loop.create_task(self.check_for_updates())

    def cog_unload(self):
        """Clean up when cog shuts down."""
        if self.task:
            self.task.cancel()

    @commands.group()
    @checks.is_owner()
    async def updatenotify(self, ctx: commands.Context):
        """Manage UpdateNotify settings."""
        if not ctx.invoked_subcommand:
            msg = (
                "Update check interval: {} minutes\nNext check will happen at {}"
            ).format(await self.config.update_check_interval(), self.next_check)
            await ctx.send(box(msg))

    @updatenotify.command()
    async def interval(self, ctx: commands.Context, interval: int):
        """Set the interval that UpdateNotify should check for updates."""
        if interval < 5:
            interval = 5
        await self.config.update_check_interval.set(interval)
        await ctx.send(
            "Update check interval is now set to {} minutes".format(
                await self.config.update_check_interval()
            )
        )
        if self.task:
            self.task.cancel()
        self.task = self.bot.loop.create_task(self.check_for_updates())

    @updatenotify.command()
    async def check(self, ctx: commands.Context):
        """Perform a manual update check."""
        async with ctx.typing():
            message = await self.update_check(manual=True)
            await ctx.send(message)

    @staticmethod
    async def get_latest_redbot_version():
        """Check PyPI for the latest update to Red-DiscordBot."""
        url = "https://pypi.org/pypi/Red-DiscordBot/json"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                return data["info"]["version"]

    @staticmethod
    async def get_latest_docker_commit():
        """Check GitHub for the latest update to phasecorex/red-discordbot."""
        url = "https://api.github.com/repos/phasecorex/docker-red-discordbot/branches/master"
        async with aiohttp.ClientSession() as session:
            on_master = True
            while url:
                async with session.get(url) as resp:
                    data = await resp.json()
                    if on_master:  # That first url has the actual commit data nested.
                        data = data["commit"]
                        on_master = False
                    if "[ci skip]" in data["commit"]["message"]:
                        url = data["parents"][0]["url"]
                        continue
                    sha = data["sha"]
                    commit_date_string = data["commit"]["committer"]["date"].rstrip("Z")
                    commit_date = datetime.datetime.fromisoformat(commit_date_string)
                    return (sha, commit_date)

    @staticmethod
    async def get_latest_docker_build_date(tag: str):
        """Check Docker for the latest update to phasecorex/red-discordbot:latest."""
        url = (
            "https://hub.docker.com/v2/repositories/"
            "phasecorex/red-discordbot/tags/?page=1&page_size=25"
        )
        async with aiohttp.ClientSession() as session:
            while url:
                async with session.get(url) as resp:
                    data = await resp.json()
                    for docker_image in data["results"]:
                        if docker_image["name"] == tag:
                            return datetime.datetime.fromisoformat(
                                docker_image["last_updated"].rstrip("Z")
                            )
                    url = data["next"]

    async def update_check(self, manual: bool = False):
        """Check for all updates."""
        if manual:
            self.notified_version = redbot_version
            self.notified_docker_version = self.docker_version

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
            message += "You are already running the latest version ({})".format(
                self.notified_version
            )
            if self.docker_version and await self.config.check_pcx_docker():
                message += (
                    "\nThe `phasecorex/red-discordbot` Docker image is also up-to-date."
                )
        if message and not manual:
            message = "Hello!\n\n" + message
        return message.strip()

    async def check_for_updates(self):
        """Loop task that checks for updates and notifies the bot owner."""
        await self.bot.wait_until_ready()
        while self.bot.get_cog("UpdateNotify") == self:
            message = await self.update_check()
            if message:
                app_info = await self.bot.application_info()
                await app_info.owner.send(message)
            seconds_to_sleep = await self.config.update_check_interval() * 60
            self.next_check = datetime.datetime.now() + datetime.timedelta(
                0, seconds_to_sleep
            )
            await asyncio.sleep(seconds_to_sleep)
