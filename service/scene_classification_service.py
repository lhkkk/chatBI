#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：chatbi
@File    ：scene_classification_service.py
@IDE     ：PyCharm
@Author  ：jyy
@Date    ：2025/8/4 下午2:57
'''
from typing import List, Dict, Optional

import pandas as pd
import requests
import toml

from langchain_classic.chains import LLMChain
from langchain_classic.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_community.chat_models import ChatTongyi
import json
from config import CommonConfig

log = CommonConfig.log

class SceneClassifier:
    """
    二级场景分类器：地域流量分析、客户流量分析、IP流量分析
    基于历史对话和实体识别分词列表，通过通义千问判断源端(source)与目的端(destination)。
    """
    def __init__(self, llm_chain: LLMChain):
        self.chain = llm_chain

    

    def get_secondary_scene(self, user_input, history_chat, tokens=None):
        """
        二级场景分类函数：规则先行、大模型兜底，基于关键词和规则判断确定二级场景
        
        Args:
            user_input: 用户输入文本
            history_chat: 历史对话记录
            tokens: 实体识别返回的分词列表
            
        Returns:
            包含二级场景分类结果的字典
        """
        import re
        import json
        
        # 如果tokens为空，使用简单规则提取关键词
        if tokens is None or not tokens:
            def extract_keywords(text):
                """提取文本中的关键词"""
                # 提取IP地址
                ip_matches = re.findall(r'\d{1,3}(?:\.\d{1,3}){3}', text)
                
                # 提取网段
                cidr_matches = re.findall(r'\d{1,3}(?:\.\d{1,3}){1,3}(?:/\d{1,2})?', text)
                
                # 提取关键词
                keyword_matches = re.findall(r'客户|账号|IP|ip|地址|网段|端口|路由器|地域|地市|省份|省际|家企宽|结算详情|气象局|公安局|小华家|客户id|客户ID|IDC+MAN', text)
                
                return list(set(ip_matches + cidr_matches + keyword_matches))
            
            tokens = extract_keywords(user_input)
        
        log.info(f"使用的关键词: {tokens}")
        
        # 1. 规则先行：基于规则的源端和目的端识别
        source, destination, rule_success = self._rule_based_extraction(user_input, tokens)
        
        # 2. 大模型兜底：如果规则识别失败，使用LLM进行补充
        if not rule_success:
            log.info("规则识别失败，使用大模型兜底")
            try:
                llm_source, llm_destination = self._llm_based_extraction(user_input, history_chat, tokens)
                if llm_source:
                    source = llm_source
                if llm_destination:
                    destination = llm_destination
            except Exception as e:
                log.error(f"大模型兜底失败: {e}")
        
        # 3. 场景分类：基于关键词的规则分类
        secondary_scene = self._rule_based_scene_classification(user_input, tokens)
        
        # 4. 完整性检查：确保源端和目的端都识别出来
        status_code, prompt = self._completeness_check(source, destination, user_input)
        
        log.info(f"场景分类结果: 场景={secondary_scene}, 状态码={status_code}, 源端={source}, 目的端={destination}")
        
        # 5. 构建返回结果
        result = {
            'status_code': status_code,
            'secondary_scene': secondary_scene,
            'prompt': prompt,
            'intermediate_result': {
                'keywords': tokens,
                'attributes': {
                    '源端': source if source else [],
                    '对端': destination if destination else []
                }
            }
        }

        return result

    def _is_ip(self, text: str) -> bool:
        try:
            import re
            # 正则表达式匹配IPv4地址，去掉\b边界，因为它无法匹配中文字符和数字之间的位置
            ip_pattern = r"\d{1,3}(?:\.\d{1,3}){3}"
            # 检查字符串中是否包含IP地址
            return bool(re.search(ip_pattern, text))
        except (TypeError, AttributeError):
            return False

    def _is_customer(self, text: str) -> bool:
        try:
            # 确保text是字符串
            text_str = str(text)
            for item in CommonConfig.CUSTOMER_MAPPING:
                if isinstance(item.get("客户名称"), str):
                    if text_str in item["客户名称"]:
                        return True
            return False
        except (TypeError, AttributeError, KeyError):
            # 如果出现任何类型错误，返回False
            return False

    def _rule_based_extraction(self, user_input, tokens):
        """
        基于规则的源端和目的端识别
        
        Args:
            user_input: 用户输入文本
            tokens: 分词列表
            
        Returns:
            source: 源端信息列表
            destination: 目的端信息列表
            success: 是否成功识别
        """
        import re
        
        source = []
        destination = []
        success = False
        
        user_input_lower = user_input.lower()
        
        # 提取IP地址
        ip_matches = re.findall(r'\d{1,3}(?:\.\d{1,3}){3}', user_input)
        
        # 提取地名
        location_matches = re.findall(r'浙江|广东|江苏|河南|杭州|台州|徐州|温州|宁波|绍兴|金华|嘉兴|湖州|舟山|丽水|衢州|广州|深圳|珠海|汕头|佛山|韶关|湛江|肇庆|江门|茂名|惠州|梅州|汕尾|河源|阳江|清远|东莞|中山|潮州|揭阳|云浮', user_input)
        
        # 提取客户名称（如【杭州市司法局】）
        customer_matches = re.findall(r'【.*?】', user_input)
        
        # 提取账号信息
        account_matches = re.findall(r'账号[^，。！？]*|客户id[^，。！？]*|客户ID[^，。！？]*', user_input)
        
        # 提取网段信息
        cidr_matches = re.findall(r'\d{1,3}(?:\.\d{1,3}){1,3}(?:/\d{1,2})?', user_input)
        
        # 提取关键词
        keyword_matches = re.findall(r'客户|账号|IP|ip|地址|网段|端口|路由器|地域|地市|省份|省际|家企宽|结算详情|气象局|公安局|小华家|客户id|客户ID|IDC|MAN|联通|外省|省内|省外|全国|跨省|异网|专线|城域网|AI|服务器|集群', user_input)
        
        # 合并所有提取的信息
        all_matches = ip_matches + location_matches + customer_matches + account_matches + cidr_matches + keyword_matches
        
        # 改进的规则：从...到... 格式
        if '从' in user_input and '到' in user_input:
            parts = user_input.split('从')
            if len(parts) > 1:
                to_parts = parts[1].split('到')
                if len(to_parts) > 1:
                    source_text = to_parts[0].strip()
                    destination_text = to_parts[1].strip()
                    
                    # 从提取的信息中匹配源端和目的端
                    for match in all_matches:
                        if match in source_text:
                            source.append(match)
                        if match in destination_text:
                            destination.append(match)
                    
                    if source and destination:
                        success = True
        
        # 如果上述规则失败，尝试基于关键词的规则
        if not success:
            # 检查是否有明确的目的端关键词
            destination_keywords = ['到', '流入', '流出到', '流向', '对端', '流入到', '流出']
            source_keywords = ['从', '源端', '源', '查询', '统计']
            
            # 如果有明确的目的端关键词
            for keyword in destination_keywords:
                if keyword in user_input:
                    # 提取目的端
                    parts = user_input.split(keyword)
                    if len(parts) > 1:
                        destination_text = parts[1].strip()
                        for match in all_matches:
                            if match in destination_text and match not in destination:
                                destination.append(match)
            
            # 如果有明确的源端关键词
            for keyword in source_keywords:
                if keyword in user_input:
                    # 提取源端
                    parts = user_input.split(keyword)
                    if len(parts) > 1:
                        source_text = parts[1].strip()
                        for match in all_matches:
                            if match in source_text and match not in source:
                                source.append(match)
            
            # 如果提取到了源端或目的端，认为成功
            if source or destination:
                success = True
        
        # 如果仍然没有识别出来，使用改进的默认规则
        if not success:
            # 检查是否有地域关键词
            region_keywords = ['浙江', '广东', '江苏', '河南', '杭州', '台州', '徐州', '外省', '省内', '省外', '全国', '跨省']
            for keyword in region_keywords:
                if keyword in user_input:
                    if not source:
                        source.append(keyword)
                    elif not destination:
                        destination.append(keyword)
            
            # 检查是否有客户关键词
            customer_keywords = ['气象局', '公安局', '客户id', '客户ID', '小华家', '账号', '客户']
            for keyword in customer_keywords:
                if keyword in user_input:
                    if not source:
                        source.append(keyword)
                    elif not destination:
                        destination.append(keyword)
            
            # 检查是否有IP关键词
            if ip_matches:
                if not source:
                    source.extend(ip_matches)
                elif not destination:
                    destination.extend(ip_matches)
            
            # 检查是否有网段关键词
            if cidr_matches:
                if not source:
                    source.extend(cidr_matches)
                elif not destination:
                    destination.extend(cidr_matches)
            
            # 如果至少识别出了一个，认为部分成功
            if source or destination:
                success = True
        
        # 改进的补充逻辑：基于上下文补充缺失的部分
        if source and not destination:
            # 根据源端类型补充目的端
            source_str = ' '.join(source)
            if any(keyword in source_str for keyword in ['外省', '省外', '跨省']):
                destination = ['本省']
            elif any(keyword in source_str for keyword in ['省内']):
                destination = ['外省']
            else:
                destination = ['省内']
            success = True
        elif destination and not source:
            # 根据目的端类型补充源端
            destination_str = ' '.join(destination)
            if any(keyword in destination_str for keyword in ['外省', '省外', '跨省']):
                source = ['本省']
            elif any(keyword in destination_str for keyword in ['省内']):
                source = ['外省']
            else:
                source = ['本省']
            success = True
        
        return source, destination, success

    def _llm_based_extraction(self, user_input, history_chat, tokens):
        """
        基于大模型的源端和目的端识别（兜底方案）
        
        Args:
            user_input: 用户输入文本
            history_chat: 历史对话记录
            tokens: 分词列表
            
        Returns:
            source: 源端信息列表
            destination: 目的端信息列表
        """
        source = []
        destination = []
        
        try:
            # 使用现有的LLM链进行提取
            llm_inputs = {
                "user_input": user_input,
                "history": str(history_chat),
                "tokens": str(tokens)
            }
            
            # 构建简单的LLM提示词
            prompt = f"""请从以下用户输入中提取源端和目的端信息：
用户输入：{user_input}
历史对话：{history_chat}
关键词：{tokens}

请按照JSON格式返回：{{"source": "源端信息", "destination": "目的端信息"}}
"""
            
            # 使用现有的LLM链（如果可用）
            if hasattr(self, 'chain') and self.chain:
                raw_output = self.chain.run(**llm_inputs)
                log.info(f"大模型提取结果: {raw_output}")
                
                # 解析结果
                import json
                result = json.loads(raw_output)
                
                if result.get("source"):
                    source = [result["source"]] if isinstance(result["source"], str) else result["source"]
                if result.get("destination"):
                    destination = [result["destination"]] if isinstance(result["destination"], str) else result["destination"]
            
        except Exception as e:
            log.error(f"大模型提取失败: {e}")
        
        return source, destination

    def _rule_based_scene_classification(self, user_input, tokens):
        """
        基于规则的场景分类
        
        Args:
            user_input: 用户输入文本
            tokens: 分词列表
            
        Returns:
            secondary_scene: 二级场景名称
        """
        import re
        
        user_input_lower = user_input.lower()
        tokens_lower = [token.lower() for token in tokens]
        
        # 客户流量分析关键词
        customer_keywords = ['气象局', '公安局', '客户id', '客户id为', '客户id:', '客户ID', '客户ID为', '客户ID:', '小华家', '账号', '客户']
        has_customer_keyword = any(keyword in user_input_lower for keyword in customer_keywords)
        
        # 检查是否有客户名称格式，如【杭州市司法局】
        has_customer_name = bool(re.search(r'【.*?】', user_input))
        
        # 账号相关关键词
        has_account = any(kw in user_input_lower for kw in ['账号', '家企宽账号', '企宽账号', '宽带账号', '账号id', '账号id:', '小明家', '小华家'])
        
        # IP流量分析关键词
        has_ip = bool(re.search(r'\d{1,3}(?:\.\d{1,3}){3}', user_input_lower))
        has_ip_keyword = any(kw in user_input_lower for kw in ['ip', 'IP', '地址', '网段', '端口', '路由器'])
        
        # 地域流量分析关键词
        has_region_keyword = any(kw in user_input_lower for kw in ['地域', '地市', '省份', '省际', '家企宽', '结算详情', '各个地市'])
        
        # 严格按照优先级规则进行场景分类
        # 最高优先级：客户流量分析 - 包含客户ID、气象局、公安局等关键词或客户名称格式
        if has_customer_keyword or has_customer_name:
            # 特殊处理：如果同时包含端口关键词，优先识别为IP流量分析
            if "端口" in user_input_lower:
                secondary_scene = "IP流量分析"
            else:
                secondary_scene = "客户流量分析"
        # 次高优先级：客户流量分析 - 包含账号相关关键词
        elif has_account:
            # 特殊处理：如果同时包含端口关键词，优先识别为IP流量分析
            if "端口" in user_input_lower:
                secondary_scene = "IP流量分析"
            else:
                secondary_scene = "客户流量分析"
        # 次高优先级：IP流量分析 - 包含具体IP地址
        elif has_ip:
            # 特殊处理：如果同时包含地域关键词，需要进一步判断
            if "各个地市" in user_input_lower or "地市" in user_input_lower:
                # 包含地市关键词，优先识别为地域流量分析
                secondary_scene = "地域流量分析"
            else:
                secondary_scene = "IP流量分析"
        # 次高优先级：IP流量分析 - 包含IP相关关键词
        elif has_ip_keyword:
            secondary_scene = "IP流量分析"
        # 最低优先级：地域流量分析 - 包含地域相关关键词或其他情况
        elif has_region_keyword:
            secondary_scene = "地域流量分析"
        # 默认情况：地域流量分析
        else:
            secondary_scene = "地域流量分析"
        
        return secondary_scene

    def _completeness_check(self, source, destination, user_input):
        """
        完整性检查：确保源端和目的端都识别出来
        
        Args:
            source: 源端信息列表
            destination: 目的端信息列表
            user_input: 用户输入文本
            
        Returns:
            status_code: 状态码（200表示完整，201表示需要补充）
            prompt: 提示信息
        """
        import re
        user_input_lower = user_input.lower()
        
        # 检查源端和目的端是否为空
        if not source and not destination:
            return 201, "请补充源端和目的端信息。"
        elif not source:
            return 201, "请补充源端信息。"
        elif not destination:
            return 201, "请补充目的端信息。"
        
        # 检查源端和目的端是否具体
        source_str = ' '.join(source) if isinstance(source, list) else str(source)
        destination_str = ' '.join(destination) if isinstance(destination, list) else str(destination)
        
        # 改进的IP检查逻辑：只有当用户明确要求具体IP时才需要补充
        if 'ip' in user_input_lower and not re.search(r'\d{1,3}(?:\.\d{1,3}){3}', source_str + destination_str):
            # 特殊处理：如果是"广东IP"、"浙江IP"等地域+IP组合，不要求补充具体IP
            if any(term in user_input_lower for term in ["广东ip", "浙江ip", "山东ip", "江苏ip", "单ip", "topip", "对应ip", "ip地址", "ip+username"]):
                return 200, ""
            # 如果用户查询的是客户、账号等非具体IP场景，也不需要补充具体IP
            elif any(term in user_input_lower for term in ["客户", "账号", "小华家", "家企宽", "气象局", "公安局"]):
                return 200, ""
            # 如果源端或目的端包含地域信息，也不需要补充具体IP
            elif any(region in source_str + destination_str for region in ["浙江", "广东", "江苏", "河南", "杭州", "台州", "徐州", "外省", "省内", "省外", "全国", "跨省"]):
                return 200, ""
            else:
                return 201, "请补充具体的IP地址。"
        
        # 改进的网段检查逻辑：只有当用户明确要求具体网段时才需要补充
        if '网段' in user_input_lower and not re.search(r'\d+', source_str + destination_str):
            # 如果用户查询的是客户、账号等非具体网段场景，也不需要补充具体网段
            if any(term in user_input_lower for term in ["客户", "账号", "小华家", "家企宽", "气象局", "公安局"]):
                return 200, ""
            # 如果源端或目的端包含地域信息，也不需要补充具体网段
            elif any(region in source_str + destination_str for region in ["浙江", "广东", "江苏", "河南", "杭州", "台州", "徐州", "外省", "省内", "省外", "全国", "跨省"]):
                return 200, ""
            else:
                return 201, "请补充具体的网段信息。"
        
        # 所有检查通过
        return 200, ""


def build_scene_chain(api_key: str, model_name: str = "qwen-max") -> LLMChain:
    """
    构建 LangChain 链，用于先总结历史对话与当前输入，再从 tokens 中提取 source 与 destination，并生成补充提示。
    输出 JSON 格式：
    {"source": ..., "destination": ..., "prompt": ...}
    """
    # 读取 TOML
    with open('./prompts/scene_prompt.toml', 'r', encoding='utf-8') as f:
        cfg = toml.load(f)
    print(cfg['second_scene']['template_system_second'])

    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(cfg['second_scene']['template_system_second']),
        HumanMessagePromptTemplate.from_template(cfg['second_scene']['template_user_second'])
    ])

    llm = ChatTongyi(temperature=0, model_name=model_name, dashscope_api_key=api_key)
    return LLMChain(llm=llm, prompt=prompt)

# 示例用法
if __name__ == "__main__":
    api_key = "sk-efea8858d7a142608b82e070fe4bfc1f"
    history = [
        "用户: 查询今年1月广东地市流量情况",
        "助手: 您想要查看哪种流量？",
        "用户: 流出外省流速"
    ]
    tokens = ['时间段','月','统计','广东','地市','流出','外省','流速']
    user_input = "请给出外省方向的实时流速趋势"
    payload = {'text': user_input}
    headers = {'Content-Type': 'application/json'}
    resp = requests.post('http://172.16.16.99:5050/nlp', json=payload, headers=headers)
    resp.raise_for_status()  # 若状态码不是 200，会抛出异常
    result = resp.json()

    print("Tokens:", result['tokens'])
    tokens = result['tokens']

    chain = build_scene_chain(api_key)
    classifier = SceneClassifier(chain)
    result = classifier.classify(user_input, history, tokens)
    print(result)

# {
#     "code": 200,
#     "primary_scene": "对话管理",
#     "current_input": "你好，请帮我查询天气。",
#     "history_input": ["早上好！", "今天天气怎么样？"]
# }
#
# {
#         "code": code, # 状态码
#         "second_scene": second_scene, # 明确的二级场景
#         "intermediate_result": {
#             "keywords": ["string", "..."],
#             "source": source, # 源端
#             "destination": destination # 目标端
#         },
#         "prompt": "" # 补充输入提示文本
#     }

    def _rule_based_extraction(self, user_input, tokens):
        """
        基于规则的源端和目的端识别
        
        Args:
            user_input: 用户输入文本
            tokens: 分词列表
            
        Returns:
            source: 源端信息列表
            destination: 目的端信息列表
            success: 是否成功识别
        """
        import re
        
        source = []
        destination = []
        success = False
        
        user_input_lower = user_input.lower()
        
        # 1. 识别源端
        # 检查是否有明确的源端关键词
        source_keywords = ['从', '由', '源', '起点', '起始', '流出', '发送', '发出']
        destination_keywords = ['到', '至', '目的', '终点', '目标', '流入', '接收', '到达']
        
        # 基于关键词的简单规则
        for i, token in enumerate(tokens):
            token_lower = token.lower()
            
            # 检查是否是源端关键词
            if any(keyword in token_lower for keyword in source_keywords):
                # 尝试获取源端内容
                if i + 1 < len(tokens):
                    source.append(tokens[i + 1])
                    success = True
            
            # 检查是否是目的端关键词
            elif any(keyword in token_lower for keyword in destination_keywords):
                # 尝试获取目的端内容
                if i + 1 < len(tokens):
                    destination.append(tokens[i + 1])
                    success = True
        
        # 2. 如果没有明确的关键词，使用基于内容的规则
        if not source and not destination:
            # 检查IP地址
            ip_pattern = r'\d{1,3}(?:\.\d{1,3}){3}'
            ip_matches = re.findall(ip_pattern, user_input)
            
            # 检查地域关键词
            region_keywords = ['广东', '浙江', '山东', '江苏', '北京', '上海', '广州', '深圳', '杭州', '南京']
            
            # 检查客户关键词
            customer_keywords = ['气象局', '公安局', '客户', '账号']
            
            # 基于内容识别源端和目的端
            for token in tokens:
                token_lower = token.lower()
                
                # 如果是IP地址，优先作为源端
                if re.match(ip_pattern, token):
                    source.append(token)
                    success = True
                # 如果是地域关键词
                elif any(region in token for region in region_keywords):
                    if '外省' in user_input_lower or '省外' in user_input_lower:
                        destination.append(token)
                    else:
                        source.append(token)
                    success = True
                # 如果是客户关键词
                elif any(customer in token for customer in customer_keywords):
                    source.append(token)
                    success = True
        
        # 3. 特殊处理：如果只有源端或只有目的端，尝试补充
        if source and not destination:
            if '外省' in user_input_lower or '省外' in user_input_lower:
                destination = ['外省']
            else:
                destination = ['省内']
            success = True
        elif destination and not source:
            source = ['本省']
            success = True
        
        return source, destination, success

    def _llm_based_extraction(self, user_input, history_chat, tokens):
        """
        基于大模型的源端和目的端识别（兜底方案）
        
        Args:
            user_input: 用户输入文本
            history_chat: 历史对话记录
            tokens: 分词列表
            
        Returns:
            source: 源端信息列表
            destination: 目的端信息列表
        """
        source = []
        destination = []
        
        try:
            # 使用现有的LLM链进行提取
            llm_inputs = {
                "user_input": user_input,
                "history": str(history_chat),
                "tokens": str(tokens)
            }
            
            # 构建简单的LLM提示词
            prompt = f"""请从以下用户输入中提取源端和目的端信息：
用户输入：{user_input}
历史对话：{history_chat}
关键词：{tokens}

请按照JSON格式返回：{{"source": "源端信息", "destination": "目的端信息"}}
"""
            
            # 使用现有的LLM链（如果可用）
            if hasattr(self, 'chain') and self.chain:
                raw_output = self.chain.run(**llm_inputs)
                log.info(f"大模型提取结果: {raw_output}")
                
                # 解析结果
                import json
                result = json.loads(raw_output)
                
                if result.get("source"):
                    source = [result["source"]] if isinstance(result["source"], str) else result["source"]
                if result.get("destination"):
                    destination = [result["destination"]] if isinstance(result["destination"], str) else result["destination"]
            
        except Exception as e:
            log.error(f"大模型提取失败: {e}")
        
        return source, destination

    def _rule_based_scene_classification(self, user_input, tokens):
        """
        基于规则的场景分类
        
        Args:
            user_input: 用户输入文本
            tokens: 分词列表
            
        Returns:
            secondary_scene: 二级场景名称
        """
        user_input_lower = user_input.lower()
        tokens_lower = [token.lower() for token in tokens]
        
        # 客户流量分析关键词
        customer_keywords = ['气象局', '公安局', '客户id', '客户id为', '客户id:', '客户ID', '客户ID为', '客户ID:', '小华家', '账号', '客户']
        has_customer_keyword = any(keyword in user_input_lower for keyword in customer_keywords)
        
        # 检查是否有客户名称格式，如【杭州市司法局】
        has_customer_name = bool(re.search(r'【.*?】', user_input))
        
        # 账号相关关键词
        has_account = any(kw in user_input_lower for kw in ['账号', '家企宽账号', '企宽账号', '宽带账号', '账号id', '账号id:', '小明家', '小华家'])
        
        # IP流量分析关键词
        has_ip = bool(re.search(r'\d{1,3}(?:\.\d{1,3}){3}', user_input_lower))
        has_ip_keyword = any(kw in user_input_lower for kw in ['ip', 'IP', '地址', '网段', '端口', '路由器'])
        
        # 地域流量分析关键词
        has_region_keyword = any(kw in user_input_lower for kw in ['地域', '地市', '省份', '省际', '家企宽', '结算详情', '各个地市'])
        
        # 严格按照优先级规则进行场景分类
        # 最高优先级：客户流量分析 - 包含客户ID、气象局、公安局等关键词或客户名称格式
        if has_customer_keyword or has_customer_name:
            secondary_scene = "客户流量分析"
        # 次高优先级：客户流量分析 - 包含账号相关关键词
        elif has_account:
            secondary_scene = "客户流量分析"
        # 次高优先级：IP流量分析 - 包含具体IP地址
        elif has_ip:
            # 特殊处理：如果同时包含地域关键词，需要进一步判断
            if "各个地市" in user_input_lower or "地市" in user_input_lower:
                # 包含地市关键词，优先识别为地域流量分析
                secondary_scene = "地域流量分析"
            else:
                secondary_scene = "IP流量分析"
        # 次高优先级：IP流量分析 - 包含IP相关关键词
        elif has_ip_keyword:
            secondary_scene = "IP流量分析"
        # 最低优先级：地域流量分析 - 包含地域相关关键词或其他情况
        elif has_region_keyword:
            secondary_scene = "地域流量分析"
        # 默认情况：地域流量分析
        else:
            secondary_scene = "地域流量分析"
        
        return secondary_scene

    def _completeness_check(self, source, destination, user_input):
        """
        完整性检查：确保源端和目的端都识别出来
        
        Args:
            source: 源端信息列表
            destination: 目的端信息列表
            user_input: 用户输入文本
            
        Returns:
            status_code: 状态码（200表示完整，201表示需要补充）
            prompt: 提示信息
        """
        user_input_lower = user_input.lower()
        
        # 检查源端和目的端是否为空
        if not source and not destination:
            return 201, "请补充源端和目的端信息。"
        elif not source:
            return 201, "请补充源端信息。"
        elif not destination:
            return 201, "请补充目的端信息。"
        
        # 检查源端和目的端是否具体
        source_str = ' '.join(source) if isinstance(source, list) else str(source)
        destination_str = ' '.join(destination) if isinstance(destination, list) else str(destination)
        
        # 检查是否有IP关键词但没有具体IP地址
        if 'ip' in user_input_lower and not re.search(r'\d{1,3}(?:\.\d{1,3}){3}', source_str + destination_str):
            # 特殊处理：如果是"广东IP"、"浙江IP"等地域+IP组合，不要求补充具体IP
            if any(term in user_input_lower for term in ["广东ip", "浙江ip", "山东ip", "江苏ip", "单ip", "topip"]):
                return 200, ""
            else:
                return 201, "请补充具体的IP地址。"
        
        # 检查是否有网段关键词但没有具体网段信息
        if '网段' in user_input_lower and not re.search(r'\d+', source_str + destination_str):
            return 201, "请补充具体的网段信息。"
        
        # 所有检查通过
        return 200, ""