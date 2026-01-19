#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/8/21 17:46
# @Author  : jyy
# @File    : fill_template_pipeline_service.py
# @Software: PyCharm
# fill_template_pipeline.py
"""
填充问题模板流水线：
- 输入：secondary_scene, third_scene, keywords, user_input, history, defaults.toml（可选）
- 处理：
    1. 规则抽取（rule_extract）
    2. LLM 抽取（llm_extract，调用 ChatTongyi）
    3. 合并决策（merge_extractions）
    4. 构建模板字段（使用合并结果或默认值）
    5. 生成完整问题并用 LLM 改写成 N 个相似问题（回退为规则改写）
- 输出： {"template_fields":..., "filled_question": "...", "rewrites": [...], "merged": ...}
"""

import os
import re
import json
from typing import List, Dict, Any, Optional, Callable
from config import CommonConfig

try:
    import toml
except Exception:
    toml = None

from langchain_classic.chains import LLMChain
from langchain_classic.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_community.chat_models import ChatTongyi
log = CommonConfig.log
# -------------------------
# 内置默认（当 defaults.toml 不存在或缺项时）
# -------------------------
BUILTIN_DEFAULTS = {
    "time": {"default": "近一个月"},
    "direction": {"default": "流出"},
    "speed_unit": {"default": "Gbps"},
    "requirement_defaults": {
        "aggregation": "按均值统计",
        "breakdown": "按类型进行细分统计"
    },
    "type_defaults": {"source_type": "", "destination_type": ""},
    "rewrite": {"n": 1}
}

# 字段映射字典：将属性提取器的中文字段映射到模板的英文字段
FIELD_MAPPING = {
    "源端": "source",
    "对端": "destination", 
    "源端类型": "source_type",
    "对端类型": "destination_type",
    "时间": "time_range",
    "时间粒度": "time_granularity",
    "流向": "direction",
    "数据类型": "data_type",
    "剔除条件": "exclude_conditions",
    "上行下行": "up_down"
}

# -------------------------
# 工具：加载 toml 配置
# -------------------------
def load_defaults(path: str = "defaults.toml") -> Dict[str, Any]:
    cfg = {}
    if toml is not None and os.path.exists(path):
        try:
            cfg = toml.load(path)
            if not isinstance(cfg, dict):
                cfg = {}
        except Exception:
            cfg = {}
    merged = {}
    for k, v in BUILTIN_DEFAULTS.items():
        merged[k] = v.copy() if isinstance(v, dict) else v
    for k, v in (cfg.items() if isinstance(cfg, dict) else []):
        if isinstance(v, dict) and k in merged:
            merged[k].update(v)
        else:
            merged[k] = v
    return merged

# -------------------------
# safe json loads：从 LLM 文本里尽量抽取 JSON
# -------------------------
def safe_json_loads(text: str) -> Optional[Dict[str, Any]]:
    if not text or "{" not in text:
        return None
    t = text.strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    start = t.find("{")
    balance = 0
    for i in range(start, len(t)):
        ch = t[i]
        if ch == "{":
            balance += 1
        elif ch == "}":
            balance -= 1
            if balance == 0:
                cand = t[start:i+1]
                try:
                    return json.loads(cand)
                except Exception:
                    break
    return None

# -------------------------
# 规则抽取：快速确定显式字段与证据（正则 / 关键词）
# -------------------------
IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
CIDR_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}/\d{1,2}\b")
UNIT_CANDIDATES = ["gbps", "mbps", "gb", "mb"]
AGG_KEYWORDS = {
    "按月聚合": ["按月", "每月", "月"],
    "按日聚合": ["按日", "每天", "日"],
    "按小时聚合": ["按小时", "小时"]
}
DIRECTION_KEYWORDS = {
    "流出": ["流出", "出省", "出口"],
    "流入": ["流入", "进省", "入口"],
    "流入流出": ["双向", "流入流出", "交互"]
}
TYPE_INDICATORS = ["IDC", "MAN", "客户", "账号", "用户"]

