from src.audio.processors.ogg2pcm.opus_stream_decoder import OpusStreamDecoder
from src.audio.processors.base import AudioProcessor


class Ogg2PcmProcessor(AudioProcessor):
    """一个有状态的处理器，负责将 OGG 流解码为 PCM 流。"""

    def __init__(self, output_config):
        self.decoder = OpusStreamDecoder(
            output_sample_rate=output_config.sample_rate,
            output_channels=output_config.channels,
            pyaudio_format=output_config.bit_size
        )

    def process(self, audio_data: bytes) -> bytes:
        self.decoder.feed_ogg_data(audio_data)
        return self.decoder.get_decoded_pcm(block=False) or b''

    def flush(self) -> bytes | None:
        remaining_data = b''
        while True:
            chunk = self.decoder.get_decoded_pcm(block=False, timeout=0.1)
            if not chunk:
                break
            remaining_data += chunk
        return remaining_data if remaining_data else None

    def close(self):
        self.decoder.close()
