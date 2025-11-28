"""CLI utility decorators and helpers."""

from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

import click

from .context import VprojContext
from .vivado import check_vivado_available

F = TypeVar("F", bound=Callable)


def vivado_command(check_vivado: bool = True) -> Callable[[F], F]:
    """Decorator for CLI commands that use VprojContext.

    This decorator:
    1. Optionally checks if Vivado is available
    2. Creates a VprojContext from click's ctx.obj
    3. Passes the context as the first argument to the decorated function
    4. Handles SystemExit for the return value

    Usage:
        @cli.command("my-command")
        @click.argument("arg")
        @vivado_command()
        def my_command(ctx: VprojContext, arg):
            '''My command docstring.'''
            return some_cmd(arg, ctx)

    Args:
        check_vivado: If True (default), verify Vivado is available before running.
                      Set to False for commands that don't need Vivado.
    """

    def decorator(f: F) -> F:
        @click.pass_context
        @wraps(f)
        def wrapper(click_ctx: click.Context, *args, **kwargs):
            ctx = VprojContext.from_click_obj(click_ctx.obj)

            if check_vivado:
                check_vivado_available(ctx.settings, ctx.proj_dir, ctx.batch)

            result = f(ctx, *args, **kwargs)

            # Handle return value - if it's an int, use it as exit code
            if isinstance(result, int):
                raise SystemExit(result)

            return result

        return wrapper  # type: ignore

    return decorator


def no_vivado_command() -> Callable[[F], F]:
    """Decorator for CLI commands that don't need Vivado.

    This is a convenience wrapper for @vivado_command(check_vivado=False).
    Use this for commands like 'check' that use verilator, not Vivado.
    """
    return vivado_command(check_vivado=False)
