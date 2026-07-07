from __future__ import annotations

import logging
from typing import ClassVar

import numpy as np
import torch
from pytorch_forecasting import (
    TemporalFusionTransformer,
    TimeSeriesDataSet,
)
from pytorch_forecasting.metrics import QuantileLoss
from pytorch_lightning import LightningModule, Trainer
from pytorch_lightning.callbacks import EarlyStopping, LearningRateMonitor
from pytorch_lightning.loggers import CSVLogger
from torch.utils.data import DataLoader

from app.core.services.torch_device import get_device, set_seed
from app.features.ml_models.shared.base import BaseMathEngine

_apply_monkey_patch_done = False


def _apply_ellipsis_patch() -> None:
    global _apply_monkey_patch_done
    if _apply_monkey_patch_done:
        return
    _apply_monkey_patch_done = True

    import pytorch_forecasting.utils._utils as pf_utils

    _orig_getitem = pf_utils.OutputMixIn.__getitem__

    def _patched_getitem(self, k):
        if isinstance(k, tuple) and len(k) >= 1 and k[0] is ...:
            if hasattr(self, "prediction"):
                return self.prediction[k]
            return _orig_getitem(self, k)
        return _orig_getitem(self, k)

    pf_utils.OutputMixIn.__getitem__ = _patched_getitem


_apply_ellipsis_patch()

logger = logging.getLogger(__name__)


def _extract_numpy(output) -> np.ndarray:
    if hasattr(output, "prediction"):
        return output.prediction.detach().cpu().numpy()
    if hasattr(output, "cpu"):
        return output.detach().cpu().numpy()
    if isinstance(output, torch.Tensor):
        return output.detach().cpu().numpy()
    raise TypeError(f"Unsupported output type: {type(output)}")


class _TFTModuleWrapper(LightningModule):
    def __init__(self, tft_model: TemporalFusionTransformer) -> None:
        super().__init__()
        self.model = tft_model

    def forward(self, x: dict[str, torch.Tensor]) -> torch.Tensor:
        return self.model(x)

    def training_step(
        self, batch: tuple[dict[str, torch.Tensor], torch.Tensor], batch_idx: int
    ) -> torch.Tensor:
        x, y = batch
        pred = self.model(x)
        loss = self.model.loss(pred, y)
        self.log("train_loss", loss, on_step=False, on_epoch=True, prog_bar=True)
        return loss

    def validation_step(
        self, batch: tuple[dict[str, torch.Tensor], torch.Tensor], batch_idx: int
    ) -> torch.Tensor:
        x, y = batch
        pred = self.model(x)
        loss = self.model.loss(pred, y)
        self.log("val_loss", loss, on_step=False, on_epoch=True, prog_bar=True)
        return loss

    def configure_optimizers(self):
        return self.model.configure_optimizers()


