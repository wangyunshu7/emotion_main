# Alibaba Cloud Linux 公网 IP 部署说明（Conda 简化版）

目标：浏览器直接打开 **http://47.245.56.28/** 进入项目。未登录时显示登录页，登录后进入日记首页。

适用 Alibaba Cloud Linux 3.2104，已安装 Conda，有 sudo 权限。本文只包含首次部署和必要排查，无需域名、证书、版本回滚或数据库备份配置。

HTTP 不加密传输密码和日记内容，适合当前演示部署；涉及真实隐私数据时建议使用 HTTPS。

```text
http://47.245.56.28:80 → Nginx
                        ├─ /          React 首页
                        ├─ /api/      FastAPI → 127.0.0.1:8000
                        └─ /health/   健康检查
FastAPI + 后台 worker → PostgreSQL 127.0.0.1:5432
```

## 1. 准备服务器与从 GitHub 拉取代码

在阿里云 ECS 安全组允许入方向 **TCP 80**。保留你使用的 SSH 端口；8000、5432 不需要开放公网。下文命令均在服务器执行。

先用当前有 Conda 的管理员账号执行：

```bash
cat /etc/os-release
conda info --base
sudo dnf install -y git nginx rsync curl ca-certificates vim
id emotion >/dev/null 2>&1 || sudo useradd -m -s /bin/bash emotion
id emotiondb >/dev/null 2>&1 || sudo useradd -m -s /bin/bash emotiondb
sudo install -d -m 0755 /srv/emotion
sudo install -d -o emotion -g emotion -m 0750 /srv/emotion/app /srv/emotion/runtime
sudo install -d -o emotion -g emotion -m 0700 /srv/emotion/runtime/privacy
sudo install -d -o emotiondb -g emotiondb -m 0755 /srv/emotion-db
sudo install -d -o emotiondb -g emotiondb -m 0700 /srv/emotion-db/data /srv/emotion-db/run
sudo install -d -o emotion -g nginx -m 0750 /var/www/emotion
```

先将项目代码提交并推送到自己的 GitHub 仓库。仓库根目录应包含 `backend/`、`frontend/`、`content/`、`scripts/`、`requirements.txt` 和 `.env.example`；不要提交本地 `.env`、`.venv`、`node_modules`、`.runtime`、`.tools`、`dist` 或测试缓存。

从 GitHub 仓库页面的 **Code → HTTPS** 复制地址，替换下方 `https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git`。在服务器管理员账号中执行，以 emotion 用户拉取到前面创建的空目录：

```bash
sudo -u emotion -H git clone --depth 1 https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git /srv/emotion/app
sudo -u emotion -H ls -la /srv/emotion/app
```

公开仓库通常无需登录。私有仓库如提示认证，Username 填 GitHub 用户名，Password 填具有该仓库读取权限的 Personal Access Token（不是 GitHub 登录密码）；不要将 Token 写入克隆地址或文档。

`/srv/emotion/app` 必须为空才能执行 clone；若其中已存在文件，先检查目录内容，不要直接删除。已有正确的 Git 仓库时无需再次克隆。克隆后应能看到 `/srv/emotion/app/backend`，然后继续第 2 节安装环境。

## 2. 准备 Conda 环境和数据库

继续在能使用 Conda 的管理员账号中执行，自动获取 Conda 路径：

```bash
EMOTION_CONDA_BASE=$(conda info --base)
conda env list
```

### 2.1 准备应用环境（二选一）

**已有 emotion 环境且已安装 requirements：** 克隆已有环境到服务目录，复用已安装的 Python 包，不重复执行 pip install。源环境保持原样。自动定位环境，不要求 Conda 必须安装在特定位置：

```bash
EMOTION_SOURCE_ENV=$(conda run -n emotion python -c 'import sys; print(sys.prefix)')
sudo "$EMOTION_CONDA_BASE/bin/conda" create -p /srv/emotion/env --clone "$EMOTION_SOURCE_ENV" -y
```

如果源环境位于 `/root/miniconda3/envs/emotion` 等 root 私有目录，普通服务用户无法直接访问，不能只把 systemd 的 Python 路径改到该目录。克隆后仍使用后文统一的 `/srv/emotion/env` 路径，无需开放 `/root` 权限或让应用以 root 运行。若 `/srv/emotion/env` 已经是准备好的环境，跳过克隆。

**尚未准备应用环境：** 只在没有可复用环境时执行以下命令，已有环境者跳过此代码块：

