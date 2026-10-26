# 心晴日记 · 情绪记录与自我关怀

基于 [项目计划](项目计划.md) 与 [开发文档](开发文档/README.md) 实现的 FastAPI + React 项目。

已提供账号与私密会话、情绪日记、日期与标签筛选、情绪统计、AI 分析与纠正、持久化 worker、规则关怀推荐、活动计时反馈、周回顾、导出与注销，以及数据库迁移、测试和部署配置。

## 目录

```text
backend/              FastAPI、SQLAlchemy、Alembic、任务与测试
frontend/             React、TypeScript、Vite、页面与浏览器测试
content/              25 项未审核活动草稿
infra/                Docker Compose、镜像、Nginx
scripts/              环境初始化、联动启动、类型导出等工具
requirements.txt      根目录 pip 安装入口
backend/requirements.txt  完整、固定版本的 Python 运行依赖
开发文档/             产品与开发契约
```

## 本地启动（Windows PowerShell）

Alibaba Cloud Linux 3.2104 服务器使用 Conda 时，参见 [公网 IP 部署说明（Conda）](Linux部署说明-Conda.md)。已按 `http://47.245.56.28/` 直接访问配置，包含 PostgreSQL、systemd 和 Nginx 的首次部署步骤。

需要 Python 3.12、Node.js 22.12+ 或兼容版本、PostgreSQL 16+。以下命令从仓库根目录开始。

### 1. 安装 Python 依赖并创建私有配置

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r requirements.txt
python scripts/setup.py
```

`setup.py` 只在 `.env` 不存在时生成配置及随机会话／隐私事件加密密钥。已有 `.env` 不会被覆盖。编辑 `DATABASE_URL` 指向自己的数据库，确保数据库已创建。不要提交 `.env`。

已安装 uv 时可替代上述安装：

```powershell
cd backend
uv sync --locked
cd ..
```

本次工作区已准备 Python 虚拟环境及位于 127.0.0.1:55432 的临时开发 PostgreSQL，私有 `.env` 指向该实例；它不是系统数据库服务。重启电脑后可运行 `scripts/local_postgres.ps1 -Action Start` 恢复。其它环境可使用本地 PostgreSQL，或运行：

```powershell
docker compose -f infra/compose.dev.yml up -d db
```

Docker 开发数据库默认 5432 端口；如改用它，需要同步修改 `.env` 中的 `DATABASE_URL`。

### 2. 迁移并启动 API 与 worker

```powershell
cd backend
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe ../scripts/dev_backend.py
```

启动器同时运行 API 与 worker，Ctrl+C 停止二者。单独运行方式：

```powershell
# 终端一，backend 目录
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
# 终端二，backend 目录
.venv/Scripts/python.exe -m app.jobs.runner
```

接口文档：http://127.0.0.1:8000/docs；健康检查：http://127.0.0.1:8000/health/ready。

### 3. 启动前端

在新终端执行：

```powershell
cd frontend
npm ci
npm run dev
```

访问 http://localhost:5173，自行注册账号。前端通过 Vite 代理访问 `/api/v1`，不需要手工填写 Cookie 或 CSRF。

### 4. 可选开发演示资料

在 backend 目录执行：

```powershell
.venv/Scripts/python.exe -m app.cli.seed --demo
```

脚本创建虚构演示账号与 7 天日记，并在本地终端显示生成的演示密码；已有账号不会覆盖。也会创建 3 项明确标记“开发演示”的文字活动，仅允许 development/test。不提供默认生产账号。

正式活动草稿校验与导入：

```powershell
.venv/Scripts/python.exe -m app.cli.import_content --path ../content --validate-only
.venv/Scripts/python.exe -m app.cli.import_content --path ../content
```

25 项草稿默认不公开；完善步骤、核查来源授权并填写真实审核信息后才可发布。`support/` 可放置符合 SupportImport 的地区资源 JSON，未经核验不填写号码。

## AI 模式

- 默认 `AI_ENABLED=false`、`AI_PROVIDER=disabled`：日记、图表、规则推荐与基础周回顾可用。
- 本地联调：设置 `AI_ENABLED=true`、`AI_PROVIDER=fake` 并重启 API/worker；在用户设置中单独授权。结果明确标注“开发模拟”，不会调用外部模型。
- 真实服务：`AI_PROVIDER=openai_compatible`，配置 HTTPS `AI_BASE_URL`（一般以 `/v1` 结尾）、密钥、模型、输入输出价格、币种和正数日预算。Adapter 调用 `/chat/completions`，要求供应商支持 JSON 输出。需核查实际数据保留条款并填写 `AI_POLICY_DESCRIPTION`。

密钥只在后端；未授权不发送日记。模型输出不是诊断。真实服务兼容性和输出质量须用实际凭据评估，本次未调用付费模型。

## 检查与测试

Python 开发依赖：

使用 `uv sync --locked` 已包含开发依赖，无需再使用 pip 重复安装，可直接运行 `uv run pytest` 等命令。以下 pip 命令适用于标准 venv 安装方式。

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
```

