from abc import ABC, abstractmethod
from io import BytesIO
from typing import ClassVar

import numpy as np
import torch


class BaseMathEngine(ABC, torch.nn.Module):
    """Unified contract for all math engines (LSTM, TFT, ensemble).

    Implements ``torch.nn.Module`` and adds train/predict/serialize.
    Consumer code depends on this ABC, not on the concrete engine,
    so the LSTM (custom loop) and TFT (Lightning) are hot-swappable
    under the ensemble orchestrator.
    """

    MODEL_ROLE: ClassVar[str]

    @abstractmethod
    def train_model(
        self,
        train_loader: torch.utils.data.DataLoader,
        val_loader: torch.utils.data.DataLoader,
    ) -> dict: ...

    @abstractmethod
    def predict(self, x: torch.Tensor) -> np.ndarray: ...

    def serialize(self) -> bytes:
        buf = BytesIO()
        torch.save(
            {
                "state_dict": self.state_dict(),
                "model_role": self.MODEL_ROLE,
            },
            buf,
        )
        return buf.getvalue()

    @classmethod
    def deserialize(cls, data: bytes) -> "BaseMathEngine":
        buf = BytesIO(data)
        checkpoint = torch.load(buf, weights_only=False)
        engine = cls()
        engine.load_state_dict(checkpoint["state_dict"])
        return engine
