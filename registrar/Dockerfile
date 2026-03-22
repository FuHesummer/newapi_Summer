FROM python:3.11-slim-bookworm

WORKDIR /app

# 使用阿里云 Debian 镜像源加速 apt
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# Camoufox (Firefox-based) system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libxshmfence1 libx11-xcb1 libxcb1 libxfixes3 \
    libxext6 libx11-6 libxcb-shm0 libxcb-render0 libxcb-shape0 \
    libgtk-3-0 libgdk-pixbuf2.0-0 libpangocairo-1.0-0 libcairo-gobject2 \
    libglib2.0-0 libdbus-1-3 libatspi2.0-0 libwayland-client0 \
    fonts-liberation ca-certificates wget \
    && rm -rf /var/lib/apt/lists/*

# 使用清华 PyPI 镜像源加速 pip
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 下载 Camoufox 浏览器（使用 GitHub 代理加速）
COPY fetch_camoufox.py .
RUN python fetch_camoufox.py && rm -f fetch_camoufox.py

COPY . .

EXPOSE 8081

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
