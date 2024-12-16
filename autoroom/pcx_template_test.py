"""Tests for template engine using Jinja2."""

import pytest
from pcx_template import (
    Template,
    TemplateTimeoutError,
)


@pytest.mark.asyncio
async def test_simple_template():
    tpl = Template()
    template_str = "Hello, {{ name }}!"
    data = {"name": "World"}
    result = await tpl.render(template_str, data)
    assert result == "Hello, World!"


@pytest.mark.asyncio
async def test_template_with_no_data():
    tpl = Template()
    template_str = "Hello, World!"
    result = await tpl.render(template_str)
    assert result == "Hello, World!"


@pytest.mark.asyncio
async def test_template_with_missing_variable():
    tpl = Template()
    template_str = "Hello, {{ name }}!"
    result = await tpl.render(template_str)
    assert result == "Hello, !"


@pytest.mark.asyncio
async def test_template_timeout():
    tpl = Template()
    template_str = """{% for i in range(100000) %}{% for j in range(100000) %}{% for k in range(100000) %}{{ i*i }}{% endfor %}{% endfor %}{% endfor %}"""
    data = {}
    with pytest.raises(TemplateTimeoutError) as excinfo:
        await tpl.render(template_str, data)
    assert "Template rendering exceeded" in str(excinfo.value)


@pytest.mark.asyncio
async def test_template_no_timeout():
    tpl = Template()
    template_str = """{% for i in range(100) %}{{ i }}\n{% endfor %}"""
    data = {}
    result = await tpl.render(template_str, data, timeout=2)
    expected_result = "\n".join(str(i) for i in range(100)) + "\n"
    assert result == expected_result


@pytest.mark.asyncio
async def test_template_with_custom_timeout():
    tpl = Template()
    template_str = """
    {% for i in range(100000) %}
    {% for j in range(100000) %}
    {{ i }}
    {% endfor %}
    {% endfor %}
    """
    data = {}
    with pytest.raises(TemplateTimeoutError) as excinfo:
        await tpl.render(template_str, data, timeout=0.1)

    assert "Template rendering exceeded 0.1 seconds" in str(excinfo.value)


@pytest.mark.asyncio
async def test_template_with_complex_data():
    tpl = Template()
    template_str = (
        "User: {{ user.name }}, Age: {{ user.age }}, Active: {{ user.active }}"
    )
    data = {"user": {"name": "John", "age": 30, "active": True}}
    result = await tpl.render(template_str, data)
    assert result == "User: John, Age: 30, Active: True"


@pytest.mark.asyncio
async def test_template_with_escape_sequences():
    tpl = Template()
    template_str = "Hello, {{ user.name }}!\nYour score: {{ user.score }}\n\nThank you!"
    data = {"user": {"name": "Alice", "score": 42}}
    result = await tpl.render(template_str, data)
    expected_result = "Hello, Alice!\nYour score: 42\n\nThank you!"
    assert result == expected_result


@pytest.mark.asyncio
async def test_deterministic_random() -> None:
    tpl = Template()
    template_str = "Random choice: {{ ['a', 'b', 'c', 'd', 'e', 'f', 'g']|random }}"
    data = {"random_seed": "test_seed"}
    result1 = await tpl.render(template_str, data)
    result2 = await tpl.render(template_str, data)
    assert result1 == result2  # Should be the same due to deterministic randomness


@pytest.mark.asyncio
async def test_deterministic_random_with_different_seeds():
    tpl = Template()
    template_str = "Random choice: {{ ['a', 'b', 'c', 'd', 'e', 'f', 'g']|random }}"
    data1 = {"random_seed": "seed1"}
    data2 = {"random_seed": "seed2"}
    result1 = await tpl.render(template_str, data1)
    result2 = await tpl.render(template_str, data2)
    assert result1 != result2  # Should be different due to different seeds


@pytest.mark.asyncio
async def test_template_with_large_data():
    tpl = Template()
    template_str = "Sum: {{ data|sum }}"
    data = {"data": list(range(10000))}
    result = await tpl.render(template_str, data)
    assert result == f"Sum: {sum(range(10000))}"


