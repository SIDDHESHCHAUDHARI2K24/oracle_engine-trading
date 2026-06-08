"""ConstituentSource protocol and utility functions."""

from typing import Protocol


class ConstituentSource(Protocol):
    """Protocol for adapters that fetch index constituent symbols."""

    async def fetch_constituents(self) -> list[str]:
        """Return list of uppercase, normalized ticker symbols."""
        ...


def normalize_constituent_symbol(symbol: str) -> str:
    """Normalize a constituent symbol to match Alpaca format.

    Rules: uppercase, dots to dashes (BRK.B → BRK-B), strip whitespace.
    """
    return symbol.strip().upper().replace(".", "-")
