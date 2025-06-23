import asyncio
import json
import logging
import websockets
from typing import Set, Dict, Any

logger = logging.getLogger(__name__)


class GameScoreWebSocketServer:
    """游戏分数同步WebSocket服务器"""
    
    def __init__(self, host: str = "localhost", port: int = 6666):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server = None
        self.current_score = 0.0
        self.game_status = "waiting"
        
    async def start(self):
        """启动WebSocket服务器"""
        try:
            async def connection_handler(websocket):
                await self.handle_client(websocket)
            
            self.server = await websockets.serve(
                connection_handler,
                self.host,
                self.port
            )
            logger.info(f"WebSocket服务器已启动: ws://{self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"WebSocket服务器启动失败: {e}")
            return False
    
    async def stop(self):
        """停止WebSocket服务器"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("WebSocket服务器已停止")
    
    async def handle_client(self, websocket):
        """处理客户端连接"""
        self.clients.add(websocket)
        client_addr = websocket.remote_address
        logger.info(f"客户端连接: {client_addr}")
        
        # 立即发送当前状态
        await self.send_to_client(websocket, {
            "type": "initial_state",
            "score": self.current_score,
            "status": self.game_status
        })
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    logger.debug(f"收到客户端消息: {data}")
                except json.JSONDecodeError:
                    logger.warning(f"无效JSON消息: {message}")
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"处理客户端消息异常: {e}")
        finally:
            self.clients.discard(websocket)
            logger.info(f"客户端断开: {client_addr}")
    
    async def send_to_client(self, websocket, data: Dict[str, Any]):
        """发送数据到指定客户端"""
        try:
            await websocket.send(json.dumps(data))
        except Exception as e:
            logger.error(f"发送数据到客户端失败: {e}")
    
    async def broadcast_score(self, score: float, status: str = "playing", user_name: str = ""):
        """广播分数给所有客户端"""
        self.current_score = score
        self.game_status = status
        
        message = {
            "type": "score_update",
            "score": score,
            "status": status,
            "user_name": user_name,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        if not self.clients:
            logger.debug(f"没有客户端连接，跳过广播: {message}")
            return
        
        # 创建发送任务列表
        tasks = []
        for client in self.clients.copy():
            tasks.append(self.send_to_client(client, message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"已广播分数给{len(tasks)}个客户端: 分数={score}, 状态={status}")
    
    async def broadcast_game_start(self, user_name: str = ""):
        """广播游戏开始"""
        await self.broadcast_score(0.0, "started", user_name)
    
    async def broadcast_game_end(self, final_score: float, user_name: str = ""):
        """广播游戏结束"""
        await self.broadcast_score(final_score, "finished", user_name)
    
    async def broadcast_game_restart(self):
        """广播游戏重启"""
        await self.broadcast_score(0.0, "restarted")