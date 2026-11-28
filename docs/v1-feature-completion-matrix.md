# 阳光口腔 CRM V1.0 功能完成矩阵

## 1. 整体完成情况

盘点基线为 `main` 的 `4c234f66f09e750b75d43f0f3bcd51bd0cec1375`。已完成的业务集中在身份与会话、会员注册和资料、积分余额、员工开通与登录、客户查询和归属、跟进与人工回访。**V1.0 的完整业务链尚未闭合**。积分流水和入账、商品和库存、实际下单、订单列表、动态凭证和核销仍有缺口，后台运营总览、系统设置和审计查询也尚未接入。API 契约中按 HTTP 方法和路径展开共 63 项，代码已注册 31 项，余 32 项包含未开发、待确认和当前关闭的契约。健康检查和框架自带文档接口不计入。

三端矩阵共 48 个功能条目。其中 20 项已完成、19 项部分完成、2 项未开发、5 项待确认、2 项已关闭。这个计数用于定位缺口，包含按端拆列的同一业务及关闭项，因此不用于推算发布完成率。

比对顺序以负责人后续明确确认和冻结规则为准。[原始开发清单](project-handoff/v1.0/00_原始开发清单.txt)记录的是原型补齐进度。[范围确认](project-handoff/v1.0/01_V1.0范围确认.md)、[原始页面清单](project-handoff/v1.0/02_模块与页面清单.md)、[业务规则](business-rules.md)、[路由与交互](navigation.md)、[API 契约](api-spec.md)、[权限矩阵](permissions.md)及[数据库字段字典](../sql/database-schema.md)用于交叉核对。通过公开访问和浏览器尝试打开[原始 Figma](https://www.figma.com/design/vHq5a7gAf59V1lDiR94NdH)，浏览器返回 “Hmm, we couldn't find that one”，当前无法读取 Frame 或核对逐页视觉。[UI Freeze](ui-freeze.md)中原冻结记录与交接包的评审中状态也尚未统一。下文的设计引用指向仓库中的文字基线。

状态口径：**已完成**表示有真实业务闭环。**部分完成**表示已有页面、API 或流程的一部分。**未开发**表示未找到实际业务实现及对应独立功能入口。**待确认**表示需负责人决定规则。**已关闭**表示已有明确的关闭决定。关闭或待确认的决策按功能拆列。手动验收另列，按负责人明确确认的范围记录，具体子用例未逐条留档时按阶段记录。以下 API 省略 `/api/v1` 前缀，`—` 表示没有适用证据。

## 2. 三端功能完成矩阵

设计依据缩写：**原**为原始开发清单及范围/页面清单，**UI** 为 UI Freeze，**导**为导航文档，**契**为 API 契约，**规**为业务规则，**权**为权限矩阵，**兑**为兑换详细设计。表内测试文件均按第 6 节路径查找。

### 2.1 会员小程序

| 功能 | 设计 | 状态 | 已有页面或代码 | 已有 API | 表 / 权限 | 自动化证据 | 手动验收 | 缺口及依赖 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 微信登录、注册与恢复 | 原、导、契、规 | 已完成 | `pages/auth/index`、`pages/member/register`、`pages/index/index`、`services/member-session.ts` | POST `/auth/wechat/login`、`/members/register`；认证刷新、退出 | accounts、members、points_accounts、customer_status、operation_logs / 公开换码、R1 | 注册、手机号共用、失效、会话恢复 | 负责人确认 2.5.4 及认证联调验收 | 运行依赖微信配置、Redis、PG、手机号保护配置 |
| 会员首页、个人中心 | 原、UI、导 | 部分完成 | `pages/member/home`、`pages/member/profile`，通过 workspace 显示导航和退出 | 会话 API；页面本身无经营数据读取 | members / R2 | 登录回跳、路由和退出 | 登录后可进入，完整首页未见专项验收 | 会员身份摘要及门诊、隐私入口；依赖现有会员资料和公共配置 |
| 会员资料只读 | 原、导、契 | 已完成 | `pages/member/profile-details` | GET `/members/me` | members、accounts / R2 本人 | 脱敏、会话失效、失败重试 | 2.5.4 修复资料空白后，负责人确认该阶段手动验收通过 | 依赖会话和手机号保护配置 |
| 修改会员资料 | 导、契、权 | 待确认 | 资料页只读 | 无 | members / R3 当前拒绝 | 权限基线 | 未开放 | 确认字段、验证及修改流程 |
| 积分余额 | 原、导、契 | 已完成 | `pages/points/index` 由 `components/workspace` 拉取余额 | GET `/members/me/points` | points_accounts / R2 本人 | 注册账户、真实余额接口、前端请求测试 | 会员注册与认证阶段通过，余额无逐例记录 | 现可查余额，余额变动依赖积分入账及兑换 |
| 积分流水 | 原、UI、导、契 | 未开发 | 积分页复用现有外壳，仅接余额 | 无 | points_records / R2 本人 | 无流水业务测试 | 未见 | 流水分页、类型筛选和记录渲染，依赖流水查询与实际积分变更 |
| 积分商城 | 原、UI、导、契 | 部分完成 | `pages/mall/index`，演示商品入口 | 无 | products / R2 已上架可见 | 路由 | 2.4 路由，业务未见 | 上架商品列表、类别、搜索和缺货状态；依赖商品 |
| 商品详情 | 原、UI、导、契 | 部分完成 | `pages/mall/detail`，演示商品 ID | 无 | products、exchange_orders / R2 | 路由 | 2.4 路由，业务未见 | 真实详情、价格、限额提示；依赖商品与限兑查询 |
| 兑换确认 | 原、UI、导、兑 | 部分完成 | `pages/mall/confirm`，演示跳转 | 无 | products、points_accounts、points_records、product_stock_records、exchange_orders / R4 | 页面栈测试；月限和并发仅有测试方案 | 2.4 路由，业务未见 | 数量、成本、幂等下单和原子扣减 |
| 兑换成功 | 原、UI、导、兑 | 部分完成 | `pages/mall/success`，文案明确为流程演示 | 无新增接口，未消费真实下单响应 | exchange_orders / R2 | 导航和页面栈 | 2.4 路由，业务未见 | 以创建结果驱动成功页，链接真实订单 |
| 兑换订单详情与凭证 | 原、导、契、兑 | 部分完成 | `pages/orders/detail` 只呈现外壳和空状态 | GET `/exchange-orders/{id}` 已实现，页面未接入；无凭证签发 | exchange_orders、redemption_credentials / R2 本人、R4 本人待核销 | 本人订单 API 和他人 404；路由 | 2.4 路由，真实兑换未见 | 真实快照和状态、签发/刷新/过期，依赖下单及核销策略 |
| 我的订单记录 | 原、UI、导、契 | 部分完成 | `pages/orders/index`，演示订单入口 | 无本人订单列表 | exchange_orders / R2 本人 | 路由 | 2.4 路由，业务未见 | 列表分页、状态筛选、真实详情跳转 |
| 隐私、协议、门诊联系与导航 | 原、导、契 | 未开发 | `/pages/member/privacy`、`/pages/member/clinic` 未注册 | 无 | system_configs / 仅公开字段，配置映射待确认 | 未见 | 未见 | 确认文案、公开字段、授权和导航方式，再接公开门诊接口 |
| 注册赠分 | 原、规、契 | 已关闭 | 注册正常完成，积分账户从零开始 | POST `/members/register` 无赠分 | points_accounts、points_records / R1 | 注册零余额 | 注册阶段通过 | 将来启用需负责人确认积分策略 |
| 支付、取消与退款 | 原、规、兑 | 已关闭 | 无 | 无 | 订单状态只允许 pending、verified / 无 | 结构基线 | 不适用 | V1.0 明确排除 |

### 2.2 员工小程序

| 功能 | 设计 | 状态 | 已有页面或代码 | 已有 API | 表 / 权限 | 自动化证据 | 手动验收 | 缺口及依赖 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 员工登录与微信绑定 | 导、契、规 | 已完成 | `pages/auth/index`、`services/staff-session.ts` | POST `/auth/wechat/staff-bind`、`/auth/wechat/login`（employee），刷新和退出 | accounts、staff_profiles、operation_logs；邀请与会话在 Redis / 一次性邀请和在职资格 | 消费竞争、重放、会员账号复用、停用、冷启动 | 2.6.3 负责人手动验收通过 | 换微信及会话内切换仍待确认 |
| 员工工作台 | 原、UI、导 | 已完成 | `pages/staff/dashboard`、`components/workspace`，有客户、任务和资料入口 | GET `/staff/me` 检查本人资料；列表在目标页面请求 | staff_profiles、accounts / R5，链接业务受 R6/R8 | 工作身份和路由 | 2.6.3、2.6.4 阶段验收 | 工作台未请求客户和任务统计。仓库路由基线要求快捷入口，Figma 视觉和潜在统计要求待核验 |
| 员工资料 | 原、导、契 | 已完成 | `pages/staff/profile`、`components/workspace` | GET `/staff/me` | staff_profiles、accounts / R5 本人 | 员工档案、退出和状态测试 | 2.6.3 阶段通过 | 依赖在职会话 |
| 客户列表 | 原、导、契 | 已完成 | `pages/staff/customers`、`services/staff-customers.ts` | GET `/staff/me/customers` | members、customer_assignments、customer_status / R6 本人当前归属 | 搜索、筛选、分页与转移后隔离 | 2.6.1 负责人通过 | 依赖归属和会员注册 |
| 客户详情与运营三状态 | 原、导、契、规 | 部分完成 | `pages/staff/customer-detail` 展示脱敏资料及三状态 | GET `/customers/{id}`；无状态 PATCH | members、customer_status、customer_assignments / R6 | 详情读取、越权和失效；无状态写入业务测试 | 2.6.1 查询通过 | 补三状态的独立编辑与审计，继续实时校验归属 |
| 当前归属与客户转移 | 原、导、契、规、权 | 已完成 | 员工通过客户列表和详情消费当前归属。后台 `/assignments` 执行分配和转移 | GET `/staff/me/customers`、`/customers/{id}`；后台 POST `/customers/{id}/transfer` | customer_assignments、members、staff_profiles / 员工 R6 读取；写和历史 R7 仅店长管理员 | 转移生效、访问回收、历史保留 | 2.6.2 阶段通过 | 原清单和导航仍有员工转移页，后续已确认由后台执行；离职交接与审批待确认 |
| 配套员工来源码和邀约注册 | 原、导、契、规 | 部分完成 | 员工 `qrcode`、`customer-invite` 路由缺失；会员登录可接收场景参数 | POST `/members/register` 消费已存在且有效的来源码；无来源码读取与轮换 | employee_qr_tokens、members、customer_assignments / R5 签发，R1 消费 | 有效/失效及再次扫码保护；无签发测试 | 会员注册侧阶段验收，签发闭环未见 | 补员工来源码签发、轮换、展示；员工本人绑定邀请是另一套凭据 |
| 后台代录客户 | 原、契 | 待确认 | 无 | 无 | members、customer_assignments / 待定 | 未见 | 未见 | 先决定是否允许及身份绑定流程 |
| 回访任务列表 | 原、UI、导、契 | 已完成 | `pages/staff/tasks` | GET `/followup-tasks` | followup_tasks、customer_assignments / R8 本人且客户仍归属 | 数据范围、转移后旧任务不可见、分页契约 | 2.6.4 手动验收通过 | 自动名单属于单独缺口 |
| 客户跟进 | 原、UI、导、契 | 已完成 | `pages/staff/followup-create`、`services/followup-form.ts` | POST `/customers/{id}/followups` | followup_records、customer_status、operation_logs / R6 当前归属 | 越权、转移并发、有效联系时间、审计回滚 | 2.6.4 手动验收通过 | 小程序当前表单提交类型和内容，契约其余可选字段未在表单开放 |
| 家访记录 | 原、UI、导、契 | 已完成 | `pages/staff/home-visit`、家访历史过滤 | GET、POST `/customers/{id}/followups` | followup_records / R6，类型 home_visit | 后端家访过滤、前端提交和返回 | 2.6.4 手动验收通过 | 依赖跟进共用服务 |
| 跟进历史 | 原、UI、导、契 | 已完成 | `pages/staff/followup-history` | GET `/customers/{id}/followups` | followup_records、customer_assignments / R6 | 时间、家访过滤及归属范围 | 2.6.4 手动验收通过 | 依赖跟进和实时归属 |
| 任务状态处理 | 原、导、契、规 | 已完成 | `pages/staff/tasks` | POST `/followup-tasks/{id}/complete`、`/postpone`、`/ignore` | followup_tasks、customer_assignments、operation_logs / R8 | 重复延期、终态冲突、竞争写入和前端刷新 | 2.6.4 手动验收通过 | 延期仅更新原任务，完成无需跟进，自动生成策略独立 |
| 普通员工核销 | 导、契、权 | 待确认 | `/pages/staff/verify` 未注册 | 无核销 API | redemption_credentials、exchange_orders / R10 普通员工未开放 | 权限规则测试；无核销测试 | 未开放 | 是否向员工开放待决定，店长和管理员仍可按已有授权先建设核销 |

### 2.3 管理后台

| 功能 | 设计 | 状态 | 已有页面或代码 | 已有 API | 表 / 权限 | 自动化证据 | 手动验收 | 缺口及依赖 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 管理员登录 | 导、契 | 已完成 | `/login`，`pages/Login.tsx`、`session.ts` | POST `/auth/admin/login`、刷新、退出 | accounts、staff_profiles、operation_logs；Redis / 在职管理员 | Argon2id、限流、异常脱敏、回跳和刷新 | 2.5.6 联调通过，2.6.4 隔离环境登录验证 | 首位管理员开通流程仍待确认 |
| 店长登录 | 导、契 | 已完成 | 同一真实登录页按返回角色进入 | 同管理员登录 | 同上 / 在职店长 | 店长凭据和角色、功能权限 | 2.5.6 联调通过，2.6.4 隔离环境登录验证 | 店长写权限按权限组分别决定 |
| 数据总览 | 原、UI、导、契 | 部分完成 | `/dashboard` 由 `WorkspacePage.tsx` 展示快捷入口及空状态 | 无 | members、followup_tasks、products、exchange_orders / R11 | 路由；无聚合业务测试 | 2.3/2.4 工程和路由 | 指标聚合、口径和刷新依赖各数据模块 |
| 会员管理 | 原、UI、导、契 | 已完成 | `/members`、`/members/:id`，`DirectoryPage.tsx` | GET `/admin/members` 及详情 | members、customer_assignments、customer_status、staff_profiles / R11 | 列表、详情、筛选、脱敏 | 2.6.1 负责人通过 | 已验收范围为查询，编辑与代录另待确认 |
| 员工管理 | 原、UI、导、契、规 | 已完成 | `/employees`、详情、`components/staff.tsx` | GET `/admin/staff` 及详情；POST 创建及绑定邀请；PATCH 停用/启用 | accounts、staff_profiles、operation_logs；Redis / R12 双角色读，R13 管理员写 | 列表、重复工号、店长拒绝、邀请和停用 | 2.6.1 与 2.6.3 负责人通过 | 已验收范围为普通员工，角色变更及换绑待确认 |
| 客户分配 | 原、导、规、权 | 已完成 | `/assignments`，`AssignmentsPage.tsx` | GET `/admin/assignments`、`/admin/assignments/candidates`；POST `/customers/{id}/transfer` | customer_assignments、members、staff_profiles、operation_logs / R7 | 首次分配、转移、竞争、回滚、前端冲突恢复 | 2.6.2 负责人通过 | 离职交接和审批另待确认 |
| 客户跟进 | 原、UI、导、契 | 已完成 | `/followups`，`FollowupPage.tsx` | GET `/admin/followups` | followup_records、members、staff_profiles / R11 | 列表筛选、分页、角色访问和请求契约 | 2.6.4 负责人通过 | 依赖员工写入；已接内容展开 |
| 回访任务（人工） | 原、导、契、权 | 已完成 | `/tasks`，全店查询、创建、忽略 | GET、POST `/followup-tasks`；POST `/followup-tasks/{id}/ignore` | followup_tasks、customer_assignments、operation_logs / R8、R9 | 当前负责人校验、店长管理员访问、冲突 | 2.6.4 负责人通过 | 后端 R8 也允许已授权管理角色调用完成和延期，后台当前界面只接忽略，符合 2.6.4 交付范围 |
| 复查和唤醒名单自动生成 | 原、规、契 | 部分完成 | `/tasks` 有现成任务消费者，生成器缺失 | 现有任务查询和处理可消费已生成任务；无生成流程 | followup_tasks、customer_status / R8、R9，生成主体另定 | 人工任务有测试，自动生成与去重仅有方案 | 人工任务已验收 | 生成时间、唤醒阈值和去重规则待负责人确认，员工手动联系 |
| 积分管理查询 | 原、UI、导、契 | 部分完成 | `/points/accounts`、`/points/records` 占位 | 无管理端积分 API | points_accounts、points_records / R11 | 路由；无真实后台积分测试 | 2.4 路由，业务未见 | 帐户、流水分页和过滤，依赖积分读模型 |
| 人工积分调整 | 契、权、兑 | 待确认 | 积分管理入口占位，无调整提交 | 无 | points_accounts、points_records、operation_logs / R14 默认拒绝 | 权限规则；无幂等和写入业务测试 | 未开放 | 需规则确认审批、额度、角色和来源后接入 |
| 商品管理 | 原、UI、导、契 | 部分完成 | `/mall/products` 及新增、详情、编辑占位 | 无查询、写入或图片票据接口 | products、operation_logs / R11 读、R15 管理员写 | 路由；无商品业务测试 | 2.4 路由，业务未见 | 上下架、价格、限额、版本和图片；店长写、时间窗和降额体验待确认 |
| 库存管理 | 导、契、兑 | 部分完成 | `/mall/products/:id/stock` 占位 | 无库存调整和流水查询 | products、product_stock_records、operation_logs / R11 读、R16 管理员写 | 路由；不可变流水结构有基线 | 2.4 路由，业务未见 | 幂等调整、非负库存、对账，依赖商品 |
| 兑换订单管理 | 原、UI、导、契 | 部分完成 | `/mall/orders`、详情占位 | 无后台订单接口；会员本人详情 API 已实现 | exchange_orders / R11 全店 | 路由，会员详情隔离测试 | 2.4 路由，业务未见 | 列表、详情和核销入口，依赖真实下单 |
| 核销与核销记录 | 原、导、契、兑 | 部分完成 | `/mall/verify`、`/mall/verifications` 占位 | 无核销或已核销记录接口 | redemption_credentials、exchange_orders、operation_logs / R10 店长管理员，R11 查询 | 路由；重复、过期、轮换、并发核销仅有方案 | 2.4 路由，业务未见 | 凭证展示、扫码与按单核销、原子校验和审计；依赖订单及凭证参数 |
| 系统设置读取 | 原、UI、导、契 | 部分完成 | `/settings` 占位；后端配置已固定 `Asia/Shanghai` | 无 GET `/admin/settings` | system_configs / R17 管理员读 | 路由及配置测试；无配置目录查询测试 | 2.4 路由，业务未见 | 指定可读键及敏感字段边界，展示时区且只读 |
| 系统设置写入 | 导、契、权 | 待确认 | 无可提交配置表单 | 无 PATCH | system_configs、operation_logs / `R17_WRITE` 默认拒绝 | 权限基线 | 未开放 | 当前无获准写入的配置键 |
| 角色权限目录 | 原、导、契、权 | 部分完成 | `/roles` 占位，后端固定矩阵生效 | 无目录 API | 固定规则在代码，候选身份由 accounts、staff_profiles、members 决定 / R18 管理员读 | 四角色基线和路由 | 2.4 路由，目录未见 | 后台只读目录需要真实接入；角色变更独立审批 |
| 操作审计 | 原、导、契、权 | 部分完成 | `/audit-logs` 占位；认证、注册、员工、归属、跟进和任务已有落库审计 | 相关写接口内部记审计；无 GET `/admin/audit-logs` | operation_logs / R18 管理员读 | 脱敏、拒绝审计、事务回滚 | 相关写业务按阶段验收，审计后台未见 | 管理员分页、筛选和脱敏输出；店长访问、导出和保留策略待确认 |

后台现有路由的分派入口见 [App.tsx](../admin-web/src/App.tsx)、[routes.ts](../admin-web/src/routes.ts)，统一占位见 [WorkspacePage.tsx](../admin-web/src/pages/WorkspacePage.tsx)。小程序注册页清单及演示链接见 [app.json](../miniprogram/app.json)、[navigation.ts](../miniprogram/config/navigation.ts)，共用外壳见 [workspace 组件](../miniprogram/components/workspace/workspace.ts)。单门店、预约和临床数据边界按已确认范围保留，预约管理及临床数据存储归为已关闭。

## 3. 后端 API 完成矩阵

口径为已挂载的业务路由，按方法和路径计数。同一路径不同方法分别统计，并将契约中的并列路径展开。核对入口为 [main.py](../backend/app/main.py)、[认证及会员路由](../backend/app/auth/routes.py)、[数据访问路由](../backend/app/access_routes.py)和[跟进及任务路由](../backend/app/followups.py)。

| 状态 | 接口 | 数量 | 权限与交付边界 |
| --- | --- | ---: | --- |
| 已完成 | POST `/auth/wechat/login`、`/auth/wechat/staff-bind`、`/auth/admin/login`、`/auth/refresh`、`/auth/logout`；GET `/auth/me` | 6 | 分别按微信身份、一次性邀请、后台账号、令牌或有效会话校验 |
| 已完成 | POST `/members/register`；GET `/members/me`、`/members/me/points` | 3 | R1、R2；注册来源码消费已接 |
| 已完成 | GET `/staff/me`、`/staff/me/customers`、`/customers/{id}` | 3 | R5、R6；角色与当前归属 |
| 已完成 | GET `/admin/members`、`/admin/members/{id}`、`/admin/staff`、`/admin/staff/{id}` | 4 | R11、R12；店长和管理员 |
| 已完成 | POST `/admin/staff`、`/admin/staff/{id}/wechat-invitation`；PATCH `/admin/staff/{id}` | 3 | R13 管理员；限普通员工 |
| 已完成 | GET `/admin/assignments`、`/admin/assignments/candidates`；POST `/customers/{id}/transfer` | 3 | R7；历史、冲突和事务审计 |
| 已完成 | GET、POST `/customers/{id}/followups`；GET `/admin/followups` | 3 | R6、R11；家访共用接口 |
| 已完成 | GET、POST `/followup-tasks`；POST `/followup-tasks/{id}/complete`、`/followup-tasks/{id}/postpone`、`/followup-tasks/{id}/ignore` | 5 | R8、R9；人工任务和状态处理 |
| 已完成 | GET `/exchange-orders/{id}` | 1 | R2 本人详情，客户端未接，查询测试以预置订单验证 |
| 待确认 | POST `/auth/select-role`；PATCH `/members/me` | 2 | 会话内切换和会员编辑；当前入口关闭 |
| 未开发 | GET `/clinic-profile` | 1 | 公开，字段及内容待审核 |
| 未开发 | GET `/staff/me/qr-code`；POST `/staff/me/qr-token/rotate` | 2 | R5，注册端已经具备消费路径 |
| 未开发 | PATCH `/customers/{id}/status` | 1 | R6，三项状态和审计 |
| 未开发 | GET `/members/me/points-records`、`/admin/points/accounts`、`/admin/points/records` | 3 | R2 本人和 R11 全店查询 |
| 待确认 | POST `/admin/points/adjustments` | 1 | R14 当前拒绝；审批、额度及授权未确认 |
| 未开发 | GET `/products`、`/products/{id}`、`/admin/products`、`/admin/products/{id}`；POST `/admin/products`、`/admin/product-images/upload-tickets`；PATCH `/admin/products/{id}` | 7 | R2、R11 读，R15 管理员写 |
| 未开发 | GET `/admin/products/{id}/stock-records`；POST `/admin/products/{id}/stock-adjustments` | 2 | R11 读、R16 管理员写 |
| 未开发 | GET `/members/me/exchange-orders`、`/admin/exchange-orders`、`/admin/exchange-orders/{id}`；POST `/exchange-orders` | 4 | R2、R11 查询，R4 本人下单 |
| 未开发 | POST `/exchange-orders/{id}/credentials`、`/exchange-orders/{id}/verify`、`/exchange-orders/verify`；GET `/admin/verifications` | 4 | R4 本人签发；R10 店长管理员核销；R11 读；动态参数及普通员工授权待确认 |
| 未开发 | GET `/admin/dashboard`、`/admin/settings`、`/admin/roles`、`/admin/audit-logs` | 4 | R11、R17、R18；时区固定只读 |
| 待确认 | PATCH `/admin/settings/{key}` | 1 | 当前无经批准的可写键 |

## 4. 数据库业务表对应

[冻结 DDL](../sql/database-v1.sql)、[字段字典](../sql/database-schema.md)、[ER 图](../sql/database-er.mmd)和 [SQLAlchemy 模型](../backend/app/db/models.py)覆盖下列 18 张表。[首次迁移验证报告](database-migration-validation.md)记录 186 个字段、32 条外键、23 个显式索引、18 个 CHECK、19 个 UNIQUE，以及结构比对、回滚和重升结果。本次核对仓库文件，未核验部署中的数据库实例，也未运行迁移。

| 表 | 主要业务 | 当前应用使用或后续工作 |
| --- | --- | --- |
| `accounts` | 微信、后台认证 | 登录、账号状态、员工/会员双身份及绑定已使用 |
| `staff_profiles` | 员工、店长、管理员 | 档案、管理员开通、微信绑定、在职校验、停用已使用 |
| `members` | 会员、资料、来源员工 | 注册、脱敏查询、当前归属及订单所有权已使用 |
| `employee_qr_tokens` | 员工客户来源码 | 已用于注册校验和绑定；签发及换码没有应用路径 |
| `customer_assignments` | 当前归属与历史 | 注册首次归属、后台手工分配/转移、数据权限已使用 |
| `customer_status` | 到店、消费、成交、有效联系、复查时间 | 注册建档、读取筛选和有效联系更新已使用；三状态编辑和名单生成待接 |
| `customer_tags` | 客户标签目录 | 有表和模型，未见管理和查询入口；需复核运营标签是否列入当期交付 |
| `member_tag_relations` | 会员与标签关联 | 有表和模型，未见贴标业务；同上 |
| `points_accounts` | 余额和累计积分 | 注册零值、本人查询已接；后台查询、入账和扣减未接 |
| `points_records` | 积分不可变流水 | 有冻结约束、索引与防改写触发器；应用无入账、扣减及查询闭环 |
| `followup_records` | 普通跟进和家访 | 写入、历史、后台筛选已接 |
| `followup_tasks` | 人工、复查和唤醒任务 | 人工任务及状态已接；复查和唤醒生成未接 |
| `products` | 商品、积分价格、月限和库存快照 | 有表和模型；商城及后台商品应用未接 |
| `exchange_orders` | 积分订单和月限统计 | 已接本人详情，未接建单、列表和核销；存在 `(member_id, product_id, created_at)` 复合索引 |
| `product_stock_records` | 库存不可变流水 | 有冻结约束和防改写触发器；调整、扣减和查询未接 |
| `redemption_credentials` | 动态核销凭证 | 有摘要、生命周期及唯一约束；签发、轮换、消费未接 |
| `system_configs` | 系统参数 | 有表和模型；无配置 API 或公开门诊读取。应用配置中的固定时区已存在 |
| `operation_logs` | 审计 | 多个已交付模块写入；后台查询和授权导出未接 |

Redis 承载真实会话、后台登录限流及员工微信绑定邀请。员工绑定邀请与 `employee_qr_tokens` 的会员客户来源码、`redemption_credentials` 的兑换核销凭证分别使用各自的用途和校验。结构约束与索引为未来业务提供基础。当前代码没有兑换事务，也没有实际调用月限索引查询的兑换服务。

## 5. 权限完成情况

| 权限 | 当前生效范围 | 缺口或关闭范围 |
| --- | --- | --- |
| R1 | 微信未注册会话创建本人会员 | 已通过注册和归属测试 |
| R2 | 本人资料、余额和订单详情 API | 积分流水、订单列表及上架商品查询未接 |
| R3 | 默认拒绝 | 会员资料编辑待确认 |
| R4 | 固定角色矩阵允许会员 | 本人兑换和待核销凭证 API 均未接 |
| R5 | 工作身份资料读取 | 员工客户来源码 API 未接 |
| R6 | 员工当前客户；店长、管理员全店；客户查询及跟进家访已接 | 运营三状态写入未接 |
| R7 | 店长、管理员归属历史、候选、分配与转移 | 普通员工无转移权限 |
| R8 | 员工须同时为任务受指派人和客户当前负责人；店长、管理员全店 | 员工状态处理已接；后台目前展示忽略 |
| R9 | 店长、管理员为当前负责人建人工任务 | 自动生成另行确认策略 |
| R10 | 店长和管理员具备基线权限 | 实际核销未接；普通员工待开放 |
| R11 | 店长、管理员全店会员与运营记录已接 | 总览、积分、商品、库存、订单及核销记录未接 |
| R12 | 店长和管理员查询员工档案 | 运营范围不扩展到账号写入 |
| R13 | 管理员开通、邀请、停用与启用普通员工 | 店长仅 R12 只读；角色变更及换绑未开放 |
| R14 | 默认拒绝 | 人工调整和店长授权待确认 |
| R15 | 固定矩阵允许管理员 | 商品写入未接，店长写待确认 |
| R16 | 固定矩阵允许管理员 | 库存调整未接，店长写待确认 |
| R17 | 固定矩阵允许管理员基础读取 | GET 未接，`R17_WRITE` 默认拒绝，店长范围待定，业务时区保持只读 |
| R18 | 固定矩阵允许管理员只读 | 角色目录和审计 GET 均未接；店长范围待定；`R18_WRITE` 拒绝 |

验证来源为[权限实现](../backend/app/auth/permissions.py)、[数据范围](../backend/app/auth/scopes.py)、[固定角色和隔离测试](../backend/tests/test_permissions.py)。有业务路由的功能按服务端会话身份和渠道授权，员工客户权限按当前关系核验。已注册接口对功能无权和不可见对象分别返回 403、404。只有权限规则及未注册路由的能力仍需随功能开发落实路由接入和端到端权限验证。

## 6. 自动化与手动验收

以下结果引用同一 SHA 的 2.6.4 合并收尾记录。本轮是静态盘点，未重跑测试或使用验收数据执行写操作。

| 端 | 基线回归 | 业务测试证据 |
| --- | --- | --- |
| 后端 | pytest 79 通过、1 项迁移集成测试跳过。mypy 36 个源文件通过，wheel 和 sdist 构建成功 | [认证](../backend/tests/test_auth.py)、[会员注册及资料](../backend/tests/test_member_registration.py)、[权限隔离](../backend/tests/test_permissions.py)、[目录](../backend/tests/test_directory.py)、[分配和转移](../backend/tests/test_assignments.py)、[员工账号](../backend/tests/test_staff_accounts.py)、[跟进任务](../backend/tests/test_followups.py) |
| 管理后台 | TypeScript、Vitest 17 项、Vite 生产构建通过，构建有大分块警告 | [路由和会话](../admin-web/src/App.test.tsx)、[归属契约](../admin-web/src/assignment-api.test.ts)、[员工管理](../admin-web/src/staff-account.test.tsx)、[跟进契约](../admin-web/src/followup-api.test.ts) |
| 小程序 | TypeScript、自动化 18 项通过 | [登录、资料、积分余额、员工及家访任务](../miniprogram/tests/member-auth.test.cjs)、[路由和页面栈](../miniprogram/tests/navigation.test.cjs)。商城导航测试覆盖页面跳转，实际建单与核销必须另验 |

手动验收证据来自负责人在任务中明确确认的阶段范围：2.3 后台工程与功能框架、2.4 三端路由、2.5.1–2.5.6 认证交付（其中 2.5.4 微信登录注册及资料补齐有单独确认）、2.6.1 目录与员工客户、2.6.2 归属、2.6.3 员工账号、2.6.4 跟进和回访。仓库中的 [2.5.4 指南](manual-test-2.5.4.md)、[2.6.3 指南](manual-test-2.6.3.md)和 [2.6.4 指南](manual-test-2.6.4.md)记录操作和预期结果。指南单独存在时，不推定所有用例均已执行；隔离凭据登录、模拟器编译、测试数据准备和自动化通过分别记录，不作为阶段业务验收的替代。积分兑换的跨月、竞争、重复提交、回滚和动态核销仍是[测试设计](test-cases.md)，尚无当前代码的端到端业务测试。

## 7. open-questions 遗留事项

逐项核对 [open-questions.md](open-questions.md)。下表拆开同一条目中的已确认范围和未决定事项。关闭范围按已确认的业务决定记录。

| 原条目 | 已确认、已实现或被后续规则取代 | 未决定或已确认尚未开发 |
| --- | --- | --- |
| 会员资料 | **已实现并通过验证**：本人读取、手机号默认脱敏。会员注册字段及手机号无需短信、可共用已由负责人确认 | **仍待负责人决定**：允许编辑的字段、修改流程及验证方式；R3 保持关闭 |
| 员工账号 | **已实现并通过验证**：原先账号如何开通、员工登录和首绑的待定方案已被 2.6.3 规则取代。管理员开通、十分钟一次性现场邀请、员工独立微信入口、同账号可兼任、停用仅撤员工会话 | **仍待负责人决定**：微信解绑/重绑、同一会话切换身份、后台代录客户。角色变更另待批 |
| 归属交接 | **已实现并通过验证**：店长和管理员首次分配、单人转移、保留来源和历史；原页面清单的员工端转移设想已由 R7 后台方案取代。2.6.2 未包含审批、自动或批量分配 | **仍待负责人决定**：离职客户处理、是否额外审批。2.6.4 已明确旧任务不自动转移，可由管理人员忽略后给新负责人建新任务 |
| 积分发放 | **已由负责人确认**：注册赠分关闭，初始余额为零且已验证。不可变流水、幂等原子扣减为冻结要求 | **已确认但尚未开发**：扣减与流水闭环。**仍待负责人决定**：积分来源、计算、有效期、人工调整审核及额度。R14 暂不开 |
| 商品和库存 | **已由负责人确认**：月限、时区和订单计量、库存扣减和流水原则；R15/R16 管理员基线写权限。商城、库存和限兑应用 **尚未开发** | **仍待负责人决定**：上架或兑换时间窗、下调月上限后的展示及处理、店长商品和库存写权限 |
| 核销与领取 | **已确认但尚未开发**：服务端动态凭证、一次消费、同一订单只成功一次，店长/管理员有 R10 基线权限；订单取消和退款明确排除 | **仍待负责人决定**：有效时长、刷新参数和触发规则、逾期领取的运营处理、普通员工核销权限 |
| 回访 | **已实现并通过验证**：2.6.4 人工任务、重复延期更新同一任务、完成与忽略终态；任务与跟进独立。手动联系和无消息通知边界已确认 | **已确认但尚未开发**：系统生成复查/唤醒名单。**仍待负责人决定**：阈值、生成时间、去重窗口，以及自动生成任务是否另有延期约束。人工任务的多次延期无需重新讨论 |
| 后台授权 | **已实现并通过验证**：管理员与店长可用已有有效账号登录，店长不具 R13 员工写权限。默认脱敏已接通相关查询 | **仍待负责人决定**：首个管理员开通、店长积分调整/系统设置/审计授权、配置写入键、手机号明文、导出与保留策略。管理员审计和角色目录读取虽有权限基线，应用尚未接 |
| 页面视觉基线 | 已有路由和文字版视觉规范 | **仍待负责人决定**：可访问的 Figma 版本及逐页冻结确认。本次无法访问 Frame |
| 文末已确认事项 | **已由负责人确认**：`BUSINESS_TIMEZONE=Asia/Shanghai`，按订单 `created_at` 归属自然月；无取消及退款。时区配置已实现 | **已确认但尚未开发**：以月初和下月月初转 UTC 后按左闭右开范围查询，聚合已提交的 `pending`、`verified` 数量并实施并发控制 |

初期交接记录里仍写待确认的注册验证、员工开通首绑、普通员工正式登录、分配转移权限与月限口径，以后续明确确认的规则为准。客户标签是否列入当期、门诊与协议的公开内容及入口也应与负责人对照现行交付范围；没有借本盘点修改决策文件。

## 8. 未完成模块与设计差异

- **积分**：补齐会员流水、后台账户和流水读操作。运营积分如何进入账户是正式兑换验收的前置决策；人工调整在 R14 明确开放前关闭。
- **商品及库存**：页面和数据库具备基础，商城目录、后台商品管理、图片、库存写入与流水查询均未接。
- **兑换及核销**：会员详情 API 是孤立的读取能力。页面演示串联不产生订单。需补真实下单、库存和积分原子扣减、幂等、跨月并发、订单列表、动态凭证和核销。核销有效期等未冻结参数需先确认。
- **会员和客户运营缺口**：员工客户来源码签发换码、公共门诊与政策入口、会员首页身份信息、客户三状态写入、复查/唤醒生成。员工转移页仍出现在历史设计中，现行 R7 以后台分配和转移为准。员工工作台只有资料请求和快捷入口，完整统计未接，待可读视觉稿确认是否需要。
- **管理闭环**：数据总览、系统设置读取、角色目录、审计查询均使用通用占位。认证及运营写路径已有审计记录，可作为日志查询的数据来源。
- **界面范围**：跟进表单只接入 2.6.4 验收要求中的类型和内容。API 已支持下一次跟进时间等可选字段，是否按原型增设表单字段需等视觉和业务复核。后台 R8 可做多种任务状态更新，前端当前仅接入该阶段要求的忽略。
- **边界**：继续按已确认规则关闭预约、临床记录、支付、取消退款和注册赠分。员工核销、会员资料编辑、配置写入等保持待确认。三端导航及工程验收覆盖范围与 V1.0 逐页业务验收范围分别记录。

## 9. 模块依赖关系

| 上游 | 依赖它的能力 |
| --- | --- |
| 会话、角色、会员与员工档案 | 三端授权；会员身份、员工现场绑定和后台管理 |
| 员工档案和客户来源码签发 | 会员扫码注册 → 首次归属 → 员工客户可见范围 |
| 当前归属及运营状态 | 客户详情/跟进/家访 → 人工回访与自动名单；转移后仍按当前归属实时校验 |
| 积分账户和不可变流水 | 会员积分记录、后台积分查询、经批准的积分入账和兑换扣减 |
| 商品、库存快照和不可变库存流水 | 商品浏览、库存调整、下单时库存校验与扣减 |
| 积分扣减、库存扣减、固定业务时区及幂等事务 | 限兑和真实订单创建 → 会员订单列表/详情、后台订单查询 |
| 待核销订单和动态凭证策略 | 凭证签发与轮换 → 店长/管理员核销 → 已核销查询和审计 |
| 各业务模块的读模型及操作日志 | 数据总览、审计查询，及最终三端综合验收 |

## 10. 建议的后续开发顺序

1. **先定发布阻塞项。** 确认积分入账来源及可验收数据路径、动态凭证时长和刷新、逾期处理、视觉基线，并明确待确认功能哪些进入本版。
2. **实现确定的查询和商品库存基础。** 积分读模型、商品读写、管理员库存调整和流水可以并行按已获准权限验收。先用授权测试数据验证，生产积分入账仍按负责人批准策略实现。
3. **实现兑换事务及三端订单闭环。** 依赖已稳定的商品、积分、库存。覆盖北京时间自然月边界、同会员同商品并发、最后库存、流水对账、幂等重试和事务回滚，再接确认、成功、列表和详情页面。
4. **接通凭证和门店核销。** 先按店长和管理员的现行 R10 边界实现，联合验收终态、并发、过期和审计。普通员工仍依据后续决策。
5. **补运营与发布配套。** 员工客户来源码、三状态更新、审计查询可独立推进，自动名单等先定策略。数据总览随后接入已稳定的指标。公共门诊、隐私协议与系统设置读入口按核定内容并行准备。最后用可访问的 Figma 执行逐页比对和三端统一业务验收。
