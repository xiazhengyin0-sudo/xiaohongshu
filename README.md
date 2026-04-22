# 小红书自动化运营系统

基于 **xiaohongshu-mcp** 和 **LangChain** 构建的智能内容运营系统，支持全流程自动化操作。

## ✨ 核心特性

### 🤖 多 AI 模型支持
| 提供商 | 模型 | 特点 |
|--------|------|------|
| **智谱AI** | GLM-4 | 国产领先大模型，推理能力强 |
| **通义千问** | Qwen-Max | 阿里云大模型，稳定可靠 |
| **DeepSeek** | DeepSeek-Chat | 性价比高，代码能力强 |
| **Moonshot** | Kimi | 长文本处理优秀 |
| **文心一言** | ERNIE-Bot-4 | 百度大模型，中文理解好 |

### 🔧 核心功能
1. **数据采集** - 通过 xiaohongshu-mcp 采集账号数据、热点话题
2. **风格分析** - AI 分析账号历史内容，提取风格特征
3. **内容生成** - 基于风格自动生成系列内容
4. **自动发布** - 定时发布、批量发布
5. **评论回复** - AI 智能回复用户评论

## 📦 快速开始

### 前置要求
- Docker & Docker Compose
- 小红书账号（已实名认证）
- AI 模型 API Key（任选其一）

### 安装步骤

```bash
# 1. 克隆项目
cd /workspace/xhs-auto-agent

# 2. 配置环境变量
cp config/.env.example config/.env
# 编辑 config/.env，填入您的 AI API Key

# 3. 启动服务
chmod +x scripts/start.sh
./scripts/start.sh
```

### 访问地址
| 服务 | 地址 |
|------|------|
| Web 管理界面 | http://localhost:3000 |
| AI 分析引擎 API | http://localhost:8001/docs |
| 数据采集服务 API | http://localhost:8002/docs |
| 小红书 MCP | http://localhost:18060 |

## 🎯 使用流程

### 1. 登录小红书
```
访问 http://localhost:3000 → 账号登录 → 扫码登录
```

### 2. 配置 AI
```
访问 AI配置 → 选择模型 → 填入 API Key → 保存
```

### 3. 采集数据
```
访问 数据采集 → 开始采集热点话题
```

### 4. 分析账号
```
访问 账号分析 → AI 分析账号风格
```

### 5. 生成内容
```
访问 AI生成 → 输入主题 → 开始生成
```

### 6. 发布内容
```
生成结果 → 点击「发布」或「定时发布」
```

## 🏗️ 项目结构

```
xhs-auto-agent/
├── docker-compose.yml          # Docker 编排配置
├── config/
│   └── .env.example            # 环境变量模板
├── services/
│   ├── ai-engine/              # AI 分析引擎 (LangChain)
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── data-collector/         # 数据采集服务 (MCP)
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── xhs-mcp/               # 小红书 MCP (Docker Hub)
├── web-ui/
│   ├── index.html             # Vue.js 管理界面
│   └── Dockerfile
├── scripts/
│   ├── start.sh               # 启动脚本
│   └── stop.sh                # 停止脚本
└── data/
    ├── cookies/               # 登录凭证存储
    ├── images/                # 图片资源
    └── cache/                 # 数据缓存
```

## 🔌 API 接口

### AI 分析引擎 (Port 8001)

```bash
# 分析内容风格
POST /analyze/style
Body: { "posts": [...], "account_name": "xxx" }

# 生成内容
POST /generate/content
Body: { "topic": "职场成长", "content_type": "series", "series_count": 5 }

# 生成评论回复
POST /generate/reply
Body: { "comment": "...", "post_title": "...", "post_content": "..." }
```

### 数据采集服务 (Port 8002)

```bash
# 检查登录状态
GET /health

# 采集热点话题
POST /collect/hot-topics
Body: { "keywords": ["职场", "穿搭"] }

# 启动定时采集
POST /collect/start-scheduled
```

### 小红书 MCP (Port 18060)

通过 MCP 协议调用，支持以下工具：
- `check_login_status` - 检查登录
- `get_login_qrcode` - 获取登录二维码
- `publish_content` - 发布图文
- `publish_with_video` - 发布视频
- `search_feeds` - 搜索内容
- `get_feed_detail` - 获取帖子详情
- `post_comment_to_feed` - 发表评论
- `like_feed` / `favorite_feed` - 点赞/收藏

## ⚙️ 配置说明

### AI 模型选择

推荐配置：
- **日常使用**: 智谱AI GLM-4 或 通义千问 Qwen-Max
- **低成本**: DeepSeek-Chat
- **长文本**: Moonshot Kimi

### 获取 API Key

| 提供商 | 获取地址 |
|--------|---------|
| 智谱AI | https://open.bigmodel.cn |
| 通义千问 | https://dashscope.console.aliyun.com |
| DeepSeek | https://platform.deepseek.com |
| Moonshot | https://platform.moonshot.cn |
| 文心一言 | https://console.bce.baidu.com |

## ⚠️ 注意事项

1. **账号安全**: 建议使用已实名认证的账号
2. **发布频率**: 每日建议不超过 50 篇
3. **内容审核**: AI 生成内容请审核后再发布
4. **Cookie 过期**: 长时间不登录需重新扫码

## 📄 许可证

MIT License

## 🙏 致谢

- [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) - 小红书 MCP 实现
- [LangChain](https://github.com/langchain-ai/langchain) - AI 应用框架
