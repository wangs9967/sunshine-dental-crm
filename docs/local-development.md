# 本地开发与验证

从仓库根目录开始。以下命令使用 PowerShell。准备 Docker Compose v2、Python 3.12、uv、Node.js 22 和微信开发者工具。

## PostgreSQL 16 和 Redis 7

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose --env-file .env -f deploy/docker-compose.dev.yml config --quiet
docker compose --env-file .env -f deploy/docker-compose.dev.yml up -d --wait
docker compose --env-file .env -f deploy/docker-compose.dev.yml ps
```

Compose 和后端共用根目录 `.env` 中的 `POSTGRES_DB`、`POSTGRES_USER` 和 `POSTGRES_PASSWORD`。后端用这组值和 `POSTGRES_HOST`、`POSTGRES_PORT` 组装 PostgreSQL 连接。Redis 使用 `REDIS_HOST`、`REDIS_PORT` 和 `REDIS_DB`。默认数据库和缓存端口仅绑定 `127.0.0.1`。端口冲突时在 `.env` 修改对应端口即可。示例密码只用于本地环境。PostgreSQL 容器的库名和账号在数据卷首次初始化时生效。

## FastAPI

```powershell
Set-Location backend
uv sync --locked --python 3.12 --extra dev
uv run --locked --extra dev python -m app.check_dependencies
uv run --locked --extra dev pytest
uv run --locked --extra dev mypy
uv build --out-dir dist
uv run --locked uvicorn app.main:app --reload --host 127.0.0.1 --port 18081
```

`uv sync` 在 `backend/.venv` 安装锁定依赖。连接检查通过实际 SQL 查询和 Redis `PING` 验证依赖服务。另开终端访问 `http://127.0.0.1:18081/health`，预期返回 `{"status":"ok"}`。该端点验证 FastAPI 进程，外部依赖使用前述连接命令检查。空白本地库的初始化、后续升级与回滚见[数据库迁移说明](database-migrations.md)。

## React 管理后台

从仓库根目录打开另一终端。

```powershell
Set-Location admin-web
npm.cmd ci
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npm.cmd run dev
```

Vite 默认开发地址为 `http://localhost:5173`，生产构建输出到 `admin-web/dist`。

## 微信原生小程序

```powershell
Set-Location miniprogram
npm.cmd ci
npm.cmd run typecheck
if (-not (Test-Path project.config.json)) {
    Copy-Item project.config.example.json project.config.json
}
```

在 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 导入 `miniprogram/`。项目配置已启用 TypeScript 编译。使用工具支持的游客或测试项目模式，可在模拟器检查「阳光口腔」占位首页。使用 TDesign 组件的页面需要先执行开发者工具的「工具 → 构建 npm」。真机预览需要满足微信平台的账号、AppID 和开发权限要求。

## 停止本地依赖

在运行 FastAPI、Vite 的终端按 `Ctrl+C`。回到仓库根目录后执行以下命令，开发数据库数据卷会保留。

```powershell
docker compose --env-file .env -f deploy/docker-compose.dev.yml down
```
