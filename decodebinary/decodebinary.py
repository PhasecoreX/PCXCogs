"""DecodeBinary cog for Red-DiscordBot by PhasecoreX."""
import asyncio
import re

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import box

__author__ = "PhasecoreX"


class DecodeBinary(commands.Cog):
    """Decodes binary strings to human readable ones."""

    default_guild_settings = {"ignore_guild": False, "ignored_channels": []}

    def __init__(self, bot):
        """Set up the plugin."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1224364860)
        self.config.register_guild(**self.default_guild_settings)

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def decodebinaryignore(self, ctx: commands.Context):
        """Change DecodeBinary cog ignore settings."""
        if not ctx.invoked_subcommand:
            guild = ctx.message.guild
            ignore_guild = await self.config.guild(guild).ignore_guild()
            ignored_channels = await self.config.guild(guild).ignored_channels()
            ignore_channel = ctx.message.channel.id in ignored_channels

            msg = "Enabled on this server:  {}".format("No" if ignore_guild else "Yes")
            if not ignore_guild:
                msg += "\nEnabled in this channel: {}".format(
                    "No" if ignore_channel else "Yes"
                )
            await ctx.send(box(msg))

    @decodebinaryignore.command(name="server")
    async def _decodebinaryignore_server(self, ctx: commands.Context):
        """Ignore/Unignore the current server."""
        guild = ctx.message.guild
        if await self.config.guild(guild).ignore_guild():
            await self.config.guild(guild).ignore_guild.set(False)
            await ctx.send("I will no longer ignore this server.")
        else:
            await self.config.guild(guild).ignore_guild.set(True)
            await ctx.send("I will ignore this server.")

    @decodebinaryignore.command(name="channel")
    async def _decodebinaryignore_channel(self, ctx: commands.Context):
        """Ignore/Unignore the current channel."""
        channel = ctx.message.channel
        guild = ctx.message.guild
        ignored_channels = await self.config.guild(guild).ignored_channels()
        if channel.id in ignored_channels:
            ignored_channels.remove(channel.id)
            await ctx.send("I will no longer ignore this channel.")
        else:
            ignored_channels.append(channel.id)
            await ctx.send("I will ignore this channel.")
        await self.config.guild(guild).ignored_channels.set(ignored_channels)

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        """Grab messages and see if we can decode them from binary."""
        if message.guild is None:
            return
        if message.author.bot:
            return
        if await self.config.guild(message.guild).ignore_guild():
            return
        if (
            message.channel.id
            in await self.config.guild(message.guild).ignored_channels()
        ):
            return

        pattern = re.compile(r"[01]{7}[01 ]*[01]")
        found = pattern.findall(message.content)
        if found:
            await self.do_translation(message, found)

    async def do_translation(self, orig_message: discord.Message, found):
        """Translate each found string and sends a message."""
        translated_messages = []
        for encoded in found:
            translated_messages.append(self.decode_binary_string(encoded))

        if len(translated_messages) == 1 and translated_messages[0]:
            await self.send_message(
                orig_message.channel,
                '{}\'s message said:\n"{}"'.format(
                    orig_message.author.display_name, translated_messages[0]
                ),
            )

        elif len(translated_messages) > 1:
            translated_counter = 0
            one_was_translated = False
            msg = "{}'s {} messages said:".format(
                orig_message.author.display_name, len(translated_messages)
            )
            for translated_message in translated_messages:
                translated_counter += 1
                if translated_message:
                    one_was_translated = True
                    msg += '\n{}. "{}"'.format(translated_counter, translated_message)
                else:
                    msg += "\n{}. (Couldn't translate this one...)".format(
                        translated_counter
                    )
            if one_was_translated:
                await self.send_message(orig_message.channel, msg)

    async def send_message(self, channel: discord.TextChannel, message: str):
        """Send a message to a channel.

        Will send a typing indicator, and will wait a variable amount of time
        based on the length of the text (to simulate typing speed)
        """
        try:
            async with channel.typing():
                await asyncio.sleep(len(message) * 0.01)
                await self.bot.send_filtered(channel, content=message)
        except discord.errors.Forbidden:
            pass  # Not allowed to send messages in this channel

    @staticmethod
    def decode_binary_string(string: str):
        """Convert a string of 1's, 0's, and spaces into an ascii string."""
        string = string.replace(" ", "")
        if len(string) % 8 != 0:
            return ""
        result = "".join(
            chr(int(string[i * 8 : i * 8 + 8], 2)) for i in range(len(string) // 8)
        )
        if DecodeBinary.is_ascii(result):
            return result
        return ""

    @staticmethod
    def is_ascii(string: str):
        """Check if a string is fully ascii characters."""
        try:
            string.encode("ascii")
            return True
        except UnicodeEncodeError:
            return False
