"""Adaptive main window with dockable panels - Fully responsive UI"""
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import numpy as np
import cv2
from utils.global_hotkeys import get_hotkey_manager

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QMessageBox, QToolBar, 
                               QStatusBar, QSizePolicy, QMenu, QGroupBox, QScrollArea, QProgressBar)
from PySide6.QtCore import Qt, QRect, QTimer, QSize
from PySide6.QtGui import QImage, QPixmap, QAction, QIcon

from core.domain import Card, GameState, GameStage, TableSize, GameType
from core.domain import TableData, PlayerInfo, TableDataCollector, DecisionEngine
from services.ml_service import MLService
from services.analysis_service import AnalysisService
from ui.dock_widgets import (TableConfigDock, CardsDock, ImagePreviewDock)

from ui.widgets import SelectionOverlay
from ui.ml_worker import MLWorker
from ui.ui_config import UIConfigManager, WindowGeometry, DockState
from utils.screen_capture import ScreenCapture

logger = logging.getLogger(__name__)


class AdaptiveMainWindow(QMainWindow):
    """
    Adaptive main window with dockable panels.
    
    Features:
    - Dockable/floatable panels
    - Persistent UI state (geometry, dock positions)
    - Responsive layout
    - Multi-monitor support
    """
    
    def __init__(self, ml_service: MLService, analysis_service: AnalysisService):
        super().__init__()

        # Services
        self.ml_service = ml_service
        self.analysis_service = analysis_service
        self.screen_capture = ScreenCapture()

        # ML Worker Thread for async processing
        self.ml_worker = MLWorker(ml_service)
        self.ml_worker.detection_complete.connect(self._on_detection_complete)
        self.ml_worker.detection_failed.connect(self._on_detection_failed)

        # UI Config Manager
        self.ui_config_manager = UIConfigManager()

        # State
        self.roi: Optional[QRect] = None
        self.captured_frame: Optional[np.ndarray] = None
        self.game_state = GameState(
            table_size=TableSize.SIX_MAX,
            game_type=GameType.CASH,
            stage=GameStage.PREFLOP,
            player_cards=[],
            board_cards=[]
        )

        # Dock widgets
        self.table_config_dock: Optional[TableConfigDock] = None
        self.cards_dock: Optional[CardsDock] = None
        self.image_preview_dock: Optional[ImagePreviewDock] = None
        
        # Table Data Collector и Decision Engine
        self.table_data_collector = TableDataCollector()
        self.decision_engine = DecisionEngine()

        # UI Components (analysis is now in central widget)
        self.game_state_label: Optional[QLabel] = None
        self.analysis_scroll: Optional[QScrollArea] = None
        self.analysis_content: Optional[QWidget] = None
        self.analysis_layout: Optional[QVBoxLayout] = None


        # Timer for debounced analysis
        self.analysis_timer = QTimer(self)
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.timeout.connect(self.analyze_situation)

        # Setup
        self.setup_ui()
        self.load_ui_state()
        self.load_roi()

        
        logger.info("Adaptive main window initialized")
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
        """Setup complete user interface"""
        self.setWindowTitle("💜 MonteLab - Adaptive UI 💜")
        
        # Set default geometry to match original (will be overridden by saved state)
        self.setGeometry(100, 100, 1000, 700)
        # Minimal constraints - allow aggressive shrinking when panels are floating
        self.setMinimumSize(400, 300)
        
        # Create central widget
        self._create_central_widget()
        
        # Create toolbar
        self._create_toolbar()
        
        # Create dock widgets
        self._create_dock_widgets()
        
        # Create status bar
        self._create_status_bar()
        
        # Setup menu bar
        self._create_menu_bar()
        
        logger.info("UI setup complete")
    
    def _create_central_widget(self):
        """Create central widget with integrated analysis area"""
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Title
        title = QLabel("MonteLab - Advanced Poker Analysis")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size: 20px; 
            font-weight: bold; 
            color: #4CAF50; 
            padding: 12px;
            background-color: #1a1a1a;
            border-radius: 6px;
        """)
        layout.addWidget(title)
        
        # Game state display
        self.game_state_label = QLabel("Current Mode: 6-Max Cash | Stage: Preflop")
        self.game_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.game_state_label.setStyleSheet("""
            font-size: 14px; 
            font-weight: bold; 
            color: #81C784; 
            padding: 10px;
            background-color: #1a1a1a;
            border-radius: 6px;
        """)
        layout.addWidget(self.game_state_label)
        
        # Integrated Analysis Area (replaces separate dock)
        analysis_group = QGroupBox("🧠 Poker Analysis")
        analysis_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #4CAF50;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 12px;
                background-color: #1e1e1e;
            }
            QGroupBox::title {
                color: #4CAF50;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        analysis_layout = QVBoxLayout(analysis_group)
        analysis_layout.setContentsMargins(8, 8, 8, 8)
        
        # Scrollable analysis content
        self.analysis_scroll = QScrollArea()
        self.analysis_scroll.setWidgetResizable(True)
        self.analysis_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.analysis_content = QWidget()
        self.analysis_layout = QVBoxLayout(self.analysis_content)
        self.analysis_layout.setSpacing(8)
        self.analysis_layout.setContentsMargins(8, 8, 8, 8)
        
        self.analysis_scroll.setWidget(self.analysis_content)
        analysis_layout.addWidget(self.analysis_scroll)
        
        layout.addWidget(analysis_group, 1)  # Take all available space
        
        # Show welcome message by default
        self.create_default_analysis()
    
    def _create_toolbar(self):
        """Create main toolbar with actions"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        
        # Select ROI action
        select_roi_action = QAction("🎯 Select Area", self)
        select_roi_action.setStatusTip("Select screen capture area")
        select_roi_action.triggered.connect(self.select_roi)
        toolbar.addAction(select_roi_action)
        
        toolbar.addSeparator()
        
        # Capture action
        self.capture_action = QAction("📸 Capture", self)
        self.capture_action.setStatusTip("Capture and detect cards")
        self.capture_action.setEnabled(False)
        self.capture_action.triggered.connect(self.capture_and_detect)
        toolbar.addAction(self.capture_action)
        
        toolbar.addSeparator()
        
        # Analyze action
        analyze_action = QAction("🧠 Analyze", self)
        analyze_action.setStatusTip("Analyze current situation")
        analyze_action.triggered.connect(self.analyze_situation)
        toolbar.addAction(analyze_action)

        toolbar.addSeparator()



        toolbar.addSeparator()

        # Clear action
        clear_action = QAction("🔄 Clear", self)
        clear_action.setStatusTip("Clear all inputs")
        clear_action.triggered.connect(self.clear_all_inputs)
        toolbar.addAction(clear_action)
        
        # Add stretch to push remaining items to right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        
        # Reset layout action
        reset_layout_action = QAction("⚡ Reset Layout", self)
        reset_layout_action.setStatusTip("Reset docks to default positions")
        reset_layout_action.triggered.connect(self.reset_dock_layout)
        toolbar.addAction(reset_layout_action)



    def _create_dock_widgets(self):
        """Create and configure all dock widgets"""
        # Table Configuration Dock (Left)
        self.table_config_dock = TableConfigDock(self)
        self.table_config_dock.table_size_changed.connect(self.on_table_size_changed)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.table_config_dock)
        
        # Cards Dock (Left, below table config)
        self.cards_dock = CardsDock(self)
        self.cards_dock.cards_changed.connect(self.on_cards_changed)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.cards_dock)
        
        # Image Preview Dock (Right)
        self.image_preview_dock = ImagePreviewDock(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.image_preview_dock)
        

        

        
        # Set relative sizes
        self.resizeDocks(
            [self.table_config_dock, self.cards_dock],
            [200, 400],
            Qt.Orientation.Vertical
        )
        
        logger.info("Dock widgets created")
    
    def _create_status_bar(self):
        """Create status bar"""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage("Ready - Configure and analyze")
        status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #1a1a1a;
                color: #888;
                border-top: 1px solid #444;
                padding: 4px;
            }
        """)
    
    def _create_menu_bar(self):
        """Create menu bar"""
        menubar = self.menuBar()
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        # Toggle dock visibility actions
        view_menu.addAction(self.table_config_dock.toggleViewAction())
        view_menu.addAction(self.cards_dock.toggleViewAction())
        view_menu.addAction(self.image_preview_dock.toggleViewAction())

        
        view_menu.addSeparator()
        
        # Reset layout action
        reset_action = QAction("Reset Layout", self)
        reset_action.triggered.connect(self.reset_dock_layout)
        view_menu.addAction(reset_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        select_roi_action = QAction("Select Capture Area", self)
        select_roi_action.triggered.connect(self.select_roi)
        tools_menu.addAction(select_roi_action)
        
        clear_action = QAction("Clear All Cards", self)
        clear_action.triggered.connect(self.clear_all_inputs)
        tools_menu.addAction(clear_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def reset_dock_layout(self):
        """Reset dock widgets to default layout"""
        # Reset to default positions
        self.removeDockWidget(self.table_config_dock)
        self.removeDockWidget(self.cards_dock)

        
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.table_config_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.cards_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.image_preview_dock)


        
        # Ensure all visible
        for dock in [self.table_config_dock, self.cards_dock, self.image_preview_dock]:
            dock.setVisible(True)
            dock.setFloating(False)
        
        self.statusBar().showMessage("Layout reset to default", 3000)
        logger.info("Dock layout reset to default")
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About MonteLab",
            """
            <h2>MonteLab - Adaptive UI</h2>
            <p><b>Version:</b> 2.0-Adaptive</p>
            <p><b>Architecture:</b> Modular with dockable panels</p>
            <br>
            <p><b>Features:</b></p>
            <ul>
            <li>Adaptive responsive UI</li>
            <li>Dockable/floatable panels</li>
            <li>Persistent layout state</li>
            <li>Multi-monitor support</li>
            <li>ML-powered card detection</li>
            <li>Advanced poker analysis</li>
            </ul>
            """
        )
    
    # ==================== Event Handlers ====================
    
    def on_table_size_changed(self, table_size: TableSize):
        """Handle table size change"""
        self.game_state.table_size = table_size
        
        # Update player and board cards from current inputs
        self.game_state.player_cards = self.get_player_cards()
        self.game_state.board_cards = self.get_board_cards()
        self.game_state.stage = self._determine_stage(self.game_state.board_cards)
        
        self.update_game_state_display()
        
        # Auto-analyze if we have valid player cards
        if len(self.game_state.player_cards) == 2:
            self.analysis_timer.stop()
            self.analysis_timer.start(300)
        
        logger.info(f"Table size changed: {table_size}")
    
    def on_game_type_changed(self, game_type: GameType):
        """Handle game type change"""
        self.game_state.game_type = game_type
        self.update_game_state_display()
        logger.info(f"Game type changed: {game_type}")
    
    def on_cards_changed(self, *args):
        """Handle card input changes"""
        # Update player cards
        player_cards = self.get_player_cards()
        self.game_state.player_cards = player_cards
        
        # Update board cards
        board_cards = self.get_board_cards()
        self.game_state.board_cards = board_cards
        self.game_state.stage = self._determine_stage(board_cards)
        
        self.update_game_state_display()
        
        # Auto-analyze if we have valid player cards
        if len(player_cards) == 2:
            # Debounce analysis
            self.analysis_timer.stop()
            self.analysis_timer.start(300)
        
        logger.debug(f"Cards changed: {len(player_cards)} player, {len(board_cards)} board")
    
    def update_game_state_display(self):
        """Update game state label"""
        players_count = self.game_state.get_players_count()
        stage_name = self.game_state.stage.value
        board_count = len(self.game_state.board_cards)
        game_type = self.game_state.game_type.value
        
        display_text = (f"Table: {players_count} Players | "
                       f"Type: {game_type} | "
                       f"Stage: {stage_name} ({board_count} cards)")
        self.game_state_label.setText(display_text)
    
    # ==================== Card Management ====================
    
    def has_player_cards(self) -> bool:
        """Check if player has valid cards"""
        if not self.cards_dock:
            return False
        
        card1 = self.cards_dock.card1_widget.get_text().strip()
        card2 = self.cards_dock.card2_widget.get_text().strip()
        return bool(card1 and card2)
    
    def get_player_cards(self) -> List[Card]:
        """Get player cards"""
        if not self.cards_dock:
            return []
        
        cards = []
        for widget in [self.cards_dock.card1_widget, self.cards_dock.card2_widget]:
            text = widget.get_text().strip()
            if text:
                card = Card.parse(text)
                if card:
                    cards.append(card)
        return cards
    
    def get_board_cards(self) -> List[Card]:
        """Get board cards"""
        if not self.cards_dock:
            return []
        
        cards = []
        widgets = [
            self.cards_dock.flop1_widget,
            self.cards_dock.flop2_widget,
            self.cards_dock.flop3_widget,
            self.cards_dock.turn_widget,
            self.cards_dock.river_widget
        ]
        
        for widget in widgets:
            text = widget.get_text().strip()
            if text:
                card = Card.parse(text)
                if card:
                    cards.append(card)
        return cards
    
    def _determine_stage(self, board_cards: List[Card]) -> GameStage:
        """Determine game stage from board cards"""
        num_board = len(board_cards)
        stage_map = {
            0: GameStage.PREFLOP,
            3: GameStage.FLOP,
            4: GameStage.TURN,
            5: GameStage.RIVER
        }
        return stage_map.get(num_board, GameStage.PREFLOP)
    
    def clear_all_inputs(self):
        """Clear all card inputs"""
        if self.cards_dock:
            self.cards_dock.clear_all_cards()
        
        self.game_state.player_cards = []
        self.game_state.board_cards = []
        self.game_state.stage = GameStage.PREFLOP
        
        self.update_game_state_display()
        
        self.create_default_analysis()
        
        self.statusBar().showMessage("🔄 All inputs cleared", 3000)
        logger.info("All inputs cleared")
    
    # ==================== ROI and Capture ====================
    
    def select_roi(self):
        """Select screen capture ROI"""
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
                    self.capture_action.setEnabled(True)
                    self.statusBar().showMessage(
                        f"✅ Area selected: {rect.width()}×{rect.height()} at ({rect.x()}, {rect.y()})",
                        5000
                    )
                    logger.info(f"ROI saved: {rect.width()}x{rect.height()}")
                else:
                    QMessageBox.warning(
                        self,
                        "Selection Too Small",
                        "Please select a larger area (minimum 50×50 pixels)"
                    )
        
        except Exception as e:
            logger.error(f"ROI selection error: {e}", exc_info=True)
            QMessageBox.critical(self, "Selection Error", f"Failed to select region: {e}")
    
    def capture_and_detect(self):
        """Capture screen and detect cards"""
        if not self.roi:
            QMessageBox.warning(self, "No Area", "Please select capture area first")
            return

        self.statusBar().showMessage("📸 Capturing and analyzing...")

        try:
            frame = self.screen_capture.grab_roi(self.roi)
            if frame is None:
                QMessageBox.warning(self, "Capture Failed", "Failed to capture screenshot")
                self.statusBar().showMessage("❌ Capture failed", 3000)
                return

            self.captured_frame = frame.copy()
            self.display_frame(frame)

            # Run ML card detection
            if self.ml_service.is_available:
                self.statusBar().showMessage("🔍 Analyzing cards with ML...")
                self._detect_and_fill_cards(frame)
            else:
                self.statusBar().showMessage(
                    "📷 Captured - ML unavailable, enter cards manually",
                    5000
                )



        except Exception as e:
            logger.error(f"Capture error: {e}", exc_info=True)
            QMessageBox.critical(self, "Capture Error", f"Failed to capture: {e}")
            self.statusBar().showMessage("❌ Capture error", 3000)
    

    
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
            self.statusBar().showMessage(f"❌ ML error: {e}", 3000)

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
                cv2.putText(
                    overlay_frame,
                    f"P: {detection.classification}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

            for detection in board_cards:
                x1, y1, x2, y2 = detection.bbox
                cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                cv2.putText(
                    overlay_frame,
                    f"B: {detection.classification}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 0, 0),
                    2
                )

            self.display_frame(overlay_frame)

            # Fill card inputs
            if len(player_cards) >= 1:
                self.cards_dock.card1_widget.set_text(player_cards[0].classification or "")
            if len(player_cards) >= 2:
                self.cards_dock.card2_widget.set_text(player_cards[1].classification or "")

            board_widgets = [
                self.cards_dock.flop1_widget,
                self.cards_dock.flop2_widget,
                self.cards_dock.flop3_widget,
                self.cards_dock.turn_widget,
                self.cards_dock.river_widget
            ]

            for i, widget in enumerate(board_widgets):
                if i < len(board_cards):
                    widget.set_text(board_cards[i].classification or "")
                else:
                    widget.clear()

            # Проверяем флаг отложенного полного анализа
            if hasattr(self, '_pending_full_analysis') and self._pending_full_analysis:
                self._pending_full_analysis = False
                
                if len(player_cards) >= 2:
                    # Запускаем полный анализ с Decision Engine
                    self._run_decision_engine_analysis()
                    self.statusBar().showMessage(
                        f"✅ Detected: {len(player_cards)} player, {len(board_cards)} board cards",
                        5000
                    )
                else:
                    self.statusBar().showMessage(
                        f"⚠️ Found {len(player_cards)} player cards - Complete manually",
                        5000
                    )
            else:
                # Обычный режим (capture_and_detect)
                if len(player_cards) >= 2:
                    self.analyze_situation()
                    self.statusBar().showMessage(
                        f"✅ Detected: {len(player_cards)} player, {len(board_cards)} board cards",
                        5000
                    )
                else:
                    self.statusBar().showMessage(
                        f"⚠️ Found {len(player_cards)} player cards - Complete manually",
                        5000
                    )

        except Exception as e:
            logger.error(f"Error processing detection results: {e}", exc_info=True)
            self.statusBar().showMessage(f"❌ Error: {e}", 3000)

    def _on_detection_failed(self, error_message: str):
        """Handle detection failure from worker thread"""
        logger.error(f"ML detection failed: {error_message}")
        self.statusBar().showMessage(f"❌ Detection failed: {error_message}", 3000)
    
    def display_frame(self, frame: np.ndarray):
        """Display frame in image preview dock"""
        if not self.image_preview_dock:
            return
        
        try:
            if len(frame.shape) == 3:
                height, width, channel = frame.shape
                bytes_per_line = 3 * width
                q_image = QImage(
                    frame.data,
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_RGB888
                ).rgbSwapped()
            else:
                height, width = frame.shape
                bytes_per_line = width
                q_image = QImage(
                    frame.data,
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_Grayscale8
                )
            
            pixmap = QPixmap.fromImage(q_image)
            self.image_preview_dock.set_pixmap(pixmap)
        
        except Exception as e:
            logger.error(f"Display error: {e}")
    
    # ==================== Analysis ====================
    
    def create_default_analysis(self):
        """Display default welcome message in analysis area"""
        self.clear_analysis_content()
        
        welcome = QLabel("🎴 Welcome to MonteLab")
        welcome.setStyleSheet("font-size: 18px; font-weight: bold; color: #4CAF50; padding: 15px;")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        instructions = QLabel("""
        <b>Instructions:</b><br>
        1. Configure table settings<br>
        2. Enter cards or use ML detection<br>
        3. Click 'Analyze' for insights<br><br>
        
        <b>Features:</b><br>
        • Hand strength evaluation<br>
        • Board texture analysis<br>
        • Outs calculation<br>
        • Strategy recommendations<br><br>
        
        <b>Tip:</b> Drag dock panels to customize layout<br>
        Right-click title bars for options<br>
        Double-click to undock/dock
        """)
        instructions.setStyleSheet("color: #ccc; padding: 15px; line-height: 1.6;")
        instructions.setWordWrap(True)
        
        self.analysis_layout.addWidget(welcome)
        self.analysis_layout.addWidget(instructions)
        self.analysis_layout.addStretch()
    
    def clear_analysis_content(self):
        """Clear all content from analysis area"""
        while self.analysis_layout.count():
            child = self.analysis_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def add_analysis_widget(self, widget: QWidget):
        """Add widget to analysis content"""
        self.analysis_layout.addWidget(widget)
    
    def add_analysis_stretch(self):
        """Add stretch to push content up"""
        self.analysis_layout.addStretch()
    
    def analyze_situation(self):
        """Analyze current poker situation"""
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
            self.statusBar().showMessage("🧠 Analyzing...", 1000)

            # Analysis with detailed game state
            analysis_result = self.analysis_service.analyze_hand(self.game_state)

            if "error" in analysis_result:
                QMessageBox.warning(self, "Analysis Error", analysis_result["error"])
            else:
                self._display_analysis_result(analysis_result)

            self.statusBar().showMessage("✅ Analysis complete", 3000)

        except Exception as e:
            logger.error(f"Analysis error: {e}", exc_info=True)
            QMessageBox.critical(self, "Analysis Error", f"Failed to analyze: {e}")
            self.statusBar().showMessage("❌ Analysis error", 3000)
    
    def _display_analysis_result(self, result: Dict[str, Any]):
        """Display analysis results in central analysis area"""
        self.clear_analysis_content()
        
        stage = result.get("stage", "")
        
        # Cards display
        cards_display = " ".join(str(c) for c in self.game_state.player_cards)
        board_display = (" ".join(str(c) for c in self.game_state.board_cards) 
                        if self.game_state.board_cards else "No board")
        
        # Title
        # Title
        title = QLabel(f"Hand Analysis — {stage.upper()}")
        title.setStyleSheet("""
            font-size: 20px; 
            font-weight: bold; 
            color: #4CAF50; 
            padding: 10px;
            background-color: rgba(76, 175, 80, 0.1);
            border-radius: 6px;
        """)
        
        # Cards info
        cards_label = QLabel(f"Player: {cards_display} | Board: {board_display}")
        cards_label.setStyleSheet("""
            font-size: 16px; 
            color: #81C784; 
            padding: 8px; 
            font-weight: bold;
            background-color: rgba(129, 199, 132, 0.1);
            border-radius: 4px;
        """)
        cards_label.setWordWrap(True)
        
        self.add_analysis_widget(title)
        self.add_analysis_widget(cards_label)
        
        # Hand strength analysis
        if "current_hand" in result:
            strength_group = QGroupBox("Hand Evaluation")
            strength_layout = QVBoxLayout(strength_group)
            
            current_hand_label = QLabel(f"Current Combination: {result['current_hand'].title()}")
            current_hand_label.setStyleSheet("""
                font-size: 16px; 
                color: #fff; 
                padding: 8px; 
                font-weight: bold;
            """)
            strength_layout.addWidget(current_hand_label)
            
            # Outs analysis
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
                
                # Calculate improvement equity
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
            outs_label.setStyleSheet("""
                font-size: 14px; 
                color: #ccc; 
                padding: 8px; 
                font-family: 'Consolas', monospace;
                background-color: rgba(0, 0, 0, 0.3);
                border-radius: 4px;
            """)
            outs_label.setWordWrap(True)
            strength_layout.addWidget(outs_label)
            
            self.add_analysis_widget(strength_group)

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
                
            self.add_analysis_widget(equity_group)
        
        # Board texture
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
            
            texture_text = ("Characteristics:\n" + "\n".join(f"• {f}" for f in features) 
                          if features else "Standard")
            
            texture_label = QLabel(texture_text)
            texture_label.setStyleSheet("font-size: 14px; color: #ccc; padding: 8px;")
            texture_label.setWordWrap(True)
            texture_layout.addWidget(texture_label)
            
            self.add_analysis_widget(texture_group)
        
        # Strategy recommendation
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
            
            self.add_analysis_widget(recommendations_group)
        
        self.add_analysis_stretch()
    
    # ==================== State Management ====================
    
    def save_roi(self):
        """Save ROI to config"""
        if self.roi:
            roi_data = [self.roi.x(), self.roi.y(), self.roi.width(), self.roi.height()]
            self.ui_config_manager.update_roi(roi_data)
            logger.info(f"ROI saved: {roi_data}")
    
    def load_roi(self):
        """Load ROI from config"""
        config = self.ui_config_manager.config
        if config.roi and len(config.roi) == 4:
            self.roi = QRect(*config.roi)
            self.capture_action.setEnabled(True)
            self.statusBar().showMessage(
                f"📁 Loaded saved area: {config.roi[2]}×{config.roi[3]}",
                3000
            )
            logger.info(f"ROI loaded: {config.roi}")



    def load_ui_state(self):
        """Load and restore UI state from config"""
        config = self.ui_config_manager.config
        
        # Restore window geometry
        if config.window_geometry:
            self.setGeometry(config.window_geometry.to_qrect())
            if config.window_geometry.maximized:
                self.showMaximized()
        
        # Restore dock states
        for dock_name, dock in [
            ("table_config", self.table_config_dock),
            ("cards", self.cards_dock),
            ("image_preview", self.image_preview_dock)
        ]:
            if dock:
                dock_state = config.dock_states.get(dock_name)
                if dock_state:
                    # Restore visibility
                    dock.setVisible(dock_state.visible)
                    
                    # Restore floating state and geometry
                    if dock_state.floating and dock_state.geometry:
                        dock.setFloating(True)
                        geom = dock_state.geometry
                        from PySide6.QtCore import QRect
                        saved_rect = QRect(
                            geom['x'], geom['y'],
                            geom['width'], geom['height']
                        )
                        # Use the new set_saved_geometry method to properly restore
                        dock.set_saved_geometry(saved_rect)
                        logger.info(f"Restored floating {dock_name}: {geom}")
        
        logger.info("UI state loaded")
    
    def save_ui_state(self):
        """Save current UI state to config"""
        # Save window geometry
        geometry = WindowGeometry.from_qrect(
            self.geometry(),
            self.isMaximized()
        )
        self.ui_config_manager.update_window_geometry(geometry)
        
        # Save dock states
        for dock_name, dock in [
            ("table_config", self.table_config_dock),
            ("cards", self.cards_dock),
            ("image_preview", self.image_preview_dock)
        ]:
            if dock:
                area_map = {
                    Qt.DockWidgetArea.LeftDockWidgetArea: "left",
                    Qt.DockWidgetArea.RightDockWidgetArea: "right",
                    Qt.DockWidgetArea.TopDockWidgetArea: "top",
                    Qt.DockWidgetArea.BottomDockWidgetArea: "bottom"
                }
                
                geometry_dict = None
                if dock.isFloating():
                    geom = dock.geometry()
                    geometry_dict = {
                        'x': geom.x(),
                        'y': geom.y(),
                        'width': geom.width(),
                        'height': geom.height()
                    }
                
                state = DockState(
                    name=dock_name,
                    floating=dock.isFloating(),
                    visible=dock.isVisible(),
                    area=area_map.get(self.dockWidgetArea(dock), "left"),
                    geometry=geometry_dict
                )
                self.ui_config_manager.update_dock_state(dock_name, state)
        
        logger.info("UI state saved")

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
                
                # Обновляем UI кнопки в table_config_dock
                if hasattr(self, 'table_config_dock') and self.table_config_dock:
                    self.table_config_dock.set_table_size(new_table_size, emit_signal=False)
                    logger.info("HANDLER: Updated table_config_dock button")
                
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
        """
        Handle Enter hotkey for analysis.
        
        Запускает полный анализ (как кнопка "Анализ").
        """
        logger.info("HOTKEY: Enter pressed -> Running full analysis")
        
        try:
            # Запуск полного анализа
            self._on_analyze_table_data()
            logger.info("HOTKEY: Full analysis completed")
            
        except Exception as e:
            logger.error(f"HOTKEY: Exception: {e}", exc_info=True)    

    # ==================== Decision Engine Integration ====================
    
    def _update_player_count_ui(self, player_count: int):
        """
        Синхронизировать количество игроков между алгоритмом и UI.
        
        Обновляет:
        - game_state.table_size
        - Кнопку в TableConfigDock
        - Отображение состояния
        
        Args:
            player_count: Количество активных игроков (2-9)
        """
        if player_count < 2 or player_count > 9:
            logger.warning(f"Invalid player count for UI update: {player_count}")
            return
        
        from core.domain import TableSize
        
        count_to_size = {
            2: TableSize.HEADS_UP,
            3: TableSize.THREE_MAX,
            4: TableSize.FOUR_MAX,
            5: TableSize.FIVE_MAX,
            6: TableSize.SIX_MAX,
            7: TableSize.SEVEN_MAX,
            8: TableSize.EIGHT_MAX,
            9: TableSize.NINE_MAX
        }
        
        new_table_size = count_to_size[player_count]
        
        # Обновить game_state
        if self.game_state.table_size != new_table_size:
            old_size = self.game_state.table_size
            self.game_state.table_size = new_table_size
            logger.info(f"Updated game_state.table_size: {old_size} -> {new_table_size}")
        
        # Обновить UI кнопку в TableConfigDock
        if hasattr(self, 'table_config_dock') and self.table_config_dock:
            self.table_config_dock.set_player_count(player_count, emit_signal=False)
            logger.info(f"Updated table_config_dock button to {player_count} players")
        
        # Обновить отображение состояния
        self.update_game_state_display()
    
    def _on_new_hand_start(self):
        """Handle 'New Hand' request"""
        logger.info("New hand start requested")
        
        self.clear_all_inputs()
        self.statusBar().showMessage("✅ New hand started (Clean state)", 3000)


    
    def _on_analyze_table_data(self):
        """
        Handle 'Analyze' request
        
        Algorithm:
        1. Capture Screen
        2. Cards Detection (ML)
        3. Equity (Monte Carlo)
        4. Decision Engine (with available data)
        """
        logger.info("Full table analysis requested")
        
        # Check ROI
        if not self.roi:
            QMessageBox.warning(self, "No Area", "Please select capture area first")
            return
        
        try:
            self.statusBar().showMessage("🔍 Analyzing situation...")
            
            # 1. Capture
            frame = self.screen_capture.grab_roi(self.roi)
            if frame is None:
                QMessageBox.warning(self, "Error", "Failed to capture screen")
                return
            
            self.captured_frame = frame.copy()
            self.display_frame(frame)
            
            # 2. ML Detection
            self._pending_full_analysis = True
            
            if hasattr(self, 'ml_service') and self.ml_service and self.ml_service.is_available:
                self._detect_and_fill_cards(frame)
                self.statusBar().showMessage("🔄 Detecting cards...")
            else:
                # ML unavailable - proceed with current cards
                self._pending_full_analysis = False
                self._run_decision_engine_analysis()
            
        except Exception as e:
            logger.error(f"Table data analysis error: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Analysis error: {e}")
    
    def _run_decision_engine_analysis(self):
        """Final analysis step with Decision Engine"""
        try:
            # Get cards
            player_cards = self.get_player_cards()
            board_cards = self.get_board_cards()
            
            if len(player_cards) != 2:
                logger.warning("Not enough player cards for analysis")
                self.statusBar().showMessage("⚠️ Please enter hero cards", 3000)
                return
            
            # Use current table data or create default
            table_data = self.table_data_collector.current_data
            
            if not table_data:
                # Create basic table data if none exists
                table_data = self.table_data_collector.new_hand_start(
                    stacks=[100.0] * 6, # Default
                    bets=[0.0] * 6,
                    pot=0.0,
                    hero_cards=[str(c) for c in player_cards],
                    hero_index=0
                )
            
            # Update cards
            table_data.hero_cards = [str(c) for c in player_cards]
            table_data.community_cards = [str(c) for c in board_cards]
            
            # Monte Carlo equity
            equity_data = self._get_equity_from_monte_carlo(player_cards, board_cards)
            
            # Decision Engine
            result = self.decision_engine.analyze(table_data, equity_data)
            viz_data = self.decision_engine.get_visualization_data(result)
            

            
            # Standard analysis for result panel
            self.analyze_situation()
            
            # Status
            hero = table_data.get_hero()
            hero_pos = hero.position if hero else "?"
            
            self.statusBar().showMessage(
                f"✅ Analysis: {result.decision.value} ({result.confidence:.0f}%) | "
                f"Pos: {hero_pos}",
                5000
            )
            
            logger.info(f"Decision Engine analysis complete: {result.decision.value}")
            
        except Exception as e:
            logger.error(f"Decision Engine analysis error: {e}", exc_info=True)
            self.statusBar().showMessage(f"❌ Analysis error: {e}", 5000)
    

    
    def _get_equity_from_monte_carlo(self, player_cards: List, board_cards: List) -> Optional[Dict]:
        """Получить эквити из Monte Carlo движка"""
        try:
            from monte_carlo_engine_v3 import MonteCarloEngineDaemon
            
            mc_engine = MonteCarloEngineDaemon()
            
            opponents = self.game_state.get_opponents_count()
            
            result = mc_engine.calculate_equity(
                hole_cards=player_cards,
                board_cards=board_cards,
                opponents=opponents,
                iterations=50000  # Быстрый расчёт
            )
            
            if result and "win_rate" in result:
                win = float(result.get("win_rate", 0.0))
                tie = float(result.get("tie_rate", 0.0))
                lose = float(result.get("lose_rate", max(0.0, 100.0 - win - tie)))
                return {
                    "win_rate": win,
                    "tie_rate": tie,
                    "lose_rate": lose,
                    "total_simulations": result.get("total_simulations", 50000)
                }
            
        except Exception as e:
            logger.error(f"Monte Carlo error: {e}")
        
        return None
    
    def closeEvent(self, event):
        """Handle window close event"""
        self.save_ui_state()
        logger.info("Application closing - UI state saved")
        event.accept()

