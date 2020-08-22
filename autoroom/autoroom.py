"""AutoRoom cog for Red-DiscordBot by PhasecoreX."""
import asyncio

import discord
from redbot.core import Config, checks, commands

from .pcx_lib import checkmark

__author__ = "PhasecoreX"


class AutoRoom(commands.Cog):
    """Automatic voice channel management."""

    default_global_settings = {"schema_version": 0}
    default_guild_settings = {
        "auto_voice_channels": {},
    }

    def __init__(self, bot):
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)
        self.autoroom_create_lock: asyncio.Lock = asyncio.Lock()

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def autoroomset(self, ctx: commands.Context):
        """Configure AutoRoom."""
        pass

    @autoroomset.command()
    async def create(
        self,
        ctx: commands.Context,
        source_voice_channel: discord.VoiceChannel,
        dest_category: discord.CategoryChannel,
    ):
        """Create an AutoRoom source.

        Anyone joining the `source_voice_channel` will automatically have a new voice channel
        (AutoRoom) created in the `dest_category`, and then be moved into it.
        """
        async with self.config.guild(ctx.message.guild).auto_voice_channels() as avcs:
            vc_id = str(source_voice_channel.id)
            avcs[vc_id] = {}
            avcs[vc_id]["dest_category_id"] = dest_category.id
            avcs[vc_id]["private"] = False
        await ctx.send(
            checkmark(
                "{} is now an AutoRoom source channel, and will create new voice channels in the {} category.".format(
                    source_voice_channel.mention, dest_category.mention,
                )
            )
        )

    @autoroomset.command()
    async def remove(
        self, ctx: commands.Context, source_voice_channel: discord.VoiceChannel,
    ):
        """Remove an AutoRoom source."""
        async with self.config.guild(ctx.message.guild).auto_voice_channels() as avcs:
            try:
                del avcs[str(source_voice_channel.id)]
            except KeyError:
                pass
        await ctx.send(
            checkmark(
                "{} is no longer an AutoRoom source channel.".format(
                    source_voice_channel.mention
                )
            )
        )

    @commands.group()
    @commands.guild_only()
    async def autoroom(self, ctx: commands.Context):
        """Manage your AutoRoom.

        This is still being worked on!
        """
        pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Do voice channel stuff when users move about channels."""
        if await self.bot.cog_disabled_in_guild(self, member.guild):
            return
        auto_voice_channels = await self.config.guild(
            member.guild
        ).auto_voice_channels()
        # If user left a voice channel that isn't an Autoroom source, do cleanup
        if not before.channel or str(before.channel.id) not in auto_voice_channels:
            await self._process_autoroom_delete(member.guild, auto_voice_channels)
        # If user entered an AutoRoom source channel, create new AutoRoom
        if after.channel and str(after.channel.id) in auto_voice_channels:
            await self._process_autoroom_create(member.guild, auto_voice_channels)

    async def _process_autoroom_create(self, guild, auto_voice_channels):
        """Create a voice channel for each member in an AutoRoom source channel."""
        if not guild.me.guild_permissions.manage_channels:
            return
        async with self.autoroom_create_lock:
            for avc_id, avc_settings in auto_voice_channels.items():
                members = guild.get_channel(int(avc_id)).members
                for member in members:
                    overwrites = {
                        guild.me: discord.PermissionOverwrite(
                            connect=True,
                            manage_channels=True,
                            move_members=True,
                            manage_roles=True,
                        ),
                        member: discord.PermissionOverwrite(
                            connect=True, manage_channels=True, move_members=True,
                        ),
                    }
                    if avc_settings["private"]:
                        overwrites[guild.default_role] = discord.PermissionOverwrite(
                            connect=False
                        )
                    new_channel_name = "{}'s Room".format(member.name)
                    new_channel = await member.guild.create_voice_channel(
                        name=new_channel_name,
                        category=guild.get_channel(avc_settings["dest_category_id"]),
                        reason="AutoRoom: New channel needed.",
                        overwrites=overwrites,
                    )
                    await member.move_to(
                        new_channel, reason="AutoRoom: Move user to new channel."
                    )
                    await asyncio.sleep(2)

    async def _process_autoroom_delete(self, guild, auto_voice_channels):
        """Delete all empty voice channels in categories."""
        if not guild.me.guild_permissions.manage_channels:
            return
        category_ids = set()
        for avc_id, avc_settings in auto_voice_channels.items():
            category_ids.add(avc_settings["dest_category_id"])
        for category_id in category_ids:
            for vc in guild.get_channel(category_id).voice_channels:
                if str(vc.id) not in auto_voice_channels and not vc.members:
                    await vc.delete(reason="AutoRoom: Channel empty.")
