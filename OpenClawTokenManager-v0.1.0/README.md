# OpenClawTokenManager v0.1.0

Kimi Code CLI (OpenClaw) 的 Token 管理工具 - 智能记忆分层压缩

## ✨ 功能特性

- 📊 **实时监控**: Token 使用量、使用率、文件大小实时显示
- 🤖 **AI 辅助压缩**: 支持 Moonshot / Kimi Code API 智能压缩记忆
- 🧠 **记忆分层**: 人设 + 长期 + 中期 + 短期四层记忆结构
- 📁 **智能文件管理**: 自动备份，保留完整历史
- 📡 **外部文件接入**: 支持监控外部日志文件实时导入
- 🎨 **内容分类**: 按角色类型显示不同颜色
- 📱 **紧凑 UI**: 默认 800x500，可调整大小

## 🏗️ 记忆结构

```
[人设/初始化] baizhi00 - 不压缩，完全保留
[长期记忆]    baizhi52 - AI压缩，8000字以内
[中期记忆]    baizhi20 - AI压缩，近期关键信息
[近5条原文]   user/assistant - 完全保留原消息
[模式消息]    baizhi21 - 仅吐槽模式有
```

## 🚀 快速开始

### 环境要求
- Python 3.8+
- requests 库

### 安装
```bash
pip install requests
```

### 启动
双击 `启动Token查看器.bat` 或运行：
```bash
python OpenClawTokenViewer.py
```

## 🔧 API 配置

### Moonshot (按量付费)
- URL: `https://api.moonshot.cn/v1/chat/completions`
- Models: `kimi-k2.5`, `kimi-k2`

### Kimi Code (月付订阅)
- URL: `https://api.kimi.com/coding/v1/chat/completions`
- Models: `kimi-for-coding`, `kimi-k2.5`

## 📖 使用说明

### 基本操作
| 控件 | 操作 |
|------|------|
| 刷新按钮 | 单击=刷新；长按1秒=切换自动刷新 |
| 读取按钮 | 单击=单次读取；长按1秒=切换自动读取 |
| 压缩按钮 | 手动执行 AI 记忆压缩 |
| 历史记录 | Shift/Ctrl 多选，右键删除 |

### 自动压缩
- 条件: Token ≥ 20000 **且** 对话 ≥ 10条
- 避免在 AI 输出期间触发
- 状态显示在底部状态栏

### 文件监控
- 选择外部文件后，自动/手动导入到当前会话
- 5秒内内容合并，自动去重
- 切换会话后自动退回手动模式

## 📁 文件说明

```
OpenClawTokenManager/
├── OpenClawTokenViewer.py    # 主程序（GUI）
├── OpenClawTokenCLI.py       # CLI 工具
├── 启动Token查看器.bat        # Windows 启动脚本
└── README.md                 # 本文件
```

### 配置文件位置
```
~/.openclaw/token_viewer_config.json
```

包含：API 设置、压缩模式、阈值、自动刷新等配置

### 备份位置
```
~/.openclaw/agents/main/sessions/backups/
```

## 🔄 更新日志

### v0.1.0 (2026-02-26)
- ✨ 首个发布版本
- 🧠 四层记忆结构（人设/长期/中期/短期）
- 🤖 支持 Moonshot 和 Kimi Code API
- 📡 外部文件监控接入
- ⚡ 拟合 Token 计算系统
- 🔄 自动压缩策略优化

## 🤝 贡献

欢迎提交 Issue 和 PR！

## 📄 许可证

MIT License

---

*Made with ❤️ for OpenClaw users*
