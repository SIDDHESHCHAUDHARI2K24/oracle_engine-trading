"""S&P 500 constituent source — scrapes Wikipedia."""
import io
import httpx
import pandas as pd
from ..base import normalize_constituent_symbol

class SP500Source:
    """Fetches S&P 500 constituents from Wikipedia."""

    async def fetch_constituents(self) -> list[str]:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        tables = pd.read_html(io.StringIO(resp.text))
        df = tables[0]
        symbols = df["Symbol"].tolist()
        return [normalize_constituent_symbol(s) for s in symbols]
