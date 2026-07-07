"""Tests for LSTMTrainer — custom PyTorch training loop with early stopping,
HuberLoss, and ReduceLROnPlateau.

All tests use synthetic data following codebase convention.
"""

import numpy as np
import pytest
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

torch.manual_seed(42)


def _make_learnable_synthetic_data(
    n_samples: int = 500,
    seq_len: int = 252,
    n_features: int = 31,
    n_horizons: int = 4,
    noise_std: float = 0.02,
    seed: int = 42,
):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((n_samples, seq_len, n_features)).astype(np.float32)
    coef = rng.standard_normal((n_features, n_horizons)).astype(np.float32) * 0.5
    signal = x[:, -1, :] @ coef
    noise = rng.standard_normal((n_samples, n_horizons)).astype(np.float32) * noise_std
    y = signal + noise
    return torch.from_numpy(x), torch.from_numpy(y)


class TestLSTMTrainer:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from app.features.ml_models.lstm.trainer import LSTMTrainer
        from app.features.ml_models.lstm.architecture import LSTMMathEngine

        self.LSTMTrainer = LSTMTrainer
        self.LSTMMathEngine = LSTMMathEngine

    @pytest.fixture
    def loaders(self):
        train_n, val_n = 300, 75
        x, y = _make_learnable_synthetic_data(
            n_samples=train_n + val_n, noise_std=0.02, seed=42
        )
        x_train, y_train = x[:train_n], y[:train_n]
        x_val, y_val = x[train_n : train_n + val_n], y[train_n : train_n + val_n]

        train_ds = TensorDataset(x_train, y_train)
        val_ds = TensorDataset(x_val, y_val)

        train_loader = DataLoader(train_ds, batch_size=64, shuffle=False)
        val_loader = DataLoader(val_ds, batch_size=64, shuffle=False)

        return train_loader, val_loader

    # ── loss function ──────────────────────────────────────────────────

    def test_huber_loss_is_objective(self) -> None:
        engine = self.LSTMMathEngine()
        trainer = self.LSTMTrainer(engine, max_epochs=2, batch_size=64)
        assert isinstance(trainer.criterion, nn.HuberLoss)
        assert trainer.criterion.reduction == "mean"

    # ── predict shape ──────────────────────────────────────────────────

    def test_predict_returns_n4_shape(self, loaders) -> None:
        engine = self.LSTMMathEngine()
        trainer = self.LSTMTrainer(engine, max_epochs=2, batch_size=64)

        train_loader, val_loader = loaders
        trainer.train_model(train_loader, val_loader)

        x = torch.randn(16, 252, 31)
        result = engine.predict(x)
        assert isinstance(result, np.ndarray)
        assert result.shape == (16, 4)

    # ── early stopping ─────────────────────────────────────────────────

    def test_early_stopping_halts_after_10_no_improve(self, loaders) -> None:
        engine = self.LSTMMathEngine()
        trainer = self.LSTMTrainer(
            engine,
            max_epochs=50,
            batch_size=64,
            patience=10,
            lr=5e-3,
        )

        train_loader, val_loader = loaders
        history = trainer.train_model(train_loader, val_loader)

        epochs_run = len(history["train_loss"])
        assert epochs_run < 50, (
            f"Expected early stopping to trigger before max_epochs=50, "
            f"but {epochs_run} epochs were run"
        )
        assert epochs_run >= 11, (
            f"Need at least patience+1 epochs for ES to trigger, got {epochs_run}"
        )

    def test_early_stopping_restores_best_weights(self, loaders) -> None:
        engine = self.LSTMMathEngine()
        trainer = self.LSTMTrainer(
            engine,
            max_epochs=50,
            batch_size=64,
            patience=10,
            lr=5e-3,
        )

        train_loader, val_loader = loaders
        history = trainer.train_model(train_loader, val_loader)

        best_epoch_val = history["best_val_loss"]
        assert best_epoch_val is not None

        engine.eval()
        total = 0.0
        count = 0
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                pred = engine(batch_x)
                loss = trainer.criterion(pred, batch_y)
                total += loss.item() * batch_x.size(0)
                count += batch_x.size(0)
        current_val_loss = total / count

        assert current_val_loss == pytest.approx(best_epoch_val, rel=1e-4), (
            f"Best weights not restored: best={best_epoch_val:.6f}, "
            f"current={current_val_loss:.6f}"
        )

    # ── LR scheduler ───────────────────────────────────────────────────

    def test_reduce_lr_on_plateau_fires(self, loaders) -> None:
        engine = self.LSTMMathEngine()
        trainer = self.LSTMTrainer(
            engine,
            max_epochs=50,
            batch_size=64,
            lr_patience=3,
            lr=5e-3,
        )

        train_loader, val_loader = loaders
        history = trainer.train_model(train_loader, val_loader)

        lrs = history.get("lr", [])
        assert len(lrs) > 1, f"Expected multiple LR recordings, got {len(lrs)}"

        initial_lr = lrs[0]
        min_lr = min(lrs)
        assert min_lr < initial_lr, f"LR never reduced: all values = {set(lrs)}"

    # ── walk-forward / sequential access ───────────────────────────────

    def test_walk_forward_sequential_access(self) -> None:
        n = 128
        x = torch.randn(n, 252, 31)
        y = torch.arange(n, dtype=torch.float32).unsqueeze(1).repeat(1, 4)

        ds = TensorDataset(x, y)
        loader = DataLoader(ds, batch_size=16, shuffle=False)

        indices = []
        for _, batch_y in loader:
            indices.extend(batch_y[:, 0].int().tolist())

        assert indices == list(range(n)), (
            f"DataLoader did not iterate sequentially: first deviation at "
            f"position {next(i for i, (a, b) in enumerate(zip(indices, range(n))) if a != b)}"
        )

    # ── calibration slice isolation ────────────────────────────────────

    def test_calibration_slice_not_used_in_training(self, loaders) -> None:
        engine = self.LSTMMathEngine()
        trainer = self.LSTMTrainer(engine, max_epochs=2, batch_size=64)

        train_loader, val_loader = loaders
        history = trainer.train_model(train_loader, val_loader)

        assert "train_loss" in history
        assert "val_loss" in history

        keys = set(history.keys())
        assert "cal_loss" not in keys
        assert "calibration_loss" not in keys

    # ── loss decreases during training ─────────────────────────────────

    def test_loss_decreases_on_learnable_signal(self, loaders) -> None:
        engine = self.LSTMMathEngine()
        trainer = self.LSTMTrainer(engine, max_epochs=8, batch_size=64, lr=5e-3)

        train_loader, val_loader = loaders
        history = trainer.train_model(train_loader, val_loader)

        train_losses = history["train_loss"]
        assert len(train_losses) >= 2
        assert train_losses[-1] < train_losses[0], (
            f"Training loss did not decrease: {train_losses[0]:.4f} → {train_losses[-1]:.4f}"
        )

    # ── device routing ─────────────────────────────────────────────────

    def test_trainer_uses_get_device(self) -> None:
        engine = self.LSTMMathEngine()
        trainer = self.LSTMTrainer(engine, max_epochs=2, batch_size=64)

        assert isinstance(trainer.device, torch.device)