def rule_extract(history: List[dict], user_input: str, keywords: List[str]) -> Dict[str, Any]:
    """
    返回结构：
    {
      "extracted": {field: value, ...},
      "confidence": {field: score, ...},
      "evidence": {field: "..." , ...}
    }
    """
    import re  # 确保re模块在函数作用域内可用
    his_input = []
    print(history)
    for item in history:
        # 提取历史中的有用文本信息
        for key, value in item.items():
            if isinstance(value, str):
                his_input.append(value)
            elif isinstance(value, dict):
                # 提取intermediate_result中的关键词、源端和目的端
                if "keywords" in value and isinstance(value["keywords"], list):
                    his_input.extend([str(kw) for kw in value["keywords"] if kw])
                if "source" in value:
                    source_val = value["source"]
                    if isinstance(source_val, list):
                        his_input.extend([str(s) for s in source_val if s])
                    else:
                        his_input.append(str(source_val))
                if "destination" in value:
                    dest_val = value["destination"]
                    if isinstance(dest_val, list):
                        his_input.extend([str(d) for d in dest_val if d])
                    else:
                        his_input.append(str(dest_val))
            elif isinstance(value, list):
                his_input.extend([str(v) for v in value if v])
    print('-------------------------')
    print(his_input)
    print('=======================================')
    print(user_input)
    print('----------------------------------')
    print(keywords)
    # 合并所有文本信息，包括历史、用户输入和关键词
    all_text = " ".join((his_input or []) + [user_input] + (keywords or []))
    txt = all_text.lower()
    
    # 初始化结果
    res = {"extracted": {}, "confidence": {}, "evidence": {}}
    
    # 处理direction：检查流向，支持多流向返回列表
    directions = []
    
    # 1. 检查是否包含双向关键词
    if any(keyword in txt for keyword in ["双向", "流入流出", "交互"]):
        directions.extend(["流入", "流出"])
    
    # 2. 检查是否同时包含流入和流出关键词
    has_inflow = any(keyword in txt for keyword in ["流入", "进省", "入口"])
    has_outflow = any(keyword in txt for keyword in ["流出", "出省", "出口"])
    
    if has_inflow and has_outflow:
        directions.extend(["流入", "流出"])
    
    # 3. 检查单个流向关键词
    if has_inflow and "流入" not in directions:
        directions.append("流入")
    elif has_outflow and "流出" not in directions:
        directions.append("流出")
    
    # 4. 默认流出
    if not directions:
        directions.append("流出")
    
    # 设置方向结果
    res["extracted"]["direction"] = directions
    res["confidence"]["direction"] = 0.9 if len(directions) > 1 else 0.8
    res["evidence"]["direction"] = f"matched:{', '.join(directions)}"

    # source/destination: 从用户输入和keywords中提取源端和目的端
    # 1. 首先从用户输入中提取
    user_input_lower = user_input.lower()
    
    # 处理包含"和"的句式，如"A和B交互流量统计"、"指定A和B交互流量统计"、"A和B流量统计"等
    if "和" in user_input and ("流量" in user_input_lower or "统计" in user_input_lower):
        # 提取"和"前后的内容
        parts = user_input.split("和")
        if len(parts) == 2:
            # 提取A部分
            a_part = parts[0].strip()
            # 移除"指定"等前缀
            if a_part.startswith("指定"):
                a_part = a_part[2:].strip()
            # 提取B部分
            b_part = parts[1].strip()
            # 移除"交互流量"、"交互流量统计"、"流量"、"统计"等后缀
            suffixes = ["交互流量", "交互流量统计", "流量", "统计", "情况", "分析", "报表"]
            for suffix in suffixes:
                if b_part.endswith(suffix):
                    b_part = b_part[:-len(suffix)].strip()
                    break
            
            # 智能判断源端和目的端
            # 检查是否有方向关键词
            direction = None
            for k, kws in DIRECTION_KEYWORDS.items():
                for kw in kws:
                    if kw in user_input_lower:
                        direction = k
                        break
                if direction:
                    break
            
            # 如果有方向关键词，将符合方向的作为源端或目的端
            if direction == "流出":
                res["extracted"]["source"] = a_part
                res["extracted"]["destination"] = b_part
            elif direction == "流入":
                res["extracted"]["source"] = b_part
                res["extracted"]["destination"] = a_part
            else:
                # 如果没有方向关键词，根据内容判断
                # 检查是否包含省份、城市等地域信息
                location_keywords = ["广东", "北京", "上海", "江苏", "浙江", "福建", "山东", "河南", "湖北", "湖南", "广东城域网", "城域网", "IDC", "MAN"]
                a_is_location = any(keyword in a_part for keyword in location_keywords)
                b_is_location = any(keyword in b_part for keyword in location_keywords)
                
                if a_is_location and b_is_location:
                    # 如果都是地域，将第一个作为源端，第二个作为目的端
                    res["extracted"]["source"] = a_part
                    res["extracted"]["destination"] = b_part
                elif a_is_location:
                    # 如果只有a是地域，将a作为源端
                    res["extracted"]["source"] = a_part
                    res["extracted"]["destination"] = b_part
                elif b_is_location:
                    # 如果只有b是地域，将b作为目的端
                    res["extracted"]["source"] = a_part
                    res["extracted"]["destination"] = b_part
                else:
                    # 其他情况，将两个都作为源端和目的端
                    res["extracted"]["source"] = [a_part, b_part]
                    res["extracted"]["destination"] = [a_part, b_part]
            
            res["confidence"]["source"] = 0.8
            res["confidence"]["destination"] = 0.8
            res["evidence"]["source"] = f"和句式提取: {a_part}"
            res["evidence"]["destination"] = f"和句式提取: {b_part}"
    
    # 2. 首先检查用户输入中是否包含IP地址或网段信息
    user_input_lower = user_input.lower()
    
    # 处理"网段是xxx"这种句式
    network_segment = None
    if "网段是" in user_input_lower:
        # 提取"网段是"后面的内容
        network_part = user_input_lower.split("网段是")[-1].strip()
        # 提取网段中的数字部分，支持完整和不完整网段格式
        network_match = re.search(r"\d{1,3}(?:\.\d{1,3}){1,3}", network_part)
        if network_match:
            network_segment = network_match.group(0)
    
    # 处理IP地址
    ip_pattern = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    ip_matches = re.findall(ip_pattern, user_input)
    
    if network_segment:
        # 提取到网段信息
        # 检查是否有之前的源端信息（如"外省网段"）
        prev_source = ""
        for item in history:
            if isinstance(item, dict) and "intermediate_result" in item:
                ir = item["intermediate_result"]
                # 优先从新的attributes结构中获取
                if "attributes" in ir and ir["attributes"].get("源端"):
                    source_val = ir["attributes"]["源端"]
                    if isinstance(source_val, list):
                        prev_source = " ".join([str(s) for s in source_val if s])
                    else:
                        prev_source = str(source_val)
                    break
                # 兼容旧的source字段
                elif "source" in ir:
                    source_val = ir["source"]
                    if isinstance(source_val, list):
                        prev_source = " ".join([str(s) for s in source_val if s])
                    else:
                        prev_source = str(source_val)
                    break
        
        # 如果有之前的源端信息（如"外省网段"），则结合生成新的源端（如"外省123.4.5网段"）
        if prev_source and "网段" in prev_source:
            new_source = re.sub(r"网段", f"{network_segment}网段", prev_source)
        else:
            new_source = f"{network_segment}网段"
        
        res["extracted"]["source"] = new_source
        res["confidence"]["source"] = 1.0
        res["evidence"]["source"] = f"网段句式提取: {new_source}"
    elif ip_matches:
        # 提取到IP地址
        ip_address = ip_matches[0]
        
        # 检查是否是"ip是xxx"或"IP是xxx"这样的句式
        if "ip是" in user_input_lower or "ip地址是" in user_input_lower:
            # 检查是否有之前的源端信息（如"广东IP"）
            prev_source = ""
            province_info = ""
            for item in history:
                if isinstance(item, dict) and "intermediate_result" in item:
                    ir = item["intermediate_result"]
                    # 优先从新的attributes结构中获取
                    if "attributes" in ir and ir["attributes"].get("源端"):
                        source_val = ir["attributes"]["源端"]
                        if isinstance(source_val, list):
                            prev_source = " ".join([str(s) for s in source_val if s])
                        else:
                            prev_source = str(source_val)
                        # 从之前的源端中提取省份信息
                        provinces = ["广东", "北京", "上海", "江苏", "浙江", "福建", "山东", "河南", "湖北", "湖南"]
                        for province in provinces:
                            if province in prev_source:
                                province_info = province
                                break
                        break
                    # 兼容旧的source字段
                    elif "source" in ir:
                        source_val = ir["source"]
                        if isinstance(source_val, list):
                            prev_source = " ".join([str(s) for s in source_val if s])
                        else:
                            prev_source = str(source_val)
                        # 从之前的源端中提取省份信息
                        provinces = ["广东", "北京", "上海", "江苏", "浙江", "福建", "山东", "河南", "湖北", "湖南"]
                        for province in provinces:
                            if province in prev_source:
                                province_info = province
                                break
                        break
            
            # 如果有省份信息，将省份信息与IP地址结合作为源端
            if province_info:
                res["extracted"]["source"] = f"{province_info}的ip{ip_address}"
                res["confidence"]["source"] = 1.0
                res["evidence"]["source"] = f"省份IP结合提取: {province_info}{ip_address}"
            else:
                # 否则直接将IP地址作为源端
                res["extracted"]["source"] = ip_address
                res["confidence"]["source"] = 1.0
                res["evidence"]["source"] = f"IP句式提取: {ip_address}"
        else:
            # 检查history和keywords中是否包含省份信息
            province_info = ""
            # 从history中提取省份信息
            for item in history:
                for key, value in item.items():
                    if isinstance(value, str):
                        # 检查是否包含省份信息
                        provinces = ["广东", "北京", "上海", "江苏", "浙江", "福建", "山东", "河南", "湖北", "湖南"]
                        for province in provinces:
                            if province in value:
                                province_info = province
                                break
                    if province_info:
                        break
                if province_info:
                    break
            
            # 从keywords中提取省份信息
            if not province_info:
                provinces = ["广东", "北京", "上海", "江苏", "浙江", "福建", "山东", "河南", "湖北", "湖南"]
                for keyword in keywords:
                    if keyword in provinces:
                        province_info = keyword
                        break
            
            # 如果有省份信息，将省份信息与IP地址结合作为源端，格式优化为"省份的ipIP地址"
            if province_info:
                res["extracted"]["source"] = f"{province_info}的ip{ip_address}"
                res["confidence"]["source"] = 1.0
                res["evidence"]["source"] = f"省份IP结合提取: {province_info}{ip_address}"
            else:
                # 否则直接将IP地址作为源端
                res["extracted"]["source"] = ip_address
                res["confidence"]["source"] = 1.0
                res["evidence"]["source"] = f"IP地址提取: {ip_address}"
    
    # 3. 如果没有提取到源端，检查是否有历史中的源端信息
    if not res["extracted"].get("source"):
        # 检查历史中的源端信息
        prev_source = ""
        for item in history:
            if isinstance(item, dict) and "intermediate_result" in item:
                ir = item["intermediate_result"]
                # 优先从新的attributes结构中获取
                if "attributes" in ir and ir["attributes"].get("源端"):
                    source_val = ir["attributes"]["源端"]
                    if isinstance(source_val, list):
                        prev_source = " ".join([str(s) for s in source_val if s])
                    else:
                        prev_source = str(source_val)
                    break
                # 兼容旧的source字段
                elif "source" in ir:
                    source_val = ir["source"]
                    if isinstance(source_val, list):
                        prev_source = " ".join([str(s) for s in source_val if s])
                    else:
                        prev_source = str(source_val)
                    break
        
        if prev_source:
            res["extracted"]["source"] = prev_source
            res["confidence"]["source"] = 0.8
            res["evidence"]["source"] = f"历史源端提取: {prev_source}"
    
    # 4. 如果没有提取到目的端，检查是否有历史中的目的端信息
    if not res["extracted"].get("destination"):
        # 检查历史中的目的端信息
        prev_dest = ""
        for item in history:
            if isinstance(item, dict) and "intermediate_result" in item:
                ir = item["intermediate_result"]
                # 优先从新的attributes结构中获取
                if "attributes" in ir and ir["attributes"].get("对端"):
                    dest_val = ir["attributes"]["对端"]
                    if isinstance(dest_val, list):
                        prev_dest = " ".join([str(d) for d in dest_val if d])
                    else:
                        prev_dest = str(dest_val)
                    break
                # 兼容旧的destination字段
                elif "destination" in ir:
                    dest_val = ir["destination"]
                    if isinstance(dest_val, list):
                        prev_dest = " ".join([str(d) for d in dest_val if d])
                    else:
                        prev_dest = str(dest_val)
                    break
        
        if prev_dest:
            res["extracted"]["destination"] = prev_dest
            res["confidence"]["destination"] = 0.8
            res["evidence"]["destination"] = f"历史目的端提取: {prev_dest}"

    # 4. 处理省内/省外流量情况，不要简单地将目标端设置为"本省+外省"，需要根据具体情况判断
    # 只有当问题明确要求统计省内省外都有的时候，才将目标端设置为"本省和外省"
    # 如果已经有明确的目的端，不要覆盖
    # 只有当没有明确的目的端时，才考虑设置为"本省和外省"
    if not res["extracted"].get("destination"):
        # 检查是否需要设置为"本省和外省"
        has_province_related = any(keyword in txt for keyword in ["省内", "省外", "本省", "外省"])
        if has_province_related:
            # 检查是否有明确的方向要求
            has_direction = False
            for k, kws in DIRECTION_KEYWORDS.items():
                for kw in kws:
                    if kw in txt:
                        has_direction = True
                        break
                if has_direction:
                    break
            
            # 检查是否是交互流量
            is_interactive = "交互" in txt
            
            # 检查是否有明确的地域目的端
            has_specific_destination = False
            # 检查历史中是否有明确的目的端
            for item in history:
                if isinstance(item, dict) and "intermediate_result" in item:
                    ir = item["intermediate_result"]
                    if "destination" in ir:
                        dest_val = ir["destination"]
                        if dest_val and dest_val != "":
                            has_specific_destination = True
                            break
            
            # 只有当没有明确的方向要求，且没有明确的地域目的端，或者包含"交互"关键词时，才将目标端设置为"本省和外省"
            if not has_specific_destination and (not has_direction or is_interactive):
                res["extracted"]["destination"] = "本省和外省"
                res["confidence"]["destination"] = 1.0
                res["evidence"]["destination"] = "省内/省外流量分析，目标端设置为本省和外省"
    
    # 5. IP/CIDR优先（仅设置源端，目标端如果已经是本省+外省则不覆盖）
    ipm = IP_RE.search(txt)
    if ipm:
        ipv = ipm.group(0)
        # 判断IP地址是源端还是目的端
        # 检查是否有"源IP"、"源端IP"、"源地址"等关键词
        if any(keyword in user_input_lower for keyword in ["源ip", "源端ip", "源地址", "源端地址"]):
            res["extracted"]["source"] = ipv
            res["confidence"]["source"] = max(res["confidence"].get("source", 0.0), 1.0)
            res["evidence"]["source"] = res["evidence"].get("source", "") + f";ip:{ipv}"
        # 检查是否有"目的IP"、"目标IP"、"目的地址"、"目标地址"等关键词
        elif any(keyword in user_input_lower for keyword in ["目的ip", "目标ip", "目的地址", "目标地址"]):
            res["extracted"]["destination"] = ipv
            res["confidence"]["destination"] = max(res["confidence"].get("destination", 0.0), 1.0)
            res["evidence"]["destination"] = res["evidence"].get("destination", "") + f";ip:{ipv}"
        else:
            # 检查history中是否包含之前的源端信息
            has_prev_source = False
            prev_source = ""
            for item in history:
                for key, value in item.items():
                    if isinstance(value, dict) and 'source' in value and value['source']:
                        prev_source = value['source']
                        has_prev_source = True
                        break
                    elif isinstance(value, str):
                        # 从字符串中提取源端信息
                        source_match = re.search(r'source\s*:\s*["\']?([^"\']+)["\']?', value) or re.search(r'源端\s*:\s*["\']?([^"\']+)["\']?', value)
                        if source_match:
                            prev_source = source_match.group(1)
                            has_prev_source = True
                            break
                if has_prev_source:
                    break
            
            if has_prev_source and prev_source:
                # 如果有之前的源端信息，结合当前IP地址构建完整源端
                # 例如："外省网段" + "1.2.3.4" -> "外省1.2.3.4网段"
                new_source = re.sub(r'网段', f'{ipv}网段', str(prev_source))
                res["extracted"]["source"] = new_source
                res["confidence"]["source"] = max(res["confidence"].get("source", 0.0), 1.0)
                res["evidence"]["source"] = res["evidence"].get("source", "") + f";结合历史源端信息构建: {new_source}"
            else:
                # 如果没有明确的源端或目的端标识，检查是否已经有源端或目的端
                # 优先将IP地址设置为源端
                if not res["extracted"].get("source"):
                    res["extracted"]["source"] = ipv
                    res["confidence"]["source"] = max(res["confidence"].get("source", 0.0), 1.0)
                    res["evidence"]["source"] = res["evidence"].get("source", "") + f";ip:{ipv}"
                # 如果已经有源端，检查是否有IP关键词，如果有，替换源端为IP地址
                elif "ip" in user_input_lower and (res["extracted"]["source"] == "IP" or res["extracted"]["source"] == "ip"):
                    res["extracted"]["source"] = ipv
                    res["confidence"]["source"] = max(res["confidence"].get("source", 0.0), 1.0)
                    res["evidence"]["source"] = res["evidence"].get("source", "") + f";ip:{ipv}"
                # 只有当目标端未设置时，才将IP地址设为目标端
                # 如果目标端已经是本省+外省，则不覆盖
                elif not res["extracted"].get("destination"):
                    res["extracted"]["destination"] = ipv
                    res["confidence"]["destination"] = max(res["confidence"].get("destination", 0.0), 1.0)
                    res["evidence"]["destination"] = res["evidence"].get("destination", "") + f";ip:{ipv}"

    cidrm = CIDR_RE.search(txt)
    if cidrm:
        cidrv = cidrm.group(0)
        # 判断CIDR是源端还是目的端
        if any(keyword in user_input_lower for keyword in ["源ip", "源端ip", "源地址", "源端地址", "源网段", "源端网段"]):
            res["extracted"]["source"] = cidrv
            res["confidence"]["source"] = max(res["confidence"].get("source", 0.0), 0.95)
            res["evidence"]["source"] = res["evidence"].get("source", "") + f";cidr:{cidrv}"
        elif any(keyword in user_input_lower for keyword in ["目的ip", "目标ip", "目的地址", "目标地址", "目的网段", "目标网段"]):
            res["extracted"]["destination"] = cidrv
            res["confidence"]["destination"] = max(res["confidence"].get("destination", 0.0), 0.95)
            res["evidence"]["destination"] = res["evidence"].get("destination", "") + f";cidr:{cidrv}"
        else:
            if not res["extracted"].get("source"):
                res["extracted"]["source"] = cidrv
                res["confidence"]["source"] = max(res["confidence"].get("source", 0.0), 0.95)
                res["evidence"]["source"] = res["evidence"].get("source", "") + f";cidr:{cidrv}"
            elif not res["extracted"].get("destination"):
                res["extracted"]["destination"] = cidrv
                res["confidence"]["destination"] = max(res["confidence"].get("destination", 0.0), 0.95)
                res["evidence"]["destination"] = res["evidence"].get("destination", "") + f";cidr:{cidrv}"

    # direction：已经在开头统一处理，此处不再重复处理

    # time_range：找数字+单位 或 上月/本月/近一个月
    m = re.search(r"(\d+)\s*(天|日|月|小时)", txt)
    if m:
        res["extracted"]["time_range"] = m.group(0)
        res["confidence"]["time_range"] = 0.9
        res["evidence"]["time_range"] = f"regex:{m.group(0)}"
    else:
        if "上月" in txt or "本月" in txt or "近一个月" in txt:
            res["extracted"]["time_range"] = "近一个月"
            res["confidence"]["time_range"] = 0.8
            res["evidence"]["time_range"] = "keyword month"

    # aggregation
    for agg, kws in AGG_KEYWORDS.items():
        for kw in kws:
            if kw in txt:
                res["extracted"]["requirement1"] = agg
                res["confidence"]["requirement1"] = 0.8
                res["evidence"]["requirement1"] = f"matched:{kw}"
                break
        if "requirement1" in res["extracted"]:
            break

    # speed unit
    for u in UNIT_CANDIDATES:
        if u in txt:
            res["extracted"]["speed_unit"] = u.upper()
            res["confidence"]["speed_unit"] = 0.9
            res["evidence"]["speed_unit"] = f"unit:{u}"
            break

    # types (IDC/MAN/客户/城域网)
    found_types = []
    
    # 先检查源端和目的端中是否包含特定类型
    source_str = str(res["extracted"].get("source", ""))
    destination_str = str(res["extracted"].get("destination", ""))
    
    # 检查源端类型
    source_types = []
    for t in TYPE_INDICATORS:
        if t.lower() in source_str.lower() or t.lower() in txt:
            source_types.append(t)
    # 检查是否包含城域网
    if "城域网" in source_str:
        source_types.append("城域网")
    
    # 检查目的端类型
    dest_types = []
    for t in TYPE_INDICATORS:
        if t.lower() in destination_str.lower() or t.lower() in txt:
            dest_types.append(t)
    # 检查是否包含城域网
    if "城域网" in destination_str:
        dest_types.append("城域网")
    
    # 移除重复类型
    source_types = list(set(source_types))
    dest_types = list(set(dest_types))
    
    # 设置源端类型
    if source_types:
        source_val = "和".join(source_types)
        res["extracted"]["source_type"] = source_val
        res["confidence"]["source_type"] = 0.8
        res["evidence"]["source_type"] = f"matched:{source_types}"
    
    # 设置目的端类型
    if dest_types:
        dest_val = "和".join(dest_types)
        res["extracted"]["destination_type"] = dest_val
        res["confidence"]["destination_type"] = 0.8
        res["evidence"]["destination_type"] = f"matched:{dest_types}"
    # 如果目的端是城域网但没有匹配到类型，设置为城域网
    elif "城域网" in destination_str:
        res["extracted"]["destination_type"] = "城域网"
        res["confidence"]["destination_type"] = 0.8
        res["evidence"]["destination_type"] = f"matched:城域网"

    # requirement2: 如果用户提到 '细分' 或 keywords 含 IDC/MAN，则构建 breakdown evidence
    # if "细分" in txt or any(k.upper() in ("IDC", "MAN") for k in (keywords or [])):
    #     # 简单说明，具体组合构建在后面填表阶段
    #     res["extracted"]["requirement2_evidence"] = "细分 or type keywords present"
    #     res["confidence"]["requirement2"] = 0.6

    return res

