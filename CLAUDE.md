# Claude Code 规则
项目：阳光口腔会员运营管理系统 V1.0。单门店，只服务阳光口腔。禁止引入多门店、门店切换、store_id、跨门店权限或未来多门店预留抽象。

## 开发前阅读
README.md 及 docs/ 下 business-rules、open-questions、ui-freeze、navigation、permissions、tech-stack、database-schema、api-spec、test-cases。

## 固定技术栈
微信原生小程序 + TypeScript + TDesign；React + TypeScript + Vite + Ant Design 5；Python + FastAPI + Pydantic 2；SQLAlchemy 2 + Alembic；PostgreSQL；Redis + Celery；COS；Docker Compose + Nginx。模块化单体，不拆微服务。

## 已确认规则
- 单门店；不接支付；不存储临床病历/诊断/影像/治疗方案。
- 会员与员工共用一个小程序。会员微信登录后填写姓名、生日、手机号。
- 员工二维码使用服务端签发 scene_token；新会员首次扫码绑定员工。
- 已有负责人的会员再次扫描其他员工二维码不得自动改绑。
- 到店、消费、成交是三个独立状态。
- 系统生成复查/唤醒名单，员工手动联系。
- 家访和到店回访均支持，统一记录。
- 积分变动必须写不可变流水；兑换必须事务化、幂等。
- 客户转移必须保留历史。

## 待确认规则
以 docs/open-questions.md 为准。未确认前不得写死积分数值、有效期、领取期限、提醒阈值、员工登录方式；不得把旧建议值当最终规则。

## 工程规范
后端校验全部权限；微信身份由后端临时 code 换取；手机号加密、默认脱敏；数据库变更使用 Alembic；API 前缀 /api/v1；关键操作事务、幂等、审计；密钥仅放环境变量。一次只做一个明确任务，完成后报告变更、运行和测试；不明确先提问。
