import asyncio
import logging

from src.app import RealTimeAudioApp

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    use_pcm = True
    print("默认使用PCM模式请求TTS音频。")
    app = RealTimeAudioApp(use_tts_pcm=use_pcm)
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("\n检测到用户中断 (Ctrl+C)。")
