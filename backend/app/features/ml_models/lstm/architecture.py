from typing import ClassVar

import numpy as np
import torch
import torch.nn as nn

from app.features.ml_models.shared.base import BaseMathEngine


class LSTMMathEngine(BaseMathEngine):
    """Bi-LSTM -> MultiheadAttention -> Mean-Pool -> MLP Head.

    Input:  [B, 252, 31]  feature tensor
    Output: [B, 4]        unbounded continuous returns
    """

    MODEL_ROLE: ClassVar[str] = "lstm"

    def __init__(self) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=31,
            hidden_size=128,
            num_layers=3,
            batch_first=True,
            bidirectional=True,
        )
        self.attention = nn.MultiheadAttention(
            embed_dim=256,
            num_heads=8,
            batch_first=True,
        )
        self.head = nn.Sequential(
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 4),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        lstm_out, _ = self.lstm(x)
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        pooled = attn_out.mean(dim=1)
        return self.head(pooled)

    def train_model(
        self,
        train_loader: torch.utils.data.DataLoader,
        val_loader: torch.utils.data.DataLoader,
    ) -> dict:
        raise NotImplementedError

    def predict(self, x: torch.Tensor) -> np.ndarray:
        self.eval()
        with torch.no_grad():
            out = self.forward(x)
        return out.cpu().numpy()
