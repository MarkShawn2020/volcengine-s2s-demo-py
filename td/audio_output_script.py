"""
TouchDesigner Script CHOP for Audio Output Processing
将此代码放入处理音频输出的Script CHOP中
"""

import numpy as np

def onCook(scriptOp):
    """音频输出处理"""
    
    # 获取Execute DAT
    execute_dat = op('voice_chat_execute')
    if not execute_dat:
        scriptOp.clear()
        return
    
    # 检查是否启用和连接
    try:
        enabled = execute_dat.module.is_enabled()
        connected = execute_dat.module.is_connected()
        
        if not (enabled and connected):
            # 输出静音
            scriptOp.clear()
            silent_samples = np.zeros(1600)  # 100ms @ 16kHz
            scriptOp.appendChan('chan1')
            for sample in silent_samples:
                scriptOp.appendSample([sample])
            return
            
    except:
        scriptOp.clear()
        return
    
    # 获取音频输出
    try:
        audio_output = execute_dat.module.get_audio_output()
        
        scriptOp.clear()
        
        if audio_output is not None and len(audio_output) > 0:
            # 有音频数据，输出到CHOP
            scriptOp.appendChan('chan1')
            for sample in audio_output:
                scriptOp.appendSample([float(sample)])
        else:
            # 没有音频数据，输出静音
            scriptOp.appendChan('chan1')
            silent_samples = np.zeros(1600)  # 100ms @ 16kHz
            for sample in silent_samples:
                scriptOp.appendSample([sample])
                
    except Exception as e:
        print(f"音频输出处理错误: {e}")
        # 错误时输出静音
        scriptOp.clear()
        scriptOp.appendChan('chan1')
        silent_samples = np.zeros(1600)
        for sample in silent_samples:
            scriptOp.appendSample([sample])

def onPulse(channel, sampleIndex, val, prev):
    """脉冲处理"""
    pass