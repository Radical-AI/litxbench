"""Code Execution Environment tools for PydanticAI agents."""

import ast
import contextlib
import contextvars
import io
import math
import sys
import textwrap
import traceback
import types
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

# Context variable to store a stack of Repl namespaces (allows nested Repl contexts)
_current_repl_namespace_stack: contextvars.ContextVar[list[dict[str, Any]] | None] = contextvars.ContextVar(  # pyright: ignore[reportExplicitAny]
    "_current_repl_namespace_stack", default=None
)


@dataclass
class CodeExecutionResult:
    """
    Attributes:
        namespace: The namespace of the code execution (contains all the variables at the end of the execution)
        stdout_output: Standard output from the code execution
        stderr_output: Standard error output from the code execution
    """

    namespace: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    stdout_output: str
    stderr_output: str


class CodeExecutionToolResult(BaseModel):
    """
    Attributes:
        stdout_output: Standard output from the code execution
        stderr_output: Standard error output from the code execution
    """

    stdout_output: str
    stderr_output: str


def code_execution_env_factory(
    namespace: dict[str, Any],
) -> tuple[Callable[[str], CodeExecutionResult], Callable[[str], CodeExecutionToolResult]]:  # pyright: ignore[reportExplicitAny]
    """Create a code execution tool with the namespace provided. All the agent needs to do is pass in code (as a string) into the tool arguments."""

    def code_execution_env(code: str) -> CodeExecutionResult:
        """Executes code"""
        metrics = _execute_code_in_namespace(code, namespace)
        return CodeExecutionResult(
            namespace=namespace,
            stdout_output=metrics.stdout_output,
            stderr_output=metrics.stderr_output,
        )

    # Note: The code execution tool is the same as the code execution environment,
    # but the result it returns doesn't have the namespace (so it's serializable to be recorded by the message history)
    def code_execution_tool(code: str) -> CodeExecutionToolResult:
        """Execute code and return the result."""
        return _execute_code_in_namespace(code, namespace)

    return code_execution_env, code_execution_tool


class Repl:
    """Context manager that provides a shared namespace for code execution."""

    def __init__(self, initial_namespace: dict[str, Any] | None = None) -> None:  # pyright: ignore[reportExplicitAny]
        """Initialize a Repl context manager with an optional initial namespace.

        Args:
            initial_namespace: Optional initial namespace dict. If None, creates a new empty dict.
        """
        self.namespace: dict[str, Any] = initial_namespace.copy() if initial_namespace is not None else {}  # pyright: ignore[reportExplicitAny]

    def __enter__(self) -> "Repl":
        """Enter the context manager and push the namespace onto the stack."""
        stack = _current_repl_namespace_stack.get()
        if stack is None:
            new_stack: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
            _ = _current_repl_namespace_stack.set(new_stack)
            stack = new_stack
        stack.append(self.namespace)
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: types.TracebackType | None
    ) -> None:
        """Exit the context manager and pop the namespace from the stack."""
        stack = _current_repl_namespace_stack.get()
        if stack and stack[-1] is self.namespace:
            _ = stack.pop()


def repl_tool(char_limit: int = -1) -> Callable[[str], CodeExecutionToolResult]:
    """Return a repl tool that reads/writes code to the shared namespace stored under the Repl context manager.

    Returns:
        A function that executes code in the current Repl namespace.

    Raises:
        RuntimeError: If called outside of a Repl context manager.
    """

    def execute_code(code: str) -> CodeExecutionToolResult:
        """Execute code in the current Repl namespace."""
        stack = _current_repl_namespace_stack.get()
        if not stack:
            raise RuntimeError("repl_tool() must be called within a Repl context manager")
        namespace = stack[-1]

        result = _execute_code_in_namespace(code, namespace, raise_on_error=False)

        # now execute the final expression and add it to the stdout_output
        try:
            final_expression_result = _evaluate_with_final_expression(code, namespace)
            if final_expression_result is not None:
                result.stdout_output += "\n" + str(final_expression_result)
        except Exception:
            # this would've already been caught by the _execute_code_in_namespace function.
            # So no need repeat this exception into the final_expression_result variable.
            pass

        if char_limit > -1 and len(result.stdout_output) > char_limit:
            first_half = result.stdout_output[: math.ceil(char_limit * 3 / 4)]
            second_half = result.stdout_output[math.floor(char_limit / 4) :]
            result.stdout_output = first_half + "\n... (truncated) ...\n" + second_half
        return result

    return execute_code


