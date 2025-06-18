import asyncio
import json
from typing import Dict, Any

import websockets

from src.adapters.proxy_server import logger
from src.volcengine import protocol


class ProxyClient:
    """代理客户端 - 管理单个浏览器连接"""

    def __init__(self, client_id: str, websocket):
        self.client_id = client_id
        self.websocket = websocket
        self.volcengine_client = None
        self.is_authenticated = False
        self.receive_task = None
        self.running = True

    async def handle(self):
        """处理客户端消息"""
        try:
            async for message in self.websocket:
                if not self.running:
                    break
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    await self._send_error("Invalid JSON format")
                except Exception as e:
                    logger.error(f"处理消息异常: {e}")
                    await self._send_error(str(e))
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端 {self.client_id} WebSocket连接关闭")
        except Exception as e:
            logger.error(f"处理客户端消息失败: {e}")

    async def _handle_message(self, data: Dict[str, Any]):
        """处理具体消息"""
        message_type = data.get("type")

        if message_type == "audio":
            await self._handle_audio(data)
        elif message_type == "text":
            await self._handle_text(data)
        elif message_type == "ping":
            await self._send_message({"type": "pong"})
        else:
            await self._send_error(f"Unknown message type: {message_type}")

    async def _handle_audio(self, data: Dict[str, Any]):
        """处理音频数据"""
        if not self.is_authenticated or not self.volcengine_client:
            await self._send_error("Not authenticated")
            return

        try:
            # 从十六进制字符串转换回字节
            audio_hex = data.get("data", "")
            audio_data = bytes.fromhex(audio_hex)

            await self.volcengine_client.push_audio(audio_data)

        except Exception as e:
            logger.error(f"处理音频失败: {e}")
            await self._send_error(f"Audio processing failed: {str(e)}")

    async def _handle_text(self, data: Dict[str, Any]):
        """处理文本消息"""
        if not self.is_authenticated or not self.volcengine_client:
            await self._send_error("Not authenticated")
            return

        try:
            content = data.get("content", "")
            await self.volcengine_client.request_say_hello(content)

        except Exception as e:
            logger.error(f"处理文本失败: {e}")
            await self._send_error(f"Text processing failed: {str(e)}")

    async def _receive_from_volcengine(self):
        """从火山引擎接收响应"""
        while self.running and self.is_authenticated and self.volcengine_client:
            try:
                response = await self.volcengine_client.on_response()
                if response:
                    await self._handle_volcengine_response(response)
                elif not self.volcengine_client.is_active:
                    logger.warning("火山引擎连接已断开")
                    break
            except Exception as e:
                logger.error(f"接收火山引擎响应失败: {e}")
                break

        logger.info(f"客户端 {self.client_id} 火山引擎接收任务结束")

    async def _handle_volcengine_response(self, response: Dict[str, Any]):
        """处理火山引擎响应"""
        event = response.get('event')

        if event == protocol.ServerEvent.TTS_RESPONSE:
            # 音频响应 - 直接发送二进制数据
            audio_data = response.get('payload_msg')
            if isinstance(audio_data, bytes):
                await self._send_audio_binary(audio_data)
        elif event == protocol.ServerEvent.ASR_INFO:
            # ASR_INFO事件：用户开始说话，通知浏览器打断AI语音
            logger.info("🛑 检测到用户语音活动，转发ASR_INFO事件")
            await self._send_message({
                "type": "event",
                "event": event,
                "data": response.get('payload_msg', {})
            })
        else:
            # 其他事件
            await self._send_message({
                "type": "event",
                "event": event,
                "data": response.get('payload_msg', {})
            })

    async def _send_message(self, message: Dict[str, Any]):
        """发送消息到浏览器"""
        if not self.running:
            return

        try:
            await self.websocket.send(json.dumps(message, ensure_ascii=False))
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端 {self.client_id} 连接已关闭，无法发送消息")
            self.running = False
        except Exception as e:
            logger.error(f"发送消息失败: {e}")

    async def _send_audio_binary(self, audio_data: bytes):
        """直接发送二进制音频数据"""
        if not self.running:
            return

        try:
            # 发送二进制数据，浏览器将收到ArrayBuffer
            await self.websocket.send(audio_data)
            logger.debug(f"发送二进制音频数据: {len(audio_data)}字节")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端 {self.client_id} 连接已关闭，无法发送音频")
            self.running = False
        except Exception as e:
            logger.error(f"发送音频失败: {e}")

    async def _send_error(self, error_message: str):
        """发送错误消息"""
        await self._send_message({
            "type": "error",
            "message": error_message
        })

    async def _send_welcome_to_volcengine(self):
        """向火山引擎发送欢迎消息"""
        try:
            from src.config import WELCOME_MESSAGE
            await self.volcengine_client.request_say_hello(WELCOME_MESSAGE)
            logger.info(f"已向火山引擎发送welcome消息: {WELCOME_MESSAGE}")
        except Exception as e:
            logger.error(f"发送welcome消息失败: {e}")

    async def cleanup(self):
        """清理资源"""
        self.running = False

        if self.receive_task:
            self.receive_task.cancel()
            try:
                await self.receive_task
            except asyncio.CancelledError:
                pass

        if self.volcengine_client:
            try:
                await self.volcengine_client.stop()
            except Exception as e:
                logger.error(f"关闭火山引擎客户端失败: {e}")
            self.volcengine_client = None
