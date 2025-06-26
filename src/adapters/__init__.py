from .base import AudioAdapter, ConnectionConfig, LocalConnectionConfig, BrowserConnectionConfig
from .browser_adapter import BrowserAudioAdapter, BrowserConnectionConfig
from .local_adapter import LocalAudioAdapter
from .touchdesigner_adapter import TouchDesignerAudioAdapter, TouchDesignerConnectionConfig
from .touchdesigner_webrtc_adapter import TouchDesignerWebRTCAudioAdapter, TouchDesignerWebRTCConnectionConfig
# 真正的WebRTC适配器需要aiortc依赖
from .touchdesigner_webrtc_proper_adapter import (
    TouchDesignerProperWebRTCAudioAdapter, TouchDesignerProperWebRTCConnectionConfig,
    )
from .type import AdapterType

WEBRTC_PROPER_AVAILABLE = True

__all__ = ["AudioAdapter", "ConnectionConfig", "LocalConnectionConfig", "BrowserConnectionConfig", "AdapterType",
    "LocalAudioAdapter", "BrowserAudioAdapter", "TouchDesignerAudioAdapter", "TouchDesignerConnectionConfig",
    "TouchDesignerWebRTCAudioAdapter", "TouchDesignerWebRTCConnectionConfig", ]

# 如果WebRTC proper可用，添加到导出列表
if WEBRTC_PROPER_AVAILABLE:
    __all__.extend(
        ["TouchDesignerProperWebRTCAudioAdapter", "TouchDesignerProperWebRTCConnectionConfig", ]
        )
