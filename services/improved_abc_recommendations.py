"""
Улучшенная система ABC рекомендаций для analysis_service.py
С учетом: board texture, количества оппонентов, стадии улицы, позиционной игры
+ GTO analysis with detailed game data: pot odds, SPR, stacks, position
"""

from typing import Dict, List, Optional
from core.domain import Card, GameState, GameStage


class ImprovedRecommendationEngine:
    """
    Расширенная система ABC рекомендаций с учетом:
    - Board texture compatibility с рукой игрока
    - Количество оппонентов (multiway vs heads-up)
    - Стадия игры (flop/turn/river)
    - Позиционные советы (для информированного пользователя)
    - Советы по поведению оппонента (для информированного пользователя)
    - GTO метрики: pot odds, SPR, стеки в BB, позиция за столом
    """

    # Константы для классификации комбинаций
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

        # NEW Detailed Data parameters (all optional)
        pot_size: Optional[int] = None,
        player_stack: Optional[int] = None,
        spr: Optional[float] = None,
        stack_in_bb: Optional[float] = None,
        position: Optional[str] = None
    ) -> str:
        """
        Главная функция генерации рекомендаций с GTO анализом
        """

        # Save game data for use in recommendation logic
        self.pot_size = pot_size
        self.player_stack = player_stack
        self.spr = spr
        self.stack_in_bb = stack_in_bb
        self.position = position

        # Нормализация названия руки
        hand_type = self._normalize_hand_name(current_hand)

        # Определяем категорию руки
        hand_category = self._categorize_hand(hand_type)

        # Проверяем совместимость руки с текстурой борда
        texture_match = self._check_texture_compatibility(hand_type, texture_analysis, board_cards)

        # Генерация базовой рекомендации с GTO-улучшениями
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

        else:  # draw / no made hand
            return self._recommend_draw_with_gto(
                total_outs, outs_breakdown, win_rate,
                texture_analysis, num_opponents, stage
            )
    
    def _normalize_hand_name(self, hand_name: str) -> str:
        """Нормализация названий комбинаций"""
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
        """Категоризация руки"""
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
    
    def _check_texture_compatibility(
        self, 
        hand_type: str, 
        texture: Dict,
        board_cards: List[Card]
    ) -> Dict[str, bool]:
        """
        Проверяет, усиливает ли текстура борда нашу руку
        или создает опасность
        """
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
        """Расчет pot odds в процентах"""
        if self.pot_size is None:
            return None
        total_pot = self.pot_size + bet_to_call
        return (bet_to_call / total_pot) * 100 if total_pot > 0 else None

    def _get_bet_sizing_advice(self, situation: str = "value") -> str:
        """
        Генерация совета по размеру ставки в BB и фишках
        situation: "value", "protection", "bluff", "semi-bluff"
        """
        if self.pot_size is None:
            return "Bet 60-75% от банка"

        sizing_map = {
            "value": (0.65, 0.85),      # 65-85% банка
            "protection": (0.55, 0.70),  # 55-70% банка
            "bluff": (0.50, 0.65),       # 50-65% банка
            "semi-bluff": (0.60, 0.75)   # 60-75% банка
        }

        min_pct, max_pct = sizing_map.get(situation, (0.60, 0.75))
        min_amount = int(self.pot_size * min_pct)
        max_amount = int(self.pot_size * max_pct)

        # Форматирование в BB если доступно
        if self.stack_in_bb is not None and self.player_stack and self.player_stack > 0:
            estimated_bb = self.player_stack / self.stack_in_bb if self.stack_in_bb > 0 else None
            if estimated_bb and estimated_bb > 0:
                min_bb = round(min_amount / estimated_bb, 1)
                max_bb = round(max_amount / estimated_bb, 1)
                return f"{min_amount}-{max_amount} фишек ({min_bb}-{max_bb} BB)"

        return f"{min_amount}-{max_amount} фишек"

    def _check_stack_depth_warning(self) -> Optional[str]:
        """Генерация предупреждений о глубине стека"""
        if self.stack_in_bb is None:
            return None

        if self.stack_in_bb < 15:
            return "⚠️ КОРОТКИЙ СТЕК (<15BB) - рассмотрите push/fold стратегию"
        elif self.stack_in_bb < 30:
            return "⚠️ Средний стек (15-30BB) - осторожная игра"
        elif self.stack_in_bb > 200:
            return "✅ Глубокий стек (>200BB) - больше места для маневров"

        return None

    def _get_simplified_action(
        self,
        situation: str,
        base_action: str
    ) -> str:
        """
        Генерация упрощенного русского вывода:
        "У вас [situation], нажимайте [action]"
        """
        return f"💡 **У вас {situation}, нажимайте {base_action}**"

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
        """GTO-улучшенные рекомендации для монстр-рук"""

        base = "💎 **МОНСТР-РУКА**\n\n"

        # Квадс
        if hand_type == 'four_kind':
            base += "🔥 **Каре** - практически непобедимая рука!\n\n"

            # SPR анализ
            if self.spr and self.spr < 2:
                base += f"⚠️ SPR={self.spr:.1f} - малый банк, играйте на максимизацию\n"

            sizing = self._get_bet_sizing_advice("value")

            if stage == GameStage.RIVER:
                situation = "натс на ривере с каре"
                action = f"bet/raise {sizing}"
            else:
                situation = "каре"
                action = "максимальная агрессия (bet/raise)"

            base += self._get_simplified_action(situation, action)

            base += "\n\n**Детали:**\n"
            base += f"• Размер ставки: {sizing}\n"

            if self.position:
                base += f"• Ваша позиция: {self.position}\n"
                if self.position in ["BTN", "CO"]:
                    base += "• В позиции: можно small bet для индуса\n"
                else:
                    base += "• Без позиции: рейз сразу\n"

            stack_warning = self._check_stack_depth_warning()
            if stack_warning:
                base += f"• {stack_warning}\n"

            base += f"• Против {num_opponents} оппонентов: крупные ставки сразу\n"

            return base
        
        # Фулл-хаус
        elif hand_type == 'full_house':
            base += "🏠 **Фулл-хаус** - очень сильная рука!\n\n"

            if texture_match['fullhouse_compatible']:
                base += "✅ Парный борд - оппоненты могут иметь меньший фулл-хаус.\n\n"
            else:
                base += "⚠️ Фулл-хаус на непарном борде - скрытая сила.\n\n"

            sizing = self._get_bet_sizing_advice("value")

            if self.spr:
                if self.spr < 4:
                    situation = "фулл-хаус с малым SPR (готовы идти олл-ин)"
                    action = f"bet/raise {sizing}, готовы к олл-ин"
                else:
                    situation = "фулл-хаус"
                    action = f"bet {sizing} для value"
            else:
                situation = "фулл-хаус"
                action = f"bet {sizing}"

            base += self._get_simplified_action(situation, action)

            base += "\n\n**Детали:**\n"
            if self.pot_size and self.pot_size > 0:
                base += f"• Текущий банк: {self.pot_size} фишек\n"
                base += f"• Рекомендуемая ставка: {sizing}\n"

            if self.position:
                base += f"• Ваша позиция: {self.position}\n"

            stack_warning = self._check_stack_depth_warning()
            if stack_warning:
                base += f"• {stack_warning}\n"

            if num_opponents == 1:
                base += "• Heads-up: можно чек-рейз для максимизации\n"
            else:
                base += f"• {num_opponents} оппонентов: прямые ставки (кто-то заплатит)\n"

            return base

        # Стрит-флеш
        else:  # straight_flush
            base += "👑 **СТРИТ-ФЛЕШ** - абсолютный орех!\n\n"

            sizing = self._get_bet_sizing_advice("value")
            situation = "стрит-флеш (непобедимая рука)"

            if self.pot_size:
                overbet = self.pot_size * 2
                action = f"overbet {overbet} фишек (2x pot) или bet {sizing}"
            else:
                action = f"overbet 2-3x pot или bet {sizing}"

            base += self._get_simplified_action(situation, action)

            base += "\n\n**Детали:**\n"
            base += "• Любая агрессия оправдана\n"
            base += f"• {num_opponents} оппонентов: кто-то обязательно заплатит\n"

            if self.position:
                base += f"• Ваша позиция: {self.position}\n"
                if self.position in ["BTN", "CO"]:
                    base += "• В позиции: slow-play разрешен для trap'а\n"
                else:
                    base += "• Без позиции: агрессия сразу\n"

            return base

    # Старый метод (сохранен как fallback)
    def _recommend_monster(self, hand_type, win_rate, texture, num_opponents, stage, texture_match):
        """Старая версия - fallback если GTO версия сломается"""
        return self._recommend_monster_with_gto(hand_type, win_rate, texture, num_opponents, stage, texture_match)
    
    # ===================== STRONG HANDS =====================
    
    def _recommend_strong(
        self,
        hand_type: str,
        win_rate: float,
        texture: Dict,
        num_opponents: int,
        stage: GameStage,
        texture_match: Dict,
        outs_breakdown: Dict
    ) -> str:
        """Рекомендации для сильных рук (флеш, стрит)"""
        
        base = "💪 **СИЛЬНАЯ РУКА**\n\n"
        
        # Флеш
        if hand_type == 'flush':
            base += "♠️ **Флеш**\n"
            
            if texture_match['flush_compatible']:
                base += "⚠️ **ВНИМАНИЕ**: Монотонный борд - возможен старший флеш у оппонента!\n"
                base += "• Оцените старшинство вашего флеша:\n"
                base += "  - Ореховый/второй флеш: Агрессивная игра\n"
                base += "  - Низкий флеш: Осторожная игра, pot control\n\n"
            else:
                base += "✅ Флеш на 2-tone борде - оппоненты не ожидают!\n\n"
            
            if win_rate >= 75:
                base += "✅ **Винрейт отличный** - играем на value!\n"
                base += "**Действия:**\n"
                base += "• Флоп/терн: Bet для защиты и value\n"
                base += "• Ривер: Крупный value bet (60-75% pot)\n"
            elif win_rate >= 55:
                base += "⚠️ **Винрейт умеренный** - осторожная игра\n"
                base += "**Действия:**\n"
                base += "• Средние ставки для value\n"
                base += "• Избегать огромных банков\n"
            else:
                base += "❌ **Винрейт низкий** - pot control обязателен!\n"
                base += "**Действия:**\n"
                base += "• Чек-колл линия\n"
                base += "• Fold к агрессии, если борд парный (фулл-хаус)\n"
            
            base += f"\n• Против {num_opponents} оппонентов: "
            if num_opponents == 1:
                base += "Можно блефкэтчить\n"
            else:
                base += "Осторожнее - кто-то может иметь старший флеш\n"
            
            base += "\n" + self._add_opponent_behavior_advice(**{
                "агрессивен": "Чек-колл или чек-рейз если флеш старший",
                "пассивен": "Bet для value - возьмёт с младшими руками",
                "на тильте": "Максимальная агрессия - заплатит широко"
            })
            
        # Стрит
        else:  # straight
            base += "📊 **Стрит**\n"
            
            if texture_match['straight_compatible']:
                base += "⚠️ Координированный борд - ваш стрит виден!\n"
                base += "• Оппоненты могут иметь тот же стрит (сплит) или старший стрит\n"
                base += "• Проверьте, ореховый ли ваш стрит\n\n"
            
            if texture.get('monotone') or texture.get('flush_draw'):
                base += "⚠️ **ОПАСНОСТЬ ФЛЕША** на борде!\n"
                base += "• Играйте осторожно если борд 3-flush\n"
                base += "• На ривере к флешу - только чек-колл малых ставок\n\n"
            
            if win_rate >= 70:
                base += "✅ **Сильный стрит** - играем агрессивно\n"
                base += "**Действия:**\n"
                base += "• Bet для value и защиты от дро\n"
                base += "• Не давать бесплатных карт к флешу\n"
            else:
                base += "⚠️ **Уязвимый стрит** - pot control\n"
                base += "**Действия:**\n"
                base += "• Средние ставки\n"
                base += "• Fold к агрессии на флешевом/парном ривере\n"
            
            base += f"\n• {num_opponents} оппонентов: "
            if num_opponents >= 3:
                base += "Multiway - кто-то может иметь флеш/фулл-хаус\n"
            
            base += "\n" + self._add_positional_advice(
                "Можно чек-рейз на терне для максимизации",
                "Bet сразу - не давать дешевых карт оппонентам"
            )
        
        return base

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
        """GTO-улучшенная версия рекомендаций для сильных рук"""

        # Получаем базовую рекомендацию
        base_rec = self._recommend_strong(hand_type, win_rate, texture, num_opponents, stage, texture_match, outs_breakdown)

        # Добавляем GTO детали
        gto_details = "\n\n" + "="*50 + "\n**📊 GTO АНАЛИЗ:**\n" + "="*50 + "\n"

        # Sizing
        sizing = self._get_bet_sizing_advice("value" if win_rate >= 60 else "protection")
        gto_details += f"• **Размер ставки**: {sizing}\n"

        # SPR
        if self.spr:
            gto_details += f"• **SPR**: {self.spr:.1f}"
            if self.spr < 5:
                gto_details += " - готовы идти олл-ин\n"
            elif self.spr > 10:
                gto_details += " - есть место для маневров\n"
            else:
                gto_details += " - средний стек\n"

        # Position
        if self.position:
            gto_details += f"• **Позиция**: {self.position}\n"
            if self.position in ["BTN", "CO"]:
                gto_details += "  → В позиции: контроль размера банка\n"
            else:
                gto_details += "  → Без позиции: осторожнее с блефами\n"

        # Stack depth
        stack_warning = self._check_stack_depth_warning()
        if stack_warning:
            gto_details += f"• {stack_warning}\n"

        # Pot size info
        if self.pot_size:
            gto_details += f"• **Текущий банк**: {self.pot_size} фишек\n"

        # Упрощенная рекомендация
        if win_rate >= 70:
            situation = f"сильный {hand_type} (винрейт {win_rate:.0f}%)"
            action = f"bet {sizing} для value"
        elif win_rate >= 55:
            situation = f"{hand_type} средней силы"
            action = f"bet {sizing} или pot control"
        else:
            situation = f"уязвимый {hand_type}"
            action = "чек-колл или fold к агрессии"

        simplified = "\n\n" + self._get_simplified_action(situation, action)

        return base_rec + gto_details + simplified

    # ===================== MEDIUM HANDS =====================
    
    def _recommend_medium(
        self,
        hand_type: str,
        win_rate: float,
        texture: Dict,
        num_opponents: int,
        stage: GameStage,
        texture_match: Dict,
        total_outs: int
    ) -> str:
        """Рекомендации для средних рук"""
        
        base = "🎯 **СРЕДНЯЯ РУКА**\n\n"
        
        # Сет/трипс
        if hand_type == 'three_kind':
            base += "🎲 **Сет/Трипс**\n"
            
            if texture_match['set_compatible']:
                base += "✅ Скрытый сет на непарном борде - сильная рука!\n\n"
            else:
                base += "⚠️ Трипс на парном борде - оппонент может иметь фулл-хаус\n\n"
            
            # Проверяем опасности на борде
            dangers = []
            if texture.get('monotone'):
                dangers.append("монотонный борд (флеш)")
            if texture.get('coordinated'):
                dangers.append("координированный борд (стрит)")
            
            if dangers:
                base += f"⚠️ **ОПАСНОСТИ**: {', '.join(dangers)}\n"
                base += "• Сет уязвим к старшим комбинациям\n"
                base += "• Играйте осторожнее на опасных бордах\n\n"
            
            # Ауты на улучшение
            if total_outs >= 7:  # ауты на фулл-хаус
                base += f"🎯 У вас {total_outs} аутов на фулл-хаус!\n"
                base += "• Можно агрессивно играть даже против возможного флеша\n\n"
            
            if win_rate >= 60:
                base += "✅ **Винрейт хороший** - играем на value\n"
                base += "**Действия:**\n"
                base += "• Флоп: Bet для защиты и value (50-60% pot)\n"
                base += "• Терн: Продолжаем bet\n"
                base += "• Ривер: Value bet если нет флеша на борде\n"
            elif win_rate >= 45:
                base += "⚠️ **Винрейт средний** - осторожная игра\n"
                base += "**Действия:**\n"
                base += "• Малые/средние ставки\n"
                base += "• Чек-колл к агрессии на опасных бордах\n"
            else:
                base += "❌ **Винрейт низкий** - скорее всего уже позади\n"
                base += "**Действия:**\n"
                base += "• Чек-fold или fold к крупным ставкам\n"
                base += "• Только cheap showdown\n"
            
            base += f"\n• {num_opponents} оппонентов: "
            if num_opponents >= 3:
                base += "Multiway - высок риск флеша/стрита у кого-то\n"
            else:
                base += "Heads-up - можете играть агрессивнее\n"
        
        # Две пары
        else:  # two_pair
            base += "🎴 **Две пары**\n"
            
            if texture.get('paired'):
                base += "⚠️ Парный борд - возможны старшие две пары/трипс/фулл-хаус\n\n"
            else:
                base += "✅ Хорошая рука на непарном борде\n\n"
            
            # Опасности
            dangers = []
            if texture.get('monotone'):
                dangers.append("флеш")
            if texture.get('coordinated'):
                dangers.append("стрит")
            if texture.get('paired'):
                dangers.append("фулл-хаус/трипс")
            
            if dangers:
                base += f"⚠️ **Возможные опасности**: {', '.join(dangers)}\n\n"
            
            # Ауты на улучшение
            if total_outs >= 4:
                base += f"🎯 {total_outs} аутов на фулл-хаус!\n"
                base += "• При агрессии оппонента - есть шанс переехать\n\n"
            
            if win_rate >= 65:
                base += "✅ **Винрейт отличный** - агрессивная игра\n"
                base += "**Действия:**\n"
                base += "• Bet для value на всех улицах\n"
                base += "• Защита от дро обязательна\n"
            elif win_rate >= 50:
                base += "✅ **Винрейт хороший** - играем на value\n"
                base += "**Действия:**\n"
                base += "• Средние ставки для value\n"
                base += "• Осторожность на опасных ривах\n"
            else:
                base += "⚠️ **Винрейт низкий** - pot control\n"
                base += "**Действия:**\n"
                base += "• Чек-колл малых ставок\n"
                base += "• Fold к агрессии на флешевых/стритовых борах\n"
            
            if stage == GameStage.RIVER:
                base += "\n📌 **На ривере:**\n"
                if texture.get('monotone') or texture.get('coordinated'):
                    base += "• Опасный борд завершился - только чек-колл малых ставок\n"
                else:
                    base += "• Сухой борд - value bet 50-60% pot\n"
        
        base += "\n" + self._add_opponent_behavior_advice(**{
            "агрессивен": "Чек-колл или чек-рейз если уверены в преимуществе",
            "пассивен": "Value bet - возьмёт с младшими парами",
            "тайтов": "Малые ставки - платит только с реальными руками"
        })
        
        return base

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
        """GTO-улучшенная версия для средних рук"""
        base_rec = self._recommend_medium(hand_type, win_rate, texture, num_opponents, stage, texture_match, total_outs)

        gto_addon = "\n\n" + "="*50 + "\n**📊 GTO АНАЛИЗ:**\n" + "="*50 + "\n"
        sizing = self._get_bet_sizing_advice("value" if win_rate >= 55 else "protection")
        gto_addon += f"• **Размер ставки**: {sizing}\n"

        if self.spr:
            gto_addon += f"• **SPR**: {self.spr:.1f}\n"
        if self.position:
            gto_addon += f"• **Позиция**: {self.position}\n"
        if self.pot_size:
            gto_addon += f"• **Банк**: {self.pot_size} фишек\n"

        stack_warning = self._check_stack_depth_warning()
        if stack_warning:
            gto_addon += f"• {stack_warning}\n"

        # Упрощенное действие
        if win_rate >= 60:
            situation = f"{hand_type} (хороший винрейт {win_rate:.0f}%)"
            action = f"bet {sizing} для value"
        elif win_rate >= 45:
            situation = f"{hand_type} (средний винрейт)"
            action = f"bet {sizing} или чек-колл"
        else:
            situation = f"слабый {hand_type}"
            action = "pot control или fold к агрессии"

        simplified = "\n\n" + self._get_simplified_action(situation, action)
        return base_rec + gto_addon + simplified

    # ===================== WEAK MADE HANDS =====================

    def _recommend_weak_made(
        self,
        hand_type: str,
        win_rate: float,
        texture: Dict,
        num_opponents: int,
        stage: GameStage,
        total_outs: int,
        outs_breakdown: Dict
    ) -> str:
        """Рекомендации для слабых готовых рук (одна пара)"""
        
        base = "⚠️ **СЛАБАЯ ГОТОВАЯ РУКА**\n\n"
        base += "🃏 **Одна пара**\n"
        
        # Оценка опасности борда
        danger_level = 0
        dangers = []
        
        if texture.get('monotone'):
            danger_level += 3
            dangers.append("монотонный борд (флеш)")
        elif texture.get('flush_draw'):
            danger_level += 2
            dangers.append("флеш-дро на борде")
        
        if texture.get('coordinated'):
            danger_level += 2
            dangers.append("координированный борд (стриты)")
        
        if texture.get('paired'):
            danger_level += 2
            dangers.append("парный борд (трипсы)")
        
        if dangers:
            base += f"⚠️ **ОПАСНОСТИ** ({danger_level}/10): {', '.join(dangers)}\n\n"
        else:
            base += "✅ Сухой борд - ваша пара может быть лучшей\n\n"
        
        # Ауты на улучшение
        if total_outs >= 5:
            base += f"🎯 {total_outs} аутов на улучшение:\n"
            if outs_breakdown.get('set_trips', 0) >= 2:
                base += f"  • {outs_breakdown['set_trips']} аутов на сет\n"
            if outs_breakdown.get('two_pair', 0) >= 3:
                base += f"  • Ауты на две пары\n"
            base += "• Можно продолжать розыгрыш при хороших pot odds\n\n"
        
        # Рекомендации по винрейту
        if win_rate >= 70:
            base += "✅ **Винрейт высокий** (likely top pair) - играем агрессивно!\n"
            base += "**Действия:**\n"
            base += "• Bet для value и защиты от дро\n"
            base += "• На терне/ривере: продолжаем bet если нет флеша/стрита\n"
            
        elif win_rate >= 55:
            base += "✅ **Винрейт хороший** - играем на value осторожно\n"
            base += "**Действия:**\n"
            base += "• Малые/средние ставки для value\n"
            base += "• Чек-колл к малой агрессии\n"
            base += "• Fold к крупным ставкам на опасных бордах\n"
            
        elif win_rate >= 40:
            base += "⚠️ **Винрейт средний** - pot control\n"
            base += "**Действия:**\n"
            base += "• Чек-колл малых ставок\n"
            base += "• Fold к агрессии\n"
            base += "• Cheap showdown если возможно\n"
            
        else:
            base += "❌ **Винрейт низкий** - вероятно уже позади\n"
            base += "**Действия:**\n"
            base += "• Чек-fold\n"
            base += "• Fold к любым ставкам\n"
            base += "• Bluff-catcher только в специальных ситуациях\n"
        
        # Мультивей vs heads-up
        base += f"\n• **{num_opponents} оппонентов**: "
        if num_opponents >= 4:
            base += "Multiway - одна пара очень слаба, играйте крайне осторожно\n"
        elif num_opponents >= 2:
            base += "3-way - осторожная игра, кто-то может иметь лучше\n"
        else:
            base += "Heads-up - можете блефкэтчить с хорошей парой\n"
        
        # Стадия игры
        if stage == GameStage.FLOP:
            base += "\n📌 **На флопе**: Оцените реакцию оппонентов перед инвестициями\n"
        elif stage == GameStage.TURN:
            base += "\n📌 **На терне**: Переоценивайте с каждой новой картой\n"
        elif stage == GameStage.RIVER:
            base += "\n📌 **На ривере**: "
            if danger_level >= 5:
                base += "Опасный борд завершился - bluff-catcher только с топ-парой\n"
            else:
                base += "Сухой борд - можете получить value с хорошей парой\n"
        
        base += "\n" + self._add_positional_advice(
            "Можете блефкэтчить с хорошей парой на сухих бордах",
            "Без позиции - играйте fit-or-fold (чек-fold если не улучшились)"
        )
        
        base += "\n" + self._add_opponent_behavior_advice(**{
            "агрессивен": "Bluff-catch с топ-парой, fold с младшими",
            "пассивен": "Малые ставки для value - часто платит с хуже",
            "тайтов": "Чек-fold - ставит только с сильными руками"
        })
        
        return base

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
        """GTO-улучшенная версия для слабых готовых рук"""
        base_rec = self._recommend_weak_made(hand_type, win_rate, texture, num_opponents, stage, total_outs, outs_breakdown)

        gto_addon = "\n\n" + "="*50 + "\n**📊 GTO АНАЛИЗ:**\n" + "="*50 + "\n"

        sizing = self._get_bet_sizing_advice("protection")
        gto_addon += f"• **Размер ставки**: {sizing}\n"

        if self.spr:
            gto_addon += f"• **SPR**: {self.spr:.1f}\n"
            if self.spr < 3:
                gto_addon += "  → Короткий SPR - push/fold территория\n"

        if self.position:
            gto_addon += f"• **Позиция**: {self.position}\n"
            if self.position in ["BTN", "CO"]:
                gto_addon += "  → В позиции: bluff-catching возможен\n"
            else:
                gto_addon += "  → Без позиции: fit-or-fold\n"

        if self.pot_size:
            gto_addon += f"• **Банк**: {self.pot_size} фишек\n"

        stack_warning = self._check_stack_depth_warning()
        if stack_warning:
            gto_addon += f"• {stack_warning}\n"

        # Упрощенное действие
        if win_rate >= 70:
            situation = "топ-пара или оверпара"
            action = f"bet {sizing} для value"
        elif win_rate >= 55:
            situation = "хорошая пара"
            action = "bet или чек-колл"
        elif win_rate >= 40:
            situation = "средняя пара"
            action = "чек-колл или fold к агрессии"
        else:
            situation = "слабая пара"
            action = "чек-fold"

        simplified = "\n\n" + self._get_simplified_action(situation, action)
        return base_rec + gto_addon + simplified

    # ===================== DRAWS =====================

    def _recommend_draw(
        self,
        total_outs: int,
        outs_breakdown: Dict,
        win_rate: float,
        texture: Dict,
        num_opponents: int,
        stage: GameStage
    ) -> str:
        """Рекомендации для дро"""
        
        base = "🎲 **ДРО / НЕТ ГОТОВОЙ КОМБИНАЦИИ**\n\n"
        
        # Классификация дро
        flush_outs = outs_breakdown.get('flush', 0)
        straight_outs = outs_breakdown.get('straight', 0)
        set_outs = outs_breakdown.get('set_trips', 0)
        overcard_outs = outs_breakdown.get('overcard', 0)
        
        # Описание дро
        draw_types = []
        if flush_outs >= 9:
            draw_types.append(f"флеш-дро ({flush_outs} аутов)")
        if straight_outs >= 8:
            draw_types.append(f"стрит-дро ({straight_outs} аутов)")
        if straight_outs >= 4 and straight_outs < 8:
            draw_types.append(f"гатшот ({straight_outs} аутов)")
        if set_outs >= 2:
            draw_types.append(f"пара с аутами на сет ({set_outs} аутов)")
        if overcard_outs >= 3:
            draw_types.append(f"оверкарты ({overcard_outs} аутов)")
        
        if draw_types:
            base += f"**У вас**: {', '.join(draw_types)}\n"
            base += f"**Всего аутов**: {total_outs}\n\n"
        else:
            base += "❌ **Значимых дро не обнаружено**\n\n"
        
        # Рекомендации по количеству аутов
        if total_outs >= 15:
            base += "🚀 **МОНСТР-ДРО** (15+ аутов) - фаворит даже против готовых рук!\n"
            base += "**Действия:**\n"
            base += "• Играйте максимально агрессивно\n"
            base += "• Рейз/3-бет для semi-bluff\n"
            base += "• Можете коллировать all-in на флопе/терне\n"
            base += "• В позиции: рассмотрите чек-рейз\n\n"
            
            base += self._add_positional_advice(
                "Чек-рейз на флопе для максимальной fold equity",
                "Рейз сразу - не давайте дешево увидеть следующую карту"
            )
        
        elif total_outs >= 12:
            base += "⚡ **СИЛЬНОЕ ДРО** (12-14 аутов) - отличные шансы!\n"
            base += "**Действия:**\n"
            base += "• Агрессивная игра оправдана\n"
            base += "• Bet/raise для semi-bluff\n"
            base += "• Коллируйте средние ставки\n"
            base += f"• Против {num_opponents} оппонентов: кто-то может сфолдить лучшую руку\n\n"
            
            if stage == GameStage.FLOP:
                cards_remaining = 2
                base += f"📊 **На флопе**: ~{min(total_outs * 4, 100):.0f}% улучшиться до ривера\n"
            else:
                cards_remaining = 1
                base += f"📊 **На терне**: ~{min(total_outs * 2, 100):.0f}% улучшиться на ривере\n"
        
        elif total_outs >= 9:
            base += "✅ **ХОРОШЕЕ ДРО** (9-11 аутов)\n"
            base += "**Действия:**\n"
            base += "• Коллируйте малые/средние ставки\n"
            base += "• Semi-bluff bet в позиции\n"
            base += "• Проверьте pot odds перед коллом:\n"
            
            if stage == GameStage.FLOP:
                base += f"  - ~{min(total_outs * 4, 100):.0f}% улучшиться до ривера\n"
                base += "  - Нужны pot odds ~2.5:1 для прибыльного колла\n"
            else:
                base += f"  - ~{min(total_outs * 2, 100):.0f}% улучшиться на ривере\n"
                base += "  - Нужны pot odds ~4:1 для прибыльного колла\n"
            
            base += "\n" + self._add_opponent_behavior_advice(**{
                "агрессивен": "Можете semi-bluff рейз если fold equity высокая",
                "пассивен": "Можете красть банк ставкой на терне",
                "тайтов": "Коллируйте и улучшайтесь - они платят с готовыми руками"
            })
        
        elif total_outs >= 6:
            base += "⚠️ **СРЕДНЕЕ ДРО** (6-8 аутов)\n"
            base += "**Действия:**\n"
            base += "• Коллируйте ТОЛЬКО малые ставки\n"
            base += "• Проверяйте pot odds обязательно\n"
            base += "• Fold к средним/крупным ставкам\n"
            
            if stage == GameStage.FLOP:
                base += f"• ~{min(total_outs * 4, 100):.0f}% шанс улучшиться до ривера\n"
            else:
                base += f"• ~{min(total_outs * 2, 100):.0f}% шанс на ривере\n"
                base += "• На терне с 6-8 аутами - нужны pot odds минимум 5:1\n"
            
            base += "\n📌 **Важно**: Не переоценивайте слабые дро!\n"
        
        elif total_outs >= 4:
            base += "🤏 **СЛАБОЕ ДРО** (4-5 аутов)\n"
            base += "**Действия:**\n"
            base += "• Коллируйте только минимальные ставки\n"
            base += "• Fold к любой существенной агрессии\n"
            base += "• Рассмотрите fold даже к малым ставкам без implied odds\n"
            
            if stage == GameStage.FLOP:
                base += f"• Только ~{min(total_outs * 4, 100):.0f}% улучшиться до ривера\n"
            else:
                base += f"• Только ~{min(total_outs * 2, 100):.0f}% попасть на ривере\n"
                base += "• **На терне со слабым дро - чаще всего fold**\n"
        
        elif total_outs >= 1:
            base += "😔 **ОЧЕНЬ СЛАБОЕ ДРО** (1-3 аута)\n"
            base += "**Действия:**\n"
            base += "• Fold к любым ставкам\n"
            base += "• Бесплатная карта - единственный вариант\n"
            base += "• Не инвестируйте в такие дро\n"
        
        else:
            base += "❌ **НЕТ АУТОВ / ВОЗДУХ**\n"
            base += "**Действия:**\n"
            base += "• Fold к любой ставке\n"
            base += "• Чистый блеф - только в специфических ситуациях\n"
            base += "• Не продолжайте без fold equity\n\n"
            
            base += self._add_positional_advice(
                "В позиции можете попробовать steal ставку на страшной карте",
                "Без позиции - чек-fold, блеф не работает"
            )
            
            base += "\n" + self._add_opponent_behavior_advice(**{
                "агрессивен": "Fold немедленно",
                "пассивен": "Можете попытаться украсть на терне/ривере",
                "показал слабость": "Блеф ставка может сработать"
            })
            
            return base
        
        # Анализ винрейта для дро
        if win_rate >= 45:
            base += f"\n✅ **Винрейт {win_rate:.1f}%** - дро имеет хорошие шансы!\n"
        elif win_rate >= 30:
            base += f"\n⚠️ **Винрейт {win_rate:.1f}%** - дро маргинальное\n"
        else:
            base += f"\n❌ **Винрейт {win_rate:.1f}%** - дро слабое, нужны отличные pot odds\n"
        
        # Multiway considerations
        if num_opponents >= 3:
            base += f"\n⚠️ **{num_opponents} оппонентов** (multiway):\n"
            base += "• Implied odds лучше (больше денег в банке при попадании)\n"
            base += "• Fold equity хуже (сложнее выбить всех блефом)\n"
            base += "• Играйте консервативнее - кто-то уже имеет готовую руку\n"
        
        # Стадия игры
        if stage == GameStage.TURN:
            base += "\n⚠️ **ВНИМАНИЕ - ВЫ НА ТЕРНЕ**:\n"
            base += "• Только 1 карта осталась (ривер)\n"
            base += "• Implied odds ухудшились\n"
            base += "• Будьте строже к pot odds\n"
        
        base += "\n" + self._add_positional_advice(
            "В позиции с дро:\n  • Можете контролировать размер банка\n  • Чек-бэк на терне для бесплатной карты\n  • Блеф на ривере если дро промахнулось но пришла страшная карта",
            "Без позиции с дро:\n  • Чек-колл линия обычно оптимальна\n  • Донк-бет только с очень сильным дро (12+ аутов)\n  • Готовьтесь фолдить на терне/ривере к агрессии"
        )
        
        return base

    def _recommend_draw_with_gto(
        self,
        total_outs: int,
        outs_breakdown: Dict,
        win_rate: float,
        texture: Dict,
        num_opponents: int,
        stage: GameStage
    ) -> str:
        """GTO-улучшенная версия для дро"""
        base_rec = self._recommend_draw(total_outs, outs_breakdown, win_rate, texture, num_opponents, stage)

        gto_addon = "\n\n" + "="*50 + "\n**📊 GTO АНАЛИЗ (POT ODDS):**\n" + "="*50 + "\n"

        # Pot odds расчеты
        if self.pot_size:
            gto_addon += f"• **Текущий банк**: {self.pot_size} фишек\n"

            # Пример расчета pot odds для разных размеров ставок
            if total_outs >= 9:
                bet_call = int(self.pot_size * 0.5)  # Предполагаем half-pot bet
                pot_odds = (bet_call / (self.pot_size + bet_call)) * 100 if bet_call > 0 else 0
                equity_needed = pot_odds

                if stage == GameStage.FLOP:
                    draw_equity = min(total_outs * 4, 100)
                else:
                    draw_equity = min(total_outs * 2, 100)

                gto_addon += f"• **При ставке {bet_call} фишек**:\n"
                gto_addon += f"  - Pot odds: {pot_odds:.1f}%\n"
                gto_addon += f"  - Ваше equity: ~{draw_equity:.0f}%\n"

                if draw_equity > equity_needed:
                    gto_addon += f"  → ПРИБЫЛЬНЫЙ КОЛЛ (+EV)\n"
                else:
                    gto_addon += f"  → УБЫТОЧНЫЙ КОЛЛ (-EV)\n"

        # Semi-bluff sizing
        if total_outs >= 12:
            sizing = self._get_bet_sizing_advice("semi-bluff")
            gto_addon += f"• **Semi-bluff размер**: {sizing}\n"

        if self.spr:
            gto_addon += f"• **SPR**: {self.spr:.1f}\n"

        if self.position:
            gto_addon += f"• **Позиция**: {self.position}\n"

        stack_warning = self._check_stack_depth_warning()
        if stack_warning:
            gto_addon += f"• {stack_warning}\n"

        # Упрощенное действие
        if total_outs >= 15:
            situation = "монстр-дро (15+ аутов)"
            action = f"raise/bet агрессивно"
        elif total_outs >= 12:
            situation = "сильное дро (12-14 аутов)"
            action = "bet для semi-bluff или call"
        elif total_outs >= 9:
            situation = "хорошее дро (9-11 аутов)"
            action = "call малые/средние ставки"
        elif total_outs >= 6:
            situation = "среднее дро (6-8 аутов)"
            action = "call только малые ставки"
        elif total_outs >= 4:
            situation = "слабое дро (4-5 аутов)"
            action = "fold к большинству ставок"
        else:
            situation = "нет дро"
            action = "fold или чистый блеф"

        simplified = "\n\n" + self._get_simplified_action(situation, action)
        return base_rec + gto_addon + simplified

    # ===================== HELPER METHODS =====================

    def _add_positional_advice(self, in_position: str, out_of_position: str) -> str:
        """Добавляет позиционные советы"""
        return (
            "┌─────────────────────────────────────┐\n"
            "│ 📍 ПОЗИЦИОННЫЕ СОВЕТЫ (для вас):   │\n"
            "└─────────────────────────────────────┘\n"
            f"🟢 **Если вы В ПОЗИЦИИ** (BTN/CO):\n   {in_position}\n\n"
            f"🔴 **Если вы БЕЗ ПОЗИЦИИ** (UTG/MP/SB/BB):\n   {out_of_position}\n"
        )
    
    def _add_opponent_behavior_advice(self, **behaviors) -> str:
        """Добавляет советы по поведению оппонента"""
        advice = (
            "┌─────────────────────────────────────┐\n"
            "│ 🎭 СОВЕТЫ ПО ОППОНЕНТУ (для вас):  │\n"
            "└─────────────────────────────────────┘\n"
        )
        
        for behavior_type, recommendation in behaviors.items():
            emoji = {
                'агрессивен': '🔥',
                'пассивен': '😴',
                'тайтов': '🛡️',
                'на тильте': '😤',
                'показал слабость': '😰'
            }.get(behavior_type, '👤')
            
            advice += f"{emoji} **Если оппонент {behavior_type}**:\n   {recommendation}\n\n"
        
        return advice.rstrip()


# ===================== INTEGRATION FUNCTION =====================

def generate_improved_recommendation(analysis_result: Dict) -> str:
    """
    Главная функция для интеграции в analysis_service.py
    
    Usage:
        from improved_abc_recommendations import generate_improved_recommendation
        
        recommendation = generate_improved_recommendation(analysis_result)
    """
    engine = ImprovedRecommendationEngine()
    
    # Extract data from analysis result
    current_hand = analysis_result.get('current_hand', 'high card')
    equity_data = analysis_result.get('equity', {})
    win_rate = equity_data.get('win_rate', 0)
    
    outs_data = analysis_result.get('outs_analysis', {})
    total_outs = analysis_result.get('total_outs', 0)
    
    texture_analysis = analysis_result.get('board_texture', {})
    
    # Get game state data (you'll need to pass this)
    # These should come from the GameState object
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
