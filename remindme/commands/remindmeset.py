from abc import ABC

from ..abc import CompositeMetaClass, MixinMeta
from redbot.core import commands, checks
from ..pcx_lib import SettingDisplay, checkmark


class RemindMeSetCommands(MixinMeta, ABC, metaclass=CompositeMetaClass):
    @commands.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def remindmeset(self, ctx: commands.Context):
        """Manage RemindMe settings."""
        pass

    @remindmeset.command()
    async def settings(self, ctx: commands.Context):
        """Display current settings."""
        guild_section = SettingDisplay("Guild Settings")
        if ctx.guild:
            guild_section.add(
                "Me too",
                "Enabled"
                if await self.config.guild(ctx.guild).me_too()
                else "Disabled",
            )

        if await ctx.bot.is_owner(ctx.author):
            global_section = SettingDisplay("Global Settings")
            global_section.add(
                "Maximum reminders per user", await self.config.max_user_reminders()
            )

            stats_section = SettingDisplay("Stats")
            stats_section.add("Pending reminders", len(await self.config.reminders()))
            stats_section.add("Total reminders sent", await self.config.total_sent())

            await ctx.send(guild_section.display(global_section, stats_section))

        else:
            await ctx.send(guild_section)

    @remindmeset.command()
    @commands.guild_only()
    async def metoo(self, ctx: commands.Context):
        """Toggle the bot asking if others want to be reminded in this guild.

        If the bot doesn't have the Add Reactions permission in the channel, it won't ask regardless.
        """
        me_too = not await self.config.guild(ctx.guild).me_too()
        await self.config.guild(ctx.guild).me_too.set(me_too)
        await ctx.send(
            checkmark(
                f"I will {'now' if me_too else 'no longer'} ask if others want to be reminded."
            )
        )

    @remindmeset.command()
    @checks.is_owner()
    async def max(self, ctx: commands.Context, maximum: int):
        """Global: Set the maximum number of reminders a user can create at one time."""
        await self.config.max_user_reminders.set(maximum)
        await ctx.send(
            checkmark(
                f"Maximum reminders per user is now set to {await self.config.max_user_reminders()}"
            )
        )
