import pandas as pd
from app.features.backtesting.strategies.mean_reversion import MeanReversion


def test_mean_reversion_entry_below_bb_lower():
    """Entry triggers when close crosses below bb_lower."""
    df = pd.DataFrame({
        'close': [100, 95, 90, 92, 88],
        'bb_lower': [98, 97, 92, 91, 90],
        'bb_middle': [100, 99, 98, 97, 96],
    })
    strategy = MeanReversion()
    entries, exits = strategy.generate_signals(df)
    assert entries.iloc[4]
    assert entries.iloc[2]
    assert not entries.iloc[3]
    assert exits.sum() >= 0


def test_mean_reversion_exit_above_bb_middle():
    """Exit triggers when close crosses above bb_middle."""
    df = pd.DataFrame({
        'close': [88, 92, 96, 100, 102],
        'bb_lower': [90, 91, 92, 93, 94],
        'bb_middle': [98, 97, 96, 95, 94],
    })
    strategy = MeanReversion()
    entries, exits = strategy.generate_signals(df)
    assert exits.iloc[3]
    assert exits.iloc[4]


def test_mean_reversion_no_signal():
    """No signals when price stays within bands."""
    df = pd.DataFrame({
        'close': [98, 98, 98, 98, 98],
        'bb_lower': [95, 95, 95, 95, 95],
        'bb_middle': [100, 100, 100, 100, 100],
    })
    strategy = MeanReversion()
    entries, exits = strategy.generate_signals(df)
    assert entries.sum() == 0
    assert exits.sum() == 0


def test_mean_reversion_lookahead_safety():
    """Changing future bars does not change past signals."""
    df = pd.DataFrame({
        'close': [100, 95, 90, 92, 88],
        'bb_lower': [98, 97, 92, 91, 90],
        'bb_middle': [100, 99, 98, 97, 96],
    })
    strategy = MeanReversion()
    entries1, _ = strategy.generate_signals(df)

    df2 = pd.concat([df, pd.DataFrame({
        'close': [999], 'bb_lower': [1], 'bb_middle': [2]
    })], ignore_index=True)
    entries2, _ = strategy.generate_signals(df2)

    for i in range(5):
        assert entries1.iloc[i] == entries2.iloc[i]
