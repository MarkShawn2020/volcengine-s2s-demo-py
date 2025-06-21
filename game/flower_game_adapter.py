import asyncio

from logger import logger
from game.config import game


class FlowerGameAdapter:
    """植物计划游戏适配器"""
    
    def __init__(self, original_adapter):
        self.original_adapter = original_adapter
        self.game_state = "waiting_name"  # waiting_name, question_1, question_2, question_3, finished
        self.user_name = ""
        self.scores = []  # 存储三个问题的得分
        self.current_question = 0
        self.waiting_custom_reply = False
    
    def __getattr__(self, name):
        """代理其他方法到原始适配器"""
        return getattr(self.original_adapter, name)
    
    async def send_welcome(self):
        """发送游戏欢迎消息"""
        await self.original_adapter.client.push_text(game['welcome_msg'])
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
        self.waiting_custom_reply = True
        if question_index >= len(game['questions']):
            await self._finish_game()
            return
            
        self.current_question = question_index
        self.game_state = f"question_{question_index + 1}"
        
        question_text = game['questions'][question_index]
        await self._send_chat_tts_text_packets(question_text)
        logger.info(f"提问第{question_index + 1}个问题")
    
    async def _handle_question_answer(self, text: str):
        self.waiting_custom_reply = False
        next_question = self.current_question + 1
        await self._ask_question(next_question)
    
    def _infer_option_from_text(self, text: str) -> str:
        """从文本中推断选项"""
        text = text.upper()
        
        # 常见的选项表达方式
        option_keywords = {
            '1': ['好朋友', '朋友', '平静', '和谐', '秩序'],
            '2': ['改善', '生活', '热烈', '科技', '奇观'],
            '3': ['威胁', '控制', '忐忑', '混沌', '未知'],
            '4': ['分离', '人类', '好奇', '自然', '复苏'],
            '5': ['无所谓', '超然', '克制', '冷静']
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
        result_msg = f"{self.user_name}，感谢你的参与！"
        
        
        evaluation = ""
        # todo: 由于分数系统现在有问题，计划改成完全随机
        # 根据分数给出评价
        # if total_score <= 60:
        #     evaluation = "你倾向于平和与稳定，喜欢和谐的环境。"
        # elif total_score <= 120:
        #     evaluation = "你对科技和改善持开放态度，相信美好的未来。"
        # elif total_score <= 180:
        #     evaluation = "你对未来既有期待又有担忧，保持着理性的思考。"
        # else:
        #     evaluation = "你是一个充满好奇心的探索者，敢于面对未知的挑战。"
        
        final_msg = f"{result_msg}{evaluation}希望你在未来植物计划展区度过愉快的时光！"
        await self._send_chat_tts_text_packets(final_msg)
        
        logger.info(f"游戏结束，{self.user_name} 总分: {total_score}, 各题得分: {self.scores}")
    
    async def _send_chat_tts_text_packets(self, text: str) -> bool:
        """发送ChatTTS文本包（复制自原始适配器）"""
        return await self.original_adapter._send_chat_tts_text_packets(text)
