FROM python:3.11-slim-bookworm

WORKDIR /app

# Install Chromium system dependencies manually (avoid playwright's broken --with-deps on Debian Trixie)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libxshmfence1 libx11-xcb1 libxcb1 libxfixes3 \
    libxext6 libx11-6 libxcb-shm0 libxcb-render0 libxcb-shape0 \
    libgtk-3-0 libgdk-pixbuf2.0-0 libpangocairo-1.0-0 libcairo-gobject2 \
    libglib2.0-0 libdbus-1-3 libatspi2.0-0 \
    fonts-liberation fonts-noto-color-emoji ca-certificates wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY . .

EXPOSE 8081

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
