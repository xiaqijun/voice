# 会话存储功能设计

## 背景

当前 MiMo 聊天机器人的对话历史存储在内存中（`ChatBot.history`），存在两个问题：
1. 服务重启后历史丢失
2. 所有用户共享同一个全局历史，无法多用户同时使用

## 目标

1. 会话持久化：服务重启后对话历史可恢复
2. 多会话支持：每个浏览器独立会话，互不干扰
3. 会话管理：支持新建、切换、删除会话

## 设计

### 模块 1：SessionStore (`session_store.py`)

新建独立模块，封装 SQLite 会话存储。

**SQLite 表结构：**

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_messages_session ON messages(session_id);
```

**SessionStore 类接口：**

- `__init__(db_path)` — 初始化 SQLite 连接
- `create_session() -> str` — 创建新会话，返回 UUID
- `get_history(session_id, limit=10) -> List[Dict]` — 获取最近 N 条消息
- `append_message(session_id, role, content)` — 追加一条消息
- `clear_session(session_id)` — 清空会话消息
- `list_sessions() -> List[Dict]` — 列出所有会话（id, created_at, updated_at, message_count, last_message）
- `delete_session(session_id)` — 删除会话及关联消息
- `get_or_create(session_id=None) -> str` — 有则返回，无则创建

### 模块 2：ChatBot 改造 (`chat_bot.py`)

**改动点：**

1. `__init__` 接受 `session_store` 参数
2. `chat()` 新增 `session_id` 参数
3. 从 `session_store.get_history()` 读取历史
4. 每次对话后 `session_store.append_message()` 写入
5. 移除 `self.history` 内存列表
6. `clear_history()` 调用 `session_store.clear_session()`

### 模块 3：Flask 中间件 + API (`app.py`)

**Session 中间件：**

- `@app.before_request` 检查 cookie 中的 `session_id`
- 无 cookie 时自动创建新会话并设置 cookie
- Cookie 有效期 30 天

**新增 API：**

| 路由 | 方法 | 功能 |
|------|------|------|
| `/api/sessions` | GET | 列出所有会话 |
| `/api/sessions` | POST | 新建会话 |
| `/api/sessions/<id>` | DELETE | 删除会话 |
| `/api/sessions/<id>/messages` | GET | 获取会话历史 |

**修改 API：**

| 路由 | 改动 |
|------|------|
| `/api/chat` | 从 cookie 读 session_id，传给 chat_bot.chat() |
| `/api/clear` | 清空当前会话而非全局历史 |

### 模块 4：前端 (`templates/index.html`)

- 顶部加会话切换按钮（显示当前会话，点击展开列表）
- 会话列表：显示每条会话的最后一条消息预览 + 时间
- 支持新建会话、切换会话、删除会话
- 切换会话时重新加载聊天记录

## 改动范围

| 文件 | 改动 |
|------|------|
| `session_store.py` | 新建，SQLite 会话存储模块 |
| `chat_bot.py` | ChatBot 接受 session_store，chat() 读写 DB |
| `app.py` | Session 中间件 + 新增会话 API |
| `templates/index.html` | 会话切换 UI |

## 不做的事

- 不做用户认证（当前是单机使用，cookie session 足够）
- 不做消息分页（保留最近 10 条作为上下文即可）
- 不做会话导出/导入
