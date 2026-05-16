#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🚀 启动小红书自动化运营系统..."

if [ ! -f "config/.env" ]; then
    echo "📋 创建配置文件..."
    cp config/.env.example config/.env
    echo "⚠️  请编辑 config/.env 文件，填入您的 AI API Key"
fi

mkdir -p data/cookies data/images data/cache
: > data/cookies/.gitkeep
: > data/images/.gitkeep
: > data/cache/.gitkeep

echo "📦 拉取 xiaohongshu-mcp 镜像..."
docker pull xpzouying/xiaohongshu-mcp:latest

echo "🔨 构建服务镜像..."
docker compose build

echo "▶️  启动服务..."
docker compose up -d

sleep 5

echo ""
echo "✅ 服务启动完成！"
echo ""
echo "📍 访问地址:"
echo "   - Web 管理界面: http://localhost:3000"
echo "   - AI 分析引擎: http://localhost:8001/docs"
echo "   - 数据采集服务: http://localhost:8002/docs"
echo "   - 小红书 MCP: http://localhost:18060"
echo ""
echo "📝 下一步:"
echo "   1. 访问 http://localhost:3000"
echo "   2. 在「账号登录」页面扫码登录小红书"
echo "   3. 在 config/.env 中配置 AI API Key 后重启 ai-engine"
echo "   4. 开始使用自动化功能"
