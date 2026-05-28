"""记忆存储实现。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import MemoryEntry, MemoryType


class MemoryStore:
    """内存记忆存储。

    支持按 session_id、memory_type 查询，
    支持过期清理和 relevance_score 排序。
    """

    def __init__(self) -> None:
        self._entries: dict[str, MemoryEntry] = {}
        self._session_index: dict[str, list[str]] = {}  # session_id -> [entry_ids]
        self._type_index: dict[str, list[str]] = {}  # memory_type -> [entry_ids]

    def save(self, entry: MemoryEntry) -> str:
        """保存记忆条目。

        如果 entry_id 已存在则更新，否则新增。
        同时维护 session 索引和类型索引。
        """
        is_update = entry.entry_id in self._entries
        if not is_update:
            # 新增：维护索引
            self._session_index.setdefault(entry.session_id, []).append(entry.entry_id)
            self._type_index.setdefault(entry.memory_type.value, []).append(entry.entry_id)
        else:
            # 更新：如果 session 或类型变了，需要重建索引
            old = self._entries[entry.entry_id]
            if old.session_id != entry.session_id:
                if old.session_id in self._session_index:
                    self._session_index[old.session_id] = [
                        eid for eid in self._session_index[old.session_id] if eid != entry.entry_id
                    ]
                self._session_index.setdefault(entry.session_id, []).append(entry.entry_id)
            if old.memory_type != entry.memory_type:
                old_type_key = old.memory_type.value
                if old_type_key in self._type_index:
                    self._type_index[old_type_key] = [
                        eid for eid in self._type_index[old_type_key] if eid != entry.entry_id
                    ]
                self._type_index.setdefault(entry.memory_type.value, []).append(entry.entry_id)

        self._entries[entry.entry_id] = entry
        return entry.entry_id

    def get(self, entry_id: str) -> MemoryEntry | None:
        """根据 entry_id 获取记忆条目。"""
        return self._entries.get(entry_id)

    def list_by_session(self, session_id: str, limit: int = 50) -> list[MemoryEntry]:
        """按 session_id 查询记忆列表，按 relevance_score 降序排列。"""
        entry_ids = self._session_index.get(session_id, [])
        entries = [self._entries[eid] for eid in entry_ids if eid in self._entries]
        entries.sort(key=lambda e: e.relevance_score, reverse=True)
        return entries[:limit]

    def list_by_type(self, memory_type: MemoryType, limit: int = 50) -> list[MemoryEntry]:
        """按 memory_type 查询记忆列表，按 relevance_score 降序排列。"""
        type_key = memory_type.value
        entry_ids = self._type_index.get(type_key, [])
        entries = [self._entries[eid] for eid in entry_ids if eid in self._entries]
        entries.sort(key=lambda e: e.relevance_score, reverse=True)
        return entries[:limit]

    def search(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """简单关键词搜索（Phase1，后续可替换为向量搜索）。

        将 query 按空格拆分为关键词，匹配 content 或 summary 中包含
        任一关键词的条目。按 relevance_score 降序排列。
        """
        if not query or not query.strip():
            return []

        keywords = query.lower().split()
        results: list[MemoryEntry] = []

        for entry in self._entries.values():
            text = (entry.content + " " + entry.summary).lower()
            # 统计命中的关键词数量作为评分依据
            hit_count = sum(1 for kw in keywords if kw in text)
            if hit_count > 0:
                results.append(entry)

        # 按 relevance_score 降序
        results.sort(key=lambda e: e.relevance_score, reverse=True)
        return results[:limit]

    def delete(self, entry_id: str) -> bool:
        """删除记忆条目，同时清理索引。返回是否成功删除。"""
        entry = self._entries.get(entry_id)
        if entry is None:
            return False

        # 清理 session 索引
        if entry.session_id in self._session_index:
            self._session_index[entry.session_id] = [
                eid for eid in self._session_index[entry.session_id] if eid != entry_id
            ]
            if not self._session_index[entry.session_id]:
                del self._session_index[entry.session_id]

        # 清理类型索引
        type_key = entry.memory_type.value
        if type_key in self._type_index:
            self._type_index[type_key] = [
                eid for eid in self._type_index[type_key] if eid != entry_id
            ]
            if not self._type_index[type_key]:
                del self._type_index[type_key]

        del self._entries[entry_id]
        return True

    def cleanup_expired(self) -> int:
        """清理过期记忆，返回清理数量。

        根据 expires_at 字段判断是否过期。expires_at 格式为 ISO 时间字符串。
        """
        now = time.time()
        expired_ids: list[str] = []

        for entry_id, entry in self._entries.items():
            if not entry.expires_at:
                continue
            try:
                # 尝试解析 ISO 格式时间戳
                from datetime import datetime

                expires_dt = datetime.fromisoformat(entry.expires_at)
                expires_ts = expires_dt.timestamp()
                if expires_ts < now:
                    expired_ids.append(entry_id)
            except (ValueError, TypeError):
                # 无法解析的 expires_at 视为永不过期
                continue

        for eid in expired_ids:
            self.delete(eid)

        return len(expired_ids)

    def clear(self, session_id: str | None = None) -> int:
        """清除记忆。

        如果指定 session_id，只清除该会话的记忆。
        如果 session_id 为 None，清除所有记忆。
        返回清除的条目数量。
        """
        if session_id is not None:
            entry_ids = self._session_index.pop(session_id, [])
            count = 0
            for eid in entry_ids:
                if eid in self._entries:
                    # 从类型索引中移除
                    entry = self._entries[eid]
                    type_key = entry.memory_type.value
                    if type_key in self._type_index:
                        self._type_index[type_key] = [
                            tid for tid in self._type_index[type_key] if tid != eid
                        ]
                        if not self._type_index[type_key]:
                            del self._type_index[type_key]
                    del self._entries[eid]
                    count += 1
            return count
        else:
            count = len(self._entries)
            self._entries.clear()
            self._session_index.clear()
            self._type_index.clear()
            return count

    def count(self, session_id: str | None = None) -> int:
        """统计记忆条目数量。

        如果指定 session_id，只统计该会话的记忆数量。
        """
        if session_id is not None:
            entry_ids = self._session_index.get(session_id, [])
            return sum(1 for eid in entry_ids if eid in self._entries)
        return len(self._entries)
