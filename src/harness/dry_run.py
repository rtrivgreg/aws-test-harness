"""
Simple dry-run flag and logging helper.

When dry-run is enabled the harness prints the actions it *would* take
but does not call the mutating AWS APIs.
"""

from __future__ import annotations

import functools
from typing import Any, Callable

from rich.console import Console

console = Console()

# Module-level flag – set by pytest fixture or CLI
_DRY_RUN: bool = False


def set_dry_run(enabled: bool) -> None:
    global _DRY_RUN
    _DRY_RUN = enabled


def is_dry_run() -> bool:
    return _DRY_RUN


def dry_run_guard(action_description: str) -> Callable:
    """
    Decorator that skips the wrapped function when dry-run is active
    and prints what would have happened instead.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if is_dry_run():
                console.print(f"[yellow]DRY-RUN[/yellow] would execute: {action_description}")
                return None
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def log(msg: str, style: str = "cyan") -> None:
    """Consistent console logging."""
    prefix = "[yellow]DRY-RUN[/yellow] " if is_dry_run() else ""
    console.print(f"{prefix}[{style}]{msg}[/{style}]")
