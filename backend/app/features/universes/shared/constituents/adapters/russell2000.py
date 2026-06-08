"""Russell 2000 constituent source — iShares IWM ETF holdings."""

import io
import csv
import httpx
from ..base import normalize_constituent_symbol


class Russell2000Source:
    """Fetches Russell 2000 constituents from iShares IWM holdings."""

    async def fetch_constituents(self) -> list[str]:
        url = "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund"
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
