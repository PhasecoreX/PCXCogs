"""NetSpeed cog for Red-DiscordBot by PhasecoreX."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import discord
import speedtest
from redbot.core import checks, commands


class NetSpeed(commands.Cog):
    """Test the internet speed of the server your bot is hosted on."""

    __author__ = "PhasecoreX"
    __version__ = "1.1.0"

    #
    # Red methods
    #

    def format_help_for_context(self, ctx: commands.Context) -> str:
        """Show version in help."""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\nCog Version: {self.__version__}"

    async def red_delete_data_for_user(self, *, _requester: str, _user_id: int) -> None:
        """Nothing to delete."""
        return

    #
    # Command methods: netspeed
    #

    @commands.command(aliases=["speedtest"])
    @checks.is_owner()
    async def netspeed(self, ctx: commands.Context) -> None:
        """Test the internet speed of the server your bot is hosted on."""
        loop = asyncio.get_event_loop()
        speed_test = speedtest.Speedtest(secure=True)
        the_embed = await ctx.send(embed=self.generate_embed(speed_test.results.dict()))
        with ThreadPoolExecutor(max_workers=1) as executor:
            await loop.run_in_executor(executor, speed_test.get_servers)
            await loop.run_in_executor(executor, speed_test.get_best_server)
            await the_embed.edit(embed=self.generate_embed(speed_test.results.dict()))
            await loop.run_in_executor(executor, speed_test.download)
            await the_embed.edit(embed=self.generate_embed(speed_test.results.dict()))
            await loop.run_in_executor(executor, speed_test.upload)
            await the_embed.edit(embed=self.generate_embed(speed_test.results.dict()))

    @staticmethod
    def generate_embed(results_dict: dict[str, Any]) -> discord.Embed:
        """Generate the embed."""
        measuring = ":mag: Measuring..."
        waiting = ":hourglass: Waiting..."

        color = discord.Color.red()
        title = "Measuring internet speed..."
        message_ping = measuring
        message_down = waiting
        message_up = waiting
        if results_dict["ping"]:
            message_ping = f"**{results_dict['ping']}** ms"
            message_down = measuring
        if results_dict["download"]:
            message_down = f"**{results_dict['download'] / 1_000_000:.2f}** mbps"
            message_up = measuring
        if results_dict["upload"]:
            message_up = f"**{results_dict['upload'] / 1_000_000:.2f}** mbps"
            title = "NetSpeed Results"
            color = discord.Color.green()
        embed = discord.Embed(title=title, color=color)
        embed.add_field(name="Ping", value=message_ping)
        embed.add_field(name="Download", value=message_down)
        embed.add_field(name="Upload", value=message_up)
        return embed
