# file: main_simple.py (最终修正版)

import asyncio
import io
import json
import logging
import queue
import threading

import pyaudio

# 假设你的模块路径是这样的
from src.volcengine import protocol
from src.volcengine.client import VoicengineClient
from src.volcengine.config import start_session_req, ws_connect_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- 音频I/O模块和主应用类的大部分保持不变 ---
def select_audio_device(p, prompt, device_type):
    info = p.get_host_api_info_by_index(0);
    numdevices = info.get('deviceCount');
    print(prompt);
    valid_choices = []
    for i in range(numdevices):
        device_info = p.get_device_info_by_host_api_device_index(0, i)
        if (device_type == 'input' and device_info.get('maxInputChannels') > 0) or (
                device_type == 'output' and device_info.get('maxOutputChannels') > 0):
            print(f"  [{i}] - {device_info.get('name')}");
            valid_choices.append(i)
    if not valid_choices: logger.error("未找到任何可用的设备！"); return None
    while True:
        choice_str = input(f"请选择设备编号 (直接回车选择第一个: {valid_choices[0]}): ")
        if not choice_str: return valid_choices[0]
        try:
            choice = int(choice_str)
            if choice in valid_choices:
                return choice
            else:
                print("无效的编号。")
        except ValueError:
            print("请输入一个数字。")


def recorder_thread(p, device_index, send_q, chunk_size, stop_event):
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=chunk_size,
        input_device_index=device_index
        )
    logger.info("录音线程已启动...");
    while not stop_event.is_set():
        try:
            data = stream.read(chunk_size, exception_on_overflow=False);
            send_q.put(data)
        except IOError:
            break
    stream.stop_stream();
    stream.close();
    logger.info("录音线程已停止。")


def player_thread(p, device_index, play_q, chunk_size, stop_event):
    stream = p.open(
        format=pyaudio.paFloat32,
        channels=1,
        rate=24000,
        output=True,
        frames_per_buffer=chunk_size,
        output_device_index=device_index
        )
    logger.info("播放线程已启动...");
    opus_buffer = io.BytesIO()
    while not stop_event.is_set():
        try:
            item = play_q.get(timeout=1);
            if item is None: continue
            payload = item.get('payload_msg')
            if isinstance(payload, bytes):
                # 'format'现在可以省略，因为播放器只处理它认识的格式
                stream.write(payload)
        except queue.Empty:
            continue
    stream.stop_stream();
    stream.close();
    logger.info("播放线程已停止。")


class RealTimeAudioApp:
    def __init__(self, use_tts_pcm: bool):
        self.use_tts_pcm = use_tts_pcm;
        self.p = pyaudio.PyAudio();
        self.client = VoicengineClient(ws_connect_config)
        self.send_queue = queue.Queue();
        self.play_queue = queue.Queue();
        self.stop_event = threading.Event()
        self.recorder = None;
        self.player = None

    async def _sender_task(self):
        logger.info("发送任务启动。")
        while self.client.is_active:
            try:
                audio_chunk = await asyncio.to_thread(self.send_queue.get, timeout=1.0);
                await self.client.push_audio(
                    audio_chunk
                    )
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"发送任务异常: {e}");
                break
        logger.info("发送任务结束。")

    async def _receiver_task(self):
        logger.info("接收任务启动。")
        while self.client.is_active and not self.stop_event.is_set():
            response = await self.client.on_response()
            if not response or "error" in response: continue

            event = response.get('event')
            if event == protocol.ServerEvent.TTS_RESPONSE:
                self.play_queue.put(response)
            elif event:
                logger.info(
                    f"收到事件: {protocol.ServerEvent(event).name} - "
                    f"{json.dumps(response.get('payload_msg', {}), ensure_ascii=False)}"
                    )

        logger.info("接收任务结束。")

    async def run(self):
        try:
            input_device_index = select_audio_device(self.p, "选择输入设备 (麦克风):", 'input')
            if input_device_index is None: return
            output_device_index = select_audio_device(self.p, "选择输出设备 (扬声器):", 'output')
            if output_device_index is None: return

            if self.use_tts_pcm:
                logger.info("配置为请求 PCM 格式的TTS音频流 (24kHz, Float32)。")
                start_session_req['tts'] = {
                    "audio_config": {
                        "format": "pcm",
                        "sample_rate": 24000
                        }
                    }
            else:
                logger.info("将接收默认的 OGG/Opus 格式音频流。")

            self.recorder = threading.Thread(
                target=recorder_thread, args=(self.p, input_device_index, self.send_queue, 1024, self.stop_event)
                )
            self.player = threading.Thread(
                target=player_thread, args=(self.p, output_device_index, self.play_queue, 1024, self.stop_event)
                )
            self.recorder.start();
            self.player.start()

            await self.client.start()
            if self.client.is_active:
                logger.info("会话建立成功，启动发送和接收任务。")
                await asyncio.gather(self._sender_task(), self._receiver_task())
            else:
                logger.error("无法建立到服务器的会话，程序退出。")
        except Exception as e:
            logger.error(f"应用主循环出现错误!", exc_info=True)
        finally:
            logger.info("开始清理资源...")
            self.stop_event.set()
            if self.client: await self.client.stop()
            if self.recorder and self.recorder.is_alive(): self.recorder.join()
            if self.player and self.player.is_alive(): self.player.join()
            self.p.terminate()
            logger.info("清理完毕，程序退出。")


if __name__ == "__main__":
    use_pcm = True
    print("默认使用PCM模式请求TTS音频。")
    app = RealTimeAudioApp(use_tts_pcm=use_pcm)
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("\n检测到用户中断 (Ctrl+C)。")
