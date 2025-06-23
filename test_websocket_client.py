#!/usr/bin/env python3
"""
WebSocket客户端测试工具
用于测试游戏分数同步功能
"""

import asyncio
import json
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_websocket_client():
    """测试WebSocket客户端连接"""
    uri = "ws://localhost:6666"
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info(f"已连接到: {uri}")
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    logger.info(f"收到消息: {json.dumps(data, indent=2, ensure_ascii=False)}")
                    
                    # 根据消息类型打印不同的信息
                    if data.get("type") == "initial_state":
                        print(f"初始状态 - 分数: {data.get('score')}, 状态: {data.get('status')}")
                    elif data.get("type") == "score_update":
                        print(f"分数更新 - 用户: {data.get('user_name', '未知')}, 分数: {data.get('score')}, 状态: {data.get('status')}")
                    
                except json.JSONDecodeError:
                    logger.warning(f"无法解析的消息: {message}")
                except Exception as e:
                    logger.error(f"处理消息异常: {e}")
    
    except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError):
        logger.error("连接被拒绝或关闭，请确保游戏应用正在运行")
    except Exception as e:
        logger.error(f"WebSocket连接异常: {e}")


async def main():
    """主函数"""
    print("WebSocket客户端测试工具")
    print("连接到游戏分数同步服务器...")
    print("按 Ctrl+C 退出")
    
    try:
        await test_websocket_client()
    except KeyboardInterrupt:
        print("\n退出测试客户端")


if __name__ == "__main__":
    asyncio.run(main())