def _evaluate_with_final_expression(code: str, namespace: dict[str, Any]) -> Any:
    """
    Execute code in the given namespace and return the value of the final
    expression statement, if present. Otherwise, return None.

    Errors are NOT caught — caller is responsible.
    """
    if namespace is None:
        namespace = {}

    if not code.strip():
        return None

    tree = ast.parse(code, mode="exec")
    if not tree.body:
        return None

    last_stmt = tree.body[-1]

    # If the last statement is not an expression, just exec and return None
    if not isinstance(last_stmt, ast.Expr):
        exec(code, namespace)
        return None

    # Execute everything except the final expression
    body_without_last = tree.body[:-1]
    module_without_last = ast.Module(body=body_without_last, type_ignores=[])
    exec(compile(module_without_last, "<string>", "exec"), namespace)

    # Evaluate the final expression
    expr = ast.Expression(last_stmt.value)
    return eval(compile(expr, "<string>", "eval"), namespace)


def _execute_code_in_namespace(
    code: str, namespace: dict[str, Any], raise_on_error: bool = True
) -> CodeExecutionToolResult:  # pyright: ignore[reportExplicitAny]
    """Execute code in the given namespace and return execution metrics.

    Args:
        code: Python code string to execute
        namespace: Dictionary to use as both globals and locals for execution

    Returns:
        Execution metrics including runtime, stdout, and stderr

    Raises:
        RuntimeError: If code execution fails, with detailed error information
    """
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    with (
        contextlib.redirect_stdout(new_target=stdout_capture),
        contextlib.redirect_stderr(stderr_capture),
    ):
        # Execute the code and capture the result with improved error surfacing
        try:
            # We use namespace for both globals and locals to ensure that imports
            # and variables defined at the top level of the code are available
            # inside functions defined in the code.
            exec(code, namespace, namespace)

        except Exception:
            exc_info = sys.exc_info()  # Capture exception info immediately
            # Pass the captured info and the *original* code string
            error_msg = _show_exec_exception_context(code, exc_info, 20)
            if error_msg is None:
                error_msg = textwrap.dedent(f"{traceback.format_exception(*exc_info)}")

            if raise_on_error:
                error_msg += textwrap.dedent(f"""
                    Stdout: {stdout_capture.getvalue()}
                    Stderr: {stderr_capture.getvalue()}""")
                raise RuntimeError(error_msg)  # noqa: B904 # use noqa so we hide the fact that we have this extra try: except block to LLMs
            else:
                stderr_capture.write(error_msg)

    return CodeExecutionToolResult(
        stdout_output=stdout_capture.getvalue(),
        stderr_output=stderr_capture.getvalue(),
    )


def _show_exec_exception_context(
    code_str: str,
    exc_info: tuple[type[BaseException] | None, BaseException | None, types.TracebackType | None],
    context_lines: int = 5,
) -> str | None:
    """Extract context lines around an exception from an executed code string.
    Args:
        code_str: String containing the Python code that was executed
        exc_info: Tuple containing exception type, value, and traceback (from sys.exc_info())
        context_lines: Number of lines to show before and after the exception line
    Returns:
        A string with a formatted error message with the line number in the executed
        code where the exception occurred. If ``exc_info`` indicates no exception (i.e., no exception was
        thrown), the function returns ``None``.
    """
    exc_type, exc_value, exc_tb = exc_info

    # If no valid exception info, return ``None`` to indicate that no exception was thrown.
    if exc_type is None or exc_value is None or exc_tb is None:
        return None

    # Split the code into lines for context display
    code_lines = code_str.split("\n")
    error_msg_parts: list[str] = []
    error_line = 0

    # Pick the innermost traceback frame that corresponds to the executed string (filename "<string>").
    def _find_exec_lineno(tb: types.TracebackType | None) -> int | None:
        """Return the lineno in the first traceback frame whose filename is '<string>'."""
        while tb is not None:
            if tb.tb_frame.f_code.co_filename == "<string>":
                return tb.tb_lineno
            tb = tb.tb_next
        return None

    lineno_in_exec = _find_exec_lineno(exc_tb)

    # Default to the captured line number if we cannot locate the frame.
    if lineno_in_exec is not None:
        error_line = lineno_in_exec
    else:
        # Fallbacks for SyntaxError or other cases
        error_line = (
            exc_value.lineno
            if isinstance(exc_value, SyntaxError) and exc_value.lineno is not None
            else exc_tb.tb_lineno
        )

    error_msg_parts.append(f"Exception: {exc_type.__name__}: {exc_value!s}")
    error_msg_parts.append(f"In executed code around line {error_line}")
    error_msg_parts.append("\nCode context:")

    # Calculate the range of lines to show
    start_line = max(0, error_line - context_lines - 1)
    end_line = min(len(code_lines), error_line + context_lines)

    # Add the context lines
    for i in range(start_line, end_line):
        line_num = i + 1
        marker = ">> " if line_num == error_line else "   "
        error_msg_parts.append(f"{marker}{line_num}: {code_lines[i]}".rstrip())

    error_msg_parts.append("\nFull traceback:")
    error_msg_parts.append("".join(traceback.format_exception(*exc_info)))

    return "\n".join(error_msg_parts)
