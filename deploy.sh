#!/bin/bash
# New-API + Registrar 一键部署脚本 (bridge 网络)
# 用法: bash deploy.sh
# 可选环境变量:
#   NEW_API_IMAGE    - new-api 镜像 (默认: ghcr.io/fuhesummer/newapi_summer:test)
#   PORT             - new-api 端口 (默认: 3000)
#   ENABLE_REGISTRAR - 是否启用注册机 (默认: true)

set -e

# ========== 配置 ==========
IMAGE="${NEW_API_IMAGE:-ghcr.io/fuhesummer/newapi_summer:test}"
PORT="${PORT:-50000}"
ENABLE_REGISTRAR="${ENABLE_REGISTRAR:-true}"
PROXY="http://13541996986Tc:@172.17.0.5:2260"
DATA_DIR="$(pwd)/newapi-data"

# ========== 颜色 ==========
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ========== 清理旧容器 ==========
info "清理旧容器..."
docker rm -f new-api redis registrar 2>/dev/null || true

# ========== 创建数据目录 ==========
mkdir -p "$DATA_DIR/data" "$DATA_DIR/logs"

# ========== 拉取镜像 ==========
info "拉取 new-api 镜像: $IMAGE"
docker pull "$IMAGE"

# ========== 启动 Redis ==========
info "启动 Redis..."
docker run -d \
  --name redis \
  --restart always \
  redis:latest

# 获取 Redis 容器 IP
REDIS_IP=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' redis)
info "Redis IP: $REDIS_IP"

# ========== 启动 New-API ==========
info "启动 New-API (端口: $PORT)..."
docker run -d \
  --name new-api \
  -p "${PORT}:50000" \
  -v "$DATA_DIR/data:/data" \
  -v "$DATA_DIR/logs:/app/logs" \
  -e TZ=Asia/Shanghai \
  -e "REDIS_CONN_STRING=redis://${REDIS_IP}:6379" \
  -e BATCH_UPDATE_ENABLED=true \
  -e ERROR_LOG_ENABLED=true \
  --restart always \
  "$IMAGE" \
  --log-dir /app/logs

# ========== 启动注册机 ==========
if [ "$ENABLE_REGISTRAR" = "true" ]; then
  REGISTRAR_DIR=""
  if [ -d "./registrar" ]; then
    REGISTRAR_DIR="./registrar"
  elif [ -d "$(dirname "$0")/registrar" ]; then
    REGISTRAR_DIR="$(dirname "$0")/registrar"
  fi

  if [ -n "$REGISTRAR_DIR" ]; then
    info "构建注册机镜像..."
    docker build -t registrar:latest "$REGISTRAR_DIR"

    info "注册机代理: $PROXY (仅 Playwright 走代理，邮箱 API 直连)"
    info "启动注册机..."
    docker run -d \
      --name registrar \
      -e DUCKMAIL_BASE_URL=https://sfj.blogsummer.cn \
      -e DUCKMAIL_API_KEY=dk_b3932aec8f2e4d8199f963de2091d4c3 \
      -e "REGISTRATION_PROXY=$PROXY" \
      --restart unless-stopped \
      registrar:latest

    REGISTRAR_IP=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' registrar)
    info "注册机已启动 (IP: $REGISTRAR_IP, 地址: http://${REGISTRAR_IP}:8081)"
  else
    warn "未找到 registrar/ 目录，跳过注册机部署"
  fi
else
  info "跳过注册机 (ENABLE_REGISTRAR=false)"
fi

# ========== 等待启动 ==========
info "等待 New-API 启动..."
for i in $(seq 1 30); do
  if curl -s "http://localhost:${PORT}/api/status" | grep -q '"success"' 2>/dev/null; then
    break
  fi
  sleep 1
done

# ========== 获取所有容器 IP ==========
NEWAPI_IP=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' new-api 2>/dev/null || echo "N/A")
REGISTRAR_IP=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' registrar 2>/dev/null || echo "N/A")

# ========== 完成 ==========
echo ""
echo "==========================================="
info "部署完成！"
echo "==========================================="
echo ""
echo "  New-API:    http://localhost:${PORT}"
echo "  数据目录:   $DATA_DIR"
echo ""
echo "  Bridge 网络 IP:"
echo "    new-api:    $NEWAPI_IP"
echo "    redis:      $REDIS_IP"
if [ "$ENABLE_REGISTRAR" = "true" ] && docker ps --format '{{.Names}}' | grep -q registrar; then
  echo "    registrar:  $REGISTRAR_IP"
  echo ""
  echo "  注册机配置:"
  echo "    new-api 中设置 Sidecar URL 为: http://${REGISTRAR_IP}:8081"
  echo "    代理: $PROXY (仅浏览器注册走代理，邮箱API直连)"
fi
echo ""
echo "  容器状态:"
docker ps --format '  {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'new-api|redis|registrar'
echo ""
echo "==========================================="
