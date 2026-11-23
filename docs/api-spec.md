# V1.0 REST API 契约

第二阶段最终评审稿。所有路径以 `/api/v1` 开头。权限组见[权限矩阵](permissions.md)，页面映射见[三端路由](navigation.md)。待定操作使用拒绝默认策略，详见[待确认事项](open-questions.md)。

## 传输约定

- JSON 使用 snake_case。标识使用 UUID 字符串，时间点使用含偏移的 RFC 3339（服务端响应统一为 UTC），生日使用 YYYY-MM-DD。所有 BIGINT 积分值使用十进制字符串，数量、月限额和版本号使用 JSON 整数。商品图片返回可访问的展示地址，上传接口返回受控对象键。
- 成功返回 `{success:true,data,request_id}`，失败返回 `{success:false,error:{code,message,details},request_id}`。表单字段问题使用 details.fields，权限和凭证错误不得暴露他人资源信息。不返回手机号密文、检索摘要、内部请求摘要或密码哈希。
- 列表使用 `page`（默认 1）、`page_size`（默认 20，最大 100），返回 `{items,page,page_size,total}`。默认按记录业务时间倒序并以 id 打破并列。各列表的可用筛选在下文列出，权限过滤先于计数与分页。
- 受保护请求使用 Bearer 会话。角色来自已认证账号和当前身份，由服务端校验。刷新会话的摘要、角色和撤销状态使用 Redis 管理，停用及权限变更后服务端重新检查身份。登录、刷新、签发二维码凭证使用 `Cache-Control: no-store`。列表对手机号默认脱敏。无权读取其他人的对象详情时返回 404。
- 200 用于查询、更新及幂等重放，201 用于创建，400 用于错误格式、缺少必需幂等键，401 用于登录失效，403 用于功能无权限，404 用于未知或不可见资源，409 用于状态冲突，422 用于字段校验，429 用于限流。兑换首次成功用 201，完成后的同请求重试用 200。
- 订单创建、人工积分调整、库存调整要求 `Idempotency-Key` 请求头。审计记录 request_id、操作人和结果，仅记录脱敏变更。

## 幂等键契约

`Idempotency-Key` 区分大小写，允许 1–128 个字符，字符集为 ASCII 字母、数字及 `.`、`_`、`:`、`-`。客户端可使用 UUID。缺失或格式不合法返回 400 `INVALID_IDEMPOTENCY_KEY`。请求体无需携带幂等键。数据库三处 `idempotency_key` 均为 `VARCHAR(128) NOT NULL`。

| 写操作 | 数据库唯一范围 | 请求摘要内容 |
|---|---|---|
| 兑换下单 | `exchange_orders` 内 `(member_id, idempotency_key)`，原样保存请求头 | `product_id`、`quantity` |
| 人工积分调整 | `points_records.idempotency_key` 全表唯一，服务端键按操作类型、认证账号及请求头派生 | `member_id`、`delta_points`、`reason` |
| 人工库存调整 | `product_stock_records.idempotency_key` 全表唯一，服务端键按操作类型、认证账号及请求头派生 | 路径中的 `product_id`、`quantity_delta`、`reason` |

