"""RemindMe cog for Red-DiscordBot ported and enhanced by PhasecoreX."""
import asyncio
import logging
import time as current_time
from datetime import timedelta

import discord
from redbot.core import Config, checks, commands
from redbot.core.commands.converter import parse_timedelta
from redbot.core.utils.chat_formatting import box, humanize_timedelta
from redbot.core.utils.predicates import MessagePredicate

from .pcx_lib import checkmark, delete, embed_splitter

__author__ = "PhasecoreX"
log = logging.getLogger("red.pcxcogs.remindme")


class RemindMe(commands.Cog):
    """Never forget anything anymore."""

    default_global_settings = {
        "schema_version": 0,
        "total_sent": 0,
        "max_user_reminders": 20,
        "reminders": [],
    }
    reminder_emoji = "🔔"

    def __init__(self, bot):
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1224364860, force_registration=True
        )
        self.config.register_global(**self.default_global_settings)
        self.bg_loop_task = None
        self.me_too_reminders = {}

    async def initialize(self):
        """Perform setup actions before loading cog."""
        await self._migrate_config()
        self._enable_bg_loop()

    async def _migrate_config(self):
        """Perform some configuration migrations."""
        if not await self.config.schema_version():
            # Add/generate USER_REMINDER_ID, rename some fields
            current_reminders = await self.config.reminders()
            new_reminders = []
            user_reminder_ids = {}
            for reminder in current_reminders:
                user_reminder_id = user_reminder_ids.get(reminder["ID"], 1)
                new_reminder = {
                    "USER_REMINDER_ID": user_reminder_id,
                    "USER_ID": reminder["ID"],
                    "REMINDER": reminder["TEXT"],
                    "FUTURE": reminder["FUTURE"],
                    "FUTURE_TEXT": reminder["FUTURE_TEXT"],
                }
                user_reminder_ids[reminder["ID"]] = user_reminder_id + 1
                new_reminders.append(new_reminder)
            await self.config.reminders.set(new_reminders)
            await self.config.schema_version.set(1)

    def _enable_bg_loop(self):
        """Set up the background loop task."""
        self.bg_loop_task = self.bot.loop.create_task(self.bg_loop())

        def error_handler(self, fut: asyncio.Future):
            try:
                fut.result()
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                log.exception(
                    "Unexpected exception occurred in background loop of RemindMe: ",
                    exc_info=exc,
                )
                asyncio.create_task(
                    self.bot.send_to_owners(
                        "An unexpected exception occurred in the background loop of RemindMe.\n"
                        "Reminders will not be sent out until the cog is reloaded.\n"
                        "Check your console or logs for details, and consider opening a bug report for this."
                    )
                )

        self.bg_loop_task.add_done_callback(error_handler)

    def cog_unload(self):
        """Clean up when cog shuts down."""
        if self.bg_loop_task:
            self.bg_loop_task.cancel()

    @commands.group()
    @checks.is_owner()
    async def remindmeset(self, ctx: commands.Context):
        """Manage RemindMe settings."""
        if not ctx.invoked_subcommand:
            msg = (
                "Maximum reminders per user: {}\n"
                "\n"
                "--Stats--\n"
                "Pending reminders:    {}\n"
                "Total reminders sent: {}"
            ).format(
                await self.config.max_user_reminders(),
                len(await self.config.reminders()),
                await self.config.total_sent(),
            )
            await ctx.send(box(msg))

    @remindmeset.command()
    async def max(self, ctx: commands.Context, maximum: int):
        """Set the maximum number of reminders a user can create at one time."""
        await self.config.max_user_reminders.set(maximum)
        await ctx.send(
            checkmark(
                "Maximum reminders per user is now set to {}".format(
                    await self.config.max_user_reminders()
                )
            )
        )

    @commands.group()
    async def reminder(self, ctx: commands.Context):
        """Manage your reminders."""

    @reminder.command(aliases=["get"])
    async def list(self, ctx: commands.Context, sort: str = "time"):
        """Show a list of all of your reminders.

        Sort can either be:
        `time` (default) for soonest expiring reminder first,
        `added` for ordering by when the reminder was added,
        `id` for ordering by ID
        """
        author = ctx.message.author
        to_send = await self.get_user_reminders(author.id)
        if sort == "time":
            to_send.sort(key=lambda reminder: reminder["FUTURE"])
        elif sort == "added":
            pass
        elif sort == "id":
            to_send.sort(key=lambda reminder: reminder["USER_REMINDER_ID"])
        else:
            await self.send_message(
                ctx,
                "That is not a valid sorting option. Choose from `time` (default), `added`, or `id`.",
            )
            return

        if not to_send:
            await self.send_message(ctx, "You don't have any upcoming reminders.")
            return

        embed = discord.Embed(
            title="Reminders for {}".format(author.name), color=await ctx.embed_color(),
        )
        embed.set_thumbnail(url=author.avatar_url)
        current_timestamp = int(current_time.time())
        for reminder in to_send:
            delta = reminder["FUTURE"] - current_timestamp
            embed.add_field(
                name="ID# {} — {}".format(
                    reminder["USER_REMINDER_ID"],
                    "In {}".format(humanize_timedelta(seconds=delta))
                    if delta > 0
                    else "Now!",
                ),
                value=reminder["REMINDER"],
                inline=False,
            )
        if ctx.message.guild is not None:
            await self.send_message(ctx, "Check your DMs for a full list!")
        await embed_splitter(embed, author)

    @reminder.command(aliases=["add"])
    async def create(self, ctx: commands.Context, time: str, *, text: str):
        """Create a reminder. Same as [p]remindme.

        Accepts: seconds, minutes, hours, days, weeks
        Examples:
        - [p]reminder create 2min Do that thing soon in 2 minutes
        - [p]remindme create 3h40m Do that thing later in 3 hours and 40 minutes
        - [p]reminder create 3 days Have sushi with Ryan and Heather
        """
        await self.create_reminder(ctx, time, text=text)

    @reminder.group(aliases=["edit"])
    async def modify(self, ctx: commands.Context):
        """Modify an existing reminder."""
        pass

    @modify.command()
    async def time(self, ctx: commands.Context, reminder_id: int, *, time: str):
        """Modify the time of an existing reminder."""
        users_reminders = await self.get_user_reminders(ctx.message.author.id)
        edit_reminder = self.get_reminder(users_reminders, reminder_id)
        if not edit_reminder:
            await self.send_non_existant_msg(ctx, reminder_id)
            return
        try:
            time_delta = parse_timedelta(time, minimum=timedelta(minutes=1))
            if not time_delta:
                await ctx.send_help()
                return
        except commands.BadArgument as ba:
            await self.send_message(ctx, str(ba))
            return
        seconds = time_delta.total_seconds()
        future = int(current_time.time() + seconds)
        future_text = humanize_timedelta(timedelta=time_delta)

        reminder = {
            "USER_REMINDER_ID": reminder_id,
            "USER_ID": edit_reminder["USER_ID"],
            "REMINDER": edit_reminder["REMINDER"],
            "FUTURE": future,
            "FUTURE_TEXT": future_text,
        }
        async with self.config.reminders() as current_reminders:
            current_reminders.remove(edit_reminder)
            current_reminders.append(reminder)
        await self.send_message(
            ctx,
            "Reminder with ID# **{}** has been edited successfully, and will now remind you {} from now.".format(
                reminder_id, future_text
            ),
        )

    @modify.command()
    async def text(self, ctx: commands.Context, reminder_id: int, *, text: str):
        """Modify the text of an existing reminder."""
        users_reminders = await self.get_user_reminders(ctx.message.author.id)
        edit_reminder = self.get_reminder(users_reminders, reminder_id)
        if not edit_reminder:
            await self.send_non_existant_msg(ctx, reminder_id)
            return
        text = text.strip()
        if len(text) > 1000:
            await self.send_message(ctx, "Your reminder text is too long.")
            return
        reminder = {
            "USER_REMINDER_ID": reminder_id,
            "USER_ID": edit_reminder["USER_ID"],
            "REMINDER": text,
            "FUTURE": edit_reminder["FUTURE"],
            "FUTURE_TEXT": edit_reminder["FUTURE_TEXT"],
        }
        async with self.config.reminders() as current_reminders:
            current_reminders.remove(edit_reminder)
            current_reminders.append(reminder)
        await self.send_message(
            ctx,
            "Reminder with ID# **{}** has been edited successfully.".format(
                reminder_id
            ),
        )

    @reminder.command(aliases=["delete"])
    async def remove(self, ctx: commands.Context, index: str):
        """Delete a reminder.

        <index> can either be:
        - a number for a specific reminder to delete
        - `last` to delete the most recently created reminder
        - `all` to delete all reminders (same as [p]forgetme)
        """
        await self.delete_reminder(ctx, index)

    @commands.command()
    async def remindme(self, ctx: commands.Context, time: str, *, text: str):
        """Send you <text> when the time is up.

        Accepts: seconds, minutes, hours, days, weeks
        Examples:
        - [p]remindme 2min Do that thing in 2 minutes
        - [p]remindme 3h40m Do that thing in 3 hours and 40 minutes
        - [p]remindme 3 days Have sushi with Ryan and Heather
        """
        await self.create_reminder(ctx, time, text=text)

    @commands.command()
    async def forgetme(self, ctx: commands.Context):
        """Remove all of your upcoming reminders."""
        await self.delete_reminder(ctx, "all")

    async def create_reminder(self, ctx: commands.Context, time: str, text: str):
        """Logic to create a reminder."""
        author = ctx.message.author
        maximum = await self.config.max_user_reminders()
        users_reminders = await self.get_user_reminders(author.id)
        if len(users_reminders) > maximum - 1:
            plural = "reminder" if maximum == 1 else "reminders"
            await self.send_message(
                ctx,
                (
                    "You have too many reminders! "
                    "I can only keep track of {} {} for you at a time.".format(
                        maximum, plural
                    )
                ),
            )
            return

        try:
            time_delta = parse_timedelta(time, minimum=timedelta(minutes=1))
            if not time_delta:
                # Try again if the user is doing the old "[p]remindme 4 hours ..." format
                time_unit = text.split()[0]
                time = "{} {}".format(time, time_unit)
                text = text[len(time_unit) :].strip()
                time_delta = parse_timedelta(time, minimum=timedelta(minutes=1))
                if not text or not time_delta:
                    await ctx.send_help()
                    return
        except commands.BadArgument as ba:
            await self.send_message(ctx, str(ba))
            return

        text = text.strip()
        if len(text) > 1000:
            await self.send_message(ctx, "Your reminder text is too long.")
            return

        seconds = time_delta.total_seconds()
        future = int(current_time.time() + seconds)
        future_text = humanize_timedelta(timedelta=time_delta)
        next_reminder_id = self.get_next_user_reminder_id(users_reminders)

        reminder = {
            "USER_REMINDER_ID": next_reminder_id,
            "USER_ID": author.id,
            "REMINDER": text,
            "FUTURE": future,
            "FUTURE_TEXT": future_text,
        }
        async with self.config.reminders() as current_reminders:
            current_reminders.append(reminder)
        await self.send_message(
            ctx, "I will remind you that in {}.".format(future_text)
        )

        can_react = ctx.channel.permissions_for(ctx.me).add_reactions
        can_edit = ctx.channel.permissions_for(ctx.me).manage_messages
        if can_react and can_edit:
            query: discord.Message = await ctx.send(
                "If anyone else would like to be reminded as well, click the bell below!"
            )
            self.me_too_reminders[query.id] = reminder
            await query.add_reaction(self.reminder_emoji)
            await asyncio.sleep(30)
            await delete(query)
            del self.me_too_reminders[query.id]

    async def delete_reminder(self, ctx: commands.Context, index: str):
        """Logic to delete reminders."""
        if not index:
            return
        author = ctx.message.author
        users_reminders = await self.get_user_reminders(author.id)

        if not users_reminders:
            await self.send_message(ctx, "You don't have any upcoming reminders.")
            return

        if index == "all":
            # Ask if the user really wants to do this
            pred = MessagePredicate.yes_or_no(ctx)
            await self.send_message(
                ctx,
                "Are you **sure** you want to remove all of your reminders? (yes/no)",
            )
            try:
                await ctx.bot.wait_for("message", check=pred, timeout=30)
            except asyncio.TimeoutError:
                pass
            if pred.result:
                pass
            else:
                await self.send_message(ctx, "I have left your reminders alone.")
                return
            await self._do_reminder_delete(users_reminders)
            await self.send_message(ctx, "All of your reminders have been removed.")
            return

        if index == "last":
            reminder_to_delete = users_reminders[len(users_reminders) - 1]
            await self._do_reminder_delete(reminder_to_delete)
            await self.send_message(
                ctx,
                "Your most recently created reminder (ID# **{}**) has been removed.".format(
                    reminder_to_delete["USER_REMINDER_ID"]
                ),
            )
            return

        try:
            int_index = int(index)
        except ValueError:
            await ctx.send_help()
            return

        reminder_to_delete = self.get_reminder(users_reminders, int_index)
        if reminder_to_delete:
            await self._do_reminder_delete(reminder_to_delete)
            await self.send_message(
                ctx, "Reminder with ID# **{}** has been removed.".format(int_index)
            )
        else:
            await self.send_non_existant_msg(ctx, int_index)

    async def _do_reminder_delete(self, reminders):
        """Actually delete a reminder."""
        if not isinstance(reminders, list):
            reminders = [reminders]
        async with self.config.reminders() as current_reminders:
            for reminder in reminders:
                current_reminders.remove(reminder)

    async def get_user_reminders(self, user_id: int):
        """Return all of a users reminders."""
        result = []
        async with self.config.reminders() as current_reminders:
            for reminder in current_reminders:
                if reminder["USER_ID"] == user_id:
                    result.append(reminder)
        return result

    async def send_non_existant_msg(self, ctx: commands.Context, reminder_id: int):
        """Send a message telling the user the reminder ID does not exist."""
        await self.send_message(
            ctx,
            "Reminder with ID# **{}** does not exist! Check the reminder list and verify you typed the correct ID#.".format(
                reminder_id
            ),
        )

    @staticmethod
    def get_reminder(reminder_list, reminder_id: int):
        """Get the reminder from reminder_list with the specified reminder_id."""
        for reminder in reminder_list:
            if reminder["USER_REMINDER_ID"] == reminder_id:
                return reminder
        return None

    @staticmethod
    def get_next_user_reminder_id(reminder_list):
        """Get the next reminder ID for a user."""
        next_reminder_id = 1
        used_reminder_ids = set()
        for reminder in reminder_list:
            used_reminder_ids.add(reminder["USER_REMINDER_ID"])
        while next_reminder_id in used_reminder_ids:
            next_reminder_id += 1
        return next_reminder_id

    @staticmethod
    def reminder_exists(reminder_list, reminder):
        """Check if a reminder is already in this reminder list (ignores user reminder ID)."""
        for existing_reminder in reminder_list:
            if (
                existing_reminder["USER_ID"] == reminder["USER_ID"]
                and existing_reminder["REMINDER"] == reminder["REMINDER"]
                and existing_reminder["FUTURE"] == reminder["FUTURE"]
                and existing_reminder["FUTURE_TEXT"] == reminder["FUTURE_TEXT"]
            ):
                return True
        return False

    @staticmethod
    async def send_message(ctx: commands.Context, message: str):
        """Send a message.

        This will append the users name if we are sending to a channel,
        or leave it as-is if we are in a DM
        """
        if ctx.message.guild is not None:
            if message[:2].lower() != "i " and message[:2].lower() != "i'":
                message = message[0].lower() + message[1:]
            message = ctx.message.author.mention + ", " + message

        await ctx.send(message)

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.raw_models.RawReactionActionEvent
    ):
        """Watches for bell reactions on reminder messages.

        Thank you SinbadCogs!
        https://github.com/mikeshardmind/SinbadCogs/blob/v3/rolemanagement/events.py
        """
        if not payload.guild_id:
            return
        if str(payload.emoji) != self.reminder_emoji:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if member.bot:
            return

        try:
            reminder = self.me_too_reminders[payload.message_id]
            users_reminders = await self.get_user_reminders(member.id)
            reminder["USER_ID"] = member.id
            if self.reminder_exists(users_reminders, reminder):
                return
            reminder["USER_REMINDER_ID"] = self.get_next_user_reminder_id(
                users_reminders
            )
            async with self.config.reminders() as current_reminders:
                current_reminders.append(reminder)
            await member.send(
                "Hello! I will remind you of that in {}.".format(
                    reminder["FUTURE_TEXT"]
                )
            )
        except KeyError:
            return

    async def bg_loop(self):
        """Background loop."""
        await self.bot.wait_until_ready()
        while True:
            await self.check_reminders()
            await asyncio.sleep(5)

    async def check_reminders(self):
        """Send reminders that have expired."""
        to_remove = []
        for reminder in await self.config.reminders():
            if reminder["FUTURE"] <= int(current_time.time()):
                try:
                    user = self.bot.get_user(reminder["USER_ID"])
                    if user is not None:
                        embed = discord.Embed(
                            title=":bell: Reminder! :bell:",
                            color=await self.bot.get_embed_color(self),
                        )
                        embed.add_field(
                            name="From {} ago:".format(reminder["FUTURE_TEXT"]),
                            value=reminder["REMINDER"],
                        )
                        await user.send(embed=embed)
                        total_sent = await self.config.total_sent()
                        await self.config.total_sent.set(total_sent + 1)
                    else:
                        # Can't see the user (no shared servers)
                        to_remove.append(reminder)
                except (discord.Forbidden, discord.NotFound):
                    to_remove.append(reminder)
                except discord.HTTPException:
                    pass
                else:
                    to_remove.append(reminder)
        for reminder in to_remove:
            async with self.config.reminders() as current_reminders:
                current_reminders.remove(reminder)
