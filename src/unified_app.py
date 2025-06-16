import asyncio
import json
import logging
import queue
import threading
from typing import Optional
import argparse

import pyaudio

from src.adapters.base import AdapterType
from src.adapters.factory import AdapterFactory
from src.audio.utils.select_audio_device import select_audio_device
from src.utils import recorder_thread, player_thread
from src.config import VOLCENGINE_APP_ID, VOLCENGINE_ACCESS_TOKEN
from src.volcengine import protocol

logger = logging.getLogger(__name__)


class UnifiedAudioApp:
    """统一音频应用 - 支持多种适配器"""
    
    def __init__(self, adapter_type: AdapterType, config: dict, use_tts_pcm: bool = True):
        self.adapter_type = adapter_type
        self.config = config
        self.use_tts_pcm = use_tts_pcm
        
        # 音频相关
        self.p = pyaudio.PyAudio()
        self.send_queue = queue.Queue()
        self.play_queue = queue.Queue()
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
            if self.adapter_type == AdapterType.LOCAL and self.use_tts_pcm:
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
            self.adapter = AdapterFactory.create_adapter(self.adapter_type, self.config)
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
    
    async def setup_audio_devices(self) -> bool:
        """设置音频设备"""
        try:
            # 选择输入设备
            input_device_index = select_audio_device(self.p, "选择输入设备 (麦克风):", 'input')
            if input_device_index is None:
                return False
            
            # 选择输出设备
            output_device_index = select_audio_device(self.p, "选择输出设备 (扬声器):", 'output')
            if output_device_index is None:
                return False
            
            # 启动录音和播放线程
            self.recorder = threading.Thread(
                target=recorder_thread, 
                args=(self.p, input_device_index, self.send_queue, 1024, self.stop_event)
            )
            self.player = threading.Thread(
                target=player_thread, 
                args=(self.p, output_device_index, self.play_queue, 1024, self.stop_event)
            )
            
            self.recorder.start()
            self.player.start()
            
            logger.info("音频设备设置完成")
            return True
            
        except Exception as e:
            logger.error(f"音频设备设置失败: {e}")
            return False
    
    async def run(self):
        """运行主循环"""
        if not await self.initialize():
            return
        
        if not await self.setup_audio_devices():
            await self.cleanup()
            return
        
        try:
            logger.info("启动音频处理任务")
            
            # 发送一个初始问候来激活对话
            await asyncio.sleep(1)  # 等待连接稳定
            await self.adapter.send_text("你好")
            logger.info("已发送初始问候消息")
            
            # 启动发送和接收任务
            self.sender_task = asyncio.create_task(self._sender_task())
            self.receiver_task = asyncio.create_task(self._receiver_task())
            
            # 等待任务完成
            await asyncio.gather(self.sender_task, self.receiver_task)
            
        except KeyboardInterrupt:
            logger.info("收到中断信号")
        except Exception as e:
            logger.error(f"运行时错误: {e}")
        finally:
            await self.cleanup()
    
    async def _sender_task(self):
        """发送音频数据任务"""
        logger.info("发送任务启动")
        audio_count = 0
        
        while not self.stop_event.is_set() and self.adapter and self.adapter.is_connected:
            try:
                # 从队列获取音频数据
                audio_chunk = await asyncio.to_thread(self.send_queue.get, timeout=1.0)
                audio_count += 1
                
                # 发送给适配器
                success = await self.adapter.send_audio(audio_chunk)
                if not success:
                    logger.warning("发送音频数据失败")
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"发送任务异常: {e}")
                break
        
        logger.info(f"发送任务结束，总共发送 {audio_count} 个音频chunk")
    
    async def _receiver_task(self):
        """接收音频数据任务"""
        logger.info("接收任务启动")
        
        # 如果是本地适配器，直接从客户端接收响应
        if self.adapter_type == AdapterType.LOCAL and hasattr(self.adapter, 'client'):
            await self._receiver_task_local()
        else:
            await self._receiver_task_generic()
        
        logger.info("接收任务结束")
    
    async def _receiver_task_local(self):
        """本地适配器的接收任务 - 从适配器队列接收响应"""
        while self.adapter.is_connected and not self.stop_event.is_set():
            try:
                # 从适配器的响应队列获取数据，而不是直接调用client.on_response()
                response = await asyncio.wait_for(self.adapter.response_queue.get(), timeout=1.0)
                if not response or "error" in response:
                    continue
                
                event = response.get('event')
                if event == protocol.ServerEvent.TTS_RESPONSE:
                    # 音频响应
                    self.play_queue.put(response)
                elif event:
                    # 其他事件，友好显示
                    try:
                        event_name = protocol.ServerEvent(event).name
                        payload = response.get('payload_msg', {})
                        if isinstance(payload, dict):
                            logger.info(f"收到事件: {event_name} - {json.dumps(payload, ensure_ascii=False)}")
                        else:
                            logger.info(f"收到事件: {event_name}")
                    except ValueError:
                        logger.info(f"收到未知事件: {event}")
                        
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"接收响应失败: {e}")
                break
    
    async def _receiver_task_generic(self):
        """通用适配器的接收任务"""
        received_count = 0
        
        try:
            async for audio_data in self.adapter.receive_audio():
                if self.stop_event.is_set():
                    break
                
                received_count += 1
                logger.debug(f"收到音频数据 #{received_count}，大小: {len(audio_data)} bytes")
                
                # 将音频数据放入播放队列
                try:
                    self.play_queue.put_nowait({"payload_msg": audio_data})
                except queue.Full:
                    logger.warning("播放队列已满，丢弃音频数据")
                    
        except Exception as e:
            logger.error(f"接收任务异常: {e}")
        
        if received_count > 0:
            logger.info(f"总共接收 {received_count} 个音频数据")
    
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


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="统一音频应用")
    parser.add_argument(
        "--adapter", 
        choices=["local", "browser"], 
        default="local",
        help="选择适配器类型"
    )
    parser.add_argument(
        "--proxy-url", 
        default="ws://localhost:8765",
        help="代理服务器URL（仅browser模式需要）"
    )
    parser.add_argument(
        "--use-pcm",
        action="store_true",
        default=True,
        help="使用PCM格式请求TTS音频（默认启用）"
    )
    
    args = parser.parse_args()
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if args.use_pcm:
        print("默认使用PCM模式请求TTS音频")
    
    # 确定适配器类型
    if args.adapter == "local":
        adapter_type = AdapterType.LOCAL
        config = {
            "app_id": VOLCENGINE_APP_ID,
            "access_token": VOLCENGINE_ACCESS_TOKEN
        }
    elif args.adapter == "browser":
        adapter_type = AdapterType.BROWSER
        config = {
            "proxy_url": args.proxy_url,
            "app_id": VOLCENGINE_APP_ID,
            "access_token": VOLCENGINE_ACCESS_TOKEN
        }
    else:
        logger.error(f"不支持的适配器类型: {args.adapter}")
        return
    
    # 创建应用
    app = UnifiedAudioApp(adapter_type, config, use_tts_pcm=args.use_pcm)
    
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("\n检测到用户中断 (Ctrl+C)")


if __name__ == "__main__":
    main()