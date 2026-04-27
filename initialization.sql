-- ============================================================
-- Vitalis 数据库初始化脚本 v2.0
-- 重构内容：废除 event 表，新增 emotion_shifts、memory_snapshots、
--           memory_anchors、user_schedule 四张表
-- ============================================================

CREATE DATABASE IF NOT EXISTS vitalis
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE vitalis;

-- -------------------------------------------
-- 1. 用户表
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    phone VARCHAR(15) NOT NULL COMMENT '手机号',
    password VARCHAR(64) NOT NULL COMMENT '登录密码',
    nickname VARCHAR(15) DEFAULT NULL COMMENT '昵称',
    avatar VARCHAR(500) DEFAULT '/static_pic/default_avatar.jpg' COMMENT '头像URL',
    has_seen_intro TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已看过引导介绍（0-未看，1-已看）',
    can_login TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否允许登录（0-禁止，1-允许）',
    invite_code VARCHAR(8) DEFAULT NULL COMMENT '用户注册时使用的邀请码',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_phone (phone),
    KEY idx_invite_code (invite_code),
    KEY idx_users_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- -------------------------------------------
-- 2. 用户状态表
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS user_status (
    user_id INT UNSIGNED NOT NULL COMMENT '用户ID（主键，关联users表）',
    physical_vitality TINYINT UNSIGNED NOT NULL DEFAULT 50 COMMENT '身心活力（0-100）',
    emotional_tone TINYINT UNSIGNED NOT NULL DEFAULT 50 COMMENT '情绪基调（0-100）',
    relationship_connection TINYINT UNSIGNED NOT NULL DEFAULT 50 COMMENT '关系联结（0-100）',
    self_worth TINYINT UNSIGNED NOT NULL DEFAULT 50 COMMENT '自我价值（0-100）',
    meaning_direction TINYINT UNSIGNED NOT NULL DEFAULT 50 COMMENT '意义方向（0-100）',
    psychological_harmony_index TINYINT UNSIGNED NOT NULL DEFAULT 63 COMMENT '心理和谐指数（1-100）',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (user_id),
    CONSTRAINT fk_user_status_user_id FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_physical_vitality CHECK (physical_vitality BETWEEN 0 AND 100),
    CONSTRAINT chk_emotional_tone CHECK (emotional_tone BETWEEN 0 AND 100),
    CONSTRAINT chk_relationship_connection CHECK (relationship_connection BETWEEN 0 AND 100),
    CONSTRAINT chk_self_worth CHECK (self_worth BETWEEN 0 AND 100),
    CONSTRAINT chk_meaning_direction CHECK (meaning_direction BETWEEN 0 AND 100),
    CONSTRAINT chk_psychological_harmony_index CHECK (psychological_harmony_index BETWEEN 1 AND 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户状态表（记录五维活力指标+心理和谐指数）';

-- -------------------------------------------
-- 3. 情绪转折表（取代原 event 表）
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS emotion_shifts (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    user_id INT UNSIGNED NOT NULL COMMENT '所属用户ID',
    emotion_change_detail TEXT NOT NULL COMMENT '情绪变化的详细描述',
    trigger_keywords VARCHAR(500) DEFAULT NULL COMMENT '触发该情绪转折的关键词，以逗号分隔',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_user_created (user_id, created_at),
    CONSTRAINT fk_emotion_shifts_user_id FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='情绪转折表';

-- -------------------------------------------
-- 4. 邀请码表
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS invite_code (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    code VARCHAR(8) NOT NULL COMMENT '邀请码',
    expiry_time DATETIME NOT NULL COMMENT '过期时间（该时间点之后邀请码失效）',
    PRIMARY KEY (id),
    UNIQUE KEY uk_code (code),
    KEY idx_expiry_time (expiry_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='邀请码表';

-- -------------------------------------------
-- 5. 对话历史表
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS conversation_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '对话记录主键ID',
    user_id INT UNSIGNED NOT NULL COMMENT '所属用户ID',
    role ENUM('user', 'assistant') NOT NULL COMMENT '消息角色：user-用户提问，assistant-AI回复',
    content TEXT NOT NULL COMMENT '消息文本内容',
    metadata JSON NULL COMMENT '附加元数据（例如AI返回的状态变更、建议等结构化数据）',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_user_time (user_id, created_at) COMMENT '用户+时间索引',
    CONSTRAINT fk_conversation_user_id FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对话历史表';

-- -------------------------------------------
-- 6. 评论表
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS comment (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '评论主键ID',
    content TEXT NOT NULL COMMENT '评论内容',
    ip_address VARCHAR(45) NOT NULL COMMENT '评论者IP地址（支持IPv4/IPv6）',
    replied TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已回复（0-未回复，1-已回复）',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_ip_time (ip_address, created_at) COMMENT '用于频率限制查询的索引',
    INDEX idx_comment_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评论表';

-- -------------------------------------------
-- 7. 用户状态历史表
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS user_status_history (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '历史记录主键ID',
    user_id INT UNSIGNED NOT NULL COMMENT '用户ID',
    physical_vitality TINYINT UNSIGNED NOT NULL COMMENT '身心活力（0-100）',
    emotional_tone TINYINT UNSIGNED NOT NULL COMMENT '情绪基调（0-100）',
    relationship_connection TINYINT UNSIGNED NOT NULL COMMENT '关系联结（0-100）',
    self_worth TINYINT UNSIGNED NOT NULL COMMENT '自我价值（0-100）',
    meaning_direction TINYINT UNSIGNED NOT NULL COMMENT '意义方向（0-100）',
    psychological_harmony_index TINYINT UNSIGNED NOT NULL COMMENT '心理和谐指数（1-100）',
    recorded_at DATETIME NOT NULL COMMENT '状态记录时间（即状态更新的时间点）',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '历史记录创建时间',
    PRIMARY KEY (id),
    KEY idx_user_recorded (user_id, recorded_at) COMMENT '按用户及记录时间排序查询',
    KEY idx_physical_vitality (physical_vitality),
    KEY idx_emotional_tone (emotional_tone),
    KEY idx_relationship_connection (relationship_connection),
    KEY idx_self_worth (self_worth),
    KEY idx_meaning_direction (meaning_direction),
    KEY idx_psychological_harmony_index (psychological_harmony_index),
    CONSTRAINT fk_status_history_user_id FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_history_physical_vitality CHECK (physical_vitality BETWEEN 0 AND 100),
    CONSTRAINT chk_history_emotional_tone CHECK (emotional_tone BETWEEN 0 AND 100),
    CONSTRAINT chk_history_relationship_connection CHECK (relationship_connection BETWEEN 0 AND 100),
    CONSTRAINT chk_history_self_worth CHECK (self_worth BETWEEN 0 AND 100),
    CONSTRAINT chk_history_meaning_direction CHECK (meaning_direction BETWEEN 0 AND 100),
    CONSTRAINT chk_history_psychological_harmony_index CHECK (psychological_harmony_index BETWEEN 1 AND 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户状态历史表';

-- -------------------------------------------
-- 8. 系统配置表
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS system_config (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '配置项主键ID',
    config_key VARCHAR(64) NOT NULL COMMENT '配置键名（唯一）',
    config_value TEXT NOT NULL COMMENT '配置值',
    description VARCHAR(255) DEFAULT NULL COMMENT '配置项说明',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

-- 初始化配置
INSERT INTO system_config (config_key, config_value, description)
VALUES ('admin_login_enabled', 'true', '是否允许管理员登录（true/false）')
ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;

-- -------------------------------------------
-- 9. 管理员操作日志表
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS admin_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '日志主键ID',
    admin_phone VARCHAR(15) NOT NULL COMMENT '执行操作的管理员手机号',
    action_type VARCHAR(32) NOT NULL COMMENT '操作类型',
    target_table VARCHAR(64) DEFAULT NULL COMMENT '操作影响的目标表名',
    target_id BIGINT DEFAULT NULL COMMENT '操作影响的记录主键ID',
    before_snapshot JSON DEFAULT NULL COMMENT '操作前的数据快照（JSON格式）',
    after_snapshot JSON DEFAULT NULL COMMENT '操作后的数据快照（JSON格式）',
    request_ip VARCHAR(45) NOT NULL COMMENT '操作请求的IP地址',
    user_agent VARCHAR(512) DEFAULT NULL COMMENT '操作请求的User-Agent',
    remark VARCHAR(255) DEFAULT NULL COMMENT '备注',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '日志记录时间',
    PRIMARY KEY (id),
    KEY idx_admin_phone (admin_phone),
    KEY idx_action_type (action_type),
    KEY idx_created_at (created_at),
    KEY idx_target (target_table, target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管理员操作日志表';

-- -------------------------------------------
-- 10. 记忆快照表（对话摘要）
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS memory_snapshots (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '快照主键ID',
    user_id INT UNSIGNED NOT NULL COMMENT '所属用户ID',
    summary TEXT NOT NULL COMMENT '一天全对话的总结摘要',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '快照生成时间',
    PRIMARY KEY (id),
    KEY idx_user_created_snapshot (user_id, created_at),
    CONSTRAINT fk_memory_snapshots_user_id FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='记忆快照表（每日对话摘要）';

-- -------------------------------------------
-- 11. 记忆锚点表（用户画像）
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS memory_anchors (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '锚点主键ID',
    user_id INT UNSIGNED NOT NULL COMMENT '所属用户ID',
    anchor_type VARCHAR(32) NOT NULL COMMENT '锚点类型（如 habit, preference, relationship 等）',
    content TEXT NOT NULL COMMENT '锚点内容（具体画像条目）',
    confidence DECIMAL(3,2) NOT NULL DEFAULT 0.00 COMMENT 'AI 对这条信息的确定程度 (0.00-1.00)',
    last_mentioned_at DATETIME DEFAULT NULL COMMENT '最后提及时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_user_anchor_type (user_id, anchor_type),
    KEY idx_user_last_mentioned (user_id, last_mentioned_at),
    CONSTRAINT chk_confidence_range CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT fk_memory_anchors_user_id FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='记忆锚点表（长期用户画像）';

-- -------------------------------------------
-- 12. 用户日程表
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS user_schedule (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '日程主键ID',
    user_id INT UNSIGNED NOT NULL COMMENT '所属用户ID',
    schedule_type VARCHAR(32) NOT NULL COMMENT '日程类型（short_task, long_goal, countdown, anniversary, birthday 等）',
    title VARCHAR(200) NOT NULL COMMENT '日程标题',
    description TEXT DEFAULT NULL COMMENT '详细描述',
    scheduled_time DATETIME DEFAULT NULL COMMENT '计划/截止/纪念日时间',
    is_completed TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已完成（0-未完成，1-已完成）',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_user_scheduled (user_id, scheduled_time),
    KEY idx_user_completed (user_id, is_completed),
    CONSTRAINT fk_user_schedule_user_id FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户日程表';