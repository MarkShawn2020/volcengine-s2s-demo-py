#!/usr/bin/env python3
"""
WebSocket调试脚本
用于独立测试WebSocket服务器
"""

import asyncio
import logging
from game.websocket_server import GameScoreWebSocketServer

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def test_server():
    """测试WebSocket服务器"""
    server = GameScoreWebSocketServer()
    
    try:
        logger.info("启动测试WebSocket服务器...")
        success = await server.start()
        if not success:
            logger.error("服务器启动失败")
            return
        
        logger.info("服务器启动成功，等待连接...")
        
        # 模拟一些分数更新
        await asyncio.sleep(2)
        await server.broadcast_game_start("测试用户")
        
        await asyncio.sleep(2)
        await server.broadcast_score(25.5, "question_1_completed", "测试用户")
        
        await asyncio.sleep(2)
        await server.broadcast_score(55.0, "question_2_completed", "测试用户")
        
        await asyncio.sleep(2)
        await server.broadcast_game_end(85.5, "测试用户")
        
        # 保持服务器运行
        logger.info("保持服务器运行，按Ctrl+C退出...")
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("收到中断信号")
    finally:
        await server.stop()
        logger.info("服务器已停止")


if __name__ == "__main__":
    asyncio.run(test_server())