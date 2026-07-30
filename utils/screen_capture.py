import platform
import tempfile
import subprocess
import os
import logging
import cv2
import numpy as np
from typing import Optional
from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication


# Условные импорты с флагами доступности
HAS_PYAUTOGUI = False
HAS_PIL = False
HAS_MSS = False

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    pyautogui = None
    
try:
    from PIL import ImageGrab
    HAS_PIL = True
except ImportError:
    ImageGrab = None
    
try:
    import mss
    HAS_MSS = True
except ImportError:
    mss = None

logger = logging.getLogger(__name__)


class ScreenCapture:
    """Cross-platform screen capture with Windows DPI fixes"""
    
    def __init__(self):
        self.os_type = platform.system()
        logger.info(f"ScreenCapture: Initializing for {self.os_type}")
        
        if self.os_type == "Windows":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
                logger.info("ScreenCapture: Windows DPI awareness enabled")
            except Exception as e:
                logger.warning(f"ScreenCapture: Could not set DPI awareness: {e}")
        
        logger.info(f"ScreenCapture: Available libraries - MSS: {HAS_MSS}, PIL: {HAS_PIL}, PyAutoGUI: {HAS_PYAUTOGUI}")
    
    def grab_full_screen(self) -> Optional[np.ndarray]:
        """Capture full primary screen"""
        try:
            screen = QGuiApplication.primaryScreen()
            if not screen:
                logger.error("ScreenCapture: No primary screen found")
                return None
            
            geometry = screen.geometry()
            roi = QRect(0, 0, geometry.width(), geometry.height())
            return self.grab_roi(roi)
            
        except Exception as e:
            logger.error(f"ScreenCapture: Full screen capture failed: {e}")
            return None
    
    def grab_roi(self, roi: QRect) -> Optional[np.ndarray]:
        """Capture screen region"""
        if roi is None or roi.width() <= 0 or roi.height() <= 0:
            logger.error(f"ScreenCapture: Invalid ROI: {roi}")
            return None
        
        logger.info(f"ScreenCapture: Capturing {roi.width()}x{roi.height()} at ({roi.x()}, {roi.y()})")
        
        if self.os_type == "Windows":
            return self._capture_windows(roi)
        elif self.os_type == "Linux":
            return self._capture_linux(roi)
        elif self.os_type == "Darwin":
            return self._capture_macos(roi)
        else:
            logger.error(f"ScreenCapture: Unsupported OS: {self.os_type}")
            return None
    
    def _to_physical_rect(self, roi: QRect) -> QRect:
        """Convert Qt logical coordinates to physical pixels"""
        try:
            center = roi.center()
            screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
            ratio = screen.devicePixelRatio() if screen else 1.0
            
            if ratio <= 0:
                ratio = 1.0
            
            phys_rect = QRect(
                int(roi.x() * ratio),
                int(roi.y() * ratio),
                int(roi.width() * ratio),
                int(roi.height() * ratio)
            )
            
            logger.info(f"  DPI ratio: {ratio:.3f}, Physical: {phys_rect.width()}x{phys_rect.height()}")
            return phys_rect
            
        except Exception as e:
            logger.error(f"ScreenCapture: DPI conversion failed: {e}")
            return roi
    
    def _capture_windows(self, roi: QRect) -> Optional[np.ndarray]:
        """Windows capture with DPI handling - FIXED: proper None checking"""
        phys = self._to_physical_rect(roi)
        
        # Try capture methods in order - FIXED: check for None explicitly
        frame = self._capture_mss(phys)
        if frame is not None:
            return frame
        
        frame = self._capture_pil(phys)
        if frame is not None:
            return frame
        
        frame = self._capture_pyautogui(phys)
        if frame is not None:
            return frame
        
        logger.error("ScreenCapture: All capture methods failed")
        return None
    
    def _capture_mss(self, phys: QRect) -> Optional[np.ndarray]:
        """MSS capture"""
        if not HAS_MSS:
            return None
            
        try:
            with mss.mss() as sct:
                monitor = {"left": phys.x(), "top": phys.y(), "width": phys.width(), "height": phys.height()}
                shot = sct.grab(monitor)
                frame = cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
                logger.info(f"ScreenCapture: MSS capture successful - {frame.shape}")
                return frame
        except Exception as e:
            logger.error(f"ScreenCapture: MSS failed: {e}")
        return None
    
    def _capture_pil(self, phys: QRect) -> Optional[np.ndarray]:
        """PIL capture"""
        if not HAS_PIL:
            return None
            
        try:
            bbox = (phys.x(), phys.y(), phys.x() + phys.width(), phys.y() + phys.height())
            img = ImageGrab.grab(bbox=bbox, all_screens=True)
            if img:
                frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                logger.info(f"ScreenCapture: PIL capture successful - {frame.shape}")
                return frame
        except Exception as e:
            logger.error(f"ScreenCapture: PIL failed: {e}")
        return None
    
    def _capture_pyautogui(self, phys: QRect) -> Optional[np.ndarray]:
        """PyAutoGUI capture"""
        if not HAS_PYAUTOGUI:
            return None
            
        try:
            region = (phys.x(), phys.y(), phys.width(), phys.height())
            img = pyautogui.screenshot(region=region)
            if img:
                frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                logger.info(f"ScreenCapture: PyAutoGUI capture successful - {frame.shape}")
                return frame
        except Exception as e:
            logger.error(f"ScreenCapture: PyAutoGUI failed: {e}")
        return None
    
    def _capture_linux(self, roi: QRect) -> Optional[np.ndarray]:
        """Linux capture via ImageMagick"""
        try:
            temp_path = os.path.join(tempfile.gettempdir(), "screenshot.png")
            cmd = ["import", "-window", "root", "-crop", f"{roi.width()}x{roi.height()}+{roi.x()}+{roi.y()}", temp_path]
            
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode == 0 and os.path.exists(temp_path):
                frame = cv2.imread(temp_path)
                os.remove(temp_path)
                if frame is not None:
                    logger.info(f"ScreenCapture: Linux capture successful - {frame.shape}")
                    return frame
        except FileNotFoundError:
            logger.error("ScreenCapture: ImageMagick not found. Install: sudo apt-get install imagemagick")
        except Exception as e:
            logger.error(f"ScreenCapture: Linux capture failed: {e}")
        return None
    
    def _capture_macos(self, roi: QRect) -> Optional[np.ndarray]:
        """macOS capture via screencapture"""
        try:
            temp_path = os.path.join(tempfile.gettempdir(), "screenshot.png")
            cmd = ["screencapture", "-x", "-R", f"{roi.x()},{roi.y()},{roi.width()},{roi.height()}", temp_path]
            
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode == 0 and os.path.exists(temp_path):
                frame = cv2.imread(temp_path)
                os.remove(temp_path)
                if frame is not None:
                    logger.info(f"ScreenCapture: macOS capture successful - {frame.shape}")
                    return frame
        except Exception as e:
            logger.error(f"ScreenCapture: macOS capture failed: {e}")
        return None
