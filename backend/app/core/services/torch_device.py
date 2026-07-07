import logging
import random

import numpy as np
import torch

logger = logging.getLogger(__name__)


def get_device() -> torch.device:
    if torch.cuda.is_available():
        device = torch.device("cuda")
        logger.info("Using CUDA device: %s", torch.cuda.get_device_name(0))
        return device
    if torch.backends.mps.is_available():
        device = torch.device("mps")
        logger.info("Using MPS device (Apple Silicon)")
        return device
    device = torch.device("cpu")
    logger.info("Using CPU device")
    return device


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    try:
        torch.use_deterministic_algorithms(True)
    except RuntimeError:
        logger.warning(
            "torch.use_deterministic_algorithms(True) not available — "
            "some operations may be non-deterministic. TFT on CUDA is the "
            "most likely cause."
        )

    logger.info("RNG seeds set to %d", seed)
