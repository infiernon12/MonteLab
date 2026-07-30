"""
Monte Carlo Backend Implementation (C++ with Python Fallback)
"""
from typing import List, Dict
import logging
import random
import time
from core.poker import MonteCarloBackend
from core.domain import Card
from core.poker.hand_evaluator import HandEvaluator

logger = logging.getLogger(__name__)


class PythonMonteCarloBackend(MonteCarloBackend):
    """
    Pure Python Monte Carlo simulation engine.
    Used as automatic fallback when C++ binary is not compiled.
    """
    
    def __init__(self):
        self.hand_evaluator = HandEvaluator()
        self.all_ranks = "23456789TJQKA"
        self.all_suits = "shdc"
        logger.info("✅ Python Monte Carlo backend initialized")

    def calculate_equity(
        self,
        hole_cards: List[Card],
        board_cards: List[Card],
        num_opponents: int = 1,
        iterations: int = 10000
    ) -> Dict[str, float]:
        """Perform Monte Carlo equity simulation in Python."""
        if len(hole_cards) != 2:
            return {"error": "Need exactly 2 hole cards"}
        
        num_opponents = max(1, min(8, num_opponents))
        used_cards = set(hole_cards + board_cards)
        
        # Build remaining deck
        deck = [
            Card(r, s) for r in self.all_ranks for s in self.all_suits
            if Card(r, s) not in used_cards
        ]
        
        needed_board = 5 - len(board_cards)
        needed_opponents = 2 * num_opponents
        needed_total = needed_board + needed_opponents
        
        if len(deck) < needed_total:
            return {"error": "Not enough cards in deck"}
        
        # Reduce iterations slightly for Python speed (5,000 runs ~ 0.1s)
        n_sims = min(iterations, 5000)
        
        wins = 0
        ties = 0
        losses = 0
        
        start_time = time.time()
        evaluator = self.hand_evaluator
        
        for _ in range(n_sims):
            sampled = random.sample(deck, needed_total)
            full_board = board_cards + sampled[:needed_board]
            
            # Evaluate hero strength
            hero_hand = hole_cards + full_board
            hero_str = evaluator._evaluate_hand_strength(hero_hand)
            
            # Evaluate best opponent strength
            best_opp_str = -1
            for opp_idx in range(num_opponents):
                opp_offset = needed_board + (opp_idx * 2)
                opp_hole = sampled[opp_offset:opp_offset + 2]
                opp_str = evaluator._evaluate_hand_strength(opp_hole + full_board)
                if opp_str > best_opp_str:
                    best_opp_str = opp_str
            
            if hero_str > best_opp_str:
                wins += 1
            elif hero_str == best_opp_str:
                ties += 1
            else:
                losses += 1

        win_rate = round((wins / n_sims) * 100, 2)
        tie_rate = round((ties / n_sims) * 100, 2)
        lose_rate = round(max(0.0, 100.0 - win_rate - tie_rate), 2)
        elapsed = time.time() - start_time
        
        logger.info(f"⚡ Python Monte Carlo ({n_sims} sims in {elapsed:.3f}s): {win_rate}% win, {tie_rate}% tie, {lose_rate}% lose")
        
        return {
            "win_rate": win_rate,
            "tie_rate": tie_rate,
            "lose_rate": lose_rate,
            "simulations_completed": n_sims,
            "calculation_mode": "python"
        }


class CppMonteCarloBackend(MonteCarloBackend):
    """C++ Monte Carlo backend implementation with automatic Python fallback"""
    
    def __init__(self):
        try:
            from monte_carlo_engine_v3 import MonteCarloEngineDaemon
            self.engine = MonteCarloEngineDaemon()
            logger.info("✅ C++ Monte Carlo daemon backend initialized")
        except Exception as e:
            logger.warning(f"C++ Monte Carlo daemon unavailable ({e}). Using Python engine fallback.")
            self.engine = None
            self.fallback_backend = PythonMonteCarloBackend()
    
    def calculate_equity(
        self,
        hole_cards: List[Card],
        board_cards: List[Card],
        num_opponents: int,
        iterations: int
    ) -> Dict[str, float]:
        """Calculate equity using C++ engine or Python fallback"""
        if self.engine is not None:
            res = self.engine.calculate_equity(hole_cards, board_cards, num_opponents, iterations)
            if res and "error" not in res:
                return res
        
        # Fallback to Python engine if C++ is not present or failed
        if not hasattr(self, 'fallback_backend'):
            self.fallback_backend = PythonMonteCarloBackend()
        return self.fallback_backend.calculate_equity(hole_cards, board_cards, num_opponents, iterations)
