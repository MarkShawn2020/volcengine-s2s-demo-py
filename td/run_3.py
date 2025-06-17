import struct
import time


class AudioSender:
    def __init__(self):
        self.lastSendTime = 0
        self.sendInterval = 1.0 / 25.0  # 25Hz发送频率
        print("[Audio Sender] init")

    def sendAudioFrame(self):
        """发送一帧音频数据"""
        current_time = time.time()

        # 控制发送频率
        if current_time - self.lastSendTime < self.sendInterval:
            return

        self.lastSendTime = current_time

        # 获取音频数据
        audioChop = op('audiodevin1')  # 替换为你的音频源
        udpOut = op('udpout1')  # 替换为你的UDP Out DAT

        if not audioChop or not udpOut:
            return

        # 获取最新的音频样本
        try:
            # 获取单声道音频数据
            samples = audioChop.chan(0).vals[-1024:]  # 最后1024个样本

            # 转换为16位PCM
            audio_data = bytes(
                [int(max(-32768, min(32767, s * 32767)))
                 for s in samples]
                )

            # 创建UDP包
            timestamp = int(current_time * 1000000)
            header = struct.pack('<QI', timestamp, len(audio_data))
            packet = header + audio_data

            # 发送
            udpOut.send(packet, asBytes=True)

            # 每100次发送显示一次状态
            if hasattr(self, 'sendCount'):
                self.sendCount += 1
            else:
                self.sendCount = 1

            if self.sendCount % 100 == 0:
                print(f"已发送 {self.sendCount} 个音频包")

        except Exception as e:
            print(f"发送音频失败: {e}")


# 创建发送器实例
if not hasattr(me, 'audioSender'):
    me.audioSender = AudioSender()


def onFrameEnd(frame):
    """每帧结束时调用"""
    if hasattr(me, 'audioSender'):
        me.audioSender.sendAudioFrame()
