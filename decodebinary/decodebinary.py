"""DecodeBinary cog for Red-DiscordBot by PhasecoreX."""

import re
from typing import ClassVar

import discord
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import info, success

from .pcx_lib import SettingDisplay, type_message


class DecodeBinary(commands.Cog):
    """Decodes binary strings to human-readable ones.

    The bot will check every message sent by users for binary and try to
    convert it to human-readable text. You can check that it is working
    by sending this message in a channel:

    01011001011000010111100100100001
    """

    __author__ = "PhasecoreX"
    __version__ = "1.2.1"

    default_global_settings: ClassVar[dict[str, int]] = {"schema_version": 0}
    default_guild_settings: ClassVar[dict[str, list[int]]] = {"ignored_channels": []}

    def __init__(self, bot: Red) -> None:
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)

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
    # Initialization methods
    #

    async def initialize(self) -> None:
        """Perform setup actions before loading cog."""
        await self._migrate_config()

    async def _migrate_config(self) -> None:
        """Perform some configuration migrations."""
        schema_version = await self.config.schema_version()

        if schema_version < 1:
            # Remove "ignore_guild"
            guild_dict = await self.config.all_guilds()
            for guild_id in guild_dict:
                await self.config.guild_from_id(guild_id).clear_raw("ignore_guild")
            await self.config.schema_version.set(1)

    #
    # Command methods: decodebinaryset
    #

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def decodebinaryset(self, ctx: commands.Context) -> None:
        """Change DecodeBinary settings."""

    @decodebinaryset.command()
    async def settings(self, ctx: commands.Context) -> None:
        """Display current settings."""
        if not ctx.guild:
            return
        ignored_channels = await self.config.guild(ctx.guild).ignored_channels()
        channel_section = SettingDisplay("Channel Settings")
        channel_section.add(
            "Enabled in this channel",
            "No" if ctx.message.channel.id in ignored_channels else "Yes",
        )
        await ctx.send(str(channel_section))

    @decodebinaryset.group()
    async def ignore(self, ctx: commands.Context) -> None:
        """Change DecodeBinary ignore settings."""

    @ignore.command()
    async def server(self, ctx: commands.Context) -> None:
        """Ignore/Unignore the current server."""
        await ctx.send(
            info(
                "Use the `[p]command enablecog` and `[p]command disablecog` to enable or disable this cog."
            )
        )

    @ignore.command()
    async def channel(self, ctx: commands.Context) -> None:
        """Ignore/Unignore the current channel."""
        if not ctx.guild:
            return
        async with self.config.guild(ctx.guild).ignored_channels() as ignored_channels:
            if ctx.channel.id in ignored_channels:
                ignored_channels.remove(ctx.channel.id)
                await ctx.send(success("I will no longer ignore this channel."))
            else:
                ignored_channels.append(ctx.channel.id)
                await ctx.send(success("I will ignore this channel."))

    #
    # Listener methods
    #

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message) -> None:
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

    #
    # Public methods
    #

    async def do_translation(
        self, orig_message: discord.Message, found: list[str]
    ) -> None:
        """Translate each found string and sends a message."""
        translated_messages = [self.decode_binary_string(encoded) for encoded in found]

        if len(translated_messages) == 1 and translated_messages[0]:
            await type_message(
                orig_message.channel,
                f'{orig_message.author.display_name}\'s message said:\n"{translated_messages[0]}"',
                allowed_mentions=discord.AllowedMentions(
                    everyone=False, users=False, roles=False
                ),
            )

        elif len(translated_messages) > 1:
            one_was_translated = False
            msg = f"{orig_message.author.display_name}'s {len(translated_messages)} messages said:"
            for translated_counter, translated_message in enumerate(
                translated_messages
            ):
                if translated_message:
                    one_was_translated = True
                    msg += f'\n{translated_counter + 1}. "{translated_message}"'
                else:
                    msg += (
                        f"\n{translated_counter + 1}. (Couldn't translate this one...)"
                    )
            if one_was_translated:
                await type_message(
                    orig_message.channel,
                    msg,
                    allowed_mentions=discord.AllowedMentions(
                        everyone=False, users=False, roles=False
                    ),
                )

    @staticmethod
    def decode_binary_string(string: str) -> str:
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
    def is_ascii(string: str) -> bool:
        """Check if a string is fully ascii characters."""
        try:
            string.encode("ascii")
        except UnicodeEncodeError:
            return False
        else:
            return True
