# -*- coding: utf-8 -*-

# @Project    :chatBI-1.0.0-develop
# @Version    :v1.0.0
# @File       :memu_service.py
# @Author     :
# @Describe   :
import os
from memu import MemuClient

# 初始化客户端
memu_client = MemuClient(
    base_url="https://api.memu.so",
    api_key="mu_jkC8iXVgFllNqopbcAwRjAzW_jJpw3LnWyX6igEo6K2Ofvc9bnC4owV8QEMaYVXTFJgPsgPtgIBv3I_jlnzYTCGviEmT0tqpbpRvYMLr9NlU"  # 或直接粘贴您的密钥
)

# 定义对话内容
conversation = [
    {"role": "user", "content": "我喜欢徒步登山。有什么安全建议吗？"},
    {"role": "assistant", "content": "以下是登山安全必备建议：务必告知他人您的路线和预计返回时间。出发前检查天气状况，若天气恶化要做好折返准备。"}
]

# 存入记忆系统
response = memu_client.memorize_conversation(
    conversation=conversation,
    user_id="user001",
    user_name="User",
    agent_id="assistant001",
    agent_name="Assistant"
)

print(f"记忆已存储！任务 ID: {response.task_id}")

import time

for i in range(100):
    time.sleep(1)
    status = memu_client.get_task_status(response.task_id)
    print(f"任务状态: {status.status}")


# 搜索相关记忆
memories = memu_client.retrieve_related_memory_items(
    user_id="user001",
    query="登山",
    top_k=3,
    min_similarity=0.0
)

# 显示结果
print(f"找到 {memories.total_found} 条相关记忆：")
for memory_item in memories.related_memories:
    print(f"- {memory_item.memory.content[:100]}...")


# 删除用户的所有记忆
delete_response = memu_client.delete_memories(user_id="user001")
print(f"已删除 {delete_response.deleted_count} 条记忆")

# 关闭客户端连接
memu_client.close()

