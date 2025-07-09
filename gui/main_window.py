"""
主窗口类
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import asyncio
import threading
import queue
import sys
import os
import pyaudio
import dotenv

# 确保环境变量被加载
dotenv.load_dotenv()

try:
    from src.adapters.type import AdapterType
    from src.config import VOLCENGINE_APP_ID, VOLCENGINE_ACCESS_TOKEN
    from src.unified_app import UnifiedAudioApp
    from logger import logger
except ImportError as e:
    print(f"导入错误: {e}")
    import sys
    sys.exit(1)

class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("火山引擎语音对话")
        self.root.geometry("800x600")
        
        # 应用状态
        self.app_instance = None
        self.is_running = False
        self.app_thread = None
        
        # 日志队列
        self.log_queue = queue.Queue()
        
        # 音频设备
        self.audio_devices = {"input": [], "output": []}
        self.selected_input_device = None
        self.selected_output_device = None
        
        self.setup_ui()
        self.setup_logging()
        self.scan_audio_devices()
        
    def setup_ui(self):
        """设置UI界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置区域
        config_frame = ttk.LabelFrame(main_frame, text="配置", padding="10")
        config_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), pady=(0, 10))
        
        # 适配器选择
        ttk.Label(config_frame, text="适配器类型:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.adapter_var = tk.StringVar(value="local")
        adapter_combo = ttk.Combobox(config_frame, textvariable=self.adapter_var, width=30)
        adapter_combo['values'] = ("local", "browser", "touchdesigner", "touchdesigner-webrtc", "touchdesigner-webrtc-proper", "text-input")
        adapter_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)
        adapter_combo.bind('<<ComboboxSelected>>', self.on_adapter_change)
        
        # 动态配置区域
        self.dynamic_frame = ttk.Frame(config_frame)
        self.dynamic_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N), pady=(10, 0))
        
        # 通用配置
        ttk.Label(config_frame, text="重连超时(秒):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.reconnect_timeout_var = tk.StringVar(value="300.0")
        ttk.Entry(config_frame, textvariable=self.reconnect_timeout_var, width=32).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # PCM选项
        self.use_pcm_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(config_frame, text="使用PCM格式TTS", variable=self.use_pcm_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # 音频设备选择
        audio_frame = ttk.LabelFrame(config_frame, text="音频设备", padding="5")
        audio_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N), pady=(10, 0))
        
        # 输入设备
        ttk.Label(audio_frame, text="麦克风:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.input_device_var = tk.StringVar()
        self.input_device_combo = ttk.Combobox(audio_frame, textvariable=self.input_device_var, width=40, state="readonly")
        self.input_device_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # 输出设备
        ttk.Label(audio_frame, text="扬声器:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.output_device_var = tk.StringVar()
        self.output_device_combo = ttk.Combobox(audio_frame, textvariable=self.output_device_var, width=40, state="readonly")
        self.output_device_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # 刷新设备按钮
        ttk.Button(audio_frame, text="刷新设备", command=self.scan_audio_devices).grid(row=2, column=0, columnspan=2, pady=5)
        
        audio_frame.columnconfigure(1, weight=1)
        
        # 控制按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.start_button = ttk.Button(button_frame, text="启动", command=self.start_app)
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_button = ttk.Button(button_frame, text="停止", command=self.stop_app, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)
        
        # 状态显示
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(button_frame, textvariable=self.status_var)
        status_label.pack(side=tk.RIGHT)
        
        # 日志显示
        log_frame = ttk.LabelFrame(main_frame, text="日志", padding="5")
        log_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 0))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, width=80)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        config_frame.columnconfigure(1, weight=1)
        
        # 初始化动态配置
        self.on_adapter_change(None)
        
    def setup_logging(self):
        """设置日志处理"""
        # 使用更长的间隔减少主线程负载
        self.root.after(200, self.process_log_queue)
        
    def process_log_queue(self):
        """处理日志队列"""
        try:
            # 批量处理日志，减少UI更新频率
            messages = []
            for _ in range(10):  # 最多处理10条消息
                try:
                    record = self.log_queue.get_nowait()
                    messages.append(record)
                except queue.Empty:
                    break
            
            if messages:
                self.log_text.insert(tk.END, "\n".join(messages) + "\n")
                self.log_text.see(tk.END)
                
        except Exception as e:
            pass
        finally:
            self.root.after(200, self.process_log_queue)
            
    def log_message(self, message):
        """添加日志消息"""
        self.log_queue.put(message)
        
    def scan_audio_devices(self):
        """扫描音频设备"""
        try:
            print("开始扫描音频设备...")
            p = pyaudio.PyAudio()
            
            # 清空设备列表
            self.audio_devices = {"input": [], "output": []}
            
            # 扫描设备
            info = p.get_host_api_info_by_index(0)
            numdevices = info.get('deviceCount')
            print(f"发现 {numdevices} 个音频设备")
            
            input_devices = []
            output_devices = []
            
            for i in range(numdevices):
                device_info = p.get_device_info_by_host_api_device_index(0, i)
                device_name = device_info.get('name')
                
                if device_info.get('maxInputChannels') > 0:
                    input_devices.append((i, device_name))
                    self.audio_devices["input"].append({"index": i, "name": device_name})
                
                if device_info.get('maxOutputChannels') > 0:
                    output_devices.append((i, device_name))
                    self.audio_devices["output"].append({"index": i, "name": device_name})
            
            # 更新下拉框
            input_names = [f"[{idx}] {name}" for idx, name in input_devices]
            output_names = [f"[{idx}] {name}" for idx, name in output_devices]
            
            self.input_device_combo['values'] = input_names
            self.output_device_combo['values'] = output_names
            
            # 选择第一个设备作为默认
            if input_names:
                self.input_device_combo.set(input_names[0])
                self.selected_input_device = input_devices[0][0]
            
            if output_names:
                self.output_device_combo.set(output_names[0])
                self.selected_output_device = output_devices[0][0]
                
            # 绑定选择事件
            self.input_device_combo.bind('<<ComboboxSelected>>', self.on_input_device_change)
            self.output_device_combo.bind('<<ComboboxSelected>>', self.on_output_device_change)
            
            p.terminate()
            print(f"扫描完成：找到 {len(input_devices)} 个输入设备，{len(output_devices)} 个输出设备")
            self.log_message(f"扫描完成：找到 {len(input_devices)} 个输入设备，{len(output_devices)} 个输出设备")
            
        except Exception as e:
            print(f"扫描音频设备失败: {str(e)}")
            self.log_message(f"扫描音频设备失败: {str(e)}")
            
    def on_input_device_change(self, event):
        """输入设备改变"""
        selection = self.input_device_var.get()
        if selection:
            # 从 "[0] Device Name" 格式中提取设备索引
            device_index = int(selection.split(']')[0][1:])
            self.selected_input_device = device_index
            self.log_message(f"已选择输入设备: {selection}")
            
    def on_output_device_change(self, event):
        """输出设备改变"""
        selection = self.output_device_var.get()
        if selection:
            # 从 "[0] Device Name" 格式中提取设备索引
            device_index = int(selection.split(']')[0][1:])
            self.selected_output_device = device_index
            self.log_message(f"已选择输出设备: {selection}")
        
    def on_adapter_change(self, event):
        """适配器改变时更新动态配置"""
        # 清空动态配置区域
        for widget in self.dynamic_frame.winfo_children():
            widget.destroy()
            
        adapter = self.adapter_var.get()
        
        if adapter == "browser":
            ttk.Label(self.dynamic_frame, text="代理URL:").grid(row=0, column=0, sticky=tk.W, pady=2)
            self.proxy_url_var = tk.StringVar(value="ws://localhost:8765")
            ttk.Entry(self.dynamic_frame, textvariable=self.proxy_url_var, width=40).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)
            
        elif adapter == "touchdesigner":
            ttk.Label(self.dynamic_frame, text="TD IP:").grid(row=0, column=0, sticky=tk.W, pady=2)
            self.td_ip_var = tk.StringVar(value="localhost")
            ttk.Entry(self.dynamic_frame, textvariable=self.td_ip_var, width=40).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)
            
            ttk.Label(self.dynamic_frame, text="TD Port:").grid(row=1, column=0, sticky=tk.W, pady=2)
            self.td_port_var = tk.StringVar(value="7000")
            ttk.Entry(self.dynamic_frame, textvariable=self.td_port_var, width=40).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2)
            
        elif adapter in ["touchdesigner-webrtc", "touchdesigner-webrtc-proper"]:
            ttk.Label(self.dynamic_frame, text="信令端口:").grid(row=0, column=0, sticky=tk.W, pady=2)
            self.signaling_port_var = tk.StringVar(value="8080")
            ttk.Entry(self.dynamic_frame, textvariable=self.signaling_port_var, width=40).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)
            
            if adapter == "touchdesigner-webrtc-proper":
                ttk.Label(self.dynamic_frame, text="WebRTC端口:").grid(row=1, column=0, sticky=tk.W, pady=2)
                self.webrtc_port_var = tk.StringVar(value="8081")
                ttk.Entry(self.dynamic_frame, textvariable=self.webrtc_port_var, width=40).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2)
                
        self.dynamic_frame.columnconfigure(1, weight=1)
        
    def get_config(self):
        """获取当前配置"""
        adapter = self.adapter_var.get()
        
        base_config = {
            "app_id": VOLCENGINE_APP_ID,
            "access_token": VOLCENGINE_ACCESS_TOKEN,
            "reconnect_timeout": float(self.reconnect_timeout_var.get())
        }
        
        if adapter == "local":
            adapter_type = AdapterType.LOCAL
            config = base_config
        elif adapter == "browser":
            adapter_type = AdapterType.BROWSER
            config = {**base_config, "proxy_url": self.proxy_url_var.get()}
        elif adapter == "touchdesigner":
            adapter_type = AdapterType.TOUCH_DESIGNER
            config = {**base_config, "td_ip": self.td_ip_var.get(), "td_port": int(self.td_port_var.get())}
        elif adapter == "touchdesigner-webrtc":
            adapter_type = AdapterType.TOUCH_DESIGNER_WEBRTC
            config = {**base_config, "signaling_port": int(self.signaling_port_var.get())}
        elif adapter == "touchdesigner-webrtc-proper":
            adapter_type = AdapterType.TOUCH_DESIGNER_WEBRTC_PROPER
            config = {**base_config, "signaling_port": int(self.signaling_port_var.get()), "webrtc_port": int(self.webrtc_port_var.get())}
        elif adapter == "text-input":
            adapter_type = AdapterType.TEXT_INPUT
            config = base_config
        else:
            raise ValueError(f"不支持的适配器类型: {adapter}")
            
        return adapter_type, config
        
    def start_app(self):
        """启动应用"""
        if self.is_running:
            return
            
        try:
            # 检查设备选择
            if self.selected_input_device is None or self.selected_output_device is None:
                messagebox.showerror("错误", "请先选择音频设备")
                return
                
            adapter_type, config = self.get_config()
            use_pcm = self.use_pcm_var.get()
            
            # 调试信息
            self.log_message(f"配置信息: {config}")
            self.log_message(f"APP_ID: {config.get('app_id', 'NOT_SET')}")
            self.log_message(f"ACCESS_TOKEN: {config.get('access_token', 'NOT_SET')[:10]}...")
            
            # 直接使用 UnifiedAudioApp，支持预选择设备
            self.app_instance = UnifiedAudioApp(
                adapter_type, 
                config, 
                use_tts_pcm=use_pcm,
                input_device_index=self.selected_input_device,
                output_device_index=self.selected_output_device
            )
            
            # 在新线程中运行应用（使用 UnifiedAudioApp 的模式）
            self.app_thread = threading.Thread(target=self.run_app_async, daemon=True)
            self.app_thread.start()
            
            self.is_running = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.status_var.set("运行中...")
            
            self.log_message(f"应用启动成功 - 适配器: {self.adapter_var.get()}")
            
        except Exception as e:
            messagebox.showerror("错误", f"启动失败: {str(e)}")
            self.log_message(f"启动失败: {str(e)}")
            
    def run_app_async(self):
        """异步运行应用"""
        try:
            # 直接使用 UnifiedAudioApp 的 run 方法
            asyncio.run(self.app_instance.run())
        except Exception as e:
            self.log_message(f"应用运行错误: {str(e)}")
        finally:
            self.root.after(0, self.on_app_stopped)
            
    def stop_app(self):
        """停止应用"""
        if not self.is_running:
            return
            
        self.is_running = False
        self.status_var.set("停止中...")
        self.log_message("正在停止应用...")
        
        # 停止 UnifiedAudioApp
        if self.app_instance:
            if hasattr(self.app_instance, 'stop_event'):
                self.app_instance.stop_event.set()
        
        # 等待线程结束
        if hasattr(self, 'app_thread') and self.app_thread.is_alive():
            self.app_thread.join(timeout=5.0)
            
    def on_app_stopped(self):
        """应用停止时的回调"""
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("已停止")
        self.log_message("应用已停止")
        
    def run(self):
        """运行GUI"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
        
    def on_closing(self):
        """关闭窗口时的处理"""
        if self.is_running:
            self.stop_app()
        self.root.destroy()