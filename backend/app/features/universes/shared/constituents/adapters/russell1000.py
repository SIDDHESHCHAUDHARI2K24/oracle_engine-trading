"""Russell 1000 constituent source — iShares IWB ETF holdings."""
import io
import csv
import httpx
from ..base import normalize_constituent_symbol

class Russell1000Source:
    """Fetches Russell 1000 constituents from iShares IWB holdings."""

    async def fetch_constituents(self) -> list[str]:
        url = "https://www.ishares.com/us/products/239707/ishares-russell-1000-etf/1467271812596.ajax?fileType=csv&fileName=IWB_holdings&dataType=fund"
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        symbols = []
        for row in reader:
            ticker = row.get("Ticker", "").strip()
            if ticker and ticker != "-":
                symbols.append(normalize_constituent_symbol(ticker))
        return symbols
