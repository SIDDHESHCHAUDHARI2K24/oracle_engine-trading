from io import BytesIO

import numpy as np
import pytest
import torch

torch.manual_seed(42)


class TestLSTMMathEngine:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from app.features.ml_models.lstm.architecture import LSTMMathEngine

        self.LSTMMathEngine = LSTMMathEngine
        self.model = LSTMMathEngine()

    @pytest.fixture
    def batch(self) -> torch.Tensor:
        return torch.randn(16, 252, 31)

    def test_forward_shape(self, batch: torch.Tensor) -> None:
        output = self.model(batch)
        assert output.shape == (16, 4)

    def test_forward_shape_single(self) -> None:
        x = torch.randn(1, 252, 31)
        output = self.model(x)
        assert output.shape == (1, 4)

    def test_output_unbounded(self, batch: torch.Tensor) -> None:
        output = self.model(batch)
        assert not torch.all((output >= 0) & (output <= 1))

    def test_no_embedding_layers(self) -> None:
        model = self.LSTMMathEngine()
        assert model.lstm.input_size == 31
        embedding_types = (torch.nn.Embedding,)
        for module in model.modules():
            assert not isinstance(module, embedding_types)

    def test_predict_returns_numpy(self, batch: torch.Tensor) -> None:
        result = self.model.predict(batch)
        assert isinstance(result, np.ndarray)
        assert result.shape == (16, 4)

    def test_predict_single_returns_numpy(self) -> None:
        x = torch.randn(1, 252, 31)
        result = self.model.predict(x)
        assert isinstance(result, np.ndarray)
        assert result.shape == (1, 4)

    def test_serialize_roundtrip(self, batch: torch.Tensor) -> None:
        model_a = self.LSTMMathEngine()
        pred_a = model_a.predict(batch)

        data = model_a.serialize()
        model_b = self.LSTMMathEngine.deserialize(data)
        pred_b = model_b.predict(batch)

        assert np.allclose(pred_a, pred_b, atol=1e-6)

    def test_model_role(self) -> None:
        assert self.model.MODEL_ROLE == "lstm"

    def test_model_role_classvar(self) -> None:
        assert self.LSTMMathEngine.MODEL_ROLE == "lstm"

    def test_serialize_includes_model_role(self) -> None:
        data = self.model.serialize()
        buf = BytesIO(data)
        checkpoint = torch.load(buf, weights_only=False)
        assert checkpoint["model_role"] == "lstm"
