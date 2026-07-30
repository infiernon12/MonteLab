"""Board texture analysis"""
from typing import List, Dict
from collections import Counter
from core.domain import Card


class BoardAnalyzer:
    """Analyze board texture and properties"""
    
    def analyze_texture(self, board_cards: List[Card]) -> Dict[str, any]:
        """Comprehensive board texture analysis"""
        if len(board_cards) < 3:
            return {"error": "Need at least 3 board cards"}
        
        suit_counter = Counter(card.suit for card in board_cards)
        rank_counter = Counter(card.rank for card in board_cards)
        rank_values = sorted([card.rank_value() for card in board_cards])
        
        max_suit_count = max(suit_counter.values())
        unique_suits = len(suit_counter)
        max_rank_count = max(rank_counter.values())
        
        return {
            "monotone": max_suit_count >= 3,
            "two_tone": sum(1 for count in suit_counter.values() if count >= 2) >= 2,
            "rainbow": unique_suits >= 3,
            "paired": max_rank_count >= 2,
            "coordinated": self._is_coordinated(rank_values),
            "straight_draws": self._count_straight_draws(rank_values),
            "flush_draw": max_suit_count == 2,
            "dry": max_suit_count == 1 and not self._is_coordinated(rank_values)
        }
    
    def _is_coordinated(self, sorted_ranks: List[int]) -> bool:
        """Check if board is coordinated (connected cards)"""
        if len(sorted_ranks) < 2:
            return False
        
        for i in range(len(sorted_ranks) - 1):
            gap = sorted_ranks[i + 1] - sorted_ranks[i]
            if gap <= 2:
                return True
        return False
    
    def _count_straight_draws(self, sorted_ranks: List[int]) -> int:
        """Count possible straight draws"""
        unique_ranks = sorted(set(sorted_ranks))
        draws = 0
        
        # Regular straights
        for start in range(2, 11):
            straight_ranks = list(range(start, start + 5))
            board_in_straight = [r for r in unique_ranks if r in straight_ranks]
            if len(board_in_straight) >= 3:
                draws += 1
        
        # Wheel
        wheel_ranks = [14, 2, 3, 4, 5]
        board_in_wheel = [r for r in unique_ranks if r in wheel_ranks]
        if len(board_in_wheel) >= 3:
            draws += 1
        
        return draws
