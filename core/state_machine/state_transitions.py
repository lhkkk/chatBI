# -*- coding: utf-8 -*-

# @Project    :chatBI_develop_1_0_0
# @Version    :v1.0.0
# @File       :state_transitions.py
# @Author     :
# @Describe   :状态转移规则 (处理100-600状态流转)


# state_transitions.py
from typing import Dict, Any, Optional, Callable, Tuple, List
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StateTransitions")


class StateTransitions:
    """状态转移规则管理器 - 按照新的业务逻辑实现"""

    def __init__(self):
        """
        初始化状态转移规则
        """
        # 状态转移规则表
        # 格式: {当前状态: [(条件函数, 下一个状态)]}
        self.transition_rules = {
            # 后端处理逻辑

            # 新会话状态 (100) - 由后端判断
            100: [
                (self.is_new_session, 100),  # 新会话 -> 100
            ],

            # 已有会话状态 - 由后端判断
            "existing_session": [
                (self.last_state_was_400, 101),  # 上条是闲聊 -> 新任务
                (self.last_state_was_200_201_202, lambda s, d, u: d.get("last_algorithm_state")),  # 保持原状态
                (self.last_state_was_203_and_confirmed, 300),  # 用户确认 -> MCP查询
                (self.last_state_was_203_and_not_confirmed, 204),  # 用户未确认 -> 修改信息
            ],

            # 算法处理逻辑

            # 新会话/新任务状态 (100/101) - 算法处理
            100: [
                (self.is_casual_chat, 400),  # 闲聊 -> 闲聊
                (self.is_not_casual_chat, 200),  # 非闲聊 -> 一级场景补充
            ],

            101: [
                (self.is_casual_chat, 400),  # 闲聊 -> 闲聊
                (self.is_not_casual_chat, 200),  # 非闲聊 -> 一级场景补充
            ],

            # 一级场景补充状态 (200) - 算法处理
            200: [
                (self.is_new_task_intent, 101),  # 检测到新任务意图 -> 新任务
                (self.scene_supplement_completed, 201),  # 一级场景补充完成 -> 二级场景补充
                (self.scene_supplement_needed, 200),  # 需要继续补充 -> 保持200
            ],

            # 二级场景补充状态 (201) - 算法处理
            201: [
                (self.is_new_task_intent, 101),  # 检测到新任务意图 -> 新任务
                (self.scene_supplement_completed, 202),  # 二级场景补充完成 -> 任务字段补充
                (self.scene_supplement_needed, 201),  # 需要继续补充 -> 保持201
            ],

            # 任务字段补充状态 (202) - 算法处理
            202: [
                (self.is_new_task_intent, 101),  # 检测到新任务意图 -> 新任务
                (self.fields_supplement_completed, 203),  # 字段补充完成 -> 用户确认
                (self.fields_supplement_needed, 202),  # 需要继续补充 -> 保持202
            ],

            # 用户确认状态 (203) - 算法处理
            203: [
                (self.user_confirmed, 203),  # 用户确认 -> 保持203 (后端会处理)
                (self.user_denied, 204),  # 用户否认 -> 用户修改
            ],

            # 用户修改状态 (204) - 算法处理
            204: [
                (self.user_modified, 203),  # 用户已修改 -> 重新确认
            ],

            # 后端专用状态 - 不经过算法

            # MCP查询状态 (300) - 后端处理
            300: [
                (self.mcp_success, 101),  # MCP成功 -> 新任务
                (self.mcp_failed, 301),  # MCP失败 -> Supersonic查询
            ],

            # Supersonic查询状态 (301) - 后端处理
            301: [
                (self.supersonic_success, 101),  # Supersonic成功 -> 新任务
                (self.supersonic_failed, 101),  # Supersonic失败 -> 新任务
            ],

            # 闲聊状态 (400) - 算法处理
            400: [
                (self.is_task_related, 101),  # 用户提到任务 -> 新任务
                (self.default_condition, 400),  # 默认 -> 保持闲聊
            ]
        }

    def determine_next_state(self, current_state: int, session_data: Dict[str, Any],
                             user_input: Optional[str] = None, is_backend: bool = True) -> int:
        """
        根据当前状态和上下文确定下一个状态

        :param current_state: 当前状态码
        :param session_data: 会话数据
        :param user_input: 用户输入（可选）
        :param is_backend: 是否是后端处理阶段
        :return: 下一个状态码
        """
        # 后端处理逻辑
        if is_backend:
            # 新会话判断
            if not session_data.get("history") or len(session_data["history"]) == 0:
                logger.info("后端判断: 新会话 -> 状态 100")
                return 100

            # 已有会话处理
            last_algorithm_state = session_data.get("last_algorithm_state")

            if last_algorithm_state == 400:  # 上条是闲聊
                logger.info("后端判断: 上条是闲聊(400) -> 新任务(101)")
                return 101

            elif last_algorithm_state in [200, 201, 202]:  # 上条是场景/字段补充
                logger.info(f"后端判断: 保持上条状态 {last_algorithm_state}")
                return last_algorithm_state

            elif last_algorithm_state == 203:  # 上条是用户确认
                if self.user_confirmed(None, session_data, user_input):
                    logger.info("后端判断: 用户已确认(203) -> MCP查询(300)")
                    return 300
                else:
                    logger.info("后端判断: 用户未确认(203) -> 修改信息(204)")
                    return 204

        # 算法处理逻辑
        # 获取当前状态的所有转移规则
        rules = self.transition_rules.get(current_state, [])

        if not rules:
            logger.warning(f"没有找到状态 {current_state} 的转移规则")
            return current_state  # 保持当前状态

        # 遍历所有规则，找到第一个满足条件的规则
        for condition_func, next_state in rules:
            if callable(next_state):
                # 如果是函数，动态计算下一个状态
                next_state_val = next_state(current_state, session_data, user_input)
            else:
                next_state_val = next_state

            if condition_func(current_state, session_data, user_input):
                logger.info(f"状态转移: {current_state} -> {next_state_val}")
                return next_state_val

        # 如果没有满足的条件，使用默认规则
        default_rule = next((rule for rule in rules if rule[0] == self.default_condition), None)
        if default_rule:
            if callable(default_rule[1]):
                return default_rule[1](current_state, session_data, user_input)
            return default_rule[1]

        return current_state  # 没有匹配规则，保持当前状态

    # ===================== 条件函数 =====================

    def default_condition(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """默认条件，总是返回True"""
        return True

    def is_new_session(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查是否是新会话"""
        return current_state == 100

    def last_state_was_400(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查上条状态是否是400（闲聊）"""
        return session_data.get("last_algorithm_state") == 400

    def last_state_was_200_201_202(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查上条状态是否是200、201或202"""
        return session_data.get("last_algorithm_state") in [200, 201, 202]

    def last_state_was_203_and_confirmed(self, current_state: int, session_data: Dict,
                                         user_input: Optional[str]) -> bool:
        """检查上条状态是203且用户已确认"""
        return session_data.get("last_algorithm_state") == 203 and self.user_confirmed(current_state, session_data,
                                                                                       user_input)

    def last_state_was_203_and_not_confirmed(self, current_state: int, session_data: Dict,
                                             user_input: Optional[str]) -> bool:
        """检查上条状态是203且用户未确认"""
        return session_data.get("last_algorithm_state") == 203 and not self.user_confirmed(current_state, session_data,
                                                                                           user_input)

    def is_casual_chat(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查是否是闲聊"""
        if not user_input:
            return False

        # 简单实现 - 实际应使用NLP模型
        casual_keywords = ["你好", "谢谢", "再见", "天气", "名字", "帮助", "吗？", "哈哈", "呵呵"]
        task_keywords = ["支付", "订单", "查询", "问题", "退款", "发货"]

        # 包含闲聊关键词且不包含任务关键词
        return (any(kw in user_input for kw in casual_keywords) and  (not any(kw in user_input for kw in task_keywords)))

    def is_not_casual_chat(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查是否不是闲聊"""
        return not self.is_casual_chat(current_state, session_data, user_input)

    def is_new_task_intent(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查用户输入是否包含新任务意图"""
        if not user_input:
            return False

        # 检测任务改变关键词
        change_keywords = ["重新", "新问题", "另一个", "不同", "不是这个", "换一个"]
        return any(kw in user_input for kw in change_keywords)

    def scene_supplement_completed(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查场景补充是否完成"""
        if not user_input:
            return False

        # 简单实现 - 实际应使用NLU模型
        # 根据当前状态判断补充是否完成
        if current_state == 200:  # 一级场景补充
            return "方式" in user_input or "问题" in user_input or "状态" in user_input
        elif current_state == 201:  # 二级场景补充
            return "国内" in user_input or "国际" in user_input or "状态" in user_input

        return False

    def scene_supplement_needed(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查场景是否需要继续补充"""
        return not self.scene_supplement_completed(current_state, session_data, user_input)

    def fields_supplement_completed(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查任务字段补充是否完成"""
        if not user_input:
            return False

        # 简单实现 - 实际应使用信息抽取模型
        # 检查是否提供了关键字段值
        if "订单" in session_data.get("task", ""):
            # 订单相关任务需要订单号
            return any(char.isdigit() for char in user_input) and len(user_input) > 6
        elif "支付" in session_data.get("task", ""):
            # 支付相关任务需要金额或交易号
            return "¥" in user_input or "元" in user_input or any(char.isdigit() for char in user_input)

        return False

    def fields_supplement_needed(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查任务字段是否需要继续补充"""
        return not self.fields_supplement_completed(current_state, session_data, user_input)

    def user_confirmed(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查用户是否确认"""
        if not user_input:
            return False
        confirm_keywords = ["是", "确认", "对的", "正确", "ok", "yes", "没问题", "是的"]
        return any(kw in user_input for kw in confirm_keywords)

    def user_denied(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查用户是否否认"""
        if not user_input:
            return False
        deny_keywords = ["不是", "不对", "错误", "修改", "no", "重新", "换一个", "不正确"]
        return any(kw in user_input for kw in deny_keywords)

    def user_modified(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查用户是否已修改"""
        # 只要有新输入就视为已修改
        return bool(user_input)

    def is_task_related(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查用户输入是否与任务相关"""
        if not user_input:
            return False

        task_keywords = ["支付", "订单", "查询", "问题", "退款", "发货", "物流", "金额"]
        return any(kw in user_input for kw in task_keywords)

    def mcp_success(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查MCP查询是否成功"""
        # 这里简化处理，实际应用中需要根据MCP的返回结果判断
        return True

    def mcp_failed(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查MCP查询是否失败"""
        # 这里简化处理，实际应用中需要根据MCP的返回结果判断
        return False

    def supersonic_success(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查Supersonic查询是否成功"""
        # 这里简化处理
        return True

    def supersonic_failed(self, current_state: int, session_data: Dict, user_input: Optional[str]) -> bool:
        """检查Supersonic查询是否失败"""
        # 这里简化处理
        return False


# 示例使用
if __name__ == "__main__":
    # 创建状态转移管理器
    transitions = StateTransitions()


    # 模拟后端处理
    def simulate_backend(session_data: Dict, user_input: str) -> int:
        """模拟后端处理逻辑"""
        # 后端判断
        next_state = transitions.determine_next_state(
            session_data.get("state"),
            session_data,
            user_input,
            is_backend=True
        )
        session_data["state"] = next_state
        return next_state


    # 模拟算法处理
    def simulate_algorithm(session_data: Dict, user_input: str) -> int:
        """模拟算法处理逻辑"""
        # 算法处理
        next_state = transitions.determine_next_state(
            session_data.get("state"),
            session_data,
            user_input,
            is_backend=False
        )
        session_data["state"] = next_state
        session_data["last_algorithm_state"] = next_state  # 记录算法返回的状态
        return next_state


    # 测试用例1: 全新会话
    print("\n=== 测试用例1: 全新会话 ===")
    session_data = {"history": []}  # 空历史表示新会话
    user_input = "我想查询订单状态"

    # 后端处理
    backend_state = simulate_backend(session_data, user_input)
    print(f"后端处理结果: {backend_state} (应为 100)")

    # 算法处理
    algorithm_state = simulate_algorithm(session_data, user_input)
    print(f"算法处理结果: {algorithm_state} (应为 200)")

    # 测试用例2: 已有会话 - 上条是闲聊
    print("\n=== 测试用例2: 上条是闲聊 ===")
    session_data = {
        "history": [{"role": "assistant", "content": "今天天气不错", "state": 400}],
        "last_algorithm_state": 400
    }
    user_input = "我想了解支付问题"

    # 后端处理
    backend_state = simulate_backend(session_data, user_input)
    print(f"后端处理结果: {backend_state} (应为 101)")

    # 算法处理
    algorithm_state = simulate_algorithm(session_data, user_input)
    print(f"算法处理结果: {algorithm_state} (应为 200)")

    # 测试用例3: 场景补充流程
    print("\n=== 测试用例3: 场景补充流程 ===")
    session_data = {
        "state": 200,
        "task": "支付咨询",
        "history": [{"role": "user", "content": "支付问题", "state": 200}],
        "last_algorithm_state": 200
    }

    # 一级场景补充
    user_input = "支付方式"
    algorithm_state = simulate_algorithm(session_data, user_input)
    print(f"一级场景补充结果: {algorithm_state} (应为 201)")

    # 二级场景补充
    user_input = "国际支付"
    algorithm_state = simulate_algorithm(session_data, user_input)
    print(f"二级场景补充结果: {algorithm_state} (应为 202)")

    # 测试用例4: 用户确认流程
    print("\n=== 测试用例4: 用户确认流程 ===")
    session_data = {
        "state": 203,
        "task": "订单查询",
        "fields": {"order_id": "ORD123456"},
        "history": [{"role": "assistant", "content": "请确认订单号", "state": 203}],
        "last_algorithm_state": 203
    }

    # 用户确认
    user_input = "是的，确认"
    backend_state = simulate_backend(session_data, user_input)
    print(f"用户确认后端处理: {backend_state} (应为 300)")

    # MCP查询 (后端处理)
    mcp_result = "查询成功"
    print(f"MCP查询结果: {mcp_result}")
    session_data["state"] = 101  # 重置为新任务

    # 测试用例5: 用户修改流程
    print("\n=== 测试用例5: 用户修改流程 ===")
    session_data = {
        "state": 203,
        "task": "订单查询",
        "fields": {"order_id": "ORD123456"},
        "history": [{"role": "assistant", "content": "请确认订单号", "state": 203}],
        "last_algorithm_state": 203
    }

    # 用户不确认
    user_input = "不对，订单号错了"
    backend_state = simulate_backend(session_data, user_input)
    print(f"用户不确认后端处理: {backend_state} (应为 204)")

    # 算法处理修改
    algorithm_state = simulate_algorithm(session_data, user_input)
    print(f"算法处理修改结果: {algorithm_state} (应为 203)")
