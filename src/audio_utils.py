import numpy as np
import struct

def calculate_volume(audio_data: bytes) -> float:
    """计算音频数据的音量（RMS）"""
    if len(audio_data) == 0:
        return 0.0
    
    # 将bytes转换为int16数组
    audio_samples = struct.unpack(f'{len(audio_data)//2}h', audio_data)
    
    # 计算RMS音量
    squares = [sample ** 2 for sample in audio_samples]
    mean_square = sum(squares) / len(squares)
    rms = (mean_square ** 0.5)
    
    # 归一化到0-1范围
    return min(rms / 32767.0, 1.0)

def has_speech_activity(audio_data: bytes, threshold: float = 0.01) -> bool:
    """检测音频中是否有语音活动"""
    volume = calculate_volume(audio_data)
    return volume > threshold

class VoiceActivityDetector:
    """简单的语音活动检测器"""
    
    def __init__(self, threshold: float = 0.01, min_speech_frames: int = 3):
        self.threshold = threshold
        self.min_speech_frames = min_speech_frames
        self.speech_frames = 0
        self.silence_frames = 0
        self.is_speaking = False
        self.max_silence_frames = 10  # 最多10帧静音后停止
    
    def process_frame(self, audio_data: bytes) -> bool:
        """
        处理音频帧，返回是否应该发送这一帧
        """
        has_activity = has_speech_activity(audio_data, self.threshold)
        
        if has_activity:
            self.speech_frames += 1
            self.silence_frames = 0
            
            # 连续几帧有语音活动才开始发送
            if self.speech_frames >= self.min_speech_frames:
                self.is_speaking = True
        else:
            self.silence_frames += 1
            self.speech_frames = 0
            
            # 连续静音一段时间后停止发送
            if self.silence_frames >= self.max_silence_frames:
                self.is_speaking = False
        
        # 返回是否应该发送这一帧
        return self.is_speaking or has_activity
    
    def get_volume(self, audio_data: bytes) -> float:
        """获取当前音频帧的音量"""
        return calculate_volume(audio_data)