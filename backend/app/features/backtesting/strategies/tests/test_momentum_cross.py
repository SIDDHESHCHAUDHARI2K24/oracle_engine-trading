import pandas as pd


def test_momentum_cross_entry_on_crossover():
    """Entry on sma_50 crossing above sma_200."""
    from app.features.backtesting.strategies.momentum_cross import MomentumCross

    df = pd.DataFrame(
        {
            "close": [100] * 80,
            "sma_50": [95] * 50 + [98] * 10 + [102] * 20,
            "sma_200": [98] * 60 + [100] * 20,
        }
    )
    strategy = MomentumCross()
    entries, exits = strategy.generate_signals(df)
    assert entries.iloc[60]


def test_momentum_cross_exit_on_inverse_crossover():
    """Exit on sma_50 crossing below sma_200."""
    from app.features.backtesting.strategies.momentum_cross import MomentumCross

    df = pd.DataFrame(
        {
            "close": [100] * 80,
            "sma_50": [105] * 50 + [101] * 10 + [98] * 20,
            "sma_200": [100] * 80,
        }
    )
    strategy = MomentumCross()
    entries, exits = strategy.generate_signals(df)
    assert exits.iloc[60]


def test_momentum_cross_no_crossover():
    """No signal when SMAs never cross."""
    from app.features.backtesting.strategies.momentum_cross import MomentumCross

    df = pd.DataFrame(
        {
            "close": [100] * 80,
            "sma_50": [105] * 80,
            "sma_200": [100] * 80,
        }
    )
    strategy = MomentumCross()
    entries, exits = strategy.generate_signals(df)
    assert entries.sum() == 0
    assert exits.sum() == 0


def test_momentum_cross_lookahead_safety():
    """Future bars don't affect past crossover signals."""
    from app.features.backtesting.strategies.momentum_cross import MomentumCross

    df = pd.DataFrame(
        {
            "close": [100] * 80,
            "sma_50": [95] * 50 + [98] * 10 + [102] * 20,
            "sma_200": [98] * 60 + [100] * 20,
        }
    )
    strategy = MomentumCross()
    entries1, _ = strategy.generate_signals(df)

    df2 = pd.concat(
        [
            df,
            pd.DataFrame(
                {"close": [100] * 10, "sma_50": [999] * 10, "sma_200": [1] * 10}
            ),
        ],
        ignore_index=True,
    )
    entries2, _ = strategy.generate_signals(df2)

    for i in range(80):
        assert entries1.iloc[i] == entries2.iloc[i]
