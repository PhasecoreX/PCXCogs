from abc import ABC

from ..abc import CompositeMetaClass
from .reminder import ReminderCommands
from .remindmeset import RemindMeSetCommands


class Commands(
    ReminderCommands, RemindMeSetCommands, ABC, metaclass=CompositeMetaClass
):
    """Class joining all command subclasses"""
