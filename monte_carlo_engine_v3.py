# monte_carlo_engine_v3.py - УЛУЧШЕННЫЙ ДЕМОН С ВАЛИДАЦИЕЙ
"""
Оптимизированный Monte Carlo движок с персистентным процессом.
УЛУЧШЕНИЯ:
- Валидация JSON результата
- Timeout на readline с retry логикой
- Автоматический fallback на Legacy при проблемах
- Защита от неполных результатов
"""

import subprocess
import logging
import os
import json
import threading
import atexit
import time
from typing import List, Dict, Optional
from pathlib import Path
from core.domain import Card

logger = logging.getLogger(__name__)


class MonteCarloEngineDaemon:
    """Оптимизированный Monte Carlo движок с персистентным процессом"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton - только один instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        project_root = Path(__file__).parent
        self.executable_path = project_root / "MonteCarlo-Poker-master" / "MonteCarloPoker.exe"
        
        if not self.executable_path.exists():
            raise FileNotFoundError(f"C++ Monte Carlo executable not found: {self.executable_path}")
        
        lookup_table = self.executable_path.parent / "lookup_tablev3.bin"
        if not lookup_table.exists():
            raise FileNotFoundError(f"Lookup table not found: {lookup_table}")
        
        self.process = None
        self.process_lock = threading.Lock()
        
        self.call_count = 0
        self.daemon_call_count = 0  # ✅ НОВОЕ: счётчик успешных daemon вызовов
        self.legacy_fallback_count = 0  # ✅ НОВОЕ: счётчик fallback на legacy
        self.total_time = 0.0
        self.daemon_mode = False
        
        try:
            self._start_daemon_process()
            self.daemon_mode = True
            logger.info("="*60)
            logger.info("🚀 DAEMON MODE ENABLED!")
            logger.info(f"⚡ Process PID: {self.process.pid}")
            logger.info(f"📚 Lookup table loaded ONCE - ready for FAST calculations")
            logger.info("="*60)
        except Exception as e:
            logger.warning(f"Failed to start daemon mode: {e}")
            logger.info("Falling back to LEGACY mode (slower)")
            self.daemon_mode = False
        
        atexit.register(self.cleanup)
        
        self._initialized = True
    
    def _start_daemon_process(self):
        """Start persistent C++ daemon process"""
        with self.process_lock:
            if self.process is not None:
                logger.warning("Terminating old daemon process...")
                self._terminate_process()
            
            try:
                self.process = subprocess.Popen(
                    [str(self.executable_path), "--daemon"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    cwd=self.executable_path.parent,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                logger.info(f"Daemon process started: PID {self.process.pid}")
                
                ready = False
                timeout = 5
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    if self.process.poll() is not None:
                        raise RuntimeError(f"Daemon process died immediately (code: {self.process.poll()})")
                    
                    try:
                        ready_signal = self.process.stdout.readline().strip()
                        if ready_signal == "READY":
                            ready = True
                            break
                        elif ready_signal:
                            logger.debug(f"Daemon output: {ready_signal}")
                    except:
                        time.sleep(0.1)
                
                if not ready:
                    raise RuntimeError("Daemon didn't send READY signal within timeout")
                
                logger.info("✅ Daemon is READY (lookup table loaded)")
                
            except Exception as e:
                logger.error(f"Failed to start daemon process: {e}")
                if self.process:
                    self._terminate_process()
                raise
    
    def _terminate_process(self):
        """Safely terminate daemon process"""
        if self.process is None:
            return
        
        try:
            if self.process.poll() is not None:
                return  # Already dead
                
            try:
                self.process.stdin.write("EXIT\n")
                self.process.stdin.flush()
                self.process.wait(timeout=2)
                logger.info("Daemon process terminated gracefully")
            except:
                self.process.kill()
                logger.warning("Daemon process force killed")
        except:
            pass
        finally:
            self.process = None
    
    def cleanup(self):
        """Cleanup on application exit"""
        logger.info("="*60)
        logger.info("📊 Monte Carlo Daemon Statistics:")
        logger.info(f"   Mode: {'DAEMON' if self.daemon_mode else 'LEGACY'}")
        logger.info(f"   Total calculations: {self.call_count}")
        logger.info(f"   Daemon calculations: {self.daemon_call_count}")
        logger.info(f"   Legacy fallbacks: {self.legacy_fallback_count}")
        if self.call_count > 0:
            avg_time = self.total_time / self.call_count
            logger.info(f"   Average time: {avg_time:.3f}s per calculation")
        logger.info("🛑 Shutting down Monte Carlo daemon...")
        logger.info("="*60)
        self._terminate_process()
    
    def _convert_card_to_cpp_format(self, card: Card) -> str:
        """Convert Card object to C++ format (rank+suit)"""
        return f"{card.rank}{card.suit}"
    
    def _validate_unique_cards(self, hole_cards: List[Card], board_cards: List[Card]) -> bool:
        """Validate that all cards are unique"""
        all_cards = hole_cards + board_cards
        card_strings = [self._convert_card_to_cpp_format(card) for card in all_cards]
        
        if len(card_strings) != len(set(card_strings)):
            duplicates = [card for card in card_strings if card_strings.count(card) > 1]
            logger.error(f"❌ Duplicate cards detected: {duplicates}")
            return False
        
        return True
    
    def _validate_result(self, result: Dict) -> bool:
        """
        ✅ ПРАКТИКА 1: Валидация JSON результата
        Проверяет, что результат содержит все необходимые поля
        Добавлен tolerance для floating point погрешностей
        """
        required_fields = ['win_rate', 'tie_rate', 'lose_rate']
        
        for field in required_fields:
            if field not in result:
                logger.error(f"❌ Incomplete result: missing '{field}'. Got: {list(result.keys())}")
                return False
        
        # Проверка валидности значений
        try:
            win = float(result['win_rate'])
            tie = float(result['tie_rate'])
            lose = float(result['lose_rate'])
            
            # ✅ ИСПРАВЛЕНИЕ: Добавлен tolerance для floating point ошибок
            # Значения от -0.01 до 0 считаем нулём (машинная погрешность)
            EPSILON = 0.01
            corrected = False
            
            # Округляем near-zero отрицательные значения до 0
            if -EPSILON <= win < 0:
                logger.debug(f"Correcting floating point error: win_rate {win} → 0.0")
                result['win_rate'] = 0.0
                win = 0.0
                corrected = True
            if -EPSILON <= tie < 0:
                logger.debug(f"Correcting floating point error: tie_rate {tie} → 0.0")
                result['tie_rate'] = 0.0
                tie = 0.0
                corrected = True
            if -EPSILON <= lose < 0:
                logger.debug(f"Correcting floating point error: lose_rate {lose} → 0.0")
                result['lose_rate'] = 0.0
                lose = 0.0
                corrected = True
            
            if corrected:
                logger.info("✅ Floating point precision corrected")
            
            # Строгая проверка диапазонов (после коррекции)
            if not (0 <= win <= 100 and 0 <= tie <= 100 and 0 <= lose <= 100):
                logger.error(f"❌ Invalid percentages: win={win}, tie={tie}, lose={lose}")
                return False
            
            # Проверка суммы (с tolerance для округления)
            total = win + tie + lose
            if not (99 <= total <= 101):  # Допускаем небольшую погрешность округления
                logger.error(f"❌ Percentages don't sum to ~100: total={total}")
                return False
                
        except (ValueError, TypeError) as e:
            logger.error(f"❌ Invalid numeric values in result: {e}")
            return False
        
        return True
    
    def calculate_equity(self, hole_cards: List[Card], board_cards: List[Card],
                        opponents: int = 1, iterations: int = 100000) -> Dict[str, float]:
        """Calculate equity using daemon (if available) or legacy mode"""
        start_time = time.time()
        
        # Валидация входных данных
        if len(hole_cards) != 2:
            return {'error': 'Need exactly 2 hole cards'}
        
        if len(board_cards) > 5:
            return {'error': 'Board cannot have more than 5 cards'}
        
        if opponents < 1 or opponents > 8:
            return {'error': 'Opponents must be between 1-8'}
        
        if not self._validate_unique_cards(hole_cards, board_cards):
            return {'error': 'Duplicate cards detected'}
        
        # Попытка расчёта через daemon
        if self.daemon_mode and self.process:
            result = self._calculate_daemon(hole_cards, board_cards, opponents, iterations)
        else:
            result = self._calculate_legacy(hole_cards, board_cards, opponents, iterations)
        
        # ✅ УЛУЧШЕНИЕ: Безопасное логирование с проверкой win_rate
        if 'error' not in result:
            elapsed = time.time() - start_time
            self.call_count += 1
            self.total_time += elapsed
            
            mode = "DAEMON" if self.daemon_mode else "LEGACY"
            
            # Безопасное извлечение win_rate
            if 'win_rate' in result:
                logger.info(f"✅ {mode} calculation #{self.call_count}: {result['win_rate']:.2f}% win (took {elapsed:.3f}s)")
            else:
                logger.warning(f"⚠️ {mode} calculation #{self.call_count}: incomplete result (took {elapsed:.3f}s)")
        else:
            logger.error(f"❌ Calculation failed: {result.get('error', 'Unknown error')}")
        
        return result
    
    def _calculate_daemon(self, hole_cards: List[Card], board_cards: List[Card],
                         opponents: int, iterations: int) -> Dict[str, float]:
        """
        ✅ УЛУЧШЕННЫЙ: Calculate using daemon process с валидацией и fallback
        """
        
        with self.process_lock:
            try:
                # Проверка что процесс жив
                if self.process.poll() is not None:
                    logger.warning("⚠️ Daemon process died, falling back to legacy")
                    self.daemon_mode = False
                    self.legacy_fallback_count += 1
                    return self._calculate_legacy(hole_cards, board_cards, opponents, iterations)
                
                # Подготовка команды
                hole_cpp = [self._convert_card_to_cpp_format(card) for card in hole_cards]
                board_cpp = [self._convert_card_to_cpp_format(card) for card in board_cards]
                
                board_str = ','.join(board_cpp) if board_cpp else ''
                hole_str = ','.join(hole_cpp)
                
                command = f"CALC {board_str}|{hole_str}|{opponents}|{iterations}\n"
                logger.debug(f"Sending to daemon: {command.strip()}")
                
                # Отправка команды
                self.process.stdin.write(command)
                self.process.stdin.flush()
                
                # ✅ ПРАКТИКА 2: Улучшенный timeout на readline
                result_line = None
                read_timeout = 5.0  # Сокращённый timeout для daemon (должен быть быстрым)
                start_time = time.time()
                retry_count = 0
                max_retries = 3
                
                while time.time() - start_time < read_timeout and retry_count < max_retries:
                    try:
                        # Проверяем что процесс ещё жив
                        if self.process.poll() is not None:
                            raise RuntimeError("Daemon process died during calculation")
                        
                        result_line = self.process.stdout.readline().strip()
                        
                        if result_line:
                            logger.debug(f"Received from daemon: {result_line[:100]}...")
                            break
                        
                        retry_count += 1
                        time.sleep(0.01)  # Небольшая задержка перед retry
                        
                    except Exception as e:
                        logger.warning(f"Read attempt {retry_count + 1} failed: {e}")
                        retry_count += 1
                        time.sleep(0.05)
                
                if not result_line:
                    raise RuntimeError(f"Daemon returned empty result after {retry_count} retries (timeout: {read_timeout}s)")
                
                # Парсинг JSON
                try:
                    result = json.loads(result_line)
                    logger.debug(f"Parsed JSON keys: {list(result.keys())}")
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Failed to parse JSON: {e}")
                    logger.error(f"Raw output: {result_line}")
                    raise
                
                # ✅ ИСПРАВЛЕНИЕ: Игнорируем маркер и читаем реальный результат
                if 'marker' in result and 'win_rate' not in result:
                    logger.info("✅ Received daemon marker, reading actual result...")
                    
                    # Читаем следующую строку с реальным результатом
                    result_line = None
                    retry_count = 0
                    start_time = time.time()
                    
                    while time.time() - start_time < read_timeout and retry_count < max_retries:
                        try:
                            if self.process.poll() is not None:
                                raise RuntimeError("Daemon process died during calculation")
                            
                            result_line = self.process.stdout.readline().strip()
                            
                            if result_line:
                                logger.debug(f"Received actual result: {result_line[:100]}...")
                                break
                            
                            retry_count += 1
                            time.sleep(0.01)
                            
                        except Exception as e:
                            logger.warning(f"Read attempt {retry_count + 1} failed: {e}")
                            retry_count += 1
                            time.sleep(0.05)
                    
                    if not result_line:
                        raise RuntimeError(f"Daemon returned empty result after marker (timeout: {read_timeout}s)")
                    
                    # Парсим реальный результат
                    try:
                        result = json.loads(result_line)
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Failed to parse actual result JSON: {e}")
                        logger.error(f"Raw output: {result_line}")
                        raise
                
                # ✅ ПРАКТИКА 1: Валидация результата
                if not self._validate_result(result):
                    logger.warning("⚠️ Daemon returned invalid result, falling back to legacy")
                    self.daemon_mode = False  # Временно отключаем daemon
                    self.legacy_fallback_count += 1
                    return self._calculate_legacy(hole_cards, board_cards, opponents, iterations)
                
                # Добавляем метаданные
                result['simulations_completed'] = iterations
                result['calculation_mode'] = 'daemon'
                
                self.daemon_call_count += 1
                logger.info(f"⚡ DAEMON calculation successful: {result['win_rate']:.2f}% win, {result['tie_rate']:.2f}% tie, {result['lose_rate']:.2f}% lose")
                return result
                
            except json.JSONDecodeError as e:
                # ✅ ПРАКТИКА 3: Fallback на Legacy при ошибке парсинга
                logger.error(f"❌ Failed to parse daemon result: {result_line if 'result_line' in locals() else 'N/A'}")
                logger.warning("⚠️ Falling back to legacy mode for this calculation")
                self.legacy_fallback_count += 1
                return self._calculate_legacy(hole_cards, board_cards, opponents, iterations)
                
            except RuntimeError as e:
                # ✅ ПРАКТИКА 3: Fallback на Legacy при timeout или смерти процесса
                logger.error(f"❌ Daemon error: {e}")
                logger.warning("⚠️ Falling back to legacy mode for this calculation")
                self.daemon_mode = False  # Отключаем daemon полностью
                self.legacy_fallback_count += 1
                return self._calculate_legacy(hole_cards, board_cards, opponents, iterations)
                
            except Exception as e:
                # ✅ ПРАКТИКА 3: Универсальный fallback
                logger.error(f"❌ Unexpected daemon error: {e}", exc_info=True)
                logger.warning("⚠️ Falling back to legacy mode for this calculation")
                self.daemon_mode = False
                self.legacy_fallback_count += 1
                return self._calculate_legacy(hole_cards, board_cards, opponents, iterations)
    
    def _calculate_legacy(self, hole_cards: List[Card], board_cards: List[Card],
                         opponents: int, iterations: int) -> Dict[str, float]:
        """Calculate using legacy subprocess.run() - SLOW but RELIABLE"""
        
        try:
            hole_cpp = [self._convert_card_to_cpp_format(card) for card in hole_cards]
            board_cpp = [self._convert_card_to_cpp_format(card) for card in board_cards]
            
            board_str = ','.join(board_cpp) if board_cpp else ''
            known_hands_str = ','.join(hole_cpp)
            
            cmd = [
                str(self.executable_path),
                board_str,
                known_hands_str,
                str(opponents)
            ]
            
            logger.debug(f"Running legacy: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.executable_path.parent,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            stdout = result.stdout.strip()
            
            if stdout:
                parsed_result = self._parse_text_output(stdout, iterations)
                parsed_result['calculation_mode'] = 'legacy'
                return parsed_result
            
            return {'error': f'No valid results (code: {result.returncode})'}
            
        except subprocess.TimeoutExpired:
            logger.error("❌ C++ simulation timeout (60s)")
            return {'error': 'Simulation timeout'}
        except Exception as e:
            logger.error(f"❌ Legacy calculation error: {e}", exc_info=True)
            return {'error': f'Calculation error: {e}'}
    
    def _parse_text_output(self, output: str, total_sims: int = 100000) -> Dict[str, float]:
        """Parse text output from C++ program (legacy format) - НАДЁЖНЫЙ"""
        import re
        
        try:
            lines = output.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('??') or 'Win %' in line or 'Hand' in line:
                    continue
                
                # Ищем все числа с плавающей точкой
                numbers = re.findall(r'\d+\.\d+', line)
                if len(numbers) >= 2:
                    win_rate = float(numbers[0])
                    tie_rate = float(numbers[1])
                    
                    # Валидация диапазона
                    if 0 <= win_rate <= 100 and 0 <= tie_rate <= 100:
                        lose_rate = max(0, 100.0 - win_rate - tie_rate)
                        
                        return {
                            'win_rate': round(win_rate, 2),
                            'tie_rate': round(tie_rate, 2),
                            'lose_rate': round(lose_rate, 2),
                            'simulations_completed': total_sims
                        }
            
            logger.error(f"❌ No parseable results in output:\n{output}")
            return {'error': 'Could not parse results'}
            
        except Exception as e:
            logger.error(f"❌ Parse error: {e}", exc_info=True)
            return {'error': f'Parse error: {e}'}