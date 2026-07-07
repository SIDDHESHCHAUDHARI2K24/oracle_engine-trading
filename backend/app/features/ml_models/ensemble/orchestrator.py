"""EnsembleOrchestrator — chains blender, calibrator, and scorer into a single
predict path that emits blended predictions, conformal intervals, and conviction
scores for each of the 4 forecast horizons.
"""

from __future__ import annotations

import numpy as np

HORIZON_LABELS = ["t1", "t5", "t10", "t15"]


class EnsembleOrchestrator:
    def __init__(self, blender, calibrator, scorer) -> None:
        self.blender = blender
        self.calibrator = calibrator
        self.scorer = scorer

    def predict(
        self,
        lstm_outputs: np.ndarray,
        tft_outputs: dict[str, np.ndarray],
        features: np.ndarray,
    ) -> dict:
        N = lstm_outputs.shape[0]
        H = lstm_outputs.shape[1]

        tft_q10 = tft_outputs["q10"]
        tft_q50 = tft_outputs["q50"]
        tft_q90 = tft_outputs["q90"]

        blended = np.zeros((N, H), dtype=np.float64)
        for h in range(H):
            for i in range(N):
                blended[i, h] = self.blender.blend_horizon(
                    lstm_outputs[i, h],
                    tft_q10[i, h],
                    tft_q50[i, h],
                    tft_q90[i, h],
                )

        lo, hi = self.calibrator.predict(blended, features)

        conviction = self.scorer.compute_conviction(blended, tft_q10, tft_q90)

        result: dict = {}
        for h, label in enumerate(HORIZON_LABELS):
            result[f"pred_{label}"] = blended[:, h].copy()
            result[f"pred_lo_{label}"] = lo[:, h].copy()
            result[f"pred_hi_{label}"] = hi[:, h].copy()
            result[f"conviction_{label}"] = conviction[:, h].copy()

        result["lstm_outputs"] = lstm_outputs.copy()
        result["tft_q10"] = tft_q10.copy()
        result["tft_q50"] = tft_q50.copy()
        result["tft_q90"] = tft_q90.copy()

        return result
