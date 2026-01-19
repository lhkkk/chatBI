# -*- coding: utf-8 -*-

# @Project    :chatBI_develop_1_0_0
# @Version    :v1.0.0
# @File       :main.py.py
# @Author     :
# @Describe   :算法服务

import time
import random
import requests

from flask import Flask,request
from config import CommonConfig
from models import openai_api
from prompts import state_prompt
from service.fill_template_pipeline_service import fill_template_pipeline
from service.primary_scene_classification import PrimarySceneClassification
from service.scene_classification_service import SceneClassifier, build_scene_chain
from service.third_scene_classification_service import build_third_chain, ThirdSceneClassifier
from service.attribute_extraction_service import AttributeExtractor
from utils.ip_utils import add_ip_to_tokens

log = CommonConfig.log
app = Flask(__name__)

API_KEY = "sk-39686688fe5b4aa39446d271b248d7b9"


@app.route("/algorithm/analyze",methods=["POST"])
def analyze():
    """
    多轮对话分析接口
    请求格式：
    {
        "session_id": "string",
        "status_code": "状态码",
        "user_input": "用户输入",
        "history_input": "历史问答信息", # 过去5条
        "primary_scene": "一级场景，前端给出",
        "secondary_scene": "二级场景，可为空",
        "keywords": {
            "start_time": "2025-07-14 00:00:00",
            "end_time": "2025-07-16 00:00:00",
            "src_code": "源端地址",
            "dst_code": "目标端地址"
        },
    }
    
    状态码说明：
    100: 新会话
    101: 新任务
    200: 一级场景补全
    201: 二级场景补全
    205: 三级场景补全
    202: 任务字段补全
    203: 字段确认
    204: 用户修改
    400: 闲聊
    500: 场景不匹配
    
    处理流程：
    新会话/新任务 → 场景判断 → 一级场景补全 → 二级场景 → 三级场景 → 三级场景补全(205) → 任务字段补全 → 问题补全 → 生成问题让用户确认(204)
    """
    start_time = time.time()
    req_data = request.json
    log.info('请求体：{}'.format(req_data))
    
    # 解析请求参数
    session_id = req_data['session_id']
    status_code = req_data['status_code']
    user_input = req_data['user_input']
    history_chat = req_data['history_input']
    primary_scene = req_data['primary_scene']
    secondary_scene = req_data['secondary_scene']
    intermediate_result = req_data['intermediate_result']
    
    # 获取当前关键词和历史关键词
    current_keywords = intermediate_result.get('keywords', [])
    history_keywords = []
    
    # 从历史聊天记录中提取已有的关键词（用于累积）
    for item in history_chat:
        if isinstance(item, dict) and 'intermediate_result' in item:
            hist_ir = item['intermediate_result']
            if isinstance(hist_ir, dict) and 'keywords' in hist_ir:
                hist_keywords.extend(hist_ir['keywords'])
    
    # 关键词累积和清空逻辑
    # 新会话/新任务时清空关键词
    if status_code in [100, 101]:
        log.info('新会话/新任务，清空关键词')
        keywords = current_keywords
    else:
        # 同一会话/任务中叠加关键词，去重
        log.info(f'当前关键词：{current_keywords}，历史关键词：{history_keywords}')
        keywords = list(set(history_keywords + current_keywords))
        log.info(f'叠加后的关键词：{keywords}')
    
    questions = req_data.get('questions', [])
    
    log.info(f'当前状态码：{status_code}，用户输入：{user_input}')
    
    # 1. 闲聊判断 - 使用改进后的智能提示词
    llm_prompt = [{"role": "user", "content": state_prompt.chat_prompt.format(history_chat, user_input)}]
    result_str = openai_api.create_openai_api_chat(llm_prompt)
    try:
        result = eval(result_str)
        if result['type'] == '闲聊':
            log.info(f'闲聊检测结果：闲聊，原因：{result.get("reason", "未知")}')
            return {
                "session_id": session_id,
                "status_code": 400,
                "primary_scene": "闲聊",
                "secondary_scene": "闲聊",
                "keywords": {},
                "analysis_result": result.get('response', '这是ngfa专业流量分析场景，请勿闲聊。请提出具体的流量分析请求。'),
                "questions": [],
                "is_new_task": False
            }
    except Exception as e:
        log.error(f'闲聊判断解析结果失败：{e}，原始结果：{result_str}')
        # 解析失败时默认非闲聊，继续处理
        pass
    
    log.info('闲聊检测结果：非闲聊')
    
    # 2. 新任务判断
    task_llm_prompt = [{
        "role": "user", 
        "content": state_prompt.new_task_prompt.format(history_chat, user_input)
    }]
    task_result = openai_api.create_openai_api_chat(task_llm_prompt)
    is_new_task = task_result.strip() == '新任务'
    log.info(f'新任务判断结果：{"新任务" if is_new_task else "延续任务"}')
    
    # 3. 一级场景分类
    primary_scene_classify = PrimarySceneClassification()
    primary_result = primary_scene_classify.classify(user_input, history_chat)
    log.info(f'一级场景分类结果：{primary_result}')
    
    # 4. 场景不匹配判断
    if primary_result != primary_scene and status_code not in [100, 101]:
        log.info(f'场景不匹配，预期：{primary_scene}，实际：{primary_result}')
        return {
            "analysis_result": f"场景不匹配，预期：{primary_scene}，实际：{primary_result}",
            "session_id": session_id,
            "status_code": 200,
            "primary_scene": primary_result,
            "secondary_scene": "",
            "intermediate_result": {},
            "questions": [],
            "is_new_task": is_new_task
        }
    
    # 5. 核心处理逻辑
    try:
        # 5.1 新会话或新任务（100/101）：开始场景判断流程
        if status_code in [100, 101]:
            log.info('处理新会话/新任务，进入场景判断流程')
            
            # 调用二级场景判断
            second_chain = build_scene_chain(API_KEY)
            second_cls = SceneClassifier(second_chain)
            secondary_result = second_cls.get_secondary_scene(user_input, history_chat)
            log.info(f'二级场景判断结果：{secondary_result}')
            
            # 提前判断三级场景，确保在所有响应中都包含三级场景
            third_scene = ""
            try:
                third_chain = build_third_chain(API_KEY)
                third_cls = ThirdSceneClassifier(third_chain, threshold=0.3)
                third_result = third_cls.classify_third_scene(
                    second_scene=secondary_result["secondary_scene"],
                    user_input=user_input,
                    history=history_chat,
                    tokens=secondary_result['intermediate_result']['keywords'],
                    fields=secondary_result["intermediate_result"]
                )
                third_scene = third_result.get("chosen_third_scene", "")
                if not third_scene:
                    # 根据二级场景默认设置三级场景
                    if secondary_result["secondary_scene"] == "地域流量分析":
                        third_scene = "地市"
                    elif secondary_result["secondary_scene"] == "IP流量分析":
                        third_scene = "IP"
                    elif secondary_result["secondary_scene"] == "客户流量分析":
                        third_scene = "客户"
            except Exception as e:
                log.error(f'提前判断三级场景失败：{e}')
                # 默认三级场景
                if secondary_result["secondary_scene"] == "地域流量分析":
                    third_scene = "地市"
            
            # 无论secondary_result的status_code是什么，都使用计算出的secondary_scene
            if secondary_result['status_code'] == 201:
                # 二级场景需要补全
                log.info('二级场景需要补全信息')
                return {
                    "session_id": session_id,
                    "status_code": 201,
                    "analysis_result": secondary_result['prompt'],
                    "primary_scene": primary_result,
                    "secondary_scene": secondary_result['secondary_scene'],
                    "third_scene": third_scene,  # 确保返回三级场景
                    "intermediate_result": secondary_result['intermediate_result'],
                    "is_new_task": is_new_task,
                    "questions": []
                }
            else:
                # 二级场景已确定，进入三级场景判断
                log.info('二级场景已确定，进入三级场景判断')
                
                # 调用三级场景判断
                third_chain = build_third_chain(API_KEY)
                third_cls = ThirdSceneClassifier(third_chain, threshold=0.5)
                third_result = third_cls.classify_third_scene(
                    second_scene=secondary_result["secondary_scene"],
                    user_input=user_input,
                    history=history_chat,
                    tokens=secondary_result['intermediate_result']['keywords'],
                    fields=secondary_result["intermediate_result"]
                )
                log.info(f'三级场景判断结果：{third_result}')
                
                if third_result['status_code'] == 205:
                    # 三级场景未确定，需要补全
                    log.info('三级场景未确定，需要补全信息')
                    return {
                        "session_id": session_id,
                        "status_code": 205,  # 返回三级场景补全状态码
                        "analysis_result": third_result['prompt'],
                        "primary_scene": primary_result,
                        "secondary_scene": third_result["second_scene"],
                        "third_scene": third_result.get("chosen_third_scene", third_scene),
                        "intermediate_result": third_result['intermediate_result'],
                        "is_new_task": is_new_task,
                        "questions": []
                    }
                else:
                    # 三级场景已确定，提取属性并检查缺失属性
                    log.info('三级场景已确定，提取属性并检查缺失属性')
                    
                    # 创建属性提取器实例
                    extractor = AttributeExtractor()
                    attributes = extractor.extract_attributes(user_input, history_chat)
                    log.info(f'属性提取结果：{attributes}')
                    
                    # 检查必要属性是否完整
                    missing_check = extractor.check_necessary_attributes(attributes)
                    log.info(f'属性检查结果：{missing_check}')
                    
                    if missing_check['has_missing']:
                        # 有缺失属性，生成引导问题，返回状态码202
                        log.info('有缺失属性，生成引导问题')
                        return {
                            "session_id": session_id,
                            "status_code": 202,
                            "analysis_result": missing_check['prompt'],
                            "primary_scene": primary_result,
                            "secondary_scene": secondary_result["secondary_scene"],
                            "third_scene": third_result["chosen_third_scene"],
                            "third_scene_confidence": third_result["confidence"],
                            "intermediate_result": {
                                **third_result['intermediate_result'],
                                "attributes": attributes,  # 保存已提取的属性
                                "missing_attributes": missing_check['missing'],  # 保存缺失的属性
                                "keywords": keywords  # 确保包含累积后的关键词
                            },
                            "is_new_task": is_new_task,
                            "questions": []
                        }
                    else:
                        # 所有必要属性都已完整，进入问题生成
                        log.info('所有必要属性都已完整，进入问题生成')
                        
                        # 调用问题生成
                        out = fill_template_pipeline(
                            api_key=API_KEY,
                            secondary_scene=secondary_result["secondary_scene"],
                            third_scene=third_result["chosen_third_scene"],
                            keywords=keywords,
                            user_input=user_input,
                            history=history_chat,
                            defaults_path=r"D:\pycharmspace\chatbi\defaults.toml",
                            n_rewrites=1,
                            model_name="qwen-max"
                        )
                        log.info(f'问题生成结果：{out}')
                        
                        if out['status_code'] == 200:
                            # 问题生成成功，返回给用户确认
                            log.info('问题生成成功，返回给用户确认')
                            # 获取生成问题的模板字段
                            template_fields = out.get('template_fields', {})
                            
                            # 不再需要构建keywords_info，直接使用intermediate_result.attributes
                            # 返回203状态码时，确保关键词被正确包含在响应中
                            # 203是一个完整的会话流程，后续请求会重新开始
                            return {
                                "session_id": session_id,
                                "status_code": 203,
                                "analysis_result": '问题生成，请用户确认',
                                "primary_scene": primary_result,
                                "secondary_scene": secondary_result["secondary_scene"],
                                "third_scene": third_result["chosen_third_scene"],
                                "third_scene_confidence": third_result["confidence"],
                                "intermediate_result": {
                                    **third_result['intermediate_result'],
                                    "attributes": attributes,  # 添加属性提取服务提取的完整属性
                                    "keywords": keywords  # 确保包含累积后的关键词
                                },
                                "is_new_task": is_new_task,
                                "questions": out['rewrites']
                            }
                        else:
                            # 需要补充问题信息
                            log.info('需要补充问题信息')
                            return {
                                "session_id": session_id,
                                "status_code": 202,
                                "analysis_result": out.get('prompt', '请补充或确认关键信息'),
                                "primary_scene": primary_result,
                                "secondary_scene": secondary_result["secondary_scene"],
                                "third_scene": third_result["chosen_third_scene"],  # 确保返回三级场景
                                "third_scene_confidence": third_result["confidence"],  # 确保返回三级场景置信度
                                "intermediate_result": {
                                    **out.get('intermediate_result', third_result['intermediate_result']),
                                    "attributes": attributes,  # 保存已提取的属性
                                    "missing_attributes": [],  # 重置缺失属性
                                    "keywords": keywords  # 确保包含累积后的关键词
                                },
                                "is_new_task": is_new_task,
                                "questions": []
                            }
        
        # 5.2 一级场景补全（200）
        elif status_code == 200:
            log.info('处理一级场景补全')
            # 一级场景已通过primary_result获取，直接进入二级场景判断
            second_chain = build_scene_chain(API_KEY)
            second_cls = SceneClassifier(second_chain)
            secondary_result = second_cls.get_secondary_scene(user_input, history_chat)
            log.info(f'二级场景判断结果：{secondary_result}')
            
            # 提前判断三级场景
            third_scene = ""
            try:
                third_chain = build_third_chain(API_KEY)
                third_cls = ThirdSceneClassifier(third_chain, threshold=0.3)
                third_result = third_cls.classify_third_scene(
                    second_scene=secondary_result["secondary_scene"],
                    user_input=user_input,
                    history=history_chat,
                    tokens=secondary_result['intermediate_result']['keywords'],
                    fields=secondary_result["intermediate_result"]
                )
                third_scene = third_result.get("chosen_third_scene", "")
                if not third_scene:
                    # 根据二级场景默认设置三级场景
                    if secondary_result["secondary_scene"] == "地域流量分析":
                        third_scene = "地市"
                    elif secondary_result["secondary_scene"] == "IP流量分析":
                        third_scene = "IP"
                    elif secondary_result["secondary_scene"] == "客户流量分析":
                        third_scene = "客户"
            except Exception as e:
                log.error(f'提前判断三级场景失败：{e}')
                # 默认三级场景
                if secondary_result["secondary_scene"] == "地域流量分析":
                    third_scene = "地市"
            
            if secondary_result['status_code'] == 201:
                # 二级场景需要补全
                return {
                    "session_id": session_id,
                    "status_code": 201,
                    "analysis_result": secondary_result['prompt'],
                    "primary_scene": primary_result,
                    "secondary_scene": secondary_result['secondary_scene'],
                    "third_scene": third_scene,  # 确保返回三级场景
                    "intermediate_result": secondary_result['intermediate_result'],
                    "is_new_task": is_new_task,
                    "questions": []
                }
            else:
                # 二级场景已确定，进入三级场景判断
                third_chain = build_third_chain(API_KEY)
                third_cls = ThirdSceneClassifier(third_chain, threshold=0.5)
                third_result = third_cls.classify_third_scene(
                    second_scene=secondary_result["secondary_scene"],
                    user_input=user_input,
                    history=history_chat,
                    tokens=secondary_result['intermediate_result']['keywords'],
                    fields=secondary_result["intermediate_result"]
                )
                log.info(f'三级场景判断结果：{third_result}')
                
                if third_result['status_code'] == 205:
                    # 三级场景未确定，需要补全
                    return {
                        "session_id": session_id,
                        "status_code": 205,  # 返回三级场景补全状态码
                        "analysis_result": third_result['prompt'],
                        "primary_scene": primary_result,
                        "secondary_scene": third_result["second_scene"],
                        "intermediate_result": third_result['intermediate_result'],
                        "is_new_task": is_new_task,
                        "questions": []
                    }
                else:
                    # 三级场景已确定，进入问题生成
                    out = fill_template_pipeline(
                        api_key=API_KEY,
                        secondary_scene=secondary_result["secondary_scene"],
                        third_scene=third_result["chosen_third_scene"],
                        keywords=keywords,
                        user_input=user_input,
                        history=history_chat,
                            defaults_path=r"D:\pycharmspace\chatbi\defaults.toml",
                            n_rewrites=1,
                            model_name="qwen-max"
                        )
                    log.info(f'问题生成结果：{out}')
                    
                    if out['status_code'] == 200:
                        # 问题生成成功，返回给用户确认
                        # 获取生成问题的模板字段
                        template_fields = out.get('template_fields', {})
                        
                        # 创建属性提取器实例，在三级场景确定后，问题补全时提取属性
                        extractor = AttributeExtractor()
                        attributes = extractor.extract_attributes(user_input, history_chat)
                        log.info(f'属性提取结果：{attributes}')
                        
                        # 不再需要构建keywords_info，直接使用intermediate_result.attributes
                        # 返回203状态码时，确保关键词被正确包含在响应中
                        # 203是一个完整的会话流程，后续请求会重新开始
                        return {
                            "session_id": session_id,
                            "status_code": 203,
                            "analysis_result": '问题生成，请用户确认',
                            "primary_scene": primary_result,
                            "secondary_scene": secondary_result["secondary_scene"],
                            "third_scene": third_result["chosen_third_scene"],
                            "third_scene_confidence": third_result["confidence"],
                            "intermediate_result": {
                                **third_result['intermediate_result'],
                                "keywords": keywords,  # 确保包含累积后的关键词
                                "attributes": attributes  # 添加提取的属性
                            },
                            "is_new_task": is_new_task,
                            "questions": out['rewrites']
                        }
                    else:
                        # 需要补充问题信息
                        return {
                            "session_id": session_id,
                            "status_code": 202,
                            "analysis_result": out.get('prompt', '请补充或确认关键信息'),
                            "primary_scene": primary_result,
                            "secondary_scene": secondary_result["secondary_scene"],
                            "third_scene": third_result["chosen_third_scene"],
                            "third_scene_confidence": third_result["confidence"],
                            "intermediate_result": out.get('intermediate_result', third_result['intermediate_result']),
                            "is_new_task": is_new_task,
                            "questions": []
                        }
        
        # 5.3 二级场景补全（201）
        elif status_code == 201:
            log.info('处理二级场景补全')
            second_chain = build_scene_chain(API_KEY)
            second_cls = SceneClassifier(second_chain)
            secondary_result = second_cls.get_secondary_scene(user_input, history_chat)
            log.info(f'二级场景判断结果：{secondary_result}')
            
            if secondary_result['status_code'] == 201:
                # 二级场景仍需要补全
                    return {
                        "session_id": session_id,
                        "status_code": 201,
                        "analysis_result": secondary_result['prompt'],
                        "primary_scene": primary_result,
                        "secondary_scene": secondary_result['secondary_scene'],
                        "intermediate_result": secondary_result['intermediate_result'],
                        "is_new_task": is_new_task,
                        "questions": []
                    }
            else:
                # 二级场景已确定，进入三级场景判断
                third_chain = build_third_chain(API_KEY)
                third_cls = ThirdSceneClassifier(third_chain, threshold=0.5)
                third_result = third_cls.classify_third_scene(
                    second_scene=secondary_result["secondary_scene"],
                    user_input=user_input,
                    history=history_chat,
                    tokens=secondary_result['intermediate_result']['keywords'],
                    fields=secondary_result["intermediate_result"]
                )
                log.info(f'三级场景判断结果：{third_result}')
                
                if third_result['status_code'] == 205:
                        # 三级场景未确定，需要补全
                        return {
                            "session_id": session_id,
                            "status_code": 205,  # 返回三级场景补全状态码
                            "analysis_result": third_result['prompt'],
                            "primary_scene": primary_result,
                            "secondary_scene": secondary_result["secondary_scene"],
                            "intermediate_result": third_result['intermediate_result'],
                            "is_new_task": is_new_task,
                            "questions": []
                        }
                else:
                    # 三级场景已确定，进入问题生成
                    out = fill_template_pipeline(
                        api_key=API_KEY,
                        secondary_scene=secondary_result["secondary_scene"],
                        third_scene=third_result["chosen_third_scene"],
                        keywords=keywords,
                        user_input=user_input,
                        history=history_chat,
                        defaults_path=r"D:\pycharmspace\chatbi\defaults.toml",
                        n_rewrites=1,
                        model_name="qwen-max"
                    )
                    log.info(f'问题生成结果：{out}')
                    
                    if out['status_code'] == 200:
                            # 问题生成成功，返回给用户确认
                            # 获取生成问题的模板字段
                            template_fields = out.get('template_fields', {})
                            
                            # 创建属性提取器实例，在三级场景确定后，问题补全时提取属性
                            extractor = AttributeExtractor()
                            attributes = extractor.extract_attributes(user_input, history_chat)
                            log.info(f'属性提取结果：{attributes}')
                            
                            # 不再需要构建keywords_info，直接使用intermediate_result.attributes
                            # 返回203状态码时，确保关键词被正确包含在响应中
                            # 203是一个完整的会话流程，后续请求会重新开始
                            return {
                                "session_id": session_id,
                                "status_code": 203,
                                "analysis_result": '问题生成，请用户确认',
                                "primary_scene": primary_result,
                                "secondary_scene": secondary_result["secondary_scene"],
                                "third_scene": third_result["chosen_third_scene"],
                                "third_scene_confidence": third_result["confidence"],
                                "intermediate_result": {
                                    **third_result['intermediate_result'],
                                    "keywords": keywords,  # 确保包含累积后的关键词
                                    "attributes": attributes  # 添加提取的属性
                                },
                                "is_new_task": is_new_task,
                                "questions": out['rewrites']
                            }
                    elif out.get('status_code') == 201 or out.get('status_code') == 202:
                        # 需要补充信息
                        return {
                            "session_id": session_id,
                            "status_code": 202,
                            "analysis_result": out.get('prompt', '需要补充信息才能生成完整问题'),
                            "primary_scene": primary_result,
                            "secondary_scene": secondary_result["secondary_scene"],
                            "third_scene": third_result["chosen_third_scene"],
                            "third_scene_confidence": third_result["confidence"],
                            "intermediate_result": out.get('intermediate_result', third_result['intermediate_result']),
                            "is_new_task": is_new_task,
                            "questions": []
                        }
                    else:
                        # 其他错误
                        return {
                            "session_id": session_id,
                            "status_code": 500,
                            "analysis_result": out.get('prompt', '需要补充信息才能生成完整问题'),
                            "primary_scene": primary_result,
                            "secondary_scene": secondary_result["secondary_scene"],
                            "third_scene": third_result["chosen_third_scene"],
                            "third_scene_confidence": third_result["confidence"],
                            "intermediate_result": third_result['intermediate_result'],
                            "is_new_task": is_new_task,
                            "questions": []
                        }
        
        # 5.4 任务字段补全（202）
        elif status_code == 202:
            log.info('处理任务字段补全')
            
            # 确保三级场景已经被正确判断
            third_scene = req_data.get('third_scene', '')
            if not third_scene:
                # 如果三级场景为空，重新调用三级场景判断
                log.info('三级场景为空，重新执行三级场景判断')
                third_chain = build_third_chain(API_KEY)
                third_cls = ThirdSceneClassifier(third_chain, threshold=0.3)  # 降低阈值，提高识别率
                third_result = third_cls.classify_third_scene(
                    second_scene=secondary_scene,
                    user_input=user_input,
                    history=history_chat,
                    tokens=intermediate_result.get('keywords', {}),
                    fields=intermediate_result
                )
                log.info(f'重新获取的三级场景结果：{third_result}')
                third_scene = third_result.get('chosen_third_scene', '')
            
            # 创建属性提取器实例
            extractor = AttributeExtractor()
            
            # 获取已有的属性和缺失属性
            existing_attributes = intermediate_result.get('attributes', {})
            log.info(f'已有的属性：{existing_attributes}')
            
            # 使用智能合并：只更新用户补充的属性，保留已有属性
            merged_attributes = extractor.smart_merge_attributes(existing_attributes, user_input, history_chat)
            log.info(f'智能合并后的属性：{merged_attributes}')
            
            # 检查合并后的属性是否还有缺失
            missing_check = extractor.check_necessary_attributes(merged_attributes)
            log.info(f'属性检查结果：{missing_check}')
            
            if missing_check['has_missing']:
                # 还有缺失属性，生成智能引导问题
                log.info('还有缺失属性，生成智能引导问题')
                return {
                    "session_id": session_id,
                    "status_code": 202,
                    "analysis_result": missing_check['prompt'],
                    "primary_scene": primary_result,
                    "secondary_scene": secondary_scene,
                    "third_scene": third_scene if third_scene else "地市",  # 确保返回三级场景，默认地市
                    "intermediate_result": {
                        **intermediate_result,
                        "attributes": merged_attributes,  # 更新合并后的属性
                        "missing_attributes": missing_check['missing']  # 更新缺失属性
                    },
                    "is_new_task": is_new_task,
                    "questions": []
                }
            else:
                # 所有必要属性都已完整，进入问题生成
                log.info('所有必要属性都已完整，进入问题生成')
                
                # 调用问题生成
                out = fill_template_pipeline(
                    api_key=API_KEY,
                    secondary_scene=secondary_scene,
                    third_scene=third_scene if third_scene else "地市",
                    keywords=keywords,
                    user_input=user_input,
                    history=history_chat,
                    defaults_path=r"D:\pycharmspace\chatbi\defaults.toml",
                    n_rewrites=1,
                    model_name="qwen-max"
                )
                log.info(f'问题生成结果：{out}')
                
                if out['status_code'] == 200:
                    # 问题生成成功，返回给用户确认
                    # 获取生成问题的模板字段
                    template_fields = out.get('template_fields', {})
                    
                    # 不再需要构建keywords_info，直接使用intermediate_result.attributes
                    # 返回203状态码时，确保关键词被正确包含在响应中
                    # 203是一个完整的会话流程，后续请求会重新开始
                    return {
                        "session_id": session_id,
                        "status_code": 203,
                        "analysis_result": '问题生成，请用户确认',
                        "primary_scene": primary_result,
                        "secondary_scene": secondary_scene,
                        "third_scene": third_scene if third_scene else "地市",
                        "intermediate_result": {
                            **intermediate_result,
                            "attributes": merged_attributes,  # 保存合并后的属性
                            "keywords": keywords  # 确保包含累积后的关键词
                        },
                        "is_new_task": is_new_task,
                        "questions": out['rewrites']
                    }
                else:
                    # 需要补充问题信息
                    return {
                        "session_id": session_id,
                        "status_code": 202,
                        "analysis_result": out.get('prompt', '请补充或确认关键信息'),
                        "primary_scene": primary_result,
                        "secondary_scene": secondary_scene,
                        "third_scene": third_scene if third_scene else "地市",
                        "intermediate_result": {
                            **intermediate_result,
                            "attributes": merged_attributes  # 保存合并后的属性
                        },
                        "is_new_task": is_new_task,
                        "questions": []
                    }
        
        # 5.5 字段确认（203）
        elif status_code == 203:
            log.info('处理字段确认')
            # 这里可以根据实际情况处理用户的确认操作
            # 暂时直接返回203，让用户确认
            return {
                "session_id": session_id,
                "status_code": 203,
                "analysis_result": '问题生成，请用户确认',
                "primary_scene": primary_result,
                "secondary_scene": secondary_scene,
                "third_scene": req_data.get('third_scene', ''),  # 确保返回三级场景
                "intermediate_result": intermediate_result,
                "is_new_task": is_new_task,
                "questions": questions
            }
        
        # 5.6 三级场景补全（205）
        elif status_code == 205:
            log.info('处理三级场景补全')
            # 三级场景已补全，直接进入问题生成
            out = fill_template_pipeline(
                api_key=API_KEY,
                secondary_scene=secondary_scene,
                third_scene=req_data.get('third_scene', ''),
                keywords=keywords,
                user_input=user_input,
                history=history_chat,
                defaults_path=r"D:\pycharmspace\chatbi\defaults.toml",
                n_rewrites=1,
                model_name="qwen-max"
            )
            log.info(f'问题生成结果：{out}')
            
            if out['status_code'] == 200:
                # 问题生成成功，返回给用户确认
                # 获取生成问题的模板字段
                template_fields = out.get('template_fields', {})
                
                # 创建属性提取器实例，在三级场景确定后，问题补全时提取属性
                extractor = AttributeExtractor()
                attributes = extractor.extract_attributes(user_input, history_chat)
                log.info(f'属性提取结果：{attributes}')
                
                # 不再需要构建keywords_info，直接使用intermediate_result.attributes
                return {
                    "session_id": session_id,
                    "status_code": 203,
                    "analysis_result": '问题生成，请用户确认',
                    "primary_scene": primary_result,
                    "secondary_scene": secondary_scene,
                    "third_scene": req_data.get('third_scene', ''),
                    "intermediate_result": {
                        **intermediate_result,
                        "attributes": attributes  # 添加提取的属性
                    },
                    "is_new_task": is_new_task,
                    "questions": out['rewrites']
                }
            else:
                # 需要补充信息
                return {
                    "session_id": session_id,
                    "status_code": 202,
                    "analysis_result": out['prompt'],
                    "primary_scene": primary_result,
                    "secondary_scene": secondary_scene,
                    "third_scene": req_data.get('third_scene', ''),  # 确保返回三级场景
                    "intermediate_result": intermediate_result,
                    "is_new_task": is_new_task,
                    "questions": []
                }
        
        # 5.7 用户修改（204）
        elif status_code == 204:
            log.info('处理用户修改')
            # 用户确认不通过，根据用户输入修改问题，重新生成问题
            # 直接进入问题生成流程
            out = fill_template_pipeline(
                api_key=API_KEY,
                secondary_scene=secondary_scene,
                third_scene=req_data.get('third_scene', ''),
                keywords=keywords,
                user_input=user_input,
                history=history_chat,
                defaults_path=r"D:\pycharmspace\chatbi\defaults.toml",
                n_rewrites=1,
                model_name="qwen-max"
            )
            log.info(f'问题生成结果：{out}')
            
            if out['status_code'] == 200:
                # 重新生成问题，返回给用户确认
                # 获取生成问题的模板字段
                template_fields = out.get('template_fields', {})
                
                # 创建属性提取器实例，在三级场景确定后，问题补全时提取属性
                extractor = AttributeExtractor()
                attributes = extractor.extract_attributes(user_input, history_chat)
                log.info(f'属性提取结果：{attributes}')
                
                # 不再需要构建keywords_info，直接使用intermediate_result.attributes
                return {
                    "session_id": session_id,
                    "status_code": 203,
                    "analysis_result": '问题已修改，请用户确认',
                    "primary_scene": primary_result,
                    "secondary_scene": secondary_scene,
                    "third_scene": req_data.get('third_scene', ''),
                    "intermediate_result": {
                        **intermediate_result,
                        "attributes": attributes  # 添加提取的属性
                    },
                    "is_new_task": is_new_task,
                    "questions": out['rewrites']
                }
            else:
                # 需要补充信息
                return {
                    "session_id": session_id,
                    "status_code": 202,
                    "analysis_result": out['prompt'],
                    "primary_scene": primary_result,
                    "secondary_scene": secondary_scene,
                    "third_scene": req_data.get('third_scene', ''),  # 确保返回三级场景
                    "intermediate_result": intermediate_result,
                    "is_new_task": is_new_task,
                    "questions": []
                }
        
        # 5.8 其他状态码
        else:
            log.warning(f'收到未处理的状态码：{status_code}')
            return {
                "session_id": session_id,
                "status_code": 500,
                "analysis_result": f'未知状态码：{status_code}',
                "primary_scene": primary_result,
                "secondary_scene": secondary_scene,
                "intermediate_result": intermediate_result,
                "is_new_task": is_new_task,
                "questions": []
            }
        
    except Exception as e:
        log.error(f'处理过程中发生错误：{e}', exc_info=True)
        return {
            "session_id": session_id,
            "status_code": 500,
            "analysis_result": f'处理失败：{str(e)}',
            "primary_scene": primary_result,
            "secondary_scene": secondary_scene,
            "intermediate_result": intermediate_result,
            "is_new_task": is_new_task,
            "questions": []
        }
    
    finally:
        end_time = time.time()
        log.info(f'算法处理分析用户问题耗时:{end_time-start_time:.2f}s')


if __name__ == '__main__':
    app.run(debug=False, host=CommonConfig.ALGO_HOST, port=CommonConfig.ALGO_PORT)

