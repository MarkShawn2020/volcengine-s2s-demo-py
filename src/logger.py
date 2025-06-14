import logging


def setup_logging(level=logging.INFO):
    """配置日志系统"""
    # Python 3.7兼容性：移除已有的handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )


logger = logging.getLogger('AudioManager')

setup_logging(logging.INFO)

def set_debug_mode(debug=False):
    """设置调试模式"""
    if debug:
        logger.setLevel(logging.DEBUG)
        setup_logging(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        setup_logging(logging.INFO)