```bash
sudo "$EMOTION_CONDA_BASE/bin/conda" create -p /srv/emotion/env --override-channels -c conda-forge python=3.12 pip -y
sudo /srv/emotion/env/bin/python -m pip install -r /srv/emotion/app/requirements.txt
```

两种方式完成后，都检查 Python 版本和依赖，并准备前端构建所需的 Node.js：

```bash
sudo -u emotion /srv/emotion/env/bin/python -c 'import sys; print(sys.version); assert sys.version_info >= (3, 12), "Python 3.12+ required"'
sudo -u emotion /srv/emotion/env/bin/python -m pip check
sudo "$EMOTION_CONDA_BASE/bin/conda" install -p /srv/emotion/env --override-channels -c conda-forge nodejs=22 -y
/srv/emotion/env/bin/node --version
```

若版本检查失败，应先将应用环境升级到 Python 3.12 并重新核对项目依赖，再继续部署。如果已有兼容的 Node.js 22.12+，可跳过 Node.js 安装命令。

### 2.2 准备独立数据库环境

PostgreSQL 与 Python 应用环境分开。已安装应用 requirements 不代表已安装 PostgreSQL 服务端；首次部署执行：

```bash
sudo "$EMOTION_CONDA_BASE/bin/conda" create -p /srv/emotion-db/env --override-channels -c conda-forge postgresql=16 -y
```

若这个数据库环境已准备好，跳过创建命令。

仅对首次部署的空数据目录执行一次初始化。Unix socket 使用本机 peer 认证，TCP 连接使用密码：

```bash
sudo -u emotiondb /srv/emotion-db/env/bin/initdb -D /srv/emotion-db/data -U emotiondb --encoding=UTF8 --locale=C --auth-local=peer --auth-host=scram-sha-256
sudo -u emotiondb tee -a /srv/emotion-db/data/postgresql.conf >/dev/null <<'CONF'
listen_addresses = '127.0.0.1'
port = 5432
unix_socket_directories = '/srv/emotion-db/run'
password_encryption = 'scram-sha-256'
CONF
```

创建数据库服务并连接数据库：

```bash
sudo tee /etc/systemd/system/emotion-postgres.service >/dev/null <<'UNIT'
[Unit]
Description=Emotion PostgreSQL
After=network.target

[Service]
User=emotiondb
Group=emotiondb
ExecStart=/srv/emotion-db/env/bin/postgres -D /srv/emotion-db/data
KillSignal=SIGINT
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now emotion-postgres
sudo -u emotiondb /srv/emotion-db/env/bin/psql -h /srv/emotion-db/run -U emotiondb -d postgres
```

在 PostgreSQL 提示符中逐行执行：

```sql
CREATE ROLE emotion_app LOGIN;
\password emotion_app
CREATE DATABASE emotion OWNER emotion_app;
\q
```

`\password` 要求输入两遍数据库密码，自己设置并记住。为简化连接地址填写，可使用至少 24 位大小写字母和数字的随机密码。

## 3. 配置后端并构建前端

切换到应用用户：

```bash
sudo -iu emotion
export PATH=/srv/emotion/env/bin:$PATH
cd /srv/emotion/app
python scripts/setup.py
chmod 600 .env
vim .env
```

在生成的 `.env` 中修改或补充以下配置。**将 YOUR_DATABASE_PASSWORD 替换为第 2 步设置的密码**；保留自动生成的 `SESSION_TOKEN_PEPPER` 和 `PRIVACY_LEDGER_KEY`，不要改成示例文字：

```dotenv
APP_ENV=production
APP_BASE_URL=http://47.245.56.28
ALLOWED_ORIGINS=http://47.245.56.28
COOKIE_SECURE=false
ALLOW_INSECURE_HTTP=true
DATABASE_URL=postgresql+psycopg://emotion_app:YOUR_DATABASE_PASSWORD@127.0.0.1:5432/emotion
PRIVACY_LEDGER_ROOT=/srv/emotion/runtime/privacy
AI_ENABLED=false
AI_PROVIDER=disabled
```

地址不加结尾斜杠。HTTP 部署必须同时设置 `ALLOW_INSECURE_HTTP=true` 和 `COOKIE_SECURE=false`，否则生产校验或登录 Cookie 会失败。数据库密码含 `@`、`:`、`/` 等特殊字符时，需先进行 URL 编码再写入连接地址。

运行迁移并构建前端，完成后返回管理员账号：

