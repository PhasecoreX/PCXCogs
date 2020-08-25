"""AutoRoom cog for Red-DiscordBot by PhasecoreX."""
import asyncio

import discord
from redbot.core import Config, checks, commands

from .pcx_lib import checkmark, delete

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
        private: bool = False,
    ):
        """Create an AutoRoom source.

        Anyone joining the `source_voice_channel` will automatically have a new voice channel
        (AutoRoom) created in the `dest_category`, and then be moved into it.

        If `private` is true, the created channel will be private, where the user can modify
        the permissions of their channel to allow others in.
        """
        async with self.config.guild(ctx.message.guild).auto_voice_channels() as avcs:
            vc_id = str(source_voice_channel.id)
            avcs[vc_id] = {}
            avcs[vc_id]["dest_category_id"] = dest_category.id
            avcs[vc_id]["private"] = private
        await ctx.send(
            checkmark(
                "{} is now an AutoRoom source, and will create new {} voice channels in the {} category.".format(
                    source_voice_channel.mention,
                    "private" if private else "public",
                    dest_category.mention,
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
        """Manage your AutoRoom."""
        pass

    @autoroom.command()
    async def public(self, ctx: commands.Context):
        """Make your AutoRoom public."""
        await self._process_allow_deny(ctx, True)

    @autoroom.command()
    async def private(self, ctx: commands.Context):
        """Make your AutoRoom private."""
        await self._process_allow_deny(ctx, False)

    @autoroom.command(aliases=["add"])
    async def allow(self, ctx: commands.Context, member: discord.Member):
        """Allow a user into your AutoRoom."""
        await self._process_allow_deny(ctx, True, member=member)

    @autoroom.command(aliases=["ban"])
    async def deny(self, ctx: commands.Context, member: discord.Member):
        """Deny a user from accessing your AutoRoom.

        If they are already in your AutoRoom, they will be disconnected.
        """
        if await self._process_allow_deny(ctx, False, member=member):
            try:
                if member in ctx.message.author.voice.channel.members:
                    await member.move_to(None, reason="AutoRoom: Deny user")
            except AttributeError:
                pass
            except discord.Forbidden:
                pass  # Shouldn't happen unless someone screws with channel permissions.

    async def _process_allow_deny(
        self, ctx: commands.Context, allow: bool, *, member: discord.Member = None
    ) -> bool:
        """Actually do channel edit for allow/deny."""
        if not await self._is_autoroom_owner(ctx.message.author):
            await ctx.react_quietly("\N{NO ENTRY SIGN}")
            await delete(ctx.message, delay=3)
            return False
        try:
            channel = ctx.message.author.voice.channel
        except AttributeError:
            await ctx.react_quietly("\N{NO ENTRY SIGN}")
            await delete(ctx.message, delay=3)
            return False
        overwrites = dict(channel.overwrites)
        do_edit = False
        if not member:
            member = ctx.guild.default_role
        elif member in [ctx.guild.me, ctx.message.author]:
            await ctx.react_quietly("\N{NO ENTRY SIGN}")
            await delete(ctx.message, delay=3)
            return False
        if member in overwrites:
            if overwrites[member].connect != allow:
                overwrites[member].update(connect=allow)
                do_edit = True
        else:
            overwrites[member] = discord.PermissionOverwrite(connect=allow)
            do_edit = True
        if do_edit:
            await channel.edit(
                overwrites=overwrites, reason="AutoRoom: Permission change",
            )
        await ctx.tick()
        await delete(ctx.message, delay=3)
        return True

    async def _is_autoroom_owner(self, member: discord.Member):
        """Check if a member is the owner of an AutoRoom."""
        if not member.voice or not member.voice.channel:
            # Not in a voice channel
            return False
        if not member.voice.channel.permissions_for(member).manage_channels:
            # User doesn't have manage_channels permission, so can't possibly be channel owner
            return False
        # We need to look up if this channel is in any of the AutoRoom destination categories
        auto_voice_channels = await self.config.guild(
            member.guild
        ).auto_voice_channels()
        for avc_settings in auto_voice_channels.values():
            if member.voice.channel.category_id == avc_settings["dest_category_id"]:
                return True
        return False

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
                            manage_roles=True,
                            move_members=True,
                        ),
                        member: discord.PermissionOverwrite(
                            connect=True, manage_channels=True,
                        ),
                        guild.default_role: discord.PermissionOverwrite(
                            connect=not avc_settings["private"]
                        ),
                    }
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
