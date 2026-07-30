"""
Decision Engine - Движок принятия решений

Основан на анализе:
- SPR (Stack-to-Pot Ratio)
- Pot Odds (Шансы банка)
- Equity (Эквити от Монте-Карло)

Выходные данные:
- Рекомендация: CALL / FOLD / RAISE
- Визуализация шансов (градусник)
- SPR светофор
- Текстовое обоснование решения
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
import logging

from .table_data import TableData, PlayerInfo

logger = logging.getLogger(__name__)


class Decision(Enum):
    """Типы решений"""
    FOLD = "FOLD"
    CHECK = "CHECK"
    CALL = "CALL"
    BET = "BET"
    RAISE = "RAISE"


class SPRLevel(Enum):
    """Уровни SPR"""
    LOW = "low"       # SPR < 3 - Игра на стек
    MEDIUM = "medium" # 3 <= SPR <= 6 - Стандартная игра
    HIGH = "high"     # SPR > 6 - Осторожная игра


class OddsZone(Enum):
    """Зоны выгодности"""
    GREEN = "green"   # Эквити выше шансов - выгодный CALL
    YELLOW = "yellow" # Пограничное решение (+/- 5%)
    RED = "red"       # Эквити ниже шансов - FOLD


@dataclass
class EffectiveStackData:
    """Данные об эффективном стеке"""
    hero_stack: int = 0
    villain_max_stack: int = 0
    effective_stack: int = 0


@dataclass
class PotOddsData:
    """Данные о шансах банка"""
    to_call: int = 0
    pot_after_call: int = 0
    required_equity: float = 0.0  # Минимальный % эквити для безубыточного колла
    is_check_available: bool = False


@dataclass
class SPRData:
    """Данные о Stack-to-Pot Ratio"""
    value: float = 0.0
    level: SPRLevel = SPRLevel.MEDIUM
    interpretation: str = ""


@dataclass
class EquityData:
    """Данные об эквити"""
    win_rate: float = 0.0         # Вероятность победы (%)
    tie_rate: float = 0.0         # Вероятность ничьей (%)
    lose_rate: float = 0.0        # Вероятность проигрыша (%)
    total_simulations: int = 0


@dataclass
class DecisionResult:
    """Полный результат анализа и рекомендации"""
    
    # Основная рекомендация
    decision: Decision = Decision.CHECK
    confidence: float = 0.0  # 0-100%
    
    # Расчетные данные
    effective_stack: EffectiveStackData = field(default_factory=EffectiveStackData)
    pot_odds: PotOddsData = field(default_factory=PotOddsData)
    spr: SPRData = field(default_factory=SPRData)
    equity: EquityData = field(default_factory=EquityData)
    
    # Сравнение эквити и шансов
    equity_vs_odds_diff: float = 0.0  # equity - required_equity
    odds_zone: OddsZone = OddsZone.YELLOW
    
    # Текстовые пояснения
    reasoning: str = ""
    short_advice: str = ""
    
    # Позиционная информация
    hero_position: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для UI"""
        return {
            "decision": self.decision.value,
            "confidence": self.confidence,
            "effective_stack": {
                "hero": self.effective_stack.hero_stack,
                "villain_max": self.effective_stack.villain_max_stack,
                "effective": self.effective_stack.effective_stack
            },
            "pot_odds": {
                "to_call": self.pot_odds.to_call,
                "pot_after_call": self.pot_odds.pot_after_call,
                "required_equity": self.pot_odds.required_equity,
                "is_check": self.pot_odds.is_check_available
            },
            "spr": {
                "value": self.spr.value,
                "level": self.spr.level.value,
                "interpretation": self.spr.interpretation
            },
            "equity": {
                "win": self.equity.win_rate,
                "tie": self.equity.tie_rate,
                "lose": self.equity.lose_rate,
                "simulations": self.equity.total_simulations
            },
            "comparison": {
                "diff": self.equity_vs_odds_diff,
                "zone": self.odds_zone.value
            },
            "reasoning": self.reasoning,
            "short_advice": self.short_advice,
            "hero_position": self.hero_position
        }


