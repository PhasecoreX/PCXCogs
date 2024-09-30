"""Module for template engine using Jinja2, safe for untrusted user templates."""

import multiprocessing
import random
from typing import Any

from jinja2 import pass_context
from jinja2.exceptions import TemplateError
from jinja2.runtime import Context
from jinja2.sandbox import ImmutableSandboxedEnvironment

TIMEOUT = 1  # Maximum runtime for template rendering in seconds / should be very low to avoid DoS attacks


class TemplateTimeoutError(TemplateError):
    """Custom exception raised when template rendering exceeds maximum runtime."""


class Template:
    """A template engine using Jinja2, safe for untrusted user templates with an immutable sandbox."""

    def __init__(self) -> None:
        """Set up the Jinja2 environment with an immutable sandbox."""
        self.env = ImmutableSandboxedEnvironment(autoescape=False)

        # Override Jinja's built-in random filter with a deterministic version
        self.env.filters["random"] = self.deterministic_random

    @pass_context
    def deterministic_random(self, ctx: Context, seq: list) -> Any:  # noqa: ANN401
        """Generate a deterministic random choice from a sequence based on the context's random_seed."""
        seed = ctx.get(
            "random_seed", random.getrandbits(32)
        )  # Use seed from context or default
        random.seed(seed)
        return random.choice(seq)  # Return a deterministic random choice  # noqa: S311

    def _render_template(
        self, template_str: str, data: dict[str, Any], queue: multiprocessing.Queue
    ) -> None:
        """Render the template in a separate process and put the result in a queue."""
        try:
            template = self.env.from_string(template_str)
            result = template.render(data)
            queue.put(result)  # Put the rendered template in the queue
        except Exception as e:  # noqa: BLE001
            queue.put(e)  # Put the exception in the queue if something goes wrong

    async def render(
        self,
        template_str: str,
        data: dict[str, Any] | None = None,
        timeout: int = TIMEOUT,  # noqa: ASYNC109
    ) -> str:
        """Render a template with the given data, enforcing a maximum runtime."""
        if data is None:
            data = {}

        queue = multiprocessing.Queue()

        # Start the rendering process
        process = multiprocessing.Process(
            target=self._render_template, args=(template_str, data, queue)
        )
        process.start()

        try:
            # Wait for the result with a timeout
            process.join(timeout)

            if process.is_alive():
                process.terminate()  # Kill the process if it exceeds the timeout
                msg = f"Template rendering exceeded {timeout} seconds."
                raise TemplateTimeoutError(msg)

            result = queue.get_nowait()  # Get the result from the queue
            if isinstance(result, Exception):
                raise result  # Re-raise the exception if something went wrong

            return result  # noqa: TRY300

        except multiprocessing.queues.Empty:
            msg = "Template rendering failed due to timeout or error."
            raise TemplateTimeoutError(msg) from None
        finally:
            process.join()  # Ensure the process is cleaned up
