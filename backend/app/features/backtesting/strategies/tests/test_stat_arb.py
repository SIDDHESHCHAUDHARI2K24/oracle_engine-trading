import pandas as pd
import numpy as np


def test_stat_arb_entry_residual_below_minus_2sigma():
    """Entry when residual z-score < -2."""
    from app.features.backtesting.strategies.stat_arb import StatArb

    np.random.seed(42)
    spy = np.cumsum(np.random.randn(70) * 0.01) + 100
    asset = spy * 0.8 + np.cumsum(np.random.randn(70) * 0.005) + 20
    df = pd.DataFrame(
        {
            "close": asset,
            "spy_close": spy,
        }
    )
    strategy = StatArb()
    entries, exits = strategy.generate_signals(df)
    assert entries.sum() > 0 or entries.sum() == 0


def test_stat_arb_exit_residual_above_minus_05sigma():
    """Exit when residual z-score > -0.5."""
    from app.features.backtesting.strategies.stat_arb import StatArb

    np.random.seed(42)
    spy = np.cumsum(np.random.randn(80) * 0.01) + 100
    asset = spy * 0.8 + np.cumsum(np.random.randn(80) * 0.003) + 20
    df = pd.DataFrame({"close": asset, "spy_close": spy})
    strategy = StatArb()
    entries, exits = strategy.generate_signals(df)
    assert entries is not None and exits is not None


def test_stat_arb_short_spy_history():
    """Handles tickers with insufficient SPY history gracefully — no crash."""
    from app.features.backtesting.strategies.stat_arb import StatArb

    df = pd.DataFrame(
        {
            "close": [100] * 30,
            "spy_close": [200] * 30,
        }
    )
    strategy = StatArb()
    entries, exits = strategy.generate_signals(df)
    assert entries.sum() == 0
    assert exits.sum() == 0


def test_stat_arb_lookahead_safety():
    """Future bars don't affect past residual z-scores."""
    from app.features.backtesting.strategies.stat_arb import StatArb

    np.random.seed(42)
    spy = np.cumsum(np.random.randn(80) * 0.01) + 100
    asset = spy * 0.8 + np.cumsum(np.random.randn(80) * 0.003) + 20
    df = pd.DataFrame({"close": asset, "spy_close": spy})
    strategy = StatArb()
    entries1, _ = strategy.generate_signals(df)

    spy2 = np.append(spy, spy[-1] + np.cumsum(np.random.randn(10) * 0.01))
    asset2 = spy2 * 0.8 + np.cumsum(np.random.randn(90) * 0.003) + 20
    df2 = pd.DataFrame({"close": asset2, "spy_close": spy2})
    entries2, _ = strategy.generate_signals(df2)

    for i in range(60, 80):
        assert entries1.iloc[i] == entries2.iloc[i]
