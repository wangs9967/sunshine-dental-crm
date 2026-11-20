# V1.0 数据库设计

第二阶段最终评审稿。PostgreSQL 16，单门店。数据库结构以 [PostgreSQL DDL](../sql/database-v1.sql)、[字段字典](../sql/database-schema.md)及 [ER 图](../sql/database-er.mmd)为同一基线。数据模型含 18 张业务表。

| 域 | 表 |
|---|---|
| 账号和会员 | accounts、staff_profiles、members、employee_qr_tokens |
| 客户运营 | customer_assignments、customer_status、customer_tags、member_tag_relations、followup_records、followup_tasks |
| 积分 | points_accounts、points_records |
| 商城和核销 | products、exchange_orders、product_stock_records、redemption_credentials |
| 配置和审计 | system_configs、operation_logs |

## 账号、归属和运营

账号可分别关联至多一个会员档案及一个员工档案。会员填姓名、生日、手机号，生日为 DATE。手机号加密，搜索 HMAC 单独保管，用于精确匹配。数据库以账号保证注册唯一，是否采用手机号唯一或验证流程待确认。加入会员时，在同一事务创建会员、运营状态与零余额积分账户，有效来源码同时建立首次归属。现有客户扫码不覆盖归属。转移先锁会员与当前归属，校验预期归属与目标在职状态，关闭旧记录、创建新记录并审计。当前归属使用部分唯一索引，首次来源保留。

到店、消费、成交分别存储。家访和普通联系写入同表，通过 contact_type 区分，只记录运营沟通。后台生成复查和唤醒任务，按 dedupe_key 防重复，员工手动联系。

## 积分、商品、订单和凭证

- 积分账户和商品库存是当前快照。变更必须分别写 points_records 和 product_stock_records。两类流水只可追加。数据库用触发器拒绝更新、删除和清空，应用角色只授予查询和追加权限。
- 订单关联会员和商品，保留下单快照、数量和积分成本。两类兑换流水分别以 `exchange_order_id` 外键指向订单，每个订单最多各有一条扣减流水。FastAPI 服务在同一事务校验订单与流水的会员、商品、金额及数量一致，并保证两条流水同时落库。
- 库存流水覆盖初始入库、人工调整、兑换扣减。商品初始库存为零，正值初始入库也必须记账；当前后台通过库存调整入口增加或减少库存。核销更新订单与凭证并写操作审计，不再次扣减积分和库存。
- 订单状态仅 pending、verified。凭证与订单一对多，同一订单最多一条未关闭凭证和一条已消费凭证。过期凭证在换码事务中作废后再签发。只存凭证摘要。核销时锁订单、重读凭证并原子写消费人、时间及订单核销结果。凭证有效期和读取权限见待确认事项。
- 管理后台查询通过订单、核销人与审计获得记录。系统配置只开放经批准的键。角色为固定基础角色，访问规则见权限矩阵。

## 月限兑与幂等

BUSINESS_TIMEZONE 默认且已确认 Asia/Shanghai（UTC+8）。以 exchange_orders.created_at（TIMESTAMPTZ）归属自然月，将业务时区的本月月初、下月月初分别转换为 UTC，再使用左闭右开区间。按会员和商品合计 pending、verified 的 SUM(quantity)。per_user_monthly_limit 为 NULL 时不限量。复合索引 (member_id, product_id, created_at) INCLUDE (quantity, status) 与等值及范围条件匹配。订单时点由服务端写入，数据库会话、系统和手机时区不参与。具体事务与签发流程见[兑换详细设计](exchange-detailed-design.md)。

订单、积分流水和库存流水均使用 `VARCHAR(128) NOT NULL` 定义幂等键。订单按会员与键唯一，两类流水分别按服务端派生键唯一。应用校验键格式、生成请求摘要并比较重试内容。详见 [API 幂等键契约](api-spec.md#幂等键契约)。

账号与运营枚举、归属结束时间、商品状态与版本、流水分类与调整原因等由 FastAPI 服务校验。身份或状态无法识别时拒绝受保护操作。归属变更仍使用事务，数据库继续限制每位会员最多一条当前归属。

| 服务校验范围 | 现行口径 |
|---|---|
| 身份与状态 | 账号状态 `active`、`disabled`、`locked`。员工、会员及标签状态为 `active`、`disabled`。员工档案角色为 `employee`、`manager`、`admin`。 |
| 来源与归属 | 注册来源为 `direct`、`employee_qr`、`admin_created`，归属来源为 `employee_qr`、`admin_transfer`、`manual`；仅经授权入口可用。关闭归属时同时填写结束时间。 |
| 运营数据 | 到店、消费、成交分别使用 [业务规则](business-rules.md) 中的枚举。任务类型 `recall`、`reactivation`、`manual`，任务状态 `pending`、`completed`、`postponed`、`ignored`。 |
| 商品及流水 | 商品状态 `draft`、`published`、`off_shelf`，版本为正整数。积分分类 `earn`、`spend`、`adjust`，累计获得和支出非负。库存分类 `initial`、`adjustment`、`exchange`。按分类校验调整原因、操作人及关联订单。 |
| 核销及审计 | 服务生成并校验 32 字节凭证摘要，保证核销时间不早于下单、作废时间不早于签发。审计角色来自可信会话或后台任务。 |
