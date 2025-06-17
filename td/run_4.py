import struct
import time

lastSendTime = 0
sendInterval = 1.0 / 25.0  # 25Hz发送频率


def onFrameEnd(frame):
    global lastSendTime, sendInterval

    """每帧发送音频（60fps = 每秒60次）"""
    # 限制发送频率到25Hz
    """发送一帧音频数据"""
    current_time = time.time()

    # 控制发送频率
    if current_time - lastSendTime < sendInterval:
        return

    lastSendTime = current_time

    # 获取音频数据 - 尝试不同的可能名称
    audioChop = None
    possible_names = ['audiodevin1', 'audiodevicein1', 'microphone1', 'mic1', 'audio1']
    
    for name in possible_names:
        try:
            chop = op(name)
            if chop and chop.numChans > 0 and chop.numSamples > 0:
                audioChop = chop
                print(f"找到音频源: {name}")
                break
        except:
            continue
    
    udpOut = op('udp_out1')  # 替换为你的UDP Out DAT名称

    if not audioChop:
        print("未找到音频源，请检查音频CHOP名称")
        return
        
    if not udpOut:
        print("未找到UDP Out DAT")
        return
    
    # 显示音频源信息
    if frame % 150 == 0:  # 每5秒显示一次
        print(f"音频源信息: 通道数={audioChop.numChans}, 样本数={audioChop.numSamples}, 采样率={audioChop.rate}")

    # 获取并发送真实音频数据
    try:
        # 获取单声道音频数据
        samples = audioChop.chan(0).vals[-1024:]  # 最后1024个样本

        # 转换为16位PCM
        audio_samples = []
        for s in samples:
            # 限制到-1.0到1.0范围，然后转换为16位整数
            sample_int = int(max(-32768, min(32767, s * 32767)))
            audio_samples.append(sample_int)

        # 打包为16位小端序有符号整数
        audio_data = struct.pack('<' + 'h' * len(audio_samples), *audio_samples)
        
        # 创建UDP包
        timestamp = int(current_time * 1000000)
        header = struct.pack('<QI', timestamp, len(audio_data))
        packet = header + audio_data

        # 使用sendBytes发送二进制数据
        print("sending....")
        udpOut.sendBytes(packet)

    except Exception as e:
        print(f"发送音频失败: {e}")