```bash
cd /srv/emotion/app/backend
python -m alembic upgrade head
cd /srv/emotion/app/frontend
npm ci
npm run build
rsync -a dist/ /var/www/emotion/
exit
```

前端默认请求同站点 `/api/v1`，无需配置为 `localhost:8000`。若服务器上存在 `frontend/.env*` 中的旧 `VITE_API_BASE_URL`，请删除该项再构建。

管理员设置静态文件权限：

```bash
sudo chown -R emotion:nginx /var/www/emotion
sudo find /var/www/emotion -type d -exec chmod 750 {} \;
sudo find /var/www/emotion -type f -exec chmod 640 {} \;
```

## 4. 启动 API 和后台 worker

管理员执行以下命令。systemd 直接使用 Conda 环境内的 Python，无需开机时执行 conda activate：

```bash
sudo tee /etc/systemd/system/emotion-api.service >/dev/null <<'UNIT'
[Unit]
Description=Emotion API
After=network.target emotion-postgres.service
Requires=emotion-postgres.service

[Service]
User=emotion
Group=emotion
WorkingDirectory=/srv/emotion/app/backend
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
UMask=0077
ExecStart=/srv/emotion/env/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1 --no-access-log
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

sudo tee /etc/systemd/system/emotion-worker.service >/dev/null <<'UNIT'
[Unit]
Description=Emotion background worker
After=network.target emotion-postgres.service
Requires=emotion-postgres.service

[Service]
User=emotion
Group=emotion
WorkingDirectory=/srv/emotion/app/backend
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
UMask=0077
ExecStart=/srv/emotion/env/bin/python -m app.jobs.runner
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now emotion-api emotion-worker
curl -f http://127.0.0.1:8000/health/ready
```

正常返回 `{"status":"ready"}`。应用自动从项目根目录 `.env` 读取配置。

## 5. 配置 Nginx，将 IP 根路径作为项目入口

管理员执行：

```bash
sudo tee /etc/nginx/conf.d/emotion.conf >/dev/null <<'NGINX'
server {
    listen 80;
    server_name 47.245.56.28;
    root /var/www/emotion;
    index index.html;
    client_max_body_size 1m;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    location /health/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    location /assets/ {
        try_files $uri =404;
        expires 7d;
    }

    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";
    }
}
NGINX
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
```

`server_name` 精确匹配公网 IP，所以访问 `http://47.245.56.28/` 会进入项目。`proxy_pass` 地址末尾不要加 `/`，否则会丢失接口路径中的 `/api/`。SPA 回退配置支持在日记详情页刷新。

### 仅在防火墙或 SELinux 已启用时处理

```bash
sudo firewall-cmd --state
getenforce
```

若 firewalld 输出 `running`，用 `sudo firewall-cmd --get-active-zones` 查看公网网卡所在区域。假设为 public，执行（不同则替换 public）：

```bash
sudo firewall-cmd --zone=public --permanent --add-service=http
sudo firewall-cmd --reload
```

命令不存在或防火墙未运行时跳过这两条防火墙配置命令。若 SELinux 输出 `Enforcing` 或 `Permissive`，执行：

```bash
sudo dnf install -y policycoreutils-python-utils
sudo semanage fcontext -a -t httpd_sys_content_t '/var/www/emotion(/.*)?'
sudo restorecon -Rv /var/www/emotion
sudo setsebool -P httpd_can_network_connect 1
```

## 6. 验证访问与必要排查

服务器执行：

```bash
sudo systemctl is-active emotion-postgres emotion-api emotion-worker nginx
curl -I -H 'Host: 47.245.56.28' http://127.0.0.1/
curl -f -H 'Host: 47.245.56.28' http://127.0.0.1/health/ready
```

随后在自己的电脑打开 **http://47.245.56.28/**，注册账号，登录、新建日记、保存并刷新，确认内容仍然存在。无需加 `/frontend` 或 `:8000`。

本方案默认关闭外部 AI，日记和基础统计可用；需要 AI 分析时，另行填写根目录 `.env.example` 中的真实供应商、模型、密钥、定价和预算配置，再重启 API 与 worker。生产环境禁止 fake provider 和演示账号种子；关怀活动按第 7 节批量导入后即可展示。

