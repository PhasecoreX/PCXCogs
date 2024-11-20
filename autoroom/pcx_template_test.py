import pytest
from pcx_template import (
    Template,
    TemplateTimeoutError,
)


@pytest.mark.asyncio
async def test_simple_template():  # noqa: D103
    tpl = Template()
    template_str = "Hello, {{ name }}!"
    data = {"name": "World"}
    result = await tpl.render(template_str, data)
    assert result == "Hello, World!"


@pytest.mark.asyncio
async def test_template_with_no_data():  # noqa: D103
    tpl = Template()
    template_str = "Hello, World!"
    result = await tpl.render(template_str)
    assert result == "Hello, World!"


@pytest.mark.asyncio
async def test_template_with_missing_variable():  # noqa: D103
    tpl = Template()
    template_str = "Hello, {{ name }}!"
    result = await tpl.render(template_str)
    assert result == "Hello, !"


@pytest.mark.asyncio
async def test_template_timeout():  # noqa: D103
    tpl = Template()
    template_str = """{% for i in range(100000) %}{% for j in range(100000) %}{% for k in range(100000) %}{{ i*i }}{% endfor %}{% endfor %}{% endfor %}"""
    data = {}
    with pytest.raises(TemplateTimeoutError) as excinfo:
        await tpl.render(template_str, data)
    assert "Template rendering exceeded" in str(excinfo.value)


@pytest.mark.asyncio
async def test_template_no_timeout():  # noqa: D103
    tpl = Template()
    template_str = """{% for i in range(100) %}{{ i }}\n{% endfor %}"""
    data = {}
    result = await tpl.render(template_str, data, timeout=2)
    expected_result = "\n".join(str(i) for i in range(100)) + "\n"
    assert result == expected_result


@pytest.mark.asyncio
async def test_template_with_custom_timeout():  # noqa: D103
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
async def test_template_with_complex_data():  # noqa: D103
    tpl = Template()
    template_str = (
        "User: {{ user.name }}, Age: {{ user.age }}, Active: {{ user.active }}"
    )
    data = {"user": {"name": "John", "age": 30, "active": True}}
    result = await tpl.render(template_str, data)
    assert result == "User: John, Age: 30, Active: True"


@pytest.mark.asyncio
async def test_template_with_escape_sequences():  # noqa: D103
    tpl = Template()
    template_str = "Hello, {{ user.name }}!\nYour score: {{ user.score }}\n\nThank you!"
    data = {"user": {"name": "Alice", "score": 42}}
    result = await tpl.render(template_str, data)
    expected_result = "Hello, Alice!\nYour score: 42\n\nThank you!"
    assert result == expected_result


@pytest.mark.asyncio
async def test_deterministic_random() -> None:  # noqa: D103
    tpl = Template()
    template_str = "Random choice: {{ ['a', 'b', 'c', 'd', 'e', 'f', 'g']|random }}"
    data = {"random_seed": "test_seed"}
    result1 = await tpl.render(template_str, data)
    result2 = await tpl.render(template_str, data)
    assert result1 == result2  # Should be the same due to deterministic randomness


@pytest.mark.asyncio
async def test_deterministic_random_with_different_seeds():  # noqa: D103
    tpl = Template()
    template_str = "Random choice: {{ ['a', 'b', 'c', 'd', 'e', 'f', 'g']|random }}"
    data1 = {"random_seed": "seed1"}
    data2 = {"random_seed": "seed2"}
    result1 = await tpl.render(template_str, data1)
    result2 = await tpl.render(template_str, data2)
    assert result1 != result2  # Should be different due to different seeds


@pytest.mark.asyncio
async def test_template_with_large_data():  # noqa: D103
    tpl = Template()
    template_str = "Sum: {{ data|sum }}"
    data = {"data": list(range(10000))}
    result = await tpl.render(template_str, data)
    assert result == f"Sum: {sum(range(10000))}"


@pytest.mark.asyncio
async def test_template_with_nested_data():  # noqa: D103
    tpl = Template()
    template_str = "User: {{ user.name }}, Address: {{ user.address.city }}, {{ user.address.zip }}"
    data = {"user": {"name": "John", "address": {"city": "New York", "zip": "10001"}}}
    result = await tpl.render(template_str, data)
    assert result == "User: John, Address: New York, 10001"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
