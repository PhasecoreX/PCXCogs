from abc import ABC, abstractmethod
from redbot.core import commands, Config
from redbot.core.bot import Red


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """This allows the metaclass used for proper type detection to coexist with discord.py's metaclass."""


class MixinMeta(ABC):
    """Base class for well behaved type hint detection with composite class.

    Basically, to keep developers sane when not all attributes are defined in each mixin.
    """

    bot: Red
    config: Config
    me_too_reminders: dict
    reminder_emoji: str

    @abstractmethod
    async def get_user_reminders(self, user_id: int):
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def get_next_user_reminder_id(reminder_list):
        raise NotImplementedError()
