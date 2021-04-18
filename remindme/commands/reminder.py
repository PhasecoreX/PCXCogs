import asyncio
import re
import time as current_time
from abc import ABC
from datetime import timedelta

import discord
from discord.ext.commands import BadArgument
from redbot.core import commands
from redbot.core.commands import parse_timedelta
from redbot.core.utils.chat_formatting import humanize_timedelta
from redbot.core.utils.predicates import MessagePredicate

from ..abc import CompositeMetaClass, MixinMeta
from ..pcx_lib import delete, embed_splitter, reply


class ReminderCommands(MixinMeta, ABC, metaclass=CompositeMetaClass):
    def __init__(self):
        optional_in_every = r"(in\s+|every\s+)?"
        amount_and_time = r"\d+\s*(weeks?|w|days?|d|hours?|hrs|hr?|minutes?|mins?|m(?!o)|seconds?|secs?|s)"
        optional_comma_space_and = r"[\s,]*(and)?\s*"

        self.timedelta_begin = re.compile(
            r"^"
            + optional_in_every
            + r"("
            + amount_and_time
            + r"("
            + optional_comma_space_and
            + amount_and_time
            + r")*"
            + r")"
            + r"\b"
        )
        self.timedelta_end = re.compile(
            r"\b"
            + optional_in_every
            + r"("
            + amount_and_time
            + r"("
            + optional_comma_space_and
            + amount_and_time
            + r")*"
            + r")"
            + r"$"
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
            to_send.sort(key=lambda reminder_info: reminder_info["FUTURE"])
        elif sort == "added":
            pass
        elif sort == "id":
            to_send.sort(key=lambda reminder_info: reminder_info["USER_REMINDER_ID"])
        else:
            await reply(
                ctx,
                "That is not a valid sorting option. Choose from `time` (default), `added`, or `id`.",
            )
            return

        if not to_send:
            await reply(ctx, "You don't have any upcoming reminders.")
            return

        embed = discord.Embed(
            title=f"Reminders for {author.display_name}",
            color=await ctx.embed_color(),
        )
        embed.set_thumbnail(url=author.avatar_url)
        current_time_seconds = int(current_time.time())
        for reminder in to_send:
            delta = reminder["FUTURE"] - current_time_seconds
            reminder_title = "ID# {} — {}".format(
                reminder["USER_REMINDER_ID"],
                "In {}".format(humanize_timedelta(seconds=delta))
                if delta > 0
                else "Now!",
            )
            if "REPEAT" in reminder and reminder["REPEAT"]:
                reminder_title = (
                    f"{reminder_title.rstrip('!')}, "
                    f"repeating every {humanize_timedelta(seconds=reminder['REPEAT'])}"
                )
            reminder_text = reminder["REMINDER"]
            if "JUMP_LINK" in reminder:
                reminder_text += f"\n([original message]({reminder['JUMP_LINK']}))"
            reminder_text = reminder_text or "(no reminder text or jump link)"
            embed.add_field(
                name=reminder_title,
                value=reminder_text,
                inline=False,
            )
        try:
            await embed_splitter(embed, author)
            if ctx.guild:
                await ctx.tick()
        except discord.Forbidden:
            await reply(ctx, "I can't DM you...")

    @reminder.command(aliases=["add"])
    async def create(self, ctx: commands.Context, *, time_and_optional_text: str = ""):
        """Create a reminder with optional reminder text.

        Same as `[p]remindme`, so check that for usage help.
        """
        await self._create_reminder(ctx, time_and_optional_text)

    @reminder.group(aliases=["edit"])
    async def modify(self, ctx: commands.Context):
        """Modify an existing reminder."""
        pass

    @modify.command()
    async def time(self, ctx: commands.Context, reminder_id: int, *, time: str):
        """Modify the time of an existing reminder."""
        users_reminders = await self.get_user_reminders(ctx.message.author.id)
        old_reminder = self._get_reminder(users_reminders, reminder_id)
        if not old_reminder:
            await self._send_non_existent_msg(ctx, reminder_id)
            return
        try:
            time_delta = parse_timedelta(time, minimum=timedelta(minutes=1))
            if not time_delta:
                await ctx.send_help()
                return
        except commands.BadArgument as ba:
            await reply(ctx, str(ba))
            return
        future = int(current_time.time() + time_delta.total_seconds())
        future_text = humanize_timedelta(timedelta=time_delta)

        new_reminder = old_reminder.copy()
        new_reminder.update(FUTURE=future, FUTURE_TEXT=future_text)
        async with self.config.reminders() as current_reminders:
            current_reminders.remove(old_reminder)
            current_reminders.append(new_reminder)
        message = (
            f"Reminder with ID# **{reminder_id}** will now remind you in {future_text}"
        )
        if "REPEAT" in new_reminder and new_reminder["REPEAT"]:
            message += f", repeating every {humanize_timedelta(seconds=new_reminder['REPEAT'])} thereafter."
        else:
            message += "."
        await reply(ctx, message)

    @modify.command()
    async def repeat(self, ctx: commands.Context, reminder_id: int, *, time: str):
        """Modify the repeating time of an existing reminder. Pass "0" to <time> in order to disable repeating."""
        users_reminders = await self.get_user_reminders(ctx.message.author.id)
        old_reminder = self._get_reminder(users_reminders, reminder_id)
        if not old_reminder:
            await self._send_non_existent_msg(ctx, reminder_id)
            return
        if time.lower() in ["0", "stop", "none", "false", "no", "cancel", "n"]:
            new_reminder = old_reminder.copy()
            new_reminder.update(REPEAT=None)
            async with self.config.reminders() as current_reminders:
                current_reminders.remove(old_reminder)
                current_reminders.append(new_reminder)
            await reply(
                ctx,
                f"Reminder with ID# **{reminder_id}** will not repeat anymore. The final reminder will be sent "
                f"in {humanize_timedelta(seconds=int(new_reminder['FUTURE'] - current_time.time()))}.",
            )
        else:
            try:
                time_delta = parse_timedelta(
                    time, minimum=timedelta(days=1), allowed_units=["weeks", "days"]
                )
                if not time_delta:
                    await ctx.send_help()
                    return
            except commands.BadArgument as ba:
                await reply(ctx, str(ba))
                return
            new_reminder = old_reminder.copy()
            new_reminder.update(REPEAT=int(time_delta.total_seconds()))
            async with self.config.reminders() as current_reminders:
                current_reminders.remove(old_reminder)
                current_reminders.append(new_reminder)
            await reply(
                ctx,
                f"Reminder with ID# **{reminder_id}** will now remind you "
                f"every {humanize_timedelta(timedelta=time_delta)}, with the first reminder being sent "
                f"in {humanize_timedelta(seconds=int(new_reminder['FUTURE'] - current_time.time()))}.",
            )

    @modify.command()
    async def text(self, ctx: commands.Context, reminder_id: int, *, text: str):
        """Modify the text of an existing reminder."""
        users_reminders = await self.get_user_reminders(ctx.message.author.id)
        old_reminder = self._get_reminder(users_reminders, reminder_id)
        if not old_reminder:
            await self._send_non_existent_msg(ctx, reminder_id)
            return
        text = text.strip()
        if len(text) > 900:
            await reply(ctx, "Your reminder text is too long.")
            return

        new_reminder = old_reminder.copy()
        new_reminder.update(REMINDER=text)
        async with self.config.reminders() as current_reminders:
            current_reminders.remove(old_reminder)
            current_reminders.append(new_reminder)
        await reply(
            ctx,
            f"Reminder with ID# **{reminder_id}** has been edited successfully.",
        )

    @reminder.command(aliases=["delete", "del"])
    async def remove(self, ctx: commands.Context, index: str):
        """Delete a reminder.

        <index> can either be:
        - a number for a specific reminder to delete
        - `last` to delete the most recently created reminder
        - `all` to delete all reminders (same as [p]forgetme)
        """
        await self._delete_reminder(ctx, index)

    @commands.command()
    async def remindme(
        self, ctx: commands.Context, *, time_and_optional_text: str = ""
    ):
        """Create a reminder with optional reminder text.

        Either of the following formats are allowed:
        `[p]remindme [in] <time> [to] [reminder_text]`
        `[p]remindme [to] [reminder_text] [in] <time>`

        `<time>` supports commas, spaces, and "and":
        `12h30m`, `6 hours 15 minutes`, `2 weeks, 4 days, and 10 seconds`
        Accepts seconds, minutes, hours, days, and weeks.

        You can also add `every <repeat_time>` to the command for repeating reminders.
        `<repeat_time>` accepts days and weeks only, but otherwise is the same as `<time>`.

        Examples:
        `[p]remindme in 8min45sec to do that thing`
        `[p]remindme to water my plants in 2 hours`
        `[p]remindme in 3 days`
        `[p]remindme 8h`
        `[p]remindme every 1 week to take out the trash`
        `[p]remindme in 1 hour to drink some water every 1 day`
        """
        await self._create_reminder(ctx, time_and_optional_text)

    @commands.command()
    async def forgetme(self, ctx: commands.Context):
        """Remove all of your upcoming reminders."""
        await self._delete_reminder(ctx, "all")

    async def _create_reminder(
        self, ctx: commands.Context, time_and_optional_text: str
    ):
        """Logic to create a reminder."""
        author = ctx.message.author
        maximum = await self.config.max_user_reminders()
        users_reminders = await self.get_user_reminders(author.id)
        if len(users_reminders) > maximum - 1:
            plural = "reminder" if maximum == 1 else "reminders"
            await reply(
                ctx,
                "You have too many reminders! "
                f"I can only keep track of {maximum} {plural} for you at a time.",
            )
            return

        try:
            (
                reminder_time,
                reminder_time_repeat,
                reminder_text,
            ) = self._process_reminder_text(time_and_optional_text.strip())
        except commands.BadArgument as ba:
            await reply(ctx, str(ba))
            return
        if not reminder_time:
            await ctx.send_help()
            return
        if len(reminder_text) > 900:
            await reply(ctx, "Your reminder text is too long.")
            return

        next_reminder_id = self.get_next_user_reminder_id(users_reminders)
        repeat = (
            int(reminder_time_repeat.total_seconds()) if reminder_time_repeat else None
        )
        future = int(current_time.time() + reminder_time.total_seconds())
        future_text = humanize_timedelta(timedelta=reminder_time)

        reminder = {
            "USER_REMINDER_ID": next_reminder_id,
            "USER_ID": author.id,
            "REMINDER": reminder_text,
            "REPEAT": repeat,
            "FUTURE": future,
            "FUTURE_TEXT": future_text,
            "JUMP_LINK": ctx.message.jump_url,
        }
        async with self.config.reminders() as current_reminders:
            current_reminders.append(reminder)
        message = f"I will remind you of {'that' if reminder_text else 'this'} "
        if repeat:
            message += f"every {humanize_timedelta(timedelta=reminder_time_repeat)}"
        else:
            message += f"in {future_text}"
        if repeat and reminder_time_repeat != reminder_time:
            message += f", with the first reminder in {future_text}."
        else:
            message += "."
        await reply(ctx, message)

        if (
            ctx.guild
            and await self.config.guild(ctx.guild).me_too()
            and ctx.channel.permissions_for(ctx.me).add_reactions
        ):
            query: discord.Message = await ctx.send(
                f"If anyone else would like {'these reminders' if repeat else 'to be reminded'} as well, "
                "click the bell below!"
            )
            self.me_too_reminders[query.id] = reminder
            await query.add_reaction(self.reminder_emoji)
            await asyncio.sleep(30)
            await delete(query)
            del self.me_too_reminders[query.id]

    def _process_reminder_text(self, reminder_text):
        """Completely process the given reminder text into timedeltas, removing them from the reminder text.

        Takes all "every {time_repeat}", "in {time}", and "{time}" from the beginning of the reminder_text.
        At most one instance of "every {time_repeat}" and one instance of "in {time}" or "{time}" will be consumed.
        If the parser runs into a timedelta (in or every) that has already been parsed, parsing stops.
        Same process is then repeated from the end of the string.

        If an "every" time is provided but no "in" time, the "every" time will be copied over to the "in" time.
        """

        reminder_time = None
        reminder_time_repeat = None
        # find the time delta(s) at the beginning of the text
        (
            reminder_time,
            reminder_time_repeat,
            reminder_text,
        ) = self._process_reminder_text_from_ends(
            reminder_time, reminder_time_repeat, reminder_text, self.timedelta_begin
        )
        # find the time delta(s) at the end of the text
        (
            reminder_time,
            reminder_time_repeat,
            reminder_text,
        ) = self._process_reminder_text_from_ends(
            reminder_time, reminder_time_repeat, reminder_text, self.timedelta_end
        )
        # cleanup
        reminder_time = reminder_time or reminder_time_repeat
        if len(reminder_text) > 1 and reminder_text[0:2] == "to":
            reminder_text = reminder_text[2:].strip()
        return reminder_time, reminder_time_repeat, reminder_text

    def _process_reminder_text_from_ends(
        self, reminder_time, reminder_time_repeat, reminder_text, search_regex
    ):
        """Repeatedly regex search and modify the reminder_text looking for all instances of timedeltas."""
        while regex_result := search_regex.search(reminder_text):
            repeating = regex_result[1] and regex_result[1].strip() == "every"
            if (repeating and reminder_time_repeat) or (
                not repeating and reminder_time
            ):
                break
            parsed_timedelta = self._parse_timedelta(regex_result[2], repeating)
            if not parsed_timedelta:
                break
            reminder_text = (
                reminder_text[0 : regex_result.span()[0]]
                + reminder_text[regex_result.span()[1] + 1 :]
            ).strip()
            if repeating:
                reminder_time_repeat = parsed_timedelta
            else:
                reminder_time = parsed_timedelta
        return reminder_time, reminder_time_repeat, reminder_text

    @staticmethod
    def _parse_timedelta(timedelta_string, repeating):
        """Parse a timedelta, taking into account if it is a repeating timedelta (day minimum) or not."""
        result = None
        testing_text = ""
        for chunk in timedelta_string.split():
            if chunk == "and":
                continue
            if chunk.isdigit():
                testing_text += chunk
                continue
            testing_text += chunk.rstrip(",")
            if repeating:
                try:
                    parsed = parse_timedelta(
                        testing_text,
                        minimum=timedelta(days=1),
                        allowed_units=["weeks", "days"],
                    )
                except commands.BadArgument as ba:
                    orig_message = str(ba)[0].lower() + str(ba)[1:]
                    raise BadArgument(
                        f"For the repeating portion of this reminder, {orig_message}. "
                        "You must only use `days` or `weeks` when dealing with repeating reminders."
                    )
            else:
                parsed = parse_timedelta(testing_text, minimum=timedelta(minutes=1))
            if parsed != result:
                result = parsed
            else:
                return None
        return result

    async def _delete_reminder(self, ctx: commands.Context, index: str):
        """Logic to delete reminders."""
        if not index:
            return
        author = ctx.message.author
        users_reminders = await self.get_user_reminders(author.id)

        if not users_reminders:
            await reply(ctx, "You don't have any upcoming reminders.")
            return

        if index == "all":
            # Ask if the user really wants to do this
            pred = MessagePredicate.yes_or_no(ctx)
            await reply(
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
                await reply(ctx, "I have left your reminders alone.")
                return
            await self._do_reminder_delete(users_reminders)
            await reply(ctx, "All of your reminders have been removed.")
            return

        if index == "last":
            reminder_to_delete = users_reminders[len(users_reminders) - 1]
            await self._do_reminder_delete(reminder_to_delete)
            await reply(
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

        reminder_to_delete = self._get_reminder(users_reminders, int_index)
        if reminder_to_delete:
            await self._do_reminder_delete(reminder_to_delete)
            await reply(ctx, f"Reminder with ID# **{int_index}** has been removed.")
        else:
            await self._send_non_existent_msg(ctx, int_index)

    async def _do_reminder_delete(self, reminders):
        """Actually delete a reminder."""
        if not reminders:
            return
        if not isinstance(reminders, list):
            reminders = [reminders]
        async with self.config.reminders() as current_reminders:
            for reminder in reminders:
                current_reminders.remove(reminder)

    @staticmethod
    async def _send_non_existent_msg(ctx: commands.Context, reminder_id: int):
        """Send a message telling the user the reminder ID does not exist."""
        await reply(
            ctx,
            f"Reminder with ID# **{reminder_id}** does not exist! "
            "Check the reminder list and verify you typed the correct ID#.",
        )

    @staticmethod
    def _get_reminder(reminder_list, reminder_id: int):
        """Get the reminder from reminder_list with the specified reminder_id."""
        for reminder in reminder_list:
            if reminder["USER_REMINDER_ID"] == reminder_id:
                return reminder
        return None
