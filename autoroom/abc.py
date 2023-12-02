"""ABC for the AutoRoom Cog."""
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import discord
from discord.ext.commands import CooldownMapping
from redbot.core import Config
from redbot.core.bot import Red

from autoroom.pcx_template import Template


class MixinMeta(ABC):
    """Base class for well-behaved type hint detection with composite class.

    Basically, to keep developers sane when not all attributes are defined in each mixin.
    """

    bot: Red
    config: Config
    template: Template
    bucket_autoroom_name: CooldownMapping
    bucket_autoroom_owner_claim: CooldownMapping
    extra_channel_name_change_delay: int

    perms_public: dict[str, bool]
    perms_locked: dict[str, bool]
    perms_private: dict[str, bool]
    perms_autoroom_owner: dict[str, bool]

    perms_legacy_text_allow: ClassVar[dict[str, bool]]
    perms_legacy_text_reset: ClassVar[dict[str, None]]
    perms_autoroom_owner_legacy_text: ClassVar[dict[str, bool]]

    @staticmethod
    @abstractmethod
    def get_template_data(member: discord.Member | discord.User) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def format_template_room_name(self, template: str, data: dict, num: int = 1) -> str:
        raise NotImplementedError

    @abstractmethod
    async def is_admin_or_admin_role(self, who: discord.Role | discord.Member) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def is_mod_or_mod_role(self, who: discord.Role | discord.Member) -> bool:
        raise NotImplementedError

    @abstractmethod
    def check_perms_source_dest(
        self,
        autoroom_source: discord.VoiceChannel,
        category_dest: discord.CategoryChannel,
        *,
        with_manage_roles_guild: bool = False,
        with_legacy_text_channel: bool = False,
        with_optional_clone_perms: bool = False,
        detailed: bool = False,
    ) -> tuple[bool, bool, str | None]:
        raise NotImplementedError

    @abstractmethod
    async def get_all_autoroom_source_configs(
        self, guild: discord.Guild
    ) -> dict[int, dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_autoroom_source_config(
        self, autoroom_source: discord.VoiceChannel
    ) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    async def get_autoroom_info(
        self, autoroom: discord.VoiceChannel | None
    ) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    async def get_autoroom_legacy_text_channel(
        self, autoroom: discord.VoiceChannel
    ) -> discord.TextChannel | None:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def check_if_member_or_role_allowed(
        channel: discord.VoiceChannel,
        member_or_role: discord.Member | discord.Role,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_member_roles(
        self, autoroom_source: discord.VoiceChannel
    ) -> list[discord.Role]:
        raise NotImplementedError

    @abstractmethod
    async def get_bot_roles(self, guild: discord.Guild) -> list[discord.Role]:
        raise NotImplementedError
