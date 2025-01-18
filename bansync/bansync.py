"""BanSync cog for Red-DiscordBot by PhasecoreX."""

import asyncio
import logging
from contextlib import suppress
from datetime import datetime
from typing import ClassVar, Literal

import discord
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import (
    bold,
    error,
    info,
    italics,
    question,
    success,
)
from redbot.core.utils.predicates import MessagePredicate

from .pcx_lib import SettingDisplay

log = logging.getLogger("red.pcxcogs.bansync")
SUPPORTED_SYNC_ACTIONS = Literal["ban", "timeout"]


class BanSync(commands.Cog):
    """Automatically sync moderation actions across servers.

    This cog allows server admins to have moderation actions
    automatically applied to members on their server when those
    actions are performed on another server that the bot is in.
    """

    __author__ = "PhasecoreX"
    __version__ = "2.0.0"

    default_global_settings: ClassVar[dict[str, int]] = {
        "schema_version": 0,
    }
    default_guild_settings: ClassVar[
        dict[str, str | dict[str, set[str]] | dict[str, dict[str, int]]]
    ] = {
        "cached_guild_name": "Unknown Server Name",
        "sync_sources": {},  # dict[str, list[str]]: source guild ID -> list of action types to pull
        "sync_destinations": {},  # dict[str, list[str]]: dest guild ID -> list of action types to push
        "sync_counts": {},  # dict[str, dict[str, int]]: source guild ID -> dict of action types and associated amounts
    }

    def __init__(self, bot: Red) -> None:
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)
        self.next_state: set[str] = set()
        self.debounce: dict[str, tuple[bool | datetime | None, int, bool]] = {}

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
        await self._update_sync_destinations()

    async def _migrate_config(self) -> None:
        """Perform some configuration migrations."""
        schema_version = await self.config.schema_version()

        if schema_version < 1:
            # Support multiple action types
            guild_dict = await self.config.all_guilds()
            for guild_id, guild_info in guild_dict.items():
                ban_sources = guild_info.get("ban_sources", [])
                if ban_sources:
                    sync_sources = {}
                    for ban_source in ban_sources:
                        sync_sources[ban_source] = ["ban"]
                    await self.config.guild_from_id(guild_id).sync_sources.set(
                        sync_sources
                    )
                    await self.config.guild_from_id(guild_id).clear_raw("ban_sources")
                ban_counts = guild_info.get("ban_count", {})
                if ban_counts:
                    sync_counts = {}
                    for pull_server_id, ban_count in ban_counts.items():
                        sync_counts[pull_server_id] = {"ban": ban_count}
                    await self.config.guild_from_id(guild_id).sync_counts.set(
                        sync_counts
                    )
                    await self.config.guild_from_id(guild_id).clear_raw("ban_count")
            await self.config.schema_version.set(1)

    async def _update_sync_destinations(self) -> None:
        """Update all guilds sync destinations to reflect which guilds are pulling from them (directed graph reversal)."""
        reversed_graph: dict[int, dict[str, list[str]]] = {}
        guild_dict = await self.config.all_guilds()
        for dest_guild_id, dest_guild_info in guild_dict.items():
            for source_guild_id, actions in dest_guild_info["sync_sources"].items():
                if source_guild_id not in reversed_graph:
                    reversed_graph[int(source_guild_id)] = {}
                reversed_graph[int(source_guild_id)][str(dest_guild_id)] = actions
        for source_guild_id in guild_dict:
            if source_guild_id in reversed_graph:
                await self.config.guild_from_id(source_guild_id).sync_destinations.set(
                    reversed_graph[source_guild_id]
                )
            else:
                await self.config.guild_from_id(
                    source_guild_id
                ).sync_destinations.clear()

    #
    # Command methods: bansync
    #

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def bansync(self, ctx: commands.Context) -> None:
        """Configure BanSync for this server."""

    @bansync.command(aliases=["info"])
    async def settings(self, ctx: commands.Context) -> None:
        """Display current settings."""
        if not ctx.guild:
            return

        check_ban_members = False
        check_moderate_members = False
        pull_servers = SettingDisplay()
        unknown_servers = []
        sync_counts = await self.config.guild(ctx.guild).sync_counts()
        sync_sources = await self.config.guild(ctx.guild).sync_sources()
        for source_guild_str, actions in sync_sources.items():
            count_info = ""
            if "ban" in actions:
                check_ban_members = True
                ban_count = sync_counts.get(source_guild_str, {}).get("ban", 0)
                count_info += f"{ban_count} ban{'' if ban_count == 1 else 's'}"
            if "timeout" in actions:
                check_moderate_members = True
                if count_info:
                    count_info += ", "
                timeout_count = sync_counts.get(source_guild_str, {}).get("timeout", 0)
                count_info += (
                    f"{timeout_count} timeout{'' if timeout_count == 1 else 's'}"
                )

            guild_source = self.bot.get_guild(int(source_guild_str))
            if guild_source:
                # Update their cached guild name
                await self.config.guild_from_id(
                    int(source_guild_str)
                ).cached_guild_name.set(guild_source.name)
                pull_servers.add(guild_source.name, count_info)
            else:
                unknown_servers.append(
                    f'`{source_guild_str}` - Last known as "{await self.config.guild_from_id(int(source_guild_str)).cached_guild_name()}", {count_info}'
                )

        info_text = ""

        if check_ban_members and not ctx.guild.me.guild_permissions.ban_members:
            info_text += error(
                "I do not have the Ban Members permission in this server!\nSyncing bans from other servers into this one will not work!\n\n"
            )
        if (
            check_moderate_members
            and not ctx.guild.me.guild_permissions.moderate_members
        ):
            info_text += error(
                "I do not have the Timeout Members permission in this server!\nSyncing timeouts from other servers into this one will not work!\n\n"
            )

        if not pull_servers:
            info_text += (
                info(bold("No servers are enabled for pulling!\n"))
                + "Use `[p]bansync enable` to add some.\n\n"
            )
        else:
            info_text += (
                ":down_arrow: "
                + bold("Pulling actions from these servers:")
                + "\n"
                + pull_servers.display()
                + "\n"
            )

        if unknown_servers:
            info_text += (
                error(bold("These servers are no longer available:"))
                + "\n"
                + italics("(I am not in them anymore)")
                + "\n"
                + "\n".join(unknown_servers)
                + "\n\n"
            )

        totals = {}
        for guild_pulls in sync_counts.values():
            for action, count in guild_pulls.items():
                if action not in totals:
                    totals[action] = 0
                totals[action] += count

        total_bans = totals.get("ban", 0)
        total_timeouts = totals.get("timeout", 0)
        info_text += italics(
            f"Pulled a total of {total_bans} ban{'' if total_bans == 1 else 's'} and {total_timeouts} timeout{'' if total_timeouts == 1 else 's'} from {len(sync_counts)} server{'' if len(sync_counts) == 1 else 's'} into this server."
        )

        await ctx.send(info_text)

    @bansync.command(aliases=["add", "pull"])
    async def enable(
        self,
        ctx: commands.Context,
        action: SUPPORTED_SYNC_ACTIONS,
        *,
        server: discord.Guild | str,
    ) -> None:
        """Enable pulling actions from a server."""
        if not ctx.guild:
            return
        if action == "ban" and not ctx.guild.me.guild_permissions.ban_members:
            await ctx.send(
                error(
                    "I do not have the Ban Members permission in this server! Syncing bans from other servers into this one will not work!"
                )
            )
            return
        if action == "timeout" and not ctx.guild.me.guild_permissions.moderate_members:
            await ctx.send(
                error(
                    "I do not have the Timeout Members permission in this server! Syncing timeouts from other servers into this one will not work!"
                )
            )
            return
        if isinstance(server, str):
            await ctx.send(
                error(
                    "I could not find that server. I can only pull actions from other servers that I am in."
                )
            )
            return
        if server == ctx.guild:
            await ctx.send(
                error("You can only pull actions in from other servers, not this one.")
            )
            return
        pull_server_str = str(server.id)
        plural_actions = self.get_plural_actions(action)
        sync_sources = await self.config.guild(ctx.guild).sync_sources()
        if pull_server_str in sync_sources and action in sync_sources[pull_server_str]:
            # Update our and their cached guild name
            await self.config.guild(ctx.guild).cached_guild_name.set(ctx.guild.name)
            await self.config.guild_from_id(server.id).cached_guild_name.set(
                server.name
            )
            await ctx.send(
                success(
                    f"We are already pulling {plural_actions} from {server.name} into this server."
                )
            )
            return

        # You really want to do this?
        pred = MessagePredicate.yes_or_no(ctx)
        await ctx.send(
            question(
                f'Are you **sure** you want to pull new {plural_actions} from the server "{server.name}" into this server? (yes/no)\n\n'
                f"Be sure to only do this for servers that you trust, as all {plural_actions} that occur there will be mirrored into this server."
            )
        )
        with suppress(asyncio.TimeoutError):
            await ctx.bot.wait_for("message", check=pred, timeout=30)
        if pred.result:
            pass
        else:
            await ctx.send(info("Cancelled adding server as an action source."))
            return

        # Update our and their cached guild name
        await self.config.guild(ctx.guild).cached_guild_name.set(ctx.guild.name)
        await self.config.guild_from_id(server.id).cached_guild_name.set(server.name)
        # Add their server to our pull list and save
        if pull_server_str not in sync_sources:
            sync_sources[pull_server_str] = []
        if action not in sync_sources[pull_server_str]:
            sync_sources[pull_server_str].append(action)
            await self.config.guild(ctx.guild).sync_sources.set(sync_sources)
        # Add our server to their push list and save
        sync_destinations = await self.config.guild_from_id(
            server.id
        ).sync_destinations()
        push_server_str = str(ctx.guild.id)
        if push_server_str not in sync_destinations:
            sync_destinations[push_server_str] = []
        if action not in sync_destinations[push_server_str]:
            sync_destinations[push_server_str].append(action)
            await self.config.guild_from_id(server.id).sync_destinations.set(
                sync_destinations
            )
        # Return
        await ctx.send(
            success(
                f'New {plural_actions} from "{server.name}" will now be pulled into this server.'
            )
        )

    @bansync.command(aliases=["remove", "del", "delete"])
    async def disable(
        self,
        ctx: commands.Context,
        action: SUPPORTED_SYNC_ACTIONS,
        *,
        server: discord.Guild | str,
    ) -> None:
        """Disable pulling actions from a server."""
        if not ctx.guild:
            return
        server_id: str | None = None
        sync_sources = await self.config.guild(ctx.guild).sync_sources()

        if isinstance(server, discord.Guild):
            # Given arg was converted to a guild, nice!
            server_id = str(server.id)
        elif server in sync_sources:
            server_id = server
        else:
            # Given arg was the name of a guild (str), or an ID not in the sync source list (str)
            # (could be a guild with a name of just numbers?)
            all_guild_dict = await self.config.all_guilds()
            for dest_guild_id, dest_guild_settings in all_guild_dict.items():
                if dest_guild_settings.get("cached_guild_name") == server:
                    server_id = str(dest_guild_id)
                    break

        plural_actions = self.get_plural_actions(action)
        if not server_id:
            await ctx.send(error("I could not find that server."))
        elif server_id in sync_sources and action in sync_sources[server_id]:
            # Remove their server from our pull list and save
            sync_sources[server_id] = [
                item for item in sync_sources[server_id] if item != action
            ]
            if not sync_sources[server_id]:
                del sync_sources[server_id]
            await self.config.guild(ctx.guild).sync_sources.set(sync_sources)
            # Remove our server from their push list and save
            sync_destinations = await self.config.guild_from_id(
                int(server_id)
            ).sync_destinations()
            push_server_str = str(ctx.guild.id)
            if push_server_str in sync_destinations:
                sync_destinations[push_server_str] = [
                    item
                    for item in sync_destinations[push_server_str]
                    if item != action
                ]
                if not sync_destinations[push_server_str]:
                    del sync_destinations[push_server_str]
                await self.config.guild_from_id(int(server_id)).sync_destinations.set(
                    sync_destinations
                )
            await ctx.send(
                success(
                    f"New {plural_actions} will no longer be pulled from that server."
                )
            )
        else:
            await ctx.send(
                info(
                    f"It doesn't seem like we were pulling {plural_actions} from that server in the first place."
                )
            )

    #
    # Listener methods
    #

    @commands.Cog.listener()
    async def on_member_ban(
        self, source_guild: discord.Guild, user: discord.Member | discord.User
    ) -> None:
        """When a user is banned, propogate that ban to other servers that are subscribed."""
        await self._handle_action(source_guild, user, "ban", data=True)

    @commands.Cog.listener()
    async def on_member_unban(
        self, source_guild: discord.Guild, user: discord.User
    ) -> None:
        """When a user is unbanned, propogate that unban to other servers that are subscribed."""
        await self._handle_action(source_guild, user, "ban", data=False)

    @commands.Cog.listener()
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        """When a user is timed out, propogate that timeout to other servers that are subscribed."""
        if after.timed_out_until and after.timed_out_until != before.timed_out_until:
            await self._handle_action(
                after.guild, after, "timeout", data=after.timed_out_until
            )
        elif not after.timed_out_until and before.timed_out_until:
            await self._handle_action(after.guild, after, "timeout", data=None)

    #
    # Private methods
    #

    async def _handle_action(
        self,
        guild: discord.Guild,
        user: discord.Member | discord.User,
        action: SUPPORTED_SYNC_ACTIONS,
        *,
        data: bool | datetime | None,
    ) -> None:
        # Update our cached guild name
        await self.config.guild(guild).cached_guild_name.set(guild.name)

        # Generate keys
        key = f"{guild.id}-{user.id}-{action}"
        next_state_key = f"{key}-{data}"

        # If this action was caused by this cog, do nothing
        # The propogation was calculated and handled by the initial guild event
        if next_state_key in self.next_state:
            log.debug("%s: Caught already propogated event, ignoring", next_state_key)
            self.next_state.remove(next_state_key)
            return

        # Debounce event action, to handle quick opposing actions (e.g. softban quickly banning and unbanning a user)
        if key not in self.debounce:
            self.debounce[key] = (data, 0, False)
        if not self.debounce[key][2] or bool(self.debounce[key][0]) == bool(data):
            log.debug("%s: New event, waiting for any cancelation events...", key)
            our_number = self.debounce[key][1] + 1
            self.debounce[key] = (data, our_number, True)
            await asyncio.sleep(2)
            if self.debounce[key] != (data, our_number, True):
                log.debug("%s: We were canceled...", key)
                if not self.debounce[key][2]:
                    log.debug("%s: ...and nothing else follows, so cleaning up", key)
                    del self.debounce[key]
                return
        else:
            log.debug(
                "%s: Canceling previous sleeping %s action", key, self.debounce[key]
            )
            self.debounce[key] = (data, self.debounce[key][1], False)
            return
        del self.debounce[key]
        log.debug("%s: Begin the propogation!", key)

        async with self.config.user(user).get_lock():
            guilds_to_process: list[int] = [guild.id]
            i = -1
            while i + 1 < len(guilds_to_process):
                i += 1
                source_guild = self.bot.get_guild(guilds_to_process[i])
                if not source_guild:
                    continue
                log.debug("%s: Processing guild #%d: %s", key, i + 1, source_guild.name)
                sync_destinations = await self.config.guild(
                    source_guild
                ).sync_destinations()
                for dest_guild_str, sync_actions in sync_destinations.items():
                    if int(dest_guild_str) in guilds_to_process:
                        continue
                    if action not in sync_actions:
                        continue
                    dest_guild = self.bot.get_guild(int(dest_guild_str))
                    if not dest_guild or dest_guild.unavailable:
                        continue

                    log.debug("%s: Sending %s to %s", key, action, dest_guild.name)
                    dest_key = f"{dest_guild.id}-{user.id}-{action}-{data}"
                    reason = f'BanSync from server "{source_guild.name}"'
                    self.next_state.add(dest_key)
                    try:
                        if action == "ban":
                            if not dest_guild.me.guild_permissions.ban_members:
                                raise PermissionError  # noqa: TRY301
                            if data:
                                await dest_guild.ban(user, reason=reason)
                            else:
                                await dest_guild.unban(user, reason=reason)
                        elif action == "timeout":
                            if not dest_guild.me.guild_permissions.moderate_members:
                                raise PermissionError  # noqa: TRY301
                            member = dest_guild.get_member(user.id)
                            if not member:
                                raise PermissionError  # noqa: TRY301
                            if isinstance(data, datetime):
                                await member.timeout(data, reason=reason)
                            else:
                                await member.timeout(None, reason=reason)

                        if data:
                            async with self.config.guild(
                                dest_guild
                            ).sync_counts() as sync_counts:
                                source_guild_str = str(source_guild.id)
                                if source_guild_str not in sync_counts:
                                    sync_counts[source_guild_str] = {}
                                if action not in sync_counts[source_guild_str]:
                                    sync_counts[source_guild_str][action] = 0
                                sync_counts[source_guild_str][action] += 1

                        guilds_to_process.append(int(dest_guild_str))
                        log.debug(
                            "%s: Successfully sent, adding %s to propogation list",
                            key,
                            dest_guild.name,
                        )
                    except (
                        discord.NotFound,
                        discord.Forbidden,
                        discord.HTTPException,
                        PermissionError,
                    ):
                        self.next_state.remove(dest_key)

    def get_plural_actions(self, action: SUPPORTED_SYNC_ACTIONS) -> str:
        """Get the plural of an action, for displaying to the user."""
        plural_actions = f"{action}s"
        if action == "ban":
            plural_actions = "bans and unbans"
        return plural_actions

    #
    # Public methods
    #
