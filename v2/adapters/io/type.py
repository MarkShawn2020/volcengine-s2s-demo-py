from enum import StrEnum


class AdapterMode(StrEnum):
    system = 'system'
    webrtc = 'webrtc'
    websocket = 'websocket'
