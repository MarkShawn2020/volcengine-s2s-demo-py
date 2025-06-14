import os

socket_config = {
    "host": os.getenv("SOCKET_HOST", "localhost"),
    "port": int(os.getenv("SOCKET_PORT", "8888")),
}
