# 会话存储功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现多会话持久化存储，每个浏览器独立会话，服务重启后对话历史可恢复。

**Architecture:** 新建 `session_store.py` 封装 SQLite 存储，ChatBot 通过 session_id 读写历史，Flask 中间件自动管理 cookie session。

**Tech Stack:** Python, SQLite3, Flask, UUID

---

### Task 1: 创建 SessionStore 模块

**Files:**
- Create: `session_store.py`

- [ ] **Step 1: 创建 session_store.py**

```python
"""会话持久化存储 - SQLite 实现"""

import sqlite3
import uuid
import os
import threading
from typing import List, Dict, Optional
from datetime import datetime


class SessionStore:
    """SQLite 会话存储"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "sessions.db")
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取线程本地数据库连接"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        """)
        conn.commit()

    def create_session(self) -> str:
        """创建新会话，返回 session_id"""
        session_id = str(uuid.uuid4())
        conn = self._get_conn()
        conn.execute("INSERT INTO sessions (id) VALUES (?)", (session_id,))
        conn.commit()
        return session_id

    def session_exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        conn = self._get_conn()
        row = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return row is not None

    def get_or_create(self, session_id: Optional[str] = None) -> str:
        """有则返回，无则创建"""
        if session_id and self.session_exists(session_id):
            return session_id
        return self.create_session()

    def get_history(self, session_id: str, limit: int = 10) -> List[Dict]:
        """获取最近 N 条消息"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def append_message(self, session_id: str, role: str, content: str):
        """追加一条消息"""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        conn.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,)
        )
        conn.commit()

    def clear_session(self, session_id: str):
        """清空会话消息"""
        conn = self._get_conn()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()

    def list_sessions(self) -> List[Dict]:
        """列出所有会话"""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT s.id, s.created_at, s.updated_at,
                   COUNT(m.id) as message_count,
                   (SELECT content FROM messages WHERE session_id = s.id ORDER BY id DESC LIMIT 1) as last_message
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, session_id: str):
        """删除会话及关联消息"""
        conn = self._get_conn()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
```

- [ ] **Step 2: 验证模块可导入**

```bash
cd e:/github/voice && python -c "from session_store import SessionStore; s = SessionStore(':memory:'); sid = s.create_session(); print('OK:', sid[:8])"
```

Expected: `OK: xxxxxxxx`

- [ ] **Step 3: 提交**

```bash
git add session_store.py
git commit -m "feat: 新建SessionStore模块(SQLite会话存储)"
```

---

### Task 2: 改造 ChatBot 接入会话存储

**Files:**
- Modify: `chat_bot.py:239-290` (ChatBot class)

- [ ] **Step 1: 修改 ChatBot.__init__**

在 `ChatBot.__init__` 中添加 `session_store` 参数。将：

```python
    def __init__(self, api_key: str = None, skill_path: str = None):
        self.client = OpenAI(
            api_key=api_key or config.MIMO_API_KEY,
            base_url=config.MIMO_BASE_URL,
        )
        self.model = config.CHAT_MODEL
        self.history: List[Dict] = []
        self._loader = SkillLoader(skill_path)
        self._base_prompt = build_system_prompt(None)
        self._last_skill_content = ""
        print(f"[ChatBot] 已就绪 (按需加载模式)")
```

替换为：

```python
    def __init__(self, api_key: str = None, skill_path: str = None, session_store=None):
        self.client = OpenAI(
            api_key=api_key or config.MIMO_API_KEY,
            base_url=config.MIMO_BASE_URL,
        )
        self.model = config.CHAT_MODEL
        self._store = session_store
        self._loader = SkillLoader(skill_path)
        self._base_prompt = build_system_prompt(None)
        self._last_skill_content = ""
        print(f"[ChatBot] 已就绪 (按需加载模式)")
```

- [ ] **Step 2: 修改 ChatBot.chat()**

将 `chat()` 方法改为从 DB 读写历史。替换整个方法：

