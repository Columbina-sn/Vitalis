# ai/memory/history_store.py
"""文件级对话历史持久化存储（JSON）。

每用户一个 JSON 文件，存储压缩摘要和近期消息。
不依赖 MySQL 表结构变更——写入 conversation_history 表的逻辑不变，
此模块作为额外的上下文持久化层。
"""

import json
import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from utills.logging_conf import get_logger

logger = get_logger(__name__)


class HistoryStore:
    """文件级对话历史存储。

    JSON 文件结构:
    {
      "user_id": 1,
      "total_rounds": 42,
      "rounds_since_compression": 12,
      "compressed_summaries": ["摘要1...", "摘要2..."],
      "recent_messages": [
        {"role": "user", "content": "...", "created_at": "2026-07-31T15:30:00"},
        {"role": "assistant", "content": "...", "created_at": "2026-07-31T15:30:05"}
      ],
      "created_at": "2026-07-31T10:00:00",
      "updated_at": "2026-07-31T15:30:05"
    }
    """

    def __init__(self, base_dir: str = "data/conversations"):
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        # 按 user_id 分锁，防止同一用户并发写入冲突
        self._locks: dict[int, asyncio.Lock] = {}

    def _get_lock(self, user_id: int) -> asyncio.Lock:
        """获取或创建用户级别的异步锁"""
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    def _file_path(self, user_id: int) -> Path:
        return self._base_dir / f"{user_id}.json"

    def _load(self, user_id: int) -> dict:
        """从文件加载数据，不存在则返回默认结构"""
        path = self._file_path(user_id)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"用户 {user_id} 历史文件损坏，重建: {e}")
        return self._default_data(user_id)

    def _save(self, user_id: int, data: dict):
        """原子写入：先写临时文件再替换"""
        data["updated_at"] = datetime.now().isoformat()
        path = self._file_path(user_id)
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(path)

    @staticmethod
    def _default_data(user_id: int) -> dict:
        return {
            "user_id": user_id,
            "total_rounds": 0,
            "rounds_since_compression": 0,
            "compressed_summaries": [],
            "recent_messages": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    # ---------- 公开方法 ----------

    async def add_message(self, user_id: int, role: str, content: str):
        """追加一条消息到 recent_messages"""
        async with self._get_lock(user_id):
            data = self._load(user_id)
            data["recent_messages"].append({
                "role": role,
                "content": content,
                "created_at": datetime.now().isoformat(),
            })
            self._save(user_id, data)

    async def get_context(self, user_id: int) -> dict:
        """获取组装好的上下文数据：所有压缩摘要 + 全部近期消息"""
        async with self._get_lock(user_id):
            data = self._load(user_id)
        return {
            "compressed_summaries": data["compressed_summaries"],
            "recent_messages": data["recent_messages"],
        }

    async def get_recent_messages(self, user_id: int, n: int = 10) -> list[dict]:
        """获取最近 n 条消息（工作 AI 用）"""
        async with self._get_lock(user_id):
            data = self._load(user_id)
        return data["recent_messages"][-n:]

    async def get_rounds_since_compression(self, user_id: int) -> int:
        """获取距上次压缩的轮数"""
        async with self._get_lock(user_id):
            data = self._load(user_id)
        return data["rounds_since_compression"]

    async def get_total_rounds(self, user_id: int) -> int:
        """获取总轮数"""
        async with self._get_lock(user_id):
            data = self._load(user_id)
        return data["total_rounds"]

    async def increment_round(self, user_id: int):
        """总轮数 +1，压缩计数 +1"""
        async with self._get_lock(user_id):
            data = self._load(user_id)
            data["total_rounds"] += 1
            data["rounds_since_compression"] += 1
            self._save(user_id, data)

    async def compress(self, user_id: int, summary_text: str):
        """执行压缩：将近期消息的摘要追加到 compressed_summaries，
        清空 recent_messages，重置计数器。"""
        async with self._get_lock(user_id):
            data = self._load(user_id)
            label = f"第{data['total_rounds'] - data['rounds_since_compression'] + 1}-{data['total_rounds']}轮摘要"
            data["compressed_summaries"].append(f"[{label}] {summary_text}")
            data["recent_messages"] = []
            data["rounds_since_compression"] = 0
            self._save(user_id, data)
            logger.info(f"用户 {user_id} 上下文已压缩，累计摘要 {len(data['compressed_summaries'])} 段")

    async def clear(self, user_id: int):
        """清除用户的所有历史（管理员操作或测试用）"""
        async with self._get_lock(user_id):
            self._save(user_id, self._default_data(user_id))
            logger.info(f"用户 {user_id} 对话历史文件已重置")
