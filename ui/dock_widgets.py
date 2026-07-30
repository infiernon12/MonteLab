"""Dockable widgets for adaptive UI - Fixed floating resize issue"""
import logging
from typing import Optional, List
from PySide6.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QGroupBox, QRadioButton, QButtonGroup,
                               QScrollArea, QPushButton, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QTimer, QRect
from PySide6.QtGui import QResizeEvent, QMoveEvent

from core.domain import TableSize, GameType
from ui.widgets import CardInputWidget

logger = logging.getLogger(__name__)


class BaseDockWidget(QDockWidget):
    """Base class for all dock widgets with common functionality"""
    
    def __init__(self, title: str, object_name: str, parent=None):
        super().__init__(title, parent)
        self.setObjectName(object_name)
        
        # Enable docking features
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        
        # Set size policies for responsive behavior
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        
        # Store floating geometry to prevent unwanted resizing
        self._floating_geometry: Optional[QRect] = None
        self._is_user_resizing = False
        self._restore_timer = QTimer(self)
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(self._restore_floating_geometry)
        
        # Container widget
        self.container = QWidget()
        self.setWidget(self.container)
        
        # Connect to topLevelChanged signal to handle float/dock transitions
        self.topLevelChanged.connect(self._on_float_changed)
        
        logger.debug(f"Initialized dock: {object_name}")
    
    def _on_float_changed(self, floating: bool):
        """Handle dock/float state change"""
        if floating:
            # When becoming floating, store current geometry
            QTimer.singleShot(100, self._capture_initial_floating_geometry)
            logger.debug(f"{self.objectName()}: Became floating")
        else:
            # Clear stored geometry when docking
            self._floating_geometry = None
            logger.debug(f"{self.objectName()}: Docked")
    
    def _capture_initial_floating_geometry(self):
        """Capture geometry after floating transition completes"""
        if self.isFloating():
            self._floating_geometry = self.geometry()
            logger.debug(f"{self.objectName()}: Captured floating geometry: {self._floating_geometry}")
    
    def resizeEvent(self, event: QResizeEvent):
        """Override resizeEvent to prevent unwanted resizing of floating widgets"""
        if self.isFloating():
            # Check if this is a user-initiated resize
            if event.spontaneous():
                # User is resizing - allow and store new size
                self._is_user_resizing = True
                super().resizeEvent(event)
                self._floating_geometry = self.geometry()
                logger.debug(f"{self.objectName()}: User resized to {self._floating_geometry}")
            else:
                # System-initiated resize (e.g., parent window moved)
                if self._floating_geometry is not None:
                    # Ignore this resize and restore our saved geometry
                    event.ignore()
                    # Schedule geometry restoration after event processing
                    self._restore_timer.start(10)
                    return
                else:
                    # No saved geometry yet, allow this resize
                    super().resizeEvent(event)
        else:
            # Not floating - normal behavior
            super().resizeEvent(event)
    
    def moveEvent(self, event: QMoveEvent):
        """Override moveEvent to track user movements"""
        super().moveEvent(event)
        if self.isFloating():
            # User moved the window - update stored geometry
            if event.spontaneous():
                self._floating_geometry = self.geometry()
                logger.debug(f"{self.objectName()}: User moved to {self._floating_geometry}")
    
    def _restore_floating_geometry(self):
        """Restore the saved floating geometry"""
        if self.isFloating() and self._floating_geometry is not None:
            current_geom = self.geometry()
            # Only restore if geometry actually changed
            if (current_geom.width() != self._floating_geometry.width() or
                current_geom.height() != self._floating_geometry.height()):
                logger.debug(f"{self.objectName()}: Restoring geometry from {current_geom} to {self._floating_geometry}")
                self.setGeometry(self._floating_geometry)
    
    def set_saved_geometry(self, geometry: QRect):
        """Set saved geometry (used when loading from config)"""
        self._floating_geometry = geometry
        if self.isFloating():
            self.setGeometry(geometry)
            logger.debug(f"{self.objectName()}: Applied saved geometry: {geometry}")


