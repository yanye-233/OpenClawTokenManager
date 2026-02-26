# OpenClawTokenManager v0.1.0

Kimi Code CLI (OpenClaw) 的 Token 管理工具 - 智能记忆分层压缩

---

## 📖 运行原理

### 问题背景
使用 Kimi Code CLI (OpenClaw) 进行长时间对话时，Token 数量会不断增长（10000 → 60000+），导致：
- API 调用成本增加
- 达到上下文长度限制
- 需要频繁手动 `/compact`

### 解决方案
OpenClawTokenManager 通过 **四层记忆压缩机制**，在保持对话连贯性的同时，显著降低 Token 使用量：

```
原始对话 (60000 tokens)
    ↓ AI 智能压缩
压缩后 (15000 tokens)
    ↓ 保留关键信息
四层记忆结构
```

### 核心机制

| 层级 | 角色 | 处理方式 | 作用 |
|------|------|----------|------|
| **人设层** | baizhi00 | ❌ 不压缩 | 保留系统初始化设定 |
| **长期记忆** | baizhi52 | 🤖 AI压缩 | 历史对话的精简总结 |
| **中期记忆** | baizhi20 | 🤖 AI压缩 | 近期关键信息 |
| **短期记忆** | 最近5条 | ✅ 原文保留 | 保持当前对话连贯 |
| **模式消息** | baizhi21 | 🎭 可选 | 吐槽/正常模式切换 |

**压缩效果**: 60000 tokens → 15000 tokens（约 **75% 减少**）

---

## ✨ 功能特性

### 1. 实时监控 📊
- Token 使用量、使用率实时显示
- 拟合 Token 计算（压缩后 30 秒内使用）
- 官方 Token 数据自动同步
- 文件大小监控

### 2. AI 记忆压缩 🤖
- 支持 **Moonshot** 和 **Kimi Code** API
- 两种压缩模式：正常模式 / 吐槽模式
- 后台线程压缩，不卡 UI
- 自动备份原始文件

### 3. 自动压缩 ⚡
- 智能触发：Token ≥ 20000 **且** 对话 ≥ 10条
- 避免在 AI 输出期间干扰
- 状态栏实时显示压缩状态

### 4. 外部文件接入 📡
- 监控外部日志/文本文件
- 自动导入到当前会话
- 5秒内内容合并，自动去重
- 切换会话后自动退回手动模式

### 5. 历史记录管理 📝
- 可视化浏览对话历史
- Shift/Ctrl 多选删除
- 删除前自动备份
- 按角色类型颜色区分

---

## 🏗️ 记忆结构详解

```
压缩前（原始对话）:
[消息1] user: 你好
[消息2] assistant: 你好！有什么可以帮你的？
[消息3] user: 帮我写个Python脚本
...（几百条消息）
[消息500] assistant: 完成了！
        ↓ AI 压缩后
压缩后（四层结构）:
[baizhi00] 人设/初始化记忆（完全保留）
[baizhi52] 长期记忆：用户需要Python脚本，已完成...
[baizhi20] 中期记忆：具体实现细节...
[消息496] user: 优化一下
[消息497] assistant: 好的
[消息498] user: 再改改
[消息499] assistant: 这样如何
[消息500] assistant: 完成了！
[baizhi21] 吐槽：这需求改得我心累（仅吐槽模式）
```

---

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

---

## 🔧 API 配置

### Moonshot (按量付费)
- URL: `https://api.moonshot.cn/v1/chat/completions`
- Models: `kimi-k2.5`, `kimi-k2`

### Kimi Code (月付订阅)
- URL: `https://api.kimi.com/coding/v1/chat/completions`
- Models: `kimi-for-coding`, `kimi-k2.5`

---

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

---

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

---

## 🔄 更新日志

### v0.1.0 (2026-02-26)
- ✨ 首个发布版本
- 🧠 四层记忆结构（人设/长期/中期/短期）
- 🤖 支持 Moonshot 和 Kimi Code API
- 📡 外部文件监控接入
- ⚡ 拟合 Token 计算系统
- 🔄 自动压缩策略优化

---

## 🗺️ 路线图

- [x] V0.1.0 Token 管理基础功能
- [ ] V2.0 AI女友陪伴阅读器 (OCR + 吐槽框)

---

## 🤝 贡献

欢迎提交 Issue 和 PR！

---

## 📄 许可证

MIT License

---

*Made with ❤️ for OpenClaw users*
