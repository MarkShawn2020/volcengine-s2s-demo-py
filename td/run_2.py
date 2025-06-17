import json
import struct
import time


class VolcEngineInterface:
    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.tcpDat = op('tcp1')  # 你的TCP DAT名称
        self.udpInDat = op('udp_in1')  # UDP接收DAT名称
        self.udpOutDat = op('udp_out1')  # UDP发送DAT名称

    def onReceive(self, dat):
        """处理接收到的TCP控制消息"""
        if dat == self.tcpDat:
            # 处理控制消息
            data = dat.text
            if data:
                try:
                    # 解析JSON消息
                    lines = data.strip().split('\n')
                    for line in lines:
                        if line:
                            message = json.loads(line)
                            self.handleControlMessage(message)
                except:
                    pass

        elif dat == self.udpInDat:
            # 处理音频数据
            self.handleAudioData(dat.bytes)

    def handleControlMessage(self, message):
        """处理控制消息"""
        msg_type = message.get('type')

        if msg_type == 'init':
            print("收到初始化消息")
            # 发送响应
            response = {
                'type': 'init_response',
                'status': 'success'
                }
            self.sendControlMessage(response)

        elif msg_type == 'text':
            content = message.get('content', '')
            print(f"收到文本: {content}")

        elif msg_type == 'ping':
            # 回复pong
            self.sendControlMessage(
                {
                    'type': 'pong'
                    }
                )

    def sendControlMessage(self, message):
        """发送控制消息"""
        try:
            message_json = json.dumps(message)
            # TCP DAT会自动处理发送
            self.tcpDat.send(message_json)
        except Exception as e:
            print(f"发送控制消息失败: {e}")

    def handleAudioData(self, audio_bytes):
        """处理接收到的音频数据"""
        if len(audio_bytes) < 12:
            return

        # 解析音频包头
        timestamp, data_length = struct.unpack('<QI', audio_bytes[:12])
        audio_data = audio_bytes[12:12 + data_length]

        # 在这里处理音频数据
        # 可以发送到Audio Device Out或其他音频处理组件
        print(f"收到音频数据: {len(audio_data)} 字节")

    def sendAudioData(self, audio_data):
        """发送音频数据到Python"""
        try:
            # 创建包头
            timestamp = int(time.time() * 1000000)
            header = struct.pack('<QI', timestamp, len(audio_data))
            packet = header + audio_data

            # 通过UDP发送
            self.udpOutDat.send(packet)

        except Exception as e:
            print(f"发送音频失败: {e}")


# 创建接口实例
interface = VolcEngineInterface(me)