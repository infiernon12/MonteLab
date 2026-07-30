"""ML Service - Abstracts card detection pipeline"""
from typing import List, Tuple, Optional
import logging
import time
import numpy as np
from pathlib import Path
from collections import OrderedDict
from core.domain import DetectedCard

logger = logging.getLogger(__name__)


class MLService:
    """High-level ML detection service with LRU caching"""

    def __init__(self, detector=None, classifier=None):
        self.detector = detector
        self.classifier = classifier
        self.is_available = detector is not None and classifier is not None

        # LRU cache for inference results
        self._cache = OrderedDict()
        self._cache_max_size = 10  # Cache last 10 frames
        self._cache_hits = 0
        self._cache_misses = 0
    
    @classmethod
    def from_weights(cls, yolo_path: str, resnet_path: str, device: str = "cpu"):
        """Factory method to load models from weights"""
        try:
            from ml.detector import TableCardDetector, CardClassifierResNet

            if not Path(yolo_path).exists() or not Path(resnet_path).exists():
                logger.warning("Model weights not found")
                return cls(None, None)

            detector = TableCardDetector(yolo_path, device)
            classifier = CardClassifierResNet(resnet_path, device)

            # Warmup models with dummy inference (important for GPU)
            logger.info("Warming up models...")
            dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
            try:
                _ = detector.predict(dummy_frame, confidence_threshold=0.3)
                dummy_crop = np.zeros((224, 224, 3), dtype=np.uint8)
                _ = classifier.classify_batch([dummy_crop])  # Test batch path
                logger.info("✅ Model warmup completed")
            except Exception as e:
                logger.warning(f"Model warmup failed (non-critical): {e}")

            logger.info("ML models loaded successfully")
            return cls(detector, classifier)

        except Exception as e:
            logger.error(f"Failed to load ML models: {e}")
            return cls(None, None)
    
    def _compute_frame_hash(self, frame: np.ndarray) -> int:
        """Compute fast hash for frame (using sampling to speed up)"""
        # Sample every 10th row and column for speed
        sample = frame[::10, ::10, :]
        return hash(sample.tobytes())

    def _add_to_cache(self, frame_hash: int, result: Tuple[List[DetectedCard], List[DetectedCard]]):
        """Add result to LRU cache"""
        # Remove oldest if cache is full
        if len(self._cache) >= self._cache_max_size:
            self._cache.popitem(last=False)  # Remove oldest (FIFO)

        self._cache[frame_hash] = result
        # Move to end to mark as recently used
        self._cache.move_to_end(frame_hash)

    def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "cache_size": len(self._cache)
        }

    def detect_and_classify(self, frame: np.ndarray,
                           confidence_threshold: float = 0.4) -> Tuple[List[DetectedCard], List[DetectedCard]]:
        """Detect and classify cards with caching, return (player_cards, board_cards)"""

        if not self.is_available:
            logger.warning("ML models not available")
            return [], []

        try:
            # Start total timing
            total_start = time.perf_counter()

            # Check cache first
            frame_hash = self._compute_frame_hash(frame)
            if frame_hash in self._cache:
                self._cache_hits += 1
                self._cache.move_to_end(frame_hash)  # Mark as recently used
                cache_time = (time.perf_counter() - total_start) * 1000
                logger.info(f"🚀 Cache HIT (hit rate: {self.get_cache_stats()['hit_rate']}, time: {cache_time:.2f}ms)")
                return self._cache[frame_hash]

            self._cache_misses += 1

            # Detection
            detect_start = time.perf_counter()
            detections = self.detector.predict(frame, confidence_threshold=confidence_threshold)
            detect_time = (time.perf_counter() - detect_start) * 1000

            # Separate by type
            player_detections = [d for d in detections if d.kind == "player"]
            board_detections = [d for d in detections if d.kind == "board"]

            # Classify
            classify_start = time.perf_counter()
            classified_player = self._classify_detections(player_detections, frame)
            classified_board = self._classify_detections(board_detections, frame)
            classify_time = (time.perf_counter() - classify_start) * 1000

            total_time = (time.perf_counter() - total_start) * 1000

            logger.info(f"✅ Detected {len(classified_player)} player, {len(classified_board)} board cards | "
                       f"Total: {total_time:.2f}ms (detect: {detect_time:.2f}ms, classify: {classify_time:.2f}ms)")

            # Cache result
            result = (classified_player, classified_board)
            self._add_to_cache(frame_hash, result)

            return result

        except Exception as e:
            logger.error(f"Detection/classification error: {e}")
            return [], []
    
    def _classify_detections(self, detections: List[DetectedCard],
                            frame: np.ndarray) -> List[DetectedCard]:
        """Classify a list of detections using batch inference (5-7x faster)"""
        if not detections:
            return []

        # Extract all crops first
        crops = []
        for detection in detections:
            x1, y1, x2, y2 = detection.bbox
            crop = frame[y1:y2, x1:x2]
            crops.append(crop)

        # Batch classification - single forward pass for all cards!
        results = self.classifier.classify_batch(crops)

        # Apply results to detections
        classified = []
        for detection, (card_label, confidence) in zip(detections, results):
            if confidence > 0.2 and card_label != "unknown":
                detection.classification = card_label
                classified.append(detection)

        return classified
