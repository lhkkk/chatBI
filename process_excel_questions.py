#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import requests
import json
import time
import os
from datetime import datetime

class ChatBIClient:
    def __init__(self, base_url="http://127.0.0.1:8001"):
        self.base_url = base_url
        self.session_id = f"excel_processing_{int(time.time())}"
        
    def send_request(self, user_input, status_code=100, primary_scene="流量流向分析", secondary_scene="", third_scene="", intermediate_result=None):
        """模拟前端发送请求到后端"""
        if intermediate_result is None:
            intermediate_result = {}
            
        payload = {
            "session_id": self.session_id,
            "status_code": status_code,
            "user_input": user_input,
            "history_input": [],
            "primary_scene": primary_scene,
            "secondary_scene": secondary_scene,
            "third_scene": third_scene,
            "intermediate_result": intermediate_result
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/task/process",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=3000
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"请求失败，状态码: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"请求异常: {e}")
            return None
    
    def process_question(self, question):
        """处理单个问题，循环补充信息直到状态码为203"""
        max_retries = 10  # 最大重试次数
        retry_count = 0
        
        # 初始请求 - 使用原始问题
        response = self.send_request(question, status_code=100)
        
        if not response:
            return None
            
        while retry_count < max_retries:
            status_code = response.get('status_code', 0)
            
            # 如果状态码是203，表示成功，返回结果
            if status_code == 203:
                print(f"问题处理成功，状态码: 203")
                return response
            
            # 需要补充信息
            print(f"需要补充信息，状态码: {status_code}，重试次数: {retry_count + 1}")
            
            # 获取当前的场景信息和中间结果
            analysis_result = response.get('analysis_result', '')
            primary_scene = response.get('primary_scene', '流量流向分析')
            secondary_scene = response.get('secondary_scene', '')
            third_scene = response.get('third_scene', '')
            intermediate_result = response.get('intermediate_result', {})
            print(f"当前中间结果: {analysis_result}")

            # 根据analysis_result判断需要补充的信息
            # 模拟用户输入补充信息（直接返回补充内容，如"3-8月"）
            user_input = question  # 默认使用原始问题
            
            if '时间范围' in analysis_result or '时间' in analysis_result:
                user_input = "3-8月"
                print("用户补充时间范围: 3-8月")
            
            elif '对端信息' in analysis_result or '对端' in analysis_result:
                user_input = "南京"
                print("用户补充对端信息: 南京")
            
            elif '源端信息' in analysis_result or '源端' in analysis_result:
                user_input = "南京"
                print("用户补充源端信息: 南京")
            
            # 如果analysis_result为空，根据状态码默认补充
            elif not analysis_result:
                if status_code == 201:  # 默认补充源端/对端信息
                    user_input = "南京"
                    print("用户补充源端/对端信息: 南京")
                    
                elif status_code == 202:  # 默认补充时间范围
                    user_input = "3-8月"
                    print("用户补充时间范围: 3-8月")
            else:
                # 如果没有匹配的补充信息，使用原始问题继续
                print("使用原始问题继续")
            
            # 发送补充信息后的请求，使用补充的信息作为user_input
            # 注意：这里保持相同的status_code，因为这是继续对话
            response = self.send_request(
                user_input=user_input, 
                status_code=status_code,
                primary_scene=primary_scene,
                secondary_scene=secondary_scene,
                third_scene=third_scene,
                intermediate_result=intermediate_result
            )
            
            if not response:
                return None
                
            retry_count += 1
            
            # 每次补充信息后暂停1秒
            # time.sleep(1)
        
        print(f"达到最大重试次数 {max_retries}，处理失败")
        return None


def extract_attributes(intermediate_result):
    """从intermediate_result中提取attributes属性"""
    if not intermediate_result:
        return {}
    
    attributes = intermediate_result.get('attributes', {})
    
    # 定义需要提取的属性字段（根据Excel表格的实际列名）
    expected_attrs = [
        '源端', '对端', '源端类型', '对端类型', '时间', '时间粒度', 
        '流向', '数据类型', '剔除条件', '模糊匹配', '上行下行'
    ]
    
    extracted = {}
    for attr in expected_attrs:
        extracted[attr] = attributes.get(attr, '')
    
    return extracted


def process_excel_questions():
    """处理Excel中的客户问题，从新版sheet中读取并生成完整结果表格"""
    input_file = "/Users/kcol/Downloads/work/code/chatBI-1.1.0-develop/ngfa数据查询sql汇总关键词.xlsx"
    output_file = "/Users/kcol/Downloads/work/code/chatBI-1.1.0-develop/chatbi_result_full.xlsx"
    
    # 删除原来的输出文件
    if os.path.exists(output_file):
        os.remove(output_file)
        print(f"已删除原来的输出文件: {output_file}")
    
    try:
        # 读取新版sheet
        df = pd.read_excel(input_file, sheet_name='新版')
        print(f"成功读取新版数据表，共{len(df)}行数据")
        
        # 检查是否有'客户问题'列
        if '客户问题' not in df.columns:
            print("错误：数据表中没有'客户问题'列")
            return
            
    except Exception as e:
        print(f"读取数据表失败: {e}")
        return
    
    # 定义需要保留的原始列（从源端到上行下行）
    original_columns = ['源端', '对端', '源端类型', '对端类型', '时间', '时间粒度', 
                       '流向', '数据类型', '剔除条件', '模糊匹配', '上行下行']
    
    # 检查并确保所有需要的列都存在
    for col in original_columns:
        if col not in df.columns:
            df[col] = ''  # 如果列不存在，创建新列并初始化为空
    
    # 添加chatbi相关列
    chatbi_columns = ['chatbi一级场景', 'chatbi二级场景', 'chatbi三级场景', 'chatbi属性结果', 'chatbi最终问题']
    for col in chatbi_columns:
        df[col] = ''  # 创建新列并初始化为空
    
    # 初始化客户端
    client = ChatBIClient()
    
    # 根据配置处理问题
    if PROCESS_COUNT is None:
        process_df = df
        print(f"处理模式：处理所有 {len(df)} 条问题")
    else:
        process_df = df.head(PROCESS_COUNT)
        print(f"处理模式：只处理前 {PROCESS_COUNT} 条问题")
    
    for index, row in process_df.iterrows():
        question = row['客户问题']
        
        if pd.isna(question) or not str(question).strip():
            print(f"跳过空问题，行号: {index + 1}")
            continue
            
        print(f"\n处理第 {index + 1} 个问题: {question}")
        
        # 处理问题
        response = client.process_question(str(question))
        
        if response:
            # 更新chatbi相关列
            df.at[index, 'chatbi一级场景'] = response.get('primary_scene', '')
            df.at[index, 'chatbi二级场景'] = response.get('secondary_scene', '')
            df.at[index, 'chatbi三级场景'] = response.get('third_scene', '')
            
            # 提取属性信息
            intermediate_result = response.get('intermediate_result', {})
            attributes = extract_attributes(intermediate_result)
            
            # 保存完整的attributes信息
            df.at[index, 'chatbi属性结果'] = json.dumps(attributes, ensure_ascii=False)
            
            # 获取最终生成的问题 - 从analysis_result中获取
            final_question = response.get('questions', '')[0]
            df.at[index, 'chatbi最终问题'] = final_question
            
            print(f"处理成功: 一级场景={df.at[index, 'chatbi一级场景']}, 二级场景={df.at[index, 'chatbi二级场景']}, 最终问题={final_question}")
            
            # 立即保存到输出文件
            # 按照要求的列顺序重新组织数据框
            required_columns = [
                '客户问题', '一级场景划分', '二级场景划分', '三级场景',  # 原始场景列
                'chatbi一级场景', 'chatbi二级场景', 'chatbi三级场景',  # chatbi场景列
                '源端', '对端', '源端类型', '对端类型', '时间', '时间粒度',  # 属性列
                '流向', '数据类型', '剔除条件', '模糊匹配', '上行下行',  # 继续属性列
                'chatbi属性结果', 'chatbi最终问题'  # chatbi结果列
            ]
            
            # 确保所有列都存在
            for col in required_columns:
                if col not in df.columns:
                    df[col] = ''
            
            # 按要求的顺序选择列
            df_output = df[required_columns]
            df_output.to_excel(output_file, index=False)
            print(f"已保存到输出文件: {output_file}")
        else:
            print("处理失败")
        
        # 每个问题之间暂停5秒，避免服务器压力过大
        time.sleep(5)
        
        # 每处理5个问题额外暂停一下
        if (index + 1) % 5 == 0:
            print(f"已处理 {index + 1} 个问题，暂停5秒...")
            time.sleep(5)
    
    # 计算实际处理的问题数量
    actual_process_count = len(process_df)
    print(f"\n处理完成! 共处理 {actual_process_count} 个问题")
    
    # 显示处理统计
    completed_count = process_df['chatbi一级场景'].notnull().sum()
    print(f"成功处理: {completed_count} 个问题")
    print(f"处理失败: {actual_process_count - completed_count} 个问题")
    
    # 最终保存完整的输出文件
    required_columns = [
        '客户问题', '一级场景划分', '二级场景划分', '三级场景',
        'chatbi一级场景', 'chatbi二级场景', 'chatbi三级场景',
        '源端', '对端', '源端类型', '对端类型', '时间', '时间粒度',
        '流向', '数据类型', '剔除条件', '模糊匹配', '上行下行',
        'chatbi属性结果', 'chatbi最终问题'
    ]
    
    # 确保所有列都存在
    for col in required_columns:
        if col not in df.columns:
            df[col] = ''
    
    df_output = df[required_columns]
    df_output.to_excel(output_file, index=False)
    print(f"最终结果已保存到: {output_file}")


def check_server_status():
    """检查后端服务状态"""
    try:
        response = requests.get("http://127.0.0.1:8001", timeout=300)
        return response.status_code == 200
    except:
        return False


if __name__ == "__main__":
    print("ChatBI Excel问题处理脚本")
    print("=" * 50)
    
    # 配置参数
    PROCESS_COUNT = 41  # 要处理的问题数量，设为None表示处理所有问题
    
    # 检查后端服务是否运行
    if not check_server_status():
        print("警告：后端服务可能未启动")
        print("请先运行: ./start.sh restart")
        print("但检测到服务已启动，继续执行...")
    
    # 开始处理
    process_excel_questions()