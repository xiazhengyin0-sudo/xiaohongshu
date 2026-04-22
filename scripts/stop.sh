#!/bin/bash

echo "🛑 停止小红书自动化运营系统..."

cd /workspace/xhs-auto-agent

docker compose down

echo "✅ 服务已停止"
