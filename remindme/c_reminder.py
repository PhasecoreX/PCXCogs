"""Commands for the average user."""

import asyncio
import datetime
from abc import ABC
from contextlib import suppress
from typing import Any

import discord
from dateutil.relativedelta import relativedelta
from pyparsing import ParseException
from redbot.core import commands
from redbot.core.config import Group
from redbot.core.utils.chat_formatting import error
from redbot.core.utils.predicates import MessagePredicate

from .abc import MixinMeta
from .pcx_lib import delete, embed_splitter, reply


class ReminderCommands(MixinMeta, ABC):
    """Commands for the average user."""

    @commands.group()
    async def reminder(self, ctx: commands.Context) -> None:
        """Manage your reminders."""

    @reminder.command(name="list", aliases=["get"])
    async def reminder_list(self, ctx: commands.Context, sort: str = "time") -> None:
        """Show a list of all of your reminders.

        Sort can either be:
        `time` (default) for soonest expiring reminder first,
        `added` for ordering by when the reminder was added,
        `id` for ordering by ID
        """
        # Grab users reminders and format them so that we can see the user_reminder_id
        author = ctx.message.author
        user_reminders = []
        user_reminders_dict = await self.config.custom(
            "REMINDER", str(author.id)
        ).all()  # Does NOT return default values
        for user_reminder_id, reminder in user_reminders_dict.items():
            reminder.update({"user_reminder_id": int(user_reminder_id)})
            user_reminders.append(reminder)

        # Check if they actually have any reminders
        if not user_reminders:
            await reply(ctx, "You don't have any upcoming reminders.")
            return

        # Sort the reminders
        if sort == "time":
            user_reminders.sort(key=lambda reminder_info: reminder_info["expires"])
        elif sort == "added":
            pass
        elif sort == "id":
            user_reminders.sort(
                key=lambda reminder_info: reminder_info["user_reminder_id"]
            )
        else:
            await reply(
                ctx,
                "That is not a valid sorting option. Choose from `time` (default), `added`, or `id`.",
            )
            return

        # Make a pretty embed listing the reminders
        embed = discord.Embed(
            title=f"Reminders for {author.display_name}",
            color=await ctx.embed_color(),
        )
        embed.set_thumbnail(url=author.display_avatar.url)
        for reminder in user_reminders:
            reminder_title = (
                f"ID# {reminder['user_reminder_id']} — <t:{reminder['expires']}:f>"
            )
            if reminder.get("repeat"):
                reminder_title += f", repeating every {self.humanize_relativedelta(reminder['repeat'])}"
            reminder_text = reminder["text"]
            if reminder.get("jump_link"):
                reminder_text += f"\n([original message]({reminder['jump_link']}))"
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
    async def create(
        self, ctx: commands.Context, *, time_and_optional_text: str = ""
    ) -> None:
        """Create a reminder with optional reminder text.

        Same as `[p]remindme`, so check that for usage help.
        """
        await self._create_reminder(ctx, time_and_optional_text)

    @reminder.group(aliases=["edit"])
    async def modify(self, ctx: commands.Context) -> None:
        """Modify an existing reminder."""

    @modify.command()
    async def time(self, ctx: commands.Context, reminder_id: int, *, time: str) -> None:
        """Modify the time of an existing reminder."""
        config_reminder = await self._get_reminder_config_group(
            ctx, ctx.message.author.id, reminder_id
        )
        if not config_reminder:
            return

        # Parse users reminder time and text
        parse_result = await self._parse_time_text(ctx, time, validate_text=False)
        if not parse_result:
            return

        # Save new values
        await config_reminder.created.set(parse_result["created_timestamp_int"])
        await config_reminder.expires.set(parse_result["expires_timestamp_int"])
        if parse_result["repeat_delta"]:
            await config_reminder.repeat.set(
                self.relativedelta_to_dict(parse_result["repeat_delta"])
            )

        # Notify background task
        await self.update_bg_task(
            ctx.message.author.id, reminder_id, await config_reminder.all()
        )

        # Pull repeat dict from config in case we didn't update it
        repeat_dict = await config_reminder.repeat()
        # Send confirmation message
        message = f"Reminder with ID# **{reminder_id}** will remind you in {self.humanize_relativedelta(parse_result['expires_delta'])} from now (<t:{parse_result['expires_timestamp_int']}:f>)"
        if repeat_dict:
            message += f", repeating every {self.humanize_relativedelta(repeat_dict)} thereafter."
        else:
            message += "."
        await reply(ctx, message)

    @modify.command()
    async def repeat(
        self, ctx: commands.Context, reminder_id: int, *, time: str
    ) -> None:
        """Modify the repeating time of an existing reminder. Pass "0" to <time> in order to disable repeating."""
        config_reminder = await self._get_reminder_config_group(
            ctx, ctx.message.author.id, reminder_id
        )
        if not config_reminder:
            return

        # Check for repeat cancel
        if time.lower() in ["0", "stop", "none", "false", "no", "cancel", "n"]:
            await config_reminder.repeat.clear()
            await reply(
                ctx,
                f"Reminder with ID# **{reminder_id}** will not repeat anymore. "
                f"The final reminder will be sent <t:{await config_reminder.expires()}:f>.",
            )
        else:
            # Parse users reminder time and text
            parse_result = await self._parse_time_text(ctx, time, validate_text=False)
            if not parse_result:
                return

            # Save new value
            await config_reminder.repeat.set(
                self.relativedelta_to_dict(parse_result["expires_delta"])
            )

            await reply(
                ctx,
                f"Reminder with ID# **{reminder_id}** will now remind you "
                f"every {self.humanize_relativedelta(parse_result['expires_delta'])}, with the first reminder being sent "
                f"<t:{await config_reminder.expires()}:f>.",
            )

    @modify.command()
    async def text(self, ctx: commands.Context, reminder_id: int, *, text: str) -> None:
        """Modify the text of an existing reminder."""
        config_reminder = await self._get_reminder_config_group(
            ctx, ctx.message.author.id, reminder_id
        )
        if not config_reminder:
            return

        text = text.strip()
        if len(text) > self.MAX_REMINDER_LENGTH:
            await reply(ctx, "Your reminder text is too long.")
            return

        await config_reminder.text.set(text)
        await reply(
            ctx,
            f"Reminder with ID# **{reminder_id}** has been edited successfully.",
        )

    @reminder.command(aliases=["delete", "del"])
    async def remove(self, ctx: commands.Context, index: str) -> None:
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
    ) -> None:
        """Create a reminder with optional reminder text.

        Either of the following formats are allowed:
        `[p]remindme [in] <time> [to] [reminder_text]`
        `[p]remindme [to] [reminder_text] [in] <time>`

        `<time>` supports commas, spaces, and "and":
        `12h30m`, `6 hours 15 minutes`, `2 weeks, 4 days, and 10 seconds`
        Accepts seconds, minutes, hours, days, and weeks.

        You can also add `every <repeat_time>` to the command for repeating reminders.
        `<repeat_time>` accepts days and weeks only, but otherwise is the same as `<time>`.

        Examples
        --------
        `[p]remindme in 8min45sec to do that thing`
        `[p]remindme to water my plants in 2 hours`
        `[p]remindme in 3 days`
        `[p]remindme 8h`
        `[p]remindme every 1 week to take out the trash`
        `[p]remindme in 1 hour to drink some water every 1 day`

        """
        await self._create_reminder(ctx, time_and_optional_text)

    @commands.command()
    async def forgetme(self, ctx: commands.Context) -> None:
        """Remove all of your upcoming reminders."""
        await self._delete_reminder(ctx, "all")

    async def _create_reminder(
        self, ctx: commands.Context, time_and_optional_text: str
    ) -> None:
        """Logic to create a reminder."""
        # Check that user is allowed to make a new reminder
        author = ctx.message.author
        maximum = await self.config.max_user_reminders()
        users_reminders = await self.config.custom(
            "REMINDER", str(author.id)
        ).all()  # Does NOT return default values
        if len(users_reminders) > maximum - 1:
            await self.send_too_many_message(ctx, maximum)
            return

        # Parse users reminder time and text
        parse_result = await self._parse_time_text(ctx, time_and_optional_text)
        if not parse_result:
            # User was already yelled at in _parse_time_text
            return

        # Create basic reminder
        new_reminder = {
            "text": parse_result["reminder_text"],
            "created": parse_result["created_timestamp_int"],
            "expires": parse_result["expires_timestamp_int"],
            "jump_link": ctx.message.jump_url,
        }

        # Check for repeating reminder
        if parse_result["repeat_delta"]:
            new_reminder["repeat"] = self.relativedelta_to_dict(
                parse_result["repeat_delta"]
            )

        # Save reminder for user (also handles notifying background task)
        if not await self.insert_reminder(author.id, new_reminder):
            await self.send_too_many_message(ctx, maximum)
            return

        # Let user know we successfully saved their reminder
        message = f"I will remind you of {'that' if parse_result['reminder_text'] else 'this'} "
        if parse_result["repeat_delta"]:
            message += (
                f"every {self.humanize_relativedelta(parse_result['repeat_delta'])}"
            )
        else:
            message += f"in {self.humanize_relativedelta(parse_result['expires_delta'])} (<t:{parse_result['expires_timestamp_int']}:f>)"
        if (
            parse_result["repeat_delta"]
            and parse_result["expires_delta"] != parse_result["repeat_delta"]
        ):
            message += f", with the first reminder in {self.humanize_relativedelta(parse_result['expires_delta'])} (<t:{parse_result['expires_timestamp_int']}:f>)."
        else:
            message += "."
        await reply(ctx, message)

        # Send "me too" message if enabled
        if (
            ctx.guild
            and await self.config.guild(ctx.guild).me_too()
            and ctx.channel.permissions_for(ctx.guild.me).add_reactions
        ):
            query: discord.Message = await ctx.send(
                f"If anyone else would like {'these reminders' if parse_result['repeat_delta'] else 'to be reminded'} as well, "
                "click the bell below!"
            )
            self.me_too_reminders[query.id] = new_reminder
            self.clicked_me_too_reminder[query.id] = {author.id}
            await query.add_reaction(self.reminder_emoji)
            await asyncio.sleep(30)
            await delete(query)
            del self.me_too_reminders[query.id]
            del self.clicked_me_too_reminder[query.id]

    async def _delete_reminder(self, ctx: commands.Context, index: str) -> None:
        """Logic to delete reminders."""
        if not index:
            return
        author = ctx.message.author

        if index == "all":
            all_users_reminders = self.config.custom("REMINDER", str(author.id))
            if not await all_users_reminders.all():
                await reply(ctx, "You don't have any upcoming reminders.")
                return

            # Ask if the user really wants to do this
            pred = MessagePredicate.yes_or_no(ctx)
            await reply(
                ctx,
                "Are you **sure** you want to remove all of your reminders? (yes/no)",
            )
            with suppress(asyncio.TimeoutError):
                await ctx.bot.wait_for("message", check=pred, timeout=30)
            if pred.result:
                pass
            else:
                await reply(ctx, "I have left your reminders alone.")
                return
            await all_users_reminders.clear()
            # Notify background task
            await self.update_bg_task(author.id)
            await reply(ctx, "All of your reminders have been removed.")
            return

        if index == "last":
            all_users_reminders_dict = await self.config.custom(
                "REMINDER", str(author.id)
            ).all()
            if not all_users_reminders_dict:
                await reply(ctx, "You don't have any upcoming reminders.")
                return

            reminder_id_to_delete = int(list(all_users_reminders_dict)[-1])
            await self.config.custom(
                "REMINDER", str(author.id), str(reminder_id_to_delete)
            ).clear()
            # Notify background task
            await self.update_bg_task(author.id, reminder_id_to_delete)
            await reply(
                ctx,
                f"Your most recently created reminder (ID# **{reminder_id_to_delete}**) has been removed.",
            )
            return

        try:
            int_index = int(index)
        except ValueError:
            await ctx.send_help()
            return

        config_reminder = await self._get_reminder_config_group(
            ctx, author.id, int_index
        )
        if not config_reminder:
            return
        await config_reminder.clear()
        # Notify background task
        await self.update_bg_task(author.id, int_index)
        await reply(ctx, f"Reminder with ID# **{int_index}** has been removed.")

    async def _get_reminder_config_group(
        self, ctx: commands.Context, user_id: int, user_reminder_id: int
    ) -> Group | None:
        config_reminder = self.config.custom(
            "REMINDER", str(user_id), str(user_reminder_id)
        )
        if not await config_reminder.expires():
            await reply(
                ctx,
                f"Reminder with ID# **{user_reminder_id}** does not exist! "
                "Check the reminder list and verify you typed the correct ID#.",
            )
            return None
        return config_reminder

    async def _parse_time_text(
        self,
        ctx: commands.Context,
        time_and_optional_text: str,
        *,
        validate_text: bool = True,
    ) -> dict[str, Any] | None:
        try:
            parse_result = self.reminder_parser.parse(time_and_optional_text.strip())
        except ParseException:
            await reply(
                ctx,
                error(
                    "I couldn't understand the format of your reminder time and text."
                ),
            )
            return None

        created_datetime = datetime.datetime.now(datetime.UTC)
        created_timestamp_int = int(created_datetime.timestamp())

        repeat_dict = parse_result.get("every", None)
        repeat_delta = None
        if repeat_dict:
            repeat_delta = relativedelta(**repeat_dict)
            try:
                # Make sure repeat isn't huge or less than 1 day
                if created_datetime + repeat_delta < created_datetime + relativedelta(
                    days=1
                ):
                    await reply(ctx, "Reminder repeat time must be at least 1 day.")
                    return None
            except (OverflowError, ValueError):
                await reply(ctx, "Reminder repeat time is too large.")
                return None

        expires_dict = parse_result.get("in", repeat_dict)
        if not expires_dict:
            await ctx.send_help()
            return None
        expires_delta = relativedelta(**expires_dict)
        try:
            # Make sure expire time isn't over 9999 years and is at least 1 minute
            if created_datetime + expires_delta < created_datetime + relativedelta(
                minutes=1
            ):
                await reply(ctx, "Reminder time must be at least 1 minute.")
                return None
        except (OverflowError, ValueError):
            await reply(ctx, "Reminder time is too large.")
            return None
        expires_datetime = created_datetime + expires_delta
        expires_timestamp_int = int(expires_datetime.timestamp())

        reminder_text = parse_result.get("text", "")
        if validate_text and len(reminder_text) > self.MAX_REMINDER_LENGTH:
            await reply(ctx, "Your reminder text is too long.")
            return None

        return {
            # Always present, never None
            "created_timestamp_int": created_timestamp_int,
            "expires_delta": expires_delta,
            "expires_timestamp_int": expires_timestamp_int,
            # Optional, could be None/empty string
            "reminder_text": reminder_text,
            "repeat_delta": repeat_delta,
        }
