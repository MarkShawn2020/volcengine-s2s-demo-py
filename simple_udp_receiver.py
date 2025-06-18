#!/usr/bin/env python3
"""
简单的UDP接收器
用于调试UDP通信问题
"""

import socket
import struct
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    port = 7002
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', port))
    
    logger.info(f"🎧 简单UDP接收器启动")
    logger.info(f"📡 监听地址: 0.0.0.0:{port}")
    logger.info("-" * 50)
    
    packet_count = 0
    
    try:
        while True:
            data, addr = sock.recvfrom(65535)
            packet_count += 1
            
            logger.info(f"📦 收到数据包 #{packet_count}")
            logger.info(f"   来源: {addr}")
            logger.info(f"   大小: {len(data)} 字节")
            
            if len(data) >= 8:
                length = struct.unpack('<I', data[:4])[0]
                msg_type = struct.unpack('<I', data[4:8])[0]
                
                logger.info(f"   长度: {length}")
                logger.info(f"   类型: {msg_type}")
                
                if msg_type == 1:  # 完整音频
                    logger.info(f"   🎵 完整音频数据")
                elif msg_type == 3:  # 状态
                    payload = data[8:8+length].decode('utf-8', errors='ignore')
                    logger.info(f"   📢 状态: {payload}")
                elif msg_type == 4:  # 分片
                    if len(data) >= 12:
                        chunk_id = struct.unpack('<H', data[8:10])[0]
                        total_chunks = struct.unpack('<H', data[10:12])[0]
                        logger.info(f"   🧩 分片: {chunk_id + 1}/{total_chunks}")
            
            logger.info("-" * 30)
            
    except KeyboardInterrupt:
        logger.info(f"\n🛑 收到中断信号，共收到 {packet_count} 个数据包")
    finally:
        sock.close()


if __name__ == "__main__":
    main()