@pytest.mark.asyncio
async def test_template_with_nested_data():
    tpl = Template()
    template_str = "User: {{ user.name }}, Address: {{ user.address.city }}, {{ user.address.zip }}"
    data = {"user": {"name": "John", "address": {"city": "New York", "zip": "10001"}}}
    result = await tpl.render(template_str, data)
    assert result == "User: John, Address: New York, 10001"


# Old template system tests: Interpolation


@pytest.mark.asyncio
async def test_no_interpolation():
    tpl = Template()
    template_str = "PhasecoreX says {hello}!"
    data = {}
    result = await tpl.render(template_str, data)
    expected = template_str
    assert expected == result


@pytest.mark.asyncio
async def test_basic_interpolation():
    tpl = Template()
    template_str = "Hello, {{subject}}!"
    data = {"subject": "world"}
    result = await tpl.render(template_str, data)
    expected = "Hello, world!"
    assert expected == result


@pytest.mark.asyncio
async def test_basic_integer_interpolation():
    tpl = Template()
    template_str = '"{{mph}} miles an hour!"'
    data = {"mph": 88}
    result = await tpl.render(template_str, data)
    expected = '"88 miles an hour!"'
    assert expected == result


@pytest.mark.asyncio
async def test_basic_float_interpolation():
    tpl = Template()
    template_str = '"{{power}} jiggawatts!"'
    data = {"power": 1.210}
    result = await tpl.render(template_str, data)
    expected = '"1.21 jiggawatts!"'
    assert expected == result


@pytest.mark.asyncio
async def test_basic_context_miss_interpolation():
    tpl = Template()
    template_str = "I ({{cannot}}) be seen!"
    data = {}
    result = await tpl.render(template_str, data)
    expected = "I () be seen!"
    assert expected == result


# Dotted Names


@pytest.mark.asyncio
async def test_dotted_names_arbitrary_depth():
    tpl = Template()
    template_str = '"{{a.b.c.d.e.name}}" == "Phil"'
    data = {"a": {"b": {"c": {"d": {"e": {"name": "Phil"}}}}}}
    result = await tpl.render(template_str, data)
    expected = '"Phil" == "Phil"'
    assert expected == result


@pytest.mark.asyncio
async def test_dotted_names_broken_chains():
    tpl = Template()
    template_str = '"{{a.b.c}}" == ""'
    data = {"a": {}}
    result = await tpl.render(template_str, data)
    expected = '"" == ""'
    assert expected == result


@pytest.mark.asyncio
async def test_dotted_names_broken_chain_resolution():
    tpl = Template()
    template_str = '"{{a.b.c.name}}" == ""'
    data = {"a": {"b": {}}, "c": {"name": "Jim"}}
    result = await tpl.render(template_str, data)
    expected = '"" == ""'
    assert expected == result


# Whitespace Sensitivity


@pytest.mark.asyncio
async def test_interpolation_surrounding_whitespace():
    tpl = Template()
    template_str = "| {{string}} |"
    data = {"string": "---"}
    result = await tpl.render(template_str, data)
    expected = "| --- |"
    assert expected == result


@pytest.mark.asyncio
async def test_interpolation_standalone():
    tpl = Template()
    template_str = "  {{string}}\n"
    data = {"string": "---"}
    result = await tpl.render(template_str, data)
    expected = "  ---\n"
    assert expected == result


# Whitespace Insensitivity


@pytest.mark.asyncio
async def test_interpolation_with_padding():
    tpl = Template()
    template_str = "|{{ string }}|"
    data = {"string": "---"}
    result = await tpl.render(template_str, data)
    expected = "|---|"
    assert expected == result


# Old template system tests: IfStatement


@pytest.mark.asyncio
async def test_if_truthy():
    tpl = Template()
    template_str = '"{% if boolean %}This should be rendered.{% endif %}"'
    data = {"boolean": True}
    result = await tpl.render(template_str, data)
    expected = '"This should be rendered."'
    assert expected == result


@pytest.mark.asyncio
async def test_if_falsey():
    tpl = Template()
    template_str = '"{% if boolean %}This should not be rendered.{% endif %}"'
    data = {"boolean": False}
    result = await tpl.render(template_str, data)
    expected = '""'
    assert expected == result


