#!/usr/bin/env python3
"""
UDP通信调试工具
用于验证UDP发送和接收是否正常工作
"""

import socket
import struct
import time
import threading
import numpy as np


def test_udp_sender(target_ip="localhost", target_port=7002, interval=2):
    """测试UDP发送"""
    print(f"🚀 开始UDP发送测试")
    print(f"📡 目标地址: {target_ip}:{target_port}")
    print(f"⏰ 发送间隔: {interval}秒")
    print("-" * 50)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # 测试数据
    test_messages = [
        # 状态消息
        {"type": 3, "data": "测试连接".encode('utf-8')},
        
        # 简单音频数据 (1秒16kHz单声道静音)
        {"type": 1, "data": np.zeros(16000, dtype=np.int16).tobytes()},
        
        # 分片音频数据 (模拟大音频文件)
        {"type": 4, "data": np.random.randint(-1000, 1000, 36000, dtype=np.int16).tobytes()},
    ]
    
    message_count = 0
    
    try:
        while True:
            for msg in test_messages:
                message_count += 1
                
                if msg["type"] == 4:  # 分片音频
                    # 模拟音频分片发送
                    audio_data = msg["data"]
                    chunk_size = 8000  # 每个分片8KB
                    total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size
                    
                    print(f"📦 发送分片音频 #{message_count}: {len(audio_data)}字节, {total_chunks}个分片")
                    
                    for chunk_id in range(total_chunks):
                        start = chunk_id * chunk_size
                        end = min(start + chunk_size, len(audio_data))
                        chunk_data = audio_data[start:end]
                        
                        # 构造分片包
                        length = len(chunk_data) + 4  # +4 for chunk_id and total_chunks
                        packet = (
                            struct.pack('<I', length) +           # 总长度
                            struct.pack('<I', msg["type"]) +      # 消息类型
                            struct.pack('<H', chunk_id) +         # 分片ID
                            struct.pack('<H', total_chunks) +     # 总分片数
                            chunk_data                            # 分片数据
                        )
                        
                        sock.sendto(packet, (target_ip, target_port))
                        print(f"   📤 发送分片 {chunk_id + 1}/{total_chunks}: {len(chunk_data)}字节")
                        time.sleep(0.1)  # 分片间隔
                        
                else:
                    # 普通消息
                    data = msg["data"]
                    length = len(data)
                    
                    packet = (
                        struct.pack('<I', length) +
                        struct.pack('<I', msg["type"]) +
                        data
                    )
                    
                    sock.sendto(packet, (target_ip, target_port))
                    
                    if msg["type"] == 3:
                        print(f"📤 发送状态消息 #{message_count}: {data.decode('utf-8', errors='ignore')}")
                    elif msg["type"] == 1:
                        print(f"📤 发送音频数据 #{message_count}: {length}字节")
                
                time.sleep(interval)
                
    except KeyboardInterrupt:
        print(f"\n🛑 发送测试中断，共发送 {message_count} 条消息")
    finally:
        sock.close()


def test_udp_receiver(listen_port=7002):
    """测试UDP接收"""
    print(f"🎧 开始UDP接收测试")
    print(f"📡 监听端口: {listen_port}")
    print("-" * 50)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', listen_port))
    sock.settimeout(1.0)
    
    packet_count = 0
    audio_chunks = {}
    
    try:
        while True:
            try:
                data, addr = sock.recvfrom(65535)
                packet_count += 1
                
                print(f"📦 收到数据包 #{packet_count}")
                print(f"   来源: {addr}")
                print(f"   大小: {len(data)} 字节")
                
                if len(data) >= 8:
                    length = struct.unpack('<I', data[:4])[0]
                    msg_type = struct.unpack('<I', data[4:8])[0]
                    
                    print(f"   类型: {msg_type}, 长度: {length}")
                    
                    if msg_type == 1:  # 完整音频
                        audio_data = data[8:8 + length]
                        print(f"   🎵 音频数据: {len(audio_data)} 字节")
                        
                    elif msg_type == 3:  # 状态
                        status_data = data[8:8 + length].decode('utf-8', errors='ignore')
                        print(f"   📢 状态: {status_data}")
                        
                    elif msg_type == 4:  # 分片音频
                        if len(data) >= 12:
                            chunk_id = struct.unpack('<H', data[8:10])[0]
                            total_chunks = struct.unpack('<H', data[10:12])[0]
                            chunk_data = data[12:12 + length - 4]
                            
                            print(f"   🧩 分片: {chunk_id + 1}/{total_chunks}, {len(chunk_data)} 字节")
                            
                            if chunk_id == 0:
                                audio_chunks.clear()
                            audio_chunks[chunk_id] = chunk_data
                            
                            if len(audio_chunks) == total_chunks:
                                complete_audio = b''.join(audio_chunks[i] for i in range(total_chunks))
                                print(f"   ✅ 重组完成: {len(complete_audio)} 字节")
                                audio_chunks.clear()
                
                print("-" * 30)
                
            except socket.timeout:
                print("⏰ 等待数据包...")
                continue
                
    except KeyboardInterrupt:
        print(f"\n🛑 接收测试中断，共收到 {packet_count} 个数据包")
    finally:
        sock.close()


def test_network_connectivity():
    """测试网络连通性"""
    print("🔍 测试网络连通性")
    print("-" * 50)
    
    # 测试端口是否被占用
    ports_to_test = [7001, 7002, 7003]
    
    for port in ports_to_test:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(('localhost', port))
            print(f"✅ 端口 {port} 可用")
            sock.close()
        except OSError as e:
            print(f"❌ 端口 {port} 被占用: {e}")
        finally:
            try:
                sock.close()
            except:
                pass
    
    # 测试localhost解析
    try:
        localhost_ip = socket.gethostbyname('localhost')
        print(f"✅ localhost 解析为: {localhost_ip}")
    except Exception as e:
        print(f"❌ localhost 解析失败: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="UDP通信调试工具")
    parser.add_argument("--mode", choices=["send", "receive", "test"], default="test", 
                       help="运行模式: send(发送测试), receive(接收测试), test(网络测试)")
    parser.add_argument("--ip", default="localhost", help="目标IP地址")
    parser.add_argument("--port", type=int, default=7002, help="端口号")
    parser.add_argument("--interval", type=int, default=3, help="发送间隔(秒)")
    
    args = parser.parse_args()
    
    if args.mode == "send":
        test_udp_sender(args.ip, args.port, args.interval)
    elif args.mode == "receive":
        test_udp_receiver(args.port)
    elif args.mode == "test":
        test_network_connectivity()
        print("\n" + "="*50)
        print("🚀 现在开始实际的发送/接收测试")
        print("请在另一个终端运行: python debug_udp.py --mode receive")
        print("然后在第三个终端运行: python debug_udp.py --mode send")
        print("="*50)


if __name__ == "__main__":
    main()