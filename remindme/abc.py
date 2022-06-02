from abc import ABC, abstractmethod
from typing import Dict, Set, Union

import discord
from dateutil.relativedelta import relativedelta
from redbot.core import Config, commands

from .reminder_parse import ReminderParser


class MixinMeta(ABC):
    """Base class for well-behaved type hint detection with composite class.

    Basically, to keep developers sane when not all attributes are defined in each mixin.
    """

    config: Config
    reminder_parser: ReminderParser
    me_too_reminders: Dict[int, dict]
    clicked_me_too_reminder: Dict[int, Set[int]]
    reminder_emoji: str

    @staticmethod
    @abstractmethod
    def humanize_relativedelta(relative_delta: Union[relativedelta, dict]):
        raise NotImplementedError()

    @abstractmethod
    async def insert_reminder(self, user_id: int, reminder: dict):
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def relativedelta_to_dict(relative_delta: relativedelta):
        raise NotImplementedError()

    @abstractmethod
    async def send_too_many_message(
        self, ctx_or_user: Union[commands.Context, discord.User], maximum: int = -1
    ):
        raise NotImplementedError()

    @abstractmethod
    async def update_bg_task(
        self, user_id: int, user_reminder_id: int = None, partial_reminder: dict = None
    ):
        raise NotImplementedError()