```python
    def chat(self, user_message: str, session_id: str = None, voice_context: str = None) -> Optional[str]:
        """与MiMo对话，按需加载 skill 章节"""
        if not session_id:
            return None

        # 写入用户消息
        self._store.append_message(session_id, "user", user_message)

        # 核心章节常驻 + 关键词匹配高级章节
        skill_content = self._loader.chat_sections(user_message)
        self._last_skill_content = skill_content

        system = build_system_prompt(skill_content)
        if voice_context:
            system += f"\n\n【用户语音特征】{voice_context}\n请根据用户的语气和情绪，选择相匹配的情绪标签和回复风格。"

        # 从 DB 读取最近 10 条历史
        history = self._store.get_history(session_id, limit=10)
        messages = [{"role": "system", "content": system}]
        messages.extend(history)

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=300,
                temperature=0.7,
            )
            reply = completion.choices[0].message.content
            # 修正标签堆叠问题
            reply = fix_stacked_tags(reply)
            # 写入助手回复
            self._store.append_message(session_id, "assistant", reply)
            return reply
        except Exception as e:
            print(f"对话请求失败: {e}")
            return None
```

- [ ] **Step 3: 修改 clear_history()**

```python
    def clear_history(self, session_id: str = None):
        """清除对话历史"""
        if session_id and self._store:
            self._store.clear_session(session_id)
```

- [ ] **Step 4: 验证语法**

```bash
cd e:/github/voice && python -c "from chat_bot import ChatBot; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: 提交**

```bash
git add chat_bot.py
git commit -m "feat: ChatBot接入SessionStore，支持多会话"
```

---

### Task 3: Flask Session 中间件 + API

**Files:**
- Modify: `app.py:1-14` (imports + globals)
- Modify: `app.py:77-85` (init_api)
- Modify: `app.py:165-177` (/api/chat)
- Modify: `app.py:359-362` (/api/clear)

- [ ] **Step 1: 添加 imports 和全局变量**

在 `app.py` 顶部 imports 中添加：

```python
from session_store import SessionStore
```

在全局变量区域添加：

```python
session_store = None
```

- [ ] **Step 2: 修改 init_api()**

在 `init_api()` 中初始化 session_store 和 chat_bot。将：

```python
def init_api():
    global tts, chat_bot
    if config.MIMO_API_KEY != "your_api_key_here":
        tts = XiaomiTTS()
        chat_bot = ChatBot()
    else:
        tts = None
        chat_bot = SimpleChatBot()
```

替换为：

```python
def init_api():
    global tts, chat_bot, session_store
    session_store = SessionStore()
    if config.MIMO_API_KEY != "your_api_key_here":
        tts = XiaomiTTS()
        chat_bot = ChatBot(session_store=session_store)
    else:
        tts = None
        chat_bot = SimpleChatBot()
```

- [ ] **Step 3: 添加 Session 中间件**

在 `init_api()` 函数之后添加：

```python
@app.before_request
def ensure_session():
    """确保每个请求都有有效的 session_id"""
    if request.path.startswith("/api/") and request.path not in ("/api/sessions",):
        session_id = request.cookies.get("session_id")
        g.session_id = session_store.get_or_create(session_id)
```

- [ ] **Step 4: 修改 /api/chat**

将：

```python
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    message = data.get("message", "").strip()
    voice_context = data.get("voice_context", "").strip() or None
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    reply = chat_bot.chat(message, voice_context=voice_context)
    if reply is None:
        return jsonify({"error": "对话请求失败"}), 500

    return jsonify({"reply": reply})
```

替换为：

```python
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    message = data.get("message", "").strip()
    voice_context = data.get("voice_context", "").strip() or None
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    session_id = getattr(g, "session_id", None)
    reply = chat_bot.chat(message, session_id=session_id, voice_context=voice_context)
    if reply is None:
        return jsonify({"error": "对话请求失败"}), 500

    resp = jsonify({"reply": reply})
    if session_id and request.cookies.get("session_id") != session_id:
        resp.set_cookie("session_id", session_id, max_age=30*24*3600, httponly=True, samesite="Lax")
    return resp
```

- [ ] **Step 5: 修改 /api/clear**

将：

```python
@app.route("/api/clear", methods=["POST"])
def api_clear():
    chat_bot.clear_history()
    return jsonify({"ok": True})
```

替换为：

```python
@app.route("/api/clear", methods=["POST"])
def api_clear():
    session_id = getattr(g, "session_id", None)
    chat_bot.clear_history(session_id=session_id)
    return jsonify({"ok": True})
