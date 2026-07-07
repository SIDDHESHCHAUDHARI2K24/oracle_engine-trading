"""LSTMTrainer — custom PyTorch training loop with HuberLoss, early stopping,
and ReduceLROnPlateau.  Device-routed through ``get_device()``.
"""

from __future__ import annotations

import copy
from typing import Any

import torch
import torch.nn as nn

from app.core.services.torch_device import get_device
from app.features.ml_models.lstm.architecture import LSTMMathEngine


class LSTMTrainer:
    """Custom training loop for ``LSTMMathEngine``.

    Implements the ``BaseMathEngine.train_model`` contract:
    accepts pre-split ``DataLoader`` instances and returns a
    per-epoch history dict.
    """

    def __init__(
        self,
        engine: LSTMMathEngine,
        max_epochs: int = 100,
        batch_size: int = 256,
        patience: int = 10,
        lr_patience: int = 5,
        lr_factor: float = 0.5,
        lr: float = 1e-3,
        weight_decay: float = 1e-4,
    ) -> None:
        self.engine = engine
        self.max_epochs = max_epochs
        self.batch_size = batch_size
        self.patience = patience
        self.lr_patience = lr_patience
        self.lr_factor = lr_factor
        self.lr = lr
        self.weight_decay = weight_decay

        self.device = get_device()
        self.criterion = nn.HuberLoss(reduction="mean")

        self.train_loss_history: list[float] = []
        self.val_loss_history: list[float] = []
        self.lr_history: list[float] = []

    def train_model(
        self,
        train_loader: torch.utils.data.DataLoader,
        val_loader: torch.utils.data.DataLoader,
    ) -> dict[str, Any]:
        self.engine.to(self.device)

        optimizer = torch.optim.AdamW(
            self.engine.parameters(),
            lr=self.lr,
            weight_decay=self.weight_decay,
        )
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode="min",
            patience=self.lr_patience,
            factor=self.lr_factor,
        )

        best_val_loss: float = float("inf")
        best_weights: dict | None = None
        no_improve_epochs: int = 0

        self.train_loss_history = []
        self.val_loss_history = []
        self.lr_history = []

        for epoch in range(1, self.max_epochs + 1):
            train_loss = self._run_epoch(train_loader, optimizer, training=True)
            self.train_loss_history.append(train_loss)

            val_loss = self._run_epoch(val_loader, optimizer, training=False)
            self.val_loss_history.append(val_loss)

            current_lr = optimizer.param_groups[0]["lr"]
            self.lr_history.append(current_lr)

            scheduler.step(val_loss)

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_weights = copy.deepcopy(self.engine.state_dict())
                no_improve_epochs = 0
            else:
                no_improve_epochs += 1

            if no_improve_epochs >= self.patience:
                break

        if best_weights is not None:
            self.engine.load_state_dict(best_weights)

        self.engine.to(torch.device("cpu"))

        return {
            "train_loss": self.train_loss_history,
            "val_loss": self.val_loss_history,
            "lr": self.lr_history,
            "best_val_loss": best_val_loss,
            "epochs_run": len(self.train_loss_history),
        }

    # ── helpers ────────────────────────────────────────────────────────

    def _run_epoch(
        self,
        loader: torch.utils.data.DataLoader,
        optimizer: torch.optim.Optimizer,
        *,
        training: bool,
    ) -> float:
        if training:
            self.engine.train()
        else:
            self.engine.eval()

        total_loss: float = 0.0
        n_samples: int = 0

        for batch_x, batch_y in loader:
            batch_x = batch_x.to(self.device)
            batch_y = batch_y.to(self.device)

            if training:
                optimizer.zero_grad()

            pred = self.engine(batch_x)
            loss = self.criterion(pred, batch_y)

            if training:
                loss.backward()
                optimizer.step()

            total_loss += loss.item() * batch_x.size(0)
            n_samples += batch_x.size(0)

        return total_loss / n_samples
