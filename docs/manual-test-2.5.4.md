# 2.5.4 手动测试指南

使用已初始化的本地测试库和专用测试微信身份。姓名、生日、手机号都填测试数据。

## 1. 测试前准备

1. 安装 Docker Desktop、Python 3.12、uv、Node.js 22 和微信开发者工具。打开 Docker Desktop，等状态显示正在运行。
2. 在项目根目录打开 PowerShell。确认根目录有本地 `.env`，其中的 PostgreSQL 和 Redis 参数指向本机。启动两个服务。

   ```powershell
   docker compose --env-file .env -f deploy/docker-compose.dev.yml up -d postgres redis
   docker compose --env-file .env -f deploy/docker-compose.dev.yml ps
   ```

   两个服务均应显示 `healthy`。测试库需要已有阳光口腔 V1.0 表结构。如果拿到的是空库，请向项目负责人获取已初始化的测试库。本轮验收无需执行迁移。

3. 从负责人处获取一个可用于真实换码的**测试小程序 AppID、对应 AppSecret 和微信开发权限**。在根目录 `.env` 设置 `WECHAT_APP_ID`、`WECHAT_APP_SECRET`。然后在 `PHONE_ENCRYPTION_KEY`、`PHONE_LOOKUP_HMAC_KEY` 各填一把不同的 32 字节 Base64 密钥。可运行下方命令生成两行，分别粘贴。已用于本地测试数据的密钥应保留。

   ```powershell
   uv run --project backend --locked python -c "import secrets; print(secrets.token_urlsafe(32) + '='); print(secrets.token_urlsafe(32) + '=')"
   ```

   AppSecret 和两把密钥只填写在后端 `.env`。

4. 在另一窗口进入 `backend`，启动 FastAPI。

   ```powershell
   uv sync --locked --python 3.12 --extra dev
   uv run --locked --extra dev python -m app.check_dependencies
   uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 18081
   ```

   本机浏览器打开 `http://127.0.0.1:18081/health` 应看到 `{"status":"ok"}`。前一条连接检查命令应分别显示 PostgreSQL 和 Redis 已连接。

5. 再开一个窗口进入 `miniprogram`，执行 `npm.cmd ci`。打开微信开发者工具，登录获授权的开发微信，选择「导入项目」，目录选择仓库内的 `miniprogram`，填第 3 步的同一个 AppID。选「工具 → 构建 npm」，再点「编译」。仅在本地模拟器测试 HTTP 时，可在项目详情的本地设置中开启「不校验合法域名」。
6. 模拟器默认访问本机 `127.0.0.1:18081`。普通手机上的 `127.0.0.1` 指向手机本身。真机扫码或体验版测试需要用手机可访问的 HTTPS 测试服务和已配置的微信请求合法域名，并将 `miniprogram/config/environment.ts` 的发布 API 地址设为该 HTTPS 地址。不要把本地数据库或 Redis 暴露到公网。

**通过标准**　依赖连接成功。模拟器能显示「会员登录」和「微信登录」。真实流程使用能换码的 AppID，游客模式和「演示会员端」仅用于预览。

## 2. 首次会员登录

| 操作 | 预期 | 通过标准 |
|---|---|---|
| 用一个尚未在测试库注册的微信身份打开小程序，点击「微信登录」。 | 打开「填写会员资料」。 | 表单包含姓名、生日和手机号三个字段，无验证码。 |

## 3. 会员注册

| 操作 | 预期 | 通过标准 |
|---|---|---|
| 填姓名 `254家庭甲`，选择 `2000-01-01`，填写测试手机号 `19900000000`，点击「提交注册」。 | 提示「注册成功」，进入「会员首页」。 | 不再次要求登录或填写资料。 |
| 点击底部「积分」。 | 显示「当前积分：0 分」。 | 读到 0 分，且未产生注册赠分。 |

## 4. 重复登录

| 操作 | 预期 | 通过标准 |
|---|---|---|
| 从「我的」点击「退出登录」，回到入口后用同一个微信身份点击「微信登录」。 | 直接进入会员首页。 | 不再出现注册表单，积分仍为 0。 |

## 5. 家庭共用手机号

| 操作 | 预期 | 通过标准 |
|---|---|---|
| 准备同一个测试 AppID 下两个不同的微信身份。用第二个身份注册 `254家庭乙`，选不同生日，填与甲相同的测试手机号。 | 乙也能注册，积分为 0。 | 两个身份分别进入各自的会员档案，没有因手机号相同而冲突。 |

独立档案可请测试环境维护人员在本地测试库执行下方查询。预期结果为 `2 / 2 / 1`，分别代表两条会员记录、两个账号和同一个手机号检索值。

```sql
SELECT count(*), count(DISTINCT account_id), count(DISTINCT phone_search_hash)
FROM members WHERE name IN ('254家庭甲', '254家庭乙');
```

如开发者工具无法切换两个测试微信身份，可用两台获得测试权限的手机。真机连接按第 1 部分准备。

## 6. 员工来源二维码

