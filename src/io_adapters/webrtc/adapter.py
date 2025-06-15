from src.audio.type import AudioType
from src.io_adapters.base import AdapterBase
from src.io_adapters.webrtc.config import WebrtcConfig
from src.utils.logger import logger


class WebRTCAdapter(AdapterBase):
    """WebRTC音频输入输出实现 - 声明式配置"""

    def __init__(self, config: WebrtcConfig):
        self._webrtc_manager = None
        self._prepared_triggered = False
        super().__init__(config)

    def _handle_webrtc_input(self, audio_data: bytes) -> None:
        """处理WebRTC音频输入"""
        if self.is_running:
            self._handle_audio_input(audio_data)

    def _handle_client_connected(self, client_id: str) -> None:
        """处理WebRTC客户端连接"""
        logger.debug(f"🔗 WebRTC客户端已连接: {client_id}")

        # 第一个客户端连接时触发prepared回调
        if not self._prepared_triggered:
            self._prepared_triggered = True
            logger.debug("🎯 WebRTC已准备就绪，触发prepared回调")
            self._on_prepared()

    def _send_webrtc_output(self, audio_data: bytes) -> None:
        """发送音频到WebRTC客户端"""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(
                self._webrtc_manager.send_audio_to_all_clients(audio_data, AudioType.pcm), loop
                )
        except Exception as e:
            logger.warning(f"发送WebRTC音频数据失败: {e}")

    def _start_webrtc(self) -> None:
        """启动WebRTC管理器"""
        import asyncio
        asyncio.create_task(self._webrtc_manager.start())

    def _stop_webrtc(self) -> None:
        """停止WebRTC管理器"""
        if self._webrtc_manager:
            self._webrtc_manager.is_running = False
            import asyncio
            asyncio.create_task(self._webrtc_manager.stop())

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

    def _handle_webrtc_audio_input(self, audio_data: bytes) -> None:
        """
        处理WebRTC音频输入

        火山规定：客户端上传音频格式要求PCM（脉冲编码调制，未经压缩的的音频格式）、单声道、采样率16000、每个采样点用int16表示、字节序为小端序。
        浏览器已经配置为16kHz采样，无需重复采样
        """
        if not self.is_running:
            return

        # 浏览器已配置为16kHz, int16, 单声道，直接使用
        # 移除重复的重采样步骤以减少延迟
        self._handle_audio_input(audio_data)

    def _handle_client_connected(self, client_id: str) -> None:
        """处理WebRTC客户端连接"""
        logger.debug(f"🔗 WebRTC客户端已连接: {client_id}")

        # 第一个客户端连接时触发prepared回调
        if not self._prepared_triggered:
            self._prepared_triggered = True
            logger.debug("🎯 WebRTC已准备就绪，触发prepared回调")
            self._on_prepared()
