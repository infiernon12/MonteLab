"""Hand evaluation logic - Separated from simulation"""
from typing import List, Tuple, Dict
from collections import Counter
from itertools import combinations
from core.domain import Card


class HandEvaluator:
    """Pure hand strength evaluation without simulation dependencies"""
    
    # Hand type base values (large gaps for kickers)
    HAND_TYPE_BASE = {
        'high_card': 0,
        'one_pair': 10000000,
        'two_pair': 20000000,
        'three_kind': 30000000,
        'straight': 40000000,
        'flush': 50000000,
        'full_house': 60000000,
        'four_kind': 70000000,
        'straight_flush': 80000000
    }
    
    WHEEL_RANKS = {2, 3, 4, 5, 14}
    
    def __init__(self):
        self._cache = {}
    
    def get_best_5_card_hand(self, cards: List[Card]) -> Tuple[List[Card], int]:
        """Find best 5-card hand and numeric strength"""
        if len(cards) < 5:
            return cards, self._evaluate_hand_strength(cards)
        
        if len(cards) == 5:
            return cards, self._evaluate_hand_strength(cards)
        
        best_hand = None
        best_strength = -1
        
        for combo in combinations(cards, 5):
            combo_list = list(combo)
            strength = self._evaluate_hand_strength(combo_list)
            if strength > best_strength:
                best_strength = strength
                best_hand = combo_list
        
        return best_hand, best_strength
    
    def _evaluate_hand_strength(self, cards: List[Card]) -> int:
        """Precise numeric hand strength evaluation"""
        if len(cards) < 2:
            return 0
        
        cards_key = tuple(sorted((c.rank, c.suit) for c in cards))
        if cards_key in self._cache:
            return self._cache[cards_key]
        
        rank_values = [card.rank_value() for card in cards]
        rank_counts = Counter(rank_values)
        suit_counts = Counter(card.suit for card in cards)
        
        ranks_by_count = sorted(rank_counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
        sorted_counts = sorted(rank_counts.values(), reverse=True)
        
        is_flush = max(suit_counts.values()) >= 5
        is_straight, straight_high = self._check_straight(rank_values)
        
        strength = self._calculate_strength(
            sorted_counts, ranks_by_count, is_flush, is_straight, straight_high, suit_counts, cards
        )
        
        self._cache[cards_key] = strength
        return strength
    
    def _calculate_strength(self, sorted_counts, ranks_by_count, is_flush, 
                          is_straight, straight_high, suit_counts, cards) -> int:
        """Calculate numeric strength based on hand type"""
        
        if is_straight and is_flush:
            return self.HAND_TYPE_BASE['straight_flush'] + straight_high
        
        if sorted_counts[0] == 4:
            quad_rank = ranks_by_count[0][0]
            kicker = ranks_by_count[1][0] if len(ranks_by_count) > 1 else 0
            return self.HAND_TYPE_BASE['four_kind'] + quad_rank * 100 + kicker
        
        if sorted_counts[0] == 3 and len(sorted_counts) > 1 and sorted_counts[1] >= 2:
            trips_rank = ranks_by_count[0][0]
            pair_rank = ranks_by_count[1][0]
            return self.HAND_TYPE_BASE['full_house'] + trips_rank * 100 + pair_rank
        
        if is_flush:
            flush_suit = max(suit_counts.keys(), key=suit_counts.get)
            flush_cards = [card for card in cards if card.suit == flush_suit]
            flush_values = sorted([card.rank_value() for card in flush_cards], reverse=True)[:5]
            kicker_score = sum(flush_values[i] * (15 ** (4-i)) for i in range(len(flush_values)))
            return self.HAND_TYPE_BASE['flush'] + kicker_score
        
        if is_straight:
            return self.HAND_TYPE_BASE['straight'] + straight_high
        
        if sorted_counts[0] == 3:
            trips_rank = ranks_by_count[0][0]
            kickers = sorted([r for r, c in ranks_by_count[1:]], reverse=True)[:2]
            kicker_score = sum(kickers[i] * (15 ** (1-i)) for i in range(len(kickers)))
            return self.HAND_TYPE_BASE['three_kind'] + trips_rank * 1000 + kicker_score
        
        if len(sorted_counts) > 1 and sorted_counts[0] == 2 and sorted_counts[1] == 2:
            pairs = sorted([r for r, c in ranks_by_count if c == 2], reverse=True)[:2]
            kicker = max([r for r, c in ranks_by_count if c == 1], default=0)
            return self.HAND_TYPE_BASE['two_pair'] + pairs[0] * 1000 + pairs[1] * 50 + kicker
        
        if sorted_counts[0] == 2:
            pair_rank = ranks_by_count[0][0]
            kickers = sorted([r for r, c in ranks_by_count[1:]], reverse=True)[:3]
            kicker_score = sum(kickers[i] * (15 ** (2-i)) for i in range(len(kickers)))
            return self.HAND_TYPE_BASE['one_pair'] + pair_rank * 10000 + kicker_score
        
        # High card
        rank_values = [card.rank_value() for card in cards]
        high_cards = sorted(rank_values, reverse=True)[:5]
        kicker_score = sum(high_cards[i] * (15 ** (4-i)) for i in range(len(high_cards)))
        return self.HAND_TYPE_BASE['high_card'] + kicker_score
    
    def _check_straight(self, rank_values: List[int]) -> Tuple[bool, int]:
        """Check for straight and return high card"""
        unique_values = sorted(set(rank_values))
        
        # Wheel (A-2-3-4-5)
        if self.WHEEL_RANKS.issubset(set(unique_values)):
            return True, 5
        
        # Regular straights
        for i in range(len(unique_values) - 4):
            if unique_values[i + 4] - unique_values[i] == 4:
                return True, unique_values[i + 4]
        
        return False, 0
    
    def get_hand_description(self, cards: List[Card]) -> str:
        """Get textual description of hand type"""
        if len(cards) < 2:
            return "High card"
        
        rank_counts = Counter(card.rank for card in cards)
        suit_counts = Counter(card.suit for card in cards)
        
        sorted_counts = sorted(rank_counts.values(), reverse=True)
        max_rank_count = sorted_counts[0]
        is_flush = max(suit_counts.values()) >= 5
        is_straight, _ = self._check_straight([card.rank_value() for card in cards])
        
        if is_straight and is_flush:
            return "Straight flush"
        elif max_rank_count >= 4:
            return "Four of a kind"
        elif max_rank_count == 3 and len(sorted_counts) > 1 and sorted_counts[1] >= 2:
            return "Full house"
        elif is_flush:
            return "Flush"
        elif is_straight:
            return "Straight"
        elif max_rank_count == 3:
            return "Three of a kind"
        elif len(sorted_counts) > 1 and sorted_counts[0] == 2 and sorted_counts[1] == 2:
            return "Two pair"
        elif max_rank_count == 2:
            return "One pair"
        else:
            return "High card"
    
    def get_hand_key(self, hole_cards: List[Card]) -> str:
        """Get hand key for preflop analysis (AA, AKs, AKo, etc.)"""
        if len(hole_cards) != 2:
            return ""
        
        c1, c2 = hole_cards
        
        if c1.rank == c2.rank:
            return f"{c1.rank}{c1.rank}"
        
        if c1.rank_value() > c2.rank_value():
            high, low = c1, c2
        else:
            high, low = c2, c1
        
        suffix = "s" if high.suit == low.suit else "o"
        return f"{high.rank}{low.rank}{suffix}"
