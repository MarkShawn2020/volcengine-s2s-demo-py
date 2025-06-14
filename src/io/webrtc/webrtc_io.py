import asyncio
from typing import Dict, Any

import src.io.webrtc.config
from src.io.io_base import IOBase
from src.io.webrtc.webrtc_manager import WebRTCManager
from src import config
from src.utils.logger import logger


class WebRTCIO(IOBase):
    """WebRTC音频输入输出实现"""
    
    def __init__(self, io_config: Dict[str, Any]):
        super().__init__(io_config)
        
        # WebRTC配置
        signaling_host = io_config.get('signaling_host', src.io.webrtc.config.webrtc_config['signaling_host'])
        signaling_port = io_config.get('signaling_port', src.io.webrtc.config.webrtc_config['signaling_port'])
        
        # 初始化WebRTC管理器
        self.webrtc_manager = WebRTCManager(
            signaling_host=signaling_host,
            signaling_port=signaling_port
        )
        
        # 设置音频输入回调
        self.webrtc_manager.set_audio_input_callback(self._handle_webrtc_audio_input)
        
    async def start(self) -> None:
        """启动WebRTC音频输入输出"""
        logger.info("🌐 启动WebRTC音频输入输出...")
        
        self.is_running = True
        
        # 启动WebRTC管理器
        await self.webrtc_manager.start()
        
        # 显示欢迎界面
        self.display_welcome_screen()
        
        # 保持运行状态
        while self.is_running:
            await asyncio.sleep(0.1)
            
    async def stop(self) -> None:
        """停止WebRTC音频输入输出"""
        logger.info("🛑 停止WebRTC音频输入输出...")
        
        self.is_running = False
        
        if self.webrtc_manager:
            await self.webrtc_manager.stop()
            
    async def send_audio_output(self, audio_data: bytes, format_type: str = "pcm") -> None:
        """发送音频输出数据"""
        if not audio_data or len(audio_data) == 0:
            return
            
        logger.debug(f"🎵 发送AI音频回复 ({format_type}): {len(audio_data)}字节")
        if self.webrtc_manager:
            self.webrtc_manager.send_audio_to_all_clients(audio_data)
            
    def display_welcome_screen(self) -> None:
        """显示WebRTC欢迎界面"""
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 80)
        print("🌐 🤖  实时语音对话系统 (WebRTC模式)  🤖 🌐")
        print("=" * 80)
        print("💡 使用说明:")
        print("   • 🌐 通过WebRTC接收浏览器音频输入")
        print("   • 🤖 AI助手会通过WebRTC返回音频回复")
        print("   • 📝 所有对话内容都会实时显示在屏幕上")
        print("   • ⚡ 支持中断对话，按 Ctrl+C 退出")
        print("=" * 80)
        print(f"🚀 WebRTC信令服务器已启动: {src.io.webrtc.config.webrtc_config['signaling_host']}:{src.io.webrtc.config.webrtc_config['signaling_port']}")
        print("请在浏览器中打开测试页面进行连接...")
        print("=" * 80 + "\n")
        
    def cleanup(self) -> None:
        """清理资源"""
        if self.webrtc_manager:
            try:
                asyncio.create_task(self.webrtc_manager.stop())
            except Exception as e:
                logger.error(f"清理WebRTC资源错误: {e}")
                
    def _handle_webrtc_audio_input(self, audio_data: bytes) -> None:
        """处理WebRTC音频输入"""
        if not self.is_running:
            return
            
        self._handle_audio_input(audio_data)