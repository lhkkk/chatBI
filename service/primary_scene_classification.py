# -*- coding: utf-8 -*-

# @Project    :chatBI-develop-1.0.0
# @Version    :v1.0.0
# @File       :primary_scene_classification.py
# @Author     :
# @Describe   : 一级场景分类
import time
import random
import json

from flask import Flask,request
from config import CommonConfig
from models import openai_api
from prompts import state_prompt


log = CommonConfig.log

# 一级场景分类提示词模板
primary_scene_prompt = """
你是一个专业的流量分析场景分类助手，请严格按照以下规则对用户输入进行一级场景分类：

### 场景映射关系
{scene_mapping_json}

### 一级场景类型定义
1. **流量流向分析**：涉及流量的源端和目的端分析，关注流量从哪里来到哪里去，对应的二级场景包括：地域流量分析、客户流量分析、IP流量分析
2. **异常流量分析**：涉及流量异常检测、异常识别、异常流量特征分析，包括PCDN流量、拉流流量、异常IP流量等，对应的二级场景包括：PCDN流量分析、客户流量分析、IP流量分析
3. **流量成分分析**：涉及流量的组成、结构、占比分析，关注流量的构成情况，对应的二级场景包括：客户流量成分分析

### 关键词规则
- **流量流向分析**关键词：查询、统计、流量、流速、流入、流出、流向、IP、客户、地域、地市、省份、IDC、城域网、MAN、专线
- **异常流量分析**关键词：异常、PCDN、拉流、被拉流、TOPIP、清单、CDNType、访问域名、域名数
- **流量成分分析**关键词：占比、成分、结构、组成、详情

### 分类规则
1. 优先匹配关键词：如果输入中包含异常流量分析的关键词（如PCDN、拉流、被拉流），则分类为异常流量分析
2. 其次匹配流量成分分析关键词（如占比、成分），则分类为流量成分分析
3. 其他情况默认分类为流量流向分析
4. 严格按照上述三种场景类型进行分类，只能返回其中一种
5. 分类结果必须是三种场景类型中的一种，不要添加任何其他内容
6. 输出格式为纯文本，不包含任何标记或解释

### 输入示例
1. 输入："分析省间流量的流动情况"
   输出：流量流向分析

2. 输入："检测网络中的异常流量"
   输出：异常流量分析

3. 输入："分析流量的协议组成"
   输出：流量成分分析

4. 输入："查询23年一年杭州的家宽账号访问PCDN域名的清单"
   输出：异常流量分析

5. 输入："top20客户-终端用户流出流量占比详情"
   输出：流量成分分析

### 用户输入
历史对话：{history_chat}
当前输入：{user_input}
"""

class PrimarySceneClassification:
    def __init__(self):
        pass

    def _correct_scene(self, scene, user_input):
        """
        根据关键词规则修正一级场景分类结果
        :param scene: 原始分类结果
        :param user_input: 用户输入
        :return: 修正后的分类结果
        """
        user_input_lower = user_input.lower()
        
        # 1. 优先检查异常流量分析关键词
        anomaly_keywords = [
            "异常", "pcdn", "拉流", "被拉流", "cdn", 
            "cdntype", "访问域名", "域名数"
        ]
        
        if any(keyword in user_input_lower for keyword in anomaly_keywords):
            log.info(f"修正场景：{scene} → 异常流量分析，匹配关键词：{[k for k in anomaly_keywords if k in user_input_lower]}")
            return "异常流量分析"
        
        # 2. 检查流量成分分析关键词
        composition_keywords = ["占比", "成分", "结构", "组成", "终端用户"]
        
        # 特殊处理：结算详情数据不属于流量成分分析
        if "结算详情" in user_input_lower or "结算数据" in user_input_lower:
            pass  # 不分类为流量成分分析
        elif any(keyword in user_input_lower for keyword in composition_keywords):
            log.info(f"修正场景：{scene} → 流量成分分析，匹配关键词：{[k for k in composition_keywords if k in user_input_lower]}")
            return "流量成分分析"
        
        # 3. 流量流向分析关键词
        flow_keywords = [
            "查询", "统计", "流量", "流速", "流入", "流出", "流向", 
            "ip", "客户", "地域", "地市", "省份", "idc", "城域网", "man", "专线", 
            "top10", "top20", "top1000", "top", "排名", "清单", "详情", "topip", "结算详情", "结算数据"
        ]
        
        # 检查是否同时包含流向和排名类关键词（如"流出Top1000"），优先流量流向分析
        has_flow = any(keyword in user_input_lower for keyword in ["流入", "流出", "流向"])
        has_rank = any(keyword in user_input_lower for keyword in ["top10", "top20", "top1000", "top", "排名"])
        
        if has_flow and has_rank:
            log.info(f"修正场景：{scene} → 流量流向分析，同时包含流向和排名关键词")
            return "流量流向分析"
        elif any(keyword in user_input_lower for keyword in flow_keywords):
            return "流量流向分析"
        
        return scene
    
    def classify(self, user_input, history_chat=""):
        """
        判断当前会话的一级场景
        :param user_input: 当前用户输入
        :param history_chat: 历史对话
        :return: 一级场景分类结果
        """
        log.info(f"开始一级场景分类，用户输入：{user_input}，历史对话：{history_chat}")
        
        # 获取场景映射配置
        scene_mapping = CommonConfig.SCENE_MAPPING
        log.info(f"场景映射配置：{scene_mapping}")
        
        # 构建大模型输入
        llm_prompt = [{"role": "user", "content": primary_scene_prompt.format(
            scene_mapping_json=json.dumps(scene_mapping, ensure_ascii=False, indent=2),
            history_chat=history_chat, 
            user_input=user_input
        )}]
        
        # 调用大模型
        try:
            result = openai_api.create_openai_api_chat(llm_prompt)
            log.info(f"大模型返回结果：{result}")
            
            # 处理返回结果，去除可能的空格和换行
            primary_scene = result.strip()
            
            # 验证返回结果是否为合法的一级场景
            valid_scenes = list(scene_mapping.keys())
            # 移除闲聊场景
            if "闲聊" in valid_scenes:
                valid_scenes.remove("闲聊")
            
            if primary_scene not in valid_scenes:
                log.warning(f"大模型返回了不合法的一级场景：{primary_scene}，使用默认值")
                primary_scene = "流量流向分析"
            
            # 根据关键词规则修正分类结果
            corrected_scene = self._correct_scene(primary_scene, user_input)
            
            log.info(f"一级场景分类结果：{corrected_scene}")
            return corrected_scene
        except Exception as e:
            log.error(f"一级场景分类失败：{e}")
            # 异常情况下，直接根据关键词规则分类
            default_scene = self._correct_scene("流量流向分析", user_input)
            log.info(f"异常情况下的分类结果：{default_scene}")
            return default_scene
