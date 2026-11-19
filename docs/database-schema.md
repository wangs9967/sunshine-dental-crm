# 数据库设计基线（PostgreSQL，单门店）
建议实体：accounts、staff_profiles、members、employee_qr_tokens、customer_assignments、customer_status、customer_tags、member_tag_relations、points_accounts、points_records、followup_records、followup_tasks、products、exchange_orders、system_configs、operation_logs。
不创建 stores 表；业务表不含 store_id。手机号加密存储并以 HMAC 检索；日志不写明文。
customer_assignments 对每个会员的当前归属建立部分唯一约束；customer_status 和 points_accounts 对 member_id 唯一。积分流水不可更新/删除。到店、消费、成交独立保存。
兑换时锁定积分账户和商品，检查幂等、上架、库存、积分、限兑；扣积分、流水、库存、订单、核销码同事务完成。客户转移关闭旧归属、新增新归属并审计。
