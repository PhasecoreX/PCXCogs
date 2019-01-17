"""
Decode binary cog for Redbot by PhasecoreX
"""
import re
import time

__version__ = "0.1.0"
__author__ = "PhasecoreX"

from redbot.core import checks, Config, commands

GUILD_SETTINGS = {
    "ignore_guild": False,
    "ignored_channels": []
}

BaseCog = getattr(commands, "Cog", object)


class DecodeBinary(BaseCog):
    """Decodes binary strings to human readable ones"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1224364860)
        self.config.register_guild(**GUILD_SETTINGS)

    @commands.group(name="decodebinaryignore", pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def decodebinaryignore(self, ctx):
        """Change DecodeBinary cog ignore settings."""

    @decodebinaryignore.command(name="server", pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _decodebinaryignore_server(self, ctx):
        """Ignore/Unignore the current server"""

        guild = ctx.message.guild
        if await self.config.guild(guild).ignore_guild():
            await self.config.guild(guild).ignore_guild.set(False)
            await ctx.send("I will no longer ignore this server.")
        else:
            await self.config.guild(guild).ignore_guild.set(True)
            await ctx.send("I will ignore this server.")

    @decodebinaryignore.command(name="channel", pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _decodebinaryignore_channel(self, ctx):
        """Ignore/Unignore the current channel"""

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

    # Come up with a new method to ignore bot commands
    async def on_message(self, message):
        """Grab messages and see if we can decode them from binary"""
        if message.guild is None:
            return
        if message.author.bot:
            return
        # if self.is_command(message):
        #     return
        if await self.config.guild(message.guild).ignore_guild():
            return
        if message.channel.id in await self.config.guild(message.guild).ignored_channels():
            return

        pattern = re.compile(r'[01][01 ]*[01]')
        found = pattern.findall(message.content)
        if found:
            await self.do_translation(message, found)

    async def do_translation(self, orig_message, found):
        """Translates each found string and sends a message"""
        translated_messages = []
        for encoded in found:
            encoded = encoded.replace(' ', '')
            if len(encoded) < 8:
                continue
            translated_messages.append(self.decode_binary_string(encoded))

        if len(translated_messages) == 1:
            if translated_messages[0]:
                msg = "{}'s message said:\n\"{}\"".format(
                    orig_message.author.display_name, translated_messages[0])
            else:
                msg = "Hmm... That doesn't look like valid binary..."
            await self.send_message(orig_message.channel, msg)

        elif len(translated_messages) > 1:
            translated_counter = 0
            one_was_translated = False
            msg = "{}'s {} messages said:".format(
                orig_message.author.display_name, len(translated_messages))
            for translated_message in translated_messages:
                translated_counter += 1
                if translated_message:
                    one_was_translated = True
                    msg += "\n{}. \"{}\"".format(translated_counter, translated_message)
                else:
                    msg += "\n{}. (Couldn't translate this one...)".format(translated_counter)
            if not one_was_translated:
                msg = "Hmm... None of that looks like valid binary..."
            await self.send_message(orig_message.channel, msg)

    @staticmethod
    async def send_message(channel, message):
        """Sends a message to a channel.

        Will send a typing indicator, and will wait a variable amount of time
        based on the length of the text (to simulate typing speed)
        """
        async with channel.typing():
            time.sleep(len(message) * 0.01)
            await channel.send(message)

    @staticmethod
    def decode_binary_string(string):
        """Converts a string of 1's and 0's into an ascii string"""
        if len(string) % 8 != 0:
            return ''
        result = ''.join(chr(int(string[i * 8:i * 8 + 8], 2)) for i in range(len(string) // 8))
        if DecodeBinary.is_ascii(result):
            return result
        return ''

    @staticmethod
    def is_ascii(string):
        """Checks if a string is fully ascii characters"""
        try:
            string.encode('ascii')
            return True
        except UnicodeEncodeError:
            return False
