"""
UI Windows Package

Contains main window implementations for different UI modes:
- MainWindow: Classic fixed-layout interface
- AdaptiveMainWindow: Dockable panels with flexible layout
"""

from .main_window import MainWindow
from .adaptive_main_window import AdaptiveMainWindow

__all__ = [
    'MainWindow',
    'AdaptiveMainWindow'
]