# ============================================================
# CodeNova Backend Dockerfile
# Python 3.11 + FastAPI + Tree-sitter
# ============================================================
FROM python:3.11-slim AS base

# 系统依赖：git（克隆仓库）、build-essential（语言包编译兜底）、libpq（postgres）
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        libpq-dev \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 升级 pip 并安装依赖（利用缓存层）；使用国内镜像加速
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 源码挂载（开发模式由 compose volume 覆盖）
# 注：tree-sitter 语言包提供预编译 wheel，语言预热在运行时由 app.bootstrap 完成
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
