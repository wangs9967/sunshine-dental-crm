# 阳光口腔会员运营管理系统 V1.0 — API / Cloud Functions 清单

> 约定：微信小程序和管理后台不直接执行敏感数据库写操作。API/云函数统一做身份认证、RBAC、参数校验、幂等和审计。

## 1. 通用返回格式

```ts
interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    requestId: string;
  };
}
```

通用错误码：
- `UNAUTHENTICATED`
- `FORBIDDEN`
- `INVALID_ARGUMENT`
- `NOT_FOUND`
- `CONFLICT`
- `RATE_LIMITED`
- `INTERNAL_ERROR`

## 2. Auth / Member

### `login`
- 角色：公开（微信会话）
- 入参：微信登录凭证
- 返回：`session`, `memberExists`, `employeeRole?`
- 说明：不接受客户端传入的 openid 作为可信身份。

### `resolveEmployeeScene`
- 角色：公开/已登录
- 入参：`sceneToken`
- 返回：安全的员工展示信息 + token 状态
- 校验：签名、有效期、员工 active、门店状态

### `registerMember`
- 角色：已登录未注册用户
- 入参：`name,birthday,phone,sceneToken?`
- 事务：是
- 流程：
  1. 检查 openid 未注册；
  2. 创建 users；
  3. 创建 customer_status；
  4. 创建 points_accounts；
  5. 若 sceneToken 合法，记录 `source_employee_id` 并建立首次归属；
  6. 调用注册积分幂等逻辑；
  7. 写审计/业务日志。
- 错误：`MEMBER_ALREADY_EXISTS`, `INVALID_SCENE_TOKEN`

### `getMemberProfile`
- 角色：member
- 返回：本人会员资料（最小必要字段）

### `updateMemberProfile`
- 角色：member
- 入参：允许修改字段白名单

## 3. Employee / QR

### `getEmployeeProfile`
- 角色：employee+

### `generateEmployeeQRCode`
- 角色：employee+
- 返回：小程序二维码/临时地址
- 规则：二维码 scene 使用服务端签发的 opaque token，不直接信任 `employee_id`。

### `getMyCustomers`
- 角色：employee+
- 入参：`keyword,statusFilters,tags,page,pageSize`
- 范围：employee 仅本人当前归属；manager 本门店；admin 按管理接口处理

### `getCustomerDetail`
- 角色：employee+
- 入参：`customerId`
- 权限：先校验当前归属/门店范围

## 4. Assignment

### `bindCustomerToEmployee`
- 内部调用为主
- 用于新会员首次扫码绑定
- 已存在当前负责人时不得覆盖

### `transferCustomer`
- 角色：manager/admin
- 入参：`customerId,newEmployeeId,reason,idempotencyKey`
- 事务：是
- 流程：关闭旧 `is_current` → 新建 assignment → 记录 operation_log
- 错误：`SAME_OWNER`, `TARGET_EMPLOYEE_DISABLED`, `CROSS_STORE_FORBIDDEN`

### `getAssignmentHistory`
- 角色：manager/admin

## 5. Customer CRM

### `updateCustomerStatus`
- 角色：employee+
- 入参：`customerId,visitStatus?,consumeStatus?,dealStatus?`
- 权限：员工仅本人客户

### `getTags`
- 角色：employee+

### `addCustomerTag` / `removeCustomerTag`
- 角色：employee+
- 必须校验客户访问范围

## 6. Follow-up

### `createFollowupRecord`
- 角色：employee+
- 入参：`customerId,type,followupAt,content,feedback,gift,nextFollowupAt,effectiveContact`
- 事务：建议
- 若 `effectiveContact=true`：更新 `customer_status.last_effective_contact_at`

### `getFollowupRecords`
- 角色：employee+
- 入参：`customerId,page,pageSize`

### `getMyFollowupTasks`
- 角色：employee+
- 入参：`taskType,status,dateRange`

### `completeFollowupTask`
- 角色：employee+
- 入参：`taskId,result,nextFollowupAt?`
- 状态机：仅 `pending/postponed → completed`

### `postponeFollowupTask`
- 角色：employee+
- 入参：`taskId,nextScheduledAt,reason`

### `ignoreFollowupTask`
- 角色：employee+/manager
- 入参：`taskId,reason`

## 7. Scheduled Functions

### `generateRecallTasks`
- 触发：每日定时
- 依据：`customer_status.next_recall_at`
- 去重：`dedupe_key = recall:{userId}:{date}`