# -------------------------
# LLM 抽取：要求返回严格 JSON，包含 extracted/confidence/evidence
# -------------------------
def build_llm_extract_chain(api_key: str, model_name: str = "general") -> LLMChain:
    system = """
你是结构化信息抽取助手。请基于下面给定的对话历史、当前输入、关键词和规则证据（rules_evidence）
从文本中抽取以下字段（如果没有请返回空字符串）：
- source: 流量的发起方。应提取地理区域（省/地市）、客户名称/ID、账号、IP/网段等实体描述，不包含时间信息和业务类型。
- destination: 流量的接收方。应提取地理区域（省/地市）、客户名称/ID、账号、IP/网段等实体描述，不包含时间信息和业务类型。
- time_range: 时间范围，如"最近3天"、"2025.10.1到2025.11.29"等
- direction: 流量方向（流入/流出）
- source_type: 源端业务类型
- destination_type: 目的端业务类型
- speed_unit: 流速单位
- requirement1: 第一个需求
- requirement2: 第二个需求

请严格输出 JSON，格式：
{{
  "extracted": {{ "source":"", "destination":"", "source_type":"", "destination_type":"", "time_range":"", "direction":"", "speed_unit":"", "aggregation":"", "breakdown":"", "metric":"" }},
  "confidence": {{ "source": 0.0, "destination": 0.0, "source_type": 0.0, "destination_type": 0.0, "time_range": 0.0, "direction": 0.0, "speed_unit": 0.0, "aggregation": 0.0, "breakdown": 0.0, "metric": 0.0 }},
  "evidence": {{ "source":"", "destination":"", "source_type":"", "destination_type":"", "time_range":"", "direction":"", "speed_unit":"", "aggregation":"", "breakdown":"", "metric":"" }}
}}
置信度范围 0-1，请在 evidence 中简要说明提取依据（引用 tokens/历史片段或规则证据）。
不要输出任何非 JSON 文本。
"""
    human = "对话历史: {history}\n当前输入: {current_input}\nkeywords: {keywords}\nrules_evidence: {rules_evidence}"
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system),
        HumanMessagePromptTemplate.from_template(human)
    ])
    llm = ChatTongyi(temperature=0, model_name=model_name, dashscope_api_key=api_key)
    return LLMChain(llm=llm, prompt=prompt)

