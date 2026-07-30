"""
Enhanced ABC Strategy & Tactical Recommendation Engine
Considers: Board texture, opponent count, game stage, positional play,
GTO analysis with detailed game data: pot odds, SPR, stack depths in BB, table position.
"""

from typing import Dict, List, Optional
from core.domain import Card, GameState, GameStage


class ImprovedRecommendationEngine:
    """
    Enhanced ABC Recommendation Engine with:
    - Board texture compatibility & threats
    - Opponent count scaling (multiway vs heads-up)
    - Game stage adjustments (preflop/flop/turn/river)
    - Positional guidance
    - Opponent tendency advice
    - GTO metrics: pot odds, SPR, stack in BB, table position
    """

    MONSTER_HANDS = {'straight_flush', 'four_kind', 'full_house'}
    STRONG_HANDS = {'flush', 'straight'}
    MEDIUM_HANDS = {'three_kind', 'two_pair'}
    WEAK_MADE_HANDS = {'one_pair'}

    def __init__(self):
        """Initialization with game data storage"""
        self.pot_size = None
        self.player_stack = None
        self.spr = None
        self.stack_in_bb = None
        self.position = None

    def generate_recommendation(
        self,
        current_hand: str,
        win_rate: float,
        total_outs: int,
        outs_breakdown: Dict[str, int],
        texture_analysis: Dict,
        num_opponents: int,
        stage: GameStage,
        board_cards: List[Card],

        pot_size: Optional[int] = None,
        player_stack: Optional[int] = None,
        spr: Optional[float] = None,
        stack_in_bb: Optional[float] = None,
        position: Optional[str] = None
    ) -> str:
        """Main recommendation generation entrypoint"""
        self.pot_size = pot_size
        self.player_stack = player_stack
        self.spr = spr
        self.stack_in_bb = stack_in_bb
        self.position = position

        if stage == GameStage.PREFLOP:
            return self._recommend_preflop(win_rate, num_opponents)

        hand_type = self._normalize_hand_name(current_hand)
        hand_category = self._categorize_hand(hand_type)
        texture_match = self._check_texture_compatibility(hand_type, texture_analysis, board_cards)

        if hand_category == 'monster':
            return self._recommend_monster_with_gto(
                hand_type, win_rate, texture_analysis,
                num_opponents, stage, texture_match
            )
        elif hand_category == 'strong':
            return self._recommend_strong_with_gto(
                hand_type, win_rate, texture_analysis,
                num_opponents, stage, texture_match, outs_breakdown
            )
        elif hand_category == 'medium':
            return self._recommend_medium_with_gto(
                hand_type, win_rate, texture_analysis,
                num_opponents, stage, texture_match, total_outs
            )
        elif hand_category == 'weak_made':
            return self._recommend_weak_made_with_gto(
                hand_type, win_rate, texture_analysis,
                num_opponents, stage, total_outs, outs_breakdown
            )
        else:
            return self._recommend_draw_with_gto(
                total_outs, outs_breakdown, win_rate,
                texture_analysis, num_opponents, stage
            )
    
    def _normalize_hand_name(self, hand_name: str) -> str:
        """Normalize hand combination names"""
        hand_map = {
            'straight flush': 'straight_flush',
            'four of a kind': 'four_kind',
            'full house': 'full_house',
            'three of a kind': 'three_kind',
            'two pair': 'two_pair',
            'one pair': 'one_pair',
            'high card': 'high_card'
        }
        return hand_map.get(hand_name.lower(), hand_name.lower())
    
    def _categorize_hand(self, hand_type: str) -> str:
        """Categorize hand strength"""
        if hand_type in self.MONSTER_HANDS:
            return 'monster'
        elif hand_type in self.STRONG_HANDS:
            return 'strong'
        elif hand_type in self.MEDIUM_HANDS:
            return 'medium'
        elif hand_type in self.WEAK_MADE_HANDS:
            return 'weak_made'
        else:
            return 'draw'

    def _recommend_preflop(self, win_rate: float, num_opponents: int) -> str:
        """Generate preflop strategy recommendation"""
        base = "♠️ **PREFLOP STRATEGY & TACTICAL ADVICE**\n\n"
        
        pos_str = f" from {self.position}" if self.position else ""
        bb_str = f" ({self.stack_in_bb:.1f} BB)" if self.stack_in_bb else ""
        
        if win_rate >= 70:
            situation = f"Premium Hole Cards{pos_str}{bb_str}"
            action = "Open Raise (2.5x-3x BB) or 3-Bet / 4-Bet for Value"
            base += self._get_simplified_action(situation, action)
            base += f"\n\n• **Win Rate vs {num_opponents} Opponents**: {win_rate:.1f}%\n"
            base += "• **Preflop Advice**: Build the pot immediately with premium holdings.\n"
        elif win_rate >= 50:
            situation = f"Strong Preflop Holding{pos_str}{bb_str}"
            action = "Open Raise (2.5x BB) or Call a Single Raise in Position"
            base += self._get_simplified_action(situation, action)
            base += f"\n\n• **Win Rate vs {num_opponents} Opponents**: {win_rate:.1f}%\n"
            base += "• **Preflop Advice**: Raise if unopened; call in position against passive raises.\n"
        elif win_rate >= 35:
            situation = f"Marginal Preflop Holding{pos_str}{bb_str}"
            action = "Fold to Raises / Steal from Late Position Only"
            base += self._get_simplified_action(situation, action)
            base += f"\n\n• **Win Rate vs {num_opponents} Opponents**: {win_rate:.1f}%\n"
            base += "• **Preflop Advice**: Avoid multiway bloated pots out of position.\n"
        else:
            situation = f"Weak Preflop Hand{pos_str}{bb_str}"
            action = "FOLD to Any Aggression"
            base += self._get_simplified_action(situation, action)
            base += f"\n\n• **Win Rate vs {num_opponents} Opponents**: {win_rate:.1f}%\n"
            base += "• **Preflop Advice**: Fold early to preserve stack for high-EV spots.\n"

        return base
    
    def _check_texture_compatibility(
        self, 
        hand_type: str, 
        texture: Dict,
        board_cards: List[Card]
    ) -> Dict[str, bool]:
        """Check whether board texture synergizes with or threatens hand"""
        return {
            'flush_compatible': hand_type == 'flush' and texture.get('monotone', False),
            'straight_compatible': hand_type == 'straight' and texture.get('coordinated', False),
            'set_compatible': hand_type == 'three_kind' and not texture.get('paired', False),
            'fullhouse_compatible': hand_type == 'full_house' and texture.get('paired', False),
            
            'flush_danger': texture.get('monotone', False) and hand_type != 'flush',
            'straight_danger': texture.get('coordinated', False) and hand_type not in ['straight', 'flush', 'full_house'],
            'pair_danger': texture.get('paired', False) and hand_type not in ['full_house', 'four_kind']
        }

    # ===================== GTO CALCULATION HELPERS =====================

    def _calculate_pot_odds_percentage(self, bet_to_call: int) -> Optional[float]:
        """Calculate pot odds percentage required"""
        if self.pot_size is None or self.pot_size <= 0:
            return None
        total_pot = self.pot_size + bet_to_call
        return (bet_to_call / total_pot) * 100 if total_pot > 0 else None

    def _get_bet_sizing_advice(self, situation: str = "value") -> str:
        """Generate recommended bet sizing in chips and BB"""
        if self.pot_size is None or self.pot_size <= 0:
            return "Bet 60-75% of pot"

        sizing_map = {
            "value": (0.65, 0.85),
            "protection": (0.55, 0.70),
            "bluff": (0.50, 0.65),
            "semi-bluff": (0.60, 0.75)
        }

        min_pct, max_pct = sizing_map.get(situation, (0.60, 0.75))
        min_amount = int(self.pot_size * min_pct)
        max_amount = int(self.pot_size * max_pct)

        if self.stack_in_bb is not None and self.player_stack and self.player_stack > 0:
            estimated_bb = self.player_stack / self.stack_in_bb if self.stack_in_bb > 0 else None
            if estimated_bb and estimated_bb > 0:
                min_bb = round(min_amount / estimated_bb, 1)
                max_bb = round(max_amount / estimated_bb, 1)
                return f"{min_amount}-{max_amount} chips ({min_bb}-{max_bb} BB)"

        return f"{min_amount}-{max_amount} chips"

    def _check_stack_depth_warning(self) -> Optional[str]:
        """Generate stack depth warning"""
        if self.stack_in_bb is None:
            return None

        if self.stack_in_bb < 15:
            return "⚠️ SHORT STACK (<15 BB) — Push/Fold strategy recommended"
        elif self.stack_in_bb < 30:
            return "⚠️ Medium Stack (15-30 BB) — Exercise pot control"
        elif self.stack_in_bb > 200:
            return "✅ Deep Stack (>200 BB) — Room for multi-street maneuvering"

        return None

    def _get_simplified_action(
        self,
        situation: str,
        base_action: str
    ) -> str:
        """Formatted action banner"""
        return f"💡 **Holding {situation} → Recommended Action: {base_action}**"

    # ===================== MONSTER HANDS WITH GTO =====================

    def _recommend_monster_with_gto(
        self,
        hand_type: str,
        win_rate: float,
        texture: Dict,
        num_opponents: int,
        stage: GameStage,
        texture_match: Dict
    ) -> str:
        """Monster hands GTO recommendation"""
        base = "💎 **MONSTER HAND**\n\n"

        if hand_type == 'four_kind':
            base += "🔥 **Four of a Kind** — Virtually unbeatable monster!\n\n"

            if self.spr and self.spr < 2:
                base += f"⚠️ Low SPR={self.spr:.1f} — Commit stack for maximum value\n"

            sizing = self._get_bet_sizing_advice("value")

            if stage == GameStage.RIVER:
                situation = "river quads (nuts)"
                action = f"BET / RAISE ({sizing})"
            else:
                situation = "quads"
                action = "Maximum Aggression (Bet/Raise)"

            base += self._get_simplified_action(situation, action)

            base += "\n\n**Strategic Details:**\n"
            base += f"• Recommended Sizing: {sizing}\n"

            if self.position:
                base += f"• Position: {self.position}\n"
                if self.position in ["BTN", "CO"]:
                    base += "• In Position: Small bet to induce bluffs/calls\n"
                else:
                    base += "• Out of Position: Raise immediately\n"

            stack_warning = self._check_stack_depth_warning()
            if stack_warning:
                base += f"• {stack_warning}\n"

            base += f"• Vs {num_opponents} Opponents: Build heavy pot immediately\n"
            return base

        elif hand_type == 'full_house':
            base += "🏠 **Full House** — Extremely strong holding!\n\n"

            if texture_match['fullhouse_compatible']:
                base += "✅ Paired board — opponents can hold lower full houses.\n\n"
            else:
                base += "⚠️ Full House on unpaired board — disguised strength.\n\n"

            sizing = self._get_bet_sizing_advice("value")

            if self.spr and self.spr < 4:
                situation = "full house with low SPR"
                action = f"BET ({sizing}), ready to commit stack"
            else:
                situation = "full house"
                action = f"BET ({sizing}) for value"

            base += self._get_simplified_action(situation, action)

            base += "\n\n**Strategic Details:**\n"
            if self.pot_size and self.pot_size > 0:
                base += f"• Current Pot: {self.pot_size} chips\n"
                base += f"• Recommended Bet: {sizing}\n"

            if self.position:
                base += f"• Position: {self.position}\n"

            stack_warning = self._check_stack_depth_warning()
            if stack_warning:
                base += f"• {stack_warning}\n"

            if num_opponents == 1:
                base += "• Heads-Up: Check-raise option for value maximization\n"
            else:
                base += f"• {num_opponents} Opponents: Direct value betting\n"

            return base

        else:
            base += "👑 **STRAIGHT FLUSH** — Absolute Nuts!\n\n"

            sizing = self._get_bet_sizing_advice("value")
            situation = "straight flush (unbeatable)"

            if self.pot_size:
                overbet = self.pot_size * 2
                action = f"OVERBET ({overbet} chips / 2x pot) or Bet ({sizing})"
            else:
                action = f"OVERBET (2-3x pot) or Bet ({sizing})"

            base += self._get_simplified_action(situation, action)

            base += "\n\n**Strategic Details:**\n"
            base += "• Any aggression is highly profitable (+EV)\n"
            base += f"• Vs {num_opponents} Opponents: Build the pot aggressively\n"

            if self.position:
                base += f"• Position: {self.position}\n"

            return base

    # ===================== STRONG HANDS =====================

    def _recommend_strong_with_gto(
        self,
        hand_type: str,
        win_rate: float,
        texture: Dict,
        num_opponents: int,
        stage: GameStage,
        texture_match: Dict,
        outs_breakdown: Dict
    ) -> str:
        """Strong hands GTO recommendation"""
        base = "💪 **STRONG HAND**\n\n"

        if hand_type == 'flush':
            base += "♠️ **Flush**\n"
            if texture_match['flush_compatible']:
                base += "⚠️ **WARNING**: Monotone board — higher flush possible!\n"
            else:
                base += "✅ Flush on 2-tone board — unexpected by opponents!\n\n"

            if win_rate >= 75:
                base += "✅ **Excellent Win Rate** — Play aggressively for value!\n"
            elif win_rate >= 55:
                base += "⚠️ **Moderate Win Rate** — Cautious value betting\n"
            else:
                base += "❌ **Low Win Rate** — Pot control mandatory!\n"
        else:
            base += "📊 **Straight**\n"
            if texture_match['straight_compatible']:
                base += "⚠️ Coordinated board — straight is visible to opponents!\n\n"
            if texture.get('monotone') or texture.get('flush_draw'):
                base += "⚠️ **FLUSH THREAT** on board!\n\n"

            if win_rate >= 70:
                base += "✅ **Strong Straight** — Bet aggressively for value & protection\n"
            else:
                base += "⚠️ **Vulnerable Straight** — Exercise pot control\n"

        gto_details = "\n**📊 GTO Metrics:**\n"
        sizing = self._get_bet_sizing_advice("value" if win_rate >= 60 else "protection")
        gto_details += f"• **Bet Sizing**: {sizing}\n"

        if self.spr:
            gto_details += f"• **SPR**: {self.spr:.1f}\n"
        if self.position:
            gto_details += f"• **Position**: {self.position}\n"
        if self.pot_size:
            gto_details += f"• **Pot Size**: {self.pot_size} chips\n"

        stack_warning = self._check_stack_depth_warning()
        if stack_warning:
            gto_details += f"• {stack_warning}\n"

        if win_rate >= 70:
            situation = f"strong {hand_type} (Equity: {win_rate:.0f}%)"
            action = f"BET ({sizing}) for value"
        elif win_rate >= 55:
            situation = f"medium {hand_type}"
            action = f"BET ({sizing}) or Pot Control"
        else:
            situation = f"vulnerable {hand_type}"
            action = "Check-Call or Fold to heavy aggression"

        simplified = "\n" + self._get_simplified_action(situation, action)
        return base + gto_details + simplified

    # ===================== MEDIUM HANDS =====================

    def _recommend_medium_with_gto(
        self,
        hand_type: str,
        win_rate: float,
        texture: Dict,
        num_opponents: int,
        stage: GameStage,
        texture_match: Dict,
        total_outs: int
    ) -> str:
        """Medium hands GTO recommendation"""
        base = "🎯 **MEDIUM HAND**\n\n"

        if hand_type == 'three_kind':
            base += "🎲 **Three of a Kind (Set / Trips)**\n"
            if texture_match['set_compatible']:
                base += "✅ Hidden Set on unpaired board — Very strong!\n\n"
            else:
                base += "⚠️ Trips on paired board — Opponent may hold full house\n\n"
        else:
            base += "🎴 **Two Pair**\n"
            if texture.get('paired'):
                base += "⚠️ Paired board — Counterfeit / Trips danger\n\n"

        gto_addon = "\n**📊 GTO Metrics:**\n"
        sizing = self._get_bet_sizing_advice("value" if win_rate >= 55 else "protection")
        gto_addon += f"• **Bet Sizing**: {sizing}\n"

        if self.spr:
            gto_addon += f"• **SPR**: {self.spr:.1f}\n"
        if self.position:
            gto_addon += f"• **Position**: {self.position}\n"

        if win_rate >= 60:
            situation = f"{hand_type} (Win Rate: {win_rate:.0f}%)"
            action = f"BET ({sizing}) for Value"
        elif win_rate >= 45:
            situation = f"{hand_type} (Moderate Win Rate)"
            action = f"BET ({sizing}) or Check-Call"
        else:
            situation = f"weak {hand_type}"
            action = "Pot Control / Fold to Heavy Raises"

        simplified = "\n" + self._get_simplified_action(situation, action)
        return base + gto_addon + simplified

    # ===================== WEAK MADE HANDS =====================

    def _recommend_weak_made_with_gto(
        self,
        hand_type: str,
        win_rate: float,
        texture: Dict,
        num_opponents: int,
        stage: GameStage,
        total_outs: int,
        outs_breakdown: Dict
    ) -> str:
        """Weak made hands GTO recommendation"""
        base = "⚠️ **WEAK MADE HAND (One Pair)**\n\n"

        if win_rate >= 70:
            base += "✅ **High Equity (Top Pair / Overpair)** — Bet for value & protection\n"
        elif win_rate >= 55:
            base += "✅ **Good Equity** — Cautious value betting\n"
        elif win_rate >= 40:
            base += "⚠️ **Medium Equity** — Pot control / Check-Call\n"
        else:
            base += "❌ **Low Equity** — Likely behind, Fold to aggression\n"

        gto_addon = "\n**📊 GTO Metrics:**\n"
        sizing = self._get_bet_sizing_advice("protection")
        gto_addon += f"• **Bet Sizing**: {sizing}\n"

        if self.spr:
            gto_addon += f"• **SPR**: {self.spr:.1f}\n"
        if self.position:
            gto_addon += f"• **Position**: {self.position}\n"

        if win_rate >= 70:
            situation = "top pair / overpair"
            action = f"BET ({sizing}) for Value"
        elif win_rate >= 55:
            situation = "good pair"
            action = "Bet or Check-Call"
        elif win_rate >= 40:
            situation = "middle pair"
            action = "Check-Call or Fold to aggression"
        else:
            situation = "weak pair"
            action = "Check-Fold"

        simplified = "\n" + self._get_simplified_action(situation, action)
        return base + gto_addon + simplified

    # ===================== DRAWS =====================

    def _recommend_draw_with_gto(
        self,
        total_outs: int,
        outs_breakdown: Dict,
        win_rate: float,
        texture: Dict,
        num_opponents: int,
        stage: GameStage
    ) -> str:
        """Draws GTO recommendation with EV evaluation"""
        base = "🎲 **DRAW / NO MADE HAND**\n\n"
        base += f"**Total Outs**: {total_outs}\n"

        if total_outs >= 15:
            base += "🚀 **MONSTER DRAW (15+ Outs)** — Favorite even against made hands!\n"
            situation = "monster draw (15+ outs)"
            action = "SEMI-BLUFF RAISE / BET Aggressively (+EV)"
        elif total_outs >= 12:
            base += "⚡ **STRONG DRAW (12-14 Outs)** — Excellent equity!\n"
            situation = "strong draw (12-14 outs)"
            action = "BET for Semi-Bluff or CALL"
        elif total_outs >= 9:
            base += "✅ **GOOD DRAW (9-11 Outs)** — Solid implied odds\n"
            situation = "flush / open-ended straight draw"
            action = "CALL small/medium bets (+EV)"
        elif total_outs >= 6:
            base += "⚠️ **MEDIUM DRAW (6-8 Outs)**\n"
            situation = "gutshot / overcards"
            action = "CALL small bets ONLY if pot odds permit"
        elif total_outs >= 4:
            base += "🤏 **WEAK DRAW (4-5 Outs)**\n"
            situation = "weak draw"
            action = "FOLD to any substantial bet"
        else:
            base += "❌ **NO DRAW / HIGH CARD**\n"
            situation = "air / no outs"
            action = "FOLD to any bet"

        gto_addon = "\n**📊 GTO Pot Odds & EV Analysis:**\n"
        if self.pot_size and self.pot_size > 0:
            gto_addon += f"• **Current Pot**: {self.pot_size} chips\n"
            if total_outs >= 9:
                bet_call = int(self.pot_size * 0.5)
                pot_odds = (bet_call / (self.pot_size + bet_call)) * 100 if bet_call > 0 else 0
                draw_equity = min(total_outs * 4 if stage == GameStage.FLOP else total_outs * 2, 100)
                gto_addon += f"• **At 1/2 Pot Bet ({bet_call} chips)**: Required Pot Odds: {pot_odds:.1f}% | Draw Equity: ~{draw_equity:.0f}%\n"
                if draw_equity > pot_odds:
                    gto_addon += "  → **PROFITABLE CALL (+EV)**\n"
                else:
                    gto_addon += "  → **UNPROFITABLE CALL (-EV)**\n"

        if total_outs >= 12:
            sizing = self._get_bet_sizing_advice("semi-bluff")
            gto_addon += f"• **Recommended Semi-Bluff Size**: {sizing}\n"

        if self.position:
            gto_addon += f"• **Position**: {self.position}\n"

        simplified = "\n" + self._get_simplified_action(situation, action)
        return base + gto_addon + simplified


def generate_improved_recommendation(analysis_result: Dict) -> str:
    """Integration helper function"""
    engine = ImprovedRecommendationEngine()
    
    current_hand = analysis_result.get('current_hand', 'high card')
    equity_data = analysis_result.get('equity', {})
    win_rate = equity_data.get('win_rate', 0)
    
    outs_data = analysis_result.get('outs_analysis', {})
    total_outs = analysis_result.get('total_outs', 0)
    
    texture_analysis = analysis_result.get('board_texture', {})
    num_opponents = analysis_result.get('num_opponents', 1)
    stage = analysis_result.get('stage', GameStage.FLOP)
    board_cards = analysis_result.get('board_cards_list', [])
    
    return engine.generate_recommendation(
        current_hand=current_hand,
        win_rate=win_rate,
        total_outs=total_outs,
        outs_breakdown=outs_data,
        texture_analysis=texture_analysis,
        num_opponents=num_opponents,
        stage=stage,
        board_cards=board_cards
    )
