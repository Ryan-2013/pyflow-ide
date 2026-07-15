"""
PyFlow AI Agent — 任務佇列系統
================================
支援：Claude · GPT-4o · LM Studio · Ollama · 任何 OpenAI 相容本地 AI
功能：任務清單、自動連續執行、SSE 串流、結果儲存
"""
from __future__ import annotations
import json, os, time, uuid, threading
from typing import Literal

# ── Task Status ───────────────────────────────────────────────────
Status = Literal['pending', 'running', 'done', 'failed', 'cancelled']

# ── In-memory task store ──────────────────────────────────────────
_tasks: list[dict] = []
_lock  = threading.Lock()


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


# ── Task CRUD ─────────────────────────────────────────────────────
def add_task(title: str, prompt: str, context: str = '',
             quick_type: str = '') -> dict:
    task = {
        'id':         _new_id(),
        'title':      title[:120],
        'prompt':     prompt,
        'context':    context,
        'quick_type': quick_type,
        'status':     'pending',
        'result':     '',
        'error':      '',
        'created_at': time.time(),
        'started_at': 0.0,
        'done_at':    0.0,
    }
    with _lock:
        _tasks.append(task)
    return task


def get_tasks() -> list[dict]:
    with _lock:
        return list(_tasks)


def get_task(tid: str) -> dict | None:
    with _lock:
        return next((t for t in _tasks if t['id'] == tid), None)


def update_task(tid: str, **kw):
    with _lock:
        t = next((t for t in _tasks if t['id'] == tid), None)
        if t:
            t.update(kw)


def delete_task(tid: str):
    with _lock:
        _tasks[:] = [t for t in _tasks if t['id'] != tid]


def clear_done():
    with _lock:
        _tasks[:] = [t for t in _tasks if t['status'] not in ('done', 'failed', 'cancelled')]


def next_pending() -> dict | None:
    with _lock:
        return next((t for t in _tasks if t['status'] == 'pending'), None)


# ── Local AI detection ────────────────────────────────────────────
LOCAL_SERVERS = [
    ('LM Studio', 'http://localhost:1234',  '/v1/models'),
    ('Ollama',    'http://localhost:11434', '/v1/models'),
    ('GPT4All',   'http://localhost:4891',  '/v1/models'),
    ('Jan',       'http://localhost:1337',  '/v1/models'),
    ('AnythingLLM','http://localhost:3001', '/api/v1/auth'),
]


def detect_local_ai() -> dict:
    import urllib.request as ur, ssl, json as _json
    ctx = ssl._create_unverified_context()
    for name, base, path in LOCAL_SERVERS:
        try:
            req = ur.Request(base + path, headers={'Authorization': 'Bearer lm-studio'})
            with ur.urlopen(req, context=ctx, timeout=1.5) as resp:
                data = _json.loads(resp.read())
                models = []
                if isinstance(data, dict):
                    if 'data' in data:
                        models = [m.get('id', m) if isinstance(m, dict) else m
                                  for m in data['data']]
                    elif 'models' in data:
                        models = data['models']
                return {
                    'available': True, 'server': name,
                    'base_url': base, 'models': models,
                    'chat_endpoint': base + '/v1/chat/completions',
                }
        except Exception:
            pass
    return {'available': False, 'server': None, 'models': [], 'base_url': ''}


# ── Build agent prompt ────────────────────────────────────────────
QUICK_PROMPTS = {
    'docstring': '為以下程式碼中所有公開函式和類別加上完整的文件字串（docstring）。保留原有功能，只新增文件。',
    'find_bugs': '仔細審查以下程式碼，找出所有潛在的 Bug、邊界條件問題、型別錯誤、空指標、資源洩漏等問題。對每個問題說明位置、原因和修復方法。',
    'write_tests': '為以下程式碼寫完整的單元測試。覆蓋所有公開函式、邊界條件和錯誤路徑。使用適合的測試框架。',
    'refactor': '重構以下程式碼：提取重複邏輯、改善命名、降低複雜度、但保持功能完全一致。解釋每個改動的原因。',
    'explain': '詳細解釋以下程式碼的功能、設計決策和每個關鍵部分的作用。假設讀者是中等程度的工程師。',
    'optimize': '分析以下程式碼的效能瓶頸並提出具體優化方案。包含時間複雜度分析和改進後的程式碼。',
    'security': '審查以下程式碼的安全性問題：SQL injection、XSS、緩衝區溢位、輸入驗證、認證缺陷等。',
    'type_hints': '為以下 Python 程式碼加上完整的型別標注（type hints）。包含函式參數、回傳值和重要變數。',
    'readme': '根據以下程式碼寫一份清晰的 README.md，包含：功能說明、安裝方式、使用範例、API 文件。',
    'simplify': '簡化以下程式碼：移除不必要的複雜度、合併重複邏輯、讓程式碼更易讀。',
}


def build_agent_prompt(task: dict) -> str:
    qtype = task.get('quick_type', '')
    base  = QUICK_PROMPTS.get(qtype, '') or task.get('prompt', '')
    ctx   = task.get('context', '')
    parts = [f'任務：{task["title"]}', '', base]
    if ctx:
        parts += ['', '程式碼：', '```', ctx[:8000], '```']
    return '\n'.join(parts)
