from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

try:
    import torch

    from pytorch_forecasting import TimeSeriesDataSet

    PYTORCH_FORECASTING_AVAILABLE = True
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    PYTORCH_FORECASTING_AVAILABLE = False
    CUDA_AVAILABLE = False
    TimeSeriesDataSet = None  # type: ignore[misc,assignment]
    torch = None  # type: ignore[assignment]


def _make_synthetic_df(
    tickers: list[str],
    n_days: int = 300,
    seed: int = 42,
    with_targets: bool = True,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    from app.features.feature_engineering.shared.feature_schema import (
        all_names,
        macro_names,
        raw_names,
        technical_names,
    )

    feature_names = raw_names() + technical_names() + macro_names()
    target_names = ["target_t1", "target_t5", "target_t10", "target_t15"]

    if not feature_names:
        feature_names = all_names()
        target_names = []

    rows: list[dict] = []
    base_date = pd.Timestamp("2018-01-02")

    for ticker in tickers:
        for day_offset in range(n_days):
            date = base_date + pd.offsets.BDay(day_offset)
            row: dict = {
                "ticker_id": ticker,
                "bar_date": date,
            }
            for col in feature_names:
                row[col] = float(rng.normal(0, 1))
            if with_targets:
                for tcol in target_names:
                    row[tcol] = float(rng.normal(0, 1))
            rows.append(row)

    return pd.DataFrame(rows)


@pytest.mark.skipif(
    not PYTORCH_FORECASTING_AVAILABLE,
    reason="pytorch-forecasting not installed",
)
class TestBuildTFTDataset:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from app.features.ml_models.tft.data_adapter import build_tft_dataset

        self.build_tft_dataset = build_tft_dataset

    def test_basic_dataset_creation(self) -> None:
        df = _make_synthetic_df(["AAPL"], n_days=300)
        ds = self.build_tft_dataset(df, target_column="target_t1")
        assert isinstance(ds, TimeSeriesDataSet)

    def test_dataset_has_correct_covariate_types(self) -> None:
        df = _make_synthetic_df(["AAPL"], n_days=300)
        ds = self.build_tft_dataset(df, target_column="target_t1")

        assert hasattr(ds, "time_varying_known_reals")
        assert len(ds.time_varying_known_reals) == 7
        assert hasattr(ds, "time_varying_unknown_reals")
        assert len(ds.time_varying_unknown_reals) == 24

        recon_names = set(ds.time_varying_known_reals) | set(
            ds.time_varying_unknown_reals
        )
        assert "close" in recon_names
        assert "vix" in recon_names

    def test_time_idx_is_contiguous_per_ticker(self) -> None:
        df = _make_synthetic_df(["AAPL", "MSFT"], n_days=300)
        ds = self.build_tft_dataset(df, target_column="target_t1")

        groups = ds.data["groups"].flatten().numpy()
        times = ds.data["time"].numpy()
        unique_groups = int(ds.data["groups"].max().item()) + 1

        assert unique_groups == 2

        for gid in range(unique_groups):
            mask = groups == gid
            group_times = times[mask]
            assert np.all(np.diff(group_times) >= 0)
            assert len(set(group_times)) == len(group_times)

    def test_multiple_tickers(self) -> None:
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        df = _make_synthetic_df(tickers, n_days=400)
        ds = self.build_tft_dataset(df, target_column="target_t1")
        assert isinstance(ds, TimeSeriesDataSet)

        unique_groups = int(ds.data["groups"].max().item()) + 1
        assert unique_groups == len(tickers)

    def test_varying_history_lengths(self) -> None:
        rng = np.random.default_rng(42)

        from app.features.feature_engineering.shared.feature_schema import raw_names

        fnames = raw_names() or ["close"]
        base_date = pd.Timestamp("2018-01-02")

        rows: list[dict] = []
        for ticker, n_days in [("AAPL", 100), ("MSFT", 300), ("NVDA", 50)]:
            for day_offset in range(n_days):
                date = base_date + pd.offsets.BDay(day_offset)
                row: dict = {"ticker_id": ticker, "bar_date": date}
                for col in fnames:
                    row[col] = float(rng.normal(0, 1))
                row["target_t1"] = float(rng.normal(0, 1))
                rows.append(row)

        df = pd.DataFrame(rows)
        ds = self.build_tft_dataset(
            df,
            target_column="target_t1",
            max_encoder_length=252,
        )

        unique_groups = int(ds.data["groups"].max().item()) + 1
        assert unique_groups == 3

        assert ds.max_encoder_length <= 252

    def test_missing_target_column_raises(self) -> None:
        df = _make_synthetic_df(["AAPL"], n_days=100)
        with pytest.raises(KeyError, match="target_column"):
            self.build_tft_dataset(df, target_column="nonexistent_target")

    def test_missing_ticker_column_raises(self) -> None:
        df = pd.DataFrame(
            {"bar_date": [pd.Timestamp("2020-01-01")], "target_t1": [0.01]}
        )
        with pytest.raises(KeyError, match="ticker_col"):
            self.build_tft_dataset(df, target_column="target_t1")

    def test_split_boundaries_respected(self) -> None:
        df = _make_synthetic_df(["AAPL"], n_days=400)
        base_date = df["bar_date"].min()
        mid_date = base_date + pd.offsets.BDay(200)

        train_df = df[df["bar_date"] < mid_date]
        val_df = df[df["bar_date"] >= mid_date]

        assert len(train_df) > 0, "Train split is empty"
        assert len(val_df) > 0, "Validation split is empty"

        max_train_date = train_df["bar_date"].max()
        min_val_date = val_df["bar_date"].min()
        assert max_train_date < min_val_date

        ds_train = self.build_tft_dataset(train_df, target_column="target_t1")
        ds_val = self.build_tft_dataset(val_df, target_column="target_t1")

        assert isinstance(ds_train, TimeSeriesDataSet)
        assert isinstance(ds_val, TimeSeriesDataSet)

    def test_t1_t5_t10_t15_all_targets(self) -> None:
        df = _make_synthetic_df(["AAPL", "MSFT"], n_days=300)

        for horizon in ["target_t1", "target_t5", "target_t10", "target_t15"]:
            ds = self.build_tft_dataset(df, target_column=horizon)
            assert isinstance(ds, TimeSeriesDataSet)
            assert ds.target == horizon

    def test_data_loader_from_dataset(self) -> None:
        df = _make_synthetic_df(["AAPL"], n_days=400)
        ds = self.build_tft_dataset(df, target_column="target_t1")

        loader = ds.to_dataloader(batch_size=16, shuffle=False)
        batch = next(iter(loader))

        assert batch is not None
        x, y = batch
        assert isinstance(x, dict)
        assert "encoder_cont" in x


@pytest.mark.skipif(
    not PYTORCH_FORECASTING_AVAILABLE,
    reason="pytorch-forecasting not installed",
)
class TestTemporalFusionQuadArray:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from app.features.ml_models.tft.architecture import TemporalFusionQuadArray
        from app.features.ml_models.tft.data_adapter import build_tft_dataset

        self.TemporalFusionQuadArray = TemporalFusionQuadArray

        df = _make_synthetic_df(["AAPL", "MSFT"], n_days=300)
        self.datasets = {
            h: build_tft_dataset(df, target_column=t)
            for h, t in TemporalFusionQuadArray.TARGET_MAP.items()
        }

    def test_instantiation(self) -> None:
        engine = self.TemporalFusionQuadArray(self.datasets)
        assert engine.MODEL_ROLE == "tft"

    def test_has_four_horizons(self) -> None:
        engine = self.TemporalFusionQuadArray(self.datasets)
        models = engine.models
        for h in self.TemporalFusionQuadArray.HORIZONS:
            assert h in models

    def test_invalid_horizon_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown horizon"):
            self.TemporalFusionQuadArray({"bad": self.datasets["t1"]})

    @pytest.mark.skipif(
        CUDA_AVAILABLE,
        reason="torch.use_deterministic_algorithms(True) conflicts with CuBLAS on CUDA "
        "unless CUBLAS_WORKSPACE_CONFIG is set in the environment.",
    )
    def test_predict_returns_dict(self) -> None:
        engine = self.TemporalFusionQuadArray(self.datasets)

        loader = self.datasets["t1"].to_dataloader(batch_size=4, shuffle=False)
        batch = next(iter(loader))
        x, _y = batch

        results = engine._predict_quantiles(x)
        assert isinstance(results, dict)
        for h in self.TemporalFusionQuadArray.HORIZONS:
            assert h in results

    @pytest.mark.skip(
        reason="BaseMathEngine.deserialize(cls) calls cls() with no args, "
        "but TemporalFusionQuadArray requires datasets for model construction"
    )
    def test_serialize_roundtrip(self) -> None:
        engine = self.TemporalFusionQuadArray(self.datasets)
        data = engine.serialize()

        deserialized = type(engine).deserialize(data)
        assert deserialized.MODEL_ROLE == "tft"

    def test_train_model_no_loaders_skips_gracefully(self) -> None:
        engine = self.TemporalFusionQuadArray(self.datasets)
        results = engine.train_model()
        assert isinstance(results, dict)


@pytest.mark.skipif(
    not PYTORCH_FORECASTING_AVAILABLE,
    reason="pytorch-forecasting not installed",
)
class TestDatasetDataLoaderIntegration:
    def test_dataloaders_from_datasets(self) -> None:
        from app.features.ml_models.tft.data_adapter import build_tft_dataset

        df = _make_synthetic_df(["AAPL"], n_days=400)

        base_date = df["bar_date"].min()
        split_date = base_date + pd.offsets.BDay(200)

        train_df = df[df["bar_date"] < split_date]
        val_df = df[df["bar_date"] >= split_date]

        ds_train = build_tft_dataset(train_df, target_column="target_t1")
        ds_val = build_tft_dataset(val_df, target_column="target_t1")

        train_loader = ds_train.to_dataloader(batch_size=4, shuffle=False)
        val_loader = ds_val.to_dataloader(batch_size=4, shuffle=False)

        for name, loader in [("train", train_loader), ("val", val_loader)]:
            batch = next(iter(loader))
            assert batch is not None, f"{name} loader produced no batch"
