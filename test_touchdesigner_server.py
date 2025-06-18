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
        # 端口配置 - 简化为只监听7002端口
        self.audio_input_port = 7002    # UDP接收音频（从Python适配器）
        
        # 服务器socket
        self.audio_input_socket = None
        
        # 运行状态
        self.running = False
        
        # 统计信息
        self.stats = {
            'audio_packets_received': 0,
        }
    
    async def start(self):
        """启动服务器"""
        logger.info("启动TouchDesigner测试服务器...")
        
        try:
            # 启动音频输入服务器 (UDP)
            await self._start_audio_input_server()
            
            self.running = True
            logger.info("TouchDesigner测试服务器启动成功")
            logger.info(f"音频输入端口: {self.audio_input_port} (UDP)")
            
            # 启动任务
            tasks = [
                asyncio.create_task(self._audio_input_handler()),
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
        
        # 关闭UDP socket
        if self.audio_input_socket:
            self.audio_input_socket.close()
        
        logger.info("服务器已停止")
        logger.info(f"最终统计: {self.stats}")
    
    async def _start_audio_input_server(self):
        """启动音频输入服务器"""
        self.audio_input_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.audio_input_socket.bind(('0.0.0.0', self.audio_input_port))
        self.audio_input_socket.setblocking(False)
        logger.info(f"音频输入服务器监听 0.0.0.0:{self.audio_input_port}")
    
    
    async def _audio_input_handler(self):
        """处理音频输入"""
        while self.running:
            try:
                # 使用select等待数据可用
                import select
                ready = select.select([self.audio_input_socket], [], [], 1.0)
                
                if ready[0]:
                    # 接收音频数据
                    data, addr = self.audio_input_socket.recvfrom(65535)
                    
                    # 简化的包解析 - 假设是我们的调试格式
                    if len(data) >= 8:
                        length = struct.unpack('<I', data[:4])[0]
                        msg_type = struct.unpack('<I', data[4:8])[0]
                        payload = data[8:8+length]
                        
                        self.stats['audio_packets_received'] += 1
                        logger.info(f"收到数据包: 类型{msg_type}, 长度{length}, 来自{addr}")
                        
                        if msg_type == 1:  # 音频数据
                            logger.info(f"🎵 收到音频数据: {len(payload)} 字节")
                        elif msg_type == 3:  # 状态消息
                            status = payload.decode('utf-8', errors='ignore')
                            logger.info(f"📢 收到状态: {status}")
                        elif msg_type == 4:  # 分片音频
                            if len(data) >= 12:
                                chunk_id = struct.unpack('<H', data[8:10])[0]
                                total_chunks = struct.unpack('<H', data[10:12])[0]
                                logger.info(f"🧩 收到分片: {chunk_id + 1}/{total_chunks}")
                else:
                    # 超时，继续循环
                    await asyncio.sleep(0.1)
                
            except Exception as e:
                if self.running:
                    logger.error(f"音频输入处理错误: {e}")
                await asyncio.sleep(0.1)
    
    
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