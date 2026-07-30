"""Main application window - Refactored with service layer - COMPLETE"""
import json
import logging
from pathlib import Path
from typing import Optional, List
import numpy as np
import cv2
from utils.global_hotkeys import get_hotkey_manager

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QGroupBox, QScrollArea, QMessageBox,
                               QRadioButton, QButtonGroup, QSizePolicy, QProgressBar)
from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import QImage, QPixmap

from core.domain import Card, GameState, GameStage, TableSize, GameType
from services.ml_service import MLService
from services.analysis_service import AnalysisService
from ui.widgets import CardInputWidget, SelectionOverlay
from ui.ml_worker import MLWorker
from utils.screen_capture import ScreenCapture

logger = logging.getLogger(__name__)


class MainWindow(QWidget):
    """Main application window with clean separation of concerns"""

    def __init__(self, ml_service: MLService, analysis_service: AnalysisService):
        super().__init__()
        self.ml_service = ml_service
        self.analysis_service = analysis_service
        self.screen_capture = ScreenCapture()

        # ML Worker Thread for async processing
        self.ml_worker = MLWorker(ml_service)
        self.ml_worker.detection_complete.connect(self._on_detection_complete)
        self.ml_worker.detection_failed.connect(self._on_detection_failed)

        self.roi: Optional[QRect] = None
        self.captured_frame: Optional[np.ndarray] = None
        self.game_state = GameState(
            table_size=TableSize.SIX_MAX,
            game_type=GameType.CASH,
            stage=GameStage.PREFLOP,
            player_cards=[],
            board_cards=[]
        )



        self.setup_ui()
        self.load_roi()
        self.load_roi()

        self.analysis_timer = QTimer(self)
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.timeout.connect(self.analyze_situation)
        self.hotkey_manager = get_hotkey_manager()
    
        if self.hotkey_manager.is_available():
            # Connect signals
            self.hotkey_manager.numpad_pressed.connect(self._on_hotkey_opponent_select)
            self.hotkey_manager.enter_pressed.connect(self._on_hotkey_capture)
            
            # Register hotkeys
            self.hotkey_manager.register_hotkeys()
            logger.info("✅ Global hotkeys enabled")
        else:
            logger.warning("⚠️  Global hotkeys not available (install: pip install keyboard)")
    
    def setup_ui(self):
        """Setup user interface"""
        self.setWindowTitle("💜 MonteLab - Refactored 💜")
        self.setGeometry(100, 100, 1000, 700)
        self.setMinimumSize(800, 600)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        main_layout = QVBoxLayout(self)
        
        title = QLabel("MonteLab - Advanced Poker Analysis (Refactored)")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #4CAF50; padding: 15px;")
        main_layout.addWidget(title)
        
        controls = self._create_controls()
        main_layout.addLayout(controls)
        
        self.game_state_label = QLabel("Current Mode: 6-Max Cash | Stage: Preflop")
        self.game_state_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #81C784; padding: 8px;")
        main_layout.addWidget(self.game_state_label)
        
        content = self._create_content_area()
        main_layout.addLayout(content, 1)
        
        self.status_label = QLabel("Ready - Configure and analyze")
        self.status_label.setStyleSheet("color: #888; padding: 8px; background-color: #222; border-radius: 4px;")
        main_layout.addWidget(self.status_label)
    
    def _create_controls(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        
        self.select_roi_btn = QPushButton("🎯 Select Area")
        self.capture_btn = QPushButton("📸 Capture")
        self.analyze_btn = QPushButton("🧠 Analyze")
        
        self.capture_btn.setEnabled(False)
        
        # Apply individual styling with colors
        self.select_roi_btn.setStyleSheet("padding: 8px 15px; font-weight: bold; background-color: #FF9800;")
        self.capture_btn.setStyleSheet("padding: 8px 15px; font-weight: bold; background-color: #2196F3;")
        self.analyze_btn.setStyleSheet("padding: 8px 15px; font-weight: bold; background-color: #4CAF50;")
        
        self.select_roi_btn.clicked.connect(self.select_roi)
        self.capture_btn.clicked.connect(self.capture_and_detect)
        self.analyze_btn.clicked.connect(self.analyze_situation)
        
        layout.addWidget(self.select_roi_btn)
        layout.addWidget(self.capture_btn)
        layout.addWidget(self.analyze_btn)
        layout.addStretch()
        
        return layout
    
    def _create_content_area(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(15)
        
        table_config = self._create_table_config()
        layout.addWidget(table_config)
        
        cards_column = self._create_cards_column()
        layout.addLayout(cards_column)
        
        analysis_frame = self._create_analysis_frame()
        layout.addWidget(analysis_frame, 1)

        # Правая колонка: Image
        right_column = QVBoxLayout()
        image_frame = self._create_image_frame()
        right_column.addWidget(image_frame, 1)
        layout.addLayout(right_column)

        return layout
    
    def _create_table_config(self) -> QGroupBox:
        frame = QGroupBox("Table Configuration")
        frame.setFixedWidth(180)
        
        layout = QVBoxLayout(frame)
        layout.setSpacing(4)
        
        self.table_size_group = QButtonGroup()
        table_sizes = [
            ("2_players", "2 Players", TableSize.HEADS_UP),
            ("3_players", "3 Players", TableSize.THREE_MAX),
            ("4_players", "4 Players", TableSize.FOUR_MAX),
            ("5_players", "5 Players", TableSize.FIVE_MAX),
            ("6_players", "6 Players", TableSize.SIX_MAX),
            ("7_players", "7 Players", TableSize.SEVEN_MAX),
            ("8_players", "8 Players", TableSize.EIGHT_MAX),
            ("9_players", "9 Players", TableSize.NINE_MAX)
        ]
        
        for btn_id, label, size in table_sizes:
            btn = QRadioButton(label)
            btn.setProperty("table_size", size)
            btn.setStyleSheet("font-size: 11px; padding: 2px;")
            
            if btn_id == "6_players":
                btn.setChecked(True)
            
            self.table_size_group.addButton(btn)
            layout.addWidget(btn)
        
        layout.addStretch()
        self.table_size_group.buttonClicked.connect(self.on_table_config_changed)
        
        return frame
    
    def _create_cards_column(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        player_cards_frame = QGroupBox("Player Cards")
        player_cards_frame.setFixedWidth(280)
        player_cards_layout = QVBoxLayout(player_cards_frame)
        player_cards_layout.setSpacing(8)
        
        self.card1_widget = CardInputWidget("Card 1:")
        self.card2_widget = CardInputWidget("Card 2:")
        
        for widget in [self.card1_widget, self.card2_widget]:
            widget.label.setFixedWidth(70)
            widget.line_edit.setFixedWidth(45)
            for btn in widget.suit_buttons:
                btn.setFixedSize(30, 30)
        
        player_cards_layout.addWidget(self.card1_widget)
        player_cards_layout.addWidget(self.card2_widget)
        
        board_cards_frame = QGroupBox("Board Cards")
        board_cards_frame.setFixedWidth(280)
        board_cards_layout = QVBoxLayout(board_cards_frame)
        board_cards_layout.setSpacing(6)
        
        self.flop1_widget = CardInputWidget("Flop 1:")
        self.flop2_widget = CardInputWidget("Flop 2:")
        self.flop3_widget = CardInputWidget("Flop 3:")
        self.turn_widget = CardInputWidget("Turn:")
        self.river_widget = CardInputWidget("River:")
        
        for widget in [self.flop1_widget, self.flop2_widget, self.flop3_widget,
                      self.turn_widget, self.river_widget]:
            widget.label.setFixedWidth(70)
            widget.line_edit.setFixedWidth(45)
            for btn in widget.suit_buttons:
                btn.setFixedSize(30, 30)
        
        board_cards_layout.addWidget(self.flop1_widget)
        board_cards_layout.addWidget(self.flop2_widget)
        board_cards_layout.addWidget(self.flop3_widget)
        board_cards_layout.addWidget(self.turn_widget)
        board_cards_layout.addWidget(self.river_widget)
        
        layout.addWidget(player_cards_frame)
        layout.addWidget(board_cards_frame)
        layout.addStretch()
        
        for widget in [self.card1_widget, self.card2_widget, 
                      self.flop1_widget, self.flop2_widget, self.flop3_widget,
                      self.turn_widget, self.river_widget]:
            widget.line_edit.textChanged.connect(self.on_cards_changed)
        
        return layout
    
    def _create_analysis_frame(self) -> QGroupBox:
        frame = QGroupBox("Poker Analysis")
        frame.setMinimumWidth(350)
        
        layout = QVBoxLayout(frame)
        
        self.analysis_scroll = QScrollArea()
        self.analysis_content = QWidget()
        self.analysis_layout = QVBoxLayout(self.analysis_content)
        
        self.analysis_scroll.setWidget(self.analysis_content)
        self.analysis_scroll.setWidgetResizable(True)
        
        layout.addWidget(self.analysis_scroll, 1)
        
        self.create_default_analysis()
        
        return frame
    
    def _create_image_frame(self) -> QGroupBox:
        frame = QGroupBox("Captured Image")
        frame.setMinimumWidth(300)
        
        layout = QVBoxLayout(frame)
        
        self.image_label = QLabel("Select area and capture\ntable to detect cards\nautomatically")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(280, 300)
        self.image_label.setStyleSheet("""
            background: #111; color: #ccc; border: 2px solid #444; 
            border-radius: 4px; font-size: 14px; padding: 15px;
        """)
        
        layout.addWidget(self.image_label, 1)

        return frame



    def create_default_analysis(self):
        while self.analysis_layout.count():
            child = self.analysis_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        welcome_label = QLabel("🃏 Welcome to MonteLab")
        welcome_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #4CAF50; padding: 15px;")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        instructions = QLabel("""
        <b>Instructions:</b><br>
        1. Select table configuration<br>
        2. Enter player cards and board cards<br>
        3. OR use ML detection by capturing area<br>
        4. Click 'Analyze' for comprehensive analysis<br><br>
        
        <b>Features:</b><br>
        • Postflop hand strength evaluation<br>
        • Board texture analysis<br>
        • Outs calculations<br>
        • Stage-specific strategy advice
        """)
        instructions.setStyleSheet("color: #ccc; padding: 20px; line-height: 1.6;")
        instructions.setWordWrap(True)
        
        self.analysis_layout.addWidget(welcome_label)
        self.analysis_layout.addWidget(instructions)
        self.analysis_layout.addStretch()
    
    def on_table_config_changed(self):
        checked_btn = self.table_size_group.checkedButton()
        if checked_btn:
            table_size = checked_btn.property("table_size")
            self.game_state.table_size = table_size
            self.update_game_state_display()
            
            if self.has_player_cards():
                self.analyze_situation()
    
    def on_cards_changed(self):
        board_cards = self.get_board_cards()
        self.game_state.board_cards = board_cards
        self.game_state.stage = self._determine_stage(board_cards)
        
        self.update_game_state_display()
        
        if self.has_player_cards():
            self.analysis_timer.stop()
            self.analysis_timer.start(300)
    
    def update_game_state_display(self):
        players_count = self.game_state.get_players_count()
        stage_name = self.game_state.stage.value
        board_count = len(self.game_state.board_cards)
        
        display_text = f"Table: {players_count} Players | Stage: {stage_name} ({board_count} cards)"
        self.game_state_label.setText(display_text)
    
    def has_player_cards(self) -> bool:
        card1 = self.card1_widget.get_text().strip()
        card2 = self.card2_widget.get_text().strip()
        return bool(card1 and card2)
    
    def get_player_cards(self) -> List[Card]:
        cards = []
        for widget in [self.card1_widget, self.card2_widget]:
            text = widget.get_text().strip()
            if text:
                card = Card.parse(text)
                if card:
                    cards.append(card)
        return cards
    
    def get_board_cards(self) -> List[Card]:
        cards = []
        for widget in [self.flop1_widget, self.flop2_widget, self.flop3_widget, 
                      self.turn_widget, self.river_widget]:
            text = widget.get_text().strip()
            if text:
                card = Card.parse(text)
                if card:
                    cards.append(card)
        return cards
    
    def _determine_stage(self, board_cards: List[Card]) -> GameStage:
        num_board = len(board_cards)
        stage_map = {
            0: GameStage.PREFLOP,
            3: GameStage.FLOP,
            4: GameStage.TURN,
            5: GameStage.RIVER
        }
        return stage_map.get(num_board, GameStage.PREFLOP)
    
    def select_roi(self):
        logger.info("ROI selection started")
        try:
            overlay = SelectionOverlay(self)
            overlay.show()
            
            result = overlay.exec()
            
            if result == overlay.DialogCode.Accepted:
                rect = overlay.selected_rect()
                
                if rect and rect.width() > 50 and rect.height() > 50:
                    self.roi = rect
                    self.save_roi()
                    self.capture_btn.setEnabled(True)
                    self.status_label.setText(
                        f"✅ Selected area: {rect.width()}×{rect.height()} at ({rect.x()}, {rect.y()})"
                    )
                    logger.info(f"ROI saved: {rect.width()}x{rect.height()}")
                else:
                    QMessageBox.warning(self, "Selection Too Small", 
                                      "Please select larger area (min 50×50)")
            
        except Exception as e:
            logger.error(f"ROI selection error: {e}", exc_info=True)
            QMessageBox.critical(self, "Selection Error", f"Failed to select region: {e}")
    
    def capture_and_detect(self):
        if not self.roi:
            QMessageBox.warning(self, "No Area", "Please select capture area first")
            return

        self.status_label.setText("📸 Capturing and analyzing...")

        try:
            frame = self.screen_capture.grab_roi(self.roi)
            if frame is None:
                QMessageBox.warning(self, "Capture Failed", "Failed to capture screenshot")
                self.status_label.setText("❌ Capture failed")
                return

            self.captured_frame = frame.copy()
            self.display_frame(frame)

            # Run ML card detection
            if self.ml_service.is_available:
                self.status_label.setText("🔍 Analyzing cards with ML...")
                self._detect_and_fill_cards(frame)
            else:
                self.status_label.setText("📷 Picture captured - ML not available, enter cards manually")

        except Exception as e:
            logger.error(f"Capture error: {e}", exc_info=True)
            QMessageBox.critical(self, "Capture Error", f"Failed to capture: {e}")
            self.status_label.setText("❌ Capture error")
    

    
    def _detect_and_fill_cards(self, frame: np.ndarray):
        """Start async ML detection in background thread (non-blocking)"""
        try:
            # Check if worker is already running
            if self.ml_worker.isRunning():
                logger.warning("ML worker already processing, skipping...")
                return

            # Start async detection
            self.ml_worker.set_frame(frame.copy(), confidence_threshold=0.4)
            self.ml_worker.start()

        except Exception as e:
            logger.error(f"Failed to start ML worker: {e}", exc_info=True)
            self.status_label.setText(f"❌ ML error: {e}")

    def _on_detection_complete(self, player_cards: List, board_cards: List):
        """Handle detection results from worker thread (runs on main thread)"""
        try:
            if self.captured_frame is None:
                return

            # Draw overlay on captured frame
            overlay_frame = self.captured_frame.copy()

            for detection in player_cards:
                x1, y1, x2, y2 = detection.bbox
                cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(overlay_frame, f"P: {detection.classification}", (x1, y1-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            for detection in board_cards:
                x1, y1, x2, y2 = detection.bbox
                cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                cv2.putText(overlay_frame, f"B: {detection.classification}", (x1, y1-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

            self.display_frame(overlay_frame)

            # Fill card widgets
            if len(player_cards) >= 1:
                self.card1_widget.set_text(player_cards[0].classification or "")
            if len(player_cards) >= 2:
                self.card2_widget.set_text(player_cards[1].classification or "")

            board_widgets = [self.flop1_widget, self.flop2_widget, self.flop3_widget,
                           self.turn_widget, self.river_widget]

            for i, widget in enumerate(board_widgets):
                if i < len(board_cards):
                    widget.set_text(board_cards[i].classification or "")
                else:
                    widget.clear()

            if len(player_cards) >= 2:
                self.analyze_situation()

            self.status_label.setText(
                f"✅ Detected: {len(player_cards)} player, {len(board_cards)} board cards"
            )

        except Exception as e:
            logger.error(f"Error processing detection results: {e}", exc_info=True)
            self.status_label.setText(f"❌ Error: {e}")

    def _on_detection_failed(self, error_message: str):
        """Handle detection failure from worker thread"""
        logger.error(f"ML detection failed: {error_message}")
        self.status_label.setText(f"❌ Detection failed: {error_message}")
    
    def display_frame(self, frame: np.ndarray):
        try:
            if len(frame.shape) == 3:
                height, width, channel = frame.shape
                bytes_per_line = 3 * width
                q_image = QImage(frame.data, width, height, bytes_per_line, 
                               QImage.Format.Format_RGB888).rgbSwapped()
            else:
                height, width = frame.shape
                bytes_per_line = width
                q_image = QImage(frame.data, width, height, bytes_per_line, 
                               QImage.Format.Format_Grayscale8)
            
            pixmap = QPixmap.fromImage(q_image)
            scaled_pixmap = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
        
        except Exception as e:
            logger.error(f"Display error: {e}")
    


    def analyze_situation(self):
        if not self.has_player_cards():
            QMessageBox.warning(self, "Input Error", "Please enter both player cards")
            return

        try:
            player_cards = self.get_player_cards()
            board_cards = self.get_board_cards()

            if len(player_cards) != 2:
                QMessageBox.warning(self, "Invalid Cards", "Please enter valid player cards")
                return

            # Обновление game state картами
            self.game_state.player_cards = player_cards
            self.game_state.board_cards = board_cards
            self.game_state.stage = self._determine_stage(board_cards)

            self.update_game_state_display()

            self.update_game_state_display()

            # Analysis with detailed game state
            analysis_result = self.analysis_service.analyze_hand(self.game_state)

            if "error" in analysis_result:
                QMessageBox.warning(self, "Analysis Error", analysis_result["error"])
            else:
                self._display_analysis_result(analysis_result)

            self.status_label.setText("✅ Analysis complete")

        except Exception as e:
            logger.error(f"Analysis error: {e}", exc_info=True)
            QMessageBox.critical(self, "Analysis Error", f"Failed to analyze: {e}")
    
    def _display_analysis_result(self, result: dict):
        while self.analysis_layout.count():
            child = self.analysis_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        stage = result.get("stage", "")
        
        cards_display = " ".join(str(c) for c in self.game_state.player_cards)
        board_display = " ".join(str(c) for c in self.game_state.board_cards) if self.game_state.board_cards else "No board"
        
        title = QLabel(f"Hand Analysis — {stage.upper()}")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #4CAF50; padding: 10px;")
        
        cards_label = QLabel(f"Player: {cards_display} | Board: {board_display}")
        cards_label.setStyleSheet("font-size: 16px; color: #81C784; padding: 8px; font-weight: bold;")
        
        self.analysis_layout.addWidget(title)
        self.analysis_layout.addWidget(cards_label)
        
        if "current_hand" in result:
            strength_group = QGroupBox("Hand Evaluation")
            strength_layout = QVBoxLayout(strength_group)
            
            current_hand_label = QLabel(f"Current Combination: {result['current_hand'].title()}")
            current_hand_label.setStyleSheet("font-size: 16px; color: #fff; padding: 8px; font-weight: bold;")
            strength_layout.addWidget(current_hand_label)
            
            outs_data = result.get("outs_analysis", {})
            total_outs = result.get("total_outs", 0)
            
            if total_outs >= 0:
                outs_text = f"🎯 OUTS ANALYSIS:\n"
                outs_text += f"• Flush: {outs_data.get('flush', 0)} outs\n"
                outs_text += f"• Straight: {outs_data.get('straight', 0)} outs\n"
                outs_text += f"• Set/Trips: {outs_data.get('set_trips', 0)} outs\n"
                outs_text += f"• Overcards: {outs_data.get('overcard', 0)} outs\n"
                outs_text += f"━━━━━━━━━━━━━━━━━━━\n"
                outs_text += f"📊 TOTAL OUTS: {total_outs}\n\n"
                
                cards_to_come = 5 - len(self.game_state.board_cards)
                if cards_to_come == 2:
                    improvement_equity = min(total_outs * 4, 100)
                    stage_text = "to river"
                elif cards_to_come == 1:
                    improvement_equity = min(total_outs * 2, 100)
                    stage_text = "on river"
                else:
                    improvement_equity = 0
                    stage_text = "completed"
                
                outs_text += f"📈 Improvement Odds {stage_text}: {improvement_equity:.2f}%\n"
                
                # Outs summary
                pass
            else:
                outs_text = "❌ No significant draws detected"
            
            outs_label = QLabel(outs_text)
            outs_label.setStyleSheet("font-size: 14px; color: #ccc; padding: 8px; font-family: 'Consolas';")
            outs_label.setWordWrap(True)
            strength_layout.addWidget(outs_label)
            
            self.analysis_layout.addWidget(strength_group)

        # Dedicated Equity (Win / Tie / Lose) Group Box
        equity = result.get("equity", {})
        if "win_rate" in equity and not equity.get("error"):
            equity_group = QGroupBox("🏆 Win Odds (Monte Carlo Equity)")
            equity_layout = QVBoxLayout(equity_group)
            equity_layout.setSpacing(6)
            
            win = float(equity.get("win_rate", 0.0))
            tie = float(equity.get("tie_rate", 0.0))
            lose = float(equity.get("lose_rate", max(0.0, 100.0 - win - tie)))
            
            stats = [
                ("Win", win, "#4CAF50"),
                ("Tie", tie, "#FFEB3B"),
                ("Lose", lose, "#F44336")
            ]
            
            for label_str, val, color in stats:
                row = QHBoxLayout()
                lbl = QLabel(f"{label_str}: {val:.2f}%")
                lbl.setFixedWidth(140)
                lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #fff;")
                
                pbar = QProgressBar()
                pbar.setRange(0, 1000)
                pbar.setValue(int(val * 10))
                pbar.setTextVisible(False)
                pbar.setFixedHeight(12)
                pbar.setStyleSheet(f"""
                    QProgressBar {{
                        background-color: #222;
                        border: 1px solid #444;
                        border-radius: 4px;
                    }}
                    QProgressBar::chunk {{
                        background-color: {color};
                        border-radius: 3px;
                    }}
                """)
                
                row.addWidget(lbl)
                row.addWidget(pbar, 1)
                equity_layout.addLayout(row)
                
            self.analysis_layout.addWidget(equity_group)
        
        texture = result.get("board_texture", {})
        if texture and "error" not in texture:
            texture_group = QGroupBox("Board Texture")
            texture_layout = QVBoxLayout(texture_group)
            
            features = []
            if texture.get('monotone'):
                features.append("🔴 Monotone")
            elif texture.get('two_tone'):
                features.append("🟡 Two-tone")
            elif texture.get('rainbow'):
                features.append("🌈 Rainbow")
            
            if texture.get('paired'):
                features.append("👥 Paired")
            
            if texture.get('coordinated'):
                features.append("🔗 Coordinated")
            elif texture.get('dry'):
                features.append("🏜️ Dry")
            
            if texture.get('flush_draw'):
                features.append("💧 Flush Draw")
            
            texture_text = "Characteristics:\n" + "\n".join(f"• {f}" for f in features) if features else "Standard"
            
            texture_label = QLabel(texture_text)
            texture_label.setStyleSheet("font-size: 14px; color: #ccc; padding: 8px;")
            texture_label.setWordWrap(True)
            texture_layout.addWidget(texture_label)
            
            self.analysis_layout.addWidget(texture_group)
        
        strategy = result.get("strategy_recommendation", "")
        if strategy:
            recommendations_group = QGroupBox("💡 ABC Strategy & Tactical Advisor")
            recommendations_layout = QVBoxLayout(recommendations_group)
            
            strategy_label = QLabel(strategy)
            strategy_label.setTextFormat(Qt.TextFormat.MarkdownText)
            strategy_label.setStyleSheet("""
                font-size: 13px; 
                color: #E6EE9C; 
                padding: 12px; 
                border: 2px solid #DCE775; 
                border-radius: 8px; 
                background-color: rgba(30, 40, 20, 0.4);
                line-height: 1.5;
            """)
            strategy_label.setWordWrap(True)
            recommendations_layout.addWidget(strategy_label)
            
            self.analysis_layout.addWidget(recommendations_group)
        
        self.analysis_layout.addStretch()
    
    def save_roi(self):
        if self.roi:
            roi_data = [self.roi.x(), self.roi.y(), self.roi.width(), self.roi.height()]
            config_data = {"roi": roi_data}
            try:
                config_file = Path(__file__).parent.parent.parent / "gui_config.json"
                with open(config_file, 'w') as f:
                    json.dump(config_data, f, indent=2)
                logger.info(f"ROI saved: {roi_data}")
            except Exception as e:
                logger.error(f"Failed to save ROI: {e}")
    
    def load_roi(self):
        config_file = Path(__file__).parent.parent.parent / "gui_config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                roi_data = data.get('roi')
                if roi_data and len(roi_data) == 4:
                    self.roi = QRect(*roi_data)
                    self.capture_btn.setEnabled(True)
                    self.status_label.setText(f"📁 Loaded saved area: {roi_data[2]}×{roi_data[3]}")
            except Exception as e:
                logger.warning(f"Failed to load ROI: {e}")





    def clear_all_inputs(self):
        """Clear all card input widgets"""
        self.card1_widget.clear()
        self.card2_widget.clear()
        self.flop1_widget.clear()
        self.flop2_widget.clear()
        self.flop3_widget.clear()
        self.turn_widget.clear()
        self.river_widget.clear()
        
        self.game_state.player_cards = []
        self.game_state.board_cards = []
        self.game_state.stage = GameStage.PREFLOP
        
        self.update_game_state_display()
        self.create_default_analysis()
        self.status_label.setText("🔄 All inputs cleared")
        logger.info("All inputs cleared")

    def _on_hotkey_opponent_select(self, number: int):
        """Handle numpad hotkey for opponent selection"""
        logger.info(f"HANDLER: Setting {number} opponents via hotkey")
        
        try:
            from core.domain import TableSize
            
            # Маппинг: количество оппонентов -> TableSize
            opponents_to_table_size = {
                1: TableSize.HEADS_UP,      # 1 оппонент
                2: TableSize.THREE_MAX,     # 2 оппонента
                3: TableSize.FOUR_MAX,      # 3 оппонента
                4: TableSize.FIVE_MAX,      # 4 оппонента
                5: TableSize.SIX_MAX,       # 5 оппонентов
                6: TableSize.SEVEN_MAX,     # 6 оппонентов
                7: TableSize.EIGHT_MAX,     # 7 оппонентов
                8: TableSize.NINE_MAX,      # 8 оппонентов
            }
            
            if number not in opponents_to_table_size:
                logger.warning(f"HANDLER: Invalid opponent count: {number} (must be 1-8)")
                return
            
            if hasattr(self, 'game_state'):
                new_table_size = opponents_to_table_size[number]
                old_table_size = self.game_state.table_size
                
                self.game_state.table_size = new_table_size
                
                logger.info(f"HANDLER: SUCCESS! Changed table_size: {old_table_size} -> {new_table_size}")
                logger.info(f"HANDLER: Opponents: {self.game_state.get_opponents_count()}")
                
                # Обновляем UI - передаём table_size как аргумент
                if hasattr(self, 'on_table_size_changed'):
                    self.on_table_size_changed(new_table_size)
                    logger.info("HANDLER: Called on_table_size_changed()")
                
                if hasattr(self, 'update_game_state_display'):
                    self.update_game_state_display()
                    logger.info("HANDLER: Called update_game_state_display()")
                
                # Если есть карты - пересчитываем анализ
                if hasattr(self, 'has_player_cards') and self.has_player_cards():
                    if hasattr(self, 'analyze_situation'):
                        self.analyze_situation()
                        logger.info("HANDLER: Called analyze_situation()")
            else:
                logger.error("HANDLER: game_state not found!")
                
        except Exception as e:
            logger.error(f"HANDLER: Exception: {e}", exc_info=True)


    def _on_hotkey_capture(self):
        """Handle Enter hotkey for capture"""
        logger.info("HANDLER: Capture hotkey pressed")
        
        try:
            from PySide6.QtWidgets import QPushButton
            
            # Вариант 1: capture_action
            if hasattr(self, 'capture_action'):
                logger.info("HANDLER: Found capture_action")
                self.capture_action.trigger()
                logger.info("HANDLER: SUCCESS! capture_action triggered")
                return
            
            # Вариант 2: capture_and_detect метод
            if hasattr(self, 'capture_and_detect'):
                logger.info("HANDLER: Found capture_and_detect method")
                self.capture_and_detect()
                logger.info("HANDLER: SUCCESS! capture_and_detect called")
                return
            
            # Вариант 3: select_roi метод
            if hasattr(self, 'select_roi'):
                logger.info("HANDLER: Found select_roi method")
                self.select_roi()
                logger.info("HANDLER: SUCCESS! select_roi called")
                return
            
            # Вариант 4: поиск кнопки
            all_buttons = self.findChildren(QPushButton)
            logger.info(f"HANDLER: Searching through {len(all_buttons)} buttons")
            
            for btn in all_buttons:
                btn_text = btn.text().lower()
                btn_name = btn.objectName().lower()
                
                if ('capture' in btn_text or 'capture' in btn_name or 
                    'grab' in btn_text or 'screen' in btn_text):
                    logger.info(f"HANDLER: Found button: '{btn.text()}' ({btn.objectName()})")
                    if btn.isEnabled():
                        btn.click()
                        logger.info("HANDLER: SUCCESS! Button clicked")
                        return
            
            logger.error("HANDLER: Could not trigger capture!")
            
        except Exception as e:
            logger.error(f"HANDLER: Exception: {e}", exc_info=True)   




    def closeEvent(self, event):
        logger.info("Application closing")
        event.accept()

