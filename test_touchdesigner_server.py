#!/usr/bin/env python3
"""
TouchDesigner模拟服务器 - 用于测试TouchDesigner适配器
模拟TouchDesigner端的行为，接收和发送控制消息及音频数据
"""

import asyncio
import json
import struct
import socket
import time
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TouchDesignerTestServer:
    """模拟TouchDesigner的测试服务器"""
    
    def __init__(self):
        # 端口配置 - 与Python适配器相对应
        self.control_port = 7003        # TCP控制连接
        self.audio_input_port = 7001    # UDP接收音频（从Python适配器）
        self.audio_output_port = 7002   # UDP发送音频（到Python适配器）
        
        # 服务器socket
        self.control_server = None
        self.audio_input_socket = None
        self.audio_output_socket = None
        
        # 客户端连接
        self.control_clients = []
        
        # 运行状态
        self.running = False
        
        # 统计信息
        self.stats = {
            'control_connections': 0,
            'control_messages_received': 0,
            'control_messages_sent': 0,
            'audio_packets_received': 0,
            'audio_packets_sent': 0
        }
    
    async def start(self):
        """启动服务器"""
        logger.info("启动TouchDesigner测试服务器...")
        
        try:
            # 启动控制服务器 (TCP)
            await self._start_control_server()
            
            # 启动音频输入服务器 (UDP)
            await self._start_audio_input_server()
            
            # 启动音频输出服务器 (UDP)
            await self._start_audio_output_server()
            
            self.running = True
            logger.info("TouchDesigner测试服务器启动成功")
            logger.info(f"控制端口: {self.control_port} (TCP)")
            logger.info(f"音频输入端口: {self.audio_input_port} (UDP)")
            logger.info(f"音频输出端口: {self.audio_output_port} (UDP)")
            
            # 启动任务
            tasks = [
                asyncio.create_task(self._audio_input_handler()),
                asyncio.create_task(self._audio_output_handler()),
                asyncio.create_task(self._stats_reporter())
            ]
            
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"服务器启动失败: {e}")
            await self.stop()
    
    async def stop(self):
        """停止服务器"""
        logger.info("停止TouchDesigner测试服务器...")
        self.running = False
        
        # 关闭控制服务器
        if self.control_server:
            self.control_server.close()
            await self.control_server.wait_closed()
        
        # 关闭UDP socket
        if self.audio_input_socket:
            self.audio_input_socket.close()
        if self.audio_output_socket:
            self.audio_output_socket.close()
        
        logger.info("服务器已停止")
        logger.info(f"最终统计: {self.stats}")
    
    async def _start_control_server(self):
        """启动控制服务器"""
        self.control_server = await asyncio.start_server(
            self._handle_control_client,
            'localhost',
            self.control_port
        )
        logger.info(f"控制服务器监听 localhost:{self.control_port}")
    
    async def _start_audio_input_server(self):
        """启动音频输入服务器"""
        self.audio_input_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.audio_input_socket.bind(('localhost', self.audio_input_port))
        self.audio_input_socket.setblocking(False)
        logger.info(f"音频输入服务器监听 localhost:{self.audio_input_port}")
    
    async def _start_audio_output_server(self):
        """启动音频输出服务器"""
        self.audio_output_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.audio_output_socket.setblocking(False)
        logger.info(f"音频输出服务器已创建")
    
    async def _handle_control_client(self, reader, writer):
        """处理控制连接客户端"""
        client_addr = writer.get_extra_info('peername')
        logger.info(f"新的控制连接: {client_addr}")
        
        self.control_clients.append({'reader': reader, 'writer': writer, 'addr': client_addr})
        self.stats['control_connections'] += 1
        
        try:
            while self.running:
                # 读取消息长度
                length_data = await reader.readexactly(4)
                message_length = struct.unpack('<I', length_data)[0]
                
                if message_length > 1024 * 1024:  # 1MB限制
                    logger.warning(f"控制消息过大: {message_length}")
                    continue
                
                # 读取消息内容
                message_data = await reader.readexactly(message_length)
                message_json = message_data.decode('utf-8')
                message = json.loads(message_json)
                
                self.stats['control_messages_received'] += 1
                logger.info(f"收到控制消息: {message}")
                
                # 处理消息
                await self._process_control_message(message, writer)
                
        except asyncio.IncompleteReadError:
            logger.info(f"控制连接断开: {client_addr}")
        except Exception as e:
            logger.error(f"控制连接处理错误: {e}")
        finally:
            # 清理连接
            self.control_clients = [c for c in self.control_clients if c['writer'] != writer]
            writer.close()
            await writer.wait_closed()
    
    async def _process_control_message(self, message: Dict[str, Any], writer):
        """处理控制消息"""
        message_type = message.get('type')
        
        if message_type == 'init':
            # 响应初始化
            response = {
                'type': 'init_response',
                'status': 'success',
                'server_info': {
                    'name': 'TouchDesigner Test Server',
                    'version': '1.0.0',
                    'capabilities': ['audio_input', 'audio_output', 'control']
                }
            }
            await self._send_control_message(response, writer)
            
        elif message_type == 'ping':
            # 响应ping
            response = {'type': 'pong', 'timestamp': time.time()}
            await self._send_control_message(response, writer)
            
        elif message_type == 'text':
            # 处理文本消息
            content = message.get('content', '')
            logger.info(f"收到文本消息: {content}")
            
            # 发送响应
            response = {
                'type': 'text_response',
                'original_text': content,
                'response': f"收到文本: {content}"
            }
            await self._send_control_message(response, writer)
            
        elif message_type == 'disconnect':
            logger.info("收到断开连接请求")
            
        else:
            logger.warning(f"未知控制消息类型: {message_type}")
    
    async def _send_control_message(self, message: Dict[str, Any], writer):
        """发送控制消息"""
        try:
            message_json = json.dumps(message, ensure_ascii=False)
            message_bytes = message_json.encode('utf-8')
            length_header = struct.pack('<I', len(message_bytes))
            
            writer.write(length_header + message_bytes)
            await writer.drain()
            
            self.stats['control_messages_sent'] += 1
            logger.debug(f"发送控制消息: {message['type']}")
            
        except Exception as e:
            logger.error(f"发送控制消息失败: {e}")
    
    async def _audio_input_handler(self):
        """处理音频输入"""
        while self.running:
            try:
                # 接收音频数据
                data, addr = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.audio_input_socket.recvfrom,
                    4096 + 12  # 音频数据 + 头部
                )
                
                if len(data) < 12:  # 头部最小长度
                    continue
                
                # 解析包头
                timestamp, data_length = struct.unpack('<QI', data[:12])
                audio_data = data[12:12+data_length]
                
                if len(audio_data) != data_length:
                    logger.warning(f"音频数据长度不匹配: 期望{data_length}, 实际{len(audio_data)}")
                    continue
                
                self.stats['audio_packets_received'] += 1
                logger.debug(f"收到音频数据: {len(audio_data)} 字节，来自 {addr}")
                
                # 可以在这里处理音频数据
                # 例如：转发到其他系统，或者进行音频处理
                
            except Exception as e:
                if self.running:
                    logger.error(f"音频输入处理错误: {e}")
                await asyncio.sleep(0.1)
    
    async def _audio_output_handler(self):
        """处理音频输出 - 发送测试音频数据"""
        while self.running:
            try:
                # 每秒发送一次测试音频数据
                await asyncio.sleep(1.0)
                
                # 生成测试音频数据（静音）
                test_audio = b'\x00' * 1024  # 1KB的静音数据
                
                # 发送给Python适配器
                await self._send_audio_data(test_audio, 'localhost', self.audio_output_port)
                
            except Exception as e:
                if self.running:
                    logger.error(f"音频输出处理错误: {e}")
                await asyncio.sleep(0.1)
    
    async def _send_audio_data(self, audio_data: bytes, target_ip: str, target_port: int):
        """发送音频数据"""
        try:
            # 创建音频包头
            timestamp = int(time.time() * 1000000)  # 微秒时间戳
            header = struct.pack('<QI', timestamp, len(audio_data))
            packet = header + audio_data
            
            # 发送UDP包
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.audio_output_socket.sendto,
                packet,
                (target_ip, target_port)
            )
            
            self.stats['audio_packets_sent'] += 1
            logger.debug(f"发送音频数据: {len(audio_data)} 字节到 {target_ip}:{target_port}")
            
        except Exception as e:
            logger.error(f"发送音频数据失败: {e}")
    
    async def _stats_reporter(self):
        """定期报告统计信息"""
        while self.running:
            await asyncio.sleep(10)  # 每10秒报告一次
            logger.info(f"统计信息: {self.stats}")


async def main():
    """主函数"""
    server = TouchDesignerTestServer()
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止服务器...")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())