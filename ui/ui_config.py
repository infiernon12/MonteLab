"""UI configuration management - Handles window state, dock positions, and user preferences"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict, field
from PySide6.QtCore import QByteArray, QRect, QPoint

logger = logging.getLogger(__name__)


@dataclass
class WindowGeometry:
    """Window geometry state"""
    x: int = 100
    y: int = 100
    width: int = 1200
    height: int = 800
    maximized: bool = False
    
    def to_qrect(self) -> QRect:
        """Convert to QRect for Qt"""
        return QRect(self.x, self.y, self.width, self.height)
    
    @classmethod
    def from_qrect(cls, rect: QRect, maximized: bool = False) -> 'WindowGeometry':
        """Create from QRect"""
        return cls(
            x=rect.x(),
            y=rect.y(),
            width=rect.width(),
            height=rect.height(),
            maximized=maximized
        )


@dataclass
class DockState:
    """State of a single dock widget"""
    name: str
    floating: bool = False
    visible: bool = True
    area: str = "left"  # left, right, top, bottom
    geometry: Optional[Dict[str, int]] = None  # For floating docks
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'floating': self.floating,
            'visible': self.visible,
            'area': self.area,
            'geometry': self.geometry
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DockState':
        """Create from dictionary"""
        return cls(
            name=data['name'],
            floating=data.get('floating', False),
            visible=data.get('visible', True),
            area=data.get('area', 'left'),
            geometry=data.get('geometry')
        )


@dataclass
class UIConfig:
    """Complete UI configuration state"""
    window_geometry: WindowGeometry = field(default_factory=WindowGeometry)
    dock_states: Dict[str, DockState] = field(default_factory=dict)
    roi: Optional[list] = None  # [x, y, width, height]
    theme: str = "dark"
    font_scale: float = 1.0
    show_tooltips: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'window_geometry': asdict(self.window_geometry),
            'dock_states': {name: state.to_dict() for name, state in self.dock_states.items()},
            'roi': self.roi,
            'theme': self.theme,
            'font_scale': self.font_scale,
            'show_tooltips': self.show_tooltips
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UIConfig':
        """Create from dictionary"""
        window_geom_data = data.get('window_geometry', {})
        window_geometry = WindowGeometry(**window_geom_data) if window_geom_data else WindowGeometry()
        
        dock_states_data = data.get('dock_states', {})
        dock_states = {name: DockState.from_dict(state_data) 
                      for name, state_data in dock_states_data.items()}
        
        return cls(
            window_geometry=window_geometry,
            dock_states=dock_states,
            roi=data.get('roi'),
            theme=data.get('theme', 'dark'),
            font_scale=data.get('font_scale', 1.0),
            show_tooltips=data.get('show_tooltips', True)
        )


class UIConfigManager:
    """Manages loading and saving UI configuration"""
    
    DEFAULT_CONFIG_NAME = "ui_config.json"
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize config manager
        
        Args:
            config_path: Custom path to config file. If None, uses project root.
        """
        if config_path is None:
            # Use project root
            config_path = Path(__file__).parent.parent / self.DEFAULT_CONFIG_NAME
        
        self.config_path = Path(config_path)
        self._config: Optional[UIConfig] = None
        logger.info(f"UI config manager initialized: {self.config_path}")
    
    def load(self) -> UIConfig:
        """
        Load UI configuration from file
        
        Returns:
            UIConfig instance (default if file doesn't exist or is invalid)
        """
        if not self.config_path.exists():
            logger.info("No UI config file found, using defaults")
            self._config = UIConfig()
            return self._config
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._config = UIConfig.from_dict(data)
            logger.info(f"UI config loaded successfully from {self.config_path}")
            return self._config
            
        except Exception as e:
            logger.error(f"Failed to load UI config: {e}", exc_info=True)
            logger.info("Using default UI config")
            self._config = UIConfig()
            return self._config
    
    def save(self, config: UIConfig) -> bool:
        """
        Save UI configuration to file
        
        Args:
            config: UIConfig instance to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self._config = config
            
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save to file with pretty formatting
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.info(f"UI config saved successfully to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save UI config: {e}", exc_info=True)
            return False
    
    @property
    def config(self) -> UIConfig:
        """Get current config (loads if not loaded)"""
        if self._config is None:
            return self.load()
        return self._config
    
    def update_window_geometry(self, geometry: WindowGeometry):
        """Update and save window geometry"""
        if self._config is None:
            self._config = self.load()
        
        self._config.window_geometry = geometry
        self.save(self._config)
    
    def update_dock_state(self, dock_name: str, state: DockState):
        """Update and save dock state"""
        if self._config is None:
            self._config = self.load()
        
        self._config.dock_states[dock_name] = state
        self.save(self._config)
    
    def update_roi(self, roi: list):
        """Update and save ROI"""
        if self._config is None:
            self._config = self.load()
        
        self._config.roi = roi
        self.save(self._config)
    
    def get_dock_state(self, dock_name: str) -> Optional[DockState]:
        """Get dock state by name"""
        if self._config is None:
            self._config = self.load()
        
        return self._config.dock_states.get(dock_name)
