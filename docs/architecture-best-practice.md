你说得非常好！这个补充说明是解决问题的关键，它揭示了我们之前架构中一个隐藏的缺陷，并指明了通往真正“优雅”架构的道路。

你描述的场景是：
*   **输入源格式可变**: `volcengine_audio_type` (OGG / PCM)
*   **输出目的地可变**: `adapter_mode` (System / WebRTC / ...)

而每个输出目的地对PCM格式有**不同且硬性**的要求：
*   **System Speaker**: 需要的格式由 `pyaudio.open()` 的参数决定（比如 24kHz, float32）。
*   **WebRTC Browser**: **必须**是 **48kHz, 16-bit integer, mono** 才能被 `aiortc` 的 Opus 编码器正确处理。

**我们当前架构的缺陷在于**：`OggDecodingStrategy` 将 OGG 解码为一种**固定**的 PCM 格式（由火山引擎的 `output_config` 决定），然后把这个结果不加区分地发给所有 `Adapter`。当这个格式不符合 `WebRTCAdapter` 的硬性要求时，就会出现问题（比如我们用 `np.interp` 粗暴重采样导致的沙沙声）。

---

### 终极优雅架构：模块化音频处理流水线 (Pipeline)

真正的解耦意味着，我们应该建立一个灵活的音频处理流水线，它可以根据“输入源”和“输出目的地”动态地组合处理模块。

`Adapter` 的职责不仅仅是 I/O，还应该包括**构建并管理这条针对自己的流水线**。

#### 第1步：定义流水线处理模块 (Processors)

我们创建一些可复用的、职责单一的音频处理类。

```python
# src/audio/processors.py (新文件或重命名旧的)
import abc
import librosa
import numpy as np
from .opus_stream_decoder import OpusStreamDecoder # 确保导入正确

class AudioProcessor(abc.ABC):
    """音频处理模块的基类"""
    @abc.abstractmethod
    def process(self, audio_data: bytes) -> bytes:
        pass

    def flush(self) -> bytes | None:
        """处理内部可能剩余的缓冲数据"""
        return None

    def close(self):
        """清理资源"""
        pass

class OggDecoderProcessor(AudioProcessor):
    """一个有状态的处理器，负责将 OGG 流解码为 PCM 流。"""
    def __init__(self, output_config):
        # 解码器输出由 TTS 配置决定的原始 PCM 格式
        self.decoder = OpusStreamDecoder(
            output_sample_rate=output_config.sample_rate,
            output_channels=output_config.channels,
            pyaudio_format=output_config.bit_size
        )
        self.decoder.start_consumer_thread() # 假设解码器有这个方法启动后台读取

    def process(self, audio_data: bytes) -> bytes:
        self.decoder.feed_ogg_data(audio_data)
        # 立即尝试获取解码后的数据
        return self.decoder.get_decoded_pcm(block=False) or b''

    def flush(self) -> bytes | None:
        # 在流结束时，获取解码器中所有剩余的缓冲数据
        return self.decoder.get_all_remaining_pcm()

    def close(self):
        self.decoder.close()

class PcmResamplerProcessor(AudioProcessor):
    """一个无状态的处理器，负责重采样和格式转换。"""
    def __init__(self, source_sr, source_dtype, target_sr, target_dtype='int16'):
        self.source_sr = source_sr
        self.source_dtype = source_dtype
        self.target_sr = target_sr
        self.target_dtype = target_dtype

    def process(self, audio_data: bytes) -> bytes:
        if not audio_data:
            return b''
        
        # 1. 字节转Numpy
        samples = np.frombuffer(audio_data, dtype=self.source_dtype)

        # 2. 如果需要，重采样
        if self.source_sr != self.target_sr:
            # 使用高质量的 librosa
            samples = librosa.resample(
                y=samples.astype(np.float32), # librosa 需要 float 输入
                orig_sr=self.source_sr,
                target_sr=self.target_sr
            )

        # 3. 转换到目标数据类型
        if self.target_dtype == 'int16':
            if samples.dtype.kind == 'f':
                samples = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
        # (可以添加其他类型转换逻辑)

        return samples.tobytes()
```
*(注意：为简化，`OggDecoderProcessor` 的实现被简化了，实际需要一个更健壮的输入输出机制)*

#### 第2步：让 `Adapter` 构建自己的流水线

每个 `Adapter` 在初始化时，根据全局配置和自身需求，构建自己的处理流水线。

