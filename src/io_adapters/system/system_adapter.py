import asyncio
import queue
import threading
import time
from typing import Dict, Any

from src.io_adapters.base import AdapterBase
from src.io_adapters.system.system_audio_manager import SystemAudioManager
from src.utils.logger import logger
from src.volcengine.config import input_audio_config


class SystemAdapter(AdapterBase):
    """系统音频输入输出实现"""

    def __init__(self, io_config: Dict[str, Any]):
        super().__init__(io_config)

        # 初始化音频设备管理器
        self.audio_device = SystemAudioManager(self.input_audio_config, self.output_audio_config)

        # 音频队列和播放流
        self.audio_queue = queue.Queue(maxsize=50)
        self.output_stream = None
        self.is_recording = False
        self.is_playing = False
        self.player_thread = None

        # 统计信息
        self.stats = {'audio_queue_overflows': 0}

    async def start(self) -> None:
        """启动音频输入输出"""
        logger.info("🎙️ 启动系统音频输入输出...")

        self.is_running = True
        self.is_recording = True
        self.is_playing = True

        # 启动音频输出流
        self.output_stream = self.audio_device.open_output_stream()

        # 启动播放线程
        self.player_thread = threading.Thread(target=self._audio_player_thread)
        self.player_thread.daemon = True
        self.player_thread.start()

        # 显示欢迎界面
        self.display_welcome_screen()

        # 系统音频立即就绪，触发prepared回调
        self._on_prepared()

        # 启动音频输入处理
        await self._process_microphone_input()

    async def stop(self) -> None:
        """停止音频输入输出"""
        logger.info("🛑 停止系统音频输入输出...")

        self.is_running = False
        self.is_recording = False
        self.is_playing = False

        # 等待播放线程结束
        if self.player_thread and self.player_thread.is_alive():
            self.player_thread.join(timeout=2.0)

    async def send_audio_output(self, audio_data: bytes, format_type: str = "pcm") -> None:
        """发送音频输出数据"""
        if not audio_data or len(audio_data) == 0:
            return

        try:
            self.audio_queue.put(audio_data, timeout=0.1)
        except queue.Full:
            self.stats['audio_queue_overflows'] += 1
            if self.stats['audio_queue_overflows'] % 10 == 1:
                logger.debug(f"⚠️ 音频队列溢出 (第{self.stats['audio_queue_overflows']}次)")

    def display_welcome_screen(self) -> None:
        """显示欢迎界面"""
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 80)
        print("🎙️ 🤖  实时语音对话系统  🤖 🎙️")
        print("=" * 80)
        print("💡 使用说明:")
        print("   • 🎤 直接说话，系统会实时识别您的语音")
        print("   • 🤖 AI助手会语音回复，同时显示文字")
        print("   • 📝 所有对话内容都会实时显示在屏幕上")
        print("   • ⚡ 支持中断对话，按 Ctrl+C 退出")
        print("=" * 80)
        print("🚀 系统已就绪，请开始说话...")
        print("=" * 80 + "\n")

    def cleanup(self) -> None:
        """清理资源"""
        if self.audio_device:
            self.audio_device.cleanup()

    def _audio_player_thread(self):
        """音频播放线程"""
        consecutive_errors = 0
        max_consecutive_errors = 5

        while self.is_playing:
            try:
                audio_data = self.audio_queue.get(timeout=1.0)
                if audio_data is not None and len(audio_data) > 0:
                    self.output_stream.write(audio_data)
                    consecutive_errors = 0

            except queue.Empty:
                time.sleep(0.1)
                consecutive_errors = 0

            except Exception as e:
                consecutive_errors += 1
                logger.debug(f"音频播放错误 ({consecutive_errors}/{max_consecutive_errors}): {e}")

                if consecutive_errors >= max_consecutive_errors:
                    logger.error("连续播放错误过多，尝试重新初始化音频流")
                    try:
                        if self.output_stream:
                            self.output_stream.stop_stream()
                            self.output_stream.close()
                        self.output_stream = self.audio_device.open_output_stream()
                        consecutive_errors = 0
                        logger.info("音频流重新初始化成功")
                    except Exception as reinit_error:
                        logger.error(f"音频流重新初始化失败: {reinit_error}")
                        time.sleep(1.0)
                else:
                    time.sleep(0.2)

    async def _process_microphone_input(self) -> None:
        """处理麦克风输入"""
        stream = self.audio_device.open_input_stream()
        logger.info("🎙️ 麦克风已就绪，开始监听...")

        while self.is_recording:
            try:
                audio_data = stream.read(input_audio_config["chunk"], exception_on_overflow=False)
                self._handle_audio_input(audio_data)
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"读取麦克风数据出错: {e}")
                await asyncio.sleep(0.1)