创建独立的 `emotion_test` 数据库，再执行；测试会清空该测试库的业务表，不使用正式数据库。

```powershell
cd backend
$env:TEST_DATABASE_URL = 'postgresql+psycopg://emotion:emotion@127.0.0.1:55432/emotion_test'
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
```

前端检查：

```powershell
cd frontend
npm run lint
npm run typecheck
npm run test -- --run
npm run build
npx playwright install chromium
$env:E2E_DATABASE_URL = 'postgresql+psycopg://emotion:emotion@127.0.0.1:55432/emotion_test'
npm run test:e2e
```

浏览器测试使用独立 8001/5174 端口、fake 模型和显式开发 fixture，不要与后端清库测试同时运行。配置地址必须以 `_test` 数据库名结尾。

更改接口后重新生成前端类型：

```powershell
backend/.venv/Scripts/python.exe scripts/export_openapi.py
cd frontend
npm run generate:api
```

## Docker 部署配置

在 `.env` 添加随机 `POSTGRES_PASSWORD`，并将 APP_BASE_URL、ALLOWED_ORIGINS 调整为实际入口地址；本机 Compose 示例入口为 http://localhost:8080。然后：

```powershell
docker compose --env-file .env -f infra/compose.yml up --build -d
```

迁移服务先运行，API、worker 等待迁移完成。生产环境另外设置 `APP_ENV=production`、HTTPS 入口和 `COOKIE_SECURE=true`，由前置 TLS 代理终止 HTTPS。示例 Compose 只绑定本机 8080，不直接发布公网。

容器 API 仅在私有 Compose 网络中由 Nginx 访问；Nginx 覆盖转发 IP，API 信任该内部转发。不要在保留此代理信任配置的同时将 API 端口直接暴露公网。

隐私事件卷与数据库卷独立。恢复备份时应保持服务离线，并重放隐私清单、撤销旧会话：

`scripts/backup.py` 提供经 pg_restore --list 校验的加密备份命令，需要单独设置 BACKUP_ENCRYPTION_KEY，并使用后端虚拟环境执行；密钥与备份分开保管。该脚本不自动恢复数据库，定时执行与恢复演练由部署环境配置。

```powershell
cd backend
.venv/Scripts/python.exe -m app.cli.privacy_replay --after-restore
```

`--after-restore` 会撤销会话与取消旧任务，只应在实际恢复流程中使用。加密密钥必须另行保管，否则无法重放清单。

## 当前交付边界

源代码与本地验证范围见 [代码实现说明](代码实现说明.md)。正式内容审核、真实模型质量评估、真实用户试用、生产 HTTPS 与备份恢复演练尚需在实际部署环境完成；不把开发 fixture 或自动化测试当作这些工作的替代。
