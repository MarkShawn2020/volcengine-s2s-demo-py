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
    while not stop_event.is_set():
        try:
            item = play_q.get(timeout=1);
            if item is None: continue
            payload = item.get('payload_msg')
            
            # 添加音频数据验证，避免播放无效数据导致滋滋声
            if isinstance(payload, bytes) and len(payload) > 0:
                # 检查音频数据大小是否合理（避免过小的数据包）
                if len(payload) >= 4:  # 至少包含一个float32样本
                    try:
                        stream.write(payload)
                        logger.debug(f"播放音频数据: 大小={len(payload)} bytes")
                    except Exception as e:
                        logger.warning(f"播放音频数据失败: {e}")
                else:
                    logger.debug(f"跳过过小的音频数据包: {len(payload)} bytes")
            else:
                logger.warning(f"播放队列收到无效数据: {type(payload)}, 大小: {len(payload) if isinstance(payload, bytes) else 'N/A'}")
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"播放线程异常: {e}")
            break
    stream.stop_stream();
    stream.close();
    logger.info("播放线程已停止。")
