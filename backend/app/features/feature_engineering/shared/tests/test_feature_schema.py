"""Tests for the locked feature_schema contract.

Verifies the 31-dim contract: counts, categories, ordering, and helper accessors.
"""

from app.features.feature_engineering.shared.feature_schema import (
    FEATURE_SCHEMA_VERSION,
    input_feature_names,
    target_names,
    raw_names,
    technical_names,
    macro_names,
    all_names,
)


class TestFeatureSchemaContract:
    def test_schema_version_is_defined(self):
        assert FEATURE_SCHEMA_VERSION == "v1.0"

    def test_exactly_31_input_features(self):
        features = input_feature_names()
        assert len(features) == 31, f"Expected 31 features, got {len(features)}"

    def test_exactly_4_targets(self):
        targets = target_names()
        assert len(targets) == 4, f"Expected 4 targets, got {len(targets)}"

    def test_total_35_columns(self):
        assert len(all_names()) == 35

    def test_raw_features_count(self):
        assert len(raw_names()) == 5

    def test_technical_features_count(self):
        assert len(technical_names()) == 19

    def test_macro_features_count(self):
        assert len(macro_names()) == 7

    def test_input_plus_targets_equals_all(self):
        assert input_feature_names() + target_names() == all_names()

    def test_first_five_are_raw(self):
        features = input_feature_names()
        expected_raw = ["open", "high", "low", "close", "volume"]
        assert features[:5] == expected_raw

    def test_raw_features_in_correct_order(self):
        assert raw_names() == ["open", "high", "low", "close", "volume"]

    def test_technical_features_start_at_index_5(self):
        features = input_feature_names()
        assert features[5] == "returns_1d"

    def test_technical_features_end_at_index_24(self):
        features = input_feature_names()
        assert features[23] == "price_to_sma200"

    def test_macro_features_start_at_index_24(self):
        features = input_feature_names()
        assert features[24] == "fed_funds_rate"

    def test_macro_features_end_at_index_31(self):
        features = input_feature_names()
        assert features[30] == "high_yield_spread"

    def test_targets_in_correct_order(self):
        assert target_names() == [
            "target_t1",
            "target_t5",
            "target_t10",
            "target_t15",
        ]

    def test_all_technical_features_present(self):
        expected = [
            "returns_1d",
            "returns_5d",
            "returns_10d",
            "returns_20d",
            "rsi_14",
            "macd",
            "macd_signal",
            "macd_hist",
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "bb_width",
            "atr_14",
            "volatility_20d",
            "volume_z_score",
            "sma_50",
            "sma_200",
            "price_to_sma50",
            "price_to_sma200",
        ]
        assert technical_names() == expected

    def test_all_macro_features_present(self):
        expected = [
            "fed_funds_rate",
            "cpi",
            "unemployment",
            "gdp",
            "yield_spread_10y_2y",
            "vix",
            "high_yield_spread",
        ]
        assert macro_names() == expected

    def test_feature_spec_has_required_fields(self):
        features = input_feature_names()
        from app.features.feature_engineering.shared.feature_schema import (
            FEATURE_SCHEMA,
        )

        for spec in FEATURE_SCHEMA:
            assert spec.name in features or spec.name in target_names()
            assert hasattr(spec, "category")
            assert hasattr(spec, "dtype")
            assert hasattr(spec, "source_lib")
            assert spec.name != ""

    def test_no_duplicate_feature_names(self):
        all_names_list = all_names()
        assert len(all_names_list) == len(set(all_names_list))
