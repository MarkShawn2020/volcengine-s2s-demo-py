"""
TouchDesigner集成脚本
这个脚本应该在TouchDesigner的Execute DAT中运行
提供了完整的音频输入输出控制
"""

import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

try:
    from td.audio_handler import TDSimpleAudio
    import numpy as np
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保所有依赖都已安装")


class TouchDesignerVoiceChat:
    """TouchDesigner语音对话控制器"""
    
    def __init__(self):
        self.audio_handler = TDSimpleAudio()
        self.is_enabled = False
        self.last_status = ""
        
        # 音频参数
        self.sample_rate = 16000
        self.buffer_size = 1600  # 100ms buffer
        
    def enable(self):
        """启用语音对话"""
        if not self.is_enabled:
            self.audio_handler.start()
            self.is_enabled = True
            print("TouchDesigner语音对话已启用")
            
    def disable(self):
        """禁用语音对话"""
        if self.is_enabled:
            self.audio_handler.stop()
            self.is_enabled = False
            print("TouchDesigner语音对话已禁用")
            
    def toggle(self):
        """切换启用状态"""
        if self.is_enabled:
            self.disable()
        else:
            self.enable()
            
    def send_audio_input(self, audio_input):
        """
        发送音频输入到语音对话系统
        
        Args:
            audio_input: 音频输入数据 (numpy array 或 TouchDesigner Audio CHOP)
        """
        if not self.is_enabled:
            return False
            
        try:
            # 处理TouchDesigner Audio CHOP输入
            if hasattr(audio_input, 'numpyArray'):
                # TouchDesigner Audio CHOP
                audio_data = audio_input.numpyArray()
                if len(audio_data.shape) > 1:
                    # 多声道，取第一个声道
                    audio_data = audio_data[0, :]
            elif isinstance(audio_data, np.ndarray):
                audio_data = audio_input
            else:
                print(f"不支持的音频输入类型: {type(audio_input)}")
                return False
                
            # 确保音频长度合适
            if len(audio_data) > 0:
                return self.audio_handler.send_audio(audio_data)
                
        except Exception as e:
            print(f"发送音频输入失败: {e}")
            
        return False
        
    def get_audio_output(self):
        """
        获取语音对话系统的音频输出
        
        Returns:
            numpy.ndarray: 音频输出数据，可以直接用于TouchDesigner Audio CHOP
        """
        if not self.is_enabled:
            return None
            
        return self.audio_handler.get_latest_audio()
        
    def send_text_message(self, text):
        """
        发送文本消息
        
        Args:
            text: 要发送的文本
        """
        if not self.is_enabled:
            return False
            
        return self.audio_handler.send_text(str(text))
        
    def get_status(self):
        """获取当前状态"""
        if not self.is_enabled:
            return "已禁用"
            
        status = self.audio_handler.get_latest_status()
        if status:
            self.last_status = status
            
        return self.last_status if self.last_status else "等待中..."
        
    @property
    def enabled(self):
        """检查是否已启用"""
        return self.is_enabled
        
    @property
    def connected(self):
        """检查是否已连接"""
        return self.is_enabled and self.audio_handler.is_running


# 全局实例，供TouchDesigner使用
voice_chat = TouchDesignerVoiceChat()


# TouchDesigner函数接口
def enable_voice_chat():
    """启用语音对话"""
    voice_chat.enable()


def disable_voice_chat():
    """禁用语音对话"""
    voice_chat.disable()


def toggle_voice_chat():
    """切换语音对话状态"""
    voice_chat.toggle()


def send_audio(audio_input):
    """发送音频输入"""
    return voice_chat.send_audio_input(audio_input)


def get_audio():
    """获取音频输出"""
    return voice_chat.get_audio_output()


def send_text(text):
    """发送文本消息"""
    return voice_chat.send_text_message(text)


def get_status():
    """获取当前状态"""
    return voice_chat.get_status()


def is_enabled():
    """检查是否启用"""
    return voice_chat.enabled


def is_connected():
    """检查是否连接"""
    return voice_chat.connected


# TouchDesigner Execute DAT回调函数
def onStart():
    """TouchDesigner启动时调用"""
    print("TouchDesigner语音对话系统初始化")


def onExit():
    """TouchDesigner退出时调用"""
    if voice_chat.enabled:
        voice_chat.disable()
    print("TouchDesigner语音对话系统已清理")


def onValueChange(channel, sampleIndex, val, prev):
    """参数值变化时调用"""
    pass


# 示例：TouchDesigner中的使用方法
"""
在TouchDesigner中使用此脚本：

1. 创建一个Execute DAT
2. 将此文件的内容复制到Execute DAT中
3. 在需要的地方调用以下函数：

# 启用/禁用语音对话
mod('execute1').enable_voice_chat()
mod('execute1').disable_voice_chat()
mod('execute1').toggle_voice_chat()

# 发送音频输入 (在Audio CHOP的Execute DAT中)
mod('execute1').send_audio(op('audiodevicein1'))

# 获取音频输出 (在Script CHOP中)
audio_output = mod('execute1').get_audio()
if audio_output is not None:
    return audio_output
else:
    return np.zeros(1600)  # 返回静音

# 发送文本消息
mod('execute1').send_text("你好")

# 获取状态
status = mod('execute1').get_status()

# 检查状态
enabled = mod('execute1').is_enabled()
connected = mod('execute1').is_connected()
"""


if __name__ == "__main__":
    # 独立运行时的测试代码
    print("TouchDesigner集成脚本测试")

    # 启用语音对话
    enable_voice_chat()

    try:
        import time

        # 发送测试消息
        send_text("TouchDesigner测试消息")

        # 运行循环
        while True:
            status = get_status()
            print(f"状态: {status}")

            # 检查音频输出
            audio = get_audio()
            if audio is not None:
                print(f"接收到音频输出: {len(audio)} 采样点")

            time.sleep(1)

    except KeyboardInterrupt:
        print("停止测试")
        disable_voice_chat()