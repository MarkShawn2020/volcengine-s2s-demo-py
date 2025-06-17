import logging
import os
from typing import Optional

from pydantic import BaseModel, Field

from src.adapters.base import AdapterType
from src.audio.type import AudioType

logger = logging.getLogger(__name__)

VOLCENGINE_APP_ID = os.environ["VOLCENGINE_APP_ID"]
VOLCENGINE_ACCESS_TOKEN = os.environ["VOLCENGINE_ACCESS_TOKEN"]
VOLCENGINE_AUDIO_TYPE: AudioType = os.getenv("VOLCENGINE_AUDIO_TYPE", AudioType.ogg)
VOLCENGINE_BOT_NAME = "小塔"
VOLCENGINE_WELCOME = f"你好，我是{VOLCENGINE_BOT_NAME}，今天很高兴遇见你~"

ADAPTER_TYPE: AdapterType = os.getenv("ADAPTER_TYPE", AdapterType.LOCAL)
logger.info(f"Adapter Type: {ADAPTER_TYPE}")


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
        type: AdapterType

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
                type=ADAPTER_TYPE, )
            )
        logger.info(f"global_config: {global_config.model_dump_json(indent=2)}")
    except Exception as e:
        logger.error(e)
        exit(-1)


validate_config()
