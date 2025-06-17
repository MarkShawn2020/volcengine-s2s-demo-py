# TouchDesigner Button 回调函数
# 将此代码放入Button的回调参数中，或者单独的Text DAT中

def onOffToOn(comp):
    """按钮按下时调用"""
    try:
        # 获取语音接口
        interface_dat = op('volc_interface')
        if not interface_dat:
            print("找不到语音接口模块")
            return
        
        # 根据按钮名称执行不同操作
        if comp.name == 'btn_connect':
            # 连接按钮
            if hasattr(interface_dat.module, 'start_interface'):
                interface_dat.module.start_interface()
                print("正在连接...")
            
        elif comp.name == 'btn_disconnect':
            # 断开按钮
            if hasattr(interface_dat.module, 'stop_interface'):
                interface_dat.module.stop_interface()
                print("已断开连接")
            
        elif comp.name == 'btn_hello':
            # 问候按钮
            if hasattr(interface_dat.module, 'send_hello'):
                interface_dat.module.send_hello()
            
        elif comp.name == 'btn_question':
            # 问题按钮
            if hasattr(interface_dat.module, 'send_question'):
                interface_dat.module.send_question()
                
        elif comp.name == 'btn_custom_text':
            # 自定义文本按钮
            text_field = op('text_input')  # Text field组件名称
            if text_field and hasattr(interface_dat.module, 'send_text'):
                text_content = text_field.par.text.eval()
                if text_content:
                    interface_dat.module.send_text(text_content)
                    print(f"发送自定义文本: {text_content}")
                
        elif comp.name == 'btn_start_audio':
            # 开始音频传输
            enable_audio_transmission(True)
            
        elif comp.name == 'btn_stop_audio':
            # 停止音频传输
            enable_audio_transmission(False)
            
        elif comp.name == 'btn_test_mic':
            # 测试麦克风
            test_microphone()
            
    except Exception as e:
        print(f"按钮回调错误: {e}")

def onOnToOff(comp):
    """按钮释放时调用"""
    pass

def enable_audio_transmission(enable):
    """启用/禁用音频传输"""
    try:
        # 获取音频输入CHOP
        audio_in = op('audioin1')  # Audio Device In CHOP名称
        if audio_in:
            audio_in.par.active = enable
            print(f"音频传输: {'启用' if enable else '禁用'}")
            
        # 更新状态显示
        status_text = op('status_text')
        if status_text:
            status_text.par.text = f"音频传输: {'ON' if enable else 'OFF'}"
            
    except Exception as e:
        print(f"音频传输控制错误: {e}")

def test_microphone():
    """测试麦克风"""
    try:
        audio_in = op('audioin1')
        if audio_in and audio_in.numSamples > 0:
            # 检查是否有音频信号
            level = abs(audio_in[0].vals[-1]) if audio_in.numChans > 0 else 0
            print(f"麦克风测试 - 当前电平: {level:.3f}")
            
            # 更新测试结果显示
            test_result = op('mic_test_result')
            if test_result:
                if level > 0.001:
                    test_result.par.text = f"麦克风正常 (电平: {level:.3f})"
                else:
                    test_result.par.text = "麦克风无信号"
        else:
            print("麦克风未检测到音频设备")
            
    except Exception as e:
        print(f"麦克风测试错误: {e}")

# 音频传输函数（在Timer CHOP的回调中使用）
def transmit_audio():
    """传输音频数据"""
    try:
        # 获取音频输入
        audio_in = op('audioin1')
        interface_dat = op('volc_interface')
        
        if audio_in and interface_dat and audio_in.numSamples > 0:
            # 检查是否启用传输
            if hasattr(interface_dat.module, 'send_audio_from_chop'):
                interface_dat.module.send_audio_from_chop('audioin1')
                
    except Exception as e:
        print(f"音频传输错误: {e}")

# 状态更新函数
def update_status():
    """更新连接状态显示"""
    try:
        interface_dat = op('volc_interface')
        status_text = op('connection_status')
        
        if interface_dat and status_text:
            if hasattr(interface_dat.module, 'is_connected'):
                connected = interface_dat.module.is_connected()
                status_text.par.text = f"连接状态: {'已连接' if connected else '未连接'}"
                
                # 更新连接指示灯
                status_light = op('status_light')
                if status_light:
                    status_light.par.r = 0 if connected else 1
                    status_light.par.g = 1 if connected else 0
                    status_light.par.b = 0
                    
    except Exception as e:
        print(f"状态更新错误: {e}")

# 快捷消息函数
def send_preset_message(message_type):
    """发送预设消息"""
    messages = {
        'weather': '今天天气怎么样？',
        'time': '现在几点了？',
        'joke': '讲个笑话吧',
        'story': '给我讲个故事',
        'music': '推荐一首歌',
        'news': '有什么新闻吗？'
    }
    
    try:
        interface_dat = op('volc_interface')
        if interface_dat and hasattr(interface_dat.module, 'send_text'):
            message = messages.get(message_type, '你好')
            interface_dat.module.send_text(message)
            print(f"发送预设消息: {message}")
    except Exception as e:
        print(f"发送预设消息错误: {e}")

# 音量控制
def set_volume(volume_level):
    """设置音量（0.0 - 1.0）"""
    try:
        audio_out = op('audioout1')  # Audio Device Out CHOP名称
        if audio_out:
            # 通过Level CHOP或直接设置音量
            level_chop = op('audio_level_control')
            if level_chop:
                level_chop.par.gain = volume_level
                print(f"音量设置为: {volume_level:.2f}")
    except Exception as e:
        print(f"音量控制错误: {e}")

print("TouchDesigner按钮回调模块加载完成")