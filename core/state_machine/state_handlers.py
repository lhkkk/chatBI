# -*- coding: utf-8 -*-

# @Project    :chatBI_develop_1_0_0
# @Version    :v1.0.0
# @File       :state_handlers.py
# @Author     :
# @Describe   :状态处理器 (每个状态码对应处理逻辑)


# state_handlers.py
from typing import Dict, Any, Optional, Tuple
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StateHandlers")


class StateHandlers:
    """状态处理器，负责处理不同状态码的业务逻辑"""

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化状态处理器

        :param config: 配置参数
        """
        self.config = config or {}
        self.handlers = {
            100: self.handle_new_session,
            101: self.handle_new_task,
            200: self.handle_primary_scene,
            201: self.handle_secondary_scene,
            202: self.handle_task_fields,
            203: self.handle_user_confirmation,
            204: self.handle_user_modification,
            300: self.handle_mcp_query,
            301: self.handle_supersonic_query,
            400: self.handle_casual_chat,
            500: self.handle_scene_mismatch
        }

    def process_state(self, state_code: int, session_data: Dict[str, Any], user_input: Optional[str] = None) -> Tuple[
        Dict, Optional[str]]:
        """
        处理状态请求

        :param state_code: 状态码
        :param session_data: 会话数据
        :param user_input: 用户输入（可选）
        :return: 更新后的会话数据和响应消息
        """
        handler = self.handlers.get(state_code)
        if not handler:
            logger.error(f"未知状态码: {state_code}")
            return session_data, "系统错误：未知状态"

        logger.info(f"处理状态 {state_code}，会话ID: {session_data.get('session_id')}")
        return handler(session_data, user_input)

    def handle_new_session(self, session_data: Dict, user_input: Optional[str]) -> Tuple[Dict, str]:
        """处理新会话状态 (100)"""
        # 初始化会话数据
        session_data.update({
            "state": 100,
            "task": None,
            "primary_scene": None,
            "secondary_scene": None,
            "fields": {},
            "confirmation_needed": False,
            "history": []
        })

        # 记录用户输入
        if user_input:
            session_data["history"].append({"role": "user", "content": user_input})

        # 欢迎消息
        welcome_msg = self.config.get("welcome_message", "您好！请问有什么可以帮您？")

        # 更新状态为等待用户输入
        session_data["state"] = 101  # 新任务状态
        return session_data, welcome_msg

    def handle_new_task(self, session_data: Dict, user_input: Optional[str]) -> Tuple[Dict, str]:
        """处理新任务状态 (101)"""
        if not user_input:
            return session_data, "请告诉我您需要什么帮助？"

        # 记录用户输入
        session_data["history"].append({"role": "user", "content": user_input})

        # 简单的意图识别（实际项目中应使用NLP模型）
        if "支付" in user_input or "付款" in user_input:
            session_data["state"] = 200  # 需要补充一级场景
            session_data["task"] = "支付咨询"
            return session_data, "请问您是想了解支付方式还是支付问题？"
        elif "订单" in user_input or "购买" in user_input:
            session_data["state"] = 200  # 需要补充一级场景
            session_data["task"] = "订单查询"
            return session_data, "请问您是想查询订单状态还是订单历史？"
        else:
            # 无法识别意图，进入闲聊状态
            session_data["state"] = 400
            return session_data, "我暂时不太明白您的意思，能再说详细一点吗？"

    def handle_primary_scene(self, session_data: Dict, user_input: Optional[str]) -> Tuple[Dict, str]:
        """处理一级场景补充状态 (200)"""
        if not user_input:
            return session_data, "请提供更多信息以便我帮助您"

        # 记录用户输入
        session_data["history"].append({"role": "user", "content": user_input})

        # 根据任务类型处理一级场景
        task = session_data.get("task")
        if task == "支付咨询":
            if "方式" in user_input or "方法" in user_input:
                session_data["primary_scene"] = "支付方式"
                session_data["state"] = 201  # 进入二级场景补充
                return session_data, "我们支持多种支付方式，请问您想了解国内支付还是国际支付？"
            elif "问题" in user_input or "失败" in user_input:
                session_data["primary_scene"] = "支付问题"
                session_data["state"] = 202  # 进入字段补充
                return session_data, "请提供您的订单号或支付凭证号，以便我们查询问题原因"

        # 默认响应
        session_data["state"] = 500  # 场景不符
        return session_data, "抱歉，我不太理解您的需求，请重新描述您的问题"

    def handle_secondary_scene(self, session_data: Dict, user_input: Optional[str]) -> Tuple[Dict, str]:
        """处理二级场景补充状态 (201)"""
        if not user_input:
            return session_data, "请提供更多信息以便我帮助您"

        # 记录用户输入
        session_data["history"].append({"role": "user", "content": user_input})

        # 根据一级场景处理二级场景
        primary_scene = session_data.get("primary_scene")
        if primary_scene == "支付方式":
            if "国内" in user_input:
                session_data["secondary_scene"] = "国内支付"
                session_data["state"] = 202  # 进入字段补充
                return session_data, "国内支付支持支付宝、微信和银行卡支付，请问您想了解哪种支付方式？"
            elif "国际" in user_input:
                session_data["secondary_scene"] = "国际支付"
                session_data["state"] = 202  # 进入字段补充
                return session_data, "国际支付支持Visa、MasterCard和PayPal，请问您想了解哪种支付方式？"

        # 默认响应
        session_data["state"] = 500  # 场景不符
        return session_data, "抱歉，我不太理解您的选择，请重新回答"

    def handle_task_fields(self, session_data: Dict, user_input: Optional[str]) -> Tuple[Dict, str]:
        """处理任务字段补充状态 (202)"""
        if not user_input:
            return session_data, "请提供所需的信息"

        # 记录用户输入
        session_data["history"].append({"role": "user", "content": user_input})

        # 根据场景收集字段
        task = session_data.get("task")
        if task == "订单查询":
            # 假设用户提供了订单号
            if len(user_input) > 8 and user_input.isalnum():
                session_data["fields"]["order_id"] = user_input
                session_data["state"] = 203  # 进入用户确认
                return session_data, f"您要查询的订单号是 {user_input}，确认查询吗？"

        # 默认响应
        return session_data, "信息已记录，还需要其他信息吗？"

    def handle_user_confirmation(self, session_data: Dict, user_input: Optional[str]) -> Tuple[Dict, str]:
        """处理用户确认状态 (203)"""
        if not user_input:
            return session_data, "请确认是否继续"

        # 记录用户输入
        session_data["history"].append({"role": "user", "content": user_input})

        # 处理用户确认
        if "是" in user_input or "确认" in user_input or "对的" in user_input:
            # 确认通过，进入查询状态
            session_data["state"] = 300  # MCP查询
            return session_data, "正在查询，请稍候..."
        else:
            # 确认不通过
            session_data["state"] = 204  # 用户修改问题
            return session_data, "好的，请提供正确的信息"

    def handle_user_modification(self, session_data: Dict, user_input: Optional[str]) -> Tuple[Dict, str]:
        """处理用户修改问题状态 (204)"""
        if not user_input:
            return session_data, "请提供修改后的信息"

        # 记录用户输入
        session_data["history"].append({"role": "user", "content": user_input})

        # 根据之前的场景决定下一步
        if session_data.get("state_before_confirmation") == 203:
            # 返回字段补充状态
            session_data["state"] = 202
            return session_data, "信息已更新，还需要其他信息吗？"

        # 默认返回新任务状态
        session_data["state"] = 101
        return session_data, "好的，请重新描述您的需求"

    def handle_mcp_query(self, session_data: Dict, user_input: Optional[str]) -> Tuple[Dict, str]:
        """处理MCP查询状态 (300)"""
        # 这里模拟MCP查询，实际项目中应调用真实服务
        task = session_data.get("task")
        result = "查询失败"

        if task == "订单查询":
            order_id = session_data["fields"].get("order_id")
            if order_id:
                # 模拟查询结果
                result = f"订单 {order_id} 状态：已发货，预计明天送达"
            else:
                result = "缺少订单号，无法查询"

        # 更新状态为完成
        session_data["state"] = 101  # 返回新任务状态

        # 记录系统响应
        session_data["history"].append({"role": "assistant", "content": result})
        return session_data, result

    def handle_supersonic_query(self, session_data: Dict, user_input: Optional[str]) -> Tuple[Dict, str]:
        """处理Supersonic查询状态 (301)"""
        # 模拟Supersonic查询
        result = "Supersonic查询结果：数据加载中..."

        # 更新状态为完成
        session_data["state"] = 101  # 返回新任务状态

        # 记录系统响应
        session_data["history"].append({"role": "assistant", "content": result})
        return session_data, result

    def handle_casual_chat(self, session_data: Dict, user_input: Optional[str]) -> Tuple[Dict, str]:
        """处理闲聊状态 (400)"""
        if not user_input:
            return session_data, "您好，有什么可以帮您？"

        # 记录用户输入
        session_data["history"].append({"role": "user", "content": user_input})

        # 简单的闲聊响应（实际项目中应使用NLP模型）
        if "你好" in user_input or "您好" in user_input:
            response = "您好！请问有什么可以帮您？"
        elif "谢谢" in user_input:
            response = "不客气，很高兴为您服务！"
        elif "再见" in user_input or "拜拜" in user_input:
            response = "再见！如有其他问题，随时欢迎咨询。"
        else:
            response = "我还在学习中，暂时不能回答这个问题"

        # 保持闲聊状态
        return session_data, response

    def handle_scene_mismatch(self, session_data: Dict, user_input: Optional[str]) -> Tuple[Dict, str]:
        """处理场景不符状态 (500)"""
        # 重置任务相关状态
        session_data.update({
            "task": None,
            "primary_scene": None,
            "secondary_scene": None,
            "fields": {},
            "confirmation_needed": False
        })

        # 返回到新任务状态
        session_data["state"] = 101

        # 提示用户重新输入
        return session_data, "抱歉，我不太理解您的需求，请重新描述您的问题"


# 示例使用
if __name__ == "__main__":
    # 创建状态处理器
    handlers = StateHandlers(config={
        "welcome_message": "欢迎使用智能客服系统！"
    })

    # 模拟会话流程
    session_data = {"session_id": "12345"}

    # 新会话
    session_data, response = handlers.process_state(100, session_data)
    print(f"状态 100: {response}")

    # 用户输入
    user_input = "我想查订单"

    # 处理新任务
    session_data, response = handlers.process_state(101, session_data, user_input)
    print(f"状态 101: {response}")

    # 一级场景补充
    session_data, response = handlers.process_state(200, session_data, "订单状态")
    print(f"状态 200: {response}")

    # 字段补充
    session_data, response = handlers.process_state(202, session_data, "ORD12345678")
    print(f"状态 202: {response}")

    # 用户确认
    session_data, response = handlers.process_state(203, session_data, "是的")
    print(f"状态 203: {response}")

    # MCP查询
    session_data, response = handlers.process_state(300, session_data)
    print(f"状态 300: {response}")