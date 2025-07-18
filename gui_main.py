#!/usr/bin/env python3
"""
GUI主程序入口
"""
import sys
import os
import tkinter as tk
from tkinter import messagebox

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dotenv
dotenv.load_dotenv()

def main():
    """GUI主函数"""
    try:
        from gui.main_window import MainWindow
        app = MainWindow()
        app.run()
    except Exception as e:
        try:
            messagebox.showerror("错误", f"应用启动失败: {str(e)}")
        except:
            print(f"应用启动失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()