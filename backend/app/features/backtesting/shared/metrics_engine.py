import pandas as pd
import vectorbt as vbt


class MetricsEngine:
    def __init__(
        self,
        init_cash: float = 100_000.0,
        fees: float = 0.001,
        risk_free: float = 0.045,
        freq: str = "1D",
    ):
        self.init_cash = init_cash
        self.fees = fees
        self.risk_free = risk_free
        self.freq = freq

    def run(self, close: pd.Series, entries: pd.Series, exits: pd.Series) -> dict:
        if not entries.any():
            return self._empty_metrics()

        try:
            portfolio = vbt.Portfolio.from_signals(
                close=close,
                entries=entries,
                exits=exits,
                init_cash=self.init_cash,
                fees=self.fees,
                freq=self.freq,
            )
        except Exception:
            return self._empty_metrics()

        trades = portfolio.trades
        if trades.count() == 0:
            return self._empty_metrics()

        records = trades.records
        gross_profits = 0.0
        gross_losses = 0.0
        if len(records) > 0:
            pnl = (
                records["pnl"]
                if "pnl" in records.columns
                else records.get("return", pd.Series([0.0]))
            )
            gross_profits = float(pnl[pnl > 0].sum())
            gross_losses = float(abs(pnl[pnl < 0].sum()))

        profit_factor = (
            gross_profits / gross_losses
            if gross_losses > 0
            else (float("inf") if gross_profits > 0 else 0.0)
        )
        if profit_factor == float("inf"):
            profit_factor = 999.0

        sharpe = portfolio.sharpe_ratio(risk_free=self.risk_free)
        max_dd = portfolio.max_drawdown()
        total_ret = portfolio.total_return()
        win_rate = trades.win_rate() or 0.0

        return {
            "sharpe_ratio": float(sharpe) if not pd.isna(float(sharpe)) else 0.0,
            "max_drawdown": float(max_dd) if not pd.isna(float(max_dd)) else 0.0,
            "total_return": float(total_ret) if not pd.isna(float(total_ret)) else 0.0,
            "win_rate": float(win_rate) if not pd.isna(float(win_rate)) else 0.0,
            "profit_factor": float(profit_factor),
            "total_trades": int(trades.count()),
            "equity_curve": self._extract_equity_curve(portfolio),
        }

    def _empty_metrics(self) -> dict:
        return {
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "total_return": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_trades": 0,
            "equity_curve": [],
        }

    def _extract_equity_curve(self, portfolio) -> list[dict]:
        try:
            values = portfolio.value()
            return [
                {"date": str(idx.date()), "value": float(v)}
                for idx, v in values.items()
            ]
        except Exception:
            return []
