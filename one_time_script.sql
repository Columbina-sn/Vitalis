-- -- ============================================================
-- -- 升级到 v2.2：新增 login_history 表，调整 users 表字段
-- -- ============================================================

-- USE vitalis;

-- -- 为 users 表增加软删除字段及索引
-- ALTER TABLE users
--     ADD COLUMN is_deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已软删除（0=正常，1=已删除）' AFTER theme_mode,
--     ADD COLUMN deleted_at DATETIME DEFAULT NULL COMMENT '软删除时间' AFTER is_deleted,
--     ADD INDEX idx_users_is_deleted (is_deleted, deleted_at);

-- -- 为 comment 表增加软删除字段及索引
-- ALTER TABLE comment
--     ADD COLUMN is_deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已软删除（0=正常，1=已删除）' AFTER replied,
--     ADD COLUMN deleted_at DATETIME DEFAULT NULL COMMENT '软删除时间' AFTER is_deleted,
--     ADD INDEX idx_comment_is_deleted (is_deleted, deleted_at);

-- ============================================================
-- 升级到 v2.3：锚点轮换机制 + 情绪日记功能
-- ============================================================

-- 为 memory_anchors 表新增轮换机制字段
ALTER TABLE memory_anchors
    ADD COLUMN last_context_at DATETIME NULL COMMENT '上次被选入上下文的时间' AFTER confidence,
    ADD COLUMN consecutive_count INT NOT NULL DEFAULT 0 COMMENT '连续入选上下文的轮数' AFTER last_context_at,
    ADD INDEX idx_user_last_context (user_id, last_context_at);

-- 为 memory_snapshots 表新增情绪日记字段
ALTER TABLE memory_snapshots
    ADD COLUMN diary_content TEXT NULL COMMENT '情绪日记正文（150-200字第二人称）' AFTER summary,
    ADD COLUMN mood_keywords JSON NULL COMMENT '情绪关键词列表' AFTER diary_content;