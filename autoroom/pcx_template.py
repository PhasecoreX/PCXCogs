"""Module for template engine using Jinja2, safe for untrusted user templates."""

from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment


class Template:
    """A template engine using Jinja2, safe for untrusted user templates."""

    def __init__(self) -> None:
        """Set up the Jinja2 environment."""
        self.env = SandboxedEnvironment(loader=BaseLoader(), autoescape=False)

    def render(self, template_str: str, data: dict[str, Any] | None = None) -> str:
        """Render a template with the given data."""
        if data is None:
            data = {}
        template = self.env.from_string(template_str)
        return template.render(data)