def llm_extract(api_key: str, history: List[str], user_input: str, keywords: List[str], rules_evidence: Dict[str, Any], model_name: str = "general") -> Dict[str, Any]:
    chain = build_llm_extract_chain(api_key, model_name=model_name)
    rules_json = json.dumps(rules_evidence or {}, ensure_ascii=False)
    log.info(f"rules_json: {rules_json}")
    log.info(f"keywords: {keywords}")
    log.info(f"history: {history}")
    log.info(f"user_input: {user_input}")
    log.info(f"api_key: {api_key}")
    raw = chain.run(history=history, current_input=user_input or "", keywords=",".join(keywords or []), rules_evidence=rules_json)
    parsed = safe_json_loads(raw)
    if not parsed:
        return {"extracted": {}, "confidence": {}, "evidence": {}, "raw": raw}
    parsed["raw"] = raw
    return parsed

# -------------------------
# validators
# -------------------------
def is_valid_time(val: str) -> bool:
    if not val: return False
    if re.search(r"\d+", val): return True
    for w in ("月", "天", "日", "小时", "星期", "周"):
        if w in val:
            return True
    return False

def is_valid_direction(val: Any) -> bool:
    if isinstance(val, list):
        # 检查列表中的每个方向是否有效
        return all(item in ("流出", "流入", "双向", "流入流出") for item in val)
    elif isinstance(val, str):
        return val in ("流出", "流入", "双向", "流入流出")
    return False

