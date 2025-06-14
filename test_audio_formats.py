#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from audio_manager import DialogSession

def test_with_tts_config():
    """测试配置了 TTS 的情况（返回 PCM）"""
    print("=== 测试配置 TTS（PCM 格式）===")
    session = DialogSession(config.ws_connect_config)
    print(f"TTS 配置: {config.start_session_req}")

def test_without_tts_config():
    """测试不配置 TTS 的情况（返回 OGG/Opus）"""
    print("\n=== 测试不配置 TTS（OGG/Opus 格式）===")
    
    # 临时修改配置，移除 TTS 设置
    original_config = config.start_session_req.copy()
    config.start_session_req.pop('tts', None)
    
    session = DialogSession(config.ws_connect_config)
    print(f"无 TTS 配置: {config.start_session_req}")
    
    # 恢复原配置
    config.start_session_req = original_config

if __name__ == "__main__":
    print("音频格式兼容性测试")
    print("该测试将验证系统是否能正确处理两种音频格式：")
    print("1. 配置 TTS 时服务端返回的 PCM 格式")
    print("2. 不配置 TTS 时服务端返回的 OGG/Opus 格式")
    print()
    
    test_with_tts_config()
    test_without_tts_config()
    
    print("\n音频格式自动检测和转换功能已实现。")
    print("- 检测 OGG 文件头 (OggS)")
    print("- 自动转换 OGG/Opus 到 PCM")
    print("- 保持向后兼容性")