"""Detection data model for ML pipeline"""
from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class DetectedCard:
    """Detected card with bounding box from ML model"""
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    kind: str  # "player" or "board"
    score: float
    classification: Optional[str] = None