@pytest.mark.asyncio
async def test_empty_lists():
    tpl = Template()
    template_str = '"{% if list %}Yay lists!{% endif %}"'
    data = {"list": []}
    result = await tpl.render(template_str, data)
    expected = '""'
    assert expected == result


@pytest.mark.asyncio
async def test_if_doubled():
    tpl = Template()
    template_str = """{% if bool %}
* first
{% endif %}
* {{two}}
{% if bool %}
* third
{% endif %}
"""
    data = {"bool": True, "two": "second"}
    result = await tpl.render(template_str, data)
    expected = """* first
* second
* third
"""
    assert expected == result


@pytest.mark.asyncio
async def test_if_nested_truthy():
    tpl = Template()
    template_str = "| A {% if bool %}B {% if bool %}C{% endif %} D{% endif %} E |"
    data = {"bool": True}
    result = await tpl.render(template_str, data)
    expected = "| A B C D E |"
    assert expected == result


@pytest.mark.asyncio
async def test_if_nested_falsey():
    tpl = Template()
    template_str = "| A {% if bool %}B {% if bool %}C{% endif %} D{% endif %} E |"
    data = {"bool": False}
    result = await tpl.render(template_str, data)
    expected = "| A  E |"
    assert expected == result


@pytest.mark.asyncio
async def test_if_context_misses():
    tpl = Template()
    template_str = "[{% if missing %}Found key 'missing'!{% endif %}]"
    data = {}
    result = await tpl.render(template_str, data)
    expected = "[]"
    assert expected == result


# Dotted Names


@pytest.mark.asyncio
async def test_if_dotted_names_truthy():
    tpl = Template()
    template_str = '"{% if a.b.c %}Here{% endif %}" == "Here"'
    data = {"a": {"b": {"c": True}}}
    result = await tpl.render(template_str, data)
    expected = '"Here" == "Here"'
    assert expected == result


@pytest.mark.asyncio
async def test_if_dotted_names_falsey():
    tpl = Template()
    template_str = '"{% if a.b.c %}Here{% endif %}" == ""'
    data = {"a": {"b": {"c": False}}}
    result = await tpl.render(template_str, data)
    expected = '"" == ""'
    assert expected == result


@pytest.mark.asyncio
async def test_if_dotted_names_broken_chains():
    tpl = Template()
    template_str = '"{% if a.b.c %}Here{% endif %}" == ""'
    data = {"a": {}}
    result = await tpl.render(template_str, data)
    expected = '"" == ""'
    assert expected == result


# Whitespace Sensitivity


@pytest.mark.asyncio
async def test_if_surrounding_whitespace():
    tpl = Template()
    template_str = " | {% if boolean %}\t|\t{% endif %} | \n"
    data = {"boolean": True}
    result = await tpl.render(template_str, data)
    expected = " | \t|\t | \n"
    assert expected == result


@pytest.mark.asyncio
async def test_if_internal_whitespace():
    tpl = Template()
    template_str = " | {% if boolean %} {# Important Whitespace #}\n {% endif %} | \n"
    data = {"boolean": True}
    result = await tpl.render(template_str, data)
    expected = " |  \n  | \n"
    assert expected == result


@pytest.mark.asyncio
async def test_if_indented_inline_sections():
    tpl = Template()
    template_str = " {% if boolean %}YES{% endif %}\n {% if boolean %}GOOD{% endif %}\n"
    data = {"boolean": True}
    result = await tpl.render(template_str, data)
    expected = " YES\n GOOD\n"
    assert expected == result


@pytest.mark.asyncio
async def test_if_standalone_lines():
    tpl = Template()
    template_str = """| This Is
{% if boolean %}
|
{% endif %}
| A Line
"""
    data = {"boolean": True}
    result = await tpl.render(template_str, data)
    expected = """| This Is
|
| A Line
"""
    assert expected == result


@pytest.mark.asyncio
async def test_if_indented_standalone_lines():
    tpl = Template()
    template_str = """| This Is
{% if boolean %}
|
{% endif %}
| A Line
"""
    data = {"boolean": True}
    result = await tpl.render(template_str, data)
    expected = """| This Is
|
| A Line
"""
    assert expected == result


