"""Application styles - Centralized styling"""


def apply_dark_theme(app):
    """Apply dark theme to application"""
    app.setStyleSheet("""
        QWidget { 
            background-color: #2b2b2b; 
            color: #ffffff; 
            font-family: 'Ubuntu', 'Segoe UI', 'Arial', sans-serif;
            font-size: 12px;
        }
        QLineEdit {
            background-color: #1a1a1a;
            border: 2px solid #555;
            color: #ffffff;
            border-radius: 6px;
            padding: 8px;
            font-size: 13px;
        }
        QLineEdit:focus {
            border-color: #4CAF50;
            background-color: #222;
        }
        QPushButton {
            background-color: #404040;
            border: 1px solid #666;
            color: #ffffff;
            padding: 10px 18px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #505050;
            border-color: #777;
        }
        QPushButton:pressed {
            background-color: #353535;
        }
        QPushButton:disabled {
            background-color: #2a2a2a;
            color: #666666;
            border-color: #444;
        }
        QGroupBox {
            font-weight: bold;
            font-size: 12px;
            border: 2px solid #555;
            border-radius: 8px;
            margin-top: 1ex;
            padding-top: 8px;
            background-color: #2a2a2a;
        }
        QScrollArea {
            border: none;
            background-color: #1a1a1a;
        }
        QScrollBar:vertical {
            background: #2a2a2a;
            width: 12px;
            border-radius: 6px;
        }
        QScrollBar::handle:vertical {
            background: #555;
            border-radius: 6px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background: #666;
        }
    """)
