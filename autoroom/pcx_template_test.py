"""Unit tests for pcx_template."""
import unittest

from template import Template


class TestTemplate(unittest.TestCase):
    def setUp(self):
        self.template = Template()

    def test_basic_substitution(self):
        template_str = "Hello {{ name }}!"
        data = {"name": "World"}
        result = self.template.render(template_str, data)
        assert result == "Hello World!"

    def test_missing_data(self):
        template_str = "Hello {{ name }}!"
        result = self.template.render(template_str, {})
        assert result == "Hello !"

    def test_html_escaping(self):
        template_str = "Data: {{ data }}"
        data = {"data": "<script>alert('test');</script>"}
        result = self.template.render(template_str, data)
        assert "<script>" not in result

    def test_complex_structure(self):
        template_str = "{{ user.name }} - {{ user.age }}"
        data = {"user": {"name": "Alice", "age": 30}}
        result = self.template.render(template_str, data)
        assert result == "Alice - 30"

    # Add more test cases as needed


if __name__ == "__main__":
    unittest.main()
