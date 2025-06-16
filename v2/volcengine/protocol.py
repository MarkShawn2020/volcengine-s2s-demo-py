import gzip
import json
from enum import IntEnum

PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001

PROTOCOL_VERSION_BITS = 4
HEADER_BITS = 4
MESSAGE_TYPE_BITS = 4
MESSAGE_TYPE_SPECIFIC_FLAGS_BITS = 4
MESSAGE_SERIALIZATION_BITS = 4
MESSAGE_COMPRESSION_BITS = 4
RESERVED_BITS = 8

# Message Type:
CLIENT_FULL_REQUEST = 0b0001
CLIENT_AUDIO_ONLY_REQUEST = 0b0010

SERVER_FULL_RESPONSE = 0b1001
SERVER_AUDIO_ONLY_RESPONSE = 0b1011  # <--- **新增**: 根据文档，这是音频响应
SERVER_ACK = 0b1011 # 文档显示 ACK 和 Audio-only response 值相同，但我们可以区分使用
SERVER_ERROR_RESPONSE = 0b1111

# Message Type Specific Flags
NO_SEQUENCE = 0b0000  # no check sequence
POS_SEQUENCE = 0b0001
NEG_SEQUENCE = 0b0010
NEG_SEQUENCE_1 = 0b0011

MSG_WITH_EVENT = 0b0100

# Message Serialization
NO_SERIALIZATION = 0b0000
JSON = 0b0001
THRIFT = 0b0011
CUSTOM_TYPE = 0b1111

# Message Compression
NO_COMPRESSION = 0b0000
GZIP = 0b0001
CUSTOM_COMPRESSION = 0b1111


def generate_header(
    version=PROTOCOL_VERSION,
    message_type=CLIENT_FULL_REQUEST,
    message_type_specific_flags=MSG_WITH_EVENT,
    serial_method=JSON,
    compression_type=GZIP,
    reserved_data=0x00,
    extension_header=bytes()
    ):
    """
    protocol_version(4 bits), header_size(4 bits),
    message_type(4 bits), message_type_specific_flags(4 bits)
    serialization_method(4 bits) message_compression(4 bits)
    reserved （8bits) 保留字段
    header_extensions 扩展头(大小等于 8 * 4 * (header_size - 1) )
    """
    header = bytearray()
    header_size = int(len(extension_header) / 4) + 1
    header.append((version << 4) | header_size)
    header.append((message_type << 4) | message_type_specific_flags)
    header.append((serial_method << 4) | compression_type)
    header.append(reserved_data)
    header.extend(extension_header)
    return header


def parse_response(res):
    """
    - header
        - (4bytes)header
        - (4bits)version(v1) + (4bits)header_size
        - (4bits)messageType + (4bits)messageTypeFlags
            -- 0001	CompleteClient | -- 0001 hasSequence
            -- 0010	audioonly      | -- 0010 isTailPacket
                                           | -- 0100 hasEvent
        - (4bits)payloadFormat + (4bits)compression
        - (8bits) reserve
    - payload
        - [optional 4 bytes] event
        - [optional] session ID
          -- (4 bytes)session ID len
          -- session ID data
        - (4 bytes)data len
        - data
    """

    if not isinstance(res, bytes) or len(res) < 4:
        return {}

    header_size = res[0] & 0x0f
    message_type = res[1] >> 4
    message_type_specific_flags = res[1] & 0x0f
    serialization_method = res[2] >> 4
    message_compression = res[2] & 0x0f

    payload_start_offset = header_size * 4
    payload = res[payload_start_offset:]

    result = {
        'message_type': message_type
        }

    # 根据文档，可选字段在payload的开头
    current_offset = 0

    # 文档指出 event 是必须的，所以我们总是先解析它
    if message_type_specific_flags & MSG_WITH_EVENT > 0:
        result['event'] = int.from_bytes(payload[current_offset:current_offset + 4], "big")
        current_offset += 4

    # Session ID
    session_id_size = int.from_bytes(payload[current_offset:current_offset + 4], "big")
    current_offset += 4
    result['session_id'] = payload[current_offset:current_offset + session_id_size].decode('utf-8')
    current_offset += session_id_size

    # 最后的 payload
    payload_size = int.from_bytes(payload[current_offset:current_offset + 4], "big")
    current_offset += 4
    payload_msg = payload[current_offset:current_offset + payload_size]

    # 只有在不是音频的情况下才尝试解压和解码
    # 服务端事件TTSResponse(352)是音频裸流
    event_id = result.get('event')
    if event_id == 352:  # TTSResponse, payload 是音频
        result['payload_msg'] = payload_msg
    else:  # 其他是JSON
        if message_compression == GZIP:
            payload_msg = gzip.decompress(payload_msg)
        if serialization_method == JSON and payload_msg:
            result['payload_msg'] = json.loads(payload_msg.decode('utf-8'))
        else:
            result['payload_msg'] = payload_msg  # 保留原始字节

    return result


class ServerEvent(IntEnum):
    """服务端事件类型枚举"""
    # Connect类事件
    CONNECTION_STARTED = 50
    CONNECTION_FAILED = 51
    CONNECTION_FINISHED = 52

    # Session类事件
    SESSION_STARTED = 150
    SESSION_FINISHED = 152
    SESSION_FAILED = 153

    # TTS类事件
    TTS_SENTENCE_START = 350
    TTS_SENTENCE_END = 351
    TTS_RESPONSE = 352
    TTS_ENDED = 359

    # ASR类事件
    ASR_INFO = 450
    ASR_RESPONSE = 451
    ASR_ENDED = 459

    # Chat类事件
    CHAT_RESPONSE = 550
    CHAT_ENDED = 559
