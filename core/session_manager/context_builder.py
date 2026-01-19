# -*- coding: utf-8 -*-

# @Project    :chatBI_develop_1_0_0
# @Version    :v1.0.0
# @File       :context_builder.py
# @Author     :
# @Describe   :对话上下文构建器


# context_builder.py
import json
from typing import List, Dict, Union, Optional


class ContextBuilder:
    def __init__(self,
                 max_history: int = 10,
                 max_tokens: int = 2048,
                 system_prompt: Optional[str] = None):
        """
        对话上下文处理器

        :param max_history: 最大历史记录条数
        :param max_tokens: 最大token限制（简易实现）
        :param system_prompt: 系统提示语（可选）
        """
        self.max_history = max_history
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt

    def _truncate_text(self, text: str, max_length: int) -> str:
        """简易文本截断，实际项目中应替换为真正的token计数"""
        return text[:max_length]

    def _count_tokens(self, text: str) -> int:
        """简易token计数（按空格分割），实际项目应使用tokenizer"""
        return len(text.split())

    def build_context(
            self,
            current_input: str,
            history: List[Dict[str, str]],
            include_system: bool = False
    ) -> List[Dict[str, str]]:
        """
        构建对话上下文

        :param current_input: 用户当前输入
        :param history: 历史对话记录，格式示例：
            [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好！有什么可以帮助您的？"},
                ...
            ]
        :param include_system: 是否包含系统提示
        :return: 处理后的完整上下文
        """
        # 1. 初始化上下文
        context = []

        # 2. 添加系统提示（如果存在且需要）
        if include_system and self.system_prompt:
            context.append({
                "role": "system",
                "content": self._truncate_text(self.system_prompt, self.max_tokens)
            })

        # 3. 截断历史记录（按条数）
        truncated_history = history[-self.max_history:]

        # 4. 合并历史和当前输入
        context.extend(truncated_history)
        # context.append({"role": "user", "content": current_input})

        # 5. 计算总token数（简易实现）
        total_tokens = sum(self._count_tokens(msg["content"]) for msg in context)

        # 6. 如果超出token限制，逐步移除最旧的历史记录
        while total_tokens > self.max_tokens and len(context) > 1:
            # 保留系统消息和当前输入，优先移除历史对话
            if len(context) > 2 and context[1]["role"] in ("user", "assistant"):
                removed = context.pop(1)  # 移除最旧的历史记录
                total_tokens -= self._count_tokens(removed["content"])
            else:
                break

        # 7. 最终检查当前输入长度
        if total_tokens > self.max_tokens:
            context[-1]["content"] = self._truncate_text(
                context[-1]["content"],
                max(1, self.max_tokens // 4)  # 至少保留1/4空间给当前输入
            )

        return context

    def to_prompt_string(
            self,
            context: List[Dict[str, str]],
            format: str = "plain"  # 可选: plain, json, huggingface
    ) -> Union[str, List[Dict]]:
        """
        将上下文转换为指定格式

        :param context: 构建好的上下文
        :param format: 输出格式
            - plain: 纯文本拼接
            - json: JSON字符串
            - huggingface: Hugging Face聊天格式（列表）
        :return: 格式化后的上下文
        """
        if format == "json":
            return json.dumps(context, ensure_ascii=False)

        if format == "huggingface":
            return context

        # 默认纯文本格式
        return "\n".join(
            [f"{msg['role'].upper()}: {msg['content']}"
             for msg in context]
        )


# 示例用法
if __name__ == "__main__":
    # 初始化处理器
    builder = ContextBuilder(
        max_history=5,
        max_tokens=512,
        system_prompt="你是一个专业的客服助手，请用简洁的语言回答问题"
    )

    # 模拟历史记录
    history = [
        {"role": "user", "content": "你们有哪些支付方式？"},
        {"role": "assistant", "content": "我们支持支付宝、微信支付和银行卡支付"},
        {"role": "user", "content": "国际信用卡可以吗？"},
        {"role": "assistant", "content": "目前暂不支持国际信用卡"}
    ]

    # 当前用户输入
    current_input = "那PayPal呢？"

    # 构建上下文
    context = builder.build_context(current_input, history)

    # 输出结果
    print("构建的上下文对象:")
    print(json.dumps(context, indent=2, ensure_ascii=False))

    print("\n纯文本格式:")
    print(builder.to_prompt_string(context))