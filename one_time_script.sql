-- ============================================================
-- 升级到 v2.2：新增 login_history 表，调整 users 表字段
-- ============================================================

USE vitalis;

-- 为 users 表增加软删除字段及索引
ALTER TABLE users
    ADD COLUMN is_deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已软删除（0=正常，1=已删除）' AFTER theme_mode,
    ADD COLUMN deleted_at DATETIME DEFAULT NULL COMMENT '软删除时间' AFTER is_deleted,
    ADD INDEX idx_users_is_deleted (is_deleted, deleted_at);

-- 为 comment 表增加软删除字段及索引
ALTER TABLE comment
    ADD COLUMN is_deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已软删除（0=正常，1=已删除）' AFTER replied,
    ADD COLUMN deleted_at DATETIME DEFAULT NULL COMMENT '软删除时间' AFTER is_deleted,
    ADD INDEX idx_comment_is_deleted (is_deleted, deleted_at);