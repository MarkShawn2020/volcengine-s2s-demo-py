import os
from typing import Optional

from pydantic import BaseModel, Field

from src.audio.type import AudioType
from src.io_adapters.type import AdapterMode
from src.io_adapters.webrtc.config import WebrtcConfig
from src.io_adapters.websocket.config import WebsocketConfig
from src.utils.logger import logger

VOLCENGINE_APP_ID = os.environ["VOLCENGINE_APP_ID"]
VOLCENGINE_ACCESS_TOKEN = os.environ["VOLCENGINE_ACCESS_TOKEN"]
VOLCENGINE_AUDIO_TYPE: AudioType = os.getenv("VOLCENGINE_AUDIO_TYPE", AudioType.ogg)
VOLCENGINE_BOT_NAME = "小塔"
VOLCENGINE_WELCOME = f"你好，我是{VOLCENGINE_BOT_NAME}，今天很高兴遇见你~"

ADAPTER_MODE: AdapterMode = os.getenv("ADAPTER_MODE", AdapterMode.system)
logger.info(f"Adapter Mode: {ADAPTER_MODE}")

webrtc_config = WebrtcConfig(
    host=os.getenv("WEBRTC_HOST", "localhost"), port=os.getenv("WEBRTC_PORT", 8765)
    )

websocket_config = WebsocketConfig(
    host=os.getenv("SOCKET_HOST", "localhost"), port=int(os.getenv("SOCKET_PORT", "8888"))
    )


def validate_config():
    class VolcengineConfig(
        BaseModel
        ):
        app_id: str = Field(min_length=1)
        access_token: str = Field(min_length=1)
        audio_type: AudioType
        bot_name: str = Field(min_length=1)
        welcome: Optional[str] = Field(min_length=1)

    class AdaptersConfig(BaseModel):
        mode: AdapterMode
        webrtc: Optional[WebrtcConfig]
        websocket: Optional[WebsocketConfig]

    class GlobalConfig(BaseModel):
        volcengine: VolcengineConfig
        adapter: AdaptersConfig

    try:
        global_config = GlobalConfig(
            volcengine=VolcengineConfig(
                app_id=VOLCENGINE_APP_ID,
                access_token=VOLCENGINE_ACCESS_TOKEN,
                audio_type=VOLCENGINE_AUDIO_TYPE,
                bot_name=VOLCENGINE_BOT_NAME,
                welcome=VOLCENGINE_WELCOME
                ),

            adapter=AdaptersConfig(
                mode=ADAPTER_MODE, webrtc=webrtc_config, websocket=websocket_config
                )
            )
        logger.info(f"global_config: {global_config.model_dump_json(indent=2)}")
    except Exception as e:
        logger.error(e)
        exit(-1)


validate_config()
