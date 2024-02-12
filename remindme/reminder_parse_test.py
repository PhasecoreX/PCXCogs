"""Unit tests for the reminder parser."""

import unittest

import reminder_parse

parser = reminder_parse.ReminderParser()


class TestCases(unittest.TestCase):
    def test_og(self):
        reminder = "2h reminder!"
        result = parser.parse(reminder)
        expected = {
            "in": {
                "hours": 2,
            },
            "text": "reminder!",
        }
        assert expected == result

    def test_og_long(self):
        reminder = "1y2mo3w4d5h6m7s reminder!"
        result = parser.parse(reminder)
        expected = {
            "in": {
                "years": 1,
                "months": 2,
                "weeks": 3,
                "days": 4,
                "hours": 5,
                "minutes": 6,
                "seconds": 7,
            },
            "text": "reminder!",
        }
        assert expected == result

    def test_in_og_long(self):
        reminder = "in 1y2mo3w4d5h6m7s reminder!"
        result = parser.parse(reminder)
        expected = {
            "in": {
                "years": 1,
                "months": 2,
                "weeks": 3,
                "days": 4,
                "hours": 5,
                "minutes": 6,
                "seconds": 7,
            },
            "text": "reminder!",
        }
        assert expected == result

    def test_in_english(self):
        reminder = "in 1 year, 2 months, 3 weeks, 4 days, 5 hours, 6 minutes, and 7 seconds reminder!"
        result = parser.parse(reminder)
        expected = {
            "in": {
                "years": 1,
                "months": 2,
                "weeks": 3,
                "days": 4,
                "hours": 5,
                "minutes": 6,
                "seconds": 7,
            },
            "text": "reminder!",
        }
        assert expected == result

    def test_in_broken_english(self):
        reminder = "in 1year2 mo, 3w4 day5hour6 mins       , and 7 s reminder!"
        result = parser.parse(reminder)
        expected = {
            "in": {
                "years": 1,
                "months": 2,
                "weeks": 3,
                "days": 4,
                "hours": 5,
                "minutes": 6,
                "seconds": 7,
            },
            "text": "reminder!",
        }
        assert expected == result

    def test_optional_to(self):
        reminder = "to eat in 3 hours"
        result = parser.parse(reminder)
        expected = {
            "in": {
                "hours": 3,
            },
            "text": "eat",
        }
        assert expected == result

    def test_only_in(self):
        reminder = "in 1 year"
        result = parser.parse(reminder)
        expected = {
            "in": {
                "years": 1,
            },
            "text": "",
        }
        assert expected == result

    def test_only_every(self):
        reminder = "every 1 year"
        result = parser.parse(reminder)
        expected = {
            "every": {
                "years": 1,
            },
            "text": "",
        }
        assert expected == result

    def test_in_every(self):
        reminder = "2w every 1 year"
        result = parser.parse(reminder)
        expected = {
            "every": {
                "years": 1,
            },
            "in": {
                "weeks": 2,
            },
            "text": "",
        }
        assert expected == result

    def test_every_in(self):
        reminder = "every 1 year in 3 weeks"
        result = parser.parse(reminder)
        expected = {
            "every": {
                "years": 1,
            },
            "in": {
                "weeks": 3,
            },
            "text": "",
        }
        assert expected == result

    def test_in_text(self):
        reminder = "in 3 weeks to keep coding"
        result = parser.parse(reminder)
        expected = {
            "in": {
                "weeks": 3,
            },
            "text": "keep coding",
        }
        assert expected == result

    def test_text_in(self):
        reminder = "to keep coding in 2 hours"
        result = parser.parse(reminder)
        expected = {
            "in": {
                "hours": 2,
            },
            "text": "keep coding",
        }
        assert expected == result

    def test_every_text(self):
        reminder = "every 3 weeks to keep coding"
        result = parser.parse(reminder)
        expected = {
            "every": {
                "weeks": 3,
            },
            "text": "keep coding",
        }
        assert expected == result

    def test_text_every(self):
        reminder = "to keep coding every 2 hours"
        result = parser.parse(reminder)
        expected = {
            "every": {
                "hours": 2,
            },
            "text": "keep coding",
        }
        assert expected == result

    def test_in_every_text(self):
        reminder = "2w every 1 year to write more code"
        result = parser.parse(reminder)
        expected = {
            "every": {
                "years": 1,
            },
            "in": {
                "weeks": 2,
            },
            "text": "write more code",
        }
        assert expected == result

    def test_every_in_text(self):
        reminder = "every 1 year in 3 weeks to write more code"
        result = parser.parse(reminder)
        expected = {
            "every": {
                "years": 1,
            },
            "in": {
                "weeks": 3,
            },
            "text": "write more code",
        }
        assert expected == result

    def test_in_text_every(self):
        reminder = "12 hrs write more code every 1 month"
        result = parser.parse(reminder)
        expected = {
            "every": {
                "months": 1,
            },
            "in": {
                "hours": 12,
            },
            "text": "write more code",
        }
        assert expected == result

    def test_every_text_in(self):
        reminder = "every 1 month to write more code in 4 hours"
        result = parser.parse(reminder)
        expected = {
            "every": {
                "months": 1,
            },
            "in": {
                "hours": 4,
            },
            "text": "write more code",
        }
        assert expected == result

    def test_text_in_every(self):
        reminder = "to write more unit tests in 8 days and 1 month every 1 week"
        result = parser.parse(reminder)
        expected = {
            "every": {
                "weeks": 1,
            },
            "in": {
                "months": 1,
                "days": 8,
            },
            "text": "write more unit tests",
        }
        assert expected == result

    def test_text_every_in(self):
        reminder = "to write more unit tests every 1 week 3 days in 2 months and 1 day"
        result = parser.parse(reminder)
        expected = {
            "every": {
                "weeks": 1,
                "days": 3,
            },
            "in": {
                "months": 2,
                "days": 1,
            },
            "text": "write more unit tests",
        }
        assert expected == result


# Run unit tests from command line
if __name__ == "__main__":
    unittest.main()