def is_valid_unit(val: str) -> bool:
    if not val: return False
    return val.lower() in ("gbps", "mbps", "gb", "mb")

def is_valid_type(val: str) -> bool:
    return bool(val)

VALIDATORS = {
    "source": lambda v: bool(v),
    "destination": lambda v: bool(v),
    "time_range": is_valid_time,
    "direction": lambda v: is_valid_direction(v) if v else True,  # allow empty
    "source_type": is_valid_type,
    "destination_type": is_valid_type,
    "speed_unit": lambda v: is_valid_unit(v) if v else True,
    "requirement1": lambda v: bool(v),
    "requirement2": lambda v: bool(v)
}

# -------------------------
# 合并逻辑（同前）
# -------------------------
def merge_field(field_name: str, rule_val: Any, rule_conf: float, llm_val: Any, llm_conf: float, validate_fn: Callable[[Any], bool], thr_rule: float = 0.9, thr_llm: float = 0.7, delta: float = 0.15) -> Dict[str, Any]:
    rule_valid = bool(rule_val) and validate_fn(rule_val)
    llm_valid = bool(llm_val) and validate_fn(llm_val)

    if rule_valid and rule_conf >= thr_rule:
        return {"value": rule_val, "source": "rule", "confidence": rule_conf, "rule_val": rule_val, "llm_val": llm_val}
    if llm_valid and (llm_conf >= thr_llm and llm_conf > rule_conf + delta):
        return {"value": llm_val, "source": "llm", "confidence": llm_conf, "rule_val": rule_val, "llm_val": llm_val}
    if rule_valid and llm_valid:
        # 当置信度相同时，优先选择LLM值，因为LLM更能理解自然语言的语义
        if rule_conf == llm_conf:
            chosen = llm_val
        else:
            chosen = rule_val if rule_conf > llm_conf else llm_val
        return {"value": chosen, "source": "merged", "confidence": max(rule_conf, llm_conf), "rule_val": rule_val, "llm_val": llm_val}
    if rule_valid:
        return {"value": rule_val, "source": "rule", "confidence": rule_conf, "rule_val": rule_val, "llm_val": llm_val}
    if llm_valid:
        return {"value": llm_val, "source": "llm", "confidence": llm_conf, "rule_val": rule_val, "llm_val": llm_val}
    return {"value": None, "source": "none", "confidence": 0.0, "rule_val": rule_val, "llm_val": llm_val}

