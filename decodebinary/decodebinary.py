"""DecodeBinary cog for Red-DiscordBot by PhasecoreX."""
import re

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import info

from .pcx_lib import SettingDisplay, checkmark, type_message

__author__ = "PhasecoreX"


class DecodeBinary(commands.Cog):
    """Decodes binary strings to human readable ones.

    The bot will check every message sent by users for binary and try to
    convert it to human readable text. You can check that it is working
    by sending this message in a channel:

    01011001011000010111100100100001
    """

    default_global_settings = {"schema_version": 0}
    default_guild_settings = {"ignored_channels": []}

    def __init__(self, bot):
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)

    async def initialize(self):
        """Perform setup actions before loading cog."""
        await self._migrate_config()

    async def _migrate_config(self):
        """Perform some configuration migrations."""
        if not await self.config.schema_version():
            # Remove "ignore_guild"
            guild_dict = await self.config.all_guilds()
            for guild_id in guild_dict:
                await self.config.guild_from_id(guild_id).clear_raw("ignore_guild")
            await self.config.schema_version.set(1)

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def decodebinaryset(self, ctx: commands.Context):
        """Change DecodeBinary settings."""
        pass

    @decodebinaryset.command()
    async def settings(self, ctx: commands.Context):
        """Display current settings."""
        ignored_channels = await self.config.guild(ctx.guild).ignored_channels()
        channel_section = SettingDisplay("Channel Settings")
        channel_section.add(
            "Enabled in this channel",
            "No" if ctx.message.channel.id in ignored_channels else "Yes",
        )
        await ctx.send(channel_section)

    @decodebinaryset.group()
    async def ignore(self, ctx: commands.Context):
        """Change DecodeBinary ignore settings."""
        pass

    @ignore.command()
    async def server(self, ctx: commands.Context):
        """Ignore/Unignore the current server."""
        await ctx.send(
            info(
                "Use the `[p]command enablecog` and `[p]command disablecog` to enable or disable this cog."
            )
        )

    @ignore.command()
    async def channel(self, ctx: commands.Context):
        """Ignore/Unignore the current channel."""
        async with self.config.guild(ctx.guild).ignored_channels() as ignored_channels:
            if ctx.channel.id in ignored_channels:
                ignored_channels.remove(ctx.channel.id)
                await ctx.send(checkmark("I will no longer ignore this channel."))
            else:
                ignored_channels.append(ctx.channel.id)
                await ctx.send(checkmark("I will ignore this channel."))

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        """Grab messages and see if we can decode them from binary."""
        if message.guild is None:
            return
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return
        if message.author.bot:
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
            await type_message(
                orig_message.channel,
                f'{orig_message.author.display_name}\'s message said:\n"{translated_messages[0]}"',
                allowed_mentions=discord.AllowedMentions(
                    everyone=False, users=False, roles=False
                ),
            )

        elif len(translated_messages) > 1:
            translated_counter = 0
            one_was_translated = False
            msg = f"{orig_message.author.display_name}'s {len(translated_messages)} messages said:"
            for translated_message in translated_messages:
                translated_counter += 1
                if translated_message:
                    one_was_translated = True
                    msg += f'\n{translated_counter}. "{translated_message}"'
                else:
                    msg += f"\n{translated_counter}. (Couldn't translate this one...)"
            if one_was_translated:
                await type_message(
                    orig_message.channel,
                    msg,
                    allowed_mentions=discord.AllowedMentions(
                        everyone=False, users=False, roles=False
                    ),
                )

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