class TableConfigDock(BaseDockWidget):
    """Dock widget for table configuration"""
    
    # Signals
    table_size_changed = Signal(TableSize)
    game_type_changed = Signal(GameType)
    
    def __init__(self, parent=None):
        super().__init__("⚙️ Table Configuration", "table_config_dock", parent)
        
        self.table_size_group = QButtonGroup(self)
        self.game_type_group = QButtonGroup(self)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self.container)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Table size section
        size_group = QGroupBox("Table Size")
        size_layout = QVBoxLayout(size_group)
        size_layout.setSpacing(4)
        
        table_sizes = [
            ("2 Players", TableSize.HEADS_UP),
            ("3 Players", TableSize.THREE_MAX),
            ("4 Players", TableSize.FOUR_MAX),
            ("5 Players", TableSize.FIVE_MAX),
            ("6 Players", TableSize.SIX_MAX),
            ("7 Players", TableSize.SEVEN_MAX),
            ("8 Players", TableSize.EIGHT_MAX),
            ("9 Players", TableSize.NINE_MAX)
        ]
        
        for label, size in table_sizes:
            btn = QRadioButton(label)
            btn.setProperty("table_size", size)
            btn.setStyleSheet("font-size: 11px; padding: 3px;")
            
            if size == TableSize.SIX_MAX:
                btn.setChecked(True)
            
            self.table_size_group.addButton(btn)
            size_layout.addWidget(btn)
        
        layout.addWidget(size_group)
        
        # Connect signals
        self.table_size_group.buttonClicked.connect(self._on_table_size_clicked)
        
    def _on_table_size_clicked(self):
        """Handle table size button click"""
        checked_btn = self.table_size_group.checkedButton()
        if checked_btn:
            table_size = checked_btn.property("table_size")
            self.table_size_changed.emit(table_size)
    
    def get_table_size(self) -> TableSize:
        """Get currently selected table size"""
        checked_btn = self.table_size_group.checkedButton()
        if checked_btn:
            return checked_btn.property("table_size")
        return TableSize.SIX_MAX
    
    def set_table_size(self, table_size: TableSize, emit_signal: bool = False):
        """
        Программно установить размер стола (выбрать соответствующую кнопку).
        
        Args:
            table_size: Новый размер стола
            emit_signal: Если True, отправить сигнал table_size_changed
        """
        for btn in self.table_size_group.buttons():
            if btn.property("table_size") == table_size:
                btn.setChecked(True)
                if emit_signal:
                    self.table_size_changed.emit(table_size)
                break
    
    def set_player_count(self, count: int, emit_signal: bool = False):
        """
        Установить количество игроков (выбрать соответствующую кнопку).
        
        Args:
            count: Количество игроков (2-9)
            emit_signal: Если True, отправить сигнал table_size_changed
        """
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
        
        if count in count_to_size:
            self.set_table_size(count_to_size[count], emit_signal)


