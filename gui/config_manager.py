"""
GUI配置管理器 - 用于持久化用户配置
"""
import json
import os
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器 - 处理配置的加载和保存"""
    
    def __init__(self):
        # 配置文件路径
        self.config_dir = Path.home() / ".volcengine-voice-chat"
        self.config_file = self.config_dir / "gui_config.json"
        
        # 默认配置
        self.default_config = {
            "bot_name": "小塔",
            "reconnect_timeout": 300.0,
            "use_pcm": True,
            "adapter_type": "local",
            "last_input_device": None,
            "last_output_device": None,
            "window_geometry": None
        }
        
        # 当前配置
        self.config = self.default_config.copy()
        
        # 确保配置目录存在
        self._ensure_config_dir()
        
        # 加载配置
        self.load_config()
    
    def _ensure_config_dir(self):
        """确保配置目录存在"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"创建配置目录失败: {e}")
    
    def load_config(self) -> Dict[str, Any]:
        """从文件加载配置"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    # 合并配置（保留默认值中的新键）
                    self.config = {**self.default_config, **saved_config}
                    logger.info(f"成功加载配置: {self.config_file}")
            else:
                logger.info("配置文件不存在，使用默认配置")
                self.config = self.default_config.copy()
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self.config = self.default_config.copy()
        
        return self.config
    
    def save_config(self) -> bool:
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info(f"成功保存配置: {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        self.config[key] = value
    
    def update(self, updates: Dict[str, Any]) -> None:
        """批量更新配置"""
        self.config.update(updates)
    
    def reset_to_defaults(self) -> None:
        """重置为默认配置"""
        self.config = self.default_config.copy()
        logger.info("配置已重置为默认值")