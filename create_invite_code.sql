USE vitalis;

-- 删除过期的邀请码（过期时间早于当前时间）
DELETE FROM invite_code WHERE expiry_time < NOW();

-- 插入一条新的邀请码（8位，由数字、大写字母、小写字母随机组成，过期时间7天后）
INSERT INTO invite_code (code, expiry_time)
SELECT CONCAT(
    ELT(FLOOR(1 + RAND() * 3),  -- 随机决定每一位的类型：1-数字，2-大写字母，3-小写字母
        LPAD(FLOOR(RAND() * 10), 1, '0'),  -- 数字 0-9
        CHAR(FLOOR(65 + RAND() * 26)),    -- 大写字母 A-Z
        CHAR(FLOOR(97 + RAND() * 26))     -- 小写字母 a-z
    ),
    ELT(FLOOR(1 + RAND() * 3),
        LPAD(FLOOR(RAND() * 10), 1, '0'),
        CHAR(FLOOR(65 + RAND() * 26)),
        CHAR(FLOOR(97 + RAND() * 26))
    ),
    ELT(FLOOR(1 + RAND() * 3),
        LPAD(FLOOR(RAND() * 10), 1, '0'),
        CHAR(FLOOR(65 + RAND() * 26)),
        CHAR(FLOOR(97 + RAND() * 26))
    ),
    ELT(FLOOR(1 + RAND() * 3),
        LPAD(FLOOR(RAND() * 10), 1, '0'),
        CHAR(FLOOR(65 + RAND() * 26)),
        CHAR(FLOOR(97 + RAND() * 26))
    ),
    ELT(FLOOR(1 + RAND() * 3),
        LPAD(FLOOR(RAND() * 10), 1, '0'),
        CHAR(FLOOR(65 + RAND() * 26)),
        CHAR(FLOOR(97 + RAND() * 26))
    ),
    ELT(FLOOR(1 + RAND() * 3),
        LPAD(FLOOR(RAND() * 10), 1, '0'),
        CHAR(FLOOR(65 + RAND() * 26)),
        CHAR(FLOOR(97 + RAND() * 26))
    ),
    ELT(FLOOR(1 + RAND() * 3),
        LPAD(FLOOR(RAND() * 10), 1, '0'),
        CHAR(FLOOR(65 + RAND() * 26)),
        CHAR(FLOOR(97 + RAND() * 26))
    ),
    ELT(FLOOR(1 + RAND() * 3),
        LPAD(FLOOR(RAND() * 10), 1, '0'),
        CHAR(FLOOR(65 + RAND() * 26)),
        CHAR(FLOOR(97 + RAND() * 26))
    )
) AS code,
DATE_ADD(NOW(), INTERVAL 7 DAY) AS expiry_time;

# -- 为 users 表增加 can_login 字段
# ALTER TABLE users
# ADD COLUMN can_login TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否允许登录（0-禁止，1-允许）'
# AFTER has_seen_intro;
#
# -- 为 user_status 表增加心理和谐指数字段（放在 meaning_direction 之后）
# ALTER TABLE user_status
# ADD COLUMN psychological_harmony_index TINYINT UNSIGNED NOT NULL DEFAULT 50 COMMENT '心理和谐指数（1-100）'
# AFTER meaning_direction;
#
# -- 添加 CHECK 约束
# ALTER TABLE user_status
# ADD CONSTRAINT chk_psychological_harmony_index CHECK (psychological_harmony_index BETWEEN 1 AND 100);
#
# -- 为 comment 表增加 replied 字段
# ALTER TABLE comment
# ADD COLUMN replied TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已回复（0-未回复，1-已回复）'
# AFTER ip_address;
#
# -- 如果 user_status_history 表也需要同步新增字段（假设历史表已存在）
# ALTER TABLE user_status_history
# ADD COLUMN psychological_harmony_index TINYINT UNSIGNED NOT NULL DEFAULT 50 COMMENT '心理和谐指数（1-100）'
# AFTER meaning_direction;
#
# ALTER TABLE user_status_history
# ADD CONSTRAINT chk_history_psychological_harmony_index CHECK (psychological_harmony_index BETWEEN 1 AND 100);