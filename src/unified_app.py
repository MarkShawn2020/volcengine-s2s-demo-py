import asyncio
import logging
import queue
import threading

import pyaudio

from src.adapters.base import LocalConnectionConfig, BrowserConnectionConfig
from src.adapters.type import AdapterType

logger = logging.getLogger(__name__)


class UnifiedAudioApp:
    """统一音频应用 - 支持多种适配器"""

    def __init__(self, adapter_type: AdapterType, config: dict, use_tts_pcm: bool = True):
        self.adapter_type = adapter_type
        self.config = config
        self.use_tts_pcm = use_tts_pcm

        # 音频相关
        self.p = pyaudio.PyAudio()
        # 使用有限队列避免延迟累积
        self.send_queue = queue.Queue()  # 最多缓存50个音频块
        self.play_queue = queue.Queue()  # 播放队列更小，减少延迟
        self.stop_event = threading.Event()

        # 线程
        self.recorder = None
        self.player = None

        # 适配器
        self.adapter = None

        # 任务
        self.sender_task = None
        self.receiver_task = None

    async def initialize(self) -> bool:
        """初始化应用"""
        try:
            # 如果是本地适配器，需要配置TTS音频格式
            if self.use_tts_pcm:
                # 临时导入配置
                from src.volcengine.config import start_session_req
                logger.info("配置为请求 PCM 格式的TTS音频流 (24kHz, Float32)")
                start_session_req['tts'] = {
                    "audio_config": {
                        "format": "pcm",
                        "sample_rate": 24000
                    }
                }

            # 创建适配器
            if self.adapter_type == AdapterType.LOCAL:
                from src.adapters.local_adapter import LocalAudioAdapter

                # 提取额外参数，包含reconnect_timeout
                extra_params = self.config.get('extra_params', {})
                if 'reconnect_timeout' in self.config:
                    extra_params['reconnect_timeout'] = self.config['reconnect_timeout']

                connection_config = LocalConnectionConfig(
                    app_id=self.config['app_id'],
                    access_token=self.config['access_token'],
                    **extra_params
                )
                self.adapter = LocalAudioAdapter(connection_config)

            elif self.adapter_type == AdapterType.BROWSER:
                from src.adapters.browser_adapter import BrowserAudioAdapter

                connection_config = BrowserConnectionConfig(
                    proxy_url=self.config['proxy_url'],
                    app_id=self.config['app_id'],
                    access_token=self.config['access_token'],
                    **self.config.get('extra_params', {})
                )
                self.adapter = BrowserAudioAdapter(connection_config)

            elif self.adapter_type == AdapterType.TOUCH_DESIGNER:
                from src.adapters.touchdesigner_adapter import TouchDesignerAudioAdapter, TouchDesignerConnectionConfig

                connection_config = TouchDesignerConnectionConfig(
                    td_ip=self.config['td_ip'],
                    td_port=self.config['td_port'],
                    listen_port=self.config.get('listen_port', 7001),
                    app_id=self.config['app_id'],
                    access_token=self.config['access_token'],
                    **self.config.get('extra_params', {})
                )
                self.adapter = TouchDesignerAudioAdapter(connection_config)

            elif self.adapter_type == AdapterType.TOUCH_DESIGNER_WEBRTC:
                from src.adapters.touchdesigner_webrtc_adapter import TouchDesignerWebRTCAudioAdapter, \
                    TouchDesignerWebRTCConnectionConfig

                connection_config = TouchDesignerWebRTCConnectionConfig(
                    signaling_port=self.config['signaling_port'],
                    app_id=self.config['app_id'],
                    access_token=self.config['access_token'],
                    **self.config.get('extra_params', {})
                )
                self.adapter = TouchDesignerWebRTCAudioAdapter(connection_config)

            elif self.adapter_type == AdapterType.TOUCH_DESIGNER_WEBRTC_PROPER:
                from src.adapters.touchdesigner_webrtc_proper_adapter import (
                    TouchDesignerProperWebRTCAudioAdapter,
                    TouchDesignerProperWebRTCConnectionConfig
                )
                connection_config = TouchDesignerProperWebRTCConnectionConfig(
                    signaling_port=self.config['signaling_port'],
                    webrtc_port=self.config['webrtc_port'],
                    app_id=self.config['app_id'],
                    access_token=self.config['access_token'],
                    **self.config.get('extra_params', {})
                )
                self.adapter = TouchDesignerProperWebRTCAudioAdapter(connection_config)

            elif self.adapter_type == AdapterType.TEXT_INPUT:
                from src.adapters.text_input_adapter import TextInputAdapter

                connection_config = LocalConnectionConfig(
                    app_id=self.config['app_id'],
                    access_token=self.config['access_token'],
                    **self.config.get('extra_params', {})
                )
                self.adapter = TextInputAdapter(connection_config)

            else:
                raise Exception(f"不支持的适配器类型: {self.adapter_type}")
            logger.info(f"创建 {self.adapter_type.value} 适配器成功")

            # 连接
            if await self.adapter.connect():
                logger.info(f"适配器连接成功")
                return True
            else:
                logger.error("适配器连接失败")
                return False

        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False

    async def run(self):
        """运行主循环"""
        if not await self.initialize():
            return

        self.recorder, self.player = await self.adapter.setup_audio_devices(self.p, self.stop_event)

        try:
            logger.info("启动音频处理任务")

            # 提示用户如何使用
            print("\n" + "=" * 60)
            if self.adapter_type == AdapterType.TEXT_INPUT:
                print("💬 文字输入对话已就绪！")
                print("💡 使用提示：")
                print("   - 在提示符处输入文字，AI会朗读回复")
                print("   - 输入 'quit' 或 'exit' 退出程序")
                print("   - 按 Ctrl+C 也可以退出程序")
            else:
                print("🎤 语音对话已就绪！")
                print("💡 使用提示：")
                print("   - 正常音量说话即可，系统会自动检测语音活动")
                print("   - 说话时会看到 🎤 发送语音 的提示")
                print("   - 静音时会显示 🔇 静音检测中 的状态")
                print("   - 按 Ctrl+C 退出程序")
            print("=" * 60 + "\n")

            # 启动发送和接收任务
            # 使用适配器内部的发送队列和播放队列
            self.sender_task = asyncio.create_task(
                self.adapter.run_sender_task(self.adapter._send_queue, self.stop_event))
            self.receiver_task = asyncio.create_task(
                self.adapter.run_receiver_task(self.adapter._play_queue, self.stop_event))

            # 等待任务完成
            await asyncio.gather(self.sender_task, self.receiver_task)

        except KeyboardInterrupt:
            logger.info("收到中断信号")
        except Exception as e:
            logger.error(f"运行时错误: {e}")
        finally:
            await self.cleanup()

    async def cleanup(self):
        """清理资源"""
        logger.info("开始清理资源...")

        # 停止事件
        self.stop_event.set()

        # 取消任务
        if self.sender_task:
            self.sender_task.cancel()
        if self.receiver_task:
            self.receiver_task.cancel()

        # 等待任务结束
        if self.sender_task:
            try:
                await self.sender_task
            except asyncio.CancelledError:
                pass
        if self.receiver_task:
            try:
                await self.receiver_task
            except asyncio.CancelledError:
                pass

        # 断开适配器
        if self.adapter:
            await self.adapter.disconnect()

        # 等待线程结束
        if self.recorder and self.recorder.is_alive():
            self.recorder.join(timeout=5)
        if self.player and self.player.is_alive():
            self.player.join(timeout=5)

        # 关闭音频
        self.p.terminate()

        logger.info("资源清理完成")
