# 阳光口腔会员运营管理系统 V1.0 — 页面路由与交互状态

## 1. 角色

| 角色 | code | 范围 |
|---|---|---|
| 会员 | member | 仅本人会员、积分、兑换数据 |
| 员工 | employee | 本人负责客户与本人任务 |
| 店长 | manager | 本门店客户/员工，可转移客户 |
| 管理员 | admin | 全局配置、积分、商品、订单、权限 |

## 2. 会员端路由

| 页面 | 建议路径 | 进入条件 | 关键参数 | 主要去向 |
|---|---|---|---|---|
| 登录/身份初始化 | `/pages/auth/index` | 未初始化会话 | `sceneToken?` | 注册/首页 |
| 会员注册 | `/pages/member/register` | 已登录但未建会员 | `sceneToken?` | 首页 |
| 首页 | `/pages/member/home` | member | - | 积分/商城/个人中心 |
| 积分明细 | `/pages/points/index` | member | - | 首页 |
| 积分商城 | `/pages/mall/index` | member | `category?` | 商品详情 |
| 商品详情 | `/pages/mall/detail` | member | `productId` | 兑换确认 |
| 兑换确认 | `/pages/mall/confirm` | member | `productId`,`quantity` | 兑换成功 |
| 兑换成功 | `/pages/mall/success` | member | `orderId` | 我的兑换/商城 |
| 我的兑换 | `/pages/orders/index` | member | `status?` | 订单详情 |
| 个人中心 | `/pages/member/profile` | member | - | 资料/积分/兑换 |

### 会员端主流程

`扫码员工二维码 → auth → 注册/登录 → 服务端验证 sceneToken → 建立会员 → 首次归属绑定 → 注册积分 → 首页`

`首页 → 积分商城 → 商品详情 → 兑换确认 → 服务端事务兑换 → 兑换成功 → 到店核销`

## 3. 员工端路由

| 页面 | 建议路径 | 角色 | 参数 | 关键交互 |
|---|---|---|---|---|
| 工作台 | `/pages/staff/dashboard` | employee+ | - | 查看今日任务/客户 |
| 我的二维码 | `/pages/staff/qrcode` | employee+ | - | 获取服务端签发二维码 |
| 我的客户 | `/pages/staff/customers` | employee+ | `filter?` | 搜索/筛选客户 |
| 客户详情 | `/pages/staff/customer-detail` | employee+ | `customerId` | 状态/标签/跟进 |
| 添加跟进 | `/pages/staff/followup-create` | employee+ | `customerId` | 新增联系记录 |
| 跟进历史 | `/pages/staff/followup-history` | employee+ | `customerId` | 时间线 |
| 家访记录 | `/pages/staff/home-visit` | employee+ | `customerId` | 新增线下家访 |
| 跟进任务 | `/pages/staff/tasks` | employee+ | `taskType?`,`status?` | 完成/延期/忽略 |
| 客户转移 | `/pages/staff/transfer` | manager/admin | `customerId` | 更换当前负责人 |

### 客户详情交互状态

客户详情必须同时展示三组独立状态：

- `visit_status`: `not_visited | visited`
- `consume_status`: `not_consumed | consumed`
- `deal_status`: `not_dealt | dealt`

不可合并成单一“客户状态”。

## 4. 管理后台路由

| 页面 | 路径 | 角色 | 说明 |
|---|---|---|---|
| 登录 | `/login` | manager/admin | 管理后台认证 |
| 数据总览 | `/dashboard` | manager/admin | 运营指标 |
| 会员管理 | `/members` | manager/admin | 查询/筛选/详情 |
| 会员详情 | `/members/:id` | manager/admin | 归属/积分/跟进 |
| 员工管理 | `/employees` | manager/admin | 员工状态/二维码/客户数 |
| 员工详情 | `/employees/:id` | manager/admin | 员工及名下客户 |
| 客户归属 | `/assignments` | manager/admin | 归属历史/转移 |
| 客户跟进 | `/followups` | manager/admin | 全部跟进记录 |
| 复查提醒 | `/tasks` | manager/admin | recall/reactivation/manual |
| 积分账户 | `/points/accounts` | admin | 积分余额查询 |
| 积分流水 | `/points/records` | admin | 不可变流水 |
| 商品管理 | `/mall/products` | admin | 上下架/库存 |
| 兑换订单 | `/mall/orders` | manager/admin | 核销/异常处理 |
| 系统设置 | `/settings` | admin | 积分/提醒/标签/门店 |
| 操作日志 | `/audit-logs` | admin | 敏感操作审计 |

## 5. 通用页面状态

所有列表页至少实现：

- `loading`
- `success`
- `empty`
- `error`
- `refreshing`
- `no_permission`

所有提交型页面至少实现：

- `idle`
- `validating`
- `submitting`
- `success`
- `business_error`
- `network_error`

## 6. 关键业务交互规则

1. 已归属会员扫描其他员工二维码：不得自动覆盖当前负责人；
2. 客户转移：manager/admin 才能执行，并保留完整历史；
3. 注册奖励：每个会员只可发放一次；
4. 积分兑换按钮：点击后必须防重复提交；
5. 订单核销：已核销订单不得重复核销；
6. 员工二维码场景参数：前端不得信任裸 `employee_id`，必须使用服务端签发的 `scene_token`；
7. 会员端手机号等隐私信息仅展示必要范围；员工列表默认脱敏；
8. 权限控制必须由服务端最终判断，前端隐藏按钮不等于权限校验。

## 7. 提醒模型

V1.0 将“复查”和“沉睡唤醒”区分处理：

- `recall`：基于明确的 `next_recall_at`（或门诊设定的复查日期）；
- `reactivation`：基于 `last_effective_contact_at`，默认 90/180/365 天；
- `manual`：员工/管理员手工创建。