class DecisionEngine:
    """
    Движок принятия решений.
    
    Поток данных:
    [TableData + Equity] -> [Preprocessing] -> [Calculations] -> [Decision Logic] -> [Result]
    """
    
    def __init__(self):
        self.last_result: Optional[DecisionResult] = None
    
    def analyze(self, 
                table_data: TableData, 
                equity: Optional[Dict[str, float]] = None) -> DecisionResult:
        """
        Основной метод анализа ситуации.
        
        Args:
            table_data: Данные стола (из TableDataCollector)
            equity: Данные эквити из Monte Carlo {"win_rate": float, "tie_rate": float, ...}
            
        Returns:
            DecisionResult с полным анализом и рекомендацией
        """
        result = DecisionResult()
        
        hero = table_data.get_hero()
        if not hero:
            result.reasoning = "Герой не определен"
            return result
        
        result.hero_position = hero.position or "Unknown"
        
        # 1. Предобработка - эффективный стек
        result.effective_stack = self._calculate_effective_stack(table_data, hero)
        
        # 2. Расчет цены колла и шансов банка
        result.pot_odds = self._calculate_pot_odds(table_data, hero)
        
        # 3. Расчет SPR (только постфлоп)
        if len(table_data.community_cards) >= 3:
            result.spr = self._calculate_spr(
                result.effective_stack.effective_stack, 
                table_data.total_pot
            )
        
        # 4. Обработка эквити
        if equity:
            result.equity = EquityData(
                win_rate=equity.get("win_rate", 0),
                tie_rate=equity.get("tie_rate", 0),
                lose_rate=100 - equity.get("win_rate", 0) - equity.get("tie_rate", 0),
                total_simulations=equity.get("total_simulations", 0)
            )
        
        # 5. Логика принятия решений
        result = self._make_decision(result, table_data)
        
        self.last_result = result
        return result
    
    def _calculate_effective_stack(self, table_data: TableData, hero: PlayerInfo) -> EffectiveStackData:
        """
        Расчет эффективного стека.
        Effective Stack = min(Hero Stack, Max Villain Stack)
        """
        hero_stack = hero.stack or 0
        
        # Находим максимальный стек среди оппонентов
        villain_stacks = [
            p.stack for p in table_data.get_active_players() 
            if not p.is_hero and p.stack is not None
        ]
        
        villain_max = max(villain_stacks) if villain_stacks else 0
        effective = min(hero_stack, villain_max) if villain_max > 0 else hero_stack
        
        return EffectiveStackData(
            hero_stack=hero_stack,
            villain_max_stack=villain_max,
            effective_stack=effective
        )
    
    def _calculate_pot_odds(self, table_data: TableData, hero: PlayerInfo) -> PotOddsData:
        """
        Расчет шансов банка.
        
        Required Equity = To_Call / (Pot + To_Call)
        """
        max_bet = table_data.get_max_bet()
        hero_bet = hero.bet
        to_call = max(0, max_bet - hero_bet)
        
        is_check = to_call == 0
        pot_after_call = table_data.total_pot + to_call
        
        # Required equity для безубыточного колла
        if pot_after_call > 0 and to_call > 0:
            required_equity = (to_call / pot_after_call) * 100
        else:
            required_equity = 0.0
        
        return PotOddsData(
            to_call=to_call,
            pot_after_call=pot_after_call,
            required_equity=required_equity,
            is_check_available=is_check
        )
    
    def _calculate_spr(self, effective_stack: int, pot: int) -> SPRData:
        """
        Расчет Stack-to-Pot Ratio.
        
        SPR < 3: Низкий - игра на стек, не выкидывай топ-пару
        3-6: Средний - стандартная игра
        > 6: Высокий - осторожная игра
        """
        if pot == 0:
            return SPRData(
                value=float('inf'),
                level=SPRLevel.HIGH,
                interpretation="Банк пуст"
            )
        
        spr = effective_stack / pot
        
        if spr < 3:
            level = SPRLevel.LOW
            interpretation = "Низкий SPR: Игра на стек. Не выкидывай топ-пару!"
        elif spr <= 6:
            level = SPRLevel.MEDIUM
            interpretation = "Средний SPR: Стандартная постфлоп игра."
        else:
            level = SPRLevel.HIGH
            interpretation = "Высокий SPR: Осторожная игра, избегай больших банков без натсов."
        
        return SPRData(
            value=round(spr, 2),
            level=level,
            interpretation=interpretation
        )
    
    def _make_decision(self, result: DecisionResult, table_data: TableData) -> DecisionResult:
        """
        Логика принятия решений.
        
        Сценарий 1: Нет ставки (Check/Bet)
        Сценарий 2: Есть ставка (Call/Fold/Raise)
        """
        pot_odds = result.pot_odds
        equity = result.equity
        
        # Сценарий 1: Чек доступен
        if pot_odds.is_check_available:
            result = self._decide_check_or_bet(result, table_data)
        else:
            # Сценарий 2: Нужно коллировать
            result = self._decide_call_or_fold(result)
        
        return result
    
    def _decide_check_or_bet(self, result: DecisionResult, table_data: TableData) -> DecisionResult:
        """Решение: Чек или Бет"""
        equity_pct = result.equity.win_rate
        num_opponents = table_data.get_active_player_count() - 1
        
        # Порог для велью-бета зависит от количества оппонентов
        # 1 оппонент: > 50%
        # 2 оппонента: > 33%
        # 3+ оппонента: > 25%
        value_threshold = 50 / max(1, num_opponents)
        
        if equity_pct > value_threshold:
            result.decision = Decision.BET
            result.confidence = min(equity_pct, 100)
            result.short_advice = f"BET for value ({equity_pct:.1f}% vs {value_threshold:.1f}% threshold)"
            result.reasoning = (
                f"Эквити {equity_pct:.1f}% превышает порог {value_threshold:.1f}% "
                f"для велью-бета против {num_opponents} оппонентов. "
                f"Рекомендуется ставка для извлечения ценности."
            )
        else:
            result.decision = Decision.CHECK
            result.confidence = 100 - equity_pct
            result.short_advice = "CHECK (not enough equity for value)"
            result.reasoning = (
                f"Эквити {equity_pct:.1f}% недостаточно для велью-бета "
                f"(нужно > {value_threshold:.1f}%). Рекомендуется чек."
            )
        
        result.odds_zone = OddsZone.YELLOW  # Нет колла - нейтральная зона
        
        return result
    
    def _decide_call_or_fold(self, result: DecisionResult) -> DecisionResult:
        """Решение: Колл или Фолд"""
        pot_odds = result.pot_odds
        equity_pct = result.equity.win_rate
        required = pot_odds.required_equity
        
        diff = equity_pct - required
        result.equity_vs_odds_diff = round(diff, 2)
        
        # Зоны решений
        if diff > 5:
            # Эквити значительно выше шансов - выгодный колл
            result.decision = Decision.CALL
            result.odds_zone = OddsZone.GREEN
            result.confidence = min(90 + diff, 100)
            result.short_advice = f"CALL (+{diff:.1f}% edge)"
            result.reasoning = (
                f"Выгодный CALL! Твоё эквити {equity_pct:.1f}% превышает "
                f"необходимые {required:.1f}% на {diff:.1f}%. "
                f"На дистанции это приносит прибыль."
            )
            
        elif diff > 0:
            # Эквити чуть выше - маргинальный колл
            result.decision = Decision.CALL
            result.odds_zone = OddsZone.YELLOW
            result.confidence = 50 + diff * 5
            result.short_advice = f"CALL (marginal, +{diff:.1f}%)"
            result.reasoning = (
                f"Маргинальный CALL. Эквити {equity_pct:.1f}% немного выше "
                f"необходимых {required:.1f}%. Колл технически плюсовый, "
                f"но с учётом рэйка может быть близок к безубыточности."
            )
            
        elif diff >= -5:
            # Пограничная зона
            result.decision = Decision.FOLD
            result.odds_zone = OddsZone.YELLOW
            result.confidence = 40
            result.short_advice = f"FOLD (borderline, {diff:.1f}%)"
            result.reasoning = (
                f"Пограничная ситуация. Эквити {equity_pct:.1f}% близко к "
                f"необходимым {required:.1f}% (разница {diff:.1f}%). "
                f"Рекомендуется осторожный фолд, но против агрессивных игроков "
                f"колл может быть оправдан."
            )
            
        else:
            # Эквити значительно ниже - чёткий фолд
            result.decision = Decision.FOLD
            result.odds_zone = OddsZone.RED
            result.confidence = min(90 - diff, 100)
            result.short_advice = f"FOLD (clear, {diff:.1f}%)"
            result.reasoning = (
                f"Чёткий FOLD. Твоё эквити {equity_pct:.1f}% значительно ниже "
                f"необходимых {required:.1f}% (разница {diff:.1f}%). "
                f"Колл минусовый на дистанции."
            )
        
        # Добавляем информацию о цене колла
        result.reasoning += (
            f"\n\nЦена колла: {pot_odds.to_call}. "
            f"Банк после колла: {pot_odds.pot_after_call}."
        )
        
        return result
    
    def get_visualization_data(self, result: DecisionResult) -> Dict[str, Any]:
        """
        Получить данные для визуализации в UI.
        
        Returns:
            Dict с данными для:
            - Градусника (pot odds vs equity)
            - SPR светофора
            - Цветового кодирования решения
        """
        return {
            # Градусник шансов
            "thermometer": {
                "pot_odds_marker": result.pot_odds.required_equity,  # Красная метка
                "equity_fill": result.equity.win_rate,               # Зелёная заливка
                "is_profitable": result.equity.win_rate > result.pot_odds.required_equity
            },
            
            # SPR светофор
            "spr_light": {
                "color": self._get_spr_color(result.spr.level),
                "value": result.spr.value,
                "text": result.spr.interpretation
            },
            
            # Цвет решения
            "decision_color": self._get_decision_color(result.decision, result.odds_zone),
            
            # Позиция
            "position_badge": {
                "text": result.hero_position,
                "color": self._get_position_color(result.hero_position)
            }
        }
    
    def _get_spr_color(self, level: SPRLevel) -> str:
        """Цвет для SPR светофора"""
        colors = {
            SPRLevel.LOW: "#F44336",    # Красный
            SPRLevel.MEDIUM: "#FFEB3B", # Жёлтый
            SPRLevel.HIGH: "#4CAF50"    # Зелёный
        }
        return colors.get(level, "#888888")
    
    def _get_decision_color(self, decision: Decision, zone: OddsZone) -> str:
        """Цвет для решения"""
        if decision == Decision.FOLD:
            return "#F44336"  # Красный
        elif decision in (Decision.CALL, Decision.CHECK):
            if zone == OddsZone.GREEN:
                return "#4CAF50"  # Зелёный
            elif zone == OddsZone.YELLOW:
                return "#FFEB3B"  # Жёлтый
            else:
                return "#FF9800"  # Оранжевый
        else:  # BET, RAISE
            return "#2196F3"  # Синий
    
    def _get_position_color(self, position: str) -> str:
        """Цвет для позиции"""
        late_positions = ["BTN", "CO", "HJ"]
        early_positions = ["UTG", "UTG+1", "MP", "MP+1"]
        blind_positions = ["BB", "SB"]
        
        if position in late_positions:
            return "#4CAF50"  # Зелёный - хорошая позиция
        elif position in early_positions:
            return "#FF9800"  # Оранжевый - ранняя позиция
        elif position in blind_positions:
            return "#F44336"  # Красный - блайнды
        else:
            return "#888888"  # Серый - неизвестно
