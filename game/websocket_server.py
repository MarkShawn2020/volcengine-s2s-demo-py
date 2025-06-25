import asyncio
import json
import logging
import websockets
from typing import Set, Dict, Any, Optional

logger = logging.getLogger(__name__)


class GameScoreWebSocketClient:
    """游戏分数同步WebSocket客户端"""
    
    def __init__(self, uri: str = "ws://localhost:6666"):
        self.uri = uri
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.current_score = 0.0
        self.game_status = "waiting"
        self.is_connected = False
        
    async def start(self):
        """连接到WebSocket服务器"""
        try:
            self.websocket = await websockets.connect(self.uri)
            self.is_connected = True
            logger.info(f"✅ WebSocket客户端已连接到: {self.uri}")
            
            # 发送初始状态
            await self.send_message({
                "type": "initial_state",
                "score": self.current_score,
                "status": self.game_status
            })
            
            return True
        except Exception as e:
            logger.error(f"WebSocket客户端连接失败: {e}")
            return False
    
    async def stop(self):
        """断开WebSocket连接"""
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
            self.is_connected = False
            logger.info("WebSocket客户端已断开")
    
    async def send_message(self, data: Dict[str, Any]):
        """发送消息到服务器"""
        if not self.is_connected or not self.websocket:
            logger.warning("WebSocket未连接，无法发送消息")
            return False
            
        try:
            await self.websocket.send(json.dumps(data))
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            self.is_connected = False
            return False
    
    async def broadcast_score(self, score: float, status: str = "playing", user_name: str = ""):
        """发送分数到服务器"""
        self.current_score = score
        self.game_status = status
        
        message = {
            "type": "score_update",
            "score": score,
            "status": status,
            "user_name": user_name,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        success = await self.send_message(message)
        if success:
            logger.info(f"已发送分数到服务器: 分数={score}, 状态={status}")
        else:
            logger.error(f"发送分数失败: 分数={score}, 状态={status}")
    
    async def broadcast_game_start(self, user_name: str = ""):
        """发送游戏开始"""
        await self.broadcast_score(0.0, "started", user_name)
    
    async def broadcast_game_end(self, final_score: float, user_name: str = ""):
        """发送游戏结束"""
        await self.broadcast_score(final_score, "finished", user_name)
    
    async def broadcast_game_restart(self):
        """发送游戏重启"""
        await self.broadcast_score(0.0, "restarted")