服务端先验证当前身份与操作权限，并比较规范化请求摘要。在同一范围内，同键同请求返回首次成功写入的资源（HTTP 200），同键异请求返回 HTTP 409 `IDEMPOTENCY_CONFLICT`。不同会员、不同后台账号或不同操作可以独立使用相同请求头。事务回滚不占键，网络超时可用原键和原请求重试。键的派生与摘要见[兑换详细设计](exchange-detailed-design.md#兑换事务与流水)。

## 通用视图

| 名称 | 响应字段 |
|---|---|
| Session | access_token、refresh_token、expires_in、account_id、selected_role、available_roles、registration_required |
| Member | id、member_no、name、birthday、phone_masked、status、registered_at；管理详情另含 source_employee_id、source_employee_name、current_staff_id、current_staff_name，以及 visit_status、consume_status、deal_status。无对应资料时相关字段为 null |
| Staff | id、employee_no、display_name、role、status |
| Customer | Member 的运营视图，另含 visit_status、consume_status、deal_status、last_effective_contact_at、next_recall_at、current_staff_id |
| Followup | id、member_id、staff_id、contact_type、followup_at、content、customer_feedback、effective_contact、gift_given、gift_name、next_followup_at |
| Task | id、member_id、assigned_staff_id、task_type、status、title、scheduled_at、postponed_until、result、completed_at |
| PointsAccount / PointsRecord | 账户含 member_id、balance、total_earned、total_spent；流水含 id、member_id、delta_points、balance_before、balance_after、record_type、source_type、created_at；后台另含经授权的 reason、operator_account_id、exchange_order_id |
| Product | id、name、category、description、cover_url、image_urls、points_price、per_user_monthly_limit、in_stock；后台另含 stock、status、sort_order、version、图片对象键 |
| Order | id、order_no、product_id、product_snapshot、quantity、points_cost_total、status、created_at、verified_at；后台另含 member_id、verified_by_account_id |
| StockRecord | id、product_id、exchange_order_id、change_type、quantity_delta、stock_before、stock_after、operator_account_id、reason、created_at |

## 登录、门诊及会员

| 方法与路径 | 权限组 | 请求和响应 |
|---|---|---|
| POST /auth/wechat/login | 公开 | code 必填，可携带 scene_token。服务端向微信换取 OpenID，返回 Session。已注册会员直接登录，首次注册时由小程序再次提交来源码。凭据无效返回 400 WECHAT_CODE_INVALID，微信服务异常返回 502 WECHAT_UNAVAILABLE。 |
| POST /auth/admin/login | 公开 | username、password。验证启用账号及在职店长或管理员档案，通过后返回 Session。凭据或资格校验失败统一返回 401 INVALID_CREDENTIALS。限流返回 429 LOGIN_RATE_LIMITED 和 Retry-After。 |
| POST /auth/refresh | 持有效刷新会话 | refresh_token，轮换令牌并返回 Session。 |
| POST /auth/logout | 已认证 | 撤销当前会话，返回 logged_out。 |
| GET /auth/me | 已认证 | account_id、selected_role、available_roles、registration_required。角色切换必须经服务端重新授权；员工开通与登录方式按评审门槛开通。 |
| POST /auth/select-role | 已认证 | role 必须在当前渠道和账号实际授权的 available_roles 中；重新签发 Session 并撤销旧会话。员工身份切换随开通规则生效。 |
| GET /clinic-profile | 公开 | 门诊名称、联系电话、地址、导航坐标、隐私协议和服务协议入口。仅返回公开配置。 |
| POST /members/register | R1 | name、birthday、phone 必填，可选 scene_token。返回 201，data 包含 Member 字段及 `session` 和 `source_status`。重复注册返回 409 MEMBER_ALREADY_REGISTERED。有效首次扫码建立首次归属。 |
| GET /members/me | R2 | 返回本人 Member。 |
| PATCH /members/me | R3 | 允许字段和手机号验证按业务确认开放。当前冻结为不可提交，开放后返回 Member。 |
| GET /members/me/points | R2 | 本人 PointsAccount。 |
| GET /members/me/points-records | R2 | 本人 PointsRecord 列表，筛选 record_type。 |

### 会话基础设施

服务端生成 `X-Request-ID`，与 JSON 中的 `request_id` 一致。认证响应使用 `Cache-Control: no-store`。无效会话返回 `401 INVALID_SESSION`，认证依赖不可用返回 `503 AUTH_UNAVAILABLE`。

访问令牌和刷新令牌均为不透明随机值。访问令牌默认有效 600 秒，会话自初次签发起最多有效 604800 秒，刷新不延长会话总期限。刷新成功会同时替换两个令牌。已使用的刷新令牌再次提交会撤销整个会话，并写入脱敏审计。客户端应确保同一会话同时只有一个刷新请求。退出撤销整个会话。

授权依据为账号、当前档案、选定角色和会话渠道。注册前会话使用 `selected_role: null`、`available_roles: []`、`registration_required: true`。后续业务接口仍需单独声明所需权限或档案。

会员注册返回的新 `session` 替代注册会话，小程序接收后进入会员首页。员工来源码的状态为 `none`（未提供）、`bound`（已关联）或 `invalid`（所提供的来源码无效、过期、撤销或来源员工不可用）。`invalid` 时仍完成注册。手机号用于联系、允许共用、无需短信验证。积分账户初始余额为字符串 `"0"`。

后台登录限流使用 300 秒窗口，每来源最多 30 次，同一来源和用户名组合最多 5 次。后台认证审计保留渠道、结果和 Request ID，登录成功记录账号与角色，失败以匿名记录原因。
| GET /members/me/exchange-orders | R2 | 本人 Order 列表，筛选 status。 |
| GET /products、GET /products/{id} | R2 | 已上架商品列表或详情；列表筛选 category、q。 |
| POST /exchange-orders | R4 | product_id、quantity 和幂等键；返回本人 Order。成本、库存、额度由服务端计算。 |
| GET /exchange-orders/{id} | R2 | 本人 Order；状态为 pending 时可请求动态凭证。 |
| POST /exchange-orders/{id}/credentials | R4 | 本人待核销订单，空请求体；返回本次 token、order_id、issued_at、expires_at。再次签发会替换旧凭证，响应不缓存。 |

## 员工与客户运营

| 方法与路径 | 权限组 | 请求和响应 |
|---|---|---|
| GET /staff/me | R5 | 当前 Staff。 |
| GET /staff/me/qr-code | R5 | 当前员工来源码状态及 expires_at。服务端只保存摘要，已签发明文无法再次读取。 |
| POST /staff/me/qr-token/rotate | R5 | 串行作废旧码并返回本次新二维码展示数据及 expires_at，不缓存响应。 |
| GET /staff/me/customers | R6 | 当前负责人为本人的 Customer 列表，筛选 q、visit_status、consume_status、deal_status。q 支持姓名、会员编号或完整手机号精确检索。 |
| GET /customers/{id} | R6 | 可见的 Customer 及当前归属。 |
| PATCH /customers/{id}/status | R6 | 三类运营状态独立更新，至少传一个字段；返回 Customer。 |
| GET /customers/{id}/followups | R6 | Followup 列表，筛选 contact_type、from、to。 |
| POST /customers/{id}/followups | R6 | contact_type、content 必填，可传 followup_at、customer_feedback、effective_contact、gift_given、gift_name、next_followup_at。返回 Followup。家访用 home_visit。 |
| POST /customers/{id}/transfer | R7 | to_staff_id、reason 必填，expected_assignment_id 用于防止覆盖并发转移。返回当前归属和历史记录 ID。 |
| GET /followup-tasks | R8 | Task 列表，筛选 status、task_type、assigned_staff_id、from、to，受角色范围限制。 |
| POST /followup-tasks | R9 | member_id、assigned_staff_id、title、scheduled_at，返回人工 Task。系统生成的复查、唤醒由后台任务执行。 |
| POST /followup-tasks/{id}/complete、/postpone、/ignore | R8 | 完成或忽略提交 result，延期提交 postponed_until，可附 result。返回更新后的 Task；已完成或已忽略的任务拒绝变更。 |
| POST /exchange-orders/{id}/verify | R10 | token 必填；服务端以订单路径与凭证建立交叉绑定。返回 verified 及 verified_at；员工使用需另行确认。 |
| POST /exchange-orders/verify | R10 | 扫码入口，仅提交 token。服务端定位订单后执行与按订单核销相同的授权和事务。 |

员工新增客户入口使用本人来源码邀请客户完成注册。现有会员的重新扫码不会覆盖归属。人工代录及账号绑定方案待确认，当前契约保留邀请注册路径。

## 管理后台

| 方法与路径 | 权限组 | 请求和响应 |
|---|---|---|
| GET /admin/dashboard | R11 | 返回会员数、待跟进任务数、上架商品数、待核销订单数，附 as_of。 |
| GET /admin/members、GET /admin/members/{id} | R11 | Member 列表或详情，列表按 q、status、staff_id 过滤。q 支持姓名、会员编号或完整手机号精确检索，staff_id 只匹配当前负责人。 |
| GET /admin/staff、GET /admin/staff/{id} | R12 | Staff 列表或详情，筛选 role、status、q（员工姓名或编号）。未分配员工编号时 employee_no 为 null。 |
| POST /admin/staff、PATCH /admin/staff/{id} | R13 | 创建或修改员工档案，含 display_name、employee_no、role、status；管理员账号授权及员工开通流程过审后开放。 |
| GET /admin/assignments | R7 | 归属列表，含 member_id、staff_id、is_current、bind_source、started_at、ended_at、change_reason，筛选 member_id、staff_id、is_current。 |
| GET /admin/assignments/candidates | R7 | 在职候选员工列表，仅含 id、display_name，支持 q。 |
| GET /admin/followups | R11 | Followup 列表，筛选 member_id、staff_id、contact_type、from、to。客户操作复用 /customers 路径。 |
| GET /admin/points/accounts、GET /admin/points/records | R11 | PointsAccount 或 PointsRecord 列表，筛选 member_id，流水另可筛选 record_type、from、to。 |
| POST /admin/points/adjustments | R14 | member_id、delta_points、reason、幂等键；审批方案确认后返回 PointsRecord。 |
| GET /admin/products、GET /admin/products/{id} | R11 | 商品后台列表或详情，列表按 q、status、category 筛选。 |
| POST /admin/products、PATCH /admin/products/{id} | R15 | 创建或编辑名称、分类、图片对象键、描述、points_price、per_user_monthly_limit、status、sort_order；更新带 expected_version，返回 Product。初始库存及后续变动走库存调整契约。 |
| POST /admin/product-images/upload-tickets | R15 | content_type、size，返回短时上传凭据、对象键和 expires_at。商品保存时只接受已授权且归本项目的对象键。 |
| GET /admin/products/{id}/stock-records | R11 | StockRecord 列表，筛选 change_type、from、to。 |
| POST /admin/products/{id}/stock-adjustments | R16 | quantity_delta、reason、幂等键，返回 StockRecord；库存不可为负。 |
| GET /admin/exchange-orders、GET /admin/exchange-orders/{id} | R11 | Order 列表或详情，筛选 order_no、member_id、product_id、status、from、to。 |
| GET /admin/verifications | R11 | 已核销 Order 列表，筛选 verified_by_account_id、from、to（核销时间）。 |
| GET /admin/settings、PATCH /admin/settings/{key} | R17 | 读写经批准的配置项，更新传 value，返回 key、value、updated_at。BUSINESS_TIMEZONE 只读展示。 |
| GET /admin/roles | R18 | 四角色固定权限说明。目录只读，角色分配受员工管理权限约束。 |
| GET /admin/audit-logs | R18 | 脱敏日志列表，筛选 module、action、actor_account_id、from、to。 |

## 兑换与核销错误

| HTTP | error.code | 条件 |
|---|---|---|
| 409 | PRODUCT_NOT_AVAILABLE / STOCK_INSUFFICIENT / POINTS_INSUFFICIENT | 商品下架、库存不足或积分不足 |
| 409 | MONTHLY_LIMIT_EXCEEDED | 同会员同商品的已提交数量加本次数量超过上限；details 可含 remaining_quantity、next_month_start_utc |
| 409 | IDEMPOTENCY_CONFLICT / VERSION_CONFLICT / ASSIGNMENT_CHANGED | 同键异请求、商品版本不匹配、归属已变化 |
| 409 | ORDER_ALREADY_VERIFIED | 已核销，订单状态保持不变 |
| 409 | CREDENTIAL_INVALID / CREDENTIAL_EXPIRED | 凭证无效、已撤销、与订单不符或已过期 |
| 403 | FEATURE_NOT_AVAILABLE / FORBIDDEN | 业务决策尚未开放，或当前身份没有操作权限 |

商品月限由服务端配置 `BUSINESS_TIMEZONE`（默认且已确认 `Asia/Shanghai`）计算，以写入的 `created_at` 为准。先计算业务月初与下月月初，再转换为 UTC，按 `[month_start_utc, next_month_start_utc)` 对已提交的 `pending` 与 `verified` 订单求 `SUM(quantity)`。`NULL` 表示不限量。同一请求跨月重试仍返回原订单。服务器系统时区、数据库会话时区与会员手机时区均不参与计算。有关加锁及重放语义见[兑换详细设计](exchange-detailed-design.md)。
