"""
UpdateNotify cog for Red-DiscordBot by PhasecoreX
"""
import asyncio
import datetime
import json
import os
import urllib.request
from redbot.core import checks, Config, commands
from redbot.core.utils.chat_formatting import box
from redbot.core import __version__ as redbot_version

__author__ = "PhasecoreX"
BaseCog = getattr(commands, "Cog", object)


class UpdateNotify(BaseCog):
    """Get notifications when your bot needs updating."""

    default_global_settings = {"update_check_interval": 60}

    def __init__(self, bot):
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
            latest_version = self.update_check()
            self.notified_version = latest_version
            message = await self.generate_update_text(redbot_version, latest_version)
            await ctx.send(message)

    @staticmethod
    def update_check():
        """Checks PyPI for the latest update to Red-DiscordBot"""
        url = "https://pypi.org/pypi/Red-DiscordBot/json"
        data = json.load(urllib.request.urlopen(url))
        return data["info"]["version"]

    @staticmethod
    async def generate_update_text(old_version: str, new_version: str):
        """Generates the text that will be sent to the user."""
        if old_version != new_version:
            message = (
                "Hello!\n\n"
                "There is a newer version of Red-DiscordBot available!\n"
                "Your version: {}\nLatest version: {}\n\n"
            ).format(old_version, new_version)
            if os.environ.get("PCX_DISCORDBOT"):
                message = message + (
                    "It looks like you're using the `phasecorex/red-discordbot` Docker image!\n"
                    "Simply issue the `[p]restart` command to have me "
                    "restart and update automatically."
                )
        else:
            message = "You are already running the latest version ({})".format(
                new_version
            )
        return message.strip()

    async def notify_owner(self, old_version: str, new_version: str):
        """Notifies the owner of the bot that there is a new version available."""
        app_info = await self.bot.application_info()
        await app_info.owner.send(
            await self.generate_update_text(old_version, new_version)
        )

    async def check_for_updates(self):
        """Main loop that checks for updates and notifies the bot owner."""
        await self.bot.wait_until_ready()
        while self.bot.get_cog("UpdateNotify") == self:
            latest_version = self.update_check()
            if latest_version != self.notified_version:
                self.notified_version = latest_version
                await self.notify_owner(redbot_version, latest_version)
            seconds_to_sleep = await self.config.update_check_interval() * 60
            self.next_check = datetime.datetime.now() + datetime.timedelta(
                0, seconds_to_sleep
            )
            await asyncio.sleep(seconds_to_sleep)
