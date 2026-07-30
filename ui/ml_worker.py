"""ML Worker Thread for async card detection and classification"""
import logging
import numpy as np
from typing import List, Tuple
from PySide6.QtCore import QThread, Signal

from core.domain import DetectedCard
from services.ml_service import MLService

logger = logging.getLogger(__name__)


class MLWorker(QThread):
    """Background worker for ML inference with cancellation support"""

    # Signals
    detection_complete = Signal(list, list)  # player_cards, board_cards
    detection_failed = Signal(str)  # error_message
    detection_cancelled = Signal()  # cancelled signal

    def __init__(self, ml_service: MLService):
        super().__init__()
        self.ml_service = ml_service
        self.frame: np.ndarray = None
        self.confidence_threshold = 0.4
        self._should_stop = False
        self._is_cancelled = False

    def set_frame(self, frame: np.ndarray, confidence_threshold: float = 0.4):
        """Set the frame to process and cancel any running inference"""
        # Cancel current inference if running
        if self.isRunning():
            logger.debug("Cancelling previous inference...")
            self._is_cancelled = True
            # Wait briefly for current inference to check cancellation flag
            self.wait(100)

        # Reset cancellation flag and set new frame
        self._is_cancelled = False
        self.frame = frame
        self.confidence_threshold = confidence_threshold

    def cancel(self):
        """Cancel current inference"""
        self._is_cancelled = True
        logger.debug("MLWorker inference cancelled")

    def run(self):
        """Execute ML detection in background thread with cancellation support"""
        try:
            # Check cancellation before starting
            if self._is_cancelled:
                logger.debug("Inference cancelled before start")
                self.detection_cancelled.emit()
                return

            if self.frame is None:
                self.detection_failed.emit("No frame to process")
                return

            if not self.ml_service.is_available:
                self.detection_failed.emit("ML service not available")
                return

            # Perform detection and classification (GPU accelerated + batched + cached)
            logger.info("Starting ML detection in background thread...")
            player_cards, board_cards = self.ml_service.detect_and_classify(
                self.frame,
                confidence_threshold=self.confidence_threshold
            )

            # Check cancellation after inference
            if self._is_cancelled:
                logger.debug("Inference cancelled after completion")
                self.detection_cancelled.emit()
                return

            logger.info(f"Detection complete: {len(player_cards)} player, {len(board_cards)} board cards")

            # Emit results back to main thread
            self.detection_complete.emit(player_cards, board_cards)

        except Exception as e:
            logger.error(f"ML worker error: {e}", exc_info=True)
            self.detection_failed.emit(str(e))

    def stop(self):
        """Stop the worker thread gracefully"""
        self._should_stop = True
        self.quit()
        self.wait()
