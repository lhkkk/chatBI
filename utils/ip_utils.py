#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IP地址处理工具
"""

import re
import logging

log = logging.getLogger(__name__)


def extract_ip_addresses(user_input: str) -> list:
    """
    从用户输入中提取IP地址
    
    :param user_input: 用户输入文本
    :return: 提取到的IP地址列表
    """
    if not user_input:
        return []
    
    # 使用正则表达式匹配IP地址
    ip_pattern = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    ip_matches = re.findall(ip_pattern, user_input)
    log.info(f"使用正则表达式提取到的IP地址: {ip_matches}")
    
    # 如果正则表达式没有提取到IP地址，尝试手动提取
    if not ip_matches:
        # 检查用户输入是否包含"是"和IP地址格式的内容
        if "是" in user_input:
            parts = user_input.split("是")
            if len(parts) > 1:
                # 检查第二部分是否包含IP地址
                ip_candidate = parts[1].strip()
                # 简单检查是否符合IP地址格式（包含三个点）
                if ip_candidate.count(".") == 3:
                    ip_matches = [ip_candidate]
                    log.info(f"手动提取到的IP地址: {ip_matches}")
    
    return ip_matches


def add_ip_to_tokens(user_input: str, tokens: list) -> list:
    """
    将提取到的IP地址添加到tokens列表中
    
    :param user_input: 用户输入文本
    :param tokens: 原始tokens列表
    :return: 添加IP地址后的tokens列表
    """
    ip_addresses = extract_ip_addresses(user_input)
    
    # 将提取到的IP地址添加到tokens中
    for ip in ip_addresses:
        if ip not in tokens:
            tokens.append(ip)
            log.info(f"将IP地址 {ip} 添加到tokens中")
    
    return tokens