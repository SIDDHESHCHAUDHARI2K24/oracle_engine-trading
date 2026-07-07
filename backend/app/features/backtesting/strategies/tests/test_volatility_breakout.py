import pandas as pd


def test_vol_breakout_entry_atr_spike_and_new_high():
    """Entry when ATR spikes AND close hits new 20-day high."""
    from app.features.backtesting.strategies.volatility_breakout import (
        VolatilityBreakout,
    )

    closes = [100] * 21 + [105] + [100] * 8
    atr_14 = [1.0] * 21 + [3.0] + [1.0] * 8
    df = pd.DataFrame(
        {
            "close": closes,
            "atr_14": atr_14,
        }
    )
    strategy = VolatilityBreakout()
    entries, exits = strategy.generate_signals(df)
    assert entries.sum() > 0


def test_vol_breakout_no_spike():
    """No entry without ATR spike."""
    from app.features.backtesting.strategies.volatility_breakout import (
        VolatilityBreakout,
    )

    df = pd.DataFrame(
        {
            "close": [100] * 30,
            "atr_14": [1.0] * 30,
        }
    )
    strategy = VolatilityBreakout()
    entries, exits = strategy.generate_signals(df)
    assert entries.sum() == 0


def test_vol_breakout_exit_below_pct_of_high():
    """Exit when close drops below 95% of 20-day high."""
    from app.features.backtesting.strategies.volatility_breakout import (
        VolatilityBreakout,
    )

    closes = [100] * 20 + [110] * 5 + [103]
    df = pd.DataFrame(
        {
            "close": closes,
            "atr_14": [1.0] * 26,
        }
    )
    strategy = VolatilityBreakout()
    entries, exits = strategy.generate_signals(df)
    assert exits.iloc[-1]


def test_vol_breakout_lookahead_safety():
    """Future bars don't affect past signals."""
    from app.features.backtesting.strategies.volatility_breakout import (
        VolatilityBreakout,
    )

    df = pd.DataFrame({"close": [100] * 30, "atr_14": [1.0] * 30})
    strategy = VolatilityBreakout()
    entries1, exits1 = strategy.generate_signals(df)

    df2 = pd.concat(
        [df, pd.DataFrame({"close": [200] * 5, "atr_14": [10.0] * 5})],
        ignore_index=True,
    )
    entries2, exits2 = strategy.generate_signals(df2)

    for i in range(30):
        assert entries1.iloc[i] == entries2.iloc[i]
        assert exits1.iloc[i] == exits2.iloc[i]
