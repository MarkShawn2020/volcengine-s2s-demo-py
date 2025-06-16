from enum import StrEnum

from pydantic import BaseModel


class AudioConfig(BaseModel):
    """音频配置数据类"""
    format: str
    bit_size: int
    channels: int
    sample_rate: int
    chunk: int


class AudioType(StrEnum):
    pcm = 'pcm'
    ogg = 'ogg'
