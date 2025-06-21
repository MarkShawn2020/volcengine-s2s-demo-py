#!/usr/bin/env python3
"""
简单的pynput权限测试
"""

def main():
    print("=== pynput权限和功能测试 ===")
    
    try:
        from pynput import keyboard
        import time
        
        print("✅ pynput库导入成功")
        
        # 测试键盘监听权限
        pressed_keys = []
        
        def on_press(key):
            try:
                key_info = ""
                if hasattr(key, 'char') and key.char is not None:
                    key_info = f"字符键: '{key.char}'"
                    if key.char == '0':
                        print("🎯 检测到数字0键按下!")
                else:
                    key_info = f"特殊键: {key}"
                
                print(f"[{len(pressed_keys)+1}] {key_info}")
                pressed_keys.append(key_info)
                
                # 收集5个按键后自动退出
                if len(pressed_keys) >= 5:
                    print("已收集5个按键，测试完成")
                    return False
                    
            except Exception as e:
                print(f"按键处理异常: {e}")
        
        def on_release(key):
            if key == keyboard.Key.esc:
                print("ESC键退出")
                return False
        
        print("\n开始键盘监听测试...")
        print("请按5个不同的键（包括数字0），或按ESC提前退出")
        print("如果没有任何反应，说明权限不足")
        print("-" * 50)
        
        # 启动监听器
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
        
        print("-" * 50)
        print(f"测试结果：收集到 {len(pressed_keys)} 个按键")
        for i, key in enumerate(pressed_keys, 1):
            print(f"  {i}. {key}")
            
        if len(pressed_keys) == 0:
            print("❌ 没有检测到任何按键 - 可能是权限问题")
            print("请检查系统偏好设置 > 安全性与隐私 > 隐私 > 辅助功能")
        else:
            print("✅ 键盘监听正常工作")
            
    except ImportError:
        print("❌ pynput库未安装，请运行: pip install pynput")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()