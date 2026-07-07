"""Shared exceptions for the Data Pipeline (Block A1)."""


class DataPipelineError(Exception):
    """Base exception for all data ingestion errors."""


class DataPipelineAlert(DataPipelineError):
    """Raised when >3 tickers in a batch fail ingestion.

    Carries the list of failed tickers and the source that failed
    for monitoring and alerting purposes.
    """

    def __init__(self, failed_tickers: list[str], source: str, batch_size: int):
        self.failed_tickers = failed_tickers
        self.source = source
        self.batch_size = batch_size
        super().__init__(
            f"DataPipelineAlert: {len(failed_tickers)}/{batch_size} tickers failed "
            f"from source '{source}'. Failed: {', '.join(failed_tickers[:10])}"
            f"{'...' if len(failed_tickers) > 10 else ''}"
        )


class FetcherError(DataPipelineError):
    """Raised when a single fetcher fails after exhausting retries."""

    def __init__(self, source: str, symbols: list[str], original_error: Exception | None = None):
        self.source = source
        self.symbols = symbols
        self.original_error = original_error
        msg = f"Fetcher '{source}' failed for {len(symbols)} symbols: {symbols[:5]}"
        if original_error:
            msg += f" — {original_error}"
        super().__init__(msg)


class EmptyDataError(FetcherError):
    """Raised when a fetcher returns an empty DataFrame for every requested symbol.

    This is distinct from a partial failure — it means the source returned
    zero rows (e.g., yfinance silent empty return). Treated as failure to
    trigger failover.
    """

    def __init__(self, source: str, symbols: list[str]):
        super().__init__(source, symbols)
