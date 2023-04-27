"""A simple template engine, safe for untrusted user templates."""

from contextlib import suppress
from typing import Any

from pyparsing import (
    Keyword,
    Literal,
    ParserElement,
    ParseResults,
    SkipTo,
    Suppress,
    delimitedList,
    infixNotation,
    opAssoc,
    pyparsing_common,
    quotedString,
)

__author__ = "PhasecoreX"


class Template:
    """A simple template engine, safe for untrusted user templates."""

    def __init__(self) -> None:
        """Set up the parser."""
        ParserElement.enablePackrat()

        expression_l = Suppress("{{")
        expression_r = Suppress("}}")
        statement_l = Suppress("{%")
        statement_r = Suppress("%}")
        comment_l = Suppress("{#")
        comment_r = Suppress("#}")

        comment = comment_l + SkipTo(comment_r)("comment") + comment_r

        identifier = pyparsing_common.identifier
        qualified_identifier = delimitedList(identifier, ".", combine=True)
        chain_filter = Suppress("|") + identifier
        expression = (
            expression_l
            + qualified_identifier("identifier")
            + chain_filter[...]("filters")
            + expression_r
        )

        statement_atom = (
            Keyword("None")
            | Keyword("False")
            | Keyword("True")
            | pyparsing_common.number
            | quotedString
            | qualified_identifier
        )

        statement_op = (
            Literal("==")
            | Literal(">=")
            | Literal("<=")
            | Literal("!=")
            | Literal("<")
            | Literal(">")
            # | Literal("not") + Literal("in")
            # | Literal("in")
            # | Literal("is") + Literal("not")
            # | Literal("is")
        )

        statement_test = infixNotation(
            statement_atom,
            [
                (statement_op, 2, opAssoc.LEFT),
                ("not", 1, opAssoc.RIGHT),
                ("and", 2, opAssoc.LEFT),
                ("or", 2, opAssoc.LEFT),
            ],
        )

        if_statement = statement_l + Keyword("if") + statement_test + statement_r
        elif_statement = statement_l + Keyword("elif") + statement_test + statement_r
        else_statement = statement_l + Keyword("else") + statement_r
        endif_statement = statement_l + Keyword("endif") + statement_r

        template = (
            comment
            | if_statement
            | elif_statement
            | else_statement
            | endif_statement
            | expression
        )

        self.template_parser = template.parseWithTabs()

    @staticmethod
    def _get_value(key: Any, data: dict[str, Any]) -> Any:  # noqa: ANN401
        if not isinstance(key, str):
            return key
        if len(key) > 1 and key[0] in ('"', "'") and key[0] == key[-1]:
            return key[1:-1]
        with suppress(KeyError):
            for attr in key.split("."):
                data = data[attr]
            return data
        return ""

    def _evaluate(self, condition: Any, data: dict[str, Any]) -> Any:  # noqa: ANN401
        # Base case
        if not isinstance(condition, ParseResults):
            return self._get_value(condition, data)
        # Not
        if condition[0] == "not":
            return not self._evaluate(condition[1], data)
        # And/Or, rhs could be ignored if short-circuiting
        lhs = self._evaluate(condition[0], data)
        if condition[1] == "and":
            return lhs and self._evaluate(condition[2], data)
        if condition[1] == "or":
            return lhs or self._evaluate(condition[2], data)
        # rhs is now required
        rhs = self._evaluate(condition[2], data)
        if not lhs and isinstance(rhs, int | float):
            lhs = 0
        if condition[1] == "==":
            return lhs == rhs
        if condition[1] == ">=":
            return lhs >= rhs
        if condition[1] == "<=":
            return lhs <= rhs
        if condition[1] == "!=":
            return lhs != rhs
        if condition[1] == "<":
            return lhs < rhs
        if condition[1] == ">":
            return lhs > rhs
        return False

    @staticmethod
    def _statement_result_append(result: str | None, to_append: str) -> str:
        if not result:
            result = ""
        if (
            to_append
            and to_append.lstrip(" \t")
            and to_append.lstrip(" \t")[0]
            in (
                "\r",
                "\n",
            )
            and (
                not result.rstrip(" \t")
                or result.rstrip(" \t")[-1]
                in (
                    "\r",
                    "\n",
                )
            )
        ):
            result = result.rstrip(" \t")
            to_append = to_append.lstrip(" \t")
            to_append = to_append[2:] if to_append.startswith("\r\n") else to_append[1:]
        return result + to_append

    def render(self, template: str = "", data: dict[str, Any] | None = None) -> str:
        """Render a template with the given data."""
        if data is None:
            data = {}
        result = ""
        current_index = 0
        # stack keeps track of if the previous check was true, and thus are printing
        stack: list[tuple[str, Any]] = [("base", True)]
        target_stack_height = len(stack)
        potential_standalone = False
        tokens = self.template_parser.scanString(template)
        for token in tokens:
            if len(stack) != target_stack_height:
                # If we are in an if statement and already found what part to print (the true part),
                # the target_stack_height will be lowered by 1. Don't print anything until we get the
                # stack height back to this value.
                stack[-1] = (stack[-1][0], False)

            # Print logic
            printing = stack[-1][1]  # last inserted element, second arg
            if token[1] != current_index and printing:
                to_append = template[current_index : token[1]]
                result = self._statement_result_append(result, to_append)
            potential_standalone = not result.rstrip(" \t") or result.rstrip(" \t")[
                -1
            ] in ("\r", "\n")

            if "comment" in token:
                pass
            elif "identifier" in token[0] and printing:
                identifier_value = str(self._get_value(token[0].identifier, data))
                if "filters" in token[0]:
                    for filter_name in token[0]["filters"]:
                        if filter_name == "lower":
                            identifier_value = identifier_value.lower()
                        elif filter_name == "upper":
                            identifier_value = identifier_value.upper()
                result += identifier_value
                potential_standalone = False
            elif token[0][0] == "if":
                if len(stack) == target_stack_height:
                    target_stack_height += 1
                evaluate_result = self._evaluate(token[0][1], data)
                stack.append(("if", evaluate_result))
            elif token[0][0] == "elif":
                if stack[-1][0] not in ("if", "elif"):
                    error_message = f"{token[0][0]!r} unexpected at position {token[1]}-{token[2]} (not in an if statement)"
                    raise RuntimeError(error_message)
                if len(stack) == target_stack_height:
                    if stack[-1][
                        1
                    ]:  # Previous part of this if statement was true, so we are done with this if statement
                        target_stack_height -= 1
                    else:
                        evaluate_result = self._evaluate(token[0][1], data)
                        stack[-1] = ("elif", evaluate_result)
            elif token[0][0] == "else":
                if stack[-1][0] not in ("if", "elif"):
                    error_message = f"{token[0][0]!r} unexpected at position {token[1]}-{token[2]} (not in an if statement)"
                    raise RuntimeError(error_message)
                if len(stack) == target_stack_height:
                    if stack[-1][
                        1
                    ]:  # Previous part of this if statement was true, so we are done with this if statement
                        target_stack_height -= 1
                    else:
                        stack[-1] = ("else", True)
            elif token[0][0] == "endif":
                if stack[-1][0] not in ("if", "elif", "else"):
                    error_message = f"{token[0][0]!r} unexpected at position {token[1]}-{token[2]} (not in an if statement)"
                    raise RuntimeError(error_message)
                if len(stack) == target_stack_height:
                    target_stack_height -= 1
                del stack[-1]
            current_index = token[2]
        if current_index != len(template):
            to_append = template[current_index : len(template)]
            result = self._statement_result_append(result, to_append)
            potential_standalone = False
        if potential_standalone:
            result = result.rstrip(" \t")
        return result
