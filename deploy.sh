#!/bin/bash
# 服务器端部署脚本 — 在远程服务器上执行
# 本地使用: ssh polysport 'cd ~/PolySport && bash deploy.sh [--backend|--frontend|--full]'
set -e

cd "$(dirname "$0")"

# 确保 uv 在 PATH 中（非交互式 SSH 不加载 ~/.bashrc）
export PATH="$HOME/.local/bin:$PATH"

MODE="${1:---full}"

echo "==> Pulling latest code..."
git pull

echo "==> Starting DB services..."
sudo docker compose up -d

if [[ "$MODE" == "--full" || "$MODE" == "--backend" ]]; then
    echo "==> Installing backend deps..."
    cd backend && uv sync --frozen && cd ..

    echo "==> Restarting backend..."
    sudo systemctl restart polysport
    echo "==> Backend status:"
    sudo systemctl status polysport --no-pager -l | head -8
fi

if [[ "$MODE" == "--full" || "$MODE" == "--frontend" ]]; then
    echo "==> Building frontend..."
    cd frontend && npm ci && npm run build && cd ..

    echo "==> Prerendering pages for SEO..."
    node scripts/prerender.mjs || echo "WARNING: Prerender failed, continuing without prerendered pages"

    echo "==> Deploying frontend static files..."
    sudo rm -rf /var/www/polysport
    sudo cp -r frontend/dist /var/www/polysport

    echo "==> Reloading Nginx..."
    sudo nginx -t && sudo systemctl reload nginx
fi

echo "==> Done! (mode: $MODE)"
