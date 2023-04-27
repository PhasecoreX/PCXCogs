"""Unit tests for pcx_template."""
import unittest

import pcx_template

renderer = pcx_template.Template()


class Interpolation(unittest.TestCase):
    def test_no_interpolation(self):
        template = "PhasecoreX says {hello}!"
        data = {}
        result = renderer.render(template, data)
        expected = template
        assert expected == result

    def test_basic_interpolation(self):
        template = "Hello, {{subject}}!"
        data = {"subject": "world"}
        result = renderer.render(template, data)
        expected = "Hello, world!"
        assert expected == result

    def test_basic_integer_interpolation(self):
        template = '"{{mph}} miles an hour!"'
        data = {"mph": 88}
        result = renderer.render(template, data)
        expected = '"88 miles an hour!"'
        assert expected == result

    def test_basic_float_interpolation(self):
        template = '"{{power}} jiggawatts!"'
        data = {"power": 1.210}
        result = renderer.render(template, data)
        expected = '"1.21 jiggawatts!"'
        assert expected == result

    def test_basic_context_miss_interpolation(self):
        template = "I ({{cannot}}) be seen!"
        data = {}
        result = renderer.render(template, data)
        expected = "I () be seen!"
        assert expected == result

    # Dotted Names

    def test_dotted_names_arbitrary_depth(self):
        template = '"{{a.b.c.d.e.name}}" == "Phil"'
        data = {"a": {"b": {"c": {"d": {"e": {"name": "Phil"}}}}}}
        result = renderer.render(template, data)
        expected = '"Phil" == "Phil"'
        assert expected == result

    def test_dotted_names_broken_chains(self):
        template = '"{{a.b.c}}" == ""'
        data = {"a": {}}
        result = renderer.render(template, data)
        expected = '"" == ""'
        assert expected == result

    def test_dotted_names_broken_chain_resolution(self):
        template = '"{{a.b.c.name}}" == ""'
        data = {"a": {"b": {}}, "c": {"name": "Jim"}}
        result = renderer.render(template, data)
        expected = '"" == ""'
        assert expected == result

    # Whitespace Sensitivity

    def test_interpolation_surrounding_whitespace(self):
        template = "| {{string}} |"
        data = {"string": "---"}
        result = renderer.render(template, data)
        expected = "| --- |"
        assert expected == result

    def test_interpolation_standalone(self):
        template = "  {{string}}\n"
        data = {"string": "---"}
        result = renderer.render(template, data)
        expected = "  ---\n"
        assert expected == result

    # Whitespace Insensitivity

    def test_interpolation_with_padding(self):
        template = "|{{ string }}|"
        data = {"string": "---"}
        result = renderer.render(template, data)
        expected = "|---|"
        assert expected == result


