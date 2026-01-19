# -*- coding: utf-8 -*-

# @Project    :chatBI_develop_1_0_0
# @Version    :v1.0.0
# @File       :session_store.py
# @Author     :
# @Describe   :会话存储(Redis/SQL)


# context_builder.py
import json
import time
from typing import List, Dict, Union, Optional, Any
import redis  # 需要安装：pip install redis


class SessionStorage:
    """会话存储抽象基类"""

    def save_session(self, session_id: str, history: List[Dict[str, str]], ttl: int = None):
        """保存会话历史"""
        raise NotImplementedError

    def get_session(self, session_id: str) -> List[Dict[str, str]]:
        """获取会话历史"""
        raise NotImplementedError

    def delete_session(self, session_id: str):
        """删除会话"""
        raise NotImplementedError

    def session_exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        raise NotImplementedError


class MemorySessionStorage(SessionStorage):
    """基于内存的会话存储（使用字典）"""

    def __init__(self):
        self.sessions = {}
        self.expiry_times = {}  # 用于存储过期时间

    def save_session(self, session_id: str, history: List[Dict[str, str]], ttl: int = None):
        """保存会话到内存"""
        self.sessions[session_id] = history

        # 设置过期时间（秒）
        if ttl:
            self.expiry_times[session_id] = time.time() + ttl
            # 启动后台清理（简单实现）
            self._clean_expired_sessions()

    def get_session(self, session_id: str) -> List[Dict[str, str]]:
        """从内存获取会话"""
        # 检查是否过期
        if session_id in self.expiry_times and time.time() > self.expiry_times[session_id]:
            self.delete_session(session_id)
            return []

        return self.sessions.get(session_id, [])

    def delete_session(self, session_id: str):
        """从内存删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.expiry_times:
            del self.expiry_times[session_id]

    def session_exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        return session_id in self.sessions

    def _clean_expired_sessions(self):
        """清理过期会话（简单实现）"""
        current_time = time.time()
        expired_ids = [sid for sid, exp_time in self.expiry_times.items() if exp_time < current_time]

        for sid in expired_ids:
            self.delete_session(sid)


class RedisSessionStorage(SessionStorage):
    """基于Redis的会话存储"""

    def __init__(self, host='localhost', port=6379, db=0, password=None):
        self.redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True  # 自动解码为字符串
        )

    def save_session(self, session_id: str, history: List[Dict[str, str]], ttl: int = None):
        """保存会话到Redis"""
        # 将会话历史序列化为JSON字符串
        history_json = json.dumps(history)
        self.redis.set(f"chat_session:{session_id}", history_json)

        # 设置过期时间
        if ttl:
            self.redis.expire(f"chat_session:{session_id}", ttl)

    def get_session(self, session_id: str) -> List[Dict[str, str]]:
        """从Redis获取会话"""
        history_json = self.redis.get(f"chat_session:{session_id}")
        if history_json:
            return json.loads(history_json)
        return []

    def delete_session(self, session_id: str):
        """从Redis删除会话"""
        self.redis.delete(f"chat_session:{session_id}")

    def session_exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        return self.redis.exists(f"chat_session:{session_id}") == 1