```

- [ ] **Step 6: 添加会话 API**

在 `/api/clear` 之后添加：

```python
@app.route("/api/sessions", methods=["GET"])
def api_list_sessions():
    """列出所有会话"""
    sessions = session_store.list_sessions()
    return jsonify({"sessions": sessions})


@app.route("/api/sessions", methods=["POST"])
def api_create_session():
    """新建会话"""
    session_id = session_store.create_session()
    resp = jsonify({"ok": True, "session_id": session_id})
    resp.set_cookie("session_id", session_id, max_age=30*24*3600, httponly=True, samesite="Lax")
    return resp


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def api_delete_session(session_id):
    """删除会话"""
    session_store.delete_session(session_id)
    return jsonify({"ok": True})


@app.route("/api/sessions/<session_id>/messages", methods=["GET"])
def api_get_messages(session_id):
    """获取会话历史消息"""
    messages = session_store.get_history(session_id, limit=50)
    return jsonify({"messages": messages})
```

- [ ] **Step 7: 验证语法**

```bash
cd e:/github/voice && python -c "from app import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 8: 提交**

```bash
git add app.py
git commit -m "feat: Flask session中间件 + 会话管理API"
```

---

### Task 4: 前端会话切换 UI

**Files:**
- Modify: `templates/index.html` (HTML + CSS + JS)

- [ ] **Step 1: 添加会话列表 HTML**

在 `<nav class="nav-sidebar">` 中，`<div class="nav-spacer"></div>` 之前插入：

```html
  <div class="nav-item" id="btnSessions" onclick="toggleSessions()" style="cursor:pointer">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M8 9h8M8 13h4"/></svg>
    <span>会话</span>
  </div>
```

- [ ] **Step 2: 添加会话面板 HTML**

在 `<body>` 中，`<nav class="nav-sidebar">` 之前添加：

```html
<!-- 会话面板 -->
<div class="sessions-overlay" id="sessionsOverlay" onclick="toggleSessions()"></div>
<div class="sessions-panel" id="sessionsPanel">
  <div class="sessions-header">
    <h3>会话列表</h3>
    <button class="btn btn-primary btn-sm" onclick="newSession()">+ 新会话</button>
  </div>
  <div class="sessions-list" id="sessionsList"></div>
</div>
```

- [ ] **Step 3: 添加会话面板 CSS**

在 `</style>` 之前添加：

```css
/* 会话面板 */
.sessions-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:98}
.sessions-overlay.show{display:block}
.sessions-panel{position:fixed;left:64px;top:0;bottom:0;width:280px;background:var(--surface);border-right:1px solid var(--border);z-index:99;transform:translateX(-100%);transition:transform .25s ease;display:flex;flex-direction:column}
.sessions-panel.open{transform:translateX(0)}
.sessions-header{display:flex;align-items:center;justify-content:space-between;padding:16px;border-bottom:1px solid var(--border)}
.sessions-header h3{font-size:14px;font-weight:600}
.sessions-list{flex:1;overflow-y:auto;padding:8px}
.session-item{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:8px;cursor:pointer;border:1px solid transparent;transition:all .15s}
.session-item:hover{background:var(--surface2)}
.session-item.active{border-color:var(--accent);background:rgba(108,92,231,.1)}
.session-item .s-info{flex:1;min-width:0}
.session-item .s-preview{font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.session-item .s-time{font-size:11px;color:var(--text2)}
.session-item .s-delete{background:transparent;color:var(--text2);border:none;padding:4px;font-size:12px;cursor:pointer;opacity:0;transition:opacity .15s}
.session-item:hover .s-delete{opacity:1}
.session-item .s-delete:hover{color:var(--red)}
@media(max-width:768px){
  .sessions-panel{left:0;width:min(280px,85vw)}
}
```

- [ ] **Step 4: 添加会话切换 JavaScript**

在 `</script>` 之前添加：