| 现象 | 检查方法 |
|---|---|
| 连接超时 | ECS 安全组 TCP 80、系统防火墙、Nginx 是否运行 |
| Nginx 欢迎页 | 确认 emotion.conf 已加载并重启 Nginx，检查是否有其他站点重复配置了 server_name 47.245.56.28 |
| 403 | 静态目录权限、index.html 是否存在、SELinux 文件标签 |
| 502 | API 服务及本机健康检查；SELinux 启用时确认允许网络代理连接 |
| 注册或保存返回 403 | ALLOWED_ORIGINS 必须是 http://47.245.56.28，修改后重启应用 |
| 登录后仍回登录页 | COOKIE_SECURE=false，清除旧 Cookie 后用 http 地址重试 |
| API 无法启动 | 数据库密码和迁移结果、自动生成的密钥、ALLOW_INSECURE_HTTP=true |

日志及重启命令：

```bash
sudo journalctl -u emotion-api -u emotion-worker -u emotion-postgres -n 80 --no-pager
sudo tail -n 50 /var/log/nginx/error.log
sudo systemctl restart emotion-api emotion-worker
```

## 7. 关怀活动库为空时的检查与导入

活动库不依赖 AI 开关，也无需用户授权 AI。页面只展示数据库中 `status=published` 且 `review_due_at` 晚于当前时间的活动。GitHub 拉取的 JSON 文件不会自动入库，需要执行下面的导入命令。

仓库内置 25 项完整的原创文字活动，五个类别各 5 项，已经批量设置为 published，无需逐项填写。文件仍为 `content/activities/drafts.json`，保留历史文件名和 slug，以兼容先前导入的草稿。内容已补充实际步骤、适用提示和来源说明；审核信息如实记录为 AI 辅助整理与自动结构校验，不代表人工或专业心理审核。复核期限为本次整理后 180 天，过期后将隐藏。

数据库迁移完成后，在服务器检查活动数量（只读，不修改数据）：

```bash
cd /srv/emotion/app/backend
sudo -u emotion /srv/emotion/env/bin/python - <<'PY'
from sqlalchemy import func, select
from app.db import SessionLocal, now
from app.models import Activity

with SessionLocal() as db:
    counts = db.execute(select(Activity.status, func.count()).group_by(Activity.status)).all()
    visible = db.scalar(select(func.count()).select_from(Activity).where(
        Activity.status == 'published', Activity.review_due_at > now()
    ))
    print('Counts by status:', dict(counts))
    print('Visible activities:', visible)
PY
```

`Counts by status: {}` 表示未入库；只有 draft 表示尚未发布；published 非零但 Visible 为 0 时，检查复核期限。Visible 大于 0 但页面为空时，清除页面类型筛选，并检查浏览器 `/api/v1/activities` 请求的状态码及响应。

确认服务器已经同步更新后的 `/srv/emotion/app/content/activities/drafts.json`；新文件中每项有完整步骤，status 均为 published。若仍显示 draft，说明服务器拿到的是旧文件，先从已推送最新改动的 GitHub 仓库同步代码，或直接上传本地更新后的同名文件覆盖。不要在 activities 目录中另存一份相同 slug 的 JSON，否则会触发重复数据校验。音乐类提供使用用户已有合法音源的文字指引，不内置音频。

先校验内容，成功后再导入：

```bash
cd /srv/emotion/app/backend
sudo -u emotion /srv/emotion/env/bin/python -m app.cli.import_content --path /srv/emotion/app/content --validate-only
sudo -u emotion /srv/emotion/env/bin/python -m app.cli.import_content --path /srv/emotion/app/content
```

成功导入后，重新运行上面的只读检查，页面可见数量应为 25。刷新活动库即可，无需重启服务或重新构建前端。相同文件重复导入不会增加重复记录；先前已入库的同 slug 草稿会更新为发布状态。已发布内容不能原地改写，后续修改时使用新的版本 slug 并归档旧版本；若曾手动发布过同 slug 的其他内容，导入器会报版本冲突，此时按新版本规则处理，不直接覆盖。不要用 `seed --demo` 初始化生产活动库，该命令仅供本地 development/test 联调。

本文已按项目代码整理，尚未连接你的 ECS 实际执行。

参考：[Alibaba Cloud Linux 官方介绍](https://www.alibabacloud.com/help/en/ecs/user-guide/alibaba-cloud-linux)、[PostgreSQL initdb](https://www.postgresql.org/docs/16/app-initdb.html)。项目已补充 HTTP 请求编号生成兼容，浏览器限制参见 [MDN randomUUID](https://developer.mozilla.org/en-US/docs/Web/API/Crypto/randomUUID) 与 [getRandomValues](https://developer.mozilla.org/en-US/docs/Web/API/Crypto/getRandomValues)。
