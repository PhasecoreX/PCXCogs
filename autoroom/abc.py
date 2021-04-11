from abc import ABC, abstractmethod
from typing import List, Union

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red

from autoroom.pcx_template import Template


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """This allows the metaclass used for proper type detection to coexist with discord.py's metaclass."""


class MixinMeta(ABC):
    """Base class for well behaved type hint detection with composite class.

    Basically, to keep developers sane when not all attributes are defined in each mixin.
    """

    bot: Red
    config: Config
    template: Template

    @staticmethod
    @abstractmethod
    def get_template_data(member: discord.Member):
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def format_template_room_name(template: str, data: dict, num: int = 0):
        raise NotImplementedError()

    @abstractmethod
    async def get_member_roles_for_source(
        self, autoroom_source: discord.VoiceChannel
    ) -> List[discord.Role]:
        raise NotImplementedError()

    @abstractmethod
    async def is_admin_or_admin_role(self, who: Union[discord.Role, discord.Member]):
        raise NotImplementedError()

    @abstractmethod
    async def is_mod_or_mod_role(self, who: Union[discord.Role, discord.Member]):
        raise NotImplementedError()

    @abstractmethod
    async def check_all_perms(self, guild: discord.Guild, detailed=False):
        raise NotImplementedError()

    @abstractmethod
    async def check_perms_source_dest(
        self,
        autoroom_source: discord.VoiceChannel,
        category_dest: discord.CategoryChannel,
        detailed=False,
    ):
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    async def check_perms_guild(
        guild: discord.Guild,
        detailed=False,
    ):
        raise NotImplementedError()

    @abstractmethod
    async def get_all_autoroom_source_configs(self, guild: discord.guild):
        raise NotImplementedError()

    @abstractmethod
    async def get_autoroom_source_config(self, autoroom_source: discord.VoiceChannel):
        raise NotImplementedError()
