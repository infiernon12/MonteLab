from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QFrame, QApplication, QMessageBox
)
from PySide6.QtCore import Qt, Signal as pyqtSignal, QTimer
from PySide6.QtGui import QFont, QIcon, QPixmap, QClipboard
from utils.hwid_generator import HWIDGenerator
import logging

logger = logging.getLogger(__name__)

class HWIDDialog(QDialog):
    """Диалоговое окно для отображения HWID пользователя"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Активация лицензии - MonteLab")
        self.setFixedSize(500, 300)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self.setModal(True)
        
        # Генерируем HWID
        try:
            self.hwid = HWIDGenerator.generate_hwid()
            logger.info(f"Generated HWID: {self.hwid}")
        except Exception as e:
            logger.error(f"Error generating HWID: {e}")
            self.hwid = "ERROR-GENERATING-HWID"
        
        self.setup_ui()
        self.setup_styles()
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Заголовок
        title_label = QLabel("🔐 Активация лицензии")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Разделитель
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # Инструкция
        instruction_label = QLabel(
            "Для активации лицензии скопируйте ваш уникальный HWID\n"
            "и отправьте его администратору:"
        )
        instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction_label.setWordWrap(True)
        layout.addWidget(instruction_label)
        
        # HWID поле
        self.hwid_display = QTextEdit()
        self.hwid_display.setPlainText(self.hwid)
        self.hwid_display.setReadOnly(True)
        self.hwid_display.setMaximumHeight(60)
        self.hwid_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hwid_display)
        
        # Кнопки
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.copy_button = QPushButton("📋 Копировать HWID")
        self.copy_button.clicked.connect(self.copy_hwid)
        button_layout.addWidget(self.copy_button)
        
        self.close_button = QPushButton("❌ Закрыть")
        self.close_button.clicked.connect(self.reject)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        
        # Дополнительная информация
        info_label = QLabel(
            "💡 После получения лицензии перезапустите приложение"
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(info_label)
    
    def setup_styles(self):
        """Настройка стилей"""
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
                border-radius: 10px;
            }
            QLabel {
                color: #ffffff;
                padding: 5px;
            }
            QTextEdit {
                background-color: #1a1a1a;
                color: #00ff00;
                border: 2px solid #4CAF50;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                font-weight: bold;
                selection-background-color: #4CAF50;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #45a049;
                transform: translateY(-1px);
            }
            QPushButton:pressed {
                background-color: #3d8b40;
                transform: translateY(1px);
            }
            QPushButton#close_button {
                background-color: #f44336;
            }
            QPushButton#close_button:hover {
                background-color: #da190b;
            }
            QPushButton#close_button:pressed {
                background-color: #b71c1c;
            }
            QFrame {
                color: #666;
            }
        """)
        
        # Устанавливаем ID для кнопки закрытия
        self.close_button.setObjectName("close_button")
    
    def copy_hwid(self):
        """Копирование HWID в буфер обмена"""
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.hwid)
            
            # Показываем уведомление
            self.copy_button.setText("✅ Скопировано!")
            self.copy_button.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                }
            """)
            
            # Возвращаем исходный текст через 2 секунды
            QTimer.singleShot(2000, self.reset_copy_button)
            
            logger.info("HWID copied to clipboard")
            
        except Exception as e:
            logger.error(f"Error copying HWID: {e}")
            QMessageBox.warning(self, "Ошибка", "Не удалось скопировать HWID")
    
    def reset_copy_button(self):
        """Сброс текста кнопки копирования"""
        self.copy_button.setText("📋 Копировать HWID")
        self.copy_button.setStyleSheet("")  # Возвращаем к стандартному стилю
    
    def get_hwid(self) -> str:
        """Получение сгенерированного HWID"""
        return self.hwid
