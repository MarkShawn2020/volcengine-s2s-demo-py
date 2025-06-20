from enum import Enum


class AdapterType(Enum):
    LOCAL = "local"
    BROWSER = "browser"
    TOUCH_DESIGNER = "touchdesigner"
    TOUCH_DESIGNER_WEBRTC = "touchdesigner_webrtc"
    TOUCH_DESIGNER_WEBRTC_PROPER = "touchdesigner_webrtc_proper"
    TEXT_INPUT = "text_input"