def merge_extractions(rule_res: Dict[str, Any],
                      llm_res: Dict[str, Any],
                      validators: Dict[str, Callable[[Any], bool]] = VALIDATORS,
                      thresholds: Dict[str, float] = None) -> Dict[str, Any]:
    """
    合并 rule_res 与 llm_res，改进点：
      - 如果 rule_val 和 llm_val 都为 None（双空），不把该字段计入需要澄清，
        后续由 defaults 填充。
      - 仍会在以下情形要求澄清：
        * 至少一方提供了值但合并后 value 为 None 或 confidence 很低；
        * 提供了冲突且置信度不足以决定时。
    返回和之前相同的结构。
    """
    thresholds = thresholds or {"thr_rule": 0.9, "thr_llm": 0.7, "delta": 0.15}
    fields = set()
    
    # 添加字段映射逻辑：将中文字段映射到英文字段
    def map_field_name(field_name: str) -> str:
        """将字段名映射到标准英文名"""
        return FIELD_MAPPING.get(field_name, field_name)
    
    # 收集所有字段，包括映射后的字段
    all_fields = set()
    
    # 处理rule_res中的字段
    for field_name in rule_res.get("extracted", {}).keys():
        mapped_name = map_field_name(field_name)
        all_fields.add(mapped_name)
    
    # 处理llm_res中的字段
    for field_name in llm_res.get("extracted", {}).keys():
        mapped_name = map_field_name(field_name)
        all_fields.add(mapped_name)
    
    # 添加预期的英文字段
    expected = ["source", "destination", "source_type", "destination_type",
                "time_range", "direction", "speed_unit", "aggregation", "requirement2", "metric"]
    all_fields.update(expected)

    merged = {}
    conflicts = {}
    needs_clarify = False
    clarify_items = []

    for f in all_fields:
        # 获取原始字段值（考虑字段映射）
        rule_val = None
        rule_conf = 0.0
        llm_val = None
        llm_conf = 0.0
        
        # 查找rule_res中的值（考虑字段映射）
        for original_field, mapped_field in FIELD_MAPPING.items():
            if mapped_field == f:
                rule_val = rule_res.get("extracted", {}).get(original_field)
                rule_conf = float(rule_res.get("confidence", {}).get(original_field, 0.0) or 0.0)
                if rule_val is not None:
                    break
        
        # 如果没找到映射的字段，尝试直接获取
        if rule_val is None:
            rule_val = rule_res.get("extracted", {}).get(f)
            rule_conf = float(rule_res.get("confidence", {}).get(f, 0.0) or 0.0)
        
        # 查找llm_res中的值（考虑字段映射）
        for original_field, mapped_field in FIELD_MAPPING.items():
            if mapped_field == f:
                llm_val = llm_res.get("extracted", {}).get(original_field)
                llm_conf = float(llm_res.get("confidence", {}).get(original_field, 0.0) or 0.0)
                if llm_val is not None:
                    break
        
        # 如果没找到映射的字段，尝试直接获取
        if llm_val is None:
            llm_val = llm_res.get("extracted", {}).get(f)
            llm_conf = float(llm_res.get("confidence", {}).get(f, 0.0) or 0.0)
        
        validate_fn = validators.get(f, lambda v: bool(v))

        merged_field = merge_field(f, rule_val, rule_conf, llm_val, llm_conf, validate_fn,
                                   thresholds["thr_rule"], thresholds["thr_llm"], thresholds["delta"])
        merged[f] = merged_field

        # 新判定逻辑：如果两路都没有提供值 -> 不触发澄清，
        # 后续由 defaults 填充。
        both_empty = (rule_val is None or rule_val == "") and (llm_val is None or llm_val == "")
        if both_empty:
            # skip adding to conflicts; allow defaults to fill later
            continue

        # 其余情况：如果合并后无值或置信度低，则需要澄清
        if merged_field["value"] is None or merged_field["confidence"] < 0.5:
            needs_clarify = True
            clarify_items.append({
                "field": f,
                "rule_val": rule_val,
                "rule_conf": rule_conf,
                "llm_val": llm_val,
                "llm_conf": llm_conf
            })
            conflicts[f] = merged_field

    clarify_prompt = ""
    if needs_clarify:
        items = [ci["field"] for ci in clarify_items]
        clarify_prompt = f"请补充或确认以下项: {', '.join(items)}。示例：源端填写IP或客户ID，时间区间填写如'近1个月'。"

    return {
        "merged": merged,
        "conflicts": conflicts,
        "status": "needs_clarify" if needs_clarify else "ok",
        "clarify_prompt": clarify_prompt,
        "audit": {
            "rule_res": rule_res,
            "llm_res": llm_res
        }
    }