class IfStatement(unittest.TestCase):
    def test_truthy(self):
        template = '"{% if boolean %}This should be rendered.{% endif %}"'
        data = {"boolean": True}
        result = renderer.render(template, data)
        expected = '"This should be rendered."'
        assert expected == result

    def test_falsey(self):
        template = '"{% if boolean %}This should not be rendered.{% endif %}"'
        data = {"boolean": False}
        result = renderer.render(template, data)
        expected = '""'
        assert expected == result

    def test_empty_lists(self):
        template = '"{% if list %}Yay lists!{% endif %}"'
        data = {"list": []}
        result = renderer.render(template, data)
        expected = '""'
        assert expected == result

    def test_doubled(self):
        template = """{% if bool %}
* first
{% endif %}
* {{two}}
{% if bool %}
* third
{% endif %}
"""
        data = {"bool": True, "two": "second"}
        result = renderer.render(template, data)
        expected = """* first
* second
* third
"""
        assert expected == result

    def test_nested_truthy(self):
        template = "| A {% if bool %}B {% if bool %}C{% endif %} D{% endif %} E |"
        data = {"bool": True}
        result = renderer.render(template, data)
        expected = "| A B C D E |"
        assert expected == result

    def test_nested_falsey(self):
        template = "| A {% if bool %}B {% if bool %}C{% endif %} D{% endif %} E |"
        data = {"bool": False}
        result = renderer.render(template, data)
        expected = "| A  E |"
        assert expected == result

    def test_context_misses(self):
        template = "[{% if missing %}Found key 'missing'!{% endif %}]"
        data = {}
        result = renderer.render(template, data)
        expected = "[]"
        assert expected == result

    # Dotted Names

    def test_dotted_names_truthy(self):
        template = '"{% if a.b.c %}Here{% endif %}" == "Here"'
        data = {"a": {"b": {"c": True}}}
        result = renderer.render(template, data)
        expected = '"Here" == "Here"'
        assert expected == result

    def test_dotted_names_falsey(self):
        template = '"{% if a.b.c %}Here{% endif %}" == ""'
        data = {"a": {"b": {"c": False}}}
        result = renderer.render(template, data)
        expected = '"" == ""'
        assert expected == result

    def test_dotted_names_broken_chains(self):
        template = '"{% if a.b.c %}Here{% endif %}" == ""'
        data = {"a": {}}
        result = renderer.render(template, data)
        expected = '"" == ""'
        assert expected == result

    # Whitespace Sensitivity

    def test_surrounding_whitespace(self):
        template = " | {% if boolean %}\t|\t{% endif %} | \n"
        data = {"boolean": True}
        result = renderer.render(template, data)
        expected = " | \t|\t | \n"
        assert expected == result

    def test_internal_whitespace(self):
        template = " | {% if boolean %} {# Important Whitespace #}\n {% endif %} | \n"
        data = {"boolean": True}
        result = renderer.render(template, data)
        expected = " |  \n  | \n"
        assert expected == result

    def test_indented_inline_sections(self):
        template = " {% if boolean %}YES{% endif %}\n {% if boolean %}GOOD{% endif %}\n"
        data = {"boolean": True}
        result = renderer.render(template, data)
        expected = " YES\n GOOD\n"
        assert expected == result

    def test_standalone_lines(self):
        template = """| This Is
{% if boolean %}
|
{% endif %}
| A Line
"""
        data = {"boolean": True}
        result = renderer.render(template, data)
        expected = """| This Is
|
| A Line
"""
        assert expected == result

    def test_indented_standalone_lines(self):
        template = """| This Is
  {% if boolean %}
|
  {% endif %}
| A Line
"""
        data = {"boolean": True}
        result = renderer.render(template, data)
        expected = """| This Is
|
| A Line
"""
        assert expected == result

    def test_standalone_line_endings(self):
        template = "|\r\n{% if boolean %}\r\n{% endif %}\r\n|"
        data = {"boolean": True}
        result = renderer.render(template, data)
        expected = "|\r\n|"
        assert expected == result

    def test_standalone_without_previous_line(self):
        template = "  {% if boolean %}\n#{% endif %}\n/"
        data = {"boolean": True}
        result = renderer.render(template, data)
        expected = "#\n/"
        assert expected == result

    def test_standalone_without_newline(self):
        template = "#{% if boolean %}\n/\n  {% endif %}"
        data = {"boolean": True}
        result = renderer.render(template, data)
        expected = "#\n/\n"
        assert expected == result

    # Whitespace Insensitivity

    def test_padding(self):
        template = "|{%      if      boolean%}={%    endif          %}|"
        data = {"boolean": True}
        result = renderer.render(template, data)
        expected = "|=|"
        assert expected == result


