#!/usr/bin/env python3
"""
TouchDesigner后端启动脚本
用于启动支持TouchDesigner的语音对话后端服务
"""

import argparse
import asyncio

from src.adapters.base import AdapterType
from src.config import VOLCENGINE_APP_ID, VOLCENGINE_ACCESS_TOKEN
from src.unified_app import UnifiedAudioApp
from src.utils.logger import logger


def main():
    """TouchDesigner后端主函数"""
    parser = argparse.ArgumentParser(description="TouchDesigner语音对话后端")
    parser.add_argument(
        "--td-ip", default="localhost", help="TouchDesigner IP地址 (默认: localhost)"
        )
    parser.add_argument(
        "--td-port", type=int, default=7000, help="TouchDesigner端口 (默认: 7000)"
        )
    parser.add_argument(
        "--listen-port", type=int, default=7001, help="监听TouchDesigner音频的端口 (默认: 7001)"
        )
    parser.add_argument(
        "--app-id", default=VOLCENGINE_APP_ID, help="火山引擎应用ID"
        )
    parser.add_argument(
        "--access-token", default=VOLCENGINE_ACCESS_TOKEN, help="火山引擎访问令牌"
        )
    parser.add_argument(
        "--use-pcm", action="store_true", default=True, help="使用PCM格式请求TTS音频（默认启用）"
        )

    args = parser.parse_args()

    # 检查必要的配置
    if not args.app_id or not args.access_token:
        logger.error("请设置火山引擎的APP_ID和ACCESS_TOKEN")
        logger.error("可以通过环境变量或命令行参数设置")
        return

    print("=" * 60)
    print("🎯 TouchDesigner语音对话后端")
    print("=" * 60)
    print(f"📡 TouchDesigner目标: {args.td_ip}:{args.td_port}")
    print(f"👂 监听端口: {args.listen_port}")
    print(f"🎵 TTS格式: {'PCM' if args.use_pcm else '默认'}")
    print(f"🔑 应用ID: {args.app_id}")
    print("=" * 60)

    # 配置TouchDesigner适配器
    config = {
        "td_ip": args.td_ip,
        "td_port": args.td_port,
        "listen_port": args.listen_port,
        "app_id": args.app_id,
        "access_token": args.access_token
        }

    # 创建应用
    app = UnifiedAudioApp(AdapterType.TOUCH_DESIGNER, config, use_tts_pcm=args.use_pcm)

    try:
        print("🚀 启动TouchDesigner语音对话后端...")
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("\n🛑 检测到用户中断 (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ 运行错误: {e}")


if __name__ == "__main__":
    main()
