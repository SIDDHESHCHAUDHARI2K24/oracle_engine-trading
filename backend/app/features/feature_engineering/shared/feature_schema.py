"""Locked 31-dimensional feature schema contract.

Single source of truth for the feature matrix column definition.
Every downstream module imports from here — no module hardcodes a column list.

The 31-dim contract: 5 raw + 19 technical + 7 macro = 31 input features.
Plus 4 continuous-return targets: T+1, T+5, T+10, T+15.
"""

from dataclasses import dataclass
from enum import Enum

FEATURE_SCHEMA_VERSION = "v1.0"


class FeatureCategory(str, Enum):
    RAW = "RAW"
    TECHNICAL = "TECHNICAL"
    MACRO = "MACRO"


class TargetCategory(str, Enum):
    TARGET = "TARGET"


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    category: FeatureCategory
    dtype: str
    source_lib: str
    window: int | None = None


@dataclass(frozen=True)
class TargetSpec:
    name: str
    category: TargetCategory = TargetCategory.TARGET
    dtype: str = "NUMERIC(18,8)"
    horizon: int = 0


RAW_FEATURES: list[FeatureSpec] = [
    FeatureSpec("open", FeatureCategory.RAW, "NUMERIC(18,6)", "raw"),
    FeatureSpec("high", FeatureCategory.RAW, "NUMERIC(18,6)", "raw"),
    FeatureSpec("low", FeatureCategory.RAW, "NUMERIC(18,6)", "raw"),
    FeatureSpec("close", FeatureCategory.RAW, "NUMERIC(18,6)", "raw"),
    FeatureSpec("volume", FeatureCategory.RAW, "BIGINT", "raw"),
]

TECHNICAL_FEATURES: list[FeatureSpec] = [
    FeatureSpec("returns_1d", FeatureCategory.TECHNICAL, "NUMERIC(18,8)", "pandas"),
    FeatureSpec("returns_5d", FeatureCategory.TECHNICAL, "NUMERIC(18,8)", "pandas"),
    FeatureSpec("returns_10d", FeatureCategory.TECHNICAL, "NUMERIC(18,8)", "pandas"),
    FeatureSpec("returns_20d", FeatureCategory.TECHNICAL, "NUMERIC(18,8)", "pandas"),
    FeatureSpec("rsi_14", FeatureCategory.TECHNICAL, "NUMERIC(18,6)", "pandas", 14),
    FeatureSpec("macd", FeatureCategory.TECHNICAL, "NUMERIC(18,8)", "pandas"),
    FeatureSpec("macd_signal", FeatureCategory.TECHNICAL, "NUMERIC(18,8)", "pandas"),
    FeatureSpec("macd_hist", FeatureCategory.TECHNICAL, "NUMERIC(18,8)", "pandas"),
    FeatureSpec("bb_upper", FeatureCategory.TECHNICAL, "NUMERIC(18,6)", "pandas", 20),
    FeatureSpec("bb_middle", FeatureCategory.TECHNICAL, "NUMERIC(18,6)", "pandas", 20),
    FeatureSpec("bb_lower", FeatureCategory.TECHNICAL, "NUMERIC(18,6)", "pandas", 20),
    FeatureSpec("bb_width", FeatureCategory.TECHNICAL, "NUMERIC(18,8)", "pandas", 20),
    FeatureSpec("atr_14", FeatureCategory.TECHNICAL, "NUMERIC(18,6)", "pandas", 14),
    FeatureSpec(
        "volatility_20d", FeatureCategory.TECHNICAL, "NUMERIC(18,8)", "pandas", 20
    ),
    FeatureSpec(
        "volume_z_score", FeatureCategory.TECHNICAL, "NUMERIC(18,8)", "pandas", 20
    ),
    FeatureSpec("sma_50", FeatureCategory.TECHNICAL, "NUMERIC(18,6)", "pandas", 50),
    FeatureSpec("sma_200", FeatureCategory.TECHNICAL, "NUMERIC(18,6)", "pandas", 200),
    FeatureSpec(
        "price_to_sma50", FeatureCategory.TECHNICAL, "NUMERIC(18,8)", "pandas", 50
    ),
    FeatureSpec(
        "price_to_sma200", FeatureCategory.TECHNICAL, "NUMERIC(18,8)", "pandas", 200
    ),
]

MACRO_FEATURES: list[FeatureSpec] = [
    FeatureSpec("fed_funds_rate", FeatureCategory.MACRO, "NUMERIC(18,6)", "macro"),
    FeatureSpec("cpi", FeatureCategory.MACRO, "NUMERIC(18,6)", "macro"),
    FeatureSpec("unemployment", FeatureCategory.MACRO, "NUMERIC(18,6)", "macro"),
    FeatureSpec("gdp", FeatureCategory.MACRO, "NUMERIC(18,6)", "macro"),
    FeatureSpec("yield_spread_10y_2y", FeatureCategory.MACRO, "NUMERIC(18,6)", "macro"),
    FeatureSpec("vix", FeatureCategory.MACRO, "NUMERIC(18,6)", "macro"),
    FeatureSpec("high_yield_spread", FeatureCategory.MACRO, "NUMERIC(18,6)", "macro"),
]

TARGETS: list[TargetSpec] = [
    TargetSpec("target_t1", horizon=1),
    TargetSpec("target_t5", horizon=5),
    TargetSpec("target_t10", horizon=10),
    TargetSpec("target_t15", horizon=15),
]

FEATURE_SCHEMA: list[FeatureSpec] = RAW_FEATURES + TECHNICAL_FEATURES + MACRO_FEATURES
ALL_SCHEMA = FEATURE_SCHEMA + TARGETS  # type: ignore[operator]


def input_feature_names() -> list[str]:
    return [f.name for f in FEATURE_SCHEMA]


def target_names() -> list[str]:
    return [t.name for t in TARGETS]


def all_names() -> list[str]:
    return input_feature_names() + target_names()


def raw_names() -> list[str]:
    return [f.name for f in RAW_FEATURES]


def technical_names() -> list[str]:
    return [f.name for f in TECHNICAL_FEATURES]


def macro_names() -> list[str]:
    return [f.name for f in MACRO_FEATURES]


def input_count() -> int:
    return 31


def target_count() -> int:
    return 4


def burn_in_days() -> int:
    return max(
        max((f.window or 0) for f in TECHNICAL_FEATURES),
        252,
    )


def max_target_horizon() -> int:
    return max(t.horizon for t in TARGETS)
