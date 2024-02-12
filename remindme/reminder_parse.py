"""A parser for remindme commands."""

from typing import Any

from pyparsing import (
    CaselessLiteral,
    Group,
    Literal,
    Optional,
    ParserElement,
    SkipTo,
    StringEnd,
    Suppress,
    Word,
    ZeroOrMore,
    nums,
    tokenMap,
)

__author__ = "PhasecoreX"


class ReminderParser:
    """A parser for remindme commands."""

    def __init__(self) -> None:
        """Set up the parser."""
        ParserElement.enablePackrat()

        unit_years = (
            CaselessLiteral("years") | CaselessLiteral("year") | CaselessLiteral("y")
        )
        years = (
            Word(nums).setParseAction(lambda token_list: [int(str(token_list[0]))])(
                "years"
            )
            + unit_years
        )
        unit_months = (
            CaselessLiteral("months") | CaselessLiteral("month") | CaselessLiteral("mo")
        )
        months = (
            Word(nums).setParseAction(lambda token_list: [int(str(token_list[0]))])(
                "months"
            )
            + unit_months
        )
        unit_weeks = (
            CaselessLiteral("weeks") | CaselessLiteral("week") | CaselessLiteral("w")
        )
        weeks = (
            Word(nums).setParseAction(lambda token_list: [int(str(token_list[0]))])(
                "weeks"
            )
            + unit_weeks
        )
        unit_days = (
            CaselessLiteral("days") | CaselessLiteral("day") | CaselessLiteral("d")
        )
        days = (
            Word(nums).setParseAction(lambda token_list: [int(str(token_list[0]))])(
                "days"
            )
            + unit_days
        )
        unit_hours = (
            CaselessLiteral("hours")
            | CaselessLiteral("hour")
            | CaselessLiteral("hrs")
            | CaselessLiteral("hr")
            | CaselessLiteral("h")
        )
        hours = (
            Word(nums).setParseAction(lambda token_list: [int(str(token_list[0]))])(
                "hours"
            )
            + unit_hours
        )
        unit_minutes = (
            CaselessLiteral("minutes")
            | CaselessLiteral("minute")
            | CaselessLiteral("mins")
            | CaselessLiteral("min")
            | CaselessLiteral("m")
        )
        minutes = (
            Word(nums).setParseAction(lambda token_list: [int(str(token_list[0]))])(
                "minutes"
            )
            + unit_minutes
        )
        unit_seconds = (
            CaselessLiteral("seconds")
            | CaselessLiteral("second")
            | CaselessLiteral("secs")
            | CaselessLiteral("sec")
            | CaselessLiteral("s")
        )
        seconds = (
            Word(nums).setParseAction(lambda token_list: [int(str(token_list[0]))])(
                "seconds"
            )
            + unit_seconds
        )

        time_unit = years | months | weeks | days | hours | minutes | seconds
        time_unit_separators = Optional(Literal(",")) + Optional(CaselessLiteral("and"))
        full_time = time_unit + ZeroOrMore(
            Suppress(Optional(time_unit_separators)) + time_unit
        )

        every_time = Group(CaselessLiteral("every") + full_time)("every")
        in_opt_time = Group(Optional(CaselessLiteral("in")) + full_time)("in")
        in_req_time = Group(CaselessLiteral("in") + full_time)("in")

        reminder_text_capture = SkipTo(
            every_time | in_req_time | StringEnd()
        ).setParseAction(tokenMap(str.strip))
        reminder_text_optional_prefix = Optional(Suppress(CaselessLiteral("to")))
        reminder_text = reminder_text_optional_prefix + reminder_text_capture("text")

        in_every_text = in_opt_time + every_time + reminder_text
        every_in_text = every_time + in_req_time + reminder_text
        in_text_every = in_opt_time + reminder_text + every_time
        every_text_in = every_time + reminder_text + in_req_time
        text_in_every = reminder_text + in_req_time + every_time
        text_every_in = reminder_text + every_time + in_req_time

        in_text = in_opt_time + reminder_text
        text_in = reminder_text + in_req_time
        every_text = every_time + reminder_text
        text_every = reminder_text + every_time

        template = (
            in_every_text
            | every_in_text
            | in_text_every
            | every_text_in
            | text_in_every
            | text_every_in
            | in_text
            | text_in
            | every_text
            | text_every
        )

        self.parser = template

    def parse(self, text: str) -> dict[str, Any]:
        """Parse text into a reminder config dict."""
        parsed = self.parser.parseString(text, parseAll=True)
        return parsed.asDict()