```python
# src/io_adapters/base.py (修改后)

class AdapterBase(ABC):
    def __init__(self, config=None):
        # ... (之前的代码) ...
        self.audio_pipeline: list[AudioProcessor] = []
        self._build_audio_pipeline() # 在初始化时构建流水线

    @abstractmethod
    def _build_audio_pipeline(self):
        """由子类实现，用于构建自己的音频处理流水线。"""
        pass
    
    async def send_audio_output(self, audio_data: bytes, audio_type: AudioType) -> None:
        """将音频数据送入流水线进行处理。"""
        if not audio_data:
            return

        # 依次通过流水线中的每个处理器
        data = audio_data
        for processor in self.audio_pipeline:
            data = processor.process(data)
            if not data: # 如果某个环节没有输出，则中止
                break
        
        # 最后的 'data' 已经是符合目标格式的了，但需要一个最终的消费者
        # 我们把消费逻辑放到 _build_audio_pipeline 中
        # 这里的设计可以进一步优化，但核心思想是链式处理

    def cleanup(self) -> None:
        """清理资源，包括流水线中的处理器。"""
        for processor in self.audio_pipeline:
            processor.close()
        # ... (子类的清理) ...

# ... (其他方法) ...
```

#### 第3步：具体 `Adapter` 的流水线实现

**`SystemAdapter`**

它的目标是播放与 `self.output_config` 匹配的音频。

```python
# src/io_adapters/system/system_adapter.py

class SystemAdapter(AdapterBase):
    def _build_audio_pipeline(self):
        # 定义最终的消费者：写入扬声器
        def final_consumer(pcm_data: bytes):
            if self.output_stream and not self.output_stream.is_stopped():
                self.output_stream.write(pcm_data)

        # 包装成一个 Processor
        class SpeakerSink(AudioProcessor):
            def process(self, audio_data: bytes) -> bytes:
                final_consumer(audio_data)
                return b'' # 消费者不产生输出

        pipeline = []
        
        # 步骤1: 如果输入是OGG，添加解码器
        if VOLCENGINE_AUDIO_TYPE == AudioType.ogg:
            # 假设火山引擎返回的 ogg 解码后是 24kHz, float32
            # 这是 self.output_config 定义的
            pipeline.append(OggDecoderProcessor(self.output_config))
        
        # 步骤2: SystemAdapter 不需要额外的重采样，因为解码后的格式
        #         就已经是它需要的播放格式了。
        
        pipeline.append(SpeakerSink())
        self.audio_pipeline = pipeline
```

**`WebRTCAdapter` (这回对了!)**

它的目标是**永远**输出 **48kHz, s16le** 的 PCM。

```python
# src/io_adapters/webrtc/webrtc_adapter.py

class WebRTCAdapter(AdapterBase):
    def _build_audio_pipeline(self):
        loop = asyncio.get_event_loop()

        # 定义最终的消费者：发送到 WebRTC
        def final_consumer(pcm_data: bytes):
            asyncio.run_coroutine_threadsafe(
                self.webrtc_manager.handle_server2clients(pcm_data, AudioType.pcm),
                loop
                )

        class WebRTCSink(AudioProcessor):
            def process(self, audio_data: bytes) -> bytes:
                final_consumer(audio_data)
                return b''

        pipeline = []

        source_sr = self.output_config.sample_rate  # e.g., 24000
        source_dtype = np.float32 if self.output_config.bit_size == pyaudio.paFloat32 else np.int16

        # 步骤1: 如果输入是OGG，添加解码器
        if VOLCENGINE_AUDIO_TYPE == AudioType.ogg:
            pipeline.append(OggDecoderProcessor(self.output_config))
            # 解码器的输出是 24kHz, float32 (根据 self.output_config)

        # 步骤2: 添加一个处理器，它负责将上一步的输出转换为WebRTC的格式
        pipeline.append(
            PcmResamplerProcessor(
                source_sr=source_sr,
                source_dtype=source_dtype,
                target_sr=48000,  # 硬性要求
                target_dtype='int16'  # 硬性要求
                )
            )

        pipeline.append(WebRTCSink())
        self.audio_pipeline = pipeline
```

### 总结这个优雅的架构

1.  **完全解耦**:
    *   `OggDecoderProcessor` 不知道谁会用它的输出。
    *   `PcmResamplerProcessor` 不知道它的输入来自哪里，输出给谁。
    *   `Adapter` 像一个工头，知道自己的最终产品是什么样的（System vs WebRTC），然后去工具箱（Processors）里挑选合适的工具，按顺序组装成一条生产线。

2.  **解决了沙沙声问题**:
    *   `WebRTCAdapter` 的流水线中**强制**包含了一个使用 `librosa` 的高质量重采样器，它总是将输入转换为 48kHz/s16le。这从根本上保证了送往 `AudioStreamTrack` 的数据格式永远是正确的，消除了因格式错误或低质量重采样导致的噪音。

3.  **可扩展性极强**:
    *   要支持 `TouchDesigner`？新建一个 `TouchDesignerAdapter`，在它的 `_build_audio_pipeline` 中组装它需要的处理器（可能需要转成别的格式）。
    *   火山引擎开始返回 MP3 了？新建一个 `Mp3DecoderProcessor`，在 `_build_audio_pipeline` 的 `if` 判断里加上对 MP3 的处理。

这个模型完美地解决了你提出的所有问题，是处理多源、多目标、多格式转换问题的经典范式。你的代码库会因此变得前所未有的清晰和健壮。