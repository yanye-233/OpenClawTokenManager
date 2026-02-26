#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaw Token 查看器 - 桌面小工具 v3.3
记忆分层管理：长期(baizhi52) + 中期(baizhi20) + 短期(最近N条)
"""

import json
import os
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
from pathlib import Path
from datetime import datetime
import time
import requests
import base64
import threading
import queue

# 配置路径（可修改）
OPENCLAW_DIR = Path.home() / ".openclaw"
SESSIONS_DIR = OPENCLAW_DIR / "agents" / "main" / "sessions"
SESSIONS_JSON = SESSIONS_DIR / "sessions.json"
BACKUP_DIR = SESSIONS_DIR / "backups"

# 配置文件路径（可自定义）
CONFIG_FILENAME = "token_viewer_config.json"  # 修改这里可更改配置文件名
CONFIG_PATH = OPENCLAW_DIR / CONFIG_FILENAME

# 角色颜色映射
ROLE_COLORS = {
    'user': '#4CAF50',
    'assistant': '#2196F3',
    'toolResult': '#FF9800',
    'tool_call': '#9C27B0',
    'system': '#F44336',
}

# 记忆 ID 常量
COMPACT_ID = "baizhi01"     # compact标记（前文截止符）
CHARACTER_ID = "baizhi00"   # 人设/初始化记忆（不变）
LONG_TERM_ID = "baizhi52"   # 长期记忆
MID_TERM_ID = "baizhi20"    # 中期记忆
MODE_MESSAGE_ID = "baizhi21"  # 模式消息（长期/中期/短期/吐槽）
SHORT_TERM_PREFIX = "白芷"   # 短期记忆前缀
SHORT_TERM_COUNT = 19       # 白芷01 到 白芷19

# API 配置
API_TEMPLATES = {
    'moonshot': {
        'url': 'https://api.moonshot.cn/v1/chat/completions',
        'models': ['kimi-k2.5', 'kimi-k2']
    },
    'kimicode': {
        # Kimi Code 的正确 API 地址
        # 参考: game_assistant/send/llm_clients/ask_kimi.py
        'url': 'https://api.kimi.com/coding/v1/chat/completions',
        'models': ['kimi-for-coding', 'kimi-k2.5']  # 支持两种模型
    }
}

def encode_key(key):
    """简单编码 API key（非加密，只是防止明文）"""
    return base64.b64encode(key.encode()).decode()

def decode_key(encoded_key):
    """解码 API key"""
    try:
        return base64.b64decode(encoded_key.encode()).decode()
    except:
        return ""

# 默认配置常量 - 修改这里即可改变所有默认值
DEFAULT_CONFIG = {
    # API设置
    'api_provider': 'moonshot',
    'model': 'kimi-k2.5',
    'api_key_encoded': '',
    
    # 压缩设置
    'compress_mode': '长期模式',  # 默认模式：长期/中期/短期/吐槽
    'auto_compress_enabled': False,  # 默认关闭自动压缩
    'auto_compress_interval': 300,  # 自动压缩间隔（秒）
    'silent_mode': False,  # 静默模式（关闭弹窗）
    
    # 文件监控设置
    'file_monitor_enabled': False,
    'file_monitor_path': '',  # 默认监控文件路径
    'file_monitor_interval': 1.0,  # 监控频率（Hz）
    
    # 阈值设置
    'long_term_threshold': 5000,   # 长期记忆触发阈值（默认5000）
    'mid_term_threshold': 2000,    # 中期记忆触发阈值（默认2000）
    'short_term_keep': 5,          # 短期记忆保留条数
    'min_message_count': 10,       # 自动压缩最小对话条数
    'min_token_count': 20000,      # 自动压缩最小token数
    
    # UI设置
    'auto_refresh_enabled': True,  # 默认开启自动刷新
    'auto_refresh_interval': 1,    # 自动刷新间隔（秒）
}

class AICompressionConfig:
    """AI 压缩配置 - 从DEFAULT_CONFIG加载默认值"""
    def __init__(self):
        # 从默认配置加载
        self.enabled = False
        self.api_provider = DEFAULT_CONFIG['api_provider']
        self.api_url = API_TEMPLATES[DEFAULT_CONFIG['api_provider']]['url']
        self.api_key_encoded = DEFAULT_CONFIG['api_key_encoded']
        self.model = DEFAULT_CONFIG['model']
        self.compress_mode = DEFAULT_CONFIG['compress_mode']
        self.auto_compress_enabled = DEFAULT_CONFIG['auto_compress_enabled']
        self.auto_compress_interval = DEFAULT_CONFIG['auto_compress_interval']
        self.silent_mode = DEFAULT_CONFIG['silent_mode']
        # 文件监控配置
        self.file_monitor_enabled = DEFAULT_CONFIG['file_monitor_enabled']
        self.file_monitor_path = DEFAULT_CONFIG['file_monitor_path']
        self.file_monitor_interval = DEFAULT_CONFIG['file_monitor_interval']
        # 阈值配置
        self.long_term_threshold = DEFAULT_CONFIG['long_term_threshold']  # 5000
        self.mid_term_threshold = DEFAULT_CONFIG['mid_term_threshold']    # 2000
        self.short_term_keep = DEFAULT_CONFIG['short_term_keep']
        self.min_message_count = DEFAULT_CONFIG['min_message_count']
        self.min_token_count = DEFAULT_CONFIG['min_token_count']
        # UI设置
        self.auto_refresh_enabled = DEFAULT_CONFIG['auto_refresh_enabled']
        self.auto_refresh_interval = DEFAULT_CONFIG['auto_refresh_interval']
        # 压缩提示词
        self.compression_prompt = """请将以下对话历史压缩为关键信息摘要。要求：
1. 低失真，保留重要决策、代码变更和关键上下文
2. 纯文本输出，不要Markdown格式
3. 少用符号，避免特殊字符
4. 不要分段，用逗号或分号连接
5. 字数越多越好，尽量详细，控制在8000字以内
6. 保留完整的技术细节和决策依据

内容："""
        # 吐槽模式提示词
        self.tsukkomi_prompt = """请对以下对话历史进行吐槽，指出其中的问题、矛盾或有趣的地方。用轻松幽默的语气，直接输出吐槽内容，不要加标题或前缀：

