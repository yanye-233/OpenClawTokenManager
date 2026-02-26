# OpenClawTokenManager v0.1.0 发布说明

## 📦 版本信息
- **版本**: v0.1.0
- **发布日期**: 2026-02-26
- **代号**: Initial Release

## 🎯 项目简介

OpenClawTokenManager 是专为 **Kimi Code CLI (OpenClaw)** 用户打造的 Token 管理工具，帮助用户：
- 实时监控 Token 使用情况
- 智能压缩对话记忆，降低 API 成本
- 管理多层记忆结构，保持对话连贯性

## ✨ 核心功能

### 1. 实时监控
- Token 使用量、使用率实时显示
- 拟合 Token 计算（压缩后 30 秒内使用）
- 官方 Token 数据自动同步

### 2. AI 记忆压缩
- 支持 Moonshot 和 Kimi Code API
- 四层记忆结构：人设 + 长期 + 中期 + 短期
- 正常模式 / 吐槽模式 两种压缩风格

### 3. 自动压缩
- 智能触发条件（Token + 对话数）
- 避免 AI 输出期间干扰
- 状态栏实时显示

### 4. 外部文件接入
- 监控外部日志文件
- 自动导入到当前会话
- 内容合并与去重

## 📁 文件清单

```
KimiTokenManager-v0.1.0/
├── OpenClawTokenViewer.py    # 主程序（GUI，约 132KB）
├── OpenClawTokenCLI.py       # CLI 工具（约 8KB）
├── 启动Token查看器.bat        # Windows 启动脚本
├── README.md                 # 使用说明
└── RELEASE_NOTES.md          # 本文件
```

## 🚀 快速开始

1. 确保已安装 Python 3.8+ 和 requests 库
2. 双击 `启动Token查看器.bat`
3. 在设置中配置 API Key
4. 选择要管理的会话，开始使用

## ⚙️ 系统要求

- Windows 10/11 (Linux/macOS 需手动运行 Python)
- Python 3.8+
- requests 库

## 🔒 隐私说明

- API Key 使用 Base64 编码存储（简单防明文）
- 配置文件存储在用户目录 `~/.openclaw/`
- 所有数据本地处理，不上传至第三方

## 🐛 已知问题

- OpenClaw 更新 Token 有延迟，使用拟合 Token 作为过渡方案
- 首次启动需要手动配置 API Key

## 📋 后续计划

- [ ] 更准确的 Token 计算
- [ ] 多会话同时管理
- [ ] 压缩历史记录查看
- [ ] 更多 API 提供商支持

## 🤝 反馈与支持

如有问题或建议，欢迎通过以下方式反馈：
- GitHub Issues
- 邮件反馈

## 📄 许可证

MIT License

---

**感谢使用 OpenClawTokenManager！**
