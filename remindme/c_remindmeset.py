"""Commands for [p]remindmeset."""

from abc import ABC

from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import success

from .abc import MixinMeta
from .pcx_lib import SettingDisplay


class RemindMeSetCommands(MixinMeta, ABC):
    """Commands for [p]remindmeset."""

    @commands.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def remindmeset(self, ctx: commands.Context) -> None:
        """Manage RemindMe settings."""

    @remindmeset.command()
    async def settings(self, ctx: commands.Context) -> None:
        """Display current settings."""
        server_section = SettingDisplay("Server Settings")
        if ctx.guild:
            server_section.add(
                "Me too",
                (
                    "Enabled"
                    if await self.config.guild(ctx.guild).me_too()
                    else "Disabled"
                ),
            )

        if await ctx.bot.is_owner(ctx.author):
            global_section = SettingDisplay("Global Settings")
            global_section.add(
                "Maximum reminders per user", await self.config.max_user_reminders()
            )

            non_repeating_reminders = 0
            repeating_reminders = 0
            all_reminders = await self.config.custom(
                "REMINDER"
            ).all()  # Does NOT return default values
            for users_reminders in all_reminders.values():
                for reminder in users_reminders.values():
                    if reminder.get("repeat"):
                        repeating_reminders += 1
                    else:
                        non_repeating_reminders += 1
            pending_reminders_message = (
                f"{non_repeating_reminders + repeating_reminders}"
            )
            if repeating_reminders:
                pending_reminders_message += (
                    f" ({repeating_reminders} "
                    f"{'is' if repeating_reminders == 1 else 'are'} repeating)"
                )

            stats_section = SettingDisplay("Stats")
            stats_section.add(
                "Pending reminders",
                pending_reminders_message,
            )
            stats_section.add("Total reminders sent", await self.config.total_sent())

            await ctx.send(server_section.display(global_section, stats_section))

        else:
            await ctx.send(str(server_section))

    @remindmeset.command()
    @commands.guild_only()
    async def metoo(self, ctx: commands.Context) -> None:
        """Toggle the bot asking if others want to be reminded in this server.

        If the bot doesn't have the Add Reactions permission in the channel, it won't ask regardless.
        """
        if not ctx.guild:
            return
        me_too = not await self.config.guild(ctx.guild).me_too()
        await self.config.guild(ctx.guild).me_too.set(me_too)
        await ctx.send(
            success(
                f"I will {'now' if me_too else 'no longer'} ask if others want to be reminded."
            )
        )

    @remindmeset.command(name="max")
    @checks.is_owner()
    async def set_max(self, ctx: commands.Context, maximum: int) -> None:
        """Global: Set the maximum number of reminders a user can create at one time."""
        await self.config.max_user_reminders.set(maximum)
        await ctx.send(
            success(
                f"Maximum reminders per user is now set to {await self.config.max_user_reminders()}"
            )
        )
