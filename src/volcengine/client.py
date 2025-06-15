import asyncio
import gzip
import json
from typing import Dict, Any

import websockets

from src.utils.logger import logger
from src.volcengine import protocol
from src.volcengine.config import start_session_req


class VoicengineClient:
    def __init__(self, config: Dict[str, Any], session_id: str):
        self.config = config
        self.logid = ""
        self.session_id = session_id
        self.ws = None

    async def connect(self) -> None:
        """建立WebSocket连接"""
        logger.info(f"url: {self.config['base_url']}, headers: {self.config['headers']}")
        self.ws = await websockets.connect(
            self.config['base_url'], additional_headers=self.config['headers'], ping_interval=None
            )
        self.logid = self.ws.response_headers.get("X-Tt-Logid") if hasattr(self.ws, 'response_headers') else None
        logger.info(f"dialog server response logid: {self.logid}")

    async def start_connection(self) -> None:
        """发送StartConnection请求"""
        start_connection_request = bytearray(protocol.generate_header())
        start_connection_request.extend(int(1).to_bytes(4, 'big'))
        payload_bytes = str.encode("{}")
        payload_bytes = gzip.compress(payload_bytes)
        start_connection_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
        start_connection_request.extend(payload_bytes)
        await self.ws.send(start_connection_request)
        logger.info("StartConnection request sent")

    async def start_session(self) -> None:
        """发送StartSession请求"""
        request_params = start_session_req
        payload_bytes = str.encode(json.dumps(request_params))
        payload_bytes = gzip.compress(payload_bytes)
        start_session_request = bytearray(protocol.generate_header())
        start_session_request.extend(int(100).to_bytes(4, 'big'))
        start_session_request.extend((len(self.session_id)).to_bytes(4, 'big'))
        start_session_request.extend(str.encode(self.session_id))
        start_session_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
        start_session_request.extend(payload_bytes)
        await self.ws.send(start_session_request)
        logger.info("StartSession request sent")

    async def say_hello(self, content: str = "你好") -> None:
        """发送SayHello事件"""
        say_hello_request = bytearray(protocol.generate_header())
        say_hello_request.extend(int(300).to_bytes(4, 'big'))  # SayHello事件ID: 300
        say_hello_request.extend((len(self.session_id)).to_bytes(4, 'big'))
        say_hello_request.extend(str.encode(self.session_id))

        payload_data = {
            "content": content
            }
        payload_bytes = str.encode(json.dumps(payload_data, ensure_ascii=False))
        payload_bytes = gzip.compress(payload_bytes)
        say_hello_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
        say_hello_request.extend(payload_bytes)
        await self.ws.send(say_hello_request)
        logger.info(f"SayHello sent: {content}")

    async def task_request(self, audio: bytes) -> None:
        try:
            if not self.ws or (hasattr(self.ws, 'closed') and self.ws.closed):
                logger.warning("WebSocket连接不可用，跳过音频请求")
                return

            task_request = bytearray(
                protocol.generate_header(
                    message_type=protocol.CLIENT_AUDIO_ONLY_REQUEST, serial_method=protocol.NO_SERIALIZATION
                    )
                )
            task_request.extend(int(200).to_bytes(4, 'big'))
            task_request.extend((len(self.session_id)).to_bytes(4, 'big'))
            task_request.extend(str.encode(self.session_id))
            payload_bytes = gzip.compress(audio)
            task_request.extend((len(payload_bytes)).to_bytes(4, 'big'))  # payload size(4 bytes)
            task_request.extend(payload_bytes)
            await self.ws.send(task_request)
        except Exception as e:
            logger.debug(f"发送音频请求失败: {e}")  # 不抛出异常，避免中断WebRTC处理

    async def receive_server_response(self) -> Dict[str, Any]:
        try:
            if self.ws is None:
                raise Exception("WebSocket connection not established")
            response = await self.ws.recv()
            data = protocol.parse_response(response)
            return data
        except Exception as e:
            raise Exception(f"Failed to receive message: {e}")

    async def finish_session(self):
        """发送结束会话请求"""
        try:
            if not self.ws or (hasattr(self.ws, 'closed') and self.ws.closed):
                logger.info("WebSocket已关闭，跳过finish_session")
                return

            finish_session_request = bytearray(protocol.generate_header())
            finish_session_request.extend(int(102).to_bytes(4, 'big'))
            payload_bytes = str.encode("{}")
            payload_bytes = gzip.compress(payload_bytes)
            finish_session_request.extend((len(self.session_id)).to_bytes(4, 'big'))
            finish_session_request.extend(str.encode(self.session_id))
            finish_session_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
            finish_session_request.extend(payload_bytes)
            await self.ws.send(finish_session_request)
            logger.info("FinishSession request sent")
        except Exception as e:
            logger.warning(f"发送finish_session请求失败: {e}")

    async def finish_connection(self):
        """发送结束连接请求"""
        try:
            if not self.ws or (hasattr(self.ws, 'closed') and self.ws.closed):
                logger.info("WebSocket已关闭，跳过finish_connection")
                return

            finish_connection_request = bytearray(protocol.generate_header())
            finish_connection_request.extend(int(2).to_bytes(4, 'big'))
            payload_bytes = str.encode("{}")
            payload_bytes = gzip.compress(payload_bytes)
            finish_connection_request.extend((len(payload_bytes)).to_bytes(4, 'big'))
            finish_connection_request.extend(payload_bytes)
            await self.ws.send(finish_connection_request)
            logger.info("FinishConnection request sent")

            # 尝试接收响应，但设置超时
            try:
                response = await asyncio.wait_for(self.ws.recv(), timeout=3.0)
                logger.info(f"FinishConnection response: {protocol.parse_response(response)}")
            except asyncio.TimeoutError:
                logger.warning("等待FinishConnection响应超时")
            except Exception as e:
                logger.warning(f"接收FinishConnection响应失败: {e}")

        except Exception as e:
            logger.warning(f"发送finish_connection请求失败: {e}")

    async def close(self) -> None:
        """关闭WebSocket连接"""
        if self.ws:
            try:
                logger.info("正在优雅关闭WebSocket连接...")

                # 检查连接状态，如果仍然开放则尝试发送关闭帧
                import websockets
                if hasattr(self.ws, 'state') and self.ws.state == websockets.protocol.State.OPEN:
                    # 发送优雅关闭帧
                    await self.ws.close(code=1000, reason="Client shutdown")
                    logger.info("WebSocket关闭帧已发送")
                elif hasattr(self.ws, 'closed') and not self.ws.closed:
                    # 对于其他WebSocket实现
                    await self.ws.close()
                    logger.info("WebSocket连接已关闭")
                else:
                    logger.info("WebSocket连接已经关闭")

            except Exception as e:
                logger.warning(f"关闭WebSocket连接时出现错误: {e}")
                try:
                    # 强制关闭连接
                    if hasattr(self.ws, 'close'):
                        await self.ws.close()
                except:
                    pass
            finally:
                self.ws = None
                logger.info("WebSocket连接清理完成")

    async def graceful_shutdown(self) -> None:
        """优雅关闭WebSocket连接，包括发送结束请求"""
        try:
            logger.info("开始优雅关闭WebSocket连接...")

            # 尝试发送结束会话请求
            await self.finish_session()

            # 短暂等待，让服务器处理请求
            await asyncio.sleep(0.1)

            # 尝试发送结束连接请求
            await self.finish_connection()

            # 短暂等待，让服务器处理请求
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.warning(f"优雅关闭过程中出现错误: {e}")
        finally:
            # 最终关闭WebSocket连接
            await self.close()