class IfNotStatement(unittest.TestCase):
    def test_falsey(self):
        template = '"{% if not boolean %}This should be rendered.{% endif %}"'
        data = {"boolean": False}
        result = renderer.render(template, data)
        expected = '"This should be rendered."'
        assert expected == result

    def test_truthy(self):
        template = '"{% if not boolean %}This should not be rendered.{% endif %}"'
        data = {"boolean": True}
        result = renderer.render(template, data)
        expected = '""'
        assert expected == result

    def test_empty_list(self):
        template = '"{% if not list %}Yay lists!{% endif %}"'
        data = {"list": []}
        result = renderer.render(template, data)
        expected = '"Yay lists!"'
        assert expected == result

    def test_doubled(self):
        template = """{% if not bool %}
* first
{% endif %}
* {{two}}
{% if not bool %}
* third
{% endif %}
"""
        data = {"bool": False, "two": "second"}
        result = renderer.render(template, data)
        expected = """* first
* second
* third
"""
        assert expected == result

    def test_nested_falsey(self):
        template = (
            "| A {% if not bool %}B {% if not bool %}C{% endif %} D{% endif %} E |"
        )
        data = {"bool": False}
        result = renderer.render(template, data)
        expected = "| A B C D E |"
        assert expected == result

    def test_nested_truthy(self):
        template = (
            "| A {% if not bool %}B {% if not bool %}C{% endif %} D{% endif %} E |"
        )
        data = {"bool": True}
        result = renderer.render(template, data)
        expected = "| A  E |"
        assert expected == result

    def test_context_misses(self):
        template = "[{% if not missing %}Cannot find key 'missing'!{% endif %}]"
        data = {}
        result = renderer.render(template, data)
        expected = "[Cannot find key 'missing'!]"
        assert expected == result

    # Dotted Names

    def test_dotted_names_truthy(self):
        template = '"{% if not a.b.c %}Here{% endif %}" == ""'
        data = {"a": {"b": {"c": True}}}
        result = renderer.render(template, data)
        expected = '"" == ""'
        assert expected == result

    def test_dotted_names_falsey(self):
        template = '"{% if not a.b.c %}Not Here{% endif %}" == "Not Here"'
        data = {"a": {"b": {"c": False}}}
        result = renderer.render(template, data)
        expected = '"Not Here" == "Not Here"'
        assert expected == result

    def test_dotted_names_broken_chains(self):
        template = '"{% if not a.b.c %}Not Here{% endif %}" == "Not Here"'
        data = {"a": {}}
        result = renderer.render(template, data)
        expected = '"Not Here" == "Not Here"'
        assert expected == result

    # Whitespace Sensitivity

    def test_surrounding_whitespace(self):
        template = " | {% if not boolean %}\t|\t{% endif %} | \n"
        data = {"boolean": False}
        result = renderer.render(template, data)
        expected = " | \t|\t | \n"
        assert expected == result

    def test_internal_whitespace(self):
        template = (
            " | {% if not boolean %} {# Important Whitespace #}\n {% endif %} | \n"
        )
        data = {"boolean": False}
        result = renderer.render(template, data)
        expected = " |  \n  | \n"
        assert expected == result

    def test_indented_inline_sections(self):
        template = " {% if not boolean %}YES{% endif %}\n {% if not boolean %}GOOD{% endif %}\n"
        data = {"boolean": False}
        result = renderer.render(template, data)
        expected = " YES\n GOOD\n"
        assert expected == result

    def test_standalone_lines(self):
        template = """| This Is
{% if not boolean %}
|
{% endif %}
| A Line
"""
        data = {"boolean": False}
        result = renderer.render(template, data)
        expected = """| This Is
|
| A Line
"""
        assert expected == result

    def test_indented_standalone_lines(self):
        template = """| This Is
  {% if not boolean %}
|
  {% endif %}
| A Line
"""
        data = {"boolean": False}
        result = renderer.render(template, data)
        expected = """| This Is
|
| A Line
"""
        assert expected == result

    def test_standalone_line_endings(self):
        template = "|\r\n{% if not boolean %}\r\n{% endif %}\r\n|"
        data = {"boolean": False}
        result = renderer.render(template, data)
        expected = "|\r\n|"
        assert expected == result

    def test_standalone_without_previous_line(self):
        template = "  {% if not boolean %}\n#{% endif %}\n/"
        data = {"boolean": False}
        result = renderer.render(template, data)
        expected = "#\n/"
        assert expected == result

    def test_standalone_without_newline(self):
        template = "#{% if not boolean %}\n/\n  {% endif %}"
        data = {"boolean": False}
        result = renderer.render(template, data)
        expected = "#\n/\n"
        assert expected == result

    # Whitespace Insensitivity

    def test_padding(self):
        template = "|{%      if     not    boolean%}={%    endif          %}|"
        data = {"boolean": False}
        result = renderer.render(template, data)
        expected = "|=|"
        assert expected == result


