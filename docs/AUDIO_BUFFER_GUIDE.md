# 音频缓冲区大小配置指南

## 问题背景

在实时语音对话系统中，音频缓冲区大小（chunk size）的配置对不同设备的兼容性有重大影响。

## 关键发现

### AirPods等蓝牙设备兼容性问题

**现象**：
- Python版本 + 系统麦克风：正常工作
- Python版本 + AirPods：无法收到服务器后续响应
- Go版本 + AirPods：正常工作

**根本原因**：音频缓冲区大小配置差异

## 技术分析

### 1. 延迟影响

| 配置 | Chunk Size | 延迟计算 | 实际延迟 | 适用性 |
|------|------------|----------|----------|--------|
| Python原配置 | 3200 samples | 3200 ÷ 16000 Hz | 200ms | ❌ 延迟过高 |
| Go配置 | 160 samples | 160 ÷ 16000 Hz | 10ms | ✅ 实时对话 |
| Python修正后 | 1600 samples | 1600 ÷ 16000 Hz | 100ms | ⚠️ 可接受但不理想 |

### 2. 蓝牙设备特殊要求

**蓝牙协议限制**：
- 蓝牙有固定时间片（7.5ms或15ms）
- 大缓冲区跨越多个蓝牙时间片
- 容易导致同步问题和音频丢失

**AirPods vs 系统麦克风**：
- **系统麦克风**：直接硬件连接，容错性强，可处理大缓冲区
- **AirPods**：通过蓝牙协议，需要严格时序控制

### 3. 最佳实践建议

**实时语音应用的缓冲区大小**：
- **5-20ms（80-320 samples @ 16kHz）**：最佳实时性，推荐用于语音对话
- **20-50ms（320-800 samples @ 16kHz）**：可接受延迟
- **>100ms（>1600 samples @ 16kHz）**：明显延迟，不适合实时对话

## 配置建议

### 推荐配置（兼容所有设备）

```python
input_audio_config = {
    "chunk": 160,  # 10ms延迟，最佳实时性
    "format": "pcm",
    "channels": 1,
    "sample_rate": 16000,
    "bit_size": pyaudio.paInt16
}
```

### 平衡配置（性能和兼容性）

```python
input_audio_config = {
    "chunk": 320,  # 20ms延迟，平衡选择
    "format": "pcm", 
    "channels": 1,
    "sample_rate": 16000,
    "bit_size": pyaudio.paInt16
}
```

## 故障排查

如果遇到蓝牙设备音频问题：

1. **检查chunk size**：确保 ≤ 800 samples（50ms @ 16kHz）
2. **测试延迟**：计算公式 = chunk_size ÷ sample_rate
3. **设备对比**：用系统麦克风测试是否正常
4. **日志分析**：查看是否收到服务器响应

## 技术细节

### Go版本成功的原因

```go
FramesPerBuffer: 160  // 10ms缓冲区，适合实时处理
Latency: defaultInputDevice.DefaultLowInputLatency  // 显式低延迟配置
```

### Python版本问题

```python
"chunk": 3200  # 200ms缓冲区 - 对AirPods来说太大
# 缺少显式延迟配置
```

## 结论

音频缓冲区大小是实时语音系统中的关键参数，特别是对蓝牙设备的兼容性有决定性影响。建议使用小缓冲区（5-20ms）以确保最佳的实时性和设备兼容性。