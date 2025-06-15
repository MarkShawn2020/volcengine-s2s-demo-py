from typing_extensions import TypedDict


class WebsocketConfig(TypedDict):
    """Socket配置数据类"""
    host: str
    port: int
