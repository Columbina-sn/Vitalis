-- ============================================================
-- 升级到 v2.2：新增 login_history 表，调整 users 表字段
-- ============================================================

USE vitalis;

-- 2.1 重命名并修改 current_token 字段（改为存储 JTI）
ALTER TABLE users
    CHANGE COLUMN current_token current_token_jti VARCHAR(128) DEFAULT NULL COMMENT '当前会话JWT唯一ID';

-- 2.2 新增 current_location 字段
ALTER TABLE users
    ADD COLUMN current_location VARCHAR(100) DEFAULT NULL COMMENT '最近登录的城市信息' AFTER current_login_ip;

-- 2.3 创建登录历史表
CREATE TABLE IF NOT EXISTS login_history (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    user_id INT UNSIGNED NOT NULL COMMENT '关联用户',
    login_ip VARCHAR(45) NOT NULL COMMENT '登录IP',
    location VARCHAR(100) DEFAULT NULL COMMENT 'IP解析的城市',
    device_info VARCHAR(200) DEFAULT NULL COMMENT '设备/浏览器信息',
    token_jti VARCHAR(128) NOT NULL COMMENT 'JWT唯一标识',
    is_valid TINYINT(1) NOT NULL DEFAULT 1 COMMENT '会话是否有效',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '登录时间',
    PRIMARY KEY (id),
    UNIQUE KEY uq_token_jti (token_jti),
    KEY idx_user_valid (user_id, is_valid),
    CONSTRAINT fk_login_history_user_id FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='登录历史表';