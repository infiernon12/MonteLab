"""Game state enums and data structures"""
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
from .card import Card


class Position(Enum):
    """Player position at the table"""
    UTG = "UTG"
    MP = "MP"
    CO = "CO"
    BTN = "BTN"
    SB = "SB"
    BB = "BB"


class Action(Enum):
    """Available player actions"""
    FOLD = "FOLD"
    CALL = "CALL"
    RAISE = "RAISE"
    ALL_IN = "ALL_IN"


class GameStage(Enum):
    """Current game stage"""
    PREFLOP = "Preflop"
    FLOP = "Flop"
    TURN = "Turn"
    RIVER = "River"


class TableSize(Enum):
    """Table size configurations"""
    HEADS_UP = "heads_up"
    THREE_MAX = "3max"
    FOUR_MAX = "4max"
    FIVE_MAX = "5max"
    SIX_MAX = "6max"
    SEVEN_MAX = "7max"
    EIGHT_MAX = "8max"
    NINE_MAX = "9max"


class GameType(Enum):
    """Game type variants"""
    CASH = "Cash"
    TOURNAMENT = "TTM"


@dataclass
class GameState:
    """Current game state snapshot with detailed game data"""
    # Core game configuration
    table_size: TableSize
    game_type: GameType
    stage: GameStage
    player_cards: List[Card]
    board_cards: List[Card]

    # Detailed game data (optional, may be None if not available)
    player_stacks: Optional[List[int]] = None      # Stack sizes for all players
    pot_size: Optional[int] = None                  # Current pot size
    player_bets: Optional[List[int]] = None         # Current bets for all players
    dealer_position: Optional[int] = None           # Dealer button position (0-based)
    big_blind: Optional[int] = None                 # BB amount for calculations

    def get_opponents_count(self) -> int:
        """Get number of opponents based on table size"""
        opponents_map = {
            TableSize.HEADS_UP: 1,
            TableSize.THREE_MAX: 2,
            TableSize.FOUR_MAX: 3,
            TableSize.FIVE_MAX: 4,
            TableSize.SIX_MAX: 5,
            TableSize.SEVEN_MAX: 6,
            TableSize.EIGHT_MAX: 7,
            TableSize.NINE_MAX: 8
        }
        return opponents_map.get(self.table_size, 1)

    def get_players_count(self) -> int:
        """Get total players at table"""
        return self.get_opponents_count() + 1

    # Detailed data helper methods

    def calculate_pot_odds(self, bet_to_call: int) -> Optional[float]:
        """Calculate pot odds percentage"""
        if self.pot_size is None or bet_to_call == 0:
            return None
        total_pot = self.pot_size + bet_to_call
        return (bet_to_call / total_pot) * 100 if total_pot > 0 else None

    def calculate_spr(self, player_index: int = 0) -> Optional[float]:
        """
        Calculate Stack-to-Pot Ratio for given player
        SPR = Effective Stack / Pot
        """
        if self.player_stacks is None or self.pot_size is None:
            return None
        if player_index >= len(self.player_stacks):
            return None
        if self.pot_size == 0:
            return None

        effective_stack = self.player_stacks[player_index]
        return effective_stack / self.pot_size

    def get_stack_in_bb(self, player_index: int = 0) -> Optional[float]:
        """Get stack size in big blinds"""
        if self.player_stacks is None or self.big_blind is None:
            return None
        if player_index >= len(self.player_stacks):
            return None
        if self.big_blind == 0:
            return None

        return self.player_stacks[player_index] / self.big_blind

    def get_position_name(self, player_index: int) -> str:
        """
        Get position name relative to dealer button
        Assumes player_index 0 is hero
        """
        if self.dealer_position is None:
            return "Unknown"

        players = self.get_players_count()
        relative_pos = (player_index - self.dealer_position) % players

        if players == 2:  # Heads-up
            return "BTN" if relative_pos == 0 else "BB"
        elif players <= 6:  # 6-max
            pos_map = {
                0: "BTN", 1: "SB", 2: "BB",
                3: "UTG", 4: "MP", 5: "CO"
            }
            return pos_map.get(relative_pos, "Unknown")
        else:  # Full ring (7-9)
            pos_map = {
                0: "BTN", 1: "SB", 2: "BB",
                3: "UTG", 4: "UTG+1", 5: "MP",
                6: "MP+1", 7: "CO", 8: "HJ"
            }
            return pos_map.get(relative_pos, "Unknown")

    def has_detailed_data(self) -> bool:
        """Check if any detailed game data is available"""
        return any([
            self.player_stacks is not None,
            self.pot_size is not None,
            self.player_bets is not None,
            self.dealer_position is not None
        ])

    def get_data_completeness(self) -> str:
        """
        Assess completeness of detailed game data
        Returns: "full", "partial", "none"
        """
        data_fields = [
            self.player_stacks,
            self.pot_size,
            self.player_bets,
            self.dealer_position
        ]
        non_none_count = sum(1 for field in data_fields if field is not None)

        if non_none_count == 4:
            return "full"
        elif non_none_count > 0:
            return "partial"
        else:
            return "none"
