#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🛑 停止小红书自动化运营系统..."
docker compose down
echo "✅ 服务已停止"
