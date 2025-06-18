#!/usr/bin/env python3
"""
测试音频流畅性的简化脚本
"""
import asyncio
import logging
from src.unified_app import UnifiedAudioApp
from src.adapters.type import AdapterType
from src.config import VOLCENGINE_APP_ID, VOLCENGINE_ACCESS_TOKEN

# 设置简洁的日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    print("🎵 测试音频流畅性...")
    print("默认使用PCM模式请求TTS音频")
    
    # 配置
    config = {
        "app_id": VOLCENGINE_APP_ID,
        "access_token": VOLCENGINE_ACCESS_TOKEN
    }
    
    # 创建应用
    app = UnifiedAudioApp(AdapterType.LOCAL, config, use_tts_pcm=True)
    
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("\n✅ 检测到用户中断 (Ctrl+C)")

if __name__ == "__main__":
    main()