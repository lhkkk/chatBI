# -*- coding: utf-8 -*-

# @Project    :chatBI_develop_1_0_0
# @Version    :v1.0.0
# @File       :backend_server.py
# @Author     :
# @Describe   :后端服务，和前端交互
import time
import asyncio

from flask import Flask,request
from config import CommonConfig
from data_source.data_source import DataSource
from core.session_manager.context_builder import ContextBuilder
from service.mcp_client import get_mcp_result


log = CommonConfig.log
app = Flask(__name__)

last_analysis_dict = {'secondary_scene': '', 'intermediate_result': {}, 'questions': [], 'status_code': 0, 'is_new_task': False}


@app.route("/task/process",methods=["POST"])
def analyze():
    start_time = time.time()
    req_data = request.json
    log.info('请求体：{}'.format(req_data))
    session_id = req_data['session_id']
    user_input = req_data['user_input']
    history_chat = req_data.get('history_input', req_data.get('history_chat', []))
    primary_scene = req_data['primary_scene']
    # 调用算法接口
    ds = DataSource()
    """
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
    """
    global last_analysis_dict
    # 优先使用前端传递的status_code，如果没有则根据历史判断
    status_code = req_data.get('status_code')
    if status_code is None:
        if len(history_chat) == 0 or (len(history_chat) == 1 and history_chat[0]['role'] == 'assistant') or last_analysis_dict.get('status_code', 0) == 0:
            log.info('新会话')
            status_code = 100
        else:
            print(history_chat)
            status_code = last_analysis_dict.get('status_code', 100)
    context_builder = ContextBuilder()
    history = context_builder.build_context(user_input, history_chat)

    # 获取前端传递的场景信息，如果没有则使用上次分析的结果
    secondary_scene = req_data.get('secondary_scene', last_analysis_dict.get('secondary_scene', ''))
    third_scene = req_data.get('third_scene', last_analysis_dict.get('third_scene', ''))
    intermediate_result = req_data.get('intermediate_result', last_analysis_dict.get('intermediate_result', {}))
    
    request_data = {
        "session_id": session_id,
        "status_code": status_code,
        "user_input": user_input,
        "history_input": history,
        "primary_scene": primary_scene,
        "secondary_scene": secondary_scene,
        "third_scene": third_scene,
        "intermediate_result": intermediate_result,
        "questions": [],
        "time": ""
    }
    result = ds.get_data_analyze(request_data)
    log.info('算法返回值：{}'.format(result))
    """
        {
        "session_id": "会话id",
        "status_code": "状态码",
        "primary_scene": "一级场景，算法验证",
        "secondary_scene": "二级场景，可以为空",
        "analysis_result": "", # 算法分析结果
        "keywords": {
            "start_time": "2025-07-14 00:00:00",
            "end_time": "2025-07-16 00:00:00",
            "src_code": "源端地址",
            "dst_code": "目标端地址"
        },
        "questions": ["问题1", "问题2"],  # 改写后的问题组
        "is_new_task": True,  # 是否是新任务
        }
    """
    end_time = time.time()
    log.info('后端处理用户问题耗时:{:.2f}s'.format(end_time-start_time))
    # 处理算法的返回
    if result['status_code'] not in [400, 500]:
        last_analysis_dict = result
        # if result['status_code'] == 203:
        #     log.info('调用mcp')
        #     mcp_result = asyncio.run(get_mcp_result(result["questions"][0]))
        #     log.info('mcp返回值：{}'.format(mcp_result))
    
    return result


if __name__ == '__main__':
    app.run(debug=False, host=CommonConfig.BACKEND_HOST, port=CommonConfig.BACKEND_PORT)