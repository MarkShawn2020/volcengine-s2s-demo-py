import asyncio

from src.io_adapters.base import AdapterBase
from src.utils.logger import logger
from .config import WebsocketConfig
from .websocket_audio_manager import WebsocketAudioManager


class WebsocketAdapter(AdapterBase):
    """Websocket音频输入输出实现"""

    def __init__(self, config: WebsocketConfig):
        super().__init__(config)

        self.socket_manager = WebsocketAudioManager(self.config)

        # 设置音频输入回调
        self.socket_manager.set_audio_input_callback(self._handle_socket_audio_input)

        # 标记是否已经触发过prepared回调
        self._prepared_triggered = False

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
                # 第一次连接时触发prepared回调
                if not self._prepared_triggered:
                    self._prepared_triggered = True
                    logger.info("🎯 Websocket已准备就绪，触发prepared回调")
                    self._on_prepared()
                await asyncio.sleep(0.01)  # 保持活跃

    async def stop(self) -> None:
        """停止Websocket音频输入输出"""
        logger.info("🛑 停止Websocket音频输入输出...")

        self.is_running = False

        if self.socket_manager:
            self.socket_manager.cleanup()

    async def send_audio_output(self, audio_data: bytes, audio_type: str = "pcm") -> None:
        """发送音频输出数据"""
        if not audio_data or len(audio_data) == 0:
            return

        logger.debug(f"🔌 发送音频输出 ({audio_type}): {len(audio_data)}字节")
        if self.socket_manager:
            self.socket_manager.send_audio_output(audio_data, audio_type)

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
        print(f"🚀 Socket服务器已启动: {socket_config['host']}:{socket_config['port']}")
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
