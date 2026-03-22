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

# Camoufox 从 GitHub Release 下载浏览器二进制，国内服务器需要代理加速
# 通过 ghgo.xyz 或 ghfast.top 代理 GitHub
RUN python -c "
import camoufox.pkgman as pm
import os

# 替换 GitHub URL 为代理 URL
original_webdl = pm.webdl
def patched_webdl(url, **kwargs):
    if 'github.com' in url:
        proxy_url = url.replace('https://github.com', 'https://ghgo.xyz/https://github.com')
        print(f'Using proxy: {proxy_url}')
        try:
            return original_webdl(proxy_url, **kwargs)
        except Exception as e:
            print(f'Proxy failed ({e}), trying ghfast.top...')
            proxy_url2 = url.replace('https://github.com', 'https://ghfast.top/https://github.com')
            try:
                return original_webdl(proxy_url2, **kwargs)
            except Exception:
                print('All proxies failed, trying direct...')
                return original_webdl(url, **kwargs)
    return original_webdl(url, **kwargs)

pm.webdl = patched_webdl
from camoufox.__main__ import CamoufoxUpdate
CamoufoxUpdate().update()
"

COPY . .

EXPOSE 8081

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
