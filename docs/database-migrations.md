# V1.0 本地数据库迁移

首版修订为 `0001_frozen_schema`，由 `backend/alembic/versions/` 中的 Python 迁移和冻结 SQL 快照组成。Alembic 连接设置复用根目录 `.env` 的 `POSTGRES_*`，进程环境变量优先。迁移文件随仓库分发，从源代码目录运行。

业务时区为 `BUSINESS_TIMEZONE=Asia/Shanghai`，环境模板与后端默认值一致。数据库时间字段使用 `TIMESTAMPTZ`。迁移不调整 PostgreSQL 系统或会话时区，月限兑继续按业务时区生成 UTC 半开查询区间。 [兑换详细设计](exchange-detailed-design.md)

## 初始化空白本地库

先在根目录按[本地开发说明](local-development.md#postgresql-16-和-redis-7)启动本地 PostgreSQL 16。检查 `.env` 和当前终端是否设置 `POSTGRES_*` 覆盖项，确认连接指向空白本地库。然后执行：

```powershell
Set-Location backend
uv sync --locked --python 3.12 --extra dev
uv run --locked alembic heads
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked alembic check
```

`current` 应显示 `0001_frozen_schema (head)`。18 张业务表之外，Alembic 会创建 `alembic_version` 记录修订。对于已有用 SQL 手工建表的数据库，需要单独对比并制定接管方案。首次迁移面向空库，直接升级不适用于已有同名表的库。

## 日常升级和回滚

- 升级前用 `alembic current` 和 `alembic history` 核对当前版本与迁移链。新结构通过新修订追加，已发布修订中的 SQL 快照保持固定。
- 升级本地数据库用 `uv run --locked alembic upgrade head`，重复运行会依照 `alembic_version` 跳过已应用修订。若需预览首次升级 SQL，运行 `uv run --locked alembic upgrade head --sql`。
- **回滚到 `base` 会删除首版 18 张业务表及其中的数据。** 仅在可丢弃的独立测试库验证 `uv run --locked alembic downgrade base`。降级结束后 `alembic_version` 表保留且为空，随后可再次 `upgrade head`。已有业务数据的环境先评估备份恢复和数据保留方案，按单独批准的变更流程处理。

## 复现迁移验收

在 `backend/` 使用 Docker 和 PostgreSQL 16 镜像。测试自动创建独立、仅本地环回可访问的容器和数据库，退出后停止容器。

```powershell
$env:SUNSHINE_TEST_POSTGRES = '1'
uv run --locked --extra dev pytest -q
Remove-Item Env:SUNSHINE_TEST_POSTGRES
```

常规 pytest 会检查冻结 SQL 快照。开启该变量后，进一步验证迁移版本、升降级、触发器及 DDL 和 ORM 的实际目录一致性。 [结构对比报告](database-migration-validation.md)
