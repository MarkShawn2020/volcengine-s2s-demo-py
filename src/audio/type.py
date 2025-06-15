from enum import StrEnum
from typing_extensions import TypedDict


class AudioConfig(TypedDict):
    """音频配置数据类"""
    format: str
    bit_size: int
    channels: int
    sample_rate: int
    chunk: int


class AudioType(StrEnum):
    pcm = 'pcm'
    ogg = 'ogg'