让测试环境维护人员先准备两个有效来源码，分别来自测试员工甲和乙。本阶段无需开通员工登录，也可在已初始化的本地测试库准备来源码。在项目根目录复制运行下面的 PowerShell。若本地数据库用户或库名已改动，将命令中的 `sunshine`、`sunshine_dental` 替换为本地值。

```powershell
$sceneA = [guid]::NewGuid().ToString('N')
$sceneB = [guid]::NewGuid().ToString('N')
@'
INSERT INTO accounts (username) VALUES ('qa254-source-a'), ('qa254-source-b')
ON CONFLICT (username) DO NOTHING;
INSERT INTO staff_profiles (account_id, display_name, role)
SELECT id, CASE username WHEN 'qa254-source-a' THEN '254员工甲' ELSE '254员工乙' END, 'employee'
FROM accounts WHERE username IN ('qa254-source-a', 'qa254-source-b')
ON CONFLICT (account_id) DO NOTHING;
INSERT INTO employee_qr_tokens (staff_id, token_hash, expires_at)
SELECT s.id, sha256(convert_to(CASE a.username WHEN 'qa254-source-a' THEN :'scene_a' ELSE :'scene_b' END, 'UTF8')),
       now() + interval '1 hour'
FROM staff_profiles s JOIN accounts a ON a.id=s.account_id
WHERE a.username IN ('qa254-source-a', 'qa254-source-b');
'@ | docker compose --env-file .env -f deploy/docker-compose.dev.yml exec -T postgres psql -v ON_ERROR_STOP=1 -U sunshine -d sunshine_dental -v "scene_a=$sceneA" -v "scene_b=$sceneB"
"员工甲来源码 $sceneA"
"员工乙来源码 $sceneB"
```

在微信开发者工具「普通编译 → 添加编译模式」选择启动页 `pages/auth/index`，启动参数设为 `scene=员工甲来源码实际值`，保存后编译。模拟器此操作验证扫码入参及绑定，真实扫码需由测试 AppID 的维护人员生成携带同一 `scene` 的可扫小程序码，再由获授权的手机扫描。

| 操作 | 预期 | 通过标准 |
|---|---|---|
| 使用未注册的测试微信身份，从员工甲来源码进入，注册姓名 `254扫码会员`。 | 注册成功，显示「已关联员工」。 | 首次来源和当前负责人均为员工甲。 |
| 退出，用同一微信身份从员工乙来源码重新进入。 | 直接登录会员首页。 | 首次来源和当前负责人仍为员工甲，当前归属只有一条。 |

维护人员可通过以下查询核对两次结果。

```sql
SELECT m.name, m.register_source, s.display_name AS first_source, c.display_name AS current_owner
FROM members m
LEFT JOIN staff_profiles s ON s.id=m.source_employee_id
LEFT JOIN customer_assignments ca ON ca.member_id=m.id AND ca.is_current
LEFT JOIN staff_profiles c ON c.id=ca.staff_id
WHERE m.name='254扫码会员';
```

## 7. 异常测试

| 操作 | 预期 | 通过标准 |
|---|---|---|
| 在本地测试后端临时清空 `WECHAT_APP_SECRET`，重启 FastAPI，点击「微信登录」。测试完恢复配置并重启。 | 提示「微信登录暂不可用，请联系门诊」。 | 留在入口，提示不显示 AppSecret 或上游原始内容。 |
| 暂停本地 FastAPI，再点击「微信登录」或提交尚未完成的注册表单。恢复服务后重试。 | 提示连接失败，注册页保留已填内容。 | 不进入会员首页，服务恢复后可重试。 |
| 新会员连续点击「提交注册」，退出后用同一微信身份重新登录。 | 只创建一个会员，登录直接进入首页。 | 用第 5 部分的查询按该姓名核对只有一个会员。接口并发冲突另有自动化测试。 |
| 用未注册的身份按第 6 部分进入，启动参数改为 `scene=invalid-254`，填写资料并提交。 | 提示注册成功且来源码无效或过期。 | 可进入会员首页且积分为 0，查询首次来源与当前负责人均为空。 |

## 8. 常见问题

- **AppID 不对**。核对微信开发者工具项目 AppID 和后端 `WECHAT_APP_ID` 完全一致。确认当前微信已被有权人员加入测试小程序，游客 AppID 只用于预览。
- **微信登录失败**。重新点击按钮获取新 code。检查测试 AppSecret 是否与 AppID 匹配、后端能否访问微信、以及开发工具是否能访问 `/health`。配置变更后重启 FastAPI。
- **手机无法连接本地后端**。手机使用第 1 部分的 HTTPS 测试服务，避免使用电脑的环回地址。确认微信公众平台已配置该请求域名。
- **数据库连接失败**。检查 Docker Desktop 已运行、PostgreSQL 显示 `healthy`，核对根目录 `.env` 中的库名、用户名、密码和端口，再运行第 4 步连接检查。若连接正常但表不存在，联系负责人更换已初始化测试库。

自动化用模拟微信接口验证流程。真实换码、两个真实测试微信身份和真机扫码按上述条件单独验收。
