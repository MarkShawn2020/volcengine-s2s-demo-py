import argparse
import asyncio

import dotenv

dotenv.load_dotenv()

from src.adapters.base import AdapterType
from src.config import VOLCENGINE_APP_ID, VOLCENGINE_ACCESS_TOKEN
from src.unified_app import UnifiedAudioApp
from src.utils.logger import logger


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="统一音频应用")
    parser.add_argument(
        "--adapter", choices=["local", "browser", "touchdesigner"], default="local", help="选择适配器类型"
        )
    parser.add_argument(
        "--proxy-url", default="ws://localhost:8765", help="代理服务器URL（仅browser模式需要）"
        )
    parser.add_argument(
        "--use-pcm", action="store_true", default=True, help="使用PCM格式请求TTS音频（默认启用）"
        )
    parser.add_argument(
        "--td-ip", default="localhost", help="TouchDesigner IP地址（仅touchdesigner模式需要）"
        )
    parser.add_argument(
        "--td-port", type=int, default=7000, help="TouchDesigner端口（仅touchdesigner模式需要）"
        )

    args = parser.parse_args()

    if args.use_pcm:
        print("默认使用PCM模式请求TTS音频")

    # 确定适配器类型
    if args.adapter == "local":
        adapter_type = AdapterType.LOCAL
        config = {
            "app_id": VOLCENGINE_APP_ID,
            "access_token": VOLCENGINE_ACCESS_TOKEN
            }
    elif args.adapter == "browser":
        adapter_type = AdapterType.BROWSER
        config = {
            "proxy_url": args.proxy_url,
            "app_id": VOLCENGINE_APP_ID,
            "access_token": VOLCENGINE_ACCESS_TOKEN
            }
    elif args.adapter == "touchdesigner":
        adapter_type = AdapterType.TOUCH_DESIGNER
        config = {
            "td_ip": args.td_ip,
            "td_port": args.td_port,
            "app_id": VOLCENGINE_APP_ID,
            "access_token": VOLCENGINE_ACCESS_TOKEN
            }
    else:
        logger.error(f"不支持的适配器类型: {args.adapter}")
        return

    # 创建应用
    app = UnifiedAudioApp(adapter_type, config, use_tts_pcm=args.use_pcm)

    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("\n检测到用户中断 (Ctrl+C)")


if __name__ == "__main__":
    main()
