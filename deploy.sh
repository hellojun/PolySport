#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "==> Pulling latest code..."
git pull

echo "==> Starting DB services..."
sudo docker compose up -d

echo "==> Installing backend deps..."
cd backend && uv sync --frozen && cd ..

echo "==> Building frontend..."
cd frontend && npm ci && npm run build && cd ..

echo "==> Deploying frontend static files..."
sudo rm -rf /var/www/polysport
sudo cp -r frontend/dist /var/www/polysport

echo "==> Restarting backend..."
sudo systemctl restart polysport

echo "==> Reloading Nginx..."
sudo nginx -t && sudo systemctl reload nginx

echo "==> Done!"
