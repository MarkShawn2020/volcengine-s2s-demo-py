#!/usr/bin/env python3
"""
简单的键盘监听测试脚本
用于测试不同键盘库的监听效果
"""

import time
import threading
import sys

def test_pynput():
    """测试 pynput 库"""
    print("=== 测试 pynput 库 ===")
    try:
        from pynput import keyboard
        import sys
        import tty
        import termios
        import threading
        
        # 设置终端为原始模式，禁用回显
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
        
        def on_press(key):
            try:
                print(f"\r\n>>> pynput on_press 被调用! key={key}, type={type(key)}")
                if hasattr(key, 'char') and key.char:
                    print(f"\r\npynput - 字符键: '{key.char}' (ASCII: {ord(key.char)})")
                    if key.char == '0':
                        print("\r\n🎯 pynput检测到主键盘0键!")
                else:
                    print(f"\r\npynput - 特殊键: {key}")
                    if str(key) == 'Key.kp_0':
                        print("\r\n🎯 pynput检测到数字键盘0键!")
            except Exception as e:
                print(f"\r\npynput按键处理异常: {e}")
        
        def on_release(key):
            if key == keyboard.Key.esc:
                print("\r\n按下ESC键，退出pynput测试")
                return False
        
        print("pynput监听已启动（原始模式），按任意键测试（ESC退出）...")
        
        try:
            with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
                listener.join()
        finally:
            # 恢复终端设置
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            
    except ImportError:
        print("❌ pynput库未安装")
    except Exception as e:
        print(f"❌ pynput测试失败: {e}")
        # 确保恢复终端设置
        try:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        except:
            pass

def test_keyboard():
    """测试 keyboard 库"""
    print("\n=== 测试 keyboard 库 ===")
    try:
        import keyboard
        
        def on_key_event(event):
            print(f"keyboard - 事件: name='{event.name}', event_type='{event.event_type}', scan_code={getattr(event, 'scan_code', 'N/A')}")
            
            if event.event_type == keyboard.KEY_DOWN:
                if event.name == '0':
                    print("🎯 keyboard检测到0键按下!")
                elif event.name == 'esc':
                    print("按下ESC键，退出keyboard测试")
                    return False
        
        print("keyboard监听已启动，按任意键测试（ESC退出）...")
        keyboard.hook(on_key_event)
        
        # 等待ESC键或手动中断
        try:
            keyboard.wait('esc')
        except KeyboardInterrupt:
            pass
        finally:
            keyboard.unhook_all()
            
    except ImportError:
        print("❌ keyboard库未安装")
    except Exception as e:
        print(f"❌ keyboard测试失败: {e}")

def test_keyboard_hotkey():
    """测试 keyboard 库的热键功能"""
    print("\n=== 测试 keyboard 热键功能 ===")
    try:
        import keyboard
        
        def on_zero_pressed():
            print("🎯 keyboard热键检测到0键按下!")
        
        def on_esc_pressed():
            print("按下ESC键，退出keyboard热键测试")
            return True
        
        print("keyboard热键监听已启动，按0键测试，按ESC退出...")
        
        # 设置热键
        keyboard.add_hotkey('0', on_zero_pressed)
        keyboard.add_hotkey('esc', on_esc_pressed)
        
        # 等待ESC键
        keyboard.wait('esc')
        keyboard.clear_all_hotkeys()
            
    except ImportError:
        print("❌ keyboard库未安装")
    except Exception as e:
        print(f"❌ keyboard热键测试失败: {e}")

def main():
    print("键盘监听测试脚本")
    print("=" * 50)
    print("请按数字0键测试监听效果")
    print("按ESC键退出当前测试")
    print("按Ctrl+C可以强制退出所有测试")
    print("=" * 50)
    
    try:
        # 测试 pynput
        test_pynput()
        
        # 测试 keyboard
        test_keyboard()
        
        # 测试 keyboard 热键
        test_keyboard_hotkey()
        
    except KeyboardInterrupt:
        print("\n用户中断测试")
    
    print("\n测试完成!")

if __name__ == "__main__":
    main()