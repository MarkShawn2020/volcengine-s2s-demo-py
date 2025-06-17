# TouchDesigner Execute DAT 回调函数
# 将此代码放入Execute DAT中

def onFrameStart(frame):
    """每帧开始时调用"""
    # 更新音频可视化
    try:
        # 获取语音接口模块
        interface_dat = op('volc_interface')  # Text DAT名称
        if interface_dat and hasattr(interface_dat.module, 'update_audio_visualization'):
            interface_dat.module.update_audio_visualization()
    except Exception as e:
        print(f"Frame update error: {e}")

def onFrameEnd(frame):
    """每帧结束时调用"""
    pass

def onStart():
    """TouchDesigner启动时调用"""
    print("TouchDesigner语音系统启动")
    
    # 自动启动语音接口
    try:
        interface_dat = op('volc_interface')
        if interface_dat and hasattr(interface_dat.module, 'start_interface'):
            interface_dat.module.start_interface()
            print("语音接口自动启动")
    except Exception as e:
        print(f"启动错误: {e}")

def onExit():
    """TouchDesigner退出时调用"""
    print("TouchDesigner语音系统关闭")
    
    # 清理语音接口
    try:
        interface_dat = op('volc_interface')
        if interface_dat and hasattr(interface_dat.module, 'stop_interface'):
            interface_dat.module.stop_interface()
            print("语音接口已关闭")
    except Exception as e:
        print(f"关闭错误: {e}")

def onProjectPreSave():
    """项目保存前调用"""
    pass

def onProjectPostSave():
    """项目保存后调用"""
    pass