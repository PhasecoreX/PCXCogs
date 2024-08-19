import pytest
from pcx_template import (
    Template,
    TemplateTimeoutError,
)


@pytest.mark.asyncio()
async def test_simple_template():
    tpl = Template()
    template_str = "Hello, {{ name }}!"
    data = {"name": "World"}
    result = await tpl.render(template_str, data)
    assert result == "Hello, World!"


@pytest.mark.asyncio()
async def test_template_with_no_data():
    tpl = Template()
    template_str = "Hello, World!"
    result = await tpl.render(template_str)
    assert result == "Hello, World!"


@pytest.mark.asyncio()
async def test_template_with_missing_variable():
    tpl = Template()
    template_str = "Hello, {{ name }}!"
    result = await tpl.render(template_str)
    assert result == "Hello, !"


@pytest.mark.asyncio()
async def test_template_timeout():
    tpl = Template()
    template_str = """{% for i in range(100000) %}{{ i*i }}{% endfor %}"""
    data = {}
    with pytest.raises(TemplateTimeoutError) as excinfo:
        await tpl.render(template_str, data)
    assert "Template rendering exceeded maximum runtime" in str(excinfo.value)


@pytest.mark.asyncio()
async def test_template_no_timeout():
    tpl = Template()
    template_str = """{% for i in range(100) %}{{ i }}\n{% endfor %}"""
    data = {}
    result = await tpl.render(template_str, data, timeout=2)
    expected_result = "\n".join(str(i) for i in range(100)) + "\n"
    assert result == expected_result


@pytest.mark.asyncio()
async def test_template_with_custom_timeout():
    tpl = Template()
    template_str = """
    {% for i in range(100000) %}
    {{ i }}
    {% endfor %}
    """
    data = {}
    with pytest.raises(TemplateTimeoutError) as excinfo:
        await tpl.render(template_str, data, timeout=0.1)
    assert "Template rendering exceeded maximum runtime" in str(excinfo.value)


@pytest.mark.asyncio()
async def test_template_with_complex_data():
    tpl = Template()
    template_str = (
        "User: {{ user.name }}, Age: {{ user.age }}, Active: {{ user.active }}"
    )
    data = {"user": {"name": "John", "age": 30, "active": True}}
    result = await tpl.render(template_str, data)
    assert result == "User: John, Age: 30, Active: True"


@pytest.mark.asyncio()
async def test_template_with_escape_sequences():
    tpl = Template()
    template_str = "Hello, {{ user.name }}!\nYour score: {{ user.score }}\n\nThank you!"
    data = {"user": {"name": "Alice", "score": 42}}
    result = await tpl.render(template_str, data)
    expected_result = "Hello, Alice!\nYour score: 42\n\nThank you!"
    assert result == expected_result


if __name__ == "__main__":
    pytest.main(["-v", __file__])
