# ============================================================
# CodeNova Frontend Dockerfile
# Node 20 + Vite + React + TypeScript
# ============================================================
FROM node:20-alpine

WORKDIR /app

# 仅先拷贝依赖清单以利用缓存
COPY package.json package-lock.json* ./

RUN npm install --registry https://registry.npmmirror.com

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
