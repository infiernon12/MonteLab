"""
Table Data - Стол-дата для покерного анализа

Содержит:
- PlayerInfo: информация об игроке (стек, ставка, позиция)
- TableData: полные данные стола для анализа
- BlindDetector: детектор блайндов для определения позиций

Алгоритм работы:
1. Stacks and bets are collected (e.g. via manual input)
2. BlindDetector определяет BB/SB по ставкам на префлопе
3. Позиции раздаются относительно BB
4. Данные сохраняются в JSON для дальнейшего анализа
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Position(Enum):
    """Позиции игроков за столом"""
    BB = "BB"       # Big Blind
    SB = "SB"       # Small Blind
    BTN = "BTN"     # Button (Dealer)
    CO = "CO"       # Cut-off
    HJ = "HJ"       # Hijack
    MP = "MP"       # Middle Position
    MP1 = "MP+1"    # Middle Position +1
    UTG1 = "UTG+1"  # Under the Gun +1
    UTG = "UTG"     # Under the Gun


# Порядок позиций от BB против часовой стрелки (действие идёт слева направо)
POSITION_ORDER_BY_PLAYERS = {
    2: [Position.BB, Position.BTN],  # BTN = SB в хедз-апе
    3: [Position.BB, Position.SB, Position.BTN],
    4: [Position.BB, Position.SB, Position.BTN, Position.CO],
    5: [Position.BB, Position.SB, Position.BTN, Position.CO, Position.HJ],
    6: [Position.BB, Position.SB, Position.BTN, Position.CO, Position.HJ, Position.MP],
    7: [Position.BB, Position.SB, Position.BTN, Position.CO, Position.HJ, Position.MP, Position.UTG],
    8: [Position.BB, Position.SB, Position.BTN, Position.CO, Position.HJ, Position.MP, Position.MP1, Position.UTG],
    9: [Position.BB, Position.SB, Position.BTN, Position.CO, Position.HJ, Position.MP, Position.MP1, Position.UTG1, Position.UTG]
}


@dataclass
class PlayerInfo:
    """Информация об игроке"""
    id: int                            # Индекс зоны (1-9)
    stack: Optional[float] = None      # Текущий стек (None = N/A - игрок отсутствует)
    bet: float = 0.0                   # Текущая ставка в раунде
    position: Optional[str] = None     # Позиция (BTN, SB, BB, UTG...)
    is_hero: bool = False              # Это наш игрок (пользователь)
    is_active: bool = True             # Игрок в игре (не фолднул)
    
    def is_present(self) -> bool:
        """Игрок присутствует за столом (имеет стек)"""
        return self.stack is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "id": self.id,
            "stack": self.stack,
            "bet": self.bet,
            "position": self.position,
            "is_hero": self.is_hero,
            "is_active": self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerInfo':
        """Создание из словаря"""
        return cls(
            id=data.get("id", 0),
            stack=data.get("stack"),
            bet=data.get("bet", 0.0),
            position=data.get("position"),
            is_hero=data.get("is_hero", False),
            is_active=data.get("is_active", True)
        )


@dataclass 
class TableData:
    """Полные данные стола (Стол-дата)"""
    
    # Карты
    hero_cards: List[str] = field(default_factory=list)      # ["Ah", "Kd"]
    community_cards: List[str] = field(default_factory=list) # Карты на столе
    
    # Банк и ставки
    total_pot: float = 0.0             # Общий размер банка
    
    # Игроки
    players: List[PlayerInfo] = field(default_factory=list)
    
    # Блайнды
    big_blind: float = 0.0             # Размер BB
    small_blind: float = 0.0           # Размер SB
    
    # Метаданные
    hand_id: int = 0                   # ID раздачи
    is_preflop: bool = True            # Префлоп стадия
    positions_detected: bool = False   # Позиции определены
    
    def get_hero(self) -> Optional[PlayerInfo]:
        """Получить данные героя"""
        for player in self.players:
            if player.is_hero:
                return player
        return None
    
    def get_active_players(self) -> List[PlayerInfo]:
        """Получить активных игроков (присутствующих за столом)"""
        return [p for p in self.players if p.is_present()]
    
    def get_active_player_count(self) -> int:
        """Количество активных игроков"""
        return len(self.get_active_players())
    
    def get_bb_player(self) -> Optional[PlayerInfo]:
        """Найти игрока на BB"""
        for player in self.players:
            if player.position == Position.BB.value:
                return player
        return None
    
    def get_sb_player(self) -> Optional[PlayerInfo]:
        """Найти игрока на SB"""
        for player in self.players:
            if player.position == Position.SB.value:
                return player
        return None
    
    def get_max_bet(self) -> float:
        """Максимальная ставка за столом"""
        if not self.players:
            return 0.0
        return max((p.bet for p in self.players if p.is_present()), default=0.0)
    
    def get_hero_to_call(self) -> float:
        """Сколько герою нужно доплатить для колла"""
        hero = self.get_hero()
        if not hero:
            return 0.0
        return max(0.0, self.get_max_bet() - hero.bet)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в JSON-совместимый словарь"""
        return {
            "hero_cards": self.hero_cards,
            "community_cards": self.community_cards,
            "total_pot": self.total_pot,
            "players": [p.to_dict() for p in self.players],
            "big_blind": self.big_blind,
            "small_blind": self.small_blind,
            "hand_id": self.hand_id,
            "is_preflop": self.is_preflop,
            "positions_detected": self.positions_detected
        }
    
    def to_json(self, pretty: bool = True) -> str:
        """Сериализация в JSON строку"""
        indent = 2 if pretty else None
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TableData':
        """Создание из словаря"""
        players = [PlayerInfo.from_dict(p) for p in data.get("players", [])]
        return cls(
            hero_cards=data.get("hero_cards", []),
            community_cards=data.get("community_cards", []),
            total_pot=data.get("total_pot", 0.0),
            players=players,
            big_blind=data.get("big_blind", 0.0),
            small_blind=data.get("small_blind", 0.0),
            hand_id=data.get("hand_id", 0),
            is_preflop=data.get("is_preflop", True),
            positions_detected=data.get("positions_detected", False)
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'TableData':
        """Десериализация из JSON строки"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def save_to_file(self, filepath: str = "table_data.json") -> bool:
        """Сохранение в файл"""
        try:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.to_json())
            
            logger.info(f"TableData saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save TableData: {e}")
            return False
    
    @classmethod
    def load_from_file(cls, filepath: str = "table_data.json") -> Optional['TableData']:
        """Загрузка из файла"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return cls.from_json(f.read())
        except Exception as e:
            logger.error(f"Failed to load TableData: {e}")
            return None


class BlindDetector:
    """
    Детектор блайндов для определения позиций игроков.
    
    Алгоритм:
    1. На префлопе анализируются ставки всех игроков
    2. Ставок должно быть 2 (SB и BB)
    3. Большая ставка = BB, меньшая = SB
    4. Позиции раздаются относительно BB по часовой стрелке
    """
    
    def __init__(self):
        self.last_detected_bb_index: Optional[int] = None
        self.last_detected_sb_index: Optional[int] = None
    
    def detect_blinds(self, players: List[PlayerInfo]) -> tuple:
        """
        Определить позиции блайндов по ставкам.
        
        Args:
            players: Список всех игроков с их ставками
            
        Returns:
            Tuple (bb_index, sb_index, bb_amount, sb_amount)
            Индексы - относительные среди активных игроков
        """
        # Фильтруем только активных игроков (с стеками)
        active_players = [p for p in players if p.is_present()]
        
        if len(active_players) < 2:
            logger.warning("Not enough active players to detect blinds")
            return None, None, 0, 0
        
        # Находим игроков со ставками
        players_with_bets = [(i, p) for i, p in enumerate(active_players) if p.bet > 0]
        
        if len(players_with_bets) < 2:
            logger.warning(f"Found only {len(players_with_bets)} players with bets, need 2")
            return None, None, 0, 0
        
        # Сортируем по размеру ставки (убывание)
        players_with_bets.sort(key=lambda x: x[1].bet, reverse=True)
        
        # BB = максимальная ставка, SB = следующая по размеру
        bb_idx, bb_player = players_with_bets[0]
        sb_idx, sb_player = players_with_bets[1]
        
        bb_amount = bb_player.bet
        sb_amount = sb_player.bet
        
        # Валидация: BB должен быть в 2 раза больше SB (с допуском)
        expected_ratio = 2.0
        actual_ratio = bb_amount / sb_amount if sb_amount > 0 else 0
        
        if not (1.8 <= actual_ratio <= 2.2):
            logger.warning(f"Unusual blind ratio: BB={bb_amount}, SB={sb_amount}, ratio={actual_ratio:.2f}")
        
        self.last_detected_bb_index = bb_idx
        self.last_detected_sb_index = sb_idx
        
        logger.info(f"Blinds detected: BB={bb_amount} (index {bb_idx}), SB={sb_amount} (index {sb_idx})")
        
        return bb_idx, sb_idx, bb_amount, sb_amount
    
    def assign_positions(self, players: List[PlayerInfo], bb_index_in_active: int) -> List[PlayerInfo]:
        """
        Раздать позиции игрокам относительно BB.
        
        Позиции раздаются против часовой стрелки от BB:
        BB -> SB -> BTN -> CO -> HJ -> MP -> UTG...
        
        Индексы игроков идут по часовой стрелке, поэтому:
        - BB на индексе bb_index
        - SB на индексе (bb_index - 1) % num_active
        - BTN на индексе (bb_index - 2) % num_active
        - и т.д.
        
        Args:
            players: Список всех игроков (включая пустые места)
            bb_index_in_active: Индекс BB среди активных игроков
            
        Returns:
            Обновленный список игроков с позициями
        """
        # Получаем активных игроков
        active_players = [p for p in players if p.is_present()]
        num_active = len(active_players)
        
        if num_active < 2 or num_active > 9:
            logger.warning(f"Invalid number of active players: {num_active}")
            return players
        
        # Получаем порядок позиций для данного количества игроков
        position_order = POSITION_ORDER_BY_PLAYERS.get(num_active)
        if not position_order:
            logger.error(f"No position order for {num_active} players")
            return players
        
        # Раздаем позиции, начиная с BB
        # Формула: offset = (bb_index - i) % num_active
        # Это даёт: BB(индекс bb) -> SB(bb-1) -> BTN(bb-2) -> ...
        for i, player in enumerate(active_players):
            # Вычисляем смещение от BB (против часовой стрелки)
            offset = (bb_index_in_active - i) % num_active
            position = position_order[offset]
            player.position = position.value
        
        logger.info(f"Positions assigned to {num_active} active players")
        for p in active_players:
            logger.info(f"  Player {p.id}: {p.position} (stack={p.stack}, bet={p.bet})")
        
        return players
    
    def detect_and_assign(self, players: List[PlayerInfo]) -> List[PlayerInfo]:
        """
        Полный цикл: определить блайнды и раздать позиции.
        
        Args:
            players: Список игроков с заполненными стеками и ставками
            
        Returns:
            Список игроков с присвоенными позициями
        """
        bb_idx, sb_idx, bb_amount, sb_amount = self.detect_blinds(players)
        
        if bb_idx is None:
            logger.error("Failed to detect blinds")
            return players
        
        return self.assign_positions(players, bb_idx)


class TableDataCollector:
    """
    Коллектор стол-даты.
    
    Отвечает за:
    - Data collection from game state
    - Определение позиций (Новый старт)
    - Обновление позиций при выходе игроков (Анализ)
    - Сохранение/загрузка TableData
    """
    
    def __init__(self):
        self.current_data: Optional[TableData] = None
        self.blind_detector = BlindDetector()
        self.data_filepath = "session_data/table_data.json"
    
    def new_hand_start(self, 
                       stacks: List[Optional[float]], 
                       bets: List[float],
                       pot: float,
                       hero_cards: List[str] = None,
                       hero_index: int = 0) -> TableData:
        """
        Новый старт - определение блайндов и позиций для новой раздачи.
        
        Вызывается кнопкой "Новый старт" в интерфейсе.
        
        Args:
            stacks: Список стеков (None = игрок отсутствует)
            bets: Список ставок
            pot: Размер банка
            hero_cards: Карты героя ["Ah", "Kd"]
            hero_index: Индекс героя (по умолчанию 0)
            
        Returns:
            TableData с определенными позициями
        """
        # Создаем игроков
        players = []
        for i, (stack, bet) in enumerate(zip(stacks, bets)):
            player = PlayerInfo(
                id=i + 1,  # 1-based индексация
                stack=stack,
                bet=bet,
                is_hero=(i == hero_index)
            )
            players.append(player)
        
        # Определяем блайнды и позиции
        players = self.blind_detector.detect_and_assign(players)
        
        # Извлекаем размеры блайндов
        bb_player = next((p for p in players if p.position == Position.BB.value), None)
        sb_player = next((p for p in players if p.position == Position.SB.value), None)
        
        bb_amount = bb_player.bet if bb_player else 0.0
        sb_amount = sb_player.bet if sb_player else 0.0
        
        # Создаем TableData
        self.current_data = TableData(
            hero_cards=hero_cards or [],
            community_cards=[],
            total_pot=pot,
            players=players,
            big_blind=bb_amount,
            small_blind=sb_amount,
            hand_id=(self.current_data.hand_id + 1) if self.current_data else 1,
            is_preflop=True,
            positions_detected=True
        )
        
        # Сохраняем
        self.current_data.save_to_file(self.data_filepath)
        
        logger.info(f"New hand started: {self.current_data.get_active_player_count()} players")
        
        return self.current_data
    
    def analyze_current(self,
                        stacks: List[Optional[float]],
                        bets: List[float],
                        pot: float,
                        community_cards: List[str] = None) -> TableData:
        """
        Анализ текущей ситуации без повторного определения блайндов.
        
        Вызывается кнопкой "Анализ" в интерфейсе.
        Позиции НЕ пересчитываются, но обновляются если игрок вышел.
        
        Args:
            stacks: Текущие стеки
            bets: Текущие ставки  
            pot: Размер банка
            community_cards: Карты на столе
            
        Returns:
            Обновленная TableData
        """
        if not self.current_data or not self.current_data.positions_detected:
            logger.warning("No positions detected, running new_hand_start")
            return self.new_hand_start(stacks, bets, pot)
        
        # Обновляем данные игроков, сохраняя позиции
        for i, (stack, bet) in enumerate(zip(stacks, bets)):
            if i < len(self.current_data.players):
                player = self.current_data.players[i]
                
                old_stack = player.stack
                player.stack = stack
                player.bet = bet
                
                # Если стек стал None - игрок вышел
                if old_stack is not None and stack is None:
                    player.is_active = False
                    logger.info(f"Player {player.id} ({player.position}) left the table")
        
        # Обновляем банк и карты
        self.current_data.total_pot = pot
        if community_cards:
            self.current_data.community_cards = community_cards
            self.current_data.is_preflop = len(community_cards) == 0
        
        # Сохраняем
        self.current_data.save_to_file(self.data_filepath)
        
        logger.info(f"Table analyzed: pot={pot}, active players={self.current_data.get_active_player_count()}")
        
        return self.current_data
    
    def load_session(self) -> Optional[TableData]:
        """Загрузить данные последней сессии"""
        self.current_data = TableData.load_from_file(self.data_filepath)
        return self.current_data
    
    def get_current_data(self) -> Optional[TableData]:
        """Получить текущие данные"""
        return self.current_data
