# -*- coding: utf-8 -*-

# @Project    :chatBI-1.0.0-develop
# @Version    :v1.0.0
# @File       :memos_service.py
# @Author     :
# @Describe   :
import requests
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass


@dataclass
class Message:
    """聊天消息模型"""
    role: str  # "user" 或 "assistant"
    content: str


class MemOSProductAPIClient:
    """
    MemOS Product API 客户端类
    提供对运行在8000端口的Product API的完整访问
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        初始化API客户端

        Args:
            base_url: API服务器地址，默认为 http://localhost:8000
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

        # 用户管理接口

    def register_user(self, user_id: str, user_name: Optional[str] = None,
                      interests: Optional[str] = None) -> Dict[str, Any]:
        """
        注册新用户

        Args:
            user_id: 用户ID（必填）
            user_name: 用户名（可选）
            interests: 用户兴趣（可选）

        Returns:
            Dict: 包含注册结果的响应数据
            {
                "code": 200,
                "message": "User registered successfully",
                "data": {"user_id": "xxx", "mem_cube_id": "xxx"}
            }
        """
        url = f"{self.base_url}/product/users/register"
        data = {"user_id": user_id}
        if user_name:
            data["user_name"] = user_name
        if interests:
            data["interests"] = interests

        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def list_users(self) -> Dict[str, Any]:
        """
        列出所有用户

        Returns:
            Dict: 包含用户列表的响应数据
            {
                "code": 200,
                "message": "Users retrieved successfully",
                "data": [{"user_id": "xxx", ...}, ...]
            }
        """
        url = f"{self.base_url}/product/users"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户信息

        Args:
            user_id: 用户ID

        Returns:
            Dict: 包含用户信息的响应数据
            {
                "code": 200,
                "message": "User info retrieved successfully",
                "data": {"user_id": "xxx", "accessible_cubes": [...]}
            }
        """
        url = f"{self.base_url}/product/users/{user_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

        # 配置管理接口

    def set_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        设置MOSProduct配置

        Args:
            config: MOSProduct配置字典

        Returns:
            Dict: 配置设置结果
            {
                "code": 200,
                "message": "Configuration set successfully",
                "data": None
            }
        """
        url = f"{self.base_url}/product/configure"
        response = self.session.post(url, json=config)
        response.raise_for_status()
        return response.json()

    def get_config(self, user_id: str) -> Dict[str, Any]:
        """
        获取MOSProduct配置

        Args:
            user_id: 用户ID

        Returns:
            Dict: 包含配置信息的响应数据
        """
        url = f"{self.base_url}/product/configure/{user_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_user_config(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户特定配置

        Args:
            user_id: 用户ID

        Returns:
            Dict: 包含用户配置的响应数据
        """
        url = f"{self.base_url}/product/users/{user_id}/config"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def update_user_config(self, user_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新用户特定配置

        Args:
            user_id: 用户ID
            config: 新的配置数据

        Returns:
            Dict: 配置更新结果
        """
        url = f"{self.base_url}/product/users/{user_id}/config"
        response = self.session.put(url, json=config)
        response.raise_for_status()
        return response.json()

        # 记忆操作接口

    def add_memory(self, user_id: str, memory_content: Optional[str] = None,
                   messages: Optional[List[Message]] = None, doc_path: Optional[str] = None,
                   mem_cube_id: Optional[str] = None, source: Optional[str] = None,
                   user_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        添加新记忆

        Args:
            user_id: 用户ID（必填）
            memory_content: 记忆内容文本（可选）
            messages: 消息列表（可选）
            doc_path: 文档路径（可选）
            mem_cube_id: 记忆立方体ID（可选）
            source: 记忆来源（可选）
            user_profile: 用户配置文件（可选）

        Returns:
            Dict: 添加记忆的结果
            {
                "code": 200,
                "message": "Memory created successfully",
                "data": None
            }
        """
        url = f"{self.base_url}/product/add"
        data = {"user_id": user_id}

        if memory_content:
            data["memory_content"] = memory_content
        if messages:
            data["messages"] = [{"role": msg.role, "content": msg.content} for msg in messages]
        if doc_path:
            data["doc_path"] = doc_path
        if mem_cube_id:
            data["mem_cube_id"] = mem_cube_id
        if source:
            data["source"] = source
        if user_profile:
            data["user_profile"] = user_profile

        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def get_all_memories(self, user_id: str, memory_type: Optional[str] = None,
                         mem_cube_ids: Optional[List[str]] = None,
                         search_query: Optional[str] = None) -> Dict[str, Any]:
        """
        获取所有记忆或子图

        Args:
            user_id: 用户ID（必填）
            memory_type: 记忆类型（可选）
            mem_cube_ids: 记忆立方体ID列表（可选）
            search_query: 搜索查询（可选，如果提供则返回子图）

        Returns:
            Dict: 包含记忆数据的响应
            {
                "code": 200,
                "message": "Memories retrieved successfully",
                "data": [...]
            }
        """
        url = f"{self.base_url}/product/get_all"
        data = {"user_id": user_id}

        if memory_type:
            data["memory_type"] = memory_type
        if mem_cube_ids:
            data["mem_cube_ids"] = mem_cube_ids
        if search_query:
            data["search_query"] = search_query

        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def search_memories(self, user_id: str, query: str, mem_cube_id: Optional[str] = None,
                        top_k: int = 10) -> Dict[str, Any]:
        """
        搜索记忆

        Args:
            user_id: 用户ID（必填）
            query: 搜索查询（必填）
            mem_cube_id: 记忆立方体ID（可选）
            top_k: 返回结果数量（默认10）

        Returns:
            Dict: 包含搜索结果的响应
            {
                "code": 200,
                "message": "Search completed successfully",
                "data": {"results": [...], "total": 10}
            }
        """
        url = f"{self.base_url}/product/search"
        data = {
            "user_id": user_id,
            "query": query,
            "top_k": top_k
        }

        if mem_cube_id:
            data["mem_cube_id"] = mem_cube_id

        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

        # 聊天和建议接口

    def chat(self, user_id: str, query: str, mem_cube_id: Optional[str] = None,
             history: Optional[List[Dict[str, str]]] = None,
             internet_search: bool = False, stream: bool = False) -> Union[Dict[str, Any], requests.Response]:
        """
        与MemOS聊天

        Args:
            user_id: 用户ID（必填）
            query: 聊天查询（必填）
            mem_cube_id: 记忆立方体ID（可选）
            history: 聊天历史（可选）
            internet_search: 是否启用网络搜索（默认False）
            stream: 是否使用流式响应（默认False）

        Returns:
            Dict 或 Response: 如果stream=False返回完整响应字典，如果stream=True返回Response对象用于流式读取
            {
                "code": 200,
                "message": "Chat response generated",
                "data": "聊天回复内容"
            }
        """
        url = f"{self.base_url}/product/chat"
        data = {
            "user_id": user_id,
            "query": query,
            "internet_search": internet_search
        }

        if mem_cube_id:
            data["mem_cube_id"] = mem_cube_id
        if history:
            data["history"] = history

        if stream:
            # 返回流式响应对象，用户需要自己处理SSE流
            response = self.session.post(url, json=data, stream=True)
            response.raise_for_status()
            return response
        else:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            return response.json()

    def get_suggestions(self, user_id: str) -> Dict[str, Any]:
        """
        获取建议查询

        Args:
            user_id: 用户ID

        Returns:
            Dict: 包含建议查询的响应
            {
                "code": 200,
                "message": "Suggestions retrieved successfully",
                "data": {"suggestions": [...]}
            }
        """
        url = f"{self.base_url}/product/suggestions/{user_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_suggestions_with_language(self, user_id: str, language: str = "zh") -> Dict[str, Any]:
        """
        获取带语言偏好的建议

        Args:
            user_id: 用户ID
            language: 语言偏好（默认"zh"）

        Returns:
            Dict: 包含建议的响应
        """
        url = f"{self.base_url}/product/suggestions"
        data = {
            "user_id": user_id,
            "language": language
        }
        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

        # 实例管理接口

    def get_instance_status(self) -> Dict[str, Any]:
        """
        获取活跃用户配置状态

        Returns:
            Dict: 包含实例状态的响应
            {
                "code": 200,
                "message": "Instance status retrieved",
                "data": {"active_users": {...}}
            }
        """
        url = f"{self.base_url}/product/instances/status"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_active_user_count(self) -> Dict[str, Any]:
        """
        获取活跃用户数量

        Returns:
            Dict: 包含活跃用户数量的响应
            {
                "code": 200,
                "message": "Active user count retrieved",
                "data": {"count": 5}
            }
        """
        url = f"{self.base_url}/product/instances/count"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    # 使用示例


if __name__ == "__main__":
    # 创建客户端实例
    client = MemOSProductAPIClient("http://192.168.36.179:8000")

    # 注册用户
    result = client.register_user("tsts", "yonghu1", "tttt")
    print("用户注册结果:", result)

    # 添加记忆
    messages = [Message("user", "你好"), Message("assistant", "你好！有什么可以帮助你的吗？")]
    memory_result = client.add_memory("test_user", messages=messages)
    print("添加记忆结果:", memory_result)

    # 搜索记忆
    search_result = client.search_memories("test_user", "你好")
    print("搜索结果:", search_result)

    # 聊天
    chat_result = client.chat("test_user", "请介绍一下MemOS")