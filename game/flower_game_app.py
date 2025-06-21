import asyncio

from game.flower_game_adapter import FlowerGameAdapter
from logger import logger
from src.adapters import AdapterType
from src.unified_app import UnifiedAudioApp
from src.volcengine import protocol


class FlowerGameApp(UnifiedAudioApp):
    """植物计划游戏应用"""
    
    def __init__(self, adapter_type: AdapterType, config: dict, use_tts_pcm: bool = True):
        super().__init__(adapter_type, config, use_tts_pcm)
        self.game_adapter = None
        self.user_text = ''
        self.is_waiting_custom_reply = False
        # 首条默认放行
        self.cur_tts_type = "chat_tts_texxt"
    
    async def run(self):
        """运行游戏应用"""
        logger.info("=== 未来植物计划展区游戏启动 ===")
        
        # 初始化应用（使用父类方法）
        success = await self.initialize()
        if not success:
            logger.error("应用初始化失败")
            return
        
        # 包装为游戏适配器
        self.game_adapter = FlowerGameAdapter(self.adapter)
        
        # 启动游戏
        try:
            await self._run_game()
        except Exception as e:
            logger.error(f"游戏运行异常: {e}")
        finally:
            await self.cleanup()
    
    async def _run_game(self):
        """运行游戏主循环"""
        # 发送欢迎消息
        
        # 设置音频设备
        recorder, player = await self.game_adapter.setup_audio_devices(self.p, self.stop_event)
        if not recorder or not player:
            logger.error("音频设备设置失败")
            return
        
        try:
            await self.game_adapter.send_welcome()
            
            logger.info("🎤 植物计划游戏对话已就绪！")
            print("\n" + "=" * 60)
            print("🌱 欢迎来到未来植物计划展区！")
            print("💡 游戏提示：")
            print("   - 听到欢迎消息后，请说出你的姓名")
            print("   - 依次回答三个问题，选择A、B、C、D或E")
            print("   - 游戏结束后会给出你的总分和评价")
            print("   - 按 Ctrl+C 可以随时退出")
            print("=" * 60 + "\n")
            
            # 启动音频处理任务
            sender_task = asyncio.create_task(
                self.game_adapter.run_sender_task(self.game_adapter._send_queue, self.stop_event)
            )
            receiver_task = asyncio.create_task(
                self._run_game_receiver_task(self.game_adapter._play_queue, self.stop_event)
            )
            
            # 等待游戏结束或用户中断
            await asyncio.gather(sender_task, receiver_task)
        
        except KeyboardInterrupt:
            logger.info("用户中断游戏")
            self.stop_event.set()
    
    async def _run_game_receiver_task(self, play_queue, stop_event):
        """运行游戏接收任务，处理ASR结果"""
        logger.info("游戏接收任务启动")
        
        while self.game_adapter.is_connected and not stop_event.is_set():
            try:
                # 从适配器的响应队列获取数据
                response = await asyncio.wait_for(self.game_adapter.response_queue.get(), timeout=1.0)
                if not response or "error" in response:
                    continue
                
                event = response.get('event')
                event_name = protocol.ServerEvent(event).name
                payload = response.get('payload_msg', {})
                if isinstance(payload, dict):
                    logger.info(f"收到事件: {event_name}({event}) - {payload}")
                else:
                    logger.info(f"收到事件: {event_name}({event})")
                
                if event == protocol.ServerEvent.TTS_RESPONSE:
                    # 音频响应 - 放入播放队列
                    logger.debug(f"收到TTS音频数据: {type(payload)}, 大小: {len(payload) if isinstance(payload, bytes) else 'N/A'}")
                    
                    try:
                        # default 是 AI 自动回复，我们直接跳过
                        if self.cur_tts_type == "default":
                            logger.warn("skip since default")
                            continue
                        
                        if play_queue.full():
                            play_queue.get_nowait()
                        play_queue.put_nowait(response)
                    except:
                        # 处理队列操作异常
                        pass
                
                elif event == protocol.ServerEvent.TTS_SENTENCE_START:
                    new_tts_type = payload.get("tts_type")
                    logger.warn(f"tts_type change: {self.cur_tts_type} --> {new_tts_type}")
                    self.cur_tts_type = new_tts_type
                
                elif event == protocol.ServerEvent.TTS_ENDED:
                    # TTS播放结束，可以接受键盘输入
                    if hasattr(self.game_adapter, 'is_playing_audio'):
                        self.game_adapter.is_playing_audio = False
                    if hasattr(self.game_adapter, 'pending_keyboard_input') and self.game_adapter.pending_keyboard_input:
                        print("\n请输入你的选择 (1-5): ", end="", flush=True)
                
                elif event == protocol.ServerEvent.ASR_INFO:
                    # ASR识别结果 - 处理用户语音
                    try:
                        while not play_queue.empty():
                            play_queue.get_nowait()  # 清空播放队列，打断AI语音
                    except:
                        pass
                elif event == protocol.ServerEvent.ASR_RESPONSE:
                    self.user_text = response.get("payload_msg", {}).get("extra", {}).get('origin_text', "")
                elif event == protocol.ServerEvent.ASR_ENDED:
                    # 处理用户语音输入
                    logger.info(f"[User Text]: {self.user_text}")
                    await self.game_adapter.process_user_speech(self.user_text)
            
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"游戏接收任务异常: {e}")
                break
        
        logger.info("游戏接收任务结束")
