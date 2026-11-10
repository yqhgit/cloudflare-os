"""Yield pages. The caller decides when to stop; this does not walk an API by itself."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any


def pages(
    fetch_page: Callable[[int, int], Any],
    *,
    start: int = 1,
    size: int = 20,
    max_pages: int = 10,
) -> Iterator[Any]:
    """Call fetch_page(page, size) at most max_pages times, starting at start."""
    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    if size < 1:
        raise ValueError("size must be at least 1")
    for offset in range(max_pages):
        yield fetch_page(start + offset, size)
