"""Equity calculator with Monte Carlo backend abstraction"""
from typing import List, Dict, Optional
from abc import ABC, abstractmethod
import logging
from core.domain import Card

logger = logging.getLogger(__name__)


class MonteCarloBackend(ABC):
    """Abstract interface for Monte Carlo simulation backends"""
    
    @abstractmethod
    def calculate_equity(self, hole_cards: List[Card], board_cards: List[Card],
                        num_opponents: int, iterations: int) -> Dict[str, float]:
        """Calculate equity using Monte Carlo simulation"""
        pass


class EquityCalculator:
    """High-level equity calculator with pluggable backends"""
    
    def __init__(self, backend: Optional[MonteCarloBackend] = None):
        self.backend = backend
        if backend is None:
            logger.warning("No Monte Carlo backend provided - equity calculations disabled")
    
    def calculate_equity(self, hole_cards: List[Card], board_cards: List[Card],
                        num_opponents: int = 1, iterations: int = 10000) -> Dict[str, float]:
        """Calculate equity with validation"""
        
        # Validation
        if len(hole_cards) != 2:
            return {"error": "Need exactly 2 hole cards"}
        
        if len(board_cards) > 5:
            return {"error": "Board cannot have more than 5 cards"}
        
        if self.backend is None:
            return {"error": "Monte Carlo backend not available"}
        
        # Delegate to backend
        return self.backend.calculate_equity(hole_cards, board_cards, num_opponents, iterations)
