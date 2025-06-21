from pynput import keyboard

def on_press(key):
    try:
        # 尝试打印字符键
        print(f'字母/数字键被按下: {key.char}')
    except AttributeError:
        # 处理特殊键 (e.g., Shift, Ctrl, Alt)
        print(f'特殊键被按下: {key}')

def on_release(key):
    print(f'键被释放: {key}')
    if key == keyboard.Key.esc:
        # 按下 Esc 键停止监听
        print('监听结束。')
        return False

# 创建一个监听器实例
print("开始监听键盘... 按下 'Esc' 键退出。")
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