内容："""
        
    def to_dict(self):
        return {
            'enabled': self.enabled,
            'api_provider': self.api_provider,
            'api_url': self.api_url,
            'api_key_encoded': self.api_key_encoded,
            'model': self.model,
            'compress_mode': self.compress_mode,
            'auto_compress_enabled': self.auto_compress_enabled,
            'auto_compress_interval': self.auto_compress_interval,
            'silent_mode': self.silent_mode,
            'file_monitor_enabled': self.file_monitor_enabled,
            'file_monitor_path': self.file_monitor_path,
            'file_monitor_interval': self.file_monitor_interval,
            'long_term_threshold': self.long_term_threshold,
            'mid_term_threshold': self.mid_term_threshold,
            'short_term_keep': self.short_term_keep,
            'min_message_count': self.min_message_count,
            'min_token_count': self.min_token_count,
            'compression_prompt': self.compression_prompt,
            'tsukkomi_prompt': self.tsukkomi_prompt,
            'auto_refresh_enabled': self.auto_refresh_enabled,
            'auto_refresh_interval': self.auto_refresh_interval
        }
        
    def from_dict(self, d):
        self.enabled = d.get('enabled', False)
        self.api_provider = d.get('api_provider', 'moonshot')
        self.api_url = d.get('api_url', API_TEMPLATES['moonshot']['url'])
        self.api_key_encoded = d.get('api_key_encoded', "")
        self.model = d.get('model', 'kimi-k2.5')
        self.compress_mode = d.get('compress_mode', '长期模式')
        self.auto_compress_enabled = d.get('auto_compress_enabled', False)
        self.auto_compress_interval = d.get('auto_compress_interval', 300)
        self.silent_mode = d.get('silent_mode', False)
        self.file_monitor_enabled = d.get('file_monitor_enabled', False)
        self.file_monitor_path = d.get('file_monitor_path', "")
        self.file_monitor_interval = d.get('file_monitor_interval', 1.0)
        self.long_term_threshold = d.get('long_term_threshold', DEFAULT_CONFIG['long_term_threshold'])
        self.mid_term_threshold = d.get('mid_term_threshold', DEFAULT_CONFIG['mid_term_threshold'])
        self.short_term_keep = d.get('short_term_keep', DEFAULT_CONFIG['short_term_keep'])
        self.min_message_count = d.get('min_message_count', DEFAULT_CONFIG['min_message_count'])
        self.min_token_count = d.get('min_token_count', DEFAULT_CONFIG['min_token_count'])
        self.compression_prompt = d.get('compression_prompt', self.compression_prompt)
        self.auto_refresh_enabled = d.get('auto_refresh_enabled', DEFAULT_CONFIG['auto_refresh_enabled'])
        self.auto_refresh_interval = d.get('auto_refresh_interval', DEFAULT_CONFIG['auto_refresh_interval'])
        self.tsukkomi_prompt = d.get('tsukkomi_prompt', self.tsukkomi_prompt)
        
    def get_api_key(self):
        """获取解码后的 API key"""
        return decode_key(self.api_key_encoded)
        
    def set_api_key(self, key):
        """设置并编码 API key"""
        self.api_key_encoded = encode_key(key)

class TokenViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OpenClaw Token 查看器 v3.3")
        self.root.geometry("1000x700")
        self.root.minsize(800, 500)
        
        self.history = []
        self.all_messages = []
        self.current_session_id = None
        self.current_jsonl_path = None
        self.all_lines = []
        
        # 先初始化配置
        self.compression_config = AICompressionConfig()
        self.load_compression_config()
        
        # 自动刷新设置从配置加载
        self.auto_refresh = self.compression_config.auto_refresh_enabled
        self.refresh_interval = self.compression_config.auto_refresh_interval
        
        # 短期记忆 ID 循环计数器
        self.short_term_counter = 1
        
        # 文件监控相关
        self.file_monitor_timer = None
        self.file_monitor_last_lines = []  # 上次读取的行列表（按顺序存储，用于增量导入）
        
        # UI自动刷新定时器
        self.ui_refresh_timer = None
        self.ui_refresh_interval = 1000  # 默认1秒刷新一次
        self.is_auto_refresh = self.compression_config.auto_refresh_enabled  # 从配置加载
        
        # 自动压缩状态提示（用于状态栏显示）
        self.auto_compress_status = ""
        
        BACKUP_DIR.mkdir(exist_ok=True)
        
        self.setup_ui()
        self.load_sessions()
        self.root.after(500, self.auto_load_on_start)
        
        # Token计算相关
        self.last_compression_time = 0  # 上次压缩时间戳
        self.estimated_tokens = 0       # 拟合Token数
        self.official_tokens = 0        # 官方Token数（来自sessions.json）
        self.use_official_tokens = False  # 是否使用官方Token（压缩后30秒内用拟合）
        
    def load_compression_config(self):
        """加载压缩配置"""
        config_path = CONFIG_PATH
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.compression_config.from_dict(data)
            except:
                pass
                
    def save_compression_config(self):
        """保存所有配置到文件"""
        config_path = CONFIG_PATH
        try:
            # 保存API设置
            self.compression_config.api_provider = self.api_provider_var.get()
            self.compression_config.model = self.model_combo.get()
            api_key = self.api_key_entry.get()
            if api_key:
                self.compression_config.set_api_key(api_key)
            
            # 保存压缩设置
            self.compression_config.compress_mode = self.compress_mode_var.get()
            self.compression_config.auto_compress_enabled = self.auto_compress_var.get()
            try:
                self.compression_config.auto_compress_interval = int(self.auto_compress_interval_spin.get())
            except:
                pass
            self.compression_config.silent_mode = self.silent_mode_var.get()
            
            # 保存文件监控配置
            self.compression_config.file_monitor_path = self.file_monitor_path_var.get()
            try:
                self.compression_config.file_monitor_interval = float(self.file_monitor_freq_spin.get())
            except:
                pass
            
            # 保存自动刷新设置
            self.compression_config.auto_refresh_enabled = self.is_auto_refresh
            self.compression_config.auto_refresh_interval = self.refresh_interval
            if api_key:
                self.compression_config.set_api_key(api_key)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.compression_config.to_dict(), f, ensure_ascii=False, indent=2)
            self.status_var.set("配置已保存")
        except Exception as e:
            print(f"保存配置失败: {e}")
            self.status_var.set(f"保存配置失败: {e}")
            
    def setup_ui(self):
        """设置UI界面"""
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        # 内容区（第4行）可扩展，统计栏（第3行）固定高度
        main_frame.rowconfigure(4, weight=1)
        
        # 控制栏
        control_frame = ttk.LabelFrame(main_frame, text="控制", padding="3")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=3)
        
        ttk.Label(control_frame, text="会话:").pack(side=tk.LEFT, padx=3)
        self.session_combo = ttk.Combobox(control_frame, width=35, state="readonly")
        self.session_combo.pack(side=tk.LEFT, padx=3)
        self.session_combo.bind("<<ComboboxSelected>>", self.on_session_selected)
        
        # 刷新按钮（支持长按自动刷新，文本根据配置设置）
        refresh_btn_text = "自动刷新" if self.compression_config.auto_refresh_enabled else "刷新"
        self.refresh_btn = tk.Button(control_frame, text=refresh_btn_text, width=8)
        self.refresh_btn.pack(side=tk.LEFT, padx=2)
        self.refresh_btn.bind('<ButtonPress-1>', self.on_refresh_press)
        self.refresh_btn.bind('<ButtonRelease-1>', self.on_refresh_release)
        
        # 长按进度条
        self.long_press_progress = ttk.Progressbar(control_frame, length=60, mode='determinate', maximum=100)
        self.long_press_progress.pack(side=tk.LEFT, padx=2)
        self.long_press_progress['value'] = 0
        
        # 阈值设置按钮
        ttk.Button(control_frame, text="阈值设置", width=8, command=self.show_threshold_settings).pack(side=tk.LEFT, padx=2)
        
        # 静默模式（关闭弹窗）
        self.silent_mode_var = tk.BooleanVar(value=self.compression_config.silent_mode)
        ttk.Checkbutton(control_frame, text="静默", variable=self.silent_mode_var,
                       command=self.toggle_silent_mode).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(control_frame, text="通讯测试", width=8, command=self.test_api).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text="保存配置", width=8, command=self.save_compression_config).pack(side=tk.LEFT, padx=2)
        
        # Sessions.json 压缩按钮（带恢复功能）
        self.sessions_compress_btn = tk.Button(control_frame, text="压缩Sessions", width=12, bg='#FFE0E0', 
                                               command=self.compress_sessions_json)
        self.sessions_compress_btn.pack(side=tk.RIGHT, padx=5)
        
        # 长按定时器
        self.long_press_timer = None
        self.long_press_progress_val = 0
        self.is_auto_refresh = self.compression_config.auto_refresh_enabled  # 从配置加载
        
        # AI 压缩控制面板（默认启用，不再显示启用复选框）
        self.ai_frame = ttk.LabelFrame(main_frame, text="AI 记忆压缩", padding="3")
        self.ai_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=3)
        
        # API 提供商
        ttk.Label(self.ai_frame, text="API:").pack(side=tk.LEFT, padx=3)
        self.api_provider_var = tk.StringVar(value=self.compression_config.api_provider)
        self.api_provider_combo = ttk.Combobox(self.ai_frame, textvariable=self.api_provider_var,
                                               values=['moonshot', 'kimicode'], width=10, state="readonly")
        self.api_provider_combo.pack(side=tk.LEFT, padx=3)
        self.api_provider_combo.bind("<<ComboboxSelected>>", self.on_api_provider_changed)
        
        # API Key
        ttk.Label(self.ai_frame, text="Key:").pack(side=tk.LEFT, padx=3)
        self.api_key_entry = ttk.Entry(self.ai_frame, show="*", width=15)
        # 显示解码后的 key
        decoded_key = self.compression_config.get_api_key()
        if decoded_key:
            self.api_key_entry.insert(0, decoded_key)
        self.api_key_entry.pack(side=tk.LEFT, padx=3)
        
        # 模式选择（简化：只保留正常模式和吐槽模式）
        ttk.Label(self.ai_frame, text="模式:").pack(side=tk.LEFT, padx=3)
        self.compress_mode_var = tk.StringVar(value='正常模式')
        self.mode_combo = ttk.Combobox(self.ai_frame, textvariable=self.compress_mode_var,
                                       values=['正常模式', '吐槽模式'], 
                                       width=10, state="readonly")
        self.mode_combo.pack(side=tk.LEFT, padx=3)
        
        # 模型
        self.model_combo = ttk.Combobox(self.ai_frame, values=API_TEMPLATES[self.compression_config.api_provider]['models'], 
                                        width=12, state="readonly")
        self.model_combo.set(self.compression_config.model)
        self.model_combo.pack(side=tk.LEFT, padx=3)
        
        # 右侧：立即压缩和自动压缩（放在同一行最右边）
        right_frame = ttk.Frame(self.ai_frame)
        right_frame.pack(side=tk.RIGHT, padx=5)
        
        # 自动压缩选项（需要从配置加载，DEFAULT_CONFIG中默认为False）
        self.auto_compress_var = tk.BooleanVar(value=self.compression_config.auto_compress_enabled)
        ttk.Checkbutton(right_frame, text="自动", variable=self.auto_compress_var).pack(side=tk.LEFT, padx=3)
        
        ttk.Label(right_frame, text="间隔(s):").pack(side=tk.LEFT, padx=1)
        self.auto_compress_interval_spin = ttk.Spinbox(right_frame, from_=30, to=3600, width=6)
        self.auto_compress_interval_spin.set(str(self.compression_config.auto_compress_interval))
        self.auto_compress_interval_spin.pack(side=tk.LEFT, padx=1)
        
        # 立即压缩按钮（带自动压缩功能）
        self.compress_btn = ttk.Button(right_frame, text="立即压缩", command=self.manual_compress_with_auto)
        self.compress_btn.pack(side=tk.LEFT, padx=5)
        
        # 外部文件接入面板（单独一行）
        file_monitor_frame = ttk.LabelFrame(main_frame, text="外部文件接入", padding="3")
        file_monitor_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=3)
        
        # 选择文件按钮
        ttk.Button(file_monitor_frame, text="选择文件", width=10, command=self.select_monitor_file).pack(side=tk.LEFT, padx=3)
        
        # 文件路径显示（只读）
        self.file_monitor_path_var = tk.StringVar(value=self.compression_config.file_monitor_path)
        self.file_monitor_entry = ttk.Entry(file_monitor_frame, textvariable=self.file_monitor_path_var, 
                                           width=45, state='readonly')
        self.file_monitor_entry.pack(side=tk.LEFT, padx=3)
        
        # 扫描频率
        ttk.Label(file_monitor_frame, text="频率(Hz):").pack(side=tk.LEFT, padx=3)
        self.file_monitor_freq_spin = ttk.Spinbox(file_monitor_frame, from_=0.1, to=10.0, width=5)
        self.file_monitor_freq_spin.set(str(self.compression_config.file_monitor_interval))
        self.file_monitor_freq_spin.pack(side=tk.LEFT, padx=3)
        
        # 文件监控按钮（单点触发/自动触发）
        self.file_monitor_btn = tk.Button(file_monitor_frame, text="读取", width=8, bg='#E0E0E0')
        self.file_monitor_btn.pack(side=tk.LEFT, padx=5)
        self.file_monitor_btn.bind('<ButtonPress-1>', self.on_file_monitor_press)
        self.file_monitor_btn.bind('<ButtonRelease-1>', self.on_file_monitor_release)
        
        # 文件监控状态标签
        self.file_monitor_status_var = tk.StringVar(value="关闭")
        ttk.Label(file_monitor_frame, textvariable=self.file_monitor_status_var, foreground='gray').pack(side=tk.LEFT, padx=3)
        
        # 文件监控长按进度条
        self.file_monitor_progress = ttk.Progressbar(file_monitor_frame, length=60, mode='determinate', maximum=100)
        self.file_monitor_progress.pack(side=tk.LEFT, padx=2)
        self.file_monitor_progress['value'] = 0
        
        # 文件监控长按定时器
        self.file_monitor_long_press_timer = None
        self.file_monitor_long_press_val = 0
        self.file_monitor_auto_mode = False
        
        # Token 统计栏（第3行，固定高度）
        stats_frame = ttk.LabelFrame(main_frame, text="Token 统计", padding="3")
        stats_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=3)
        
        self.stats_labels = {}
        stats_items = [
            ("input_tokens", "输入:"),
            ("output_tokens", "输出:"),
            ("total_tokens", "总计:"),
            ("estimated_tokens", "拟合:"),  # 新增：拟合Token
            ("usage_percent", "使用率:"),
            ("line_count", "行数:"),
            ("long_term", "长期:"),
            ("mid_term", "中期:"),
            ("short_term", "短期:"),
        ]
        
        for i, (key, label) in enumerate(stats_items):
            ttk.Label(stats_frame, text=label).grid(row=0, column=i*2, padx=2)
            self.stats_labels[key] = ttk.Label(stats_frame, text="-", font=("Consolas", 9, "bold"))
            self.stats_labels[key].grid(row=0, column=i*2+1, padx=2)
        
        # 主要内容区（第4行，可扩展）
        content_paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        content_paned.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=3)
        
        # 左侧：历史记录
        left_frame = ttk.LabelFrame(content_paned, text="历史记录", padding="3")
        content_paned.add(left_frame, weight=1)
        
        history_control = ttk.Frame(left_frame)
        history_control.pack(fill=tk.X, pady=2)
        
        ttk.Label(history_control, text="数量:").pack(side=tk.LEFT, padx=2)
        self.history_count_var = tk.StringVar(value="10")
        ttk.Combobox(history_control, textvariable=self.history_count_var, 
                    values=["10", "20", "50", "全部"], width=6, state="readonly").pack(side=tk.LEFT, padx=2)
        self.history_count_var.trace('w', lambda *args: self.load_history())
        
        ttk.Label(history_control, text="筛选:").pack(side=tk.LEFT, padx=5)
        self.filter_var = tk.StringVar(value="all")
        ttk.Combobox(history_control, textvariable=self.filter_var,
                    values=["all", "user", "assistant", "toolResult"], width=10, state="readonly").pack(side=tk.LEFT, padx=2)
        self.filter_var.trace('w', lambda *args: self.load_history())
        
        # 删除选中行按钮
        ttk.Button(history_control, text="删除选中", width=10, 
                  command=self.delete_selected_history).pack(side=tk.RIGHT, padx=5)
        
        self.history_listbox = tk.Listbox(left_frame, height=15, font=("Consolas", 9), selectmode=tk.EXTENDED)
        self.history_listbox.pack(fill=tk.BOTH, expand=True, pady=2)
        self.history_listbox.bind("<<ListboxSelect>>", self.on_history_selected)
        
        # 右侧：预览和内容
        right_frame = ttk.Frame(content_paned)
        content_paned.add(right_frame, weight=2)
        
        preview_frame = ttk.LabelFrame(right_frame, text="预览", padding="3")
        preview_frame.pack(fill=tk.X, pady=2)
        
        self.preview_text = tk.Text(preview_frame, height=3, wrap=tk.WORD, font=("Consolas", 9))
        self.preview_text.pack(fill=tk.X)
        
        detail_frame = ttk.LabelFrame(right_frame, text="详细内容", padding="3")
        detail_frame.pack(fill=tk.BOTH, expand=True, pady=2)
        
        self.content_text = scrolledtext.ScrolledText(detail_frame, wrap=tk.WORD, 
                                                       font=("Consolas", 9), height=10)
        self.content_text.pack(fill=tk.BOTH, expand=True)
        
        self.attachment_label = ttk.Label(right_frame, text="附件: 无", foreground="gray")
        self.attachment_label.pack(fill=tk.X, pady=2)
        
        # 底部：文件编辑（可折叠，第5行）
        self.edit_frame = ttk.LabelFrame(main_frame, text="文件编辑 ▶", padding="3")
        self.edit_frame.grid(row=5, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=3)
        self.edit_frame.bind('<Button-1>', self.toggle_edit_panel)
        self.edit_frame.grid_remove()
        
        self.edit_text = scrolledtext.ScrolledText(self.edit_frame, wrap=tk.WORD, 
                                                    font=("Consolas", 8), height=8)
        self.edit_text.pack(fill=tk.BOTH, expand=True)
        
        edit_btn_frame = ttk.Frame(self.edit_frame)
        edit_btn_frame.pack(fill=tk.X, pady=2)
        
        ttk.Button(edit_btn_frame, text="加载", command=self.load_file_for_edit).pack(side=tk.LEFT, padx=2)
        ttk.Button(edit_btn_frame, text="保存", command=self.save_file_edit).pack(side=tk.LEFT, padx=2)
        ttk.Button(edit_btn_frame, text="备份", command=self.backup_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(edit_btn_frame, text="删最后N", command=self.delete_last_n_lines).pack(side=tk.LEFT, padx=2)
        ttk.Button(edit_btn_frame, text="删前N", command=self.delete_first_n_lines).pack(side=tk.LEFT, padx=2)
        ttk.Button(edit_btn_frame, text="截断", command=self.truncate_file).pack(side=tk.LEFT, padx=2)
        
        # AI 结果区（第6行）
        self.ai_result_frame = ttk.LabelFrame(main_frame, text="AI 压缩结果", padding="3")
        self.ai_result_frame.grid(row=6, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=3)
        
        self.ai_result_text = scrolledtext.ScrolledText(self.ai_result_frame, wrap=tk.WORD, 
                                                         font=("Consolas", 9), height=6)
        self.ai_result_text.pack(fill=tk.BOTH, expand=True)
        
        ai_result_btn_frame = ttk.Frame(self.ai_result_frame)
        ai_result_btn_frame.pack(fill=tk.X, pady=2)
        
        ttk.Button(ai_result_btn_frame, text="应用压缩", command=self.apply_compression).pack(side=tk.LEFT, padx=2)
        ttk.Button(ai_result_btn_frame, text="复制结果", command=self.copy_ai_result).pack(side=tk.LEFT, padx=2)
        ttk.Button(ai_result_btn_frame, text="清空", command=self.clear_ai_result).pack(side=tk.LEFT, padx=2)
        
        # 状态栏（第7行）
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=3)
        
    def show_threshold_settings(self):
        """显示阈值设置对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("记忆阈值设置")
        dialog.geometry("350x350")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 自动压缩触发条件（与关系）
        ttk.Label(dialog, text="=== 自动压缩触发条件（需同时满足） ===", font=('', 9, 'bold')).pack(pady=5)
        
        ttk.Label(dialog, text="最小对话条数:").pack(pady=3)
        msg_count_entry = ttk.Entry(dialog)
        msg_count_entry.insert(0, str(self.compression_config.min_message_count))
        msg_count_entry.pack()
        
        ttk.Label(dialog, text="最小Token数:").pack(pady=3)
        token_count_entry = ttk.Entry(dialog)
        token_count_entry.insert(0, str(self.compression_config.min_token_count))
        token_count_entry.pack()
        
        ttk.Separator(dialog, orient='horizontal').pack(fill='x', pady=10)
        
        # 记忆分层阈值
        ttk.Label(dialog, text="=== 记忆分层阈值 ===", font=('', 9, 'bold')).pack(pady=5)
        
        ttk.Label(dialog, text="长期记忆触发阈值 (token):").pack(pady=3)
        long_entry = ttk.Entry(dialog)
        long_entry.insert(0, str(self.compression_config.long_term_threshold))
        long_entry.pack()
        
        ttk.Label(dialog, text="中期记忆触发阈值 (token):").pack(pady=3)
        mid_entry = ttk.Entry(dialog)
        mid_entry.insert(0, str(self.compression_config.mid_term_threshold))
        mid_entry.pack()
        
        ttk.Label(dialog, text="短期记忆保留条数:").pack(pady=3)
        short_entry = ttk.Entry(dialog)
        short_entry.insert(0, str(self.compression_config.short_term_keep))
        short_entry.pack()
        
        def save():
            try:
                self.compression_config.min_message_count = int(msg_count_entry.get())
                self.compression_config.min_token_count = int(token_count_entry.get())
                self.compression_config.long_term_threshold = int(long_entry.get())
                self.compression_config.mid_term_threshold = int(mid_entry.get())
                self.compression_config.short_term_keep = int(short_entry.get())
                self.save_compression_config()
                dialog.destroy()
                self.status_var.set("阈值设置已保存")
            except:
                messagebox.showerror("错误", "请输入有效的数字")
        
        ttk.Button(dialog, text="保存", command=save).pack(pady=10)
        
    def on_api_provider_changed(self, event=None):
        """API 提供商改变时更新 URL 和模型列表"""
        provider = self.api_provider_var.get()
        if provider in API_TEMPLATES:
            self.compression_config.api_provider = provider
            self.compression_config.api_url = API_TEMPLATES[provider]['url']
            self.model_combo['values'] = API_TEMPLATES[provider]['models']
            self.model_combo.set(API_TEMPLATES[provider]['models'][0])
            
    def toggle_edit_panel(self, event=None):
        """切换编辑面板显示"""
        if self.edit_frame.winfo_viewable():
            self.edit_frame.grid_remove()
        else:
            self.edit_frame.grid()
            
    def auto_load_on_start(self):
        """启动时自动加载 - 恢复所有保存的配置"""
        # 恢复API设置
        self.api_provider_var.set(self.compression_config.api_provider)
        self.on_api_provider_changed()  # 更新模型列表
        self.model_combo.set(self.compression_config.model)
        decoded_key = self.compression_config.get_api_key()
        if decoded_key:
            self.api_key_entry.delete(0, tk.END)
            self.api_key_entry.insert(0, decoded_key)
        
        # 恢复压缩设置
        self.compress_mode_var.set(self.compression_config.compress_mode)
        self.auto_compress_var.set(self.compression_config.auto_compress_enabled)
        self.auto_compress_interval_spin.set(str(self.compression_config.auto_compress_interval))
        self.silent_mode_var.set(self.compression_config.silent_mode)
        
        # 恢复文件监控配置
        self.file_monitor_path_var.set(self.compression_config.file_monitor_path)
        self.file_monitor_freq_spin.set(str(self.compression_config.file_monitor_interval))
        
        # 注意：自动压缩现在需要点击"立即压缩"按钮后才会启动
        # 这里只恢复UI状态，不自动启动循环
        if self.compression_config.auto_compress_enabled:
            self.status_var.set("自动压缩已启用，点击立即压缩开始执行")
        
        # 如果文件监控之前是启用的，恢复UI状态（但不自动启动，需要用户点击）
        if self.compression_config.file_monitor_enabled:
            self.file_monitor_status_var.set("待启动")
            self.status_var.set("文件监控已启用，点击'读取'按钮开始")
        
        if self.current_session_id:
            self.refresh_current()
            self.load_history()
            self.status_var.set("已自动加载当前会话，自动刷新已开启")
        
        # 启动UI自动刷新循环（1秒一次）
        self.start_ui_refresh_loop()
        
        # 默认开启自动刷新循环
        if self.is_auto_refresh:
            self.auto_refresh_loop()
        
    def start_ui_refresh_loop(self):
        """启动UI自动刷新循环"""
        self.ui_refresh_loop()
    
    def ui_refresh_loop(self):
        """UI自动刷新循环 - 每秒检查文件变化"""
        if not self.current_session_id or not self.current_jsonl_path:
            self.ui_refresh_timer = self.root.after(self.ui_refresh_interval, self.ui_refresh_loop)
            return
        
        try:
            # 检查文件是否有变化（通过比较行数）
            if self.current_jsonl_path.exists():
                with open(self.current_jsonl_path, 'r', encoding='utf-8', errors='ignore') as f:
                    current_lines = f.readlines()
                
                # 如果行数变化，自动刷新
                if len(current_lines) != len(self.all_lines):
                    self.refresh_current()
                    self.load_history()
        except:
            pass
        
        # 设置下次刷新
        self.ui_refresh_timer = self.root.after(self.ui_refresh_interval, self.ui_refresh_loop)
        
    def stop_ui_refresh_loop(self):
        """停止UI自动刷新循环"""
        if self.ui_refresh_timer:
            self.root.after_cancel(self.ui_refresh_timer)
            self.ui_refresh_timer = None
        
    def toggle_ai_compression(self):
        """切换 AI 压缩开关"""
        self.compression_config.enabled = self.ai_enable_var.get()
        if self.compression_config.enabled:
            self.compression_config.api_provider = self.api_provider_var.get()
            self.compression_config.api_url = API_TEMPLATES[self.compression_config.api_provider]['url']
            self.compression_config.set_api_key(self.api_key_entry.get())
            self.compression_config.model = self.model_combo.get()
            self.save_compression_config()
            self.status_var.set("AI 压缩已启用")
        else:
            self.status_var.set("AI 压缩已禁用")
            
    def test_api(self):
        """测试 API 连接"""
        api_key = self.api_key_entry.get()
        if not api_key:
            messagebox.showerror("错误", "请先输入 API Key")
            return
            
        self.status_var.set("正在测试 API...")
        self.root.update()
        
        try:
            provider = self.api_provider_var.get()
            url = API_TEMPLATES[provider]['url']
            model = self.model_combo.get()
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Kimi Code 需要特殊 headers
            if provider == 'kimicode':
                headers["User-Agent"] = "claude-code/0.1.0"
                headers["X-Client-Name"] = "claude-code"
            
            data = {
                "model": model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 10
            }
            
            self.ai_result_text.delete(1.0, tk.END)
            self.ai_result_text.insert(tk.END, f"测试 {provider} API...\n")
            self.ai_result_text.insert(tk.END, f"URL: {url}\n")
            self.ai_result_text.insert(tk.END, f"Model: {model}\n")
            self.ai_result_text.insert(tk.END, "-" * 40 + "\n")
            
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=10
            )
            
            self.ai_result_text.insert(tk.END, f"Status: {response.status_code}\n")
            self.ai_result_text.insert(tk.END, f"Response: {response.text[:500]}\n")
            
            if response.status_code == 200:
                messagebox.showinfo("成功", "API 连接测试成功！")
                self.status_var.set("API 测试成功")
            else:
                messagebox.showerror("失败", f"API 返回错误: {response.status_code}")
                self.status_var.set(f"API 测试失败: {response.status_code}")
                
        except Exception as e:
            error_msg = str(e)
            self.ai_result_text.insert(tk.END, f"Error: {error_msg}\n")
            messagebox.showerror("错误", f"API 测试失败: {error_msg}")
            self.status_var.set(f"API 测试失败: {error_msg}")
            
    def get_next_short_term_id(self):
        """获取下一个短期记忆 ID"""
        id_num = self.short_term_counter
        self.short_term_counter += 1
        if self.short_term_counter > SHORT_TERM_COUNT:
            self.short_term_counter = 1
        return f"{SHORT_TERM_PREFIX}{id_num:02d}"
        
    def parse_memory_structure(self):
        """解析当前文件的记忆结构 - 只解析message类型"""
        character = None    # 人设/初始化记忆 (baizhi00)
        long_term = None    # 长期记忆 (baizhi52)
        mid_term = None     # 中期记忆 (baizhi20)
        short_terms = []    # 短期记忆 (白芷01-19 + 其他)
        other_messages = [] # 其他message类型（非标准ID的）
        
        for i, line in enumerate(self.all_lines):
            try:
                data = json.loads(line.strip())
                msg_type = data.get('type', '')
                msg_id = data.get('id', '')
                
                # 只解析message类型，忽略session/model_change等非message类型
                if msg_type == 'message':
                    if msg_id == CHARACTER_ID:
                        character = {'index': i, 'data': data, 'line': line}
                    elif msg_id == LONG_TERM_ID:
                        long_term = {'index': i, 'data': data, 'line': line}
                    elif msg_id == MID_TERM_ID:
                        mid_term = {'index': i, 'data': data, 'line': line}
                    elif msg_id.startswith(SHORT_TERM_PREFIX):
                        short_terms.append({'index': i, 'data': data, 'line': line})
                    else:
                        # 其他message类型，视为短期记忆
                        other_messages.append({'index': i, 'data': data, 'line': line})
                        
            except:
                pass
        
        # 将其他message也加入短期记忆
        short_terms.extend(other_messages)
        short_terms.sort(key=lambda x: x['index'])
                
        return {
            'character': character,
            'long_term': long_term,
            'mid_term': mid_term,
            'short_terms': short_terms
        }
        
    def extract_message_text(self, msg_data):
        """从消息数据中提取文本"""
        msg = msg_data.get('message', {})
        content = msg.get('content', [])
        if content and isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    return item.get('text', '')
        return ''
    
    def calculate_estimated_tokens(self):
        """计算拟合Token数（基于文本内容）
        
        计算规则：
        - assistant角色（初始化+记忆）：字符数 ≈ token数
        - extern消息（外部高频数据）：固定50 token/条（小数据高频）
        """
        total_tokens = 0
        extern_count = 0
        
        for line in self.all_lines:
            try:
                data = json.loads(line.strip())
                if data.get('type') == 'message':
                    msg = data.get('message', {})
                    role = msg.get('role', '')
                    msg_id = data.get('id', '')
                    content = msg.get('content', [])
                    
                    # extern消息：固定50 token（小数据高频更新）
                    if role == 'toolResult' and msg_id.startswith('extern'):
                        extern_count += 1
                        total_tokens += 50  # 固定50 token/条
                    # assistant角色：字符数 ≈ token数
                    elif role == 'assistant' and isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                text = item.get('text', '')
                                total_tokens += len(text)
            except:
                pass
        
        return total_tokens
    
    def get_effective_tokens(self):
        """获取有效的Token数
        
        策略：
        - 压缩后30秒内：使用拟合Token
        - 30秒后：如果官方Token更新了，使用官方Token
        """
        current_time = time.time()
        time_since_compression = current_time - self.last_compression_time
        
        # 计算拟合Token
        self.estimated_tokens = self.calculate_estimated_tokens()
        
        # 压缩后30秒内，使用拟合Token
        if time_since_compression < 30:
            self.use_official_tokens = False
            return self.estimated_tokens
        
        # 30秒后，尝试使用官方Token
        try:
            if SESSIONS_JSON.exists():
                with open(SESSIONS_JSON, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for key, value in data.items():
                    if key.startswith("agent:") and value.get('sessionId') == self.current_session_id:
                        official = value.get('totalTokens', 0)
                        # 如果官方Token变化了，说明已更新
                        if official != self.official_tokens and official > 0:
                            self.official_tokens = official
                            self.use_official_tokens = True
                        break
        except:
            pass
        
        # 如果官方数据可用且已更新，使用官方；否则使用拟合
        if self.use_official_tokens and self.official_tokens > 0:
            return self.official_tokens
        return self.estimated_tokens
    
    def is_ai_outputting(self):
        """检查AI是否正在输出（近10秒内有assistant消息且id非extern）
        
        用于避免在AI输出期间触发自动压缩
        """
        current_time = time.time()
        
        # 检查最近的消息
        for line in reversed(self.all_lines[-10:]):  # 只检查最近10条
            try:
                data = json.loads(line.strip())
                if data.get('type') == 'message':
                    msg = data.get('message', {})
                    role = msg.get('role', '')
                    msg_id = data.get('id', '')
                    timestamp = data.get('timestamp', '')
                    
                    # 如果是assistant角色且id非extern
                    if role == 'assistant' and not msg_id.startswith('extern'):
                        # 解析时间戳
                        try:
                            msg_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            msg_timestamp = msg_time.timestamp()
                            # 如果在近10秒内
                            if current_time - msg_timestamp < 10:
                                return True
                        except:
                            pass
            except:
                pass
        
        return False
        
    def create_memory_message(self, msg_id, text, role='assistant'):
        """创建记忆消息（默认role=assistant，让AI助手能读取）"""
        return {
            "type": "message",
            "id": msg_id,
            "timestamp": datetime.now().isoformat() + "Z",
            "message": {
                "role": role,
                "content": [{"type": "text", "text": text}]
            }
        }
        
    def call_ai_compression(self, content_to_compress):
        """调用 AI 进行压缩"""
        api_key = self.api_key_entry.get()
        if not api_key:
            raise Exception("未设置 API Key")
            
        provider = self.api_provider_var.get()
        url = API_TEMPLATES[provider]['url']
        model = self.model_combo.get()
            
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Kimi Code 需要特殊 headers
        if provider == 'kimicode':
            headers["User-Agent"] = "claude-code/0.1.0"
            headers["X-Client-Name"] = "claude-code"
        
        prompt = f"""{self.compression_config.compression_prompt}

{content_to_compress}"""

        # kimi-k2.5 模型只支持 temperature=1
        temp = 1.0 if 'k2.5' in model else 0.3

        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
            "temperature": temp
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)

            if response.status_code == 200:
                try:
                    result = response.json()
                    # 检查 API 返回的错误
                    if 'error' in result:
                        raise Exception(f"API 返回错误: {result['error']}")
                    if 'choices' not in result or not result['choices']:
                        raise Exception(f"API 返回格式异常: {result}")
                    message = result['choices'][0].get('message', {})
                    if not message:
                        raise Exception(f"API 返回的 message 为空: {result['choices'][0]}")
                    # Kimi Code 可能返回 reasoning_content
                    content = message.get('content', '')
                    if not content:
                        content = message.get('reasoning_content', '')
                    return content.strip() if content else "(无回复)"
                except (KeyError, IndexError, json.JSONDecodeError) as e:
                    raise Exception(f"解析 API 响应失败: {e}, 响应: {response.text[:500]}")
            else:
                raise Exception(f"API 错误: {response.status_code} - {response.text[:500]}")
        except requests.exceptions.Timeout:
            raise Exception("API 请求超时")
        except requests.exceptions.ConnectionError:
            raise Exception("无法连接到 API，请检查网络")
            
    def manual_compress_with_auto(self):
        """立即压缩（带自动压缩选项）"""
        # 如果勾选了自动压缩，启动自动压缩循环
        if self.auto_compress_var.get():
            # 切换按钮文本为"触发"
            self.compress_btn.config(text="触发")
            
            self.compression_config.auto_compress_enabled = True
            try:
                self.compression_config.auto_compress_interval = int(self.auto_compress_interval_spin.get())
            except:
                self.compression_config.auto_compress_interval = 300
            self.save_compression_config()
            self.status_var.set(f"自动压缩已启动，间隔{self.compression_config.auto_compress_interval}秒")
            # 启动自动压缩循环
            self.auto_compress_loop()
        else:
            # 如果取消勾选，停止自动压缩
            if self.compression_config.auto_compress_enabled:
                self.compression_config.auto_compress_enabled = False
                self.save_compression_config()
                self.status_var.set("自动压缩已停止")
            
            # 恢复按钮文本为"立即压缩"
            self.compress_btn.config(text="立即压缩")
            
            # 执行一次手动压缩
            self.manual_compress()
    
    def manual_compress(self):
        """手动触发 AI 压缩（后台线程执行）"""
        if not self.current_jsonl_path:
            messagebox.showwarning("警告", "请先选择会话")
            return
            
        api_key = self.api_key_entry.get()
        if not api_key:
            messagebox.showerror("错误", "请先输入 API Key")
            return
        
        # 获取当前模式
        mode = self.compress_mode_var.get()
        
        # 在后台线程执行压缩
        def compress_worker():
            try:
                # 解析当前记忆结构
                memory = self.parse_memory_structure()
                
                # 提取人设记忆（baizhi00）- 不压缩，直接保留
                character_content = ""
                if memory['character']:
                    character_content = self.extract_message_text(memory['character']['data'])
                
                # 提取长期和中期记忆内容
                long_content = ""
                if memory['long_term']:
                    long_content = self.extract_message_text(memory['long_term']['data'])
                
                mid_content = ""
                if memory['mid_term']:
                    mid_content = self.extract_message_text(memory['mid_term']['data'])
                
                # 收集短期记忆内容（实际的对话历史）
                short_contents = []
                for short in memory['short_terms']:
                    text = self.extract_message_text(short['data'])
                    if text and len(text) > 10:  # 过滤太短的
                        short_contents.append(text[:1000])  # 每条最多 1000 字
                
                # 构建要压缩的实际内容
                if not short_contents:
                    self.root.after(0, lambda: self.status_var.set("没有可压缩的短期记忆"))
                    return
                
                # 简化：只保留正常模式和吐槽模式
                if mode == '正常模式':
                    self.root.after(0, lambda: self.status_var.set("正常模式压缩中..."))
                    # 正常模式：压缩所有对话内容生成新的记忆
                    all_history = []
                    if character_content:
                        all_history.append(f"【人设/初始化】{character_content[:2000]}")
                    # 包含之前的记忆内容（如果有）
                    if long_content:
                        all_history.append(f"【之前的长期记忆】{long_content[:3000]}")
                    if mid_content:
                        all_history.append(f"【之前的中期记忆】{mid_content[:3000]}")
                    all_history.append("【最近对话历史】")
                    all_history.extend(short_contents[-20:])
                    
                    history_text = "\n\n".join(all_history)
                    combined_prompt = f"{self.compression_config.compression_prompt}\n\n{history_text}"
                    new_long_text = self.call_ai_compression(combined_prompt)
                    
                    # 在主线程更新 UI
                    def update_ui_normal():
                        result_text = f"【新的记忆】\n{new_long_text}"
                        self.ai_result_text.delete(1.0, tk.END)
                        self.ai_result_text.insert(tk.END, result_text)
                        self.auto_compress_status = f"正常模式压缩完成 [{datetime.now().strftime('%H:%M:%S')}]"
                    
                    self.root.after(0, update_ui_normal)
                    
                elif mode == '吐槽模式':
                    self.root.after(0, lambda: self.status_var.set("吐槽模式：正在吐槽先前内容..."))
                    # 吐槽模式：对先前内容进行吐槽
                    all_history = []
                    if character_content:
                        all_history.append(f"【人设/初始化】{character_content[:1000]}")
                    if long_content:
                        all_history.append(f"【之前的长期记忆】{long_content[:1000]}")
                    if mid_content:
                        all_history.append(f"【之前的中期记忆】{mid_content[:1000]}")
                    all_history.append("【最近对话历史】")
                    all_history.extend(short_contents[-5:])
                    
                    history_text = "\n\n".join(all_history)
                    tsukkomi_prompt = f"{self.compression_config.tsukkomi_prompt}\n\n{history_text}"
                    tsukkomi_text = self.call_ai_compression(tsukkomi_prompt)
                    
                    def update_ui_tsukkomi():
                        result_text = f"【吐槽内容】\n{tsukkomi_text}"
                        self.ai_result_text.delete(1.0, tk.END)
                        self.ai_result_text.insert(tk.END, result_text)
                        self.auto_compress_status = f"吐槽模式完成 [{datetime.now().strftime('%H:%M:%S')}]"
                    
                    self.root.after(0, update_ui_tsukkomi)
                
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"[DEBUG] 压缩失败详情:\n{error_detail}")
                error_msg = str(e) if e else "未知错误(请查看控制台)"
                
                def show_error():
                    self.status_var.set(f"压缩失败: {error_msg}")
                    messagebox.showerror("错误", f"AI 压缩失败: {error_msg}\n\n请查看控制台获取详细信息")
                
                self.root.after(0, show_error)
        
        # 启动后台线程
        thread = threading.Thread(target=compress_worker, daemon=True)
        thread.start()
            
    def find_compact_marker_index(self):
        """查找 compact 标记的位置（通过 summary 字段标识）"""
        for i, line in enumerate(self.all_lines):
            try:
                data = json.loads(line.strip())
                if data.get('type') == 'message':
                    # 检查是否有 summary 字段且值为 "AI总结占位"
                    if data.get('summary') == "AI总结占位":
                        return i
                    # 或者检查消息内容是否包含占位标识（兼容旧版本）
                    msg = data.get('message', {})
                    content = msg.get('content', [])
                    if content and isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                text = item.get('text', '')
                                if 'summary: AI总结占位' in text or '===COMPACT===' in text:
                                    return i
            except:
                pass
        return -1

    def apply_compression(self):
        """应用 AI 压缩结果 - 首次：替换第一个user为compact标记；后续：从compact标记开始替换"""
        result_text = self.ai_result_text.get(1.0, tk.END).strip()
        if not result_text:
            messagebox.showwarning("警告", "没有压缩结果可应用")
            return

        if not messagebox.askyesno("确认", "首次：替换第一个user为compact标记\n后续：从compact标记开始替换为新的记忆结构\n确定要应用吗？"):
            return

        try:
            # 解析结果
            new_long_text = ""
            new_mid_text = ""

            # 查找长期记忆
            if "【新的长期记忆】" in result_text:
                long_start = result_text.find("【新的长期记忆】") + len("【新的长期记忆】")
                if "=" * 20 in result_text:
                    long_end = result_text.find("=" * 20)
                    new_long_text = result_text[long_start:long_end].strip()
                elif "【新的中期记忆】" in result_text:
                    long_end = result_text.find("【新的中期记忆】")
                    new_long_text = result_text[long_start:long_end].strip()

            # 查找中期记忆
            if "【新的中期记忆】" in result_text:
                mid_start = result_text.find("【新的中期记忆】") + len("【新的中期记忆】")
                new_mid_text = result_text[mid_start:].strip()

            if not new_long_text and not new_mid_text:
                messagebox.showerror("错误", "无法解析压缩结果，请检查格式")
                return

            # 解析当前记忆结构
            memory = self.parse_memory_structure()

            # 如果只有一个有内容，另一个使用旧内容
            if not new_long_text and memory['long_term']:
                new_long_text = self.extract_message_text(memory['long_term']['data'])
            if not new_mid_text and memory['mid_term']:
                new_mid_text = self.extract_message_text(memory['mid_term']['data'])

            # 备份
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKUP_DIR / f"{self.current_session_id}_{timestamp}.jsonl"
            import shutil
            shutil.copy2(self.current_jsonl_path, backup_path)

            # 查找是否已存在 compact 标记
            compact_index = self.find_compact_marker_index()
            
            # 构建新的文件内容
            new_lines = []
            insert_index = -1  # 标记插入位置

            if compact_index == -1:
                # 首次压缩：找到第一个user，将其位置替换为compact标记
                first_user_index = -1
                for i, line in enumerate(self.all_lines):
                    try:
                        data = json.loads(line.strip())
                        if data.get('type') == 'message':
                            msg = data.get('message', {})
                            role = msg.get('role', '')
                            if role == 'user':
                                first_user_index = i
                                break
                    except:
                        pass
                
                if first_user_index == -1:
                    messagebox.showwarning("警告", "没有找到user消息，无法应用压缩")
                    return
                
                # 保留第一个user之前的所有行
                new_lines.extend(self.all_lines[:first_user_index])
                insert_index = first_user_index
                
                # 找到最后一个保留的message的id作为compact的parentId
                last_retained_msg_id = None
                for line in reversed(new_lines):
                    try:
                        data = json.loads(line.strip())
                        if data.get('type') == 'message':
                            last_retained_msg_id = data.get('id')
                            break
                    except:
                        pass
            else:
                # 后续压缩：保留compact标记之前的所有行（包括compact标记本身的位置）
                new_lines.extend(self.all_lines[:compact_index])
                insert_index = compact_index
                
                # 找到最后一个保留的message的id作为compact的parentId
                last_retained_msg_id = None
                for line in reversed(new_lines):
                    try:
                        data = json.loads(line.strip())
                        if data.get('type') == 'message':
                            last_retained_msg_id = data.get('id')
                            break
                    except:
                        pass

            # 创建 compact 标记消息（包含 summary 字段作为标识符）
            compact_msg = self.create_memory_message(CHARACTER_ID, "===COMPACT===\nsummary: AI总结占位")
            compact_msg['summary'] = "AI总结占位"  # 添加标识字段
            compact_msg['parentId'] = last_retained_msg_id
            new_lines.append(json.dumps(compact_msg, ensure_ascii=False) + "\n")

            # 添加 baizhi52 长期记忆
            long_msg = self.create_memory_message(LONG_TERM_ID, new_long_text)
            long_msg['parentId'] = CHARACTER_ID
            new_lines.append(json.dumps(long_msg, ensure_ascii=False) + "\n")

            # 添加 baizhi20 中期记忆
            mid_msg = self.create_memory_message(MID_TERM_ID, new_mid_text)
            mid_msg['parentId'] = LONG_TERM_ID
            new_lines.append(json.dumps(mid_msg, ensure_ascii=False) + "\n")

            # 保留最近5条原始对话消息（排除之前压缩生成的消息）
            # 只保留 role 为 user 或 assistant 的原始消息
            original_messages = []
            for short in memory['short_terms']:
                msg_data = short['data']
                msg = msg_data.get('message', {})
                role = msg.get('role', '')
                msg_id = msg_data.get('id', '')
                # 只保留原始对话消息（user/assistant），排除外部导入和已压缩的消息
                if role in ['user', 'assistant'] and not msg_id.startswith('extern') and not msg_id.startswith('baizhi'):
                    original_messages.append(short)
            
            recent_shorts = original_messages[-5:]
            last_short_id = None
            for i, short in enumerate(recent_shorts):
                short_data = short['data'].copy()
                if i == 0:
                    # 第一条短期记忆的parentId指向中期记忆
                    short_data['parentId'] = MID_TERM_ID
                new_lines.append(json.dumps(short_data, ensure_ascii=False) + "\n")
                last_short_id = short_data.get('id')

            # 只有吐槽模式才添加第6条（baizhi21）
            mode = self.compress_mode_var.get()
            if mode == '吐槽模式':
                # 吐槽模式：第6句放吐槽内容
                mode_content = ""
                if "=" * 20 in result_text:
                    parts = result_text.split("=" * 20)
                    if len(parts) > 2:
                        mode_content = parts[-1].strip()
                if not mode_content:
                    mode_content = result_text
                
                if mode_content:
                    mode_msg = self.create_memory_message(MODE_MESSAGE_ID, mode_content)
                    if last_short_id:
                        mode_msg['parentId'] = last_short_id
                    else:
                        mode_msg['parentId'] = MID_TERM_ID
                    new_lines.append(json.dumps(mode_msg, ensure_ascii=False) + "\n")

            # 保存 jsonl 文件
            with open(self.current_jsonl_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            self.all_lines = new_lines
            
            # 更新 sessions.json 中的 token 统计
            self.update_sessions_json_after_compression()
            
            # 记录压缩时间，用于Token计算策略
            self.last_compression_time = time.time()
            self.use_official_tokens = False  # 压缩后30秒内使用拟合Token
            
            self.status_var.set(f"压缩已应用，备份: {backup_path.name}")
            
            # 根据静默模式决定是否显示弹窗
            if not self.compression_config.silent_mode:
                if compact_index == -1:
                    messagebox.showinfo("成功", f"首次压缩已应用！\n第一个user已替换为compact标记")
                else:
                    messagebox.showinfo("成功", f"后续压缩已应用！\n从compact标记开始更新记忆结构")
            
            self.refresh_current()
            self.load_history()

        except Exception as e:
            if not self.compression_config.silent_mode:
                messagebox.showerror("错误", f"应用压缩失败: {e}")
    
    def update_sessions_json_after_compression(self):
        """压缩后更新 sessions.json 中的 token 统计"""
        try:
            if not SESSIONS_JSON.exists():
                return
            
            # 计算新的行数和估计的 token 数
            new_line_count = len(self.all_lines)
            
            # 估算 token 数（简化估算：每行大约 100-200 tokens）
            estimated_tokens = new_line_count * 150
            
            # 读取并更新 sessions.json
            with open(SESSIONS_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            updated = False
            for key, value in data.items():
                if key.startswith("agent:") and value.get('sessionId') == self.current_session_id:
                    # 更新 token 数（取估计值和原值的较小者，避免过度估算）
                    old_tokens = value.get('totalTokens', 0)
                    new_tokens = min(estimated_tokens, old_tokens) if old_tokens > 0 else estimated_tokens
                    value['totalTokens'] = new_tokens
                    value['inputTokens'] = int(new_tokens * 0.7)  # 估算输入占 70%
                    value['outputTokens'] = int(new_tokens * 0.3)  # 估算输出占 30%
                    updated = True
                    break
            
            if updated:
                with open(SESSIONS_JSON, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"更新 sessions.json 失败: {e}")
            
    def copy_ai_result(self):
        """复制 AI 结果"""
        text = self.ai_result_text.get(1.0, tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("已复制到剪贴板")
        
    def clear_ai_result(self):
        """清空 AI 结果"""
        self.ai_result_text.delete(1.0, tk.END)
        
    def load_sessions(self):
        """加载会话列表"""
        try:
            sessions = []
            if SESSIONS_JSON.exists():
                with open(SESSIONS_JSON, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if key.startswith("agent:"):
                            session_id = value.get('sessionId', 'unknown')
                            model = value.get('model', 'unknown')
                            total = value.get('totalTokens', 0)
                            sessions.append(f"{session_id} | {model} | {total} tokens")
                            
            if sessions:
                self.session_combo['values'] = sessions
                self.session_combo.current(0)
                self.on_session_selected(None)
            else:
                self.session_combo['values'] = ["无可用会话"]
                
        except Exception as e:
            messagebox.showerror("错误", f"加载会话失败: {e}")
            
    def on_session_selected(self, event):
        """选择会话时"""
        selection = self.session_combo.get()
        if not selection or selection == "无可用会话":
            return
            
        session_id = selection.split(" | ")[0]
        self.current_session_id = session_id
        self.current_jsonl_path = SESSIONS_DIR / f"{session_id}.jsonl"
        self.all_lines = []
        self.all_messages = []
        
        # 切换会话时，清空文件监控缓存（确保新对话能重新读取）
        print(f"[文件监控] 切换会话到: {session_id}，清空缓存")
        self.file_monitor_last_lines = []
        
        # 如果文件监控在自动模式，退回手动模式
        if self.file_monitor_auto_mode:
            print(f"[文件监控] 检测到会话变动，自动模式退回手动")
            self.stop_file_monitor_auto()
            self.status_var.set("切换对话：外部接入已退回手动模式")
        
        self.refresh_current()
        self.load_history()
        
    def refresh_current(self):
        """刷新当前会话 - 使用拟合Token计算"""
        if not self.current_session_id:
            return
            
        try:
            # 优先从jsonl文件直接读取（实时）
            if self.current_jsonl_path and self.current_jsonl_path.exists():
                with open(self.current_jsonl_path, 'r', encoding='utf-8', errors='ignore') as f:
                    self.all_lines = f.readlines()
                
                line_count = len(self.all_lines)
                self.stats_labels["line_count"].config(text=f"{line_count}")
                
                # 计算拟合Token（基于文本内容）
                estimated_total = self.calculate_estimated_tokens()
                self.estimated_tokens = estimated_total
                estimated_input = int(estimated_total * 0.7)
                estimated_output = int(estimated_total * 0.3)
                context_tokens = 262144
                
                self.stats_labels["input_tokens"].config(text=f"{estimated_input:,}")
                self.stats_labels["output_tokens"].config(text=f"{estimated_output:,}")
                self.stats_labels["estimated_tokens"].config(text=f"{estimated_total:,}")  # 拟合Token
                
                # 获取有效Token（拟合或官方）
                effective_tokens = self.get_effective_tokens()
                self.stats_labels["total_tokens"].config(text=f"{effective_tokens:,}")
                
                usage = (effective_tokens / context_tokens) * 100
                self.stats_labels["usage_percent"].config(text=f"{usage:.1f}%")
                
                # 统计记忆结构
                memory = self.parse_memory_structure()
                self.stats_labels["long_term"].config(text="有" if memory['long_term'] else "无")
                self.stats_labels["mid_term"].config(text="有" if memory['mid_term'] else "无")
                self.stats_labels["short_term"].config(text=f"{len(memory['short_terms'])}")
            
            # 尝试从sessions.json获取更准确的token数（如果有的话）
            try:
                if SESSIONS_JSON.exists():
                    with open(SESSIONS_JSON, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    for key, value in data.items():
                        if value.get('sessionId') == self.current_session_id:
                            # 如果sessions.json的token数更大，使用它
                            json_tokens = value.get('totalTokens', 0)
                            current_display = int(self.stats_labels["total_tokens"].cget("text").replace(',', ''))
                            if json_tokens > current_display:
                                self.stats_labels["total_tokens"].config(text=f"{json_tokens:,}")
                                input_tokens = value.get('inputTokens', int(json_tokens * 0.7))
                                output_tokens = value.get('outputTokens', int(json_tokens * 0.3))
                                self.stats_labels["input_tokens"].config(text=f"{input_tokens:,}")
                                self.stats_labels["output_tokens"].config(text=f"{output_tokens:,}")
                                context_tokens = value.get('contextTokens', 262144)
                                usage = (json_tokens / context_tokens) * 100
                                self.stats_labels["usage_percent"].config(text=f"{usage:.1f}%")
                            break
            except:
                pass
            
        except Exception as e:
            self.status_var.set(f"刷新失败: {e}")
            
    def load_history(self):
        """加载历史记录"""
        if not self.current_jsonl_path or not self.current_jsonl_path.exists():
            return
            
        try:
            self.history_listbox.delete(0, tk.END)
            self.history = []
            self.all_messages = []
            
            count_str = self.history_count_var.get()
            max_count = 999999 if count_str == "全部" else int(count_str)
            
            # 解析所有消息
            for i, line in enumerate(self.all_lines):
                try:
                    data = json.loads(line.strip())
                    if data.get('type') == 'message':
                        msg = data.get('message', {})
                        role = msg.get('role', 'unknown')
                        timestamp = data.get('timestamp', '')
                        msg_id = data.get('id', '')
                        
                        # 标记记忆类型
                        memory_type = "普通"
                        if msg_id == CHARACTER_ID:
                            memory_type = "【人设】"
                        elif msg_id == LONG_TERM_ID:
                            memory_type = "【长期】"
                        elif msg_id == MID_TERM_ID:
                            memory_type = "【中期】"
                        elif msg_id.startswith(SHORT_TERM_PREFIX):
                            memory_type = "【短期】"
                        
                        content = msg.get('content', [])
                        text = ""
                        attachments = []
                        
                        if content and isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get('type') == 'text':
                                        text = item.get('text', '')
                                    elif item.get('type') == 'image':
                                        attachments.append('[图片]')
                                    elif item.get('type') == 'file':
                                        attachments.append(f"[文件]")
                        
                        msg_obj = {
                            'line_num': i + 1,
                            'role': role,
                            'memory_type': memory_type,
                            'timestamp': timestamp,
                            'text': text,
                            'attachments': attachments,
                            'data': data,
                            'line': line
                        }
                        self.all_messages.append(msg_obj)
                except:
                    pass
            
            # 筛选
            filter_type = self.filter_var.get()
            filtered = [m for m in self.all_messages if filter_type == "all" or m['role'] == filter_type]
            
            # 显示
            display_messages = list(reversed(filtered[-max_count:]))
            
            for msg in display_messages:
                self.history.append(msg)
                
                time_str = msg['timestamp'][11:19] if msg['timestamp'] else '??'
                preview = msg['text'][:25].replace('\n', ' ') if msg['text'] else '(无文本)'
                attach_str = f"[{len(msg['attachments'])}]" if msg['attachments'] else ""
                display = f"{msg['memory_type']}[{msg['role'][:3]}] {time_str} {attach_str} {preview}"
                
                # 根据记忆类型设置颜色
                if msg['memory_type'] == "【人设】":
                    color = '#FF5722'  # 深橙色（人设最重要）
                elif msg['memory_type'] == "【长期】":
                    color = '#E91E63'  # 粉色
                elif msg['memory_type'] == "【中期】":
                    color = '#9C27B0'  # 紫色
                elif msg['memory_type'] == "【短期】":
                    color = '#FF9800'  # 橙色
                else:
                    color = ROLE_COLORS.get(msg['role'], 'black')
                
                self.history_listbox.insert(tk.END, display)
                self.history_listbox.itemconfig(tk.END, {'fg': color})
                
            # 合并显示加载数量、时间和自动压缩状态
            time_str = datetime.now().strftime('%H:%M:%S')
            status_text = f"已加载 {len(self.history)} 条历史 | 刷新: {time_str}"
            if self.auto_compress_status:
                status_text += f" | {self.auto_compress_status}"
            self.status_var.set(status_text)
            
        except Exception as e:
            self.status_var.set(f"加载历史失败: {e}")
            
    def on_history_selected(self, event):
        """选择历史记录时显示详情"""
        selection = self.history_listbox.curselection()
        if not selection:
            return
            
        index = selection[0]
        if index < len(self.history):
            msg = self.history[index]
            self.display_message(msg)
            
    def display_message(self, msg):
        """显示消息详情"""
        self.preview_text.delete(1.0, tk.END)
        if msg['text']:
            preview = msg['text'][:200].replace('\n', ' ')
            if len(msg['text']) > 200:
                preview += "..."
            self.preview_text.insert(tk.END, preview)
        
        self.content_text.delete(1.0, tk.END)
        self.content_text.insert(tk.END, f"类型: {msg['memory_type']}\n")
        self.content_text.insert(tk.END, f"行号: {msg['line_num']}\n")
        self.content_text.insert(tk.END, f"角色: {msg['role']}\n")
        self.content_text.insert(tk.END, f"时间: {msg['timestamp']}\n")
        self.content_text.insert(tk.END, "-" * 40 + "\n\n")
        
        if msg['text']:
            self.content_text.insert(tk.END, "【文本内容】\n")
            self.content_text.insert(tk.END, msg['text'])
            self.content_text.insert(tk.END, "\n\n")
        
        if msg['attachments']:
            attach_text = ", ".join(msg['attachments'])
            self.attachment_label.config(text=f"附件: {attach_text}", foreground="orange")
        else:
            self.attachment_label.config(text="附件: 无", foreground="gray")
        
        self.content_text.insert(tk.END, "-" * 40 + "\n")
        self.content_text.insert(tk.END, "【原始JSON】\n")
        formatted = json.dumps(msg['data'], ensure_ascii=False, indent=2)
        self.content_text.insert(tk.END, formatted)
    
    def delete_selected_history(self):
        """删除选中的历史记录行（支持多选）"""
        selection = self.history_listbox.curselection()
        if not selection:
            if not self.compression_config.silent_mode:
                messagebox.showwarning("警告", "请先选择要删除的行")
            return
        
        # 获取所有选中的行号（按降序排列，从后往前删）
        indices = sorted(selection, reverse=True)
        line_nums = []
        for idx in indices:
            if idx < len(self.history):
                line_nums.append(self.history[idx]['line_num'])
        
        if not line_nums:
            return
        
        # 确认删除（静默模式下跳过确认）
        if not self.compression_config.silent_mode:
            preview = f"共 {len(line_nums)} 行"
            if len(line_nums) <= 3:
                preview = f"第 {', '.join(map(str, sorted(line_nums)))} 行"
            if not messagebox.askyesno("确认", f"确定要删除 {preview} 吗？"):
                return
        
        try:
            # 备份文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKUP_DIR / f"{self.current_session_id}_{timestamp}.jsonl"
            import shutil
            shutil.copy2(self.current_jsonl_path, backup_path)
            
            # 按降序删除行（从后往前删，避免行号变化）
            new_lines = self.all_lines.copy()
            for line_num in sorted(line_nums, reverse=True):
                new_lines = new_lines[:line_num-1] + new_lines[line_num:]
            
            # 保存文件
            with open(self.current_jsonl_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            
            self.all_lines = new_lines
            
            # 刷新显示
            self.refresh_current()
            self.load_history()
            
            self.status_var.set(f"已删除 {len(line_nums)} 行，备份: {backup_path.name}")
            
        except Exception as e:
            if not self.compression_config.silent_mode:
                messagebox.showerror("错误", f"删除失败: {e}")
            
    def decode_selected(self):
        """解码当前选中的行"""
        try:
            text = self.content_text.get(1.0, tk.END)
            if "【原始JSON】" in text:
                json_part = text.split("【原始JSON】")[1].strip()
                data = json.loads(json_part)
                self.content_text.delete(1.0, tk.END)
                self.content_text.insert(tk.END, json.dumps(data, ensure_ascii=False, indent=2))
        except:
            pass
            
    def copy_content(self):
        """复制内容到剪贴板"""
        try:
            text = self.content_text.get(1.0, tk.END)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status_var.set("已复制到剪贴板")
        except:
            pass
            
    def clear_display(self):
        """清空显示"""
        self.preview_text.delete(1.0, tk.END)
        self.content_text.delete(1.0, tk.END)
        self.attachment_label.config(text="附件: 无", foreground="gray")
        
    def load_file_for_edit(self):
        """加载文件到编辑区"""
        if not self.current_jsonl_path or not self.current_jsonl_path.exists():
            messagebox.showwarning("警告", "请先选择会话")
            return
            
        try:
            with open(self.current_jsonl_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            self.edit_text.delete(1.0, tk.END)
            self.edit_text.insert(tk.END, content)
            self.status_var.set(f"已加载文件: {self.current_jsonl_path.name}")
            
        except Exception as e:
            messagebox.showerror("错误", f"加载文件失败: {e}")
            
    def save_file_edit(self):
        """保存文件修改"""
        if not self.current_jsonl_path:
            return
            
        if not messagebox.askyesno("确认", "直接修改 jsonl 文件可能导致数据损坏！\n确定要保存吗？"):
            return
            
        try:
            content = self.edit_text.get(1.0, tk.END)
            lines = content.strip().split('\n')
            for i, line in enumerate(lines):
                if line.strip():
                    json.loads(line)
                    
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKUP_DIR / f"{self.current_session_id}_{timestamp}.jsonl"
            import shutil
            shutil.copy2(self.current_jsonl_path, backup_path)
            
            with open(self.current_jsonl_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            self.status_var.set(f"已保存，备份: {backup_path.name}")
            messagebox.showinfo("成功", f"文件已保存！\n原文件已备份到 backups 目录")
            self.refresh_current()
            
        except json.JSONDecodeError as e:
            messagebox.showerror("错误", f"JSON 格式错误: {e}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")
            
    def delete_last_n_lines(self):
        """删除最后N行"""
        if not self.all_lines:
            return
            
        n = simpledialog.askinteger("输入", "删除最后多少行？", initialvalue=10, minvalue=1)
        if not n:
            return
            
        if len(self.all_lines) <= n:
            messagebox.showwarning("警告", "行数不足")
            return
            
        if not messagebox.askyesno("确认", f"确定删除最后 {n} 行吗？"):
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKUP_DIR / f"{self.current_session_id}_{timestamp}.jsonl"
            import shutil
            shutil.copy2(self.current_jsonl_path, backup_path)
            
            new_lines = self.all_lines[:-n]
            with open(self.current_jsonl_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
                
            self.all_lines = new_lines
            self.status_var.set(f"已删除最后 {n} 行")
            self.refresh_current()
            
        except Exception as e:
            messagebox.showerror("错误", f"删除失败: {e}")
            
    def delete_first_n_lines(self):
        """删除前N行"""
        if not self.all_lines:
            return
            
        # 找到第一条 message 的位置
        first_msg_index = 0
        for i, line in enumerate(self.all_lines):
            try:
                data = json.loads(line.strip())
                if data.get('type') == 'message':
                    first_msg_index = i
                    break
            except:
                pass
        
        max_delete = len(self.all_lines) - first_msg_index - self.compression_config.short_term_keep
        if max_delete <= 0:
            messagebox.showwarning("警告", "没有可删除的行（需要保留短期记忆）")
            return
            
        n = simpledialog.askinteger("输入", 
            f"第一条消息在第 {first_msg_index + 1} 行\n"
            f"最多可删除: {max_delete} 行\n"
            f"要删除前多少行？", 
            initialvalue=min(10, max_delete), minvalue=1, maxvalue=max_delete)
            
        if not n:
            return
            
        if not messagebox.askyesno("确认", f"确定删除前 {n} 行吗？"):
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKUP_DIR / f"{self.current_session_id}_{timestamp}.jsonl"
            import shutil
            shutil.copy2(self.current_jsonl_path, backup_path)
            
            new_lines = self.all_lines[n:]
            with open(self.current_jsonl_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
                
            self.all_lines = new_lines
            self.status_var.set(f"已删除前 {n} 行")
            self.refresh_current()
            
        except Exception as e:
            messagebox.showerror("错误", f"删除失败: {e}")
            
    def truncate_file(self):
        """截断文件"""
        if not self.all_lines:
            return
            
        n = simpledialog.askinteger("输入", f"保留前多少行？（当前共 {len(self.all_lines)} 行）", 
                                   initialvalue=min(100, len(self.all_lines)), minvalue=1)
        if not n:
            return
            
        if len(self.all_lines) <= n:
            messagebox.showinfo("提示", f"文件只有 {len(self.all_lines)} 行，无需截断")
            return
            
        if not messagebox.askyesno("确认", f"确定要截断为前 {n} 行吗？"):
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKUP_DIR / f"{self.current_session_id}_{timestamp}.jsonl"
            import shutil
            shutil.copy2(self.current_jsonl_path, backup_path)
            
            with open(self.current_jsonl_path, 'w', encoding='utf-8') as f:
                f.writelines(self.all_lines[:n])
                
            self.all_lines = self.all_lines[:n]
            self.status_var.set(f"已截断为前 {n} 行")
            self.refresh_current()
            
        except Exception as e:
            messagebox.showerror("错误", f"截断失败: {e}")
            
    def backup_file(self):
        """备份文件"""
        if not self.current_jsonl_path or not self.current_jsonl_path.exists():
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKUP_DIR / f"{self.current_session_id}_{timestamp}.jsonl"
            import shutil
            shutil.copy2(self.current_jsonl_path, backup_path)
            
            self.status_var.set(f"已备份: {backup_path.name}")
            messagebox.showinfo("成功", f"文件已备份到 backups 目录:\n{backup_path.name}")
            
        except Exception as e:
            messagebox.showerror("错误", f"备份失败: {e}")
            
    def on_refresh_press(self, event=None):
        """刷新按钮按下 - 开始长按检测"""
        if self.is_auto_refresh:
            # 如果已经在自动刷新模式，单击取消
            self.is_auto_refresh = False
            self.refresh_btn.config(text="刷新")
            self.status_var.set("自动刷新已取消")
            return
        
        # 开始长按检测
        self.long_press_progress_val = 0
        self.long_press_progress['value'] = 0
        self._long_press_step()
    
    def _long_press_step(self):
        """长按进度步进"""
        if self.is_auto_refresh:
            return
        
        self.long_press_progress_val += 5  # 每步增加5%
        self.long_press_progress['value'] = self.long_press_progress_val
        
        if self.long_press_progress_val >= 100:
            # 长按满，开启自动刷新
            self.is_auto_refresh = True
            self.refresh_btn.config(text="自动刷新")
            self.status_var.set("自动刷新已开启，再次点击取消")
            self.long_press_progress['value'] = 0
            # 启动自动刷新循环
            self.auto_refresh_loop()
        else:
            # 继续步进（每50ms一次，总共1秒满）
            self.long_press_timer = self.root.after(50, self._long_press_step)
    
    def on_refresh_release(self, event=None):
        """刷新按钮释放"""
        if self.long_press_timer:
            self.root.after_cancel(self.long_press_timer)
            self.long_press_timer = None
        
        if not self.is_auto_refresh:
            # 如果不是自动刷新模式，执行单次刷新
            self.long_press_progress['value'] = 0
            # 刷新会话列表（检测新开对话）和当前会话
            self.load_sessions()
            self.refresh_current()
            self.load_history()
    
    def auto_refresh_loop(self):
        """自动刷新循环"""
        if self.is_auto_refresh:
            # 刷新会话列表（检测新开对话）和当前会话
            self.load_sessions()
            self.refresh_current()
            self.load_history()
            # 自动刷新间隔1秒
            self.root.after(1000, self.auto_refresh_loop)
    
    def compress_sessions_json(self):
        """压缩 sessions.json，移除历史token统计，保留当前token数"""
        if not SESSIONS_JSON.exists():
            messagebox.showwarning("警告", "sessions.json 不存在")
            return
        
        try:
            # 读取原始文件
            with open(SESSIONS_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 备份原文件
            backup_path = SESSIONS_JSON.with_suffix('.json.backup')
            import shutil
            shutil.copy2(SESSIONS_JSON, backup_path)
            
            # 压缩数据：只保留必要的字段
            compressed_count = 0
            for key, value in data.items():
                if key.startswith("agent:"):
                    # 保留当前token数，删除历史统计
                    if 'tokenHistory' in value:
                        del value['tokenHistory']
                        compressed_count += 1
                    # 删除其他不必要的历史数据
                    for field in ['inputHistory', 'outputHistory', 'usageHistory']:
                        if field in value:
                            del value[field]
                            compressed_count += 1
            
            # 保存压缩后的文件
            with open(SESSIONS_JSON, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 计算压缩效果
            original_size = os.path.getsize(backup_path)
            compressed_size = os.path.getsize(SESSIONS_JSON)
            saved = original_size - compressed_size
            
            self.status_var.set(f"Sessions.json 已压缩: {saved/1024:.1f}KB 节省")
            
            # 切换按钮为恢复模式
            self.sessions_compress_btn.config(text="恢复Sessions", bg='#E0FFE0', 
                                              command=self.restore_sessions_json)
            
            if not self.compression_config.silent_mode:
                messagebox.showinfo("成功", f"sessions.json 已压缩\n"
                                   f"原始大小: {original_size/1024:.1f}KB\n"
                                   f"压缩后: {compressed_size/1024:.1f}KB\n"
                                   f"节省: {saved/1024:.1f}KB ({saved/original_size*100:.1f}%)\n"
                                   f"备份: {backup_path.name}")
            
        except Exception as e:
            if not self.compression_config.silent_mode:
                messagebox.showerror("错误", f"压缩失败: {e}")
            self.status_var.set(f"压缩失败: {e}")
    
    def restore_sessions_json(self):
        """恢复 sessions.json 从备份"""
        backup_path = SESSIONS_JSON.with_suffix('.json.backup')
        
        if not backup_path.exists():
            messagebox.showwarning("警告", "备份文件不存在，无法恢复")
            return
        
        try:
            # 恢复备份
            import shutil
            shutil.copy2(backup_path, SESSIONS_JSON)
            
            self.status_var.set("Sessions.json 已恢复")
            
            # 切换按钮回压缩模式
            self.sessions_compress_btn.config(text="压缩Sessions", bg='#FFE0E0',
                                              command=self.compress_sessions_json)
            
            if not self.compression_config.silent_mode:
                messagebox.showinfo("成功", "sessions.json 已从备份恢复")
            
        except Exception as e:
            if not self.compression_config.silent_mode:
                messagebox.showerror("错误", f"恢复失败: {e}")
            self.status_var.set(f"恢复失败: {e}")
    
    def toggle_auto_compress(self):
        """切换自动压缩"""
        self.compression_config.auto_compress_enabled = self.auto_compress_var.get()
        if self.compression_config.auto_compress_enabled:
            try:
                self.compression_config.auto_compress_interval = int(self.auto_compress_interval_spin.get())
            except:
                self.compression_config.auto_compress_interval = 300
            self.save_compression_config()
            self.status_var.set(f"自动压缩已启用，间隔{self.compression_config.auto_compress_interval}秒")
            # 启动自动压缩循环
            self.auto_compress_loop()
        else:
            self.status_var.set("自动压缩已禁用")
    
    def auto_compress_loop(self):
        """自动压缩循环"""
        if self.compression_config.auto_compress_enabled and self.current_jsonl_path:
            # 执行压缩并应用
            self.manual_compress_and_apply()
            # 设置下次执行
            interval_ms = self.compression_config.auto_compress_interval * 1000
            self.root.after(interval_ms, self.auto_compress_loop)
    
    def check_compression_conditions(self):
        """检查是否满足自动压缩条件（与关系：同时满足才触发）
        返回: (是否满足, 原因)
        """
        try:
            # 从配置获取阈值
            min_tokens = self.compression_config.min_token_count
            min_messages = self.compression_config.min_message_count
            
            # 从 sessions.json 获取 token 信息
            total_tokens = 0
            if SESSIONS_JSON.exists():
                with open(SESSIONS_JSON, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if key.startswith("agent:") and value.get('sessionId') == self.current_session_id:
                            total_tokens = value.get('totalTokens', 0)
                            break
            
            # 统计对话条数（message 类型且 role 为 user 或 assistant）
            message_count = 0
            if self.current_jsonl_path and self.current_jsonl_path.exists():
                with open(self.current_jsonl_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        try:
                            data = json.loads(line.strip())
                            if data.get('type') == 'message':
                                msg = data.get('message', {})
                                role = msg.get('role', '')
                                if role in ['user', 'assistant']:
                                    message_count += 1
                        except:
                            pass
            
            # 检查条件（与关系：同时满足）
            token_ok = total_tokens >= min_tokens
            msg_ok = message_count >= min_messages
            
            if not token_ok and not msg_ok:
                return False, f"Token {total_tokens}/{min_tokens}，对话 {message_count}/{min_messages}，均未满足"
            elif not token_ok:
                return False, f"Token {total_tokens} < {min_tokens}，对话 {message_count} 已满足"
            elif not msg_ok:
                return False, f"Token {total_tokens} 已满足，对话 {message_count} < {min_messages}"
            
            return True, f"条件满足：Token {total_tokens}/{min_tokens}，对话 {message_count}/{min_messages}"
            
        except Exception as e:
            return False, f"检查条件失败: {e}"
    
    def manual_compress_and_apply(self):
        """自动执行压缩并应用（静默模式）"""
        if not self.current_jsonl_path:
            return
        
        api_key = self.api_key_entry.get()
        if not api_key:
            return
        
        # 检查AI是否正在输出（避免在AI输出期间压缩）
        if self.is_ai_outputting():
            self.auto_compress_status = f"自动压缩跳过: AI正在输出 [{datetime.now().strftime('%H:%M:%S')}]"
            return
        
        # JSON 核验：检查 token 和对话条数
        can_compress, reason = self.check_compression_conditions()
        time_str = datetime.now().strftime('%H:%M:%S')
        if not can_compress:
            self.auto_compress_status = f"自动压缩跳过: {reason} [{time_str}]"
            return
        
        self.auto_compress_status = f"自动压缩开始: {reason} [{time_str}]"
        
        # 临时设置静默模式
        original_silent = self.compression_config.silent_mode
        self.compression_config.silent_mode = True
        
        def compress_worker():
            try:
                # 解析当前记忆结构
                memory = self.parse_memory_structure()
                
                # 提取长期和中期记忆内容
                long_content = ""
                if memory['long_term']:
                    long_content = self.extract_message_text(memory['long_term']['data'])
                
                mid_content = ""
                if memory['mid_term']:
                    mid_content = self.extract_message_text(memory['mid_term']['data'])
                
                # 收集短期记忆内容
                short_contents = []
                for short in memory['short_terms']:
                    text = self.extract_message_text(short['data'])
                    if text and len(text) > 10:
                        short_contents.append(text[:1000])
                
                if not short_contents:
                    return
                
                # 根据模式执行压缩
                mode = self.compress_mode_var.get()
                
                if mode == '长期模式':
                    # 长期模式：只压缩最近20条短期记忆作为新的长期记忆
                    # 不传入旧的长期记忆内容，避免累积
                    all_history = ["【最近对话历史】"]
                    all_history.extend(short_contents[-20:])
                    
                    history_text = "\n\n".join(all_history)
                    combined_prompt = f"{self.compression_config.compression_prompt}\n\n{history_text}"
                    new_long_text = self.call_ai_compression(combined_prompt)
                    
                    # 中期记忆使用最近10条单独压缩
                    recent_history = "\n\n".join(short_contents[-10:])
                    mid_prompt = f"{self.compression_config.compression_prompt}\n\n【最近对话历史】\n\n{recent_history}"
                    new_mid_text = self.call_ai_compression(mid_prompt)
                    
                elif mode == '中期模式':
                    new_long_text = long_content if long_content else "（无长期记忆）"
                    
                    recent_history = "\n\n".join(short_contents[-10:])
                    mid_prompt = f"{self.compression_config.compression_prompt}\n\n【最近对话历史】\n\n{recent_history}"
                    new_mid_text = self.call_ai_compression(mid_prompt)
                    
                elif mode == '短期模式':
                    # 短期模式不执行压缩
                    self.compression_config.silent_mode = original_silent
                    return
                    
                elif mode == '吐槽模式':
                    new_long_text = long_content if long_content else "（无长期记忆）"
                    new_mid_text = mid_content if mid_content else "（无中期记忆）"
                
                # 在主线程应用压缩
                def apply_in_main():
                    try:
                        self.apply_compression_silent(new_long_text, new_mid_text)
                    except:
                        pass
                    finally:
                        self.compression_config.silent_mode = original_silent
                
                self.root.after(0, apply_in_main)
                
            except Exception as e:
                self.compression_config.silent_mode = original_silent
        
        thread = threading.Thread(target=compress_worker, daemon=True)
        thread.start()
    
    def apply_compression_silent(self, new_long_text, new_mid_text):
        """静默应用压缩（无弹窗）"""
        try:
            # 备份
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKUP_DIR / f"{self.current_session_id}_{timestamp}.jsonl"
            import shutil
            shutil.copy2(self.current_jsonl_path, backup_path)
            
            # 查找 compact 标记
            compact_index = self.find_compact_marker_index()
            
            # 构建新的文件内容
            new_lines = []
            last_retained_msg_id = None
            
            if compact_index == -1:
                # 首次压缩
                first_user_index = -1
                for i, line in enumerate(self.all_lines):
                    try:
                        data = json.loads(line.strip())
                        if data.get('type') == 'message':
                            msg = data.get('message', {})
                            if msg.get('role', '') == 'user':
                                first_user_index = i
                                break
                    except:
                        pass
                
                if first_user_index == -1:
                    return
                
                new_lines.extend(self.all_lines[:first_user_index])
                
                for line in reversed(new_lines):
                    try:
                        data = json.loads(line.strip())
                        if data.get('type') == 'message':
                            last_retained_msg_id = data.get('id')
                            break
                    except:
                        pass
            else:
                new_lines.extend(self.all_lines[:compact_index])
                
                for line in reversed(new_lines):
                    try:
                        data = json.loads(line.strip())
                        if data.get('type') == 'message':
                            last_retained_msg_id = data.get('id')
                            break
                    except:
                        pass
            
            # 添加 compact 标记
            compact_msg = self.create_memory_message(CHARACTER_ID, "===COMPACT===\nsummary: AI总结占位")
            compact_msg['summary'] = "AI总结占位"
            compact_msg['parentId'] = last_retained_msg_id
            new_lines.append(json.dumps(compact_msg, ensure_ascii=False) + "\n")
            
            # 添加长期和中期记忆
            long_msg = self.create_memory_message(LONG_TERM_ID, new_long_text)
            long_msg['parentId'] = CHARACTER_ID
            new_lines.append(json.dumps(long_msg, ensure_ascii=False) + "\n")
            
            mid_msg = self.create_memory_message(MID_TERM_ID, new_mid_text)
            mid_msg['parentId'] = LONG_TERM_ID
            new_lines.append(json.dumps(mid_msg, ensure_ascii=False) + "\n")
            
            # 解析当前记忆结构获取短期记忆
            memory = self.parse_memory_structure()
            recent_shorts = memory['short_terms'][-5:]
            last_short_id = None
            
            for i, short in enumerate(recent_shorts):
                short_data = short['data'].copy()
                if i == 0:
                    short_data['parentId'] = MID_TERM_ID
                new_lines.append(json.dumps(short_data, ensure_ascii=False) + "\n")
                last_short_id = short_data.get('id')
            
            # 只有吐槽模式才添加 baizhi21
            mode = self.compress_mode_var.get()
            if mode == '吐槽模式':
                mode_content = new_long_text  # 吐槽内容
                if mode_content:
                    mode_msg = self.create_memory_message(MODE_MESSAGE_ID, mode_content)
                    if last_short_id:
                        mode_msg['parentId'] = last_short_id
                    else:
                        mode_msg['parentId'] = MID_TERM_ID
                    new_lines.append(json.dumps(mode_msg, ensure_ascii=False) + "\n")
            
            # 保存
            with open(self.current_jsonl_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            
            self.all_lines = new_lines
            
            # 记录压缩时间
            self.last_compression_time = time.time()
            self.use_official_tokens = False
            
            self.status_var.set(f"自动压缩已应用，备份: {backup_path.name}")
            self.refresh_current()
            
        except Exception as e:
            self.status_var.set(f"自动压缩失败: {e}")
    
    def toggle_silent_mode(self):
        """切换静默模式"""
        self.compression_config.silent_mode = self.silent_mode_var.get()
        self.save_compression_config()
        status = "开启" if self.compression_config.silent_mode else "关闭"
        self.status_var.set(f"静默模式已{status}")
    
    def select_monitor_file(self):
        """选择要监控的文件"""
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title="选择要监控的文件",
            filetypes=[("文本文件", "*.txt"), ("JSON文件", "*.json"), ("JSONL文件", "*.jsonl"), ("所有文件", "*.*")]
        )
        if file_path:
            self.compression_config.file_monitor_path = file_path
            self.file_monitor_path_var.set(file_path)
            self.save_compression_config()
            self.status_var.set(f"已选择监控文件: {file_path}")
    
    def on_file_monitor_press(self, event=None):
        """文件监控按钮按下 - 开始长按检测"""
        if self.file_monitor_auto_mode:
            # 如果已经在自动模式，单击停止
            self.stop_file_monitor_auto()
            return
        
        # 检查前提条件
        if not self.current_jsonl_path:
            messagebox.showwarning("警告", "请先选择一个会话")
            return
        
        if not self.compression_config.file_monitor_path:
            messagebox.showwarning("警告", "请先选择要监控的文件")
            return
        
        # 开始长按检测
        self.file_monitor_long_press_val = 0
        self.file_monitor_progress['value'] = 0
        self._file_monitor_long_press_step()
    
    def _file_monitor_long_press_step(self):
        """文件监控长按进度步进"""
        if self.file_monitor_auto_mode:
            return
        
        self.file_monitor_long_press_val += 5  # 每步增加5%
        self.file_monitor_progress['value'] = self.file_monitor_long_press_val
        
        if self.file_monitor_long_press_val >= 100:
            # 长按满，开启自动模式
            self.start_file_monitor_auto()
        else:
            # 继续步进（每50ms一次，总共1秒满）
            self.file_monitor_long_press_timer = self.root.after(50, self._file_monitor_long_press_step)
    
    def on_file_monitor_release(self, event=None):
        """文件监控按钮释放"""
        if self.file_monitor_long_press_timer:
            self.root.after_cancel(self.file_monitor_long_press_timer)
            self.file_monitor_long_press_timer = None
        
        if not self.file_monitor_auto_mode:
            # 如果不是自动模式，执行单次读取
            self.file_monitor_progress['value'] = 0
            self.manual_read_file()
    
    def start_file_monitor_auto(self):
        """启动文件监控自动模式"""
        self.file_monitor_auto_mode = True
        self.file_monitor_btn.config(text="自动", bg='#4CAF50')
        self.file_monitor_status_var.set("自动")
        self.file_monitor_progress['value'] = 0
        
        # 初始化并启动
        self._init_file_monitor()
        self.file_monitor_loop()
        
        # 保存配置
        self.compression_config.file_monitor_enabled = True
        self.save_compression_config()
        
        self.status_var.set("文件监控自动模式已启动")
    
    def stop_file_monitor_auto(self):
        """停止文件监控自动模式"""
        self.file_monitor_auto_mode = False
        self.file_monitor_btn.config(text="读取", bg='#E0E0E0')
        self.file_monitor_status_var.set("关闭")
        self.file_monitor_progress['value'] = 0
        
        # 停止循环
        if self.file_monitor_timer:
            self.root.after_cancel(self.file_monitor_timer)
            self.file_monitor_timer = None
        
        # 保存配置
        self.compression_config.file_monitor_enabled = False
        self.save_compression_config()
        
        self.status_var.set("文件监控已停止")
    
    def manual_read_file(self):
        """手动单次读取文件（清空缓存，重新加载）"""
        # 检查前提条件
        if not self.current_jsonl_path:
            messagebox.showwarning("警告", "请先选择一个会话")
            return
        
        if not self.compression_config.file_monitor_path:
            messagebox.showwarning("警告", "请先选择要监控的文件")
            return
        
        # 手动读取时清空缓存，重新加载
        print("[文件监控] 手动读取：清空缓存，重新加载")
        self.file_monitor_last_lines = []
        
        # 执行一次读取
        self.check_and_import_file()
    
    def _init_file_monitor(self):
        """初始化文件监控状态"""
        self.file_monitor_last_content = ""
        self.file_monitor_last_lines = []
        
        # 预读取现有内容作为基准（不导入）
        if os.path.exists(self.compression_config.file_monitor_path):
            try:
                with open(self.compression_config.file_monitor_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                self.file_monitor_last_lines = [line.strip() for line in lines if line.strip()]
                print(f"[文件监控] 预读取 {len(self.file_monitor_last_lines)} 行作为基准")
            except Exception as e:
                print(f"[文件监控] 预读取失败: {e}")
        
        # 更新频率
        try:
            freq = float(self.file_monitor_freq_spin.get())
            self.compression_config.file_monitor_interval = freq
        except:
            pass
        
        print(f"[文件监控] 目标会话: {self.current_jsonl_path}")
    
    def file_monitor_loop(self):
        """文件监控循环"""
        if not self.file_monitor_auto_mode:
            return
        
        try:
            self.check_and_import_file()
        except Exception as e:
            print(f"[文件监控] 错误: {e}")
        
        # 计算下次执行时间（毫秒）
        interval_ms = int(1000 / self.compression_config.file_monitor_interval)
        self.file_monitor_timer = self.root.after(interval_ms, self.file_monitor_loop)
    
    def check_and_import_file(self):
        """检查文件并导入新增内容（基于内容哈希检测新行）"""
        file_path = self.compression_config.file_monitor_path
        if not file_path or not os.path.exists(file_path):
            print(f"[文件监控] 文件不存在: {file_path}")
            return
        
        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # 过滤空行
            current_lines = [line.strip() for line in lines if line.strip()]
            
            # 将已导入的行转为集合用于快速查找
            imported_set = set(self.file_monitor_last_lines)
            
            # 找出真正的新行（不在已导入集合中的）
            new_lines = []
            for line in current_lines:
                if line not in imported_set:
                    new_lines.append(line)
            
            print(f"[文件监控] 当前文件行数: {len(current_lines)}, 已导入: {len(imported_set)}, 新行: {len(new_lines)}")
            
            if not new_lines:
                print(f"[文件监控] 无新增内容")
                return
            
            print(f"[文件监控] 新增 {len(new_lines)} 行")
            
            # 按5秒时间窗口合并消息
            merged_messages = self.merge_messages_by_time_window(new_lines, len(imported_set))
            print(f"[文件监控] 合并为 {len(merged_messages)} 条消息")
            
            # 更新已导入的行记录（添加所有当前行，包括可能的手动修改）
            self.file_monitor_last_lines = current_lines.copy()
            
            if merged_messages:
                # 将新消息追加到当前会话
                self.append_external_messages(merged_messages)
                self.status_var.set(f"从外部文件导入 {len(merged_messages)} 条消息 (原始{len(new_lines)}行，共{len(current_lines)}行)")
                print(f"[文件监控] 导入完成")
            
        except Exception as e:
            print(f"[文件监控] 读取文件失败: {e}")
            import traceback
            traceback.print_exc()
    
    def merge_messages_by_time_window(self, lines, start_index=0, window_seconds=5):
        """双5秒合并策略：本地5秒+时间戳5秒，去除重复内容
        
        合并规则：
        1. 去重：基于内容（去掉时间戳后）去重
        2. 双5秒：满足任一条件即合并
           - 本地5秒：相邻行索引差 <= 10（假设每秒2条）
           - 时间戳5秒：时间戳差值 <= 5秒
        3. 上限：每批最多10条
        
        Args:
            lines: 消息行列表
            start_index: 起始行号（用于生成ID）
            window_seconds: 时间窗口大小（秒），默认5
        
        Returns:
            合并后的消息列表
        """
        from datetime import datetime
        import re
        
        if not lines:
            return []
        
        # 解析每行的时间戳和内容
        parsed_lines = []
        for i, line in enumerate(lines):
            timestamp = self._extract_timestamp(line)
            content = self.remove_timestamp(line)
            parsed_lines.append({
                'original': line,
                'timestamp': timestamp,
                'content': content,
                'index': i
            })
        
        # 去重：基于内容（去掉时间戳后）
        seen_contents = set()
        unique_lines = []
        for pl in parsed_lines:
            content_key = pl['content'].strip()
            if content_key and content_key not in seen_contents:
                seen_contents.add(content_key)
                unique_lines.append(pl)
        
        if not unique_lines:
            return []
        
        # 如果只有一行，直接返回
        if len(unique_lines) == 1:
            return [self.wrap_external_message(unique_lines[0]['original'], start_index)]
        
        # 双5秒合并策略
        merged = []
        current_batch = [unique_lines[0]]
        current_start_idx = start_index
        
        for i in range(1, len(unique_lines)):
            current_line = unique_lines[i]
            first_line = current_batch[0]
            
            # 双5秒判断
            local_window_ok = False  # 本地5秒（基于索引）
            timestamp_window_ok = False  # 时间戳5秒
            
            # 本地5秒：索引差 <= 10（假设每秒2条，5秒=10条）
            index_diff = current_line['index'] - first_line['index']
            local_window_ok = (index_diff <= 10)
            
            # 时间戳5秒
            if first_line['timestamp'] and current_line['timestamp']:
                time_diff = (current_line['timestamp'] - first_line['timestamp']).total_seconds()
                timestamp_window_ok = (time_diff <= window_seconds)
            
            # 双5秒：满足任一条件即可合并
            should_merge = local_window_ok or timestamp_window_ok
            
            # 如果在任一窗口内且批次未满10条，加入当前批次
            if should_merge and len(current_batch) < 10:
                current_batch.append(current_line)
            else:
                # 合并当前批次
                merged_content = "\n".join([cl['original'] for cl in current_batch])
                merged_msg = self.wrap_external_message(merged_content, current_start_idx)
                merged.append(merged_msg)
                
                # 开始新批次
                current_batch = [current_line]
                current_start_idx = start_index + current_line['index']
        
        # 处理最后一批
        if current_batch:
            merged_content = "\n".join([cl['original'] for cl in current_batch])
            merged_msg = self.wrap_external_message(merged_content, current_start_idx)
            merged.append(merged_msg)
        
        return merged
    
    def _extract_timestamp(self, line):
        """从行中提取时间戳"""
        from datetime import datetime
        import re
        
        patterns = [
            r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)',
            r'\[(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)[^\]]*\]',
            r'm:\[(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)[^\]]*\]',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                ts_str = match.group(1)
                try:
                    return datetime.fromisoformat(ts_str.replace('Z', '+00:00').replace(' ', 'T'))
                except:
                    try:
                        return datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                    except:
                        pass
        return None
    
    def remove_timestamp(self, line):
        """移除行中的时间戳，只保留内容
        
        支持的时间戳格式：
        - 2024-01-01 12:00:00.123
        - 2024-01-01T12:00:00.123
        - [2024-01-01 12:00:00]
        - m:[2024-01-01 12:00:00]
        """
        import re
        
        # 匹配常见时间戳格式
        patterns = [
            r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?\s*',  # 2024-01-01 12:00:00.123
            r'^\[\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?\]\s*',  # [2024-01-01 12:00:00]
            r'^m:\[\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?[^\]]*\]\s*',  # m:[2024-01-01 12:00:00 GMT+8]
        ]
        
        for pattern in patterns:
            line = re.sub(pattern, '', line)
        
        return line.strip()
    
    def parse_external_file(self, content):
        """解析外部文件内容，返回消息列表
        
        外部文件格式规范：
        - 纯文本格式，每行一条消息
        - 不需要JSON格式，直接写入文本内容即可
        - 示例：
          2024-01-01 12:00:00.123 系统启动
          2024-01-01 12:00:01.456 检测到新连接
          2024-01-01 12:00:02.789 数据处理完成
        
        返回的消息：
        - role 统一为 'toolResult'
        - id 基于毫秒级时间戳+行号
        """
        messages = []
        
        lines = content.strip().split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # 纯文本直接包装，role固定为toolResult
            messages.append(self.wrap_external_message(line, i))
        
        return messages
    
    def wrap_external_message(self, data, line_index=0):
        """将外部数据包装成标准message格式（外部文件保持toolResult）
        
        Args:
            data: 可以是字符串或字典
            line_index: 行号，用于生成唯一ID
        """
        from datetime import datetime
        
        if isinstance(data, dict):
            content = data.get('content', data.get('text', str(data)))
            role = data.get('role', 'toolResult')  # 外部文件保持toolResult
        else:
            content = str(data)
            role = 'toolResult'  # 外部文件保持toolResult
        
        # 使用简洁的ID格式：extern + 序号
        msg_id = f"extern{line_index:04d}"
        
        return {
            "type": "message",
            "id": msg_id,
            "timestamp": datetime.now().isoformat() + "Z",
            "message": {
                "role": role,
                "content": [{"type": "text", "text": content}]
            }
        }
    
    def get_message_hash(self, msg):
        """获取消息的内容哈希（用于去重）"""
        try:
            content = ""
            if 'message' in msg:
                msg_data = msg['message']
                if 'content' in msg_data:
                    for item in msg_data['content']:
                        if isinstance(item, dict) and 'text' in item:
                            content += item['text']
            # 取前100个字符的哈希
            content = content[:100]
            import hashlib
            return hashlib.md5(content.encode()).hexdigest()
        except:
            return str(msg)
    
    def append_external_messages(self, messages):
        """将外部消息追加到当前会话"""
        print(f"[文件监控] append_external_messages 被调用，消息数: {len(messages)}")
        
        if not self.current_jsonl_path:
            print("[文件监控] 错误: current_jsonl_path 为空")
            return
        
        print(f"[文件监控] 目标文件: {self.current_jsonl_path}")
        
        try:
            # 读取现有内容
            existing_lines = []
            if self.current_jsonl_path.exists():
                with open(self.current_jsonl_path, 'r', encoding='utf-8', errors='ignore') as f:
                    existing_lines = f.readlines()
                print(f"[文件监控] 现有文件行数: {len(existing_lines)}")
            else:
                print(f"[文件监控] 目标文件不存在，将创建新文件")
            
            # 找到最后一条消息的parentId
            last_parent_id = None
            for line in reversed(existing_lines):
                try:
                    data = json.loads(line.strip())
                    if data.get('type') == 'message':
                        last_parent_id = data.get('id')
                        break
                except:
                    pass
            
            print(f"[文件监控] 最后一条消息ID: {last_parent_id}")
            
            # 追加新消息
            new_lines = existing_lines.copy()
            for i, msg in enumerate(messages):
                if i == 0 and last_parent_id:
                    msg['parentId'] = last_parent_id
                msg_line = json.dumps(msg, ensure_ascii=False) + "\n"
                new_lines.append(msg_line)
                print(f"[文件监控] 追加消息 {i+1}: id={msg.get('id')}, parentId={msg.get('parentId')}")
            
            # 保存
            print(f"[文件监控] 写入文件，总行数: {len(new_lines)}")
            with open(self.current_jsonl_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            print("[文件监控] 文件写入完成")
            
            # 更新内存中的数据
            self.all_lines = new_lines
            
            # 刷新显示
            print("[文件监控] 刷新UI显示")
            self.refresh_current()
            self.load_history()
            print("[文件监控] 导入完成")
            
        except Exception as e:
            print(f"[文件监控] 追加外部消息失败: {e}")
            import traceback
            traceback.print_exc()

def main():
    root = tk.Tk()
    app = TokenViewerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