@pytest.mark.asyncio
async def test_if_standalone_line_endings():
    tpl = Template()
    template_str = "|\r\n{% if boolean %}\r\n{% endif %}\r\n|"
    data = {"boolean": True}
    result = await tpl.render(template_str, data)
    expected = "|\r\n|"
    assert expected == result


@pytest.mark.asyncio
async def test_if_standalone_without_previous_line():
    tpl = Template()
    template_str = "  {% if boolean %}\n#{% endif %}\n/"
    data = {"boolean": True}
    result = await tpl.render(template_str, data)
    expected = "#\n/"
    assert expected == result


@pytest.mark.asyncio
async def test_if_standalone_without_newline():
    tpl = Template()
    template_str = "#{% if boolean %}\n/\n  {% endif %}"
    data = {"boolean": True}
    result = await tpl.render(template_str, data)
    expected = "#\n/\n"
    assert expected == result


# Whitespace Insensitivity


@pytest.mark.asyncio
async def test_if_padding():
    tpl = Template()
    template_str = "|{%      if      boolean%}={%    endif          %}|"
    data = {"boolean": True}
    result = await tpl.render(template_str, data)
    expected = "|=|"
    assert expected == result


# Old template system tests: IfNotStatement


@pytest.mark.asyncio
async def test_falsey():
    tpl = Template()
    template_str = '"{% if not boolean %}This should be rendered.{% endif %}"'
    data = {"boolean": False}
    result = await tpl.render(template_str, data)
    expected = '"This should be rendered."'
    assert expected == result


@pytest.mark.asyncio
async def test_truthy():
    tpl = Template()
    template_str = '"{% if not boolean %}This should not be rendered.{% endif %}"'
    data = {"boolean": True}
    result = await tpl.render(template_str, data)
    expected = '""'
    assert expected == result


@pytest.mark.asyncio
async def test_empty_list():
    tpl = Template()
    template_str = '"{% if not list %}Yay lists!{% endif %}"'
    data = {"list": []}
    result = await tpl.render(template_str, data)
    expected = '"Yay lists!"'
    assert expected == result


@pytest.mark.asyncio
async def test_doubled():
    tpl = Template()
    template_str = """{% if not bool %}
* first
{% endif %}
* {{two}}
{% if not bool %}
* third
{% endif %}
"""
    data = {"bool": False, "two": "second"}
    result = await tpl.render(template_str, data)
    expected = """* first
* second
* third
"""
    assert expected == result


@pytest.mark.asyncio
async def test_nested_falsey():
    tpl = Template()
    template_str = (
        "| A {% if not bool %}B {% if not bool %}C{% endif %} D{% endif %} E |"
    )
    data = {"bool": False}
    result = await tpl.render(template_str, data)
    expected = "| A B C D E |"
    assert expected == result


@pytest.mark.asyncio
async def test_nested_truthy():
    tpl = Template()
    template_str = (
        "| A {% if not bool %}B {% if not bool %}C{% endif %} D{% endif %} E |"
    )
    data = {"bool": True}
    result = await tpl.render(template_str, data)
    expected = "| A  E |"
    assert expected == result


@pytest.mark.asyncio
async def test_context_misses():
    tpl = Template()
    template_str = "[{% if not missing %}Cannot find key 'missing'!{% endif %}]"
    data = {}
    result = await tpl.render(template_str, data)
    expected = "[Cannot find key 'missing'!]"
    assert expected == result


# Dotted Names


@pytest.mark.asyncio
async def test_dotted_names_truthy():
    tpl = Template()
    template_str = '"{% if not a.b.c %}Here{% endif %}" == ""'
    data = {"a": {"b": {"c": True}}}
    result = await tpl.render(template_str, data)
    expected = '"" == ""'
    assert expected == result


@pytest.mark.asyncio
async def test_dotted_names_falsey():
    tpl = Template()
    template_str = '"{% if not a.b.c %}Not Here{% endif %}" == "Not Here"'
    data = {"a": {"b": {"c": False}}}
    result = await tpl.render(template_str, data)
    expected = '"Not Here" == "Not Here"'
    assert expected == result


@pytest.mark.asyncio
async def test_ifnot_dotted_names_broken_chains():
    tpl = Template()
    template_str = '"{% if not a.b.c %}Not Here{% endif %}" == "Not Here"'
    data = {"a": {}}
    result = await tpl.render(template_str, data)
    expected = '"Not Here" == "Not Here"'
    assert expected == result


# Whitespace Sensitivity


@pytest.mark.asyncio
async def test_ifnot_surrounding_whitespace():
    tpl = Template()
    template_str = " | {% if not boolean %}\t|\t{% endif %} | \n"
    data = {"boolean": False}
    result = await tpl.render(template_str, data)
    expected = " | \t|\t | \n"
    assert expected == result


@pytest.mark.asyncio
async def test_internal_whitespace():
    tpl = Template()
    template_str = (
        " | {% if not boolean %} {# Important Whitespace #}\n {% endif %} | \n"
    )
    data = {"boolean": False}
    result = await tpl.render(template_str, data)
    expected = " |  \n  | \n"
    assert expected == result


@pytest.mark.asyncio
async def test_indented_inline_sections():
    tpl = Template()
    template_str = (
        " {% if not boolean %}YES{% endif %}\n {% if not boolean %}GOOD{% endif %}\n"
    )
    data = {"boolean": False}
    result = await tpl.render(template_str, data)
    expected = " YES\n GOOD\n"
    assert expected == result


@pytest.mark.asyncio
async def test_standalone_lines():
    tpl = Template()
    template_str = """| This Is
{% if not boolean %}
|
{% endif %}
| A Line
"""
    data = {"boolean": False}
    result = await tpl.render(template_str, data)
    expected = """| This Is
|
| A Line
"""
    assert expected == result


@pytest.mark.asyncio
async def test_indented_standalone_lines():
    tpl = Template()
    template_str = """| This Is
{% if not boolean %}
|
{% endif %}
| A Line
"""
    data = {"boolean": False}
    result = await tpl.render(template_str, data)
    expected = """| This Is
|
| A Line
"""
    assert expected == result


@pytest.mark.asyncio
async def test_ifnot_standalone_line_endings():
    tpl = Template()
    template_str = "|\r\n{% if not boolean %}\r\n{% endif %}\r\n|"
    data = {"boolean": False}
    result = await tpl.render(template_str, data)
    expected = "|\r\n|"
    assert expected == result


@pytest.mark.asyncio
async def test_ifnot_standalone_without_previous_line():
    tpl = Template()
    template_str = "  {% if not boolean %}\n#{% endif %}\n/"
    data = {"boolean": False}
    result = await tpl.render(template_str, data)
    expected = "#\n/"
    assert expected == result


@pytest.mark.asyncio
async def test_ifnot_standalone_without_newline():
    tpl = Template()
    template_str = "#{% if not boolean %}\n/\n  {% endif %}"
    data = {"boolean": False}
    result = await tpl.render(template_str, data)
    expected = "#\n/\n"
    assert expected == result


# Whitespace Insensitivity


@pytest.mark.asyncio
async def test_padding():
    tpl = Template()
    template_str = "|{%      if     not    boolean%}={%    endif          %}|"
    data = {"boolean": False}
    result = await tpl.render(template_str, data)
    expected = "|=|"
    assert expected == result


# Old template system tests: ElseStatement


@pytest.mark.asyncio
async def test_else():
    tpl = Template()
    template_str = "{% if 1 > 2 %}Bad...{% else %}Good!{% endif %}"
    data = {}
    result = await tpl.render(template_str, data)
    expected = "Good!"
    assert expected == result


# Old template system tests: ElifStatement


@pytest.mark.asyncio
async def test_elif():
    tpl = Template()
    template_str = "{% if 1 > 2 %}Bad if...{% elif 2 == 3 %}Bad elif 1...{% elif 1 == 1 %}Good!{% elif 1 == 2 %}Bad elif 2...{% else %}Bad else...{% endif %}"
    data = {}
    result = await tpl.render(template_str, data)
    expected = "Good!"
    assert expected == result


