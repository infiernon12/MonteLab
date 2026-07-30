"""Card domain model - Immutable playing card representation"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Card:
    """Immutable playing card with validation"""
    rank: str  # 2-9, T, J, Q, K, A
    suit: str  # c, d, h, s
    
    VALID_RANKS = {'2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A'}
    VALID_SUITS = {'c', 'd', 'h', 's'}
    
    RANK_VALUES = {
        '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
        'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
    }
    
    def __post_init__(self):
        if self.rank not in self.VALID_RANKS:
            raise ValueError(f"Invalid rank: {self.rank}")
        if self.suit not in self.VALID_SUITS:
            raise ValueError(f"Invalid suit: {self.suit}")
    
    def rank_value(self) -> int:
        """Get numeric value of rank (2=2, ..., A=14)"""
        return self.RANK_VALUES[self.rank]
    
    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"
    
    @classmethod
    def parse(cls, card_str: str) -> Optional['Card']:
        """Parse card from string (e.g. 'As', 'Kh')"""
        if not card_str or len(card_str.strip()) < 2:
            return None
        
        card_str = card_str.strip().upper()
        if len(card_str) != 2:
            return None
        
        rank, suit = card_str[0], card_str[1].lower()
        
        if rank not in cls.VALID_RANKS or suit not in cls.VALID_SUITS:
            return None
        
        return cls(rank, suit)
