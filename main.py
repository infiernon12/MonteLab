"""
MonteLab - Advanced Poker Analysis & Monte Carlo Engine
Main Application Entry Point (MIT Open-Source Edition)
"""

import sys
import argparse
import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel,
    QPushButton, QButtonGroup, QRadioButton, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MonteLab")


class UISelectionDialog(QDialog):
    """Dialog for selecting between Classic and Adaptive interface modes."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_mode = "adaptive"
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("MonteLab - Select Interface Mode")
        self.setFixedSize(480, 360)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("MonteLab Poker Analyzer")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #4CAF50;")
        layout.addWidget(title)
        
        desc = QLabel("Choose your preferred interface layout:")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #ccc; font-size: 13px;")
        layout.addWidget(desc)
        
        mode_group = QGroupBox("Interface Modes")
        mode_layout = QVBoxLayout(mode_group)
        
        self.button_group = QButtonGroup(self)
        
        self.adaptive_radio = QRadioButton(" Adaptive Dockable Mode (Recommended)")
        self.adaptive_radio.setStyleSheet("font-size: 13px; font-weight: bold; color: #fff; padding: 5px;")
        adaptive_desc = QLabel("Modern dockable interface with moveable panels and saved layouts.")
        adaptive_desc.setStyleSheet("color: #aaa; font-size: 11px; padding-left: 20px;")
        adaptive_desc.setWordWrap(True)
        
        self.classic_radio = QRadioButton(" Classic Single-Window Mode")
        self.classic_radio.setStyleSheet("font-size: 13px; font-weight: bold; color: #fff; padding: 5px;")
        classic_desc = QLabel("Traditional fixed-layout interface.")
        classic_desc.setStyleSheet("color: #aaa; font-size: 11px; padding-left: 20px;")
        classic_desc.setWordWrap(True)
        
        self.button_group.addButton(self.adaptive_radio, 1)
        self.button_group.addButton(self.classic_radio, 2)
        self.adaptive_radio.setChecked(True)
        
        mode_layout.addWidget(self.adaptive_radio)
        mode_layout.addWidget(adaptive_desc)
        mode_layout.addWidget(self.classic_radio)
        mode_layout.addWidget(classic_desc)
        
        layout.addWidget(mode_group)
        
        self.start_btn = QPushButton("Launch Application")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.start_btn.clicked.connect(self.on_start)
        layout.addWidget(self.start_btn)
        
        self.setStyleSheet("QDialog { background-color: #2b2b2b; } QGroupBox { color: #4CAF50; font-weight: bold; }")

    def on_start(self):
        if self.classic_radio.isChecked():
            self.selected_mode = "classic"
        else:
            self.selected_mode = "adaptive"
        self.accept()


def main():
    parser = argparse.ArgumentParser(description="MonteLab - Poker Analysis & Monte Carlo Engine")
    parser.add_argument(
        "--ui",
        choices=["classic", "adaptive", "select"],
        default="select",
        help="Interface mode to launch (default: select dialog)"
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Starting MonteLab v2.0 (Open-Source Edition)")
    logger.info("=" * 60)

    app = QApplication(sys.argv)
    app.setApplicationName("MonteLab")
    app.setApplicationVersion("2.0.0")

    # Apply dark theme
    try:
        from ui.styles import apply_dark_theme
        app.setStyle("Fusion")
        apply_dark_theme(app)
    except Exception as e:
        logger.warning(f"Could not apply theme: {e}")

    # Determine UI mode
    ui_mode = args.ui
    if ui_mode == "select":
        dialog = UISelectionDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            logger.info("User cancelled startup")
            return 0
        ui_mode = dialog.selected_mode

    # Initialize Services
    logger.info("Initializing ML and Poker Engine Services...")
    script_dir = Path(__file__).parent
    yolo_path = script_dir / "models" / "YOLOX_Detector.pth"
    resnet_path = script_dir / "models" / "ResNet_Classifier.pt"

    # Compute Device Detection
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Compute device selected: {device.upper()}")
    except ImportError:
        device = "cpu"
        logger.warning("PyTorch not installed, fallback to CPU")

    # ML Service Initialization
    from services.ml_service import MLService
    if yolo_path.exists() and resnet_path.exists():
        ml_service = MLService.from_weights(str(yolo_path), str(resnet_path), device=device)
        logger.info("✅ ML Model service initialized with trained weights")
    else:
        logger.warning(f"⚠️  ML weights not found in models/ directory. Run without ML detector or download weights.")
        ml_service = MLService(None, None)

    # Monte Carlo Engine Initialization
    from core.poker import EquityCalculator, CppMonteCarloBackend
    try:
        mc_backend = CppMonteCarloBackend()
        equity_calc = EquityCalculator(backend=mc_backend)
        logger.info("✅ Monte Carlo C++ Backend initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️  C++ Monte Carlo Backend unavailable ({e}). Using Python fallback.")
        equity_calc = EquityCalculator(backend=None)

    from services.analysis_service import AnalysisService
    analysis_service = AnalysisService(equity_calc)

    # Launch Window according to selected mode
    if ui_mode == "classic":
        logger.info("Launching Classic Single-Window Interface...")
        from ui.windows.main_window import MainWindow
        window = MainWindow(ml_service, analysis_service)
    else:
        logger.info("Launching Adaptive Dockable Interface...")
        from ui.windows.adaptive_main_window import AdaptiveMainWindow
        window = AdaptiveMainWindow(ml_service, analysis_service)

    window.show()
    logger.info("MonteLab is ready.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
