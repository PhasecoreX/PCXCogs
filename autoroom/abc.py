from abc import ABC, abstractmethod
from typing import List, Union

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """This allows the metaclass used for proper type detection to coexist with discord.py's metaclass."""


class MixinMeta(ABC):
    """Base class for well behaved type hint detection with composite class.

    Basically, to keep developers sane when not all attributes are defined in each mixin.
    """

    bot: Red
    config: Config

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
    async def check_required_perms(
        self, guild: discord.guild, also_check_autorooms: bool = False
    ):
        raise NotImplementedError()

    @abstractmethod
    async def get_all_autoroom_source_configs(self, guild: discord.guild):
        raise NotImplementedError()

    @abstractmethod
    async def get_autoroom_source_config(self, autoroom_source: discord.VoiceChannel):
        raise NotImplementedError()
