"""UpdateNotify cog for Red-DiscordBot by PhasecoreX."""
import asyncio
import datetime
import json
import os

import aiohttp
from redbot.core import Config
from redbot.core import __version__ as redbot_version
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box

__author__ = "PhasecoreX"


class UpdateNotify(commands.Cog):
    """Get notifications when your bot needs updating."""

    default_global_settings = {"update_check_interval": 60}

    def __init__(self, bot):
        """Set up the plugin."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, 1224364860)
        self.config.register_global(**self.default_global_settings)
        self.notified_version = redbot_version
        self.task = self.bot.loop.create_task(self.check_for_updates())
        self.next_check = datetime.datetime.now()

    def __unload(self):
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

    async def update_check(self, manual: bool = False):
        """Check for all updates."""
        message = ""
        if manual:
            self.notified_version = redbot_version
        latest_redbot_version = await self.get_latest_redbot_version()
        if self.notified_version != latest_redbot_version:
            message = (
                "There is a newer version of Red-DiscordBot available!\n"
                "Your version: {}\nLatest version: {}\n\n"
            ).format(redbot_version, latest_redbot_version)
            if os.environ.get("PCX_DISCORDBOT"):
                message = message + (
                    "It looks like you're using the `phasecorex/red-discordbot` Docker image!\n"
                    "Simply issue the `[p]restart` command to have me "
                    "restart and update automatically."
                )
        elif manual:
            message = "You are already running the latest version ({})".format(
                self.notified_version
            )
        if message and not manual:
            message = "Hello!\n\n" + message
        self.notified_version = latest_redbot_version
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
