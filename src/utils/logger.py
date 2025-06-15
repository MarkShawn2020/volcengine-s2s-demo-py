import logging
import os
from datetime import datetime


def setup_logging(level=logging.INFO):
    """配置日志系统"""
    # Python 3.7兼容性：移除已有的handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # 创建logs目录
    os.makedirs('logs', exist_ok=True)

    # 生成基于时间戳的日志文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f'logs/webrtc_dialog_{timestamp}.log'
    latest_log_link = 'logs/latest.log'

    # 配置格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)  # 控制台使用环境变量指定的级别

    # 文件处理器 - 始终记录DEBUG级别
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)  # 文件始终记录DEBUG级别

    # 配置根logger - 设置为DEBUG以确保文件能收到所有消息
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # 屏蔽第三方库的DEBUG日志以减少噪音
    logging.getLogger('websockets').setLevel(logging.WARNING)
    logging.getLogger('aiortc').setLevel(logging.WARNING)
    logging.getLogger('aioice').setLevel(logging.WARNING)
    logging.getLogger('av').setLevel(logging.WARNING)

    # 创建或更新符号链接指向最新的日志文件
    try:
        # 如果符号链接已存在，先删除
        if os.path.islink(latest_log_link):
            os.unlink(latest_log_link)
        elif os.path.exists(latest_log_link):
            os.remove(latest_log_link)

        # 创建相对路径的符号链接
        # 使用相对路径避免绝对路径问题
        relative_log_path = os.path.basename(log_filename)
        os.symlink(relative_log_path, latest_log_link)

        print(f"📝 日志文件: {log_filename}")
        print(f"🔗 最新日志链接: {latest_log_link}")
    except OSError as e:
        # 在某些系统上可能无法创建符号链接（如Windows），静默处理
        print(f"📝 日志文件: {log_filename}")
        print(f"⚠️ 无法创建符号链接: {e}")

    return log_filename


logger = logging.getLogger('AudioManager')

# 从环境变量读取日志级别
log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
log_level_map = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
    }
log_level = log_level_map.get(log_level_str, logging.INFO)

# 设置日志并获取文件名
current_log_file = setup_logging(log_level)


def set_debug_mode(debug=False):
    """设置调试模式"""
    global current_log_file
    if debug:
        logger.setLevel(logging.DEBUG)
        current_log_file = setup_logging(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        current_log_file = setup_logging(logging.INFO)