class CardsDock(BaseDockWidget):
    """Dock widget for player and board cards"""
    
    # Signals
    cards_changed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__("🃏 Cards", "cards_dock", parent)
        
        # Card input widgets
        self.card1_widget: Optional[CardInputWidget] = None
        self.card2_widget: Optional[CardInputWidget] = None
        self.flop1_widget: Optional[CardInputWidget] = None
        self.flop2_widget: Optional[CardInputWidget] = None
        self.flop3_widget: Optional[CardInputWidget] = None
        self.turn_widget: Optional[CardInputWidget] = None
        self.river_widget: Optional[CardInputWidget] = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self.container)
        layout.setSpacing(10)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Player cards section
        player_group = QGroupBox("Player Cards")
        player_layout = QVBoxLayout(player_group)
        player_layout.setSpacing(6)
        
        self.card1_widget = CardInputWidget("Card 1:")
        self.card2_widget = CardInputWidget("Card 2:")
        
        for widget in [self.card1_widget, self.card2_widget]:
            self._configure_card_widget(widget)
            player_layout.addWidget(widget)
        
        layout.addWidget(player_group)
        
        # Board cards section
        board_group = QGroupBox("Board Cards")
        board_layout = QVBoxLayout(board_group)
        board_layout.setSpacing(6)
        
        self.flop1_widget = CardInputWidget("Flop 1:")
        self.flop2_widget = CardInputWidget("Flop 2:")
        self.flop3_widget = CardInputWidget("Flop 3:")
        self.turn_widget = CardInputWidget("Turn:")
        self.river_widget = CardInputWidget("River:")
        
        for widget in [self.flop1_widget, self.flop2_widget, self.flop3_widget,
                      self.turn_widget, self.river_widget]:
            self._configure_card_widget(widget)
            board_layout.addWidget(widget)
        
        layout.addWidget(board_group)
        
        # Clear button
        clear_btn = QPushButton("🔄 Clear All Cards")
        clear_btn.clicked.connect(self.clear_all_cards)
        clear_btn.setStyleSheet("padding: 6px; font-weight: bold;")
        layout.addWidget(clear_btn)
        
        layout.addStretch()
        
        # Connect change signals
        for widget in self.get_all_card_widgets():
            widget.line_edit.textChanged.connect(self.cards_changed.emit)
    
    def _configure_card_widget(self, widget: CardInputWidget):
        """Configure card widget for consistent appearance"""
        widget.label.setFixedWidth(70)
        widget.line_edit.setFixedWidth(45)
        for btn in widget.suit_buttons:
            btn.setFixedSize(30, 30)
    
    def get_all_card_widgets(self) -> List[CardInputWidget]:
        """Get all card input widgets"""
        return [
            self.card1_widget, self.card2_widget,
            self.flop1_widget, self.flop2_widget, self.flop3_widget,
            self.turn_widget, self.river_widget
        ]
    
    def clear_all_cards(self):
        """Clear all card inputs"""
        for widget in self.get_all_card_widgets():
            widget.clear()
        logger.info("All cards cleared")


class AnalysisDock(BaseDockWidget):
    """Dock widget for analysis results"""
    
    def __init__(self, parent=None):
        super().__init__("🧠 Analysis", "analysis_dock", parent)
        
        self.scroll_area: Optional[QScrollArea] = None
        self.content_widget: Optional[QWidget] = None
        self.content_layout: Optional[QVBoxLayout] = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Scrollable area for analysis content
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(8)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        
        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area)
        
        # Show welcome message by default
        self.show_welcome_message()
    
    def show_welcome_message(self):
        """Display welcome/instructions message"""
        self.clear_content()
        
        welcome = QLabel("🃏 Welcome to MonteLab")
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
        • Strategy recommendations
        """)
        instructions.setStyleSheet("color: #ccc; padding: 15px; line-height: 1.6;")
        instructions.setWordWrap(True)
        
        self.content_layout.addWidget(welcome)
        self.content_layout.addWidget(instructions)
        self.content_layout.addStretch()
    
    def clear_content(self):
        """Clear all content from analysis area"""
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def add_widget(self, widget: QWidget):
        """Add widget to analysis content"""
        self.content_layout.addWidget(widget)
    
    def add_stretch(self):
        """Add stretch to push content up"""
        self.content_layout.addStretch()


class ImagePreviewDock(BaseDockWidget):
    """Dock widget for captured image preview"""
    
    def __init__(self, parent=None):
        super().__init__("📸 Image Preview", "image_preview_dock", parent)
        
        self.image_label: Optional[QLabel] = None
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(8, 8, 8, 8)
        
        self.image_label = QLabel("Select area and capture\nto see detected cards")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(250, 200)
        self.image_label.setStyleSheet("""
            background: #111; 
            color: #ccc; 
            border: 2px solid #444; 
            border-radius: 4px; 
            font-size: 13px; 
            padding: 15px;
        """)
        self.image_label.setScaledContents(False)
        
        layout.addWidget(self.image_label, 1)
    
    def set_placeholder_text(self, text: str):
        """Set placeholder text"""
        self.image_label.setText(text)
        self.image_label.setPixmap(None)
    
    def set_pixmap(self, pixmap):
        """Set image pixmap"""
        if pixmap:
            scaled_pixmap = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
        else:
            self.image_label.setPixmap(None)




