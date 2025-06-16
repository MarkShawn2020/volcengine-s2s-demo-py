import logging

logger = logging.getLogger(__name__)


def select_audio_device(p, prompt, device_type):
    info = p.get_host_api_info_by_index(0);
    numdevices = info.get('deviceCount');
    print(prompt);
    valid_choices = []
    for i in range(numdevices):
        device_info = p.get_device_info_by_host_api_device_index(0, i)
        if (device_type == 'input' and device_info.get('maxInputChannels') > 0) or (
                device_type == 'output' and device_info.get('maxOutputChannels') > 0):
            print(f"  [{i}] - {device_info.get('name')}");
            valid_choices.append(i)
    if not valid_choices: logger.error("未找到任何可用的设备！"); return None
    while True:
        choice_str = input(f"请选择设备编号 (直接回车选择第一个: {valid_choices[0]}): ")
        if not choice_str: return valid_choices[0]
        try:
            choice = int(choice_str)
            if choice in valid_choices:
                return choice
            else:
                print("无效的编号。")
        except ValueError:
            print("请输入一个数字。")