def build_template_fields_from_merged(merged: Dict[str, Any], secondary_scene: str, third_scene: str, keywords: List[str], defaults: Dict[str, Any]) -> Dict[str, Any]:
    m = merged.get("merged", {})
    def get_field(key: str, default_path: List[str], fallback: Any = ""):
        # 首先尝试从合并结果中获取字段值（考虑字段映射）
        v = m.get(key, {}).get("value")
        if v:
            return v
        
        # 如果没找到，尝试通过反向映射查找中文字段
        for chinese_field, english_field in FIELD_MAPPING.items():
            if english_field == key:
                v = m.get(chinese_field, {}).get("value")
                if v:
                    return v
                break
        
        # fallback to defaults (path like ["time","default"] or ["type_defaults","source_type"])
        cur = defaults
        try:
            for k in default_path:
                cur = cur[k]
            return cur
        except Exception:
            return fallback

    # 提取模板所需的核心字段，与build_filled_question保持一致
    source = get_field("source", ["source"], "")
    destination = get_field("destination", ["destination"], "")
    time_range = get_field("time_range", ["time", "default"], BUILTIN_DEFAULTS["time"]["default"])
    source_type = get_field("source_type", ["type_defaults", "source_type"], "")
    destination_type = get_field("destination_type", ["type_defaults", "destination_type"], "")
    speed_unit = get_field("speed_unit", ["speed_unit", "default"], BUILTIN_DEFAULTS["speed_unit"]["default"])
    requirement1 = get_field("requirement1", ["requirement_defaults", "aggregation"], BUILTIN_DEFAULTS["requirement_defaults"]["aggregation"])
    metric = get_field("metric", ["metric", "default"], "流量流速")
    aggregation = get_field("aggregation", ["aggregation", "default"], "按均值统计")
    exclude_conditions = get_field("exclude_conditions", ["exclude_conditions", "default"], "")
    up_down = get_field("up_down", ["up_down", "default"], "上行")

    # 获取其他辅助属性（用于requirement2构建）
    time_granularity = get_field("time_granularity", ["time_granularity", "default"], "")
    data_type = get_field("data_type", ["data_type", "default"], "")
    supplementary_info = get_field("supplementary_info", ["supplementary_info", "default"], "")

    # requirement2 (breakdown)：简化构建逻辑，与模板保持一致
    req2 = m.get("requirement2", {}).get("value")
    if not req2:
        # 基于模板的默认值构建requirement2
        req2 = defaults.get("requirement_defaults", {}).get("breakdown", BUILTIN_DEFAULTS["requirement_defaults"]["breakdown"])
    
    # 构建模板字段，只包含build_filled_question所需的字段
    template_fields = {
        "secondary_scene": secondary_scene,
        "third_scene": third_scene,
        "keywords": keywords,
        "source": source,
        "destination": destination,
        "time_range": time_range,
        "source_type": source_type,
        "destination_type": destination_type,
        "speed_unit": speed_unit,
        "requirement1": requirement1,
        "requirement2": req2,
        "metric": metric,
        "aggregation": aggregation,
        "exclude_conditions": exclude_conditions,
        "up_down": up_down,
        # 保留部分辅助属性用于调试
        "time_granularity": time_granularity,
        "data_type": data_type,
        "supplementary_info": supplementary_info
    }
    return template_fields





def build_filled_question(template_fields: Dict[str, Any]) -> str:
    # -------------------------
    # 构建模板字段与完整问题
    # -------------------------
    
    # 获取字段值，完全从template_fields中获取，不使用默认值
    time_range = template_fields.get("time_range")
    source = template_fields.get("source")
    destination = template_fields.get("destination")
    source_type = template_fields.get("source_type")
    destination_type = template_fields.get("destination_type")
    speed_unit = template_fields.get("speed_unit")
    metric = template_fields.get("metric")
    aggregation = template_fields.get("aggregation")
    requirement1 = template_fields.get("requirement1")
    requirement2 = template_fields.get("requirement2")
    exclude_conditions = template_fields.get("exclude_conditions")
    up_down = template_fields.get("up_down")
    
    # 构建问题模板，空值不拼接
    parts = []
    
    # 核心查询部分（必须存在）
    parts.append(f"查询{time_range}内，{source}到{destination}的{metric}")
    
    # 类型信息（可选）
    if source_type and destination_type:
        parts.append(f"源端类型为{source_type}，对端类型为{destination_type}")
    elif source_type:
        parts.append(f"源端类型为{source_type}")
    elif destination_type:
        parts.append(f"对端类型为{destination_type}")
    
    # 技术参数（可选）
    if speed_unit and aggregation:
        parts.append(f"流量单位为{speed_unit}，统计方式为{aggregation}")
    elif speed_unit:
        parts.append(f"流量单位为{speed_unit}")
    elif aggregation:
        parts.append(f"统计方式为{aggregation}")
    
    # 查询要求（可选）
    if requirement1 and requirement2:
        parts.append(f"要求{requirement1}并且{requirement2}")
    elif requirement1:
        parts.append(f"要求{requirement1}")
    elif requirement2:
        parts.append(f"要求{requirement2}")
    
    # 流量方向和剔除条件（可选）
    if up_down and exclude_conditions:
        parts.append(f"{up_down}流量剔除条件为{exclude_conditions}")
    elif up_down:
        parts.append(f"{up_down}流量")
    elif exclude_conditions:
        parts.append(f"剔除条件为{exclude_conditions}")
    
    template_result = "，".join(parts)
    log.info(f"构建模板结果: {template_result}")
    return template_result

