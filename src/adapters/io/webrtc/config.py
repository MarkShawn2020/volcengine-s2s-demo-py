from pydantic import BaseModel


class WebrtcConfig(BaseModel):
    host: str
    port: int

    sample_rate: int
