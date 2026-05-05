-- ============================================================
-- Vitalis 数据库 v2.0 → v2.1 升级脚本
-- 适用场景：已有 v2.0 版本数据库，仅需升级调整
-- 注意：执行前请备份数据
-- ============================================================

USE vitalis;

-- 1. 向 users 表添加三个新字段
ALTER TABLE users
    ADD COLUMN current_token VARCHAR(500) DEFAULT NULL COMMENT '当前登录JWT令牌' AFTER invite_code,
    ADD COLUMN current_login_ip VARCHAR(45) DEFAULT NULL COMMENT '当前登录IP地址' AFTER current_token,
    ADD COLUMN theme_mode TINYINT UNSIGNED NOT NULL DEFAULT 2 COMMENT '主题模式：0-浅色，1-深色，2-跟随系统' AFTER current_login_ip;

-- 2. 从 emotion_shifts 表删除 trigger_keywords 字段
ALTER TABLE emotion_shifts DROP COLUMN trigger_keywords;

-- 3. 从 memory_anchors 表删除 last_mentioned_at 字段及其索引
ALTER TABLE memory_anchors DROP INDEX idx_user_last_mentioned;
ALTER TABLE memory_anchors DROP COLUMN last_mentioned_at;