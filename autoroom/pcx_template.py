"""Module for template engine using Jinja2, safe for untrusted user templates."""

import random
from typing import Any

from func_timeout import FunctionTimedOut, func_timeout
from jinja2 import Undefined, pass_context
from jinja2.exceptions import TemplateError
from jinja2.runtime import Context
from jinja2.sandbox import ImmutableSandboxedEnvironment

TIMEOUT = 0.25  # Maximum runtime for template rendering in seconds / should be very low to avoid DoS attacks


class TemplateTimeoutError(TemplateError):
    """Custom exception raised when template rendering exceeds maximum runtime."""


class SilentUndefined(Undefined):
    """Class that converts Undefined type to None."""

    def _fail_with_undefined_error(self, *_args: Any, **_kwargs: Any) -> None:  # type: ignore[incorrect-return-type]  # noqa: ANN401
        return None


class Template:
    """A template engine using Jinja2, safe for untrusted user templates with an immutable sandbox."""

    def __init__(self) -> None:
        """Set up the Jinja2 environment with an immutable sandbox."""
        self.env = ImmutableSandboxedEnvironment(
            finalize=self.finalize,
            undefined=SilentUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

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

    def finalize(self, element: Any) -> Any:  # noqa: ANN401
        """Callable that converts None elements to an empty string."""
        return element if element is not None else ""

    def _render_template(self, template_str: str, data: dict[str, Any]) -> str:
        """Render the template to a string."""
        return self.env.from_string(template_str).render(data)

    async def render(
        self,
        template_str: str,
        data: dict[str, Any] | None = None,
        timeout: float = TIMEOUT,  # noqa: ASYNC109
    ) -> str:
        """Render a template with the given data, enforcing a maximum runtime."""
        if data is None:
            data = {}
        try:
            result: str = func_timeout(
                timeout, self._render_template, args=(template_str, data)
            )  # type: ignore[unknown-return-type]
        except FunctionTimedOut as err:
            msg = f"Template rendering exceeded {timeout} seconds."
            raise TemplateTimeoutError(msg) from err
        return result
