import os

webrtc_config = {
    "signaling_host": os.getenv("WEBRTC_SIGNALING_HOST", "localhost"),
    "signaling_port": int(os.getenv("WEBRTC_SIGNALING_PORT", "8765")),
}
