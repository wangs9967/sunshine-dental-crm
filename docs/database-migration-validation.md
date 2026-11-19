# V1.0 首次迁移结构对比报告

开发分支为 `codex/database-migration`。首版 Alembic 修订为 `0001_frozen_schema`，无前置修订。冻结 SQL、字段字典和 ER 图保持原样。迁移 SQL 快照与已验收的 `sql/database-v1.sql` 内容完全相同。 [迁移脚本](../backend/alembic/versions/0001_frozen_schema.py) · [SQL 快照](../backend/alembic/versions/0001_frozen_schema.sql) · [SQLAlchemy 模型](../backend/app/db/models.py)

## PostgreSQL 结构对比

在临时 PostgreSQL 16.16 容器内创建三个全新的数据库，分别直接加载冻结 DDL、执行 Alembic 和用 SQLAlchemy `Base.metadata.create_all()` 验证模型定义。比较 PostgreSQL 系统目录中的对象名称和规范化定义，覆盖字段顺序、类型、可空性、服务端默认值、外键动作、索引顺序、部分索引谓词和覆盖列。

| 对比项 | 冻结 DDL | Alembic 升级与再次升级 |
|---|---:|---:|
| 业务表 | 18 | 18 |
| 字段 | 186 | 186 |
| 主键 | 18 | 18 |
| 外键 | 32 | 32 |
| 显式索引 | 23 | 23 |
| `CHECK` 约束 | 18 | 18 |
| `UNIQUE` 约束 | 19 | 19 |
| 流水触发器 | 2 | 2 |
| 流水触发函数 | 1 | 1 |

Alembic 升级和再次升级的业务对象定义均与冻结 DDL 一致，`alembic_version` 单独计数。SQLAlchemy 模型创建的表、字段、约束及显式索引同样一致。函数和触发器由版本迁移安装。月限兑复合索引的等值列、时间范围列和覆盖列不变，动态核销的两个部分唯一索引均已创建。

## 执行结果

| 验收项 | 结果 |
|---|---|
| 空库 `upgrade head` 及已达 head 后再次执行 | 成功，版本表只有 `0001_frozen_schema` |
| `alembic current` 与 `alembic check` | 当前版本为 head，模型未产生新的迁移操作 |
| `downgrade base` | 成功移除业务对象，`alembic_version` 保留为空 |
| 降级后 `upgrade head` | 成功，目录结构与首次升级及冻结 DDL 一致 |
| 积分及库存流水保护 | 两个触发器均拒绝 `UPDATE`、`DELETE`、`TRUNCATE`，返回 SQLSTATE `55000` |
| 动态核销 | 使用 SQLAlchemy 映射写入测试凭证，数据库拒绝同一订单出现第二条未关闭凭证或第二条已消费凭证 |
| 离线 SQL | 输出包含两个触发器，函数内的 PostgreSQL `%` 格式占位符保留 |

迁移验收只连接测试容器。容器退出后自动清理。既有开发库和生产库均未执行迁移。完整测试及复现命令见[迁移测试](../backend/tests/test_database_migration.py)和[本地数据库迁移](database-migrations.md)。

后端 pytest 共 4 项通过，mypy 与 wheel、源码包构建通过。现有健康检查仍报告 Starlette TestClient 弃用提示，迁移测试通过。
