FROM python:3.11

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget tar bash procps \
    libnss3 libatk-bridge2.0-0 libgtk-3-0 libxss1 libasound2 \
    libgbm1 libxshmfence1 libxcomposite1 libxrandr2 \
    libxdamage1 libxfixes3 libxext6 libx11-xcb1 libxkbcommon0 \
    libpango-1.0-0 libcairo2 libatspi2.0-0 libdrm2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
