# =====================================================================
#  医智助手 · 前端镜像
#  Vue 3 + Vite 构建，产物由 nginx 提供静态文件并反向代理 /api。
# =====================================================================

# ---------- 阶段 1：构建 ----------
FROM node:20-alpine AS build

WORKDIR /app

# 先复制依赖清单，利用 Docker 层缓存，避免源码变更时重复安装依赖
COPY package.json package-lock.json ./
# npm ci 严格按 lockfile 安装，保证可复现构建
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

# ---------- 阶段 2：运行 ----------
FROM nginx:1.25-alpine

# 将构建产物复制到 nginx 站点目录
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