# -------------------------
# 改写：调用 LLM（或本地回退）
# -------------------------
def build_rewrite_chain(api_key: str, model_name: str = "general") -> LLMChain:
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(
            "你是一个专业的网络流量数据分析问句改写助手。请根据原问题生成表达通顺、符合text2sql要求的改写句子。\n\n"
            "## 关键属性说明：\n"
            "1. **时间范围**：查询的时间段，如'过去两个月'、'近一周'等\n"
            "2. **源端和对端**：流量的起点和终点，如'外省城域网'到'浙江各地市'\n"
            "3. **源端类型和对端类型**：业务类型，如'IDC'、'城域网'等\n"
            "4. **流量单位**：数据单位，如'Gbps'\n"
            "5. **统计方式**：数据统计方法，如'月均流量'、'按均值统计'等\n"
            "6. **聚合要求**：数据聚合方式，如'按月聚合'、'按类型细分统计'等\n"
            "7. **剔除条件**：需要排除的数据项，如'天翼云'，这是独立的过滤条件\n"
            "8. **流量方向**：上行或下行流量，这是独立的流量属性\n\n"
            "## 改写要求：\n"
            "- 保持原问题的所有属性和逻辑关系\n"
            "- 确保'剔除条件'和'流量方向'是独立的属性，不要混淆\n"
            "- 使句子更自然流畅，但不要改变原意\n"
            "- 符合数据库查询语句的自然语言表达\n\n"
            "请严格输出 JSON：{{\"rewrites\": [\"..\",\"..\",\"..\"]}}，不要输出任何多余文本。"
        ),
        HumanMessagePromptTemplate.from_template("原问题: {filled_question}")
    ])
    llm = ChatTongyi(temperature=0.2, model_name=model_name, api_key=api_key)
    return LLMChain(llm=llm, prompt=prompt)

def local_rewrites(fq: str, n: int = 3) -> List[str]:
    rew = []
    rew.append(re.sub(r"^查询(.+?)，", r"\1内，请帮我查询", fq, count=1))
    rew.append(fq.replace("查询", "请查询").replace("要求", "并且要求"))
    rew.append(fq.replace("类型限制", "仅限类型为").replace("流速单位", "单位为"))
    return rew[:n]

def rewrite_filled_question(api_key: str, filled_question: str, n: int = 3, model_name: str = "general") -> List[str]:
    log.info(f"原问题: {filled_question}")
    try:
        chain = build_rewrite_chain(api_key, model_name=model_name)
        raw = chain.run(filled_question=filled_question)
        parsed = safe_json_loads(raw)
        if parsed and isinstance(parsed.get("rewrites"), list):
            ret = [str(s).strip() for s in parsed["rewrites"][:n] if s]
            if len(ret) >= 1:
                return ret[:n]
    except Exception:
        pass
    # fallback
    return local_rewrites(filled_question, n=n)

# -------------------------
# 主函数：将以上步骤串起来
# -------------------------
def fill_template_pipeline(
    api_key: str,
    secondary_scene: str,
    third_scene: str,
    keywords: List[str],
    user_input: str,
    history: List[dict],
    defaults_path: str = "defaults.toml",
    n_rewrites: int = None,
    model_name: str = "general"
) -> Dict[str, Any]:
    """
    返回：
    {
      "template_fields": {...},
      "filled_question": "...",
      "rewrites": [...],
      "merged": {...}  # 合并 audit 信息
    }
    """
    defaults = load_defaults(defaults_path)
    if n_rewrites is None:
        n_rewrites = defaults.get("rewrite", {}).get("n", BUILTIN_DEFAULTS["rewrite"]["n"])

    # 1) 规则抽取
    rule_res = rule_extract(history, user_input, keywords)

    # 2) LLM 抽取（把 rules_evidence 传入，帮助 LLM 校验）
    rules_evidence = {
        "rule_extracted": rule_res.get("extracted", {}),
        "rule_evidence": rule_res.get("evidence", {})
    }
    llm_res = llm_extract(api_key, history, user_input, keywords, rules_evidence, model_name=model_name)

    # 3) 合并
    merged = merge_extractions(rule_res, llm_res)

    # 如果需要澄清，直接返回澄清提示与中间结果（source/destination）
    if merged.get("status") != "ok":
        # 从merged中获取源端和目的端
        src = merged.get("merged", {}).get("source", {}).get("value")
        dst = merged.get("merged", {}).get("destination", {}).get("value")
        
        # 如果源端或目的端为空，使用默认值
        if not src:
            # 从用户输入和keywords中提取合理的源端，避免使用无关的IP地址
            src = ""
        if not dst:
            # 从用户输入和keywords中提取合理的目的端，避免使用无关的IP地址
            dst = ""
        
        # 过滤keywords，移除无关的IP地址
        filtered_keywords = []
        for kw in keywords:
            if kw:
                kw_str = str(kw)
                # 检查是否是IP地址，如果是则跳过
                if not ("172." in kw_str or "192." in kw_str or "10." in kw_str or "127." in kw_str):
                    filtered_keywords.append(kw_str)
        
        return {
            "status_code": 202,
            "secondary_scene": secondary_scene,
            "third_scene": third_scene,
            "intermediate_result": {"keywords": filtered_keywords, "source": src or "", "destination": dst or ""},
            "prompt": merged.get("clarify_prompt", "请补充或确认关键信息"),
            "merged": merged
        }

    # 4) 构建模板字段（使用合并结果或 defaults）
    template_fields = build_template_fields_from_merged(merged, secondary_scene, third_scene, keywords, defaults)

    # 5) 生成 filled_question
    filled_question = build_filled_question(template_fields)
    print(filled_question)
    # 6) 改写生成 N 个相似问题
    rewrites = rewrite_filled_question(api_key, filled_question, n=n_rewrites, model_name=model_name)

    # 7) 输出
    return {
        "status_code": 200,
        "secondary_scene": secondary_scene,
        "third_scene": third_scene,
        "template_fields": template_fields,
        "filled_question": filled_question,
        "rewrites": rewrites,
        "merged": merged
    }

# -------------------------
# quick demo
# -------------------------
if __name__ == "__main__":
    API_KEY = 'sk-efea8858d7a142608b82e070fe4bfc1f'
    # 示例输入（已明确二级/三级场景）
    secondary_scene = "客户流量分析"
    third_scene = "TOP账号"
    keywords = ['广东', '外省', 'TOP', '账号', '端口', '95', 'IDC', 'MAN']
    user_input = "请给出上月广东到外省方向的前十TOP账号及其端口分布和95峰值流量"
    history = [
        "用户: 我想看上月广东地市流出外省的流速",
        "助手: 你想按客户还是按IP查看？",
        "用户: 想看外省方向的TOP账号和端口占比"
    ]
    out = fill_template_pipeline(
        api_key=API_KEY,
        secondary_scene=secondary_scene,
        third_scene=third_scene,
        keywords=keywords,
        user_input=user_input,
        history=history,
        defaults_path=r"D:\pycharmspace\chatbi\defaults.toml",
        n_rewrites=3,
        model_name="qwen-max"
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
