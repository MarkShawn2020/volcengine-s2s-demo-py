import asyncio

from src.audio.type import AudioType
from src.io_adapters.base import AdapterBase
from src.io_adapters.webrtc.config import WebrtcConfig
from src.io_adapters.webrtc.webrtc_manager import WebRTCManager
from src.utils.logger import logger


class WebRTCAdapter(AdapterBase):
    """WebRTC音频输入输出实现"""

    def __init__(self, config: WebrtcConfig):
        super().__init__(config)

        # 初始化WebRTC管理器
        self.webrtc_manager = WebRTCManager(**self.config)

        # 设置音频输入回调
        self.webrtc_manager.set_audio_input_callback(self._handle_webrtc_audio_input)

        # 设置客户端连接回调
        self.webrtc_manager.set_client_connected_callback(self._handle_client_connected)

        # 标记是否已经触发过prepared回调
        self._prepared_triggered = False

    async def start(self) -> None:
        logger.info("🌐 启动WebRTC音频输入输出...")
        self.is_running = True

        # 获取当前事件循环，用于跨线程调度
        loop = asyncio.get_event_loop()

        # 1. 定义处理PCM数据的回调
        def pcm_to_webrtc(pcm_data: bytes):
            # 使用 loop.call_soon_threadsafe 从其他线程安全地调度协程
            # 这是从同步线程调用异步代码的标准方式
            asyncio.run_coroutine_threadsafe(
                self.webrtc_manager.send_audio_to_all_clients(pcm_data, AudioType.pcm),
                loop
                )

        # 2. 初始化音频处理器
        self._initialize_audio_processor(pcm_to_webrtc)

        # 3. 启动WebRTC管理器 (它内部不应该有阻塞循环)
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

        if self.processing_strategy:
            self.processing_strategy.stop()

        if self.webrtc_manager:
            # 确保WebRTC管理器也停止
            self.webrtc_manager.is_running = False
            await self.webrtc_manager.stop()

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
        print(
            f"🚀 WebRTC信令服务器已启动: {self.config['host']}:"
            f"{self.config['port']}"
            )
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

    def _handle_client_connected(self, client_id: str) -> None:
        """处理WebRTC客户端连接"""
        logger.info(f"🔗 WebRTC客户端已连接: {client_id}")

        # 第一个客户端连接时触发prepared回调
        if not self._prepared_triggered:
            self._prepared_triggered = True
            logger.info("🎯 WebRTC已准备就绪，触发prepared回调")
            self._on_prepared()
