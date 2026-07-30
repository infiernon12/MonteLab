"""Monte Carlo backend implementation"""
from typing import List, Dict
import logging
from core.poker import MonteCarloBackend
from core.domain import Card
from monte_carlo_engine_v3 import MonteCarloEngineDaemon

logger = logging.getLogger(__name__)


class CppMonteCarloBackend(MonteCarloBackend):
    """C++ Monte Carlo backend implementation"""
    
    def __init__(self):
        try:
            self.engine = MonteCarloEngineDaemon()
            logger.info("C++ Monte Carlo backend initialized")
        except Exception as e:
            logger.error(f"Failed to initialize C++ backend: {e}")
            raise
    
    def calculate_equity(self, hole_cards: List[Card], board_cards: List[Card],
                        num_opponents: int, iterations: int) -> Dict[str, float]:
        """Calculate equity using C++ engine"""
        return self.engine.calculate_equity(hole_cards, board_cards, num_opponents, iterations)
