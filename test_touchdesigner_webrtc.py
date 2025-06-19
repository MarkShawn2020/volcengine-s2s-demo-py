#!/usr/bin/env python3
"""
TouchDesigner WebRTC适配器测试脚本

这个脚本用于测试TouchDesigner WebRTC适配器的基本功能，
包括连接、消息传递和音频处理。
"""

import asyncio
import logging
import json
import websockets
import base64
from src.adapters.touchdesigner_webrtc_adapter import (
    TouchDesignerWebRTCAudioAdapter,
    TouchDesignerWebRTCConnectionConfig
)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockTouchDesignerClient:
    """模拟TouchDesigner客户端用于测试"""
    
    def __init__(self, server_host="localhost", server_port=8080):
        self.server_host = server_host
        self.server_port = server_port
        self.websocket = None
        self.connected = False
        
    async def connect(self):
        """连接到WebRTC适配器"""
        try:
            uri = f"ws://{self.server_host}:{self.server_port}"
            self.websocket = await websockets.connect(uri)
            self.connected = True
            logger.info(f"模拟TD客户端连接成功: {uri}")
            
            # 发送初始offer
            await self.send_offer()
            
            # 启动消息监听
            await self.listen_for_messages()
            
        except Exception as e:
            logger.error(f"连接失败: {e}")
            
    async def send_offer(self):
        """发送WebRTC offer"""
        offer = {
            "type": "offer",
            "sdp": "v=0\r\no=- 12345 0 IN IP4 127.0.0.1\r\ns=TouchDesigner Test\r\nt=0 0\r\n",
            "timestamp": asyncio.get_event_loop().time()
        }
        
        await self.websocket.send(json.dumps(offer))
        logger.info("发送WebRTC offer")
        
    async def send_text_message(self, text):
        """发送文本消息"""
        if not self.connected:
            logger.warning("未连接，无法发送文本")
            return
            
        message = {
            "type": "text-message",
            "text": text,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        await self.websocket.send(json.dumps(message))
        logger.info(f"发送文本: {text}")
        
    async def send_audio_data(self, audio_data):
        """发送音频数据"""
        if not self.connected:
            logger.warning("未连接，无法发送音频")
            return
            
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        message = {
            "type": "audio-data",
            "audio": audio_b64,
            "length": len(audio_data),
            "timestamp": asyncio.get_event_loop().time()
        }
        
        await self.websocket.send(json.dumps(message))
        logger.info(f"发送音频数据: {len(audio_data)} 字节")
        
    async def listen_for_messages(self):
        """监听来自适配器的消息"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"收到无效JSON: {message}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket连接已关闭")
            self.connected = False
        except Exception as e:
            logger.error(f"监听消息时出错: {e}")
            
    async def handle_message(self, data):
        """处理收到的消息"""
        message_type = data.get("type")
        
        if message_type == "answer":
            logger.info(f"收到WebRTC answer，会话ID: {data.get('session_id', 'N/A')}")
        elif message_type == "audio-response":
            audio_length = data.get("length", 0)
            logger.info(f"收到音频响应: {audio_length} 字节")
        elif message_type == "status":
            status = data.get("message", "")
            logger.info(f"收到状态: {status}")
        else:
            logger.info(f"收到未知消息类型: {message_type}")
            
    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            logger.info("模拟TD客户端已断开连接")


async def test_adapter_basic():
    """测试适配器基本功能"""
    logger.info("开始测试TouchDesigner WebRTC适配器基本功能")
    
    # 创建适配器配置 (使用测试参数)
    config = TouchDesignerWebRTCConnectionConfig(
        signaling_port=8080,
        app_id="test_app_id",
        access_token="test_access_token"
    )
    
    # 创建适配器
    adapter = TouchDesignerWebRTCAudioAdapter(config)
    
    try:
        # 启动适配器
        logger.info("启动适配器...")
        success = await adapter.connect()
        
        if not success:
            logger.error("适配器启动失败")
            return False
            
        logger.info("适配器启动成功")
        
        # 等待信令服务器完全启动
        await asyncio.sleep(1)
        
        # 创建模拟TD客户端
        client = MockTouchDesignerClient()
        
        # 启动客户端连接 (在后台运行)
        client_task = asyncio.create_task(client.connect())
        
        # 等待连接建立
        await asyncio.sleep(2)
        
        if client.connected:
            logger.info("客户端连接成功，开始测试消息传递")
            
            # 测试文本消息
            await client.send_text_message("Hello from TouchDesigner!")
            await asyncio.sleep(1)
            
            # 测试音频数据 (模拟)
            fake_audio = b'\x00\x01' * 1000  # 2000字节的模拟音频
            await client.send_audio_data(fake_audio)
            await asyncio.sleep(1)
            
            # 发送更多测试消息
            await client.send_text_message("Testing WebRTC adapter")
            await asyncio.sleep(1)
            
            logger.info("测试消息发送完成")
        else:
            logger.error("客户端连接失败")
            
        # 运行一段时间以观察行为
        logger.info("运行测试 10 秒...")
        await asyncio.sleep(10)
        
        # 清理
        await client.disconnect()
        client_task.cancel()
        
        try:
            await client_task
        except asyncio.CancelledError:
            pass
            
        await adapter.disconnect()
        logger.info("适配器测试完成")
        
        return True
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        try:
            await adapter.disconnect()
        except:
            pass
        return False


async def test_multiple_clients():
    """测试多客户端连接"""
    logger.info("开始测试多客户端连接")
    
    config = TouchDesignerWebRTCConnectionConfig(
        signaling_port=8081,  # 使用不同端口避免冲突
        app_id="test_app_id",
        access_token="test_access_token"
    )
    
    adapter = TouchDesignerWebRTCAudioAdapter(config)
    
    try:
        await adapter.connect()
        await asyncio.sleep(1)
        
        # 创建多个客户端
        clients = []
        client_tasks = []
        
        for i in range(3):
            client = MockTouchDesignerClient("localhost", 8081)
            clients.append(client)
            
            # 启动连接
            task = asyncio.create_task(client.connect())
            client_tasks.append(task)
            
            await asyncio.sleep(0.5)  # 错开连接时间
            
        # 等待所有连接建立
        await asyncio.sleep(3)
        
        # 测试每个客户端发送消息
        for i, client in enumerate(clients):
            if client.connected:
                await client.send_text_message(f"Message from client {i+1}")
                await asyncio.sleep(0.5)
                
        logger.info("多客户端测试运行 5 秒...")
        await asyncio.sleep(5)
        
        # 清理
        for client in clients:
            await client.disconnect()
            
        for task in client_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
        await adapter.disconnect()
        logger.info("多客户端测试完成")
        
        return True
        
    except Exception as e:
        logger.error(f"多客户端测试失败: {e}")
        try:
            await adapter.disconnect()
        except:
            pass
        return False


async def main():
    """主测试函数"""
    logger.info("TouchDesigner WebRTC适配器测试开始")
    
    # 测试基本功能
    test1_result = await test_adapter_basic()
    
    # 等待端口释放
    await asyncio.sleep(2)
    
    # 测试多客户端
    test2_result = await test_multiple_clients()
    
    # 测试结果
    if test1_result and test2_result:
        logger.info("所有测试通过！")
    else:
        logger.error("部分测试失败")
        
    logger.info("测试结束")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
    except Exception as e:
        logger.error(f"测试运行时出错: {e}")