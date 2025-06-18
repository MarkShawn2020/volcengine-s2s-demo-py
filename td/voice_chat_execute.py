"""
TouchDesigner Execute DAT for Voice Chat
将此代码放入TouchDesigner的Execute DAT中
"""

import os
import sys

# 确保可以导入项目模块
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
print(f"project_root: {project_root}")
if project_root not in sys.path:
    sys.path.append(project_root)

from td.td_integration import TouchDesignerVoiceChat

# 全局变量
voice_chat = None
initialized = False


def onStart():
    """TouchDesigner启动时调用"""
    global voice_chat, initialized

    try:
        voice_chat = TouchDesignerVoiceChat()
        initialized = True
        print("语音对话系统初始化成功")
    except Exception as e:
        print(f"初始化失败: {e}")
        initialized = False


def onExit():
    """TouchDesigner退出时调用"""
    global voice_chat

    if voice_chat and voice_chat.enabled:
        voice_chat.disable()
        print("语音对话系统已清理")


def onValueChange(channel, sampleIndex, val, prev):
    """参数值变化时调用"""
    global voice_chat, initialized

    if not initialized or not voice_chat:
        return

    # 获取当前组件
    comp = me.parent()

    # 处理Enable参数变化
    if channel.name == 'Enable':
        if val > 0.5:  # 启用
            if not voice_chat.enabled:
                voice_chat.enable()
                print("语音对话已启用")
        else:  # 禁用
            if voice_chat.enabled:
                voice_chat.disable()
                print("语音对话已禁用")


def onPulse(channel, sampleIndex, val, prev):
    """脉冲参数变化时调用"""
    global voice_chat, initialized

    if not initialized or not voice_chat:
        return

    # 处理发送文本按钮
    if channel.name == 'Sendtext':
        comp = me.parent()
        text_input = comp.par.Textinput.eval()
        if text_input:
            voice_chat.send_text_message(text_input)
            print(f"发送文本: {text_input}")


def get_voice_chat():
    """获取语音对话实例"""
    global voice_chat, initialized

    if not initialized:
        onStart()

    return voice_chat if initialized else None


def send_audio_input(audio_chop):
    """发送音频输入"""
    vc = get_voice_chat()
    if vc and vc.enabled:
        try:
            return vc.send_audio_input(audio_chop)
        except Exception as e:
            print(f"发送音频失败: {e}")
            return False
    return False


def get_audio_output():
    """获取音频输出"""
    vc = get_voice_chat()
    if vc and vc.enabled:
        try:
            return vc.get_audio_output()
        except Exception as e:
            print(f"获取音频输出失败: {e}")
            return None
    return None


def get_status():
    """获取状态"""
    vc = get_voice_chat()
    if vc:
        return vc.get_status()
    return "未初始化"


def is_enabled():
    """检查是否启用"""
    vc = get_voice_chat()
    return vc.enabled if vc else False


def is_connected():
    """检查是否连接"""
    vc = get_voice_chat()
    return vc.connected if vc else False


# 回调函数映射
callbacks = {
    'onStart': onStart,
    'onExit': onExit,
    'onValueChange': onValueChange,
    'onPulse': onPulse
    }
