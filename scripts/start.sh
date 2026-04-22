#!/bin/bash

echo "🚀 启动小红书自动化运营系统..."

cd /workspace/xhs-auto-agent

# 检查 .env 文件
if [ ! -f "config/.env" ]; then
    echo "📋 创建配置文件..."
    cp config/.env.example config/.env
    echo "⚠️  请编辑 config/.env 文件，填入您的 AI API Key"
fi

# 创建数据目录
mkdir -p data/cookies data/images data/cache

# 拉取最新镜像
echo "📦 拉取 xiaohongshu-mcp 镜像..."
docker pull xpzouying/xiaohongshu-mcp:latest

# 构建本地服务
echo "🔨 构建服务镜像..."
docker compose build

# 启动服务
echo "▶️  启动服务..."
docker compose up -d

# 等待服务启动
sleep 5

# 检查服务状态
echo ""
echo "✅ 服务启动完成！"
echo ""
echo "📍 访问地址:"
echo "   - Web 管理界面: http://localhost:3000"
echo "   - AI 分析引擎: http://localhost:8001"
echo "   - 数据采集服务: http://localhost:8002"
echo "   - 小红书 MCP: http://localhost:18060"
echo ""
echo "📝 下一步:"
echo "   1. 访问 http://localhost:3000"
echo "   2. 在「账号登录」页面扫码登录小红书"
echo "   3. 在「AI配置」页面配置 AI API Key"
echo "   4. 开始使用自动化功能"
echo ""
