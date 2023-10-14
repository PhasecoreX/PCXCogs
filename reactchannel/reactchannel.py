"""ReactChannel cog for Red-DiscordBot by PhasecoreX."""
import datetime
from contextlib import suppress
from typing import ClassVar

import discord
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.utils import AsyncIter
from redbot.core.utils.chat_formatting import box, error, pagify, success, warning

from .pcx_lib import delete

KARMATOP_LIMIT = 10


class ReactChannel(commands.Cog):
    """Per-channel auto reaction tools.

    Admins can set up certain channels to be ReactChannels, where each message in it
    will automatically have reactions applied. Depending on the type of ReactChannel,
    click these reactions could trigger automatic actions.

    Additionally, Admins can set up server-wide upvote and/or downvote emojis, where
    reacting to messages with these (in any channel) will increase or decrease the
    message owners total karma.
    """

    __author__ = "PhasecoreX"
    __version__ = "3.1.2"

    default_global_settings: ClassVar[dict[str, int]] = {"schema_version": 0}
    default_guild_settings: ClassVar[dict[str, dict[str, str | int | None]]] = {
        "emojis": {"upvote": None, "downvote": None},
    }
    default_react_channel_settings: ClassVar[dict] = {
        "reaction_template": None,  # Can be "vote", "checklist", or a list of ("emoji", "action") tuples.
        "react_to": {
            "users": True,
            "bots": False,
            "myself": False,
        },
        "react_roles": [],
        "react_roles_allow": True,
        "react_filter": {
            "text": True,
            "commands": False,
            "images": True,
        },
    }
    default_member_settings: ClassVar[dict[str, int]] = {"karma": 0, "created_at": 0}

    def __init__(self, bot: Red) -> None:
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)
        self.config.init_custom("REACT_CHANNEL", 2)
        self.config.register_custom(
            "REACT_CHANNEL", **self.default_react_channel_settings
        )
        self.config.register_member(**self.default_member_settings)
        self.emoji_cache = {}

    #
    # Red methods
    #

    def format_help_for_context(self, ctx: commands.Context) -> str:
        """Show version in help."""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\nCog Version: {self.__version__}"

    async def red_delete_data_for_user(self, *, _requester: str, user_id: int) -> None:
        """Users can reset their karma back to zero I guess."""
        all_members = await self.config.all_members()
        async for guild_id, member_dict in AsyncIter(all_members.items(), steps=100):
            if user_id in member_dict:
                await self.config.member_from_ids(guild_id, user_id).clear()

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
            # If guild had a vote channel, set up default upvote and downvote emojis
            guild_dict = await self.config.all_guilds()
            for guild_id, guild_info in guild_dict.items():
                channels = guild_info.get("channels", {})
                if channels:
                    for channel_type in channels.values():
                        if channel_type == "vote":
                            emoji_group = self.config.guild_from_id(guild_id).emojis
                            if isinstance(emoji_group, commands.Group):
                                await emoji_group.upvote.set(
                                    guild_info.get("upvote", "\ud83d\udd3c")
                                )
                                await emoji_group.downvote.set(
                                    guild_info.get("downvote", "\ud83d\udd3d")
                                )
                                break
                await self.config.guild_from_id(guild_id).clear_raw("upvote")
                await self.config.guild_from_id(guild_id).clear_raw("downvote")
            await self.config.clear_raw("version")
            await self.config.schema_version.set(1)

        if schema_version < 2:  # noqa: PLR2004
            # Migrate to REACT_CHANNEL custom config group
            guild_dict = await self.config.all_guilds()
            for guild_id in guild_dict:
                channels = await self.config.guild_from_id(guild_id).get_raw(
                    "channels", default={}
                )
                for channel_id, channel_type in channels.items():
                    await self.config.custom(
                        "REACT_CHANNEL", guild_id, channel_id
                    ).set_raw(
                        value={
                            "channel_type": channel_type,
                            "ignore_bots": channel_type == "vote",
                        }
                    )
                await self.config.guild_from_id(guild_id).clear_raw("channels")
            await self.config.schema_version.set(2)

        if schema_version < 3:  # noqa: PLR2004
            # Migrate to new react filters
            all_react_channels = await self.config.custom("REACT_CHANNEL").all()
            for guild_id, guild_react_channels in all_react_channels.items():
                for (
                    channel_id,
                    react_channel_config,
                ) in guild_react_channels.items():
                    channel_type = react_channel_config["channel_type"]
                    if channel_type in ("vote", "checklist"):
                        await self.config.custom(
                            "REACT_CHANNEL", guild_id, channel_id
                        ).reaction_template.set(channel_type)
                        if (
                            channel_type == "checklist"
                            and "ignore_bots" in react_channel_config
                            and not react_channel_config["ignore_bots"]
                        ):
                            await self.config.custom(
                                "REACT_CHANNEL", guild_id, channel_id
                            ).react_to.bots.set(
                                True  # noqa: FBT003
                            )
                    elif isinstance(channel_type, list):
                        emoji_tuple_list = [(emoji, None) for emoji in channel_type]
                        if emoji_tuple_list:
                            await self.config.custom(
                                "REACT_CHANNEL", guild_id, channel_id
                            ).reaction_template.set(emoji_tuple_list)
                    await self.config.custom(
                        "REACT_CHANNEL", guild_id, channel_id
                    ).clear_raw("channel_type")
                    await self.config.custom(
                        "REACT_CHANNEL", guild_id, channel_id
                    ).clear_raw("ignore_bots")
            await self.config.schema_version.set(3)

        if schema_version < 4:  # noqa: PLR2004
            # Add "myself" react to option
            all_react_channels = await self.config.custom("REACT_CHANNEL").all()
            for guild_id, guild_react_channels in all_react_channels.items():
                for (
                    channel_id,
                    react_channel_config,
                ) in guild_react_channels.items():
                    if (
                        "react_to" in react_channel_config
                        and "bots" in react_channel_config["react_to"]
                    ):
                        await self.config.custom(
                            "REACT_CHANNEL", guild_id, channel_id
                        ).react_to.myself.set(react_channel_config["react_to"]["bots"])
            await self.config.schema_version.set(4)

    #
    # Command methods: reactchannelset
    #

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def reactchannelset(self, ctx: commands.Context) -> None:
        """Manage ReactChannel settings."""

    @reactchannelset.command()
    async def settings(self, ctx: commands.Context) -> None:
        """Display current settings."""
        if not ctx.guild:
            return
        message = ""
        channels = await self.config.custom(
            "REACT_CHANNEL", str(ctx.guild.id)
        ).all()  # Does NOT return default values
        for channel_id in channels:
            channel = ctx.guild.get_channel(int(channel_id))
            if not channel:
                await self.config.custom(
                    "REACT_CHANNEL", str(ctx.guild.id), channel_id
                ).clear()
                continue
            channel_settings = await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).all()  # Does return default values
            reaction_template = channel_settings["reaction_template"]
            emojis = "???"
            if reaction_template == "checklist":
                emojis = "\N{WHITE HEAVY CHECK MARK}"
            elif reaction_template == "vote":
                emojis = ""
                upvote = await self._get_emoji(ctx.guild, "upvote")
                downvote = await self._get_emoji(ctx.guild, "downvote")
                if upvote:
                    emojis += str(upvote)
                if downvote:
                    if emojis:
                        emojis += " "
                    emojis += str(downvote)
                if not emojis:
                    emojis = "(disabled, see `[p]reactchannelset emoji`)"
            elif isinstance(channel_settings["reaction_template"], list):
                emojis = ""
                for emoji_tuple in channel_settings["reaction_template"]:
                    emojis += f" {emoji_tuple[0]}"
                reaction_template = "custom"
            message += (
                f"\n{channel.mention}: {reaction_template.capitalize()} - {emojis}"
            )
            # react_to
            sources = []
            for source, enabled in channel_settings["react_to"].items():
                if enabled:
                    if source == "myself":
                        sources.append(f"Myself ({ctx.guild.me.display_name})")
                    elif source == "bots":
                        sources.append("Other Bots")
                    else:
                        sources.append(f"{source.capitalize()}")
            if sources:
                message += f"\nSources: {', '.join(sources)}"
            else:
                message += "\nSources: None"
            # react_roles
            roles_list = self._list_roles(ctx.guild, channel_settings["react_roles"])
            if roles_list:
                if channel_settings["react_roles_allow"]:
                    message += f"\nOnly Roles: \n{roles_list}"
                else:
                    message += f"\nIgnoring Roles: \n{roles_list}"
            # react_filter
            filters = [
                r_filter.capitalize()
                for r_filter, enabled in channel_settings["react_filter"].items()
                if enabled
            ]
            if filters:
                message += f"\nContent: {', '.join(filters)}"
            else:
                message += "\nContent: None"
            message += "\n"
        if not message:
            message = " None"
        message = "**ReactChannels configured:**\n" + message
        for page in pagify(message, ["\n\n", "\n"], priority=True):
            await ctx.send(page)

    @reactchannelset.group()
    async def enable(self, ctx: commands.Context) -> None:
        """Enable ReactChannel functionality in a channel."""

    @enable.command()
    async def checklist(
        self, ctx: commands.Context, channel: discord.TextChannel | None = None
    ) -> None:
        """All messages will have a checkmark. Clicking it will delete the message."""
        await self._save_channel(ctx, channel, "checklist")

    @enable.command()
    async def vote(
        self, ctx: commands.Context, channel: discord.TextChannel | None = None
    ) -> None:
        """All user messages will have an up and down arrow. Clicking them will affect a user's karma total."""
        await self._save_channel(ctx, channel, "vote")

    @enable.command()
    async def custom(self, ctx: commands.Context, *, emojis: str) -> None:
        """All messages will have the specified emoji(s).

        When specifying multiple, make sure there's a space between each emoji.
        """
        await self._save_channel(ctx, None, list(dict.fromkeys(emojis.split())))

    async def _save_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None,
        reaction_template: str | list,
    ) -> None:
        """Actually save the ReactChannel settings."""
        if channel is None:
            if isinstance(ctx.message.channel, discord.TextChannel):
                channel = ctx.message.channel
            else:
                return
        if isinstance(reaction_template, list):
            emoji_tuple_list = []
            try:
                for emoji in reaction_template:
                    await ctx.message.add_reaction(emoji)
                for emoji in reaction_template:
                    await ctx.message.remove_reaction(emoji, channel.guild.me)
                    emoji_tuple_list.append((emoji, None))
            except discord.HTTPException:
                await ctx.send(
                    error(
                        f"{'That' if len(reaction_template) == 1 else 'One of those emojis'} is not a valid emoji I can use!"
                    )
                )
                return
            await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).reaction_template.set(emoji_tuple_list)

        else:
            await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).reaction_template.set(reaction_template)
            # Make sure we don't react to bots
            if reaction_template == "vote":
                await self.config.custom(
                    "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
                ).react_to.bots.clear()

        custom_emojis = ""
        if isinstance(reaction_template, list):
            custom_emojis = f" ({', '.join(reaction_template)})"
            reaction_template = "custom"
        await ctx.send(
            success(
                f"{channel.mention} is now a {reaction_template} ReactChannel.{custom_emojis}"
            )
        )
        if (
            reaction_template == "vote"
            and not await self._get_emoji(channel.guild, "upvote")
            and not await self._get_emoji(channel.guild, "downvote")
        ):
            await ctx.send(
                warning(
                    "You do not have an upvote or downvote emoji set for this server. "
                    "You will need at least one set in order for this ReactChannel to work. "
                    "Check `[p]reactchannelset emoji` for more information."
                )
            )

    @reactchannelset.command()
    async def disable(
        self, ctx: commands.Context, channel: discord.TextChannel | None = None
    ) -> None:
        """Disable ReactChannel functionality in a channel."""
        if channel is None:
            if isinstance(ctx.message.channel, discord.TextChannel):
                channel = ctx.message.channel
            else:
                return

        await self.config.custom(
            "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
        ).clear()
        await ctx.send(
            success(
                f"ReactChannel functionality has been disabled on {channel.mention}."
            )
        )

    @reactchannelset.group(name="filter")
    async def set_filter(self, ctx: commands.Context) -> None:
        """Only react to certain messages in a ReactChannel."""

    @set_filter.group()
    async def source(self, ctx: commands.Context) -> None:
        """Control who is reacted to."""

    @source.command(aliases=["user"])
    async def users(
        self, ctx: commands.Context, channel: discord.TextChannel | None
    ) -> None:
        """Toggle reacting to user messages."""
        if channel is None:
            if isinstance(ctx.message.channel, discord.TextChannel):
                channel = ctx.message.channel
            else:
                return
        reaction_template = await self.config.custom(
            "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
        ).reaction_template()
        if not reaction_template:
            await ctx.send(error(f"{channel.mention} is not a ReactChannel."))
        else:
            react_to_users = not await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_to.users()
            await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_to.users.set(react_to_users)
            await ctx.send(
                success(
                    f"{channel.mention} ReactChannel will {'now' if react_to_users else 'no longer'} automatically react to users."
                )
            )

    @source.command(aliases=["bot"])
    async def bots(
        self, ctx: commands.Context, channel: discord.TextChannel | None
    ) -> None:
        """Toggle reacting to other bot messages."""
        if channel is None:
            if isinstance(ctx.message.channel, discord.TextChannel):
                channel = ctx.message.channel
            else:
                return
        reaction_template = await self.config.custom(
            "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
        ).reaction_template()
        if not reaction_template:
            await ctx.send(error(f"{channel.mention} is not a ReactChannel."))
        else:
            react_to_bots = not await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_to.bots()
            if reaction_template == "vote" and react_to_bots:
                await ctx.send(
                    warning("Bots are always ignored on vote ReactChannels.")
                )
                return
            await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_to.bots.set(react_to_bots)
            await ctx.send(
                success(
                    f"{channel.mention} ReactChannel will {'now' if react_to_bots else 'no longer'} automatically react to bots."
                )
            )

    @source.command(aliases=["me"])
    async def myself(
        self, ctx: commands.Context, channel: discord.TextChannel | None
    ) -> None:
        """Toggle reacting to my own messages."""
        if channel is None:
            if isinstance(ctx.message.channel, discord.TextChannel):
                channel = ctx.message.channel
            else:
                return
        reaction_template = await self.config.custom(
            "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
        ).reaction_template()
        if not reaction_template:
            await ctx.send(error(f"{channel.mention} is not a ReactChannel."))
        else:
            react_to_myself = not await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_to.myself()
            if reaction_template == "vote" and react_to_myself:
                await ctx.send(
                    warning("Bots are always ignored on vote ReactChannels.")
                )
                return
            await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_to.myself.set(react_to_myself)
            await ctx.send(
                success(
                    f"{channel.mention} ReactChannel will {'now' if react_to_myself else 'no longer'} automatically react to my ({channel.guild.me.display_name}) messages."
                )
            )

    @set_filter.group()
    async def role(self, ctx: commands.Context) -> None:
        """Filter what user roles will be reacted to."""

    @role.command(name="add")
    async def role_add(
        self,
        ctx: commands.Context,
        role: discord.Role,
        channel: discord.TextChannel | None,
    ) -> None:
        """Add a role to the role filter."""
        if channel is None:
            if isinstance(ctx.message.channel, discord.TextChannel):
                channel = ctx.message.channel
            else:
                return
        reaction_template = await self.config.custom(
            "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
        ).reaction_template()
        if not reaction_template:
            await ctx.send(error(f"{channel.mention} is not a ReactChannel."))
        else:
            react_role_ids = await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_roles()
            if role.id not in react_role_ids:
                react_role_ids.append(role.id)
                await self.config.custom(
                    "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
                ).react_roles.set(react_role_ids)

            react_roles_allow = await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_roles_allow()

            await ctx.send(
                success(
                    f"{channel.mention} ReactChannel will {'only' if react_roles_allow else 'not'} react to users with the given roles:\n\n"
                    f"{self._list_roles(channel.guild, react_role_ids)}"
                )
            )

    @role.command(name="remove", aliases=["delete", "rem"])
    async def role_remove(
        self,
        ctx: commands.Context,
        role: discord.Role,
        channel: discord.TextChannel | None,
    ) -> None:
        """Remove a role from the role filter."""
        if channel is None:
            if isinstance(ctx.message.channel, discord.TextChannel):
                channel = ctx.message.channel
            else:
                return
        reaction_template = await self.config.custom(
            "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
        ).reaction_template()
        if not reaction_template:
            await ctx.send(error(f"{channel.mention} is not a ReactChannel."))
        else:
            react_role_ids = await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_roles()
            if role.id in react_role_ids:
                react_role_ids.remove(role.id)
                await self.config.custom(
                    "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
                ).react_roles.set(react_role_ids)

            if not react_role_ids:
                await ctx.send(
                    success(
                        f"{channel.mention} ReactChannel will not filter on roles anymore."
                    )
                )
            else:
                react_roles_allow = await self.config.custom(
                    "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
                ).react_roles_allow()

                await ctx.send(
                    success(
                        f"{channel.mention} ReactChannel will {'only' if react_roles_allow else 'not'} react to users with the given roles:\n\n"
                        f"{self._list_roles(channel.guild, react_role_ids)}"
                    )
                )

    @role.command(name="toggle")
    async def role_toggle(
        self, ctx: commands.Context, channel: discord.TextChannel | None
    ) -> None:
        """Toggle between allowing or denying these roles."""
        if channel is None:
            if isinstance(ctx.message.channel, discord.TextChannel):
                channel = ctx.message.channel
            else:
                return
        reaction_template = await self.config.custom(
            "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
        ).reaction_template()
        if not reaction_template:
            await ctx.send(error(f"{channel.mention} is not a ReactChannel."))
        else:
            react_roles_allow = not await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_roles_allow()
            await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_roles_allow.set(react_roles_allow)

            react_role_ids = await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_roles()
            if react_role_ids:
                await ctx.send(
                    success(
                        f"{channel.mention} ReactChannel will {'only' if react_roles_allow else 'not'} react to users with the given roles:\n\n"
                        f"{self._list_roles(channel.guild, react_role_ids)}"
                    )
                )
            else:
                await ctx.send(
                    warning(
                        f"{channel.mention} ReactChannel will {'only' if react_roles_allow else 'not'} react to users with specific roles. "
                        "You don't have any roles set up though, so this will not take effect. "
                        "Use `[p]reactchannelset filter role add` to begin filtering based on roles."
                    )
                )

    @set_filter.group()
    async def content(self, ctx: commands.Context) -> None:
        """Filter what type of messages will be reacted to."""

    @content.command()
    async def text(
        self, ctx: commands.Context, channel: discord.TextChannel | None
    ) -> None:
        """Toggle reacting to text-only messages."""
        if channel is None:
            if isinstance(ctx.message.channel, discord.TextChannel):
                channel = ctx.message.channel
            else:
                return
        reaction_template = await self.config.custom(
            "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
        ).reaction_template()
        if not reaction_template:
            await ctx.send(error(f"{channel.mention} is not a ReactChannel."))
        else:
            react_filter_text = not await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_filter.text()
            await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_filter.text.set(react_filter_text)
            await ctx.send(
                success(
                    f"{channel.mention} ReactChannel will {'now' if react_filter_text else 'no longer'} automatically react to text-only messages."
                )
            )

    @content.command(name="commands", aliases=["command"])
    async def content_commands(
        self, ctx: commands.Context, channel: discord.TextChannel | None
    ) -> None:
        """Toggle reacting to command messages."""
        if channel is None:
            if isinstance(ctx.message.channel, discord.TextChannel):
                channel = ctx.message.channel
            else:
                return
        reaction_template = await self.config.custom(
            "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
        ).reaction_template()
        if not reaction_template:
            await ctx.send(error(f"{channel.mention} is not a ReactChannel."))
        else:
            react_filter_commands = not await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_filter.commands()
            await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_filter.commands.set(react_filter_commands)
            await ctx.send(
                success(
                    f"{channel.mention} ReactChannel will {'now' if react_filter_commands else 'no longer'} automatically react to command messages."
                )
            )

    @content.command(aliases=["image"])
    async def images(
        self, ctx: commands.Context, channel: discord.TextChannel | None
    ) -> None:
        """Toggle reacting to images."""
        if channel is None:
            if isinstance(ctx.message.channel, discord.TextChannel):
                channel = ctx.message.channel
            else:
                return
        reaction_template = await self.config.custom(
            "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
        ).reaction_template()
        if not reaction_template:
            await ctx.send(error(f"{channel.mention} is not a ReactChannel."))
        else:
            react_filter_images = not await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_filter.images()
            await self.config.custom(
                "REACT_CHANNEL", str(channel.guild.id), str(channel.id)
            ).react_filter.images.set(react_filter_images)
            await ctx.send(
                success(
                    f"{channel.mention} ReactChannel will {'now' if react_filter_images else 'no longer'} automatically react to images."
                )
            )

    @reactchannelset.group()
    async def emoji(self, ctx: commands.Context) -> None:
        """Manage emojis used for ReactChannels."""
        if not ctx.guild:
            return
        if not ctx.invoked_subcommand:
            upvote = await self._get_emoji(ctx.guild, "upvote")
            downvote = await self._get_emoji(ctx.guild, "downvote")
            message = f"Upvote emoji: {upvote if upvote else 'None'}\n"
            message += f"Downvote emoji: {downvote if downvote else 'None'}"
            await ctx.send(message)

    @emoji.command(name="upvote")
    async def set_upvote(
        self, ctx: commands.Context, emoji: discord.Emoji | str
    ) -> None:
        """Set the upvote emoji used. Use "none" to remove the emoji and disable upvotes."""
        await self._save_emoji(ctx, emoji, "upvote")

    @emoji.command(name="downvote")
    async def set_downvote(
        self, ctx: commands.Context, emoji: discord.Emoji | str
    ) -> None:
        """Set the downvote emoji used. Use "none" to remove the emoji and disable downvotes."""
        await self._save_emoji(ctx, emoji, "downvote")

    async def _save_emoji(
        self, ctx: commands.Context, emoji: discord.Emoji | str, emoji_type: str
    ) -> None:
        """Actually save the emoji."""
        if not ctx.guild:
            return
        if emoji == "none":
            setting = getattr(self.config.guild(ctx.guild).emojis, emoji_type)
            await setting.set(None)
            await ctx.send(
                success(
                    f"{emoji_type.capitalize()} emoji for this server has been disabled"
                )
            )
            await self._get_emoji(ctx.guild, emoji_type, refresh=True)
            return
        try:
            if isinstance(emoji, discord.PartialEmoji):
                await ctx.send(error("That is not a valid emoji I can use!"))
                return
            await ctx.message.add_reaction(emoji)
            await ctx.message.remove_reaction(emoji, ctx.guild.me)
            save = emoji
            if isinstance(emoji, discord.Emoji):
                save = emoji.id
            setting = getattr(self.config.guild(ctx.guild).emojis, emoji_type)
            await setting.set(save)
            await ctx.send(
                success(
                    f"{emoji_type.capitalize()} emoji for this server has been set to {emoji}"
                )
            )
            await self._get_emoji(ctx.guild, emoji_type, refresh=True)
        except (discord.HTTPException, TypeError):
            await ctx.send(error("That is not a valid emoji I can use!"))

    #
    # Command methods
    #

    @commands.command()
    @commands.guild_only()
    async def karma(
        self, ctx: commands.Context, member: discord.Member | None = None
    ) -> None:
        """View your (or another users) total karma for messages in this server."""
        prefix = f"{ctx.message.author.mention}, you have"
        if member and member != ctx.message.author:
            prefix = f"{member.display_name} has"
        elif isinstance(ctx.message.author, discord.Member):
            member = ctx.message.author
        else:
            return
        member_config = self.config.member(member)
        total_karma = await member_config.karma()
        await ctx.send(f"{prefix} **{total_karma}** message karma")

    @commands.command()
    @commands.guild_only()
    async def karmatop(self, ctx: commands.Context) -> None:
        """View the members in this server with the highest total karma."""
        if not ctx.guild:
            return
        all_guild_members_dict = await self.config.all_members(ctx.guild)
        all_guild_members_sorted_list = sorted(
            all_guild_members_dict.items(),
            key=lambda x: x[1]["karma"],
            reverse=True,
        )
        added = 0  # We want the top 10 that are still in the guild
        message = "Rank | Name                             | Karma\n-----------------------------------------------\n"
        for data in all_guild_members_sorted_list:
            member = ctx.guild.get_member(data[0])
            if member:
                added += 1
                message += f"{str(added).rjust(3)}  | {member.display_name[:32].ljust(32)} | {data[1]['karma']}\n"
                if added >= KARMATOP_LIMIT:
                    break
        await ctx.send(box(message))

    @commands.command()
    @commands.guild_only()
    async def upvote(self, ctx: commands.Context) -> None:
        """View the upvote reaction for this server."""
        if not ctx.guild:
            return
        upvote = await self._get_emoji(ctx.guild, "upvote")
        if upvote:
            await ctx.send(
                f"This servers upvote emoji is {upvote}. React to other members messages to give them karma!"
            )
        else:
            await ctx.send("This server does not have an upvote emoji set")

    @commands.command()
    @commands.guild_only()
    async def downvote(self, ctx: commands.Context) -> None:
        """View the downvote reaction for this server."""
        if not ctx.guild:
            return
        downvote = await self._get_emoji(ctx.guild, "downvote")
        if downvote:
            await ctx.send(
                f"This servers downvote emoji is {downvote}. React to other members messages to remove karma."
            )
        else:
            await ctx.send("This server does not have a downvote emoji set")

    #
    # Listener methods
    #

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Watch for messages in enabled react channels to add reactions."""
        # DM/Malformed message
        if message.guild is None or message.channel is None:
            return
        # Disabled cog
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return
        # Can't react
        if not message.channel.permissions_for(message.guild.me).add_reactions:
            return
        # react_to check
        if message.author == message.guild.me:
            if not await self.config.custom(
                "REACT_CHANNEL", str(message.guild.id), str(message.channel.id)
            ).react_to.myself():
                return
        elif message.author.bot:
            if not await self.config.custom(
                "REACT_CHANNEL", str(message.guild.id), str(message.channel.id)
            ).react_to.bots():
                return
        elif not await self.config.custom(
            "REACT_CHANNEL", str(message.guild.id), str(message.channel.id)
        ).react_to.users():
            return
        # react_roles check
        react_role_ids = await self.config.custom(
            "REACT_CHANNEL", str(message.guild.id), str(message.channel.id)
        ).react_roles()
        if react_role_ids:
            if not isinstance(message.author, discord.Member):
                return
            member_role_ids = [role.id for role in message.author.roles]
            has_matching_role = any(
                role_id in react_role_ids for role_id in member_role_ids
            )
            react_roles_allow = await self.config.custom(
                "REACT_CHANNEL", str(message.guild.id), str(message.channel.id)
            ).react_roles_allow()
            # If the user has a matching role, and we are denying roles, or if they don't, and we are allowing roles
            if has_matching_role != react_roles_allow:
                return
        # react_filter check
        ctx = await self.bot.get_context(message)
        if ctx and ctx.valid:
            # command
            if not await self.config.custom(
                "REACT_CHANNEL", str(message.guild.id), str(message.channel.id)
            ).react_filter.commands():
                return
        elif (
            message.attachments
            and message.attachments[0].content_type
            and message.attachments[0].content_type.startswith("image")
        ):
            # image
            if not await self.config.custom(
                "REACT_CHANNEL", str(message.guild.id), str(message.channel.id)
            ).react_filter.images():
                return
        elif not await self.config.custom(
            "REACT_CHANNEL", str(message.guild.id), str(message.channel.id)
        ).react_filter.text():
            # text
            return
        # Actually do reactions now!
        reaction_template = await self.config.custom(
            "REACT_CHANNEL", str(message.guild.id), str(message.channel.id)
        ).reaction_template()
        if reaction_template == "checklist":
            # checklist
            await message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        elif reaction_template == "vote" and not message.author.bot:
            # vote
            for emoji_type in ["upvote", "downvote"]:
                emoji = await self._get_emoji(message.guild, emoji_type)
                if emoji:
                    with suppress(discord.HTTPException):
                        await message.add_reaction(emoji)
        elif isinstance(reaction_template, list):
            # Custom reactions
            for emoji_tuple in reaction_template:
                with suppress(discord.HTTPException):
                    await message.add_reaction(emoji_tuple[0])

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        """Watch for reactions added to a message."""
        # Only guilds where the cog is enabled
        if not payload.guild_id or await self.bot.cog_disabled_in_guild_raw(
            self.qualified_name, payload.guild_id
        ):
            return
        # Get required data
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        channel = guild.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        member = guild.get_member(payload.user_id)  # User who added a reaction
        if not guild or not channel or not member or not payload.message_id:
            return
        # Ignore bots
        if member.bot:
            return
        # Get reaction_template and message
        reaction_template = await self.config.custom(
            "REACT_CHANNEL", str(payload.guild_id), str(payload.channel_id)
        ).reaction_template()
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return
        if not message:
            return
        # Process checklist
        if (
            str(payload.emoji) == "\N{WHITE HEAVY CHECK MARK}"
            and reaction_template == "checklist"
        ):
            await delete(message)
            return
        # Process vote
        upvote = await self._get_emoji(guild, "upvote")
        downvote = await self._get_emoji(guild, "downvote")
        karma = 0
        if upvote and payload.emoji == upvote:
            karma = 1
        elif downvote and payload.emoji == downvote:
            karma = -1
        if karma:
            message_author = message.author
            if (
                message_author.bot
                or not isinstance(message_author, discord.Member)
                or member == message_author
            ):
                # Bots can't get karma, only members of the guild, and members can't upvote themselves
                return
            await self._increment_karma(message_author, karma)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        """Watch for reactions removed from messages."""
        # Only guilds where the cog is enabled
        if not payload.guild_id or await self.bot.cog_disabled_in_guild_raw(
            self.qualified_name, payload.guild_id
        ):
            return
        # Get required data
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        channel = guild.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        member = guild.get_member(payload.user_id)  # User whose reaction was removed
        if not guild or not channel or not member or not payload.message_id:
            return
        # Get message
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return
        if not message:
            return
        # Process vote
        upvote = await self._get_emoji(guild, "upvote")
        downvote = await self._get_emoji(guild, "downvote")
        karma = 0
        if upvote and payload.emoji == upvote:
            karma = -1
        elif downvote and payload.emoji == downvote:
            karma = 1
        if karma:
            message_author = message.author
            if (
                message_author.bot
                or not isinstance(message_author, discord.Member)
                or member == message_author
            ):
                # Bots can't get karma, only members of the guild, and members can't upvote themselves
                return
            await self._increment_karma(message_author, karma)

    @commands.Cog.listener()
    async def on_guild_channel_delete(
        self, guild_channel: discord.abc.GuildChannel
    ) -> None:
        """Clean up config when a ReactChannel is deleted."""
        await self.config.custom(
            "REACT_CHANNEL", str(guild_channel.guild.id), str(guild_channel.id)
        ).clear()

    #
    # Private methods
    #

    async def _get_emoji(
        self, guild: discord.Guild, emoji_type: str, *, refresh: bool = False
    ) -> discord.Emoji | None:
        """Get an emoji, ready for sending/reacting."""
        if guild.id not in self.emoji_cache:
            self.emoji_cache[guild.id] = {}
        if emoji_type in self.emoji_cache[guild.id] and not refresh:
            return self.emoji_cache[guild.id][emoji_type]
        emoji = await getattr(self.config.guild(guild).emojis, emoji_type)()
        if isinstance(emoji, int):
            emoji = self.bot.get_emoji(emoji)
        self.emoji_cache[guild.id][emoji_type] = emoji
        return emoji

    async def _increment_karma(self, member: discord.Member, delta: int) -> None:
        """Increment a users karma."""
        async with self.config.member(member).karma.get_lock():
            member_config = self.config.member(member)
            total_karma = await member_config.karma()
            total_karma += delta
            await member_config.karma.set(total_karma)
            if await member_config.created_at() == 0:
                time = int(datetime.datetime.now(datetime.UTC).timestamp())
                await member_config.created_at.set(time)

    @staticmethod
    def _list_roles(guild: discord.Guild, role_ids: list[int]) -> str:
        result = ""
        for role_id in role_ids:
            role = guild.get_role(role_id)
            if role:
                result += f"- {role.name}\n"
        return result.strip()