### `generateReactivationTasks`
- 触发：每日定时
- 依据：`last_effective_contact_at`
- 阈值：90/180/365 天（配置化）
- 去重：每个用户、规则、周期只生成一条有效任务

## 8. Points

### `getPointsAccount`
- 角色：member（本人）/admin（查询）

### `getPointsRecords`
- 角色：member（本人）/admin

### `grantRegisterBonus`
- 内部函数
- 幂等键：`register_bonus:{userId}`
- 事务：是
- 规则：查 points_records 幂等键后再发放，禁止只依赖 boolean 标记

### `adjustPoints`
- 角色：admin
- 入参：`userId,amount,reason,idempotencyKey`
- 事务：是
- 操作：账户余额 + 流水 + 审计原子完成
- 错误：`INSUFFICIENT_POINTS`, `DUPLICATE_REQUEST`

## 9. Mall / Product

### `getProducts`
- 角色：member+
- 仅返回 `online` 商品

### `getProductDetail`
- 角色：member+

### `createProduct` / `updateProduct` / `setProductStatus`
- 角色：admin
- 库存和价格只能后端写

## 10. Exchange Order

### `exchangeProduct`
- 角色：member
- 入参：`productId,quantity,idempotencyKey`
- **必须使用数据库事务**
- 原子流程：
  1. 校验商品 online；
  2. 校验数量和限购；
  3. 校验库存；
  4. 校验积分余额；
  5. 扣积分账户；
  6. 新增 points_records（type=exchange）；
  7. 扣商品库存；
  8. 创建 exchange_orders；
  9. 生成核销码。
- 任一步失败全部回滚。
- 错误：`PRODUCT_OFFLINE`,`OUT_OF_STOCK`,`POINTS_NOT_ENOUGH`,`LIMIT_EXCEEDED`,`DUPLICATE_REQUEST`

### `getMyExchangeOrders`
- 角色：member

### `getExchangeOrderDetail`
- 角色：member（本人）/manager/admin

### `verifyExchangeOrder`
- 角色：manager/admin（或明确授权的员工）
- 入参：`orderId/verificationCode,idempotencyKey`
- 原子状态：`pending → verified`
- 防重复核销

### `cancelExchangeOrder`
- 角色：admin（V1）
- 仅允许满足规则的 pending 订单
- 若需要退积分，取消 + 积分退款 + 流水在同一事务中完成

## 11. Admin Queries

### `adminGetDashboard`
- 角色：manager/admin
- manager 限本门店

### `adminGetMembers`
### `adminGetEmployees`
### `adminGetFollowups`
### `adminGetTasks`
### `adminGetPointsRecords`
### `adminGetOrders`

全部支持分页、筛选，并执行数据范围校验。

## 12. System Config / Audit

### `getSystemConfigs`
- 角色：admin

### `updateSystemConfig`
- 角色：admin
- 变更必须写 operation_logs

### `getOperationLogs`
- 角色：admin
- 返回脱敏审计数据

## 13. RBAC 矩阵

| 能力 | member | employee | manager | admin |
|---|---:|---:|---:|---:|
| 查看本人积分 | ✅ | - | - | ✅ |
| 兑换商品 | ✅ | - | - | - |
| 查看本人客户 | - | ✅ | ✅ | ✅ |
| 修改客户状态 | - | ✅(本人客户) | ✅(本店) | ✅ |
| 新增跟进 | - | ✅(本人客户) | ✅(本店) | ✅ |
| 转移客户 | - | ❌ | ✅(本店) | ✅ |
| 人工调整积分 | - | ❌ | ❌ | ✅ |
| 商品管理 | - | ❌ | ❌ | ✅ |
| 核销订单 | - | 按授权 | ✅ | ✅ |
| 系统配置 | - | ❌ | ❌ | ✅ |
| 查看审计日志 | - | ❌ | ❌ | ✅ |

## 14. 云函数目录建议

```text
cloudfunctions/
  auth-login/
  member-register/
  member-profile/
  employee-profile/
  employee-qrcode/
  customer-list/
  customer-detail/
  customer-status-update/
  customer-transfer/
  followup-create/
  followup-list/
  followup-task-list/
  followup-task-complete/
  scheduler-recall/
  scheduler-reactivation/
  points-account/
  points-records/
  points-adjust/
  product-list/
  product-manage/
  exchange-product/
  exchange-orders/
  exchange-verify/
  admin-dashboard/
  system-config/
  audit-logs/
  _shared/
```

`_shared` 统一放：认证、RBAC、错误码、日志、参数校验、幂等、事务辅助、ID/订单号生成。
