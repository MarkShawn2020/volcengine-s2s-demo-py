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
    
    print(f"📝 日志文件: {log_filename}")
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
    if debug:
        logger.setLevel(logging.DEBUG)
        setup_logging(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        setup_logging(logging.INFO)
