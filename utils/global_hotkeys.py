"""Global hotkey handler for MonteLab"""
import logging
from typing import Callable, Optional
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

try:
    import keyboard
    HAS_KEYBOARD = True
    logger.info("keyboard library available for global hotkeys")
except ImportError:
    keyboard = None
    HAS_KEYBOARD = False
    logger.warning("keyboard library not available. Install: pip install keyboard")


class GlobalHotkeyManager(QObject):
    """Manages global hotkeys that work even when window is not focused"""
    
    numpad_pressed = Signal(int)
    enter_pressed = Signal()
    
    def __init__(self):
        super().__init__()
        self._registered = False
        self._active = False
        
        if not HAS_KEYBOARD:
            logger.error("GlobalHotkeyManager: keyboard library not available")
    
    def is_available(self) -> bool:
        return HAS_KEYBOARD
    
    def register_hotkeys(self):
        if not HAS_KEYBOARD:
            logger.error("Cannot register hotkeys: keyboard library not available")
            return False
        
        if self._registered:
            logger.warning("Hotkeys already registered")
            return True
        
        try:
            for i in range(1, 10):
                keyboard.add_hotkey(f'num {i}', lambda n=i: self._on_numpad(n), suppress=False)
                logger.info(f"Registered hotkey: Numpad/{i} -> Select {i} opponent(s)")
            
            keyboard.add_hotkey('enter', self._on_enter, suppress=False)
            keyboard.add_hotkey('num enter', self._on_enter, suppress=False)
            logger.info("Registered hotkey: Enter -> Capture")
            
            self._registered = True
            self._active = True
            logger.info("Global hotkeys registered successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register hotkeys: {e}")
            return False
    
    def unregister_hotkeys(self):
        if not HAS_KEYBOARD or not self._registered:
            return
        
        try:
            keyboard.unhook_all()
            self._registered = False
            self._active = False
            logger.info("Global hotkeys unregistered")
        except Exception as e:
            logger.error(f"Failed to unregister hotkeys: {e}")
    
    def set_active(self, active: bool):
        self._active = active
        logger.info(f"Global hotkeys {'enabled' if active else 'disabled'}")
    
    def _on_numpad(self, number: int):
        if not self._active:
            return
        
        logger.info(f"HOTKEY: Numpad {number} pressed -> Setting {number} opponent(s)")
        self.numpad_pressed.emit(number - 1)
    
    def _on_enter(self):
        if not self._active:
            return
        
        logger.info("HOTKEY: Enter pressed -> Triggering capture")
        self.enter_pressed.emit()


_hotkey_manager: Optional[GlobalHotkeyManager] = None


def get_hotkey_manager() -> GlobalHotkeyManager:
    global _hotkey_manager
    if _hotkey_manager is None:
        _hotkey_manager = GlobalHotkeyManager()
    return _hotkey_manager