```javascript
// ---- 会话管理 ----
let currentSessionId = null;

function toggleSessions() {
  const panel = $('#sessionsPanel');
  const overlay = $('#sessionsOverlay');
  const isOpen = panel.classList.contains('open');
  panel.classList.toggle('open');
  overlay.classList.toggle('show');
  if (!isOpen) loadSessions();
}

async function loadSessions() {
  try {
    const res = await fetch('/api/sessions');
    const data = await res.json();
    const list = $('#sessionsList');
    list.innerHTML = '';
    if (data.sessions.length === 0) {
      list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text2);font-size:13px">暂无会话</div>';
      return;
    }
    data.sessions.forEach(s => {
      const div = document.createElement('div');
      div.className = 'session-item' + (s.id === currentSessionId ? ' active' : '');
      div.innerHTML = `
        <div class="s-info">
          <div class="s-preview">${s.last_message || '空会话'}</div>
          <div class="s-time">${formatTime(s.updated_at)}</div>
        </div>
        <button class="s-delete" onclick="event.stopPropagation();deleteSession('${s.id}')" title="删除">&#10005;</button>
      `;
      div.onclick = () => switchSession(s.id);
      list.appendChild(div);
    });
  } catch (e) { console.error('加载会话列表失败:', e); }
}

function formatTime(ts) {
  if (!ts) return '';
  const d = new Date(ts + (ts.includes('Z') || ts.includes('+') ? '' : 'Z'));
  const now = new Date();
  const diff = now - d;
  if (diff < 60000) return '刚刚';
  if (diff < 3600000) return Math.floor(diff/60000) + '分钟前';
  if (diff < 86400000) return Math.floor(diff/3600000) + '小时前';
  return d.toLocaleDateString('zh-CN');
}

async function switchSession(sessionId) {
  currentSessionId = sessionId;
  document.cookie = `session_id=${sessionId};max-age=${30*24*3600};path=/;samesite=lax`;
  toggleSessions();
  await loadMessages(sessionId);
}

async function newSession() {
  try {
    const res = await fetch('/api/sessions', {method: 'POST'});
    const data = await res.json();
    if (data.ok) {
      currentSessionId = data.session_id;
      document.cookie = `session_id=${data.session_id};max-age=${30*24*3600};path=/;samesite=lax`;
      $('#messages').innerHTML = '<div class="msg system">新会话已创建</div>';
      toggleSessions();
    }
  } catch (e) { console.error('创建会话失败:', e); }
}

async function deleteSession(sessionId) {
  if (!confirm('确定删除此会话？')) return;
  try {
    await fetch('/api/sessions/' + sessionId, {method: 'DELETE'});
    if (sessionId === currentSessionId) {
      currentSessionId = null;
      $('#messages').innerHTML = '<div class="msg system">会话已删除，请新建会话</div>';
    }
    loadSessions();
  } catch (e) { console.error('删除会话失败:', e); }
}

async function loadMessages(sessionId) {
  try {
    const res = await fetch('/api/sessions/' + sessionId + '/messages');
    const data = await res.json();
    const container = $('#messages');
    container.innerHTML = '';
    if (data.messages.length === 0) {
      container.innerHTML = '<div class="msg system">开始新的对话吧</div>';
      return;
    }
    data.messages.forEach(m => {
      const div = document.createElement('div');
      div.className = 'msg ' + (m.role === 'user' ? 'user' : 'bot');
      div.textContent = m.content;
      container.appendChild(div);
    });
    container.scrollTop = container.scrollHeight;
  } catch (e) { console.error('加载消息失败:', e); }
}
```

- [ ] **Step 5: 提交**

```bash
git add templates/index.html
git commit -m "feat: 前端会话切换UI(新建/切换/删除)"
```

---

### Task 5: 部署并验证

**Files:**
- None (deploy only)

- [ ] **Step 1: 推送代码**

```bash
git push
```

- [ ] **Step 2: 部署**

```bash
python deploy.py
```

- [ ] **Step 3: 验证会话 API**

```bash
# 创建会话
curl -s -c /tmp/cookies.txt http://47.243.104.165:5000/api/sessions -X POST | python -m json.tool

# 列出会话
curl -s -b /tmp/cookies.txt http://47.243.104.165:5000/api/sessions | python -m json.tool
```

- [ ] **Step 4: 浏览器验证**

打开 http://47.243.104.165:5000 ，验证：
1. 点击"会话"按钮打开会话面板
2. 新建会话、发送消息、刷新页面后历史仍在
3. 切换会话、删除会话功能正常