class TemporalFusionQuadArray(BaseMathEngine):
    """Four-horizon TFT ensemble using pytorch-forecasting + Lightning.

    Each horizon model is a :class:`TemporalFusionTransformer` trained
    with QuantileLoss([0.1, 0.5, 0.9]).  Prediction returns full quantile
    distributions across all horizons.

    Datasets are injected via constructor for testability — this class
    does not create its own ``TimeSeriesDataSet`` instances.
    """

    MODEL_ROLE: ClassVar[str] = "tft"

    HORIZONS: ClassVar[list[str]] = ["t1", "t5", "t10", "t15"]
    TARGET_MAP: ClassVar[dict[str, str]] = {
        "t1": "target_t1",
        "t5": "target_t5",
        "t10": "target_t10",
        "t15": "target_t15",
    }
    QUANTILES: ClassVar[list[float]] = [0.1, 0.5, 0.9]

    def __init__(
        self,
        datasets: dict[str, TimeSeriesDataSet],
        *,
        seed: int = 42,
    ) -> None:
        super().__init__()
        set_seed(seed)
        self.datasets = datasets
        self._wrappers: dict[str, _TFTModuleWrapper] = {}
        self._device: torch.device | None = None

        for horizon, ds in datasets.items():
            self._validate_horizon(horizon)
            tft_model = TemporalFusionTransformer.from_dataset(
                ds,
                learning_rate=1e-3,
                hidden_size=64,
                attention_head_size=4,
                dropout=0.1,
                hidden_continuous_size=32,
                loss=QuantileLoss(self.QUANTILES),
                optimizer="Adam",
                reduce_on_plateau_patience=4,
            )
            self._wrappers[horizon] = _TFTModuleWrapper(tft_model)

    @staticmethod
    def _validate_horizon(horizon: str) -> None:
        if horizon not in TemporalFusionQuadArray.HORIZONS:
            raise ValueError(
                f"Unknown horizon '{horizon}'. Expected one of {TemporalFusionQuadArray.HORIZONS}"
            )

    @property
    def models(self) -> dict[str, TemporalFusionTransformer]:
        return {h: w.model for h, w in self._wrappers.items()}

    def _resolve_device(self) -> torch.device:
        if self._device is None:
            self._device = get_device()
        return self._device

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        raise NotImplementedError(
            "TemporalFusionQuadArray uses predict() not forward(); "
            "forward() is not the primary interface."
        )

    def train_model(
        self,
        train_loaders: dict[str, DataLoader] | None = None,
        val_loaders: dict[str, DataLoader] | None = None,
        *,
        max_epochs: int = 100,
        patience: int = 10,
        min_delta: float = 1e-4,
        enable_progress_bar: bool = False,
    ) -> dict[str, dict]:
        if train_loaders is None:
            train_loaders = {}
        if val_loaders is None:
            val_loaders = {}

        results: dict[str, dict] = {}

        for horizon in self.HORIZONS:
            if horizon not in self._wrappers:
                logger.warning(
                    "No model initialized for horizon '%s'; skipping.", horizon
                )
                continue

            wrapper = self._wrappers[horizon]
            train_loader = train_loaders.get(horizon)
            val_loader = val_loaders.get(horizon)

            if train_loader is None:
                logger.warning(
                    "No train DataLoader for horizon '%s'; skipping.", horizon
                )
                continue

            logger.info("Training TFT for horizon '%s' ...", horizon)

            early_stop = EarlyStopping(
                monitor="val_loss",
                patience=patience,
                min_delta=min_delta,
                mode="min",
                verbose=False,
            )
            lr_monitor = LearningRateMonitor(logging_interval="epoch")

            trainer = Trainer(
                max_epochs=max_epochs,
                accelerator="gpu" if str(self._resolve_device()) == "cuda" else "cpu",
                devices=1,
                callbacks=[early_stop, lr_monitor],
                logger=CSVLogger("lightning_logs", name=f"tft_{horizon}"),
                enable_progress_bar=enable_progress_bar,
                enable_model_summary=False,
            )

            trainer.fit(
                wrapper,
                train_dataloaders=train_loader,
                val_dataloaders=val_loader,
            )

            best_score = (
                early_stop.best_score if hasattr(early_stop, "best_score") else None
            )
            results[horizon] = {
                "best_val_loss": best_score,
                "stopped_epoch": trainer.current_epoch,
            }
            logger.info(
                "TFT horizon '%s' training complete. Best val loss: %s",
                horizon,
                best_score,
            )

        return results

    def predict(self, x: torch.Tensor) -> np.ndarray:
        return self._predict_quantiles(x)

    def _predict_quantiles(
        self,
        data: dict[str, torch.Tensor] | torch.Tensor,
    ) -> np.ndarray:
        results: dict[str, np.ndarray] = {}
        device = self._resolve_device()

        for horizon in self.HORIZONS:
            if horizon not in self._wrappers:
                continue
            wrapper = self._wrappers[horizon]
            wrapper.to(device)
            wrapper.eval()

            with torch.no_grad():
                if isinstance(data, torch.Tensor):
                    output = wrapper(data.to(device))
                    results[horizon] = _extract_numpy(output)
                elif isinstance(data, dict):
                    data_device = {
                        k: v.to(device) if isinstance(v, torch.Tensor) else v
                        for k, v in data.items()
                    }
                    output = wrapper(data_device)
                    results[horizon] = _extract_numpy(output)

        return results
