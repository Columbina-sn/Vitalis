-- ============================================================
-- Vitalis 数据库升级脚本 v1 -> v2
-- 用途：废除 event 表，新增四张记忆与情绪相关的表
-- ============================================================
USE vitalis;

-- 1. 删除旧的 event 表（级联外键已设置，安全删除）
DROP TABLE IF EXISTS event;

-- 2. 创建情绪转折表
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

-- 3. 创建记忆快照表
CREATE TABLE IF NOT EXISTS memory_snapshots (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '快照主键ID',
    user_id INT UNSIGNED NOT NULL COMMENT '所属用户ID',
    summary TEXT NOT NULL COMMENT '一天全对话的总结摘要',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '快照生成时间',
    PRIMARY KEY (id),
    KEY idx_user_created_snapshot (user_id, created_at),
    CONSTRAINT fk_memory_snapshots_user_id FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='记忆快照表（每日对话摘要）';

-- 4. 创建记忆锚点表
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

-- 5. 创建用户日程表
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