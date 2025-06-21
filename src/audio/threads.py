import io
import logging
import queue

import pyaudio

logger = logging.getLogger(__name__)


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
                # 减少播放日志输出频率，避免干扰键盘输入
                # logger.debug(f"播放音频数据: 大小={len(payload)} bytes")
                # 'format'现在可以省略，因为播放器只处理它认识的格式
                stream.write(payload)
            else:
                logger.warning(f"播放队列收到非音频数据: {type(payload)}")
        except queue.Empty:
            continue
    stream.stop_stream();
    stream.close();
    logger.info("播放线程已停止。")
