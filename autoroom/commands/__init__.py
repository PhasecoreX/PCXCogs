from abc import ABC

from ..abc import CompositeMetaClass
from .autoroom import AutoRoomCommands
from .autoroomset import AutoRoomSetCommands


class Commands(
    AutoRoomCommands, AutoRoomSetCommands, ABC, metaclass=CompositeMetaClass
):
    """Class joining all command subclasses"""
