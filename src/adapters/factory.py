from typing import Dict, Any

from src.adapters.base import (
    AudioAdapter, AdapterType, 
    LocalConnectionConfig, BrowserConnectionConfig, TouchDesignerConnectionConfig
)
from src.adapters.local_adapter import LocalAudioAdapter
from src.adapters.browser_adapter import BrowserAudioAdapter


class AdapterFactory:
    """适配器工厂类"""
    
    @staticmethod
    def create_adapter(adapter_type: AdapterType, config: Dict[str, Any]) -> AudioAdapter:
        """创建对应类型的适配器"""
        
        if adapter_type == AdapterType.LOCAL:
            connection_config = LocalConnectionConfig(
                app_id=config['app_id'],
                access_token=config['access_token'],
                **config.get('extra_params', {})
            )
            return LocalAudioAdapter(connection_config)
        
        elif adapter_type == AdapterType.BROWSER:
            connection_config = BrowserConnectionConfig(
                proxy_url=config['proxy_url'],
                app_id=config['app_id'],
                access_token=config['access_token'],
                **config.get('extra_params', {})
            )
            return BrowserAudioAdapter(connection_config)
        
        elif adapter_type == AdapterType.TOUCHDESIGNER:
            # TouchDesigner适配器待实现
            raise NotImplementedError("TouchDesigner adapter not implemented yet")
        
        else:
            raise ValueError(f"Unsupported adapter type: {adapter_type}")
    
    @staticmethod
    def get_available_adapters() -> list[AdapterType]:
        """获取可用的适配器类型"""
        return [AdapterType.LOCAL, AdapterType.BROWSER]
    
    @staticmethod
    def get_adapter_requirements(adapter_type: AdapterType) -> Dict[str, Any]:
        """获取适配器所需的配置参数"""
        
        if adapter_type == AdapterType.LOCAL:
            return {
                "required": ["app_id", "access_token"],
                "optional": ["base_url", "bot_name"],
                "description": "直接连接火山引擎API，需要app_id和access_token"
            }
        
        elif adapter_type == AdapterType.BROWSER:
            return {
                "required": ["proxy_url", "app_id", "access_token"],
                "optional": ["timeout"],
                "description": "通过代理服务器连接，需要proxy_url、app_id和access_token"
            }
        
        elif adapter_type == AdapterType.TOUCHDESIGNER:
            return {
                "required": [],
                "optional": [],
                "description": "TouchDesigner适配器（待实现）"
            }
        
        else:
            return {
                "required": [],
                "optional": [],
                "description": "未知适配器类型"
            }