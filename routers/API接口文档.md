# 元气岛 Vitalis · 后端接口文档

> 版本：v0.2  
> 基础URL：`http://localhost:8080`（部署后替换为实际域名）  
> 认证方式：除特别说明外，均需在请求头携带 `Authorization: Bearer <token>`  
> 通用成功响应格式：`{ "code": 200, "message": "...", "data": ... }`  
> 通用错误响应：对应 HTTP 状态码，`detail` 字段描述具体原因

---

## 1. 认证模块 `/auth`

### 1.1 用户注册
**POST** `/auth/register`

- **说明**：手机号 + 密码 + 8位邀请码注册，成功返回 JWT token
- **请求体 (JSON)**
  ```json
  {
    "phone": "13800138000",
    "password": "123456",
    "invite_code": "aB3dE7fG"
  }
  ```
- **成功响应**
  ```json
  {
    "code": 200,
    "message": "注册成功",
    "data": {
      "access_token": "<jwt>",
      "token_type": "bearer"
    }
  }
  ```
- **常见错误**
  - `400`：手机号已被注册 / 邀请码无效或已过期
  - `422`：参数校验失败（手机号格式、密码长度、邀请码长度等）

---

### 1.2 用户登录 / 管理员一级验证
**POST** `/auth/login`

- **说明**：普通用户直接返回 token；管理员手机号返回 `require_second_factor: true`
- **请求体 (JSON)**
  ```json
  {
    "phone": "13800138000",
    "password": "123456"
  }
  ```
- **普通用户成功响应**
  ```json
  {
    "code": 200,
    "message": "登录成功",
    "data": {
      "access_token": "<jwt>",
      "token_type": "bearer"
    }
  }
  ```
- **管理员一级验证成功**
  ```json
  {
    "code": 200,
    "message": "一级验证通过，需要二级密码验证",
    "data": {
      "require_second_factor": true,
      "phone": "管理员手机号"
    }
  }
  ```
- **常见错误**
  - `401`：手机号或密码错误
  - `403`：管理员登录入口已关闭 / 账号已被禁止登录
  - `429`：管理员一级验证次数超限

---

### 1.3 管理员二级验证
**POST** `/auth/admin/second-verify`

- **说明**：在 `/auth/login` 返回 `require_second_factor: true` 后的30秒内调用，验证二级密码，成功返回管理员 token（有效期24小时）
- **请求参数 (Query String)**
  - `phone` (string, 必填)：管理员手机号
  - `second_password` (string, 必填)：二级密码（明文）
- **成功响应**
  ```json
  {
    "code": 200,
    "message": "管理员验证通过",
    "data": {
      "access_token": "<jwt>",
      "token_type": "bearer"
    }
  }
  ```
- **常见错误**：`400`（无效请求）、`401`（二级密码错误 / 会话超时）

---

## 2. 用户模块 `/user`

> 以下接口均需携带普通用户的 JWT（`access_token`）

### 2.1 获取基本信息
**GET** `/user/base-info`

- **说明**：返回是否看过新手引导、头像URL
- **成功响应 data**
  ```json
  {
    "has_seen_intro": false,
    "avatar": "/static_pic/default_avatar.jpg"
  }
  ```

### 2.2 获取五维状态
**GET** `/user/status`

- **说明**：返回最新的身心活力、情绪基调、关系联结、自我价值、意义方向、心理和谐指数（0-100）
- **成功响应 data**
  ```json
  {
    "physical_vitality": 60,
    "emotional_tone": 75,
    "relationship_connection": 80,
    "self_worth": 65,
    "meaning_direction": 55,
    "psychological_harmony_index": 63
  }
  ```

### 2.3 标记引导完成
**POST** `/user/mark-intro`

- **说明**：将 `has_seen_intro` 置为 `true`
- **请求体**：空 `{}`

### 2.4 获取个人信息
**GET** `/user/information`

- **说明**：获取手机号、昵称、头像URL、邀请码
- **成功响应 data**
  ```json
  {
    "phone": "13800138000",
    "nickname": "小鸽子",
    "avatar": "/static_pic/avatar/xxx.jpg",
    "invite_code": "aB3dE7fG"
  }
  ```

### 2.5 修改昵称
**POST** `/user/nickname`

- **请求体**
  ```json
  { "nickname": "新昵称" }
  ```
- **约束**：1-15个字符

### 2.6 上传头像
**POST** `/user/avatar`

- **说明**：上传图片文件，支持 JPEG / PNG / GIF / WEBP，最大 5MB（可在 `.env` 中调整）
- **请求格式**：`multipart/form-data`，字段名 `file`
- **成功响应 data**
  ```json
  { "avatar_url": "/static_pic/avatar/abc123.jpg" }
  ```
- **常见错误**：`400`（格式不支持）、`413`（文件过大）

### 2.7 修改密码
**POST** `/user/change-password`

- **请求体**
  ```json
  {
    "old_password": "旧密码",
    "new_password": "新密码"
  }
  ```
- **约束**：新密码长度 6-20，不能与旧密码相同
- **常见错误**：`400`（旧密码错误 / 新密码不符合要求）

### 2.8 注销账户
**POST** `/user/delete-account`

- **说明**：验证密码后永久删除账户及所有关联数据（状态、情绪、对话、日程等），并清理头像文件
- **请求体**
  ```json
  { "password": "当前密码" }
  ```
- **常见错误**：`400`（密码错误）

### 2.9 查看状态历史趋势
**GET** `/user/status-history/{dimension}`

- **说明**：获取某维度近10次记录值，用于绘制折线图
- **路径参数** `dimension` 可选值：
  - `physical_vitality`
  - `emotional_tone`
  - `relationship_connection`
  - `self_worth`
  - `meaning_direction`
  - `psychological_harmony_index`
- **成功响应 data**
  ```json
  {
    "dimension": "emotional_tone",
    "history": [
      { "recorded_at": "2026-05-01T10:30:00", "value": 72 },
      { "recorded_at": "2026-05-01T09:00:00", "value": 68 }
    ]
  }
  ```

### 2.10 导出个人数据
**GET** `/user/export`

- **说明**：生成包含基本信息、状态、日记、画像、日程的 HTML 报告，以附件形式下载
- **响应头**：`Content-Type: text/html`，`Content-Disposition: attachment; filename=vitalis_report_<uid>_<timestamp>.html`

### 2.11 获取所有日程
**GET** `/user/schedules`

- **说明**：返回未完成（有时间的在前，无时间在后）和已完成（按更新时间倒序）两组日程
- **成功响应 data**
  ```json
  {
    "uncompleted": [
      {
        "id": 1,
        "schedule_type": "countdown",
        "title": "五一放假",
        "description": "期待假期",
        "scheduled_time": "2026-05-01T00:00:00",
        "is_completed": false,
        "created_at": "...",
        "updated_at": "..."
      }
    ],
    "completed": []
  }
  ```

---

## 3. 聊天模块 `/chat`

### 3.1 发送消息并获取 AI 回复
**POST** `/chat/conversation`

- **说明**：并行调用共情 AI 和生产力 AI，返回拼接后的完整回复，同时自动更新五维状态、记录情绪转折、处理画像/日程/改名
- **请求体**
  ```json
  { "message": "今天心情不太好" }
  ```
- **成功响应 data**
  ```json
  {
    "reply": "（小元的完整回复，可能包含 OS 部分）",
    "status_updates": {
      "physical_vitality": 50,
      "emotional_tone": 40,
      "relationship_connection": 75,
      "self_worth": 65,
      "meaning_direction": 60,
      "psychological_harmony_index": 58
    }
  }
  ```

### 3.2 获取对话历史（游标分页）
**GET** `/chat/history`

- **查询参数**
  - `before_id` (int, 可选)：游标，不传则取最新一页
  - `page_size` (int, 默认20, 最大50)
- **成功响应 data**
  ```json
  {
    "list": [
      {
        "id": 123,
        "role": "user",
        "content": "今天累了",
        "created_at": "2026-05-01T21:00:00"
      },
      {
        "id": 124,
        "role": "assistant",
        "content": "累了就休息一下～",
        "created_at": "2026-05-01T21:00:05"
      }
    ],
    "hasMore": true
  }
  ```

### 3.3 按日期查询对话历史
**GET** `/chat/history/date`

- **查询参数** `date` (string, 必填)：`YYYY-MM-DD`
- **成功响应 data**
  ```json
  {
    "list": [ ... ],
    "total": 12
  }
  ```

---

## 4. 评论模块 `/comment`

> 公开接口，无需登录

### 4.1 获取评论列表（游标分页）
**GET** `/comment/list`

- **说明**：优先展示字数 >50 的长评，同优先级按时间倒序
- **查询参数**
  - `page_size` (int, 默认10, 1-20)
  - `cursor_is_long` (bool, 可选)
  - `cursor_created_at` (string, ISO格式, 可选)
  - `cursor_id` (int, 可选)
- **成功响应 data**
  ```json
  {
    "list": [
      {
        "id": 1,
        "content": "很好的产品！",
        "ip_address": "127.0.0.1",
        "replied": false,
        "created_at": "2026-05-01T12:00:00"
      }
    ],
    "nextCursor": {
      "is_long": true,
      "created_at": "2026-05-01T12:00:00",
      "id": 1
    }
  }
  ```

### 4.2 发表评论
**POST** `/comment/new-comment`

- **请求体**
  ```json
  { "content": "这是一条评论" }
  ```
- **频率限制**：同一 IP 每分钟最多1条，每小时最多5条（可在 `.env` 调整）
- **常见错误**：`429`（频率超限）

---

## 5. 管理员模块 `/admin`

> 所有管理员接口均需携带 `is_admin: true` 的 JWT，且熔断开关 `admin_login_enabled` 必须为 `true`

### 5.1 获取统计数据
**GET** `/admin/stats`

- **成功响应 data**
  ```json
  {
    "total_users": 128,
    "today_conversations": 42,
    "total_comments": 15,
    "active_invite_codes": 7
  }
  ```

### 5.2 批量生成邀请码
**POST** `/admin/invite-codes/batch`

- **请求体**
  ```json
  {
    "count": 5,
    "expiry_days": 7
  }
  ```
  - `count`：1-100
  - `expiry_days`：1-7
- **成功响应 data**
  ```json
  {
    "codes": ["a1B2c3D4", "E5f6G7h8"],
    "expiry_time": "2026-05-08T12:00:00"
  }
  ```

### 5.3 分页查询用户列表
**GET** `/admin/users`

- **查询参数**：`page`（默认1）、`page_size`（默认20）
- **成功响应 data**
  ```json
  {
    "total": 128,
    "list": [
      {
        "id": 1,
        "phone": "13800138000",
        "nickname": "小明",
        "invite_code": "aB3dE7fG",
        "created_at": "2026-04-01T10:00:00",
        "psychological_harmony_index": 63,
        "conversation_count": 120,
        "can_login": true
      }
    ]
  }
  ```

### 5.4 编辑用户
**PUT** `/admin/users/{user_id}`

- **请求体**
  ```json
  {
    "phone": "13800138000",
    "nickname": "新昵称",
    "can_login": true
  }
  ```

### 5.5 删除用户
**DELETE** `/admin/users/{user_id}`

- **说明**：级联删除所有关联数据，并清理自定义头像文件

### 5.6 分页查询评论
**GET** `/admin/comments`

- **查询参数**：`page`、`page_size`
- **成功响应 data** 每条包含 `id`, `content`, `ip_address`, `replied`, `created_at`

### 5.7 编辑评论
**PUT** `/admin/comments/{comment_id}`

- **请求体**
  ```json
  { "content": "（可追加管理员回复）", "replied": true }
  ```

### 5.8 删除评论
**DELETE** `/admin/comments/{comment_id}`

### 5.9 分页查询邀请码
**GET** `/admin/invite-codes`

- **成功响应 data** 每条包含 `id`, `code`, `expiry_time`

### 5.10 编辑邀请码
**PUT** `/admin/invite-codes/{invite_id}`

- **请求体**
  ```json
  {
    "code": "newCode1",
    "expiry_time": "2026-05-10T00:00:00"
  }
  ```

### 5.11 删除邀请码
**DELETE** `/admin/invite-codes/{invite_id}`

### 5.12 查询所有操作日志（传统分页）
**GET** `/admin/logs-all`

- **查询参数**：`page`、`page_size`
- **成功响应 data** 每条包含 `id`, `admin_phone`, `action_type`, `remark`, `created_at`

### 5.13 按日期范围查询操作日志（游标分页）
**GET** `/admin/logs`

- **查询参数**
  - `start_date` / `end_date` (string, 可选)：`YYYY-MM-DD`
  - `cursor_created_at` / `cursor_id` (游标)
  - `page_size` (默认20)
- **成功响应 data** 返回 `list` 和 `next_cursor`

### 5.14 删除单条操作日志
**DELETE** `/admin/logs/{log_id}`

### 5.15 关闭管理员登录入口
**POST** `/admin/system-config/disable`

- **说明**：一键熔断，当前会话继续有效，后续新会话无法进入管理后台

### 5.16 每日摘要运行状态
**GET** `/admin/daily-summary/status`

- **成功响应 data**
  ```json
  { "alreadyTriggered": true }
  ```

### 5.17 手动触发每日摘要
**POST** `/admin/daily-summary/trigger`

- **说明**：每天仅能手动触发一次（若当日已有自动或手动运行则返回409）
- **成功响应 message**：`"每日摘要生成任务已启动"`

---

## 附录

### 认证与权限
- 注册/登录成功返回 `access_token`，客户端需存入 `localStorage`
- 后续请求在 `Authorization` 头中携带 `Bearer <token>`
- 管理员接口的 token 含有 `is_admin: true`，熔断开关可通过 `system_config` 表动态控制

### 通用错误响应
- 业务异常返回 400/401/403/404/409/422/429 等，`detail` 字段提供具体描述
- 500 错误在开发模式下附带详细堆栈，生产环境应关闭 `DEBUG_MODE`

### 数据脱敏
- 管理后台返回的手机号默认中间四位隐藏，前端可点击切换显示完整号码