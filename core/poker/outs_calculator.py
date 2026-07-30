"""Outs calculator - Separated from hand evaluation"""
from typing import List, Dict, Set
from collections import Counter
from core.domain import Card


class OutsCalculator:
    """Calculate outs for different draw types"""
    
    VALID_RANKS = {'2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A'}
    VALID_SUITS = {'c', 'd', 'h', 's'}
    
    def calculate_outs(self, hole_cards: List[Card], board_cards: List[Card]) -> Dict[str, int]:
        """Calculate outs without double counting"""
        if len(board_cards) >= 5:
            return {'flush': 0, 'straight': 0, 'set_trips': 0, 'overcard': 0}
        
        remaining_cards = self._get_remaining_cards(hole_cards, board_cards)
        
        # Calculate all outs by type (as sets to avoid duplicates)
        flush_outs = self._count_flush_outs(hole_cards, board_cards, remaining_cards)
        straight_outs = self._count_straight_outs(hole_cards, board_cards, remaining_cards, flush_outs)
        set_outs = self._count_set_outs(hole_cards, board_cards, remaining_cards, flush_outs | straight_outs)
        overcard_outs = self._count_overcard_outs(hole_cards, board_cards, remaining_cards, 
                                                   flush_outs | straight_outs | set_outs)
        
        return {
            'flush': len(flush_outs),
            'straight': len(straight_outs),
            'set_trips': len(set_outs),
            'overcard': len(overcard_outs)
        }
    
    def _get_remaining_cards(self, hole_cards: List[Card], board_cards: List[Card]) -> List[Card]:
        """Get all remaining cards in deck"""
        used_cards = set((c.rank, c.suit) for c in hole_cards + board_cards)
        remaining = []
        
        for rank in self.VALID_RANKS:
            for suit in self.VALID_SUITS:
                if (rank, suit) not in used_cards:
                    remaining.append(Card(rank, suit))
        
        return remaining
    
    def _count_flush_outs(self, hole_cards: List[Card], board_cards: List[Card],
                         remaining_cards: List[Card]) -> Set:
        """Count flush draw outs"""
        all_cards = hole_cards + board_cards
        suit_counts = Counter(card.suit for card in all_cards)
        flush_outs = set()
        
        for suit, count in suit_counts.items():
            if count == 4:
                player_suit_count = sum(1 for card in hole_cards if card.suit == suit)
                if player_suit_count >= 1:
                    for card in remaining_cards:
                        if card.suit == suit:
                            flush_outs.add((card.rank, card.suit))
        
        return flush_outs
    
    def _count_straight_outs(self, hole_cards: List[Card], board_cards: List[Card],
                            remaining_cards: List[Card], excluded_outs: Set) -> Set:
        """Count straight draw outs"""
        all_cards = hole_cards + board_cards
        all_ranks = sorted(set(card.rank_value() for card in all_cards))
        hole_ranks = set(card.rank_value() for card in hole_cards)
        straight_outs = set()
        
        # Regular straights
        for start in range(2, 11):
            straight_ranks = set(range(start, start + 5))
            present_ranks = set(all_ranks) & straight_ranks
            
            if len(present_ranks) == 4 and hole_ranks & present_ranks:
                missing_rank = (straight_ranks - set(all_ranks)).pop()
                for card in remaining_cards:
                    if (card.rank_value() == missing_rank and 
                        (card.rank, card.suit) not in excluded_outs):
                        straight_outs.add((card.rank, card.suit))
        
        # Wheel (A-2-3-4-5)
        wheel_ranks = {14, 2, 3, 4, 5}
        present_wheel = set(all_ranks) & wheel_ranks
        
        if len(present_wheel) == 4 and hole_ranks & present_wheel:
            missing_rank = (wheel_ranks - set(all_ranks)).pop()
            for card in remaining_cards:
                if (card.rank_value() == missing_rank and 
                    (card.rank, card.suit) not in excluded_outs):
                    straight_outs.add((card.rank, card.suit))
        
        return straight_outs
    
    def _count_set_outs(self, hole_cards: List[Card], board_cards: List[Card],
                       remaining_cards: List[Card], excluded_outs: Set) -> Set:
        """Count set/trips improvement outs"""
        all_cards = hole_cards + board_cards
        rank_counts = Counter(card.rank for card in all_cards)
        hole_ranks = [card.rank for card in hole_cards]
        set_outs = set()
        
        # Trips → Quads and Full House
        for rank, count in rank_counts.items():
            if count == 3 and rank in hole_ranks:
                # Quads (1 out)
                for card in remaining_cards:
                    if (card.rank == rank and 
                        (card.rank, card.suit) not in excluded_outs):
                        set_outs.add((card.rank, card.suit))
                
                # Full House (pair up other ranks)
                for other_rank, other_count in rank_counts.items():
                    if other_rank != rank and other_count >= 1:
                        remaining_of_rank = sum(1 for card in remaining_cards 
                                              if card.rank == other_rank)
                        
                        count_added = 0
                        for card in remaining_cards:
                            if (card.rank == other_rank and 
                                count_added < remaining_of_rank and
                                (card.rank, card.suit) not in excluded_outs):
                                set_outs.add((card.rank, card.suit))
                                count_added += 1
        
        return set_outs
    
    def _count_overcard_outs(self, hole_cards: List[Card], board_cards: List[Card],
                            remaining_cards: List[Card], excluded_outs: Set) -> Set:
        """Count overcard outs"""
        if not board_cards:
            return set()
        
        board_high = max(card.rank_value() for card in board_cards)
        overcard_outs = set()
        
        for hole_card in hole_cards:
            if hole_card.rank_value() > board_high:
                for card in remaining_cards:
                    if (card.rank == hole_card.rank and 
                        (card.rank, card.suit) not in excluded_outs):
                        overcard_outs.add((card.rank, card.suit))
        
        return overcard_outs
