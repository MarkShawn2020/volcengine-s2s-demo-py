import dotenv

dotenv.load_dotenv()

import asyncio
import argparse
from game.flower_game_app import FlowerGameApp

from src.adapters.type import AdapterType
from src.config import VOLCENGINE_APP_ID, VOLCENGINE_ACCESS_TOKEN
from logger import logger


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
