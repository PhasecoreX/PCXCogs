"""Module for template engine using Jinja2, safe for untrusted user templates."""

import multiprocessing
from typing import Any

from jinja2.sandbox import ImmutableSandboxedEnvironment


class TemplateTimeoutError(Exception):
    """Custom exception raised when template rendering exceeds maximum runtime."""


class Template:
    """A template engine using Jinja2, safe for untrusted user templates with an immutable sandbox."""

    def __init__(self) -> None:
        """Set up the Jinja2 environment with an immutable sandbox."""
        self.env = ImmutableSandboxedEnvironment(autoescape=False)

    def _render_template(
        self, template_str: str, data: dict[str, Any], queue: multiprocessing.Queue
    ) -> None:
        """Render a template with the given data and put the result in the queue."""
        try:
            template = self.env.from_string(template_str)
            result = template.render(data)
            queue.put(result)
        except Exception as e:  # noqa: BLE001
            queue.put(e)

    async def render(
        self,
        template_str: str,
        data: dict[str, Any] | None = None,
        timeout: int = 2,  # in seconds
    ) -> str:
        """Render a template with the given data, enforcing a maximum runtime."""
        if data is None:
            data = {}

        queue = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=self._render_template, args=(template_str, data, queue)
        )
        process.start()
        process.join(timeout=timeout)

        if process.is_alive():
            process.terminate()
            msg = "Template rendering exceeded maximum runtime"
            raise TemplateTimeoutError(msg)

        # Get the result from the queue
        result = queue.get()
        if isinstance(result, Exception):
            raise result  # Re-raise the exception if something went wrong in the process

        return result
