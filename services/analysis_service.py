"""Analysis Service - Orchestrates poker analysis with improved recommendations"""
from typing import Dict, List
import logging
from core.domain import Card, GameState, GameStage
from core.poker import HandEvaluator, EquityCalculator, BoardAnalyzer, OutsCalculator

logger = logging.getLogger(__name__)


class AnalysisService:
    """High-level poker analysis orchestration with improved ABC recommendations"""
    
    def __init__(self, equity_calculator: EquityCalculator):
        self.hand_evaluator = HandEvaluator()
        self.board_analyzer = BoardAnalyzer()
        self.outs_calculator = OutsCalculator()
        self.equity_calculator = equity_calculator
        
        # Import recommendation engine
        try:
            from services.improved_abc_recommendations import ImprovedRecommendationEngine
            self.recommendation_engine = ImprovedRecommendationEngine()
            self.use_improved_recommendations = True
            logger.info("Loaded improved recommendation engine")
        except ImportError:
            logger.warning("Improved recommendation engine not found, using basic recommendations")
            self.recommendation_engine = None
            self.use_improved_recommendations = False
    
    def analyze_hand(self, game_state: GameState) -> Dict[str, any]:
        """Comprehensive hand analysis"""
        
        # Validation
        if len(game_state.player_cards) != 2:
            return {"error": "Need exactly 2 player cards"}
        
        # Determine analysis type based on stage
        if game_state.stage == GameStage.PREFLOP:
            return self._analyze_preflop(game_state)
        else:
            return self._analyze_postflop(game_state)
    
    def _analyze_preflop(self, game_state: GameState) -> Dict[str, any]:
        """Preflop analysis (would integrate with GTO charts)"""
        hand_key = self.hand_evaluator.get_hand_key(game_state.player_cards)
        
        return {
            "stage": "preflop",
            "hand_key": hand_key,
            "cards_display": " ".join(str(c) for c in game_state.player_cards),
            # GTO recommendations would go here
        }
    
    def _analyze_postflop(self, game_state: GameState) -> Dict[str, any]:
        """Postflop analysis with hand strength, outs, equity"""
        
        # Hand strength evaluation
        all_cards = game_state.player_cards + game_state.board_cards
        best_hand, strength = self.hand_evaluator.get_best_5_card_hand(all_cards)
        current_hand = self.hand_evaluator.get_hand_description(best_hand)
        
        # Outs calculation
        outs_data = {}
        total_outs = 0
        if len(game_state.board_cards) < 5:
            outs_data = self.outs_calculator.calculate_outs(
                game_state.player_cards,
                game_state.board_cards
            )
            total_outs = sum(outs_data.values())
        
        # Board texture analysis
        texture_analysis = {}
        if len(game_state.board_cards) >= 3:
            texture_analysis = self.board_analyzer.analyze_texture(game_state.board_cards)
        
        # Equity simulation
        equity_data = {}
        if len(game_state.board_cards) >= 3:
            try:
                equity_data = self.equity_calculator.calculate_equity(
                    game_state.player_cards,
                    game_state.board_cards,
                    num_opponents=game_state.get_opponents_count(),
                    iterations=50000
                )
            except Exception as e:
                logger.error(f"Equity calculation failed: {e}")
                equity_data = {"error": str(e)}
        
        # Strategic recommendation - NEW IMPROVED VERSION
        if self.use_improved_recommendations and self.recommendation_engine:
            strategy = self._generate_improved_strategy(
                current_hand=current_hand,
                equity_data=equity_data,
                outs_data=outs_data,
                total_outs=total_outs,
                texture_analysis=texture_analysis,
                game_state=game_state
            )
        else:
            # Fallback to basic strategy
            strategy = self._generate_basic_strategy(
                current_hand, total_outs, equity_data, texture_analysis, len(game_state.board_cards)
            )
        
        return {
            "stage": game_state.stage.value,
            "current_hand": current_hand,
            "hand_strength_numeric": strength,
            "best_5_cards": [str(c) for c in best_hand],
            "outs_analysis": outs_data,
            "total_outs": total_outs,
            "board_texture": texture_analysis,
            "equity": equity_data,
            "strategy_recommendation": strategy,
            # Additional data for improved recommendations
            "num_opponents": game_state.get_opponents_count(),
            "board_cards_list": game_state.board_cards,

            # Detailed game data
            "pot_size": game_state.pot_size,
            "player_stacks": game_state.player_stacks,
            "spr": game_state.calculate_spr(0) if game_state.player_stacks else None,
            "stack_in_bb": game_state.get_stack_in_bb(0),
            "dealer_position": game_state.dealer_position,
            "player_position": game_state.get_position_name(0) if game_state.dealer_position is not None else None,
            "has_detailed_data": game_state.has_detailed_data(),
            "data_completeness": game_state.get_data_completeness()
        }
    
    def _generate_improved_strategy(
        self,
        current_hand: str,
        equity_data: Dict,
        outs_data: Dict,
        total_outs: int,
        texture_analysis: Dict,
        game_state: GameState
    ) -> str:
        """Generate improved strategic recommendation"""

        try:
            win_rate = equity_data.get('win_rate', 0)

            recommendation = self.recommendation_engine.generate_recommendation(
                current_hand=current_hand,
                win_rate=win_rate,
                total_outs=total_outs,
                outs_breakdown=outs_data,
                texture_analysis=texture_analysis,
                num_opponents=game_state.get_opponents_count(),
                stage=game_state.stage,
                board_cards=game_state.board_cards,

                # Detailed data for GTO recommendations
                pot_size=game_state.pot_size,
                player_stack=game_state.player_stacks[0] if game_state.player_stacks else None,
                spr=game_state.calculate_spr(0),
                stack_in_bb=game_state.get_stack_in_bb(0),
                position=game_state.get_position_name(0) if game_state.dealer_position is not None else None
            )

            return recommendation
            
        except Exception as e:
            logger.error(f"Improved recommendation generation failed: {e}")
            # Fallback to basic
            return self._generate_basic_strategy(
                current_hand, total_outs, equity_data, 
                texture_analysis, len(game_state.board_cards)
            )
    
    def _generate_basic_strategy(
        self, 
        current_hand: str, 
        total_outs: int, 
        equity_data: Dict, 
        texture_analysis: Dict, 
        board_cards_count: int
    ) -> str:
        """Basic ABC strategy recommendation (fallback)"""
        
        strong_hands = ['four of a kind', 'full house', 'flush', 'straight', 'three of a kind']
        medium_hands = ['two pair', 'one pair']
        
        win_rate = equity_data.get('win_rate', 0)
        
        # Strong made hands
        if any(hand in current_hand.lower() for hand in strong_hands):
            if win_rate > 70:
                return "💪 ОЧЕНЬ СИЛЬНАЯ РУКА - Ставьте крупно на вэлью!"
            else:
                return "✅ СИЛЬНАЯ РУКА - Ставьте на вэлью"
        
        # Medium hands
        if any(hand in current_hand.lower() for hand in medium_hands):
            if win_rate > 55:
                return "👍 СРЕДНЯЯ РУКА - Ставьте средне или коллируйте"
            else:
                return "⚠️ ОСТОРОЖНО - Чек-колл или небольшая ставка"
        
        # Drawing hands
        if total_outs >= 12:
            return "🚀 МОНСТР-ДРО - Играйте очень агрессивно!"
        elif total_outs >= 8:
            return "⚡ ХОРОШЕЕ ДРО - Полу-блеф или колл"
        elif total_outs >= 4:
            return "🤞 СЛАБОЕ ДРО - Коллируйте дешево"
        
        # Weak hands
        if board_cards_count == 5:
            return "❌ СЛАБАЯ РУКА - Скорее всего ФОЛД к ставкам"
        else:
            return "😕 СЛАБАЯ ПОЗИЦИЯ - Чек или фолд к агрессии"