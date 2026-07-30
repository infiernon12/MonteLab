"""Reusable card input widget with suit buttons"""

from functools import partial
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QLineEdit


class CardLineEdit(QLineEdit):
    """Enhanced QLineEdit with wheel scrolling for ranks"""
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']

    def wheelEvent(self, event):
        """Scroll wheel to cycle through ranks"""
        text = self.text().upper()
        suit = ''
        rank = 'A'

        if len(text) == 2:
            rank, suit = text[0], text[1]
        elif len(text) == 1:
            rank = text[0]

        try:
            current_idx = self.ranks.index(rank)
        except ValueError:
            current_idx = len(self.ranks) - 1

        scroll_delta = event.angleDelta().y()
        if scroll_delta > 0:
            new_idx = (current_idx + 1) % len(self.ranks)
        else:
            new_idx = (current_idx - 1) % len(self.ranks)

        new_rank = self.ranks[new_idx]
        self.setText(new_rank + suit)
        self.selectAll()
        event.accept()


class CardInputWidget(QWidget):
    """Card input with suit buttons and auto-highlight"""

    def __init__(self, label_text: str, parent=None):
        super().__init__(parent)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(8)

        # Label
        self.label = QLabel(label_text)
        self.label.setFixedWidth(80)
        self.label.setStyleSheet("color: #fff; font-weight: bold;")
        self.layout.addWidget(self.label)

        # Card input with wheel scrolling
        self.line_edit = CardLineEdit()
        self.line_edit.setFixedWidth(50)
        self.line_edit.setMaxLength(2)
        self.line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.line_edit.setStyleSheet("""
            QLineEdit {
                font-weight: bold; font-size: 18px; text-transform: uppercase;
                padding: 8px; border: 2px solid #555; border-radius: 6px;
                background-color: #1a1a1a; color: white;
            }
            QLineEdit:focus { border-color: #4CAF50; background-color: #222; }
            QLineEdit:hover { border-color: #777; background-color: #222; }
        """)
        self.line_edit.setToolTip("🎮 Scroll wheel to change rank\n🖱️ Click suit buttons")
        self.layout.addWidget(self.line_edit)

        # Suit buttons with metadata
        self.suit_buttons = []
        self.suit_data = []  # Store suit metadata for highlighting

        suits = [
            ("s", "♠", "#1a1a1a", "#f0f0f0"),
            ("h", "♥", "#e53935", "#fff0f0"),
            ("c", "♣", "#1a1a1a", "#f0f0f0"),
            ("d", "♦", "#e53935", "#fff0f0")
        ]

        for suit_char, suit_symbol, text_color, bg_color in suits:
            btn = QPushButton(suit_symbol)
            btn.setFixedSize(36, 36)

            # Define normal and highlighted styles
            normal_style = f"""
                QPushButton {{
                    font-size: 22px; font-weight: bold; color: {text_color};
                    background-color: {bg_color}; border: 2px solid #999; border-radius: 8px;
                    margin-left: 3px; padding: 2px;
                }}
                QPushButton:hover {{
                    background-color: #4CAF50; color: white; border-color: #4CAF50;
                }}
                QPushButton:pressed {{
                    background-color: #388E3C; color: white; border-color: #388E3C;
                }}
            """

            highlighted_style = f"""
                QPushButton {{
                    font-size: 22px; font-weight: bold; color: #000000;
                    background-color: #FFC107; border: 3px solid #FFA000; border-radius: 8px;
                    margin-left: 3px; padding: 2px;
                }}
                QPushButton:hover {{
                    background-color: #FFD54F; color: #000000; border-color: #FF6F00;
                }}
            """

            btn.setStyleSheet(normal_style)
            btn.clicked.connect(partial(self.on_suit_clicked, suit_char))
            self.layout.addWidget(btn)
            self.suit_buttons.append(btn)

            # Store suit metadata
            self.suit_data.append({
                'char': suit_char.lower(),
                'button': btn,
                'normal_style': normal_style,
                'highlighted_style': highlighted_style
            })

        # Connect text change signal to update highlight
        self.line_edit.textChanged.connect(self._update_suit_highlight)

    def _update_suit_highlight(self):
        """Update suit button highlighting based on text input"""
        text = self.line_edit.text().upper()
        current_suit = None

        # Extract suit from text (second character if present)
        if len(text) >= 2:
            current_suit = text[1].lower()

        # Update all button styles
        for suit_info in self.suit_data:
            if suit_info['char'] == current_suit:
                # Highlight active suit
                suit_info['button'].setStyleSheet(suit_info['highlighted_style'])
            else:
                # Reset to normal style
                suit_info['button'].setStyleSheet(suit_info['normal_style'])

    def on_suit_clicked(self, suit_char: str):
        """Handle suit button click"""
        text = self.line_edit.text().upper()
        rank = text[0] if len(text) > 0 else 'A'
        self.line_edit.setText(rank + suit_char.upper())
        self.line_edit.setFocus()
        self.line_edit.selectAll()
        # Highlight updates automatically via textChanged signal

    def get_text(self) -> str:
        return self.line_edit.text().upper()

    def set_text(self, text: str):
        self.line_edit.setText(text.upper())
        # Highlight updates automatically via textChanged signal

    def clear(self):
        self.line_edit.clear()
        # Highlight updates automatically via textChanged signal
