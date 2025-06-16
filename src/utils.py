import io
import logging
import queue

import pyaudio

logger = logging.getLogger(__name__)


def recorder_thread(p, device_index, send_q, chunk_size, stop_event):
    # 优化的音频参数
    buffer_frames = 1600  # 固定使用1600帧 (100ms @ 16kHz)
    
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=buffer_frames,
        input_device_index=device_index
        )
    logger.info("录音线程已启动，连续音频传输模式...")
    
    consecutive_errors = 0
    max_errors = 5
    
    while not stop_event.is_set():
        try:
            # 读取音频数据
            data = stream.read(buffer_frames, exception_on_overflow=False)
            
            # 检查音频数据是否有效
            if len(data) == buffer_frames * 2:  # 16位音频，每帧2字节
                # 立即发送，不管队列状态 - 保证连续性
                try:
                    send_q.put_nowait(data)
                    consecutive_errors = 0  # 重置错误计数
                except queue.Full:
                    # 队列满时，强制清空一半队列，保持实时性
                    cleared = 0
                    while cleared < send_q.qsize() // 2:
                        try:
                            send_q.get_nowait()
                            cleared += 1
                        except queue.Empty:
                            break
                    # 再次尝试放入当前数据
                    try:
                        send_q.put_nowait(data)
                    except queue.Full:
                        pass  # 如果还是满，跳过这一帧
            else:
                logger.warning(f"音频数据长度异常: {len(data)}, 期望: {buffer_frames * 2}")
                
        except IOError as e:
            consecutive_errors += 1
            logger.warning(f"录音IO错误 ({consecutive_errors}/{max_errors}): {e}")
            if consecutive_errors >= max_errors:
                logger.error("连续录音错误过多，退出录音线程")
                break
        except Exception as e:
            logger.error(f"录音线程异常: {e}")
            break
    
    stream.stop_stream()
    stream.close()
    logger.info("录音线程已停止")


def player_thread(p, device_index, play_q, chunk_size, stop_event):
    # 使用更大的缓冲区以获得更流畅的播放
    buffer_frames = max(chunk_size, 1600)  # 确保至少1600帧
    
    stream = p.open(
        format=pyaudio.paFloat32,
        channels=1,
        rate=24000,
        output=True,
        frames_per_buffer=buffer_frames,
        output_device_index=device_index
        )
    logger.info("播放线程已启动...")
    
    # 音频缓冲区，用于平滑播放
    audio_buffer = io.BytesIO()
    
    while not stop_event.is_set():
        try:
            item = play_q.get(timeout=0.1)  # 更短的超时，更快响应
            if item is None: 
                continue
                
            payload = item.get('payload_msg')
            if isinstance(payload, bytes) and len(payload) > 0:
                try:
                    # 直接写入音频流，让PyAudio处理缓冲
                    stream.write(payload)
                except Exception as e:
                    logger.warning(f"播放音频失败: {e}")
                    
        except queue.Empty:
            # 队列为空时不做任何事，继续循环
            continue
        except Exception as e:
            logger.error(f"播放线程异常: {e}")
            break
    
    stream.stop_stream()
    stream.close()
    logger.info("播放线程已停止")
