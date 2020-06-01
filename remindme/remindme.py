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

from .pcx_lib import checkmark, delete

__author__ = "PhasecoreX"
log = logging.getLogger("red.pcxcogs.remindme")


class RemindMe(commands.Cog):
    """Never forget anything anymore."""

    default_global_settings = {
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
        self.enable_bg_loop()
        self.me_too_reminders = {}

    def enable_bg_loop(self):
        """Set up the background loop task."""
        self.bg_loop_task = self.bot.loop.create_task(self.bg_loop())
        self.bg_loop_task.add_done_callback(self._error_handler)

    def _error_handler(self, fut: asyncio.Future):
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
    async def list(self, ctx: commands.Context):
        """Show a list of all of your reminders."""
        author = ctx.message.author
        to_send = await self.get_user_reminders(author.id)

        if not to_send:
            await self.send_message(ctx, "You don't have any upcoming reminders.")
        else:
            embed = discord.Embed(
                title="Reminders for {}".format(author.name),
                color=await ctx.embed_color(),
            )
            embed.set_thumbnail(url=author.avatar_url)
            current_timestamp = int(current_time.time())
            count = 0
            for reminder in to_send:
                count += 1
                delta = reminder["FUTURE"] - current_timestamp
                embed.add_field(
                    name="#{} - {}".format(
                        count,
                        "In {}".format(humanize_timedelta(seconds=delta))
                        if delta > 0
                        else "Now!",
                    ),
                    value=reminder["TEXT"],
                    inline=False,
                )
            await author.send(embed=embed)
            if ctx.message.guild is not None:
                await self.send_message(ctx, "Check your DMs for a full list!")

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

    @reminder.command(aliases=["delete"])
    async def remove(self, ctx: commands.Context, index: str):
        """Delete a reminder.

        <index> can either be:
        * a number for a specific reminder to delete
        * "last" to delete the most recently created reminder
        * "all" to delete all reminders (same as [p]forgetme)
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
        if maximum - 1 < len(await self.get_user_reminders(author.id)):
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
        if len(text) > 1900:
            await self.send_message(ctx, "Your reminder text is too long.")
            return

        seconds = time_delta.total_seconds()
        future = int(current_time.time() + seconds)
        future_text = humanize_timedelta(timedelta=time_delta)

        reminder = {
            "ID": author.id,
            "FUTURE": future,
            "TEXT": text,
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
        to_remove = await self.get_user_reminders(author.id)

        if not to_remove:
            await self.send_message(ctx, "You don't have any upcoming reminders.")
            return

        async with self.config.reminders() as current_reminders:
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
                for reminder in to_remove:
                    current_reminders.remove(reminder)
                await self.send_message(ctx, "All of your reminders have been removed.")
                return

            if index == "last":
                current_reminders.remove(to_remove[len(to_remove) - 1])
                await self.send_message(
                    ctx, "Your most recently created reminder has been removed."
                )
                return

            try:
                int_index = int(index)
            except ValueError:
                return
            if int_index > 0:
                if len(to_remove) < int_index:
                    await self.send_message(
                        ctx,
                        "You don't have that many reminders! (you only have {})".format(
                            len(to_remove)
                        ),
                    )
                else:
                    current_reminders.remove(to_remove[int_index - 1])
                    await self.send_message(
                        ctx, "Reminder #{} has been removed.".format(int_index)
                    )

    async def get_user_reminders(self, user_id: int):
        """Return all of a users reminders."""
        result = []
        async with self.config.reminders() as current_reminders:
            for reminder in current_reminders:
                if reminder["ID"] == user_id:
                    result.append(reminder)
        return result

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
            reminder["ID"] = member.id
            async with self.config.reminders() as current_reminders:
                if not current_reminders.count(reminder):
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
                    user = self.bot.get_user(reminder["ID"])
                    if user is not None:
                        embed = discord.Embed(
                            title=":bell: Reminder! :bell:",
                            color=await self.bot.get_embed_color(self),
                        )
                        embed.add_field(
                            name="From {} ago:".format(reminder["FUTURE_TEXT"]),
                            value=reminder["TEXT"],
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
