"""Selection overlay for ROI capture"""
import logging
from typing import Optional
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QGuiApplication, QPainter, QPen, QBrush, QColor
from PySide6.QtWidgets import QDialog

logger = logging.getLogger(__name__)


class SelectionOverlay(QDialog):
    """Transparent overlay for ROI selection"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("SelectionOverlay: Initializing...")
        
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | 
                          Qt.WindowType.FramelessWindowHint | 
                          Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        self.start_global: Optional[QPoint] = None
        self.end_global: Optional[QPoint] = None
        
        # Cover all screens
        try:
            primary_screen = QGuiApplication.primaryScreen()
            virtual_geom = primary_screen.virtualGeometry()
            self.setGeometry(virtual_geom)
            logger.info(f"Overlay covers: {virtual_geom.width()}x{virtual_geom.height()}")
        except Exception as e:
            logger.error(f"Failed to get screen geometry: {e}")
            self.setGeometry(0, 0, 1920, 1080)
        
        self.setCursor(Qt.CursorShape.CrossCursor)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_global = event.globalPosition().toPoint()
            self.end_global = self.start_global
            logger.info(f"Selection started at ({self.start_global.x()}, {self.start_global.y()})")
            self.update()
    
    def mouseMoveEvent(self, event):
        if self.start_global is not None:
            self.end_global = event.globalPosition().toPoint()
            self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.start_global is not None:
            self.end_global = event.globalPosition().toPoint()
            rect = QRect(self.start_global, self.end_global).normalized()
            logger.info(f"Selection complete: {rect.width()}x{rect.height()} at ({rect.x()}, {rect.y()})")
            self.accept()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            logger.info("Selection cancelled")
            self.reject()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Semi-transparent background
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        if not self.start_global or not self.end_global:
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            hint_text = "Click and drag to select capture area • ESC to cancel"
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, hint_text)
            return
        
        # Convert to local coordinates
        start_local = self.mapFromGlobal(self.start_global)
        end_local = self.mapFromGlobal(self.end_global)
        rect = QRect(start_local, end_local).normalized()
        
        # Clear selected area
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(rect, QColor(0, 0, 0, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        
        # Green selection rectangle
        painter.setPen(QPen(QColor(0, 255, 0), 3, Qt.PenStyle.SolidLine))
        painter.drawRect(rect)
        painter.fillRect(rect, QColor(0, 255, 0, 30))
        
        # Coordinates text
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        text = f"{rect.width()}×{rect.height()} at ({rect.x()}, {rect.y()})"
        text_rect = painter.fontMetrics().boundingRect(text)
        text_rect.adjust(-8, -5, 8, 5)
        text_pos = rect.topLeft() + QPoint(5, -text_rect.height() - 5)
        
        if text_pos.y() < 0:
            text_pos = rect.bottomLeft() + QPoint(5, 10)
        
        text_rect.moveTo(text_pos)
        painter.drawRect(text_rect)
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
    
    def selected_rect(self) -> Optional[QRect]:
        """Return global QRect for screen capture"""
        if self.start_global and self.end_global:
            rect = QRect(self.start_global, self.end_global).normalized()
            logger.info(f"Final selection: {rect.width()}x{rect.height()} at ({rect.x()}, {rect.y()})")
            return rect
        return None
