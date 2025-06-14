import asyncio
from typing import Dict, Any

import src.io.websocket.config
from src.io.io_base import IOBase
from src.io.websocket.socket_manager import SocketAudioManager, SocketConfig
from src import config
from src.utils.logger import logger


class WebsocketIO(IOBase):
    """Websocket音频输入输出实现"""
    
    def __init__(self, io_config: Dict[str, Any]):
        super().__init__(io_config)
        
        # Socket配置
        socket_host = io_config.get('host', src.io.websocket.config.socket_config['host'])
        socket_port = io_config.get('port', src.io.websocket.config.socket_config['port'])
        
        # 初始化Socket管理器
        socket_config = SocketConfig(host=socket_host, port=socket_port)
        self.socket_manager = SocketAudioManager(socket_config)
        
        # 设置音频输入回调
        self.socket_manager.set_audio_input_callback(self._handle_socket_audio_input)
        
    async def start(self) -> None:
        """启动Websocket音频输入输出"""
        logger.info("🔌 启动Websocket音频输入输出...")
        
        self.is_running = True
        
        # 启动Socket服务器
        await self.socket_manager.start_server()
        
        # 显示欢迎界面
        self.display_welcome_screen()
        
        # 等待连接和处理
        while self.is_running:
            if not self.socket_manager.is_connected:
                await asyncio.sleep(0.1)  # 等待客户端连接
            else:
                await asyncio.sleep(0.01)  # 保持活跃
                
    async def stop(self) -> None:
        """停止Websocket音频输入输出"""
        logger.info("🛑 停止Websocket音频输入输出...")
        
        self.is_running = False
        
        if self.socket_manager:
            self.socket_manager.cleanup()
            
    async def send_audio_output(self, audio_data: bytes, format_type: str = "pcm") -> None:
        """发送音频输出数据"""
        if not audio_data or len(audio_data) == 0:
            return
            
        logger.debug(f"🔌 发送音频输出 ({format_type}): {len(audio_data)}字节")
        if self.socket_manager:
            self.socket_manager.send_audio_output(audio_data, format_type)
            
    def display_welcome_screen(self) -> None:
        """显示Socket欢迎界面"""
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 80)
        print("🔌 🤖  实时语音对话系统 (Socket模式)  🤖 🔌")
        print("=" * 80)
        print("💡 使用说明:")
        print("   • 🔌 通过Socket接收客户端音频输入")
        print("   • 🤖 AI助手会通过Socket返回音频回复")
        print("   • 📝 所有对话内容都会实时显示在屏幕上")
        print("   • ⚡ 支持中断对话，按 Ctrl+C 退出")
        print("=" * 80)
        print(f"🚀 Socket服务器已启动: {src.io.websocket.config.socket_config['host']}:{src.io.websocket.config.socket_config['port']}")
        print("等待客户端连接...")
        print("=" * 80 + "\n")
        
    def cleanup(self) -> None:
        """清理资源"""
        if self.socket_manager:
            self.socket_manager.cleanup()
            
    def _handle_socket_audio_input(self, audio_data: bytes) -> None:
        """处理Socket音频输入"""
        if not self.is_running:
            return
            
        self._handle_audio_input(audio_data)