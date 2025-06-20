import argparse
import asyncio
import json
import re
import logging

import dotenv

dotenv.load_dotenv()

from src.adapters.type import AdapterType
from src.config import VOLCENGINE_APP_ID, VOLCENGINE_ACCESS_TOKEN
from src.unified_app import UnifiedAudioApp
from src.volcengine import protocol
from logger import logger


class FlowerGameAdapter:
    """植物计划游戏适配器"""
    
    def __init__(self, original_adapter):
        self.original_adapter = original_adapter
        self.game_state = "waiting_name"  # waiting_name, question_1, question_2, question_3, finished
        self.user_name = ""
        self.scores = []  # 存储三个问题的得分
        self.current_question = 0
        
        # 游戏问题和选项分值
        self.questions = [
            "你认为AI将如何影响我们的未来？请选择你的看法：A 成为好朋友，B 改善生活，C 威胁控制，D 与人类分离，E 无所谓",
            "你心中的未来世界是什么样？请选择你想要的未来：A 和谐秩序，B 科技奇观，C 混沌未知，D 自然复苏，E 冷静克制",
            "你此刻的情绪是？请选择你的感受：A 平静，B 热烈，C 忐忑，D 好奇，E 超然"
        ]
        
        # 选项分值映射
        self.option_scores = {
            'A': 0, 'B': 20, 'C': 40, 'D': 60, 'E': 80
        }
    
    def __getattr__(self, name):
        """代理其他方法到原始适配器"""
        return getattr(self.original_adapter, name)
    
    async def send_welcome(self):
        """发送游戏欢迎消息"""
        welcome_msg = "你好，欢迎来到未来植物计划展区，站在指定区域，说出你的姓名，然后开始你的互动之旅。"
        await self.original_adapter.client.push_text(welcome_msg)
        self.game_state = "waiting_name"
        logger.info("游戏开始，等待用户说出姓名")
    
    async def process_user_speech(self, text: str):
        """处理用户语音输入"""
        text = text.strip()
        if not text:
            return
            
        logger.info(f"用户语音: {text}, 当前状态: {self.game_state}")
        
        if self.game_state == "waiting_name":
            await self._handle_name_input(text)
        elif self.game_state.startswith("question_"):
            await self._handle_question_answer(text)
    
    async def _handle_name_input(self, text: str):
        """处理姓名输入"""
        # 简单提取姓名（可以根据需要改进）
        self.user_name = text
        logger.info(f"用户姓名: {self.user_name}")
        
        # 问候并开始第一个问题
        greeting = f"你好，{self.user_name}！现在开始我们的互动问答。"
        await self._send_chat_tts_text_packets(greeting)
        
        # 稍等一下再问第一个问题
        await asyncio.sleep(2)
        await self._ask_question(0)
    
    async def _ask_question(self, question_index: int):
        """提问"""
        if question_index >= len(self.questions):
            await self._finish_game()
            return
            
        self.current_question = question_index
        self.game_state = f"question_{question_index + 1}"
        
        question_text = self.questions[question_index]
        await self._send_chat_tts_text_packets(question_text)
        logger.info(f"提问第{question_index + 1}个问题")
    
    async def _handle_question_answer(self, text: str):
        """处理问题回答"""
        # 提取选项 A, B, C, D, E
        option_match = re.search(r'[ABCDE]', text.upper())
        if not option_match:
            # 如果没有明确选项，尝试从语音中推断
            option = self._infer_option_from_text(text)
        else:
            option = option_match.group(0)
        
        if option not in self.option_scores:
            # 无法识别选项，要求重新回答
            retry_msg = "抱歉，我没有听清楚你的选择，请重新选择 A、B、C、D 或 E。"
            await self._send_chat_tts_text_packets(retry_msg)
            return
        
        # 记录得分
        score = self.option_scores[option]
        self.scores.append(score)
        logger.info(f"用户选择: {option}, 得分: {score}")
        
        # 确认选择
        confirm_msg = f"好的，你选择了 {option}。"
        await self._send_chat_tts_text_packets(confirm_msg)
        
        # 继续下一个问题或结束游戏
        await asyncio.sleep(1)
        next_question = self.current_question + 1
        if next_question < len(self.questions):
            await self._ask_question(next_question)
        else:
            await self._finish_game()
    
    def _infer_option_from_text(self, text: str) -> str:
        """从文本中推断选项"""
        text = text.upper()
        
        # 常见的选项表达方式
        option_keywords = {
            'A': ['好朋友', '朋友', '平静', '和谐', '秩序'],
            'B': ['改善', '生活', '热烈', '科技', '奇观'],
            'C': ['威胁', '控制', '忐忑', '混沌', '未知'],
            'D': ['分离', '人类', '好奇', '自然', '复苏'],
            'E': ['无所谓', '超然', '克制', '冷静']
        }
        
        for option, keywords in option_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return option
        
        # 如果没有匹配到关键词，返回空字符串
        return ""
    
    async def _finish_game(self):
        """结束游戏并计算总分"""
        total_score = sum(self.scores)
        self.game_state = "finished"
        
        # 生成总结消息
        result_msg = f"{self.user_name}，感谢你的参与！你的总分是 {total_score} 分。"
        
        # 根据分数给出评价
        if total_score <= 60:
            evaluation = "你倾向于平和与稳定，喜欢和谐的环境。"
        elif total_score <= 120:
            evaluation = "你对科技和改善持开放态度，相信美好的未来。"
        elif total_score <= 180:
            evaluation = "你对未来既有期待又有担忧，保持着理性的思考。"
        else:
            evaluation = "你是一个充满好奇心的探索者，敢于面对未知的挑战。"
        
        final_msg = f"{result_msg}{evaluation}希望你在未来植物计划展区度过愉快的时光！"
        await self._send_chat_tts_text_packets(final_msg)
        
        logger.info(f"游戏结束，{self.user_name} 总分: {total_score}, 各题得分: {self.scores}")
    
    async def _send_chat_tts_text_packets(self, text: str) -> bool:
        """发送ChatTTS文本包（复制自原始适配器）"""
        return await self.original_adapter._send_chat_tts_text_packets(text)


class FlowerGameApp(UnifiedAudioApp):
    """植物计划游戏应用"""
    
    def __init__(self, adapter_type: AdapterType, config: dict, use_tts_pcm: bool = True):
        super().__init__(adapter_type, config, use_tts_pcm)
        self.game_adapter = None
        self.user_text = ''
    
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
                    
                try:
                    pass
                    # logger.info(f"[Response]: {response}")
                except Exception as e:
                    pass
            
                event = response.get('event')
                if event == protocol.ServerEvent.TTS_RESPONSE:
                    # 音频响应 - 放入播放队列
                    audio_data = response.get('payload_msg')
                    logger.debug(f"收到TTS音频数据: {type(audio_data)}, 大小: {len(audio_data) if isinstance(audio_data, bytes) else 'N/A'}")
                    
                    try:
                        if play_queue.full():
                            play_queue.get_nowait()
                        play_queue.put_nowait(response)
                    except:
                        # 处理队列操作异常
                        pass
                    
                elif event == protocol.ServerEvent.ASR_RESPONSE:
                    self.user_text = response.get("payload_msg", {}).get("extra", {}).get('origin_text', "")
                
                elif event == protocol.ServerEvent.ASR_INFO:
                    # ASR识别结果 - 处理用户语音
                    try:
                        while not play_queue.empty():
                            play_queue.get_nowait()  # 清空播放队列，打断AI语音
                    except:
                        pass
                    # 处理用户语音输入
                    logger.info(f"[User Text]: {self.user_text}")
                    await self.game_adapter.process_user_speech(self.user_text)
                elif event:
                    # 其他事件
                    try:
                        event_name = protocol.ServerEvent(event).name
                        payload = response.get('payload_msg', {})
                        if isinstance(payload, dict):
                            logger.debug(f"收到事件: {event_name} - {payload}")
                        else:
                            logger.debug(f"收到事件: {event_name}")
                    except ValueError:
                        logger.debug(f"收到未知事件: {event}")
            
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"游戏接收任务异常: {e}")
                break
        
        logger.info("游戏接收任务结束")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="未来植物计划展区游戏")
    parser.add_argument(
        "--adapter", 
        choices=["local"], 
        default="local", 
        help="选择适配器类型（目前只支持local）"
    )
    parser.add_argument(
        "--use-pcm", action="store_true", default=True, help="使用PCM格式请求TTS音频（默认启用）"
    )

    args = parser.parse_args()

    if args.use_pcm:
        print("默认使用PCM模式请求TTS音频")

    # 配置
    config = {
        "app_id": VOLCENGINE_APP_ID,
        "access_token": VOLCENGINE_ACCESS_TOKEN
    }

    # 创建游戏应用
    app = FlowerGameApp(AdapterType.LOCAL, config, use_tts_pcm=args.use_pcm)

    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("\n检测到用户中断 (Ctrl+C)")


if __name__ == "__main__":
    main()
