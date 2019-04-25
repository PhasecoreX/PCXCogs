"""RemindMe cog for Red-DiscordBot ported and enhanced by PhasecoreX."""
import asyncio
import time

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import box

__author__ = "PhasecoreX"


class RemindMe(commands.Cog):
    """Never forget anything anymore."""

    default_global_settings = {"max_user_reminders": 20, "reminders": []}
    reminder_emoji = "🔔"

    def __init__(self, bot):
        """Set up the plugin."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, 1224364860)
        self.config.register_global(**self.default_global_settings)
        self.units = {
            "minute": 60,
            "min": 60,
            "m": 60,
            "hour": 3600,
            "hr": 3600,
            "h": 3600,
            "day": 86400,
            "d": 86400,
            "week": 604800,
            "wk": 604800,
            "w": 604800,
            "month": 2592000,
            "mon": 2592000,
            "mo": 2592000,
        }
        self.time = 5
        self.task = self.bot.loop.create_task(self.check_reminders())
        self.me_too_reminders = {}

    def __unload(self):
        if self.task:
            self.task.cancel()

    @commands.group()
    @checks.is_owner()
    async def remindmeset(self, ctx: commands.Context):
        """Manage RemindMe settings."""
        if not ctx.invoked_subcommand:
            msg = "Maximum reminders per user: {}".format(
                await self.config.max_user_reminders()
            )
            await ctx.send(box(msg))

    @remindmeset.command()
    async def max(self, ctx: commands.Context, maximum: int):
        """Set the maximum number of reminders a user can create at one time."""
        await self.config.max_user_reminders.set(maximum)
        await ctx.send(
            "Maximum reminders per user is now set to {}".format(
                await self.config.max_user_reminders()
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
            message_dm = "Here is a list of all of your current reminders:"
            count = 0
            for reminder in to_send:
                count += 1
                message_dm += "\n\n#" + str(count) + ". " + reminder["TEXT"]
            await author.send(message_dm)
            if ctx.message.guild is not None:
                await self.send_message(ctx, "Check your DMs for a full list!")

    @reminder.command(aliases=["add"])
    async def create(
        self, ctx: commands.Context, quantity: int, time_unit: str, *, text: str
    ):
        """Create a reminder.

        Same as [p]remindme
        Accepts: minutes, hours, days, weeks, months
        Example: [p]reminder create 3 days Have sushi with Ryan and Heather
        """
        await self.create_reminder(ctx, quantity, time_unit, text=text)

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
    async def remindme(
        self, ctx: commands.Context, quantity: int, time_unit: str, *, text: str
    ):
        """Send you <text> when the time is up.

        Accepts: minutes, hours, days, weeks, months
        Example: [p]remindme 3 days Have sushi with Ryan and Heather
        """
        await self.create_reminder(ctx, quantity, time_unit, text=text)

    @commands.command()
    async def forgetme(self, ctx: commands.Context):
        """Remove all of your upcoming reminders."""
        await self.delete_reminder(ctx, "all")

    async def create_reminder(
        self, ctx: commands.Context, quantity: int, time_unit: str, text: str
    ):
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

        time_unit = time_unit.lower()
        plural = ""
        if time_unit.endswith("s"):
            time_unit = time_unit[:-1]
        if quantity != 1:
            plural = "s"
        if time_unit not in self.units:
            await self.send_message(
                ctx, "Invalid time unit. Choose minutes/hours/days/weeks/months"
            )
            return
        if quantity < 1:
            await self.send_message(ctx, "Quantity must be greater than 0.")
            return
        if len(text) > 1960:
            await self.send_message(ctx, "Your reminder text is too long.")
            return
        # Get full name of time unit
        for unit_key, unit_value in self.units.items():
            if unit_value == self.units[time_unit]:
                time_unit = unit_key
                break
        seconds = self.units[time_unit] * quantity
        future = int(time.time() + seconds)
        future_text = "{} {}".format(str(quantity), time_unit + plural)

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
                "If anyone else would like to be reminded as well, click the {} below!".format(
                    self.reminder_emoji
                )
            )
            self.me_too_reminders[query.id] = reminder
            await query.add_reaction(self.reminder_emoji)
            await asyncio.sleep(30)
            await query.delete()
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

    async def on_raw_reaction_add(
        self, payload: discord.raw_models.RawReactionActionEvent
    ):
        """Watches for bell reactions on reminder messages."""
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

    async def check_reminders(self):
        """Loop task that sends reminders."""
        await self.bot.wait_until_ready()
        while self.bot.get_cog("RemindMe") == self:
            to_remove = []
            for reminder in await self.config.reminders():
                if reminder["FUTURE"] <= int(time.time()):
                    try:
                        user = discord.utils.get(
                            self.bot.get_all_members(), id=reminder["ID"]
                        )
                        if user is not None:
                            await user.send(
                                "Hello! You asked me to remind you this {} ago:\n{}".format(
                                    reminder["FUTURE_TEXT"], reminder["TEXT"]
                                )
                            )
                        else:
                            # Can't see the user (no shared servers)
                            to_remove.append(reminder)
                    except (discord.errors.Forbidden, discord.errors.NotFound):
                        to_remove.append(reminder)
                    except discord.errors.HTTPException:
                        pass
                    else:
                        to_remove.append(reminder)
            for reminder in to_remove:
                async with self.config.reminders() as current_reminders:
                    current_reminders.remove(reminder)
            await asyncio.sleep(self.time)