class ElseStatement(unittest.TestCase):
    def test_else(self):
        template = "{% if 1 > 2 %}Bad...{% else %}Good!{% endif %}"
        data = {}
        result = renderer.render(template, data)
        expected = "Good!"
        assert expected == result


class ElifStatement(unittest.TestCase):
    def test_elif(self):
        template = "{% if 1 > 2 %}Bad if...{% elif 2 == 3 %}Bad elif 1...{% elif 1 == 1 %}Good!{% elif 1 == 2 %}Bad elif 2...{% else %}Bad else...{% endif %}"
        data = {}
        result = renderer.render(template, data)
        expected = "Good!"
        assert expected == result


class Comment(unittest.TestCase):
    def test_inline(self):
        template = "12345{# Comment Block! #}67890"
        data = {}
        result = renderer.render(template, data)
        expected = "1234567890"
        assert expected == result

    def test_multiline(self):
        template = """12345{#
  This is a
  multi-line comment...
#}67890
"""
        data = {}
        result = renderer.render(template, data)
        expected = """1234567890
"""
        assert expected == result

    def test_standalone(self):
        template = """Begin.
{# Comment Block! #}
End.
"""
        data = {}
        result = renderer.render(template, data)
        expected = """Begin.
End.
"""
        assert expected == result

    def test_indented_standalone(self):
        template = """Begin.
  {# Indented Comment Block! #}
End.
"""
        data = {}
        result = renderer.render(template, data)
        expected = """Begin.
End.
"""
        assert expected == result

    def test_standalone_line_endings(self):
        template = "|\r\n{# Standalone Comment #}\r\n|"
        data = {}
        result = renderer.render(template, data)
        expected = "|\r\n|"
        assert expected == result

    def test_standalone_without_previous_line(self):
        template = "  {# I'm Still Standalone #}\n!"
        data = {}
        result = renderer.render(template, data)
        expected = "!"
        assert expected == result

    def test_standalone_without_newline(self):
        template = "!\n  {# I'm Still Standalone #}"
        data = {}
        result = renderer.render(template, data)
        expected = "!\n"
        assert expected == result

    def test_multiline_standalone(self):
        template = """Begin.
{#
Something's going on here...
#}
End.
"""
        data = {}
        result = renderer.render(template, data)
        expected = """Begin.
End.
"""
        assert expected == result

    def test_indented_multiline_standalone(self):
        template = """Begin.
  {#
    Something's going on here...
  #}
End.
"""
        data = {}
        result = renderer.render(template, data)
        expected = """Begin.
End.
"""
        assert expected == result

    def test_indented_inline(self):
        template = "  12 {# 34 #}\n"
        data = {}
        result = renderer.render(template, data)
        expected = "  12 \n"
        assert expected == result

    def test_surrounding_whitespace(self):
        template = "12345 {# Comment Block! #} 67890"
        data = {}
        result = renderer.render(template, data)
        expected = "12345  67890"
        assert expected == result


class Filter(unittest.TestCase):
    def test_invalid(self):
        template = "{{words | invalidFilter}}"
        data = {"words": "This won't be changed"}
        result = renderer.render(template, data)
        expected = "This won't be changed"
        assert expected == result

    def test_lower(self):
        template = "{{word | lower}}"
        data = {"word": "QUIET"}
        result = renderer.render(template, data)
        expected = "quiet"
        assert expected == result

    def test_upper(self):
        template = "{{word | upper}}"
        data = {"word": "loud"}
        result = renderer.render(template, data)
        expected = "LOUD"
        assert expected == result

    def test_multiple(self):
        template = "{{word | upper | lower | upper | lower | upper | lower | upper | lower | upper}}"
        data = {"word": "loud"}
        result = renderer.render(template, data)
        expected = "LOUD"
        assert expected == result


# Run unit tests from command line
if __name__ == "__main__":
    unittest.main()
