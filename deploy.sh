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
PORT="${PORT:-3000}"
ENABLE_REGISTRAR="${ENABLE_REGISTRAR:-true}"
PROXY="${REGISTRATION_PROXY:-}"
DATA_DIR="$(pwd)/newapi-data"
REPO_URL="https://github.com/FuHesummer/newapi_Summer.git"
REPO_BRANCH="${REPO_BRANCH:-test}"
REPO_DIR="$(pwd)/newapi-source"

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

  # 始终从 GitHub 同步最新注册机源码
  if [ -d "$REPO_DIR/.git" ]; then
    # 已有仓库，拉取最新
    info "同步注册机源码 (git pull)..."
    cd "$REPO_DIR"
    git fetch origin "$REPO_BRANCH" 2>/dev/null || true
    git checkout "$REPO_BRANCH" 2>/dev/null || true
    git reset --hard "origin/$REPO_BRANCH" 2>/dev/null || true
    cd - > /dev/null
    info "注册机源码已同步到最新 ($REPO_BRANCH 分支)"
  else
    # 首次部署：从 GitHub 克隆
    info "首次部署，从 GitHub 克隆注册机源码..."
    rm -rf "$REPO_DIR"
    git clone --branch "$REPO_BRANCH" --depth 1 "$REPO_URL" "$REPO_DIR" || error "克隆仓库失败"
    info "注册机源码克隆完成"
  fi

  # 使用同步后的源码目录
  if [ -d "$REPO_DIR/registrar" ] && [ -f "$REPO_DIR/registrar/Dockerfile" ]; then
    REGISTRAR_DIR="$REPO_DIR/registrar"
  else
    warn "GitHub 仓库中未找到 registrar/Dockerfile，检查本地目录..."
    if [ -d "./registrar" ] && [ -f "./registrar/Dockerfile" ]; then
      REGISTRAR_DIR="./registrar"
    fi
  fi

  if [ -n "$REGISTRAR_DIR" ]; then
    info "构建注册机镜像 (源码: $REGISTRAR_DIR)..."
    docker build -t registrar:latest "$REGISTRAR_DIR"

    info "启动注册机..."
    # 注意：注册机浏览器（Camoufox）不走代理，直接访问目标网站
    # REGISTRATION_PROXY 环境变量留空即可，Camoufox 不支持 SOCKS 代理
    docker run -d \
      --name registrar \
      -e DUCKMAIL_BASE_URL=https://sfj.blogsummer.cn \
      -e DUCKMAIL_API_KEY=dk_b3932aec8f2e4d8199f963de2091d4c3 \
      -e REGISTRATION_PROXY= \
      -e REGISTER_HEADLESS=true \
      --restart unless-stopped \
      registrar:latest

    REGISTRAR_IP=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' registrar)
    info "注册机已启动 (IP: $REGISTRAR_IP, 地址: http://${REGISTRAR_IP}:8081)"
  else
    warn "未找到 registrar/Dockerfile，跳过注册机部署"
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
  echo "    注意: Camoufox 浏览器不走代理，直接访问目标网站"
fi
echo ""
echo "  容器状态:"
docker ps --format '  {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'new-api|redis|registrar'
echo ""
echo "==========================================="
