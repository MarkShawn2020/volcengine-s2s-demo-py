import asyncio
import threading
import time
from pynput import keyboard

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
        self._keyboard_thread = None
        self._keyboard_stop_event = threading.Event()
        self._event_loop = None
    
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
        
        # 保存事件循环引用
        self._event_loop = asyncio.get_event_loop()
        
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
        
        # 启动键盘监听线程
        self._start_keyboard_monitor()
        
        # 设置键盘回调函数，按0键重新开始游戏
        # self.game_adapter.keyboard_callback = self._restart_game
        
        try:
            await self.game_adapter.send_welcome()
            
            logger.info("🎤 植物计划游戏对话已就绪！")
            print("\n" + "=" * 60)
            print("🌱 欢迎来到未来植物计划展区！")
            print("💡 游戏提示：")
            print("   - 听到欢迎消息后，请说出你的姓名")
            print("   - 依次回答三个问题，选择A、B、C、D或E")
            print("   - 游戏结束后会给出你的总分和评价")
            print("   - 按 0 键可以重新开始游戏")
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
        finally:
            self._stop_keyboard_monitor()
    
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
    
    def _restart_game(self):
        """重新开始游戏"""
        logger.info("🔄 检测到0键按下，重新开始游戏")
        print("\n🔄 重新开始游戏...\n")
        
        # 重置游戏状态
        self.game_adapter.game_state = "waiting_name"
        self.game_adapter.user_name = ""
        self.game_adapter.scores = []
        self.game_adapter.current_question = 0
        self.game_adapter.waiting_custom_reply = False
        
        try:
            # 清空播放队列
            while not self.game_adapter._play_queue.empty():
                self.game_adapter._play_queue.get_nowait()
        except:
            pass
        
        # 使用正确的方式在线程中调用异步方法
        if self._event_loop and not self._event_loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(
                self._restart_session_and_game(), 
                self._event_loop
            )
            try:
                future.result(timeout=10.0)
                logger.info("✅ 游戏重置完成，已重新启动会话并发送欢迎消息")
            except Exception as e:
                logger.error(f"❌ 重置游戏失败: {e}")
        else:
            logger.error("❌ 事件循环不可用，无法重置游戏")
    
    async def _restart_session_and_game(self):
        """重启会话并开始游戏"""
        try:
            # 获取底层客户端
            client = self.adapter.client
            
            logger.info("🔄 正在关闭当前会话...")
            # 先关闭当前会话
            await client.request_stop_session()
            logger.info("✅ 会话关闭请求已发送")
            
            logger.info("🔄 正在启动新会话...")
            # 生成新的会话ID
            import uuid
            client.session_id = str(uuid.uuid4())
            logger.info(f"🆔 新会话ID: {client.session_id[:8]}...")
            
            # 重新启动会话
            await client.request_start_session()
            logger.info("✅ 新会话启动请求已发送")
            
            # 短暂等待
            logger.info("⏳ 短暂等待...")
            await asyncio.sleep(0.5)
            
            logger.info("🔄 正在发送欢迎消息...")
            # 发送欢迎消息，添加超时保护
            await self.game_adapter.send_welcome()
            logger.info("✅ 欢迎消息已发送")
            
            logger.info("✅ 会话重启和游戏重置完成")
            
        except asyncio.TimeoutError as e:
            logger.error(f"❌ 重启会话超时: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ 重启会话失败: {e}", exc_info=True)
            raise
    
    def _start_keyboard_monitor(self):
        """启动键盘监听线程"""
        def keyboard_monitor():
            logger.info("🎹 键盘监听线程启动")
            
            def on_press(key):
                try:
                    # 只监控0键
                    if hasattr(key, 'char') and key.char == '0':
                        logger.info("🎯 检测到0键按下!")
                        print("\n" + "="*50)
                        print("🔄 检测到0键，正在重置游戏...")
                        print("="*50)
                        self._restart_game()
                    elif str(key) == 'Key.kp_0':
                        logger.info("🎯 检测到数字键盘0键按下!")
                        print("\n" + "="*50)
                        print("🔄 检测到数字键盘0键，正在重置游戏...")
                        print("="*50)
                        self._restart_game()
                except Exception as e:
                    logger.error(f"按键处理异常: {e}")
            
            def on_release(key):
                # 可以在这里处理按键释放事件，现在暂时不需要
                pass
            
            # 使用pynput的监听器
            listener = keyboard.Listener(
                on_press=on_press,
                on_release=on_release
            )
            listener.start()
            
            try:
                # 修复：使用独立的停止事件和时间睡眠，避免与主线程的stop_event冲突
                while not self._keyboard_stop_event.is_set():
                    time.sleep(0.1)  # 使用time.sleep而不是event.wait
            finally:
                listener.stop()
                logger.info("🎹 键盘监听线程结束")
        
        # 重置键盘停止事件
        self._keyboard_stop_event.clear()
        self._keyboard_thread = threading.Thread(target=keyboard_monitor, daemon=True)
        self._keyboard_thread.start()
        logger.info("✅ 键盘监听线程已启动")
        
        # 添加权限检查提示
        print("\n" + "🔔" * 50)
        print("🔔 pynput键盘监听已启动！")
        print("🔔 如果按0键无反应，请检查macOS系统偏好设置：")
        print("🔔 系统偏好设置 > 安全性与隐私 > 隐私 > 辅助功能")
        print("🔔 确保您的终端应用有权限访问")
        print("🔔 现在请按任意键测试键盘监听是否工作...")
        print("🔔" * 50 + "\n")
    
    def _stop_keyboard_monitor(self):
        """停止键盘监听线程"""
        logger.info("🛑 正在停止键盘监听线程...")
        
        # 设置停止标志
        self._keyboard_stop_event.set()
        
        if self._keyboard_thread and self._keyboard_thread.is_alive():
            self._keyboard_thread.join(timeout=2.0)
            if self._keyboard_thread.is_alive():
                logger.warning("⚠️ 键盘监听线程未能在2秒内正常结束")
            else:
                logger.info("✅ 键盘监听线程已正常结束")
        
        self._keyboard_thread = None