# Old template system tests: Comment


@pytest.mark.asyncio
async def test_inline():
    tpl = Template()
    template_str = "12345{# Comment Block! #}67890"
    data = {}
    result = await tpl.render(template_str, data)
    expected = "1234567890"
    assert expected == result


@pytest.mark.asyncio
async def test_multiline():
    tpl = Template()
    template_str = """12345{#
This is a
multi-line comment...
#}67890
"""
    data = {}
    result = await tpl.render(template_str, data)
    expected = """1234567890
"""
    assert expected == result


@pytest.mark.asyncio
async def test_standalone():
    tpl = Template()
    template_str = """Begin.
{# Comment Block! #}
End.
"""
    data = {}
    result = await tpl.render(template_str, data)
    expected = """Begin.
End.
"""
    assert expected == result


@pytest.mark.asyncio
async def test_indented_standalone():
    tpl = Template()
    template_str = """Begin.
{# Indented Comment Block! #}
End.
"""
    data = {}
    result = await tpl.render(template_str, data)
    expected = """Begin.
End.
"""
    assert expected == result


@pytest.mark.asyncio
async def test_standalone_line_endings():
    tpl = Template()
    template_str = "|\r\n{# Standalone Comment #}\r\n|"
    data = {}
    result = await tpl.render(template_str, data)
    expected = "|\r\n|"
    assert expected == result


@pytest.mark.asyncio
async def test_standalone_without_previous_line():
    tpl = Template()
    template_str = "  {# I'm Still Standalone #}\n!"
    data = {}
    result = await tpl.render(template_str, data)
    expected = "!"
    assert expected == result


@pytest.mark.asyncio
async def test_standalone_without_newline():
    tpl = Template()
    template_str = "!\n  {# I'm Still Standalone #}"
    data = {}
    result = await tpl.render(template_str, data)
    expected = "!\n"
    assert expected == result


@pytest.mark.asyncio
async def test_multiline_standalone():
    tpl = Template()
    template_str = """Begin.
{#
Something's going on here...
#}
End.
"""
    data = {}
    result = await tpl.render(template_str, data)
    expected = """Begin.
End.
"""
    assert expected == result


@pytest.mark.asyncio
async def test_indented_multiline_standalone():
    tpl = Template()
    template_str = """Begin.
{#
Something's going on here...
#}
End.
"""
    data = {}
    result = await tpl.render(template_str, data)
    expected = """Begin.
End.
"""
    assert expected == result


@pytest.mark.asyncio
async def test_indented_inline():
    tpl = Template()
    template_str = "  12 {# 34 #}\n"
    data = {}
    result = await tpl.render(template_str, data)
    expected = "  12 \n"
    assert expected == result


@pytest.mark.asyncio
async def test_surrounding_whitespace():
    tpl = Template()
    template_str = "12345 {# Comment Block! #} 67890"
    data = {}
    result = await tpl.render(template_str, data)
    expected = "12345  67890"
    assert expected == result


# Old template system tests: Filter


@pytest.mark.asyncio
async def test_invalid():
    tpl = Template()
    template_str = "{{words | invalidFilter}}"
    data = {"words": "This won't be changed"}
    result = await tpl.render(template_str, data)
    expected = "This won't be changed"
    assert expected == result


@pytest.mark.asyncio
async def test_lower():
    tpl = Template()
    template_str = "{{word | lower}}"
    data = {"word": "QUIET"}
    result = await tpl.render(template_str, data)
    expected = "quiet"
    assert expected == result


@pytest.mark.asyncio
async def test_upper():
    tpl = Template()
    template_str = "{{word | upper}}"
    data = {"word": "loud"}
    result = await tpl.render(template_str, data)
    expected = "LOUD"
    assert expected == result


@pytest.mark.asyncio
async def test_multiple():
    tpl = Template()
    template_str = "{{word | upper | lower | upper | lower | upper | lower | upper | lower | upper}}"
    data = {"word": "loud"}
    result = await tpl.render(template_str, data)
    expected = "LOUD"
    assert expected == result


if __name__ == "__main__":
    pytest.main(["-v", __file__])
