"""
TouchDesigner Script CHOP for Audio Input Processing
将此代码放入处理音频输入的Script CHOP中
"""

import numpy as np

def onCook(scriptOp):
    """音频输入处理"""
    
    # 获取Execute DAT
    execute_dat = op('voice_chat_execute')
    if not execute_dat:
        print("找不到voice_chat_execute")
        return
    
    # 获取音频输入
    audio_input = op('audiodevicein1')
    if not audio_input:
        print("找不到音频输入设备")
        return
    
    # 检查是否启用
    try:
        enabled = execute_dat.module.is_enabled()
        if not enabled:
            return
    except:
        return
    
    # 发送音频到语音对话系统
    try:
        success = execute_dat.module.send_audio_input(audio_input)
        if success:
            # 可以在这里添加音频发送成功的指示
            pass
    except Exception as e:
        print(f"音频输入处理错误: {e}")

def onPulse(channel, sampleIndex, val, prev):
    """脉冲处理"""
    pass