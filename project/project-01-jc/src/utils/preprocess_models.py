"""Image preprocess result model. See spec-02 §3.1."""
from dataclasses import dataclass

import numpy as np


@dataclass
class PreprocessResult:
    """Result of the image preprocess pipeline."""

    image: np.ndarray | None = None  # processed BGR image; None on decode error
    rotation_angle: int = 0          # clockwise rotation applied: 0/90/180/270
    quad: list | None = None         # detected card quad [[x,y],...] or None
    found_card: bool = False         # whether a card region was detected
    error: str | None = None         # None = success
