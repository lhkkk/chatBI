# -*- coding: utf-8 -*-

# @Project    :chatBI_develop_1_0_0
# @Version    :v1.0.0
# @File       :data_source.py
# @Author     :
# @Describe   :
import sys
import time

from config import CommonConfig
# from send_request import SendRequest
from data_source.send_request import SendRequest

sys.path.append('..')


log = CommonConfig.log
# 放到配置文件里面
API_URL = CommonConfig.BACKEND_URL


class DataSource(object):
    def __init__(self):
        self.url = API_URL
        self.send_request = SendRequest()

    # 批量获取历史数据
    def get_data_analyze(self, data_body, method="post", api_name="/algorithm/analyze"):
        """
        算法和后端交互
        {
        "session_id": "string",
        "tasks": [
            {
                "task_id": "string",
                "status_code": 0,
                "latest_input": "string",
                "history_input": ["string", "..."],
                "intermediate_result": {
                    "primary_scene": "string",
                    "secondary_scene": "string",
                    "keywords": ["string", "..."],
                    "similar_questions": ["string", "..."],
                    "selected_similar_question": "string",
                    "supplementary_info": "string"
                }
                },
                {}
        ]
        }
        """
        start = time.time()
        api_url = 'http://' + CommonConfig.ALGO_HOST + ':' + str(CommonConfig.ALGO_PORT) + api_name
        result = self.send_request.send_request(api_url, data_body, method=method)
        end = time.time()
        log.info(f'算法与后端交互接口耗时:{end - start}')
        # if result is None:
        #     self.algorithm_alarm("0", "100001", "100015", "1", 'signalHistoryBatch接口超时', '1', CommonConfig.NOID)
        return result

    def get_web_data(self, data_body, method="post", api_name="/task/process"):
        """
        前后端交互的接口
        :param data_body:
        :param method:
        :param api_name:
        :return:
        {
          "session_id": "string",      // 会话唯一标识
          "status_code": "integer",    // 前端传递的状态码（100/101/305/400）
          "user_input": "string",      // 用户原始输入
          "confirmed_data": {          // 用户确认的补充数据（仅status=305/400时存在）
            "type": "enum(primary_scene|secondary_scene|field|conflict|default)",
            "value": "object"          // 补充的具体值
          },
          "current_context": {         // 当前任务上下文（非新任务时必填）
            "primary_scene": "string",
            "secondary_scene": "string",
            "params": {                // 已收集的参数
              "time_range": "最近1小时",
              "ip": "192.168.1.1",
              ...
            }
          }
        }
        """
        start = time.time()
        api_url = 'http://' + CommonConfig.BACKEND_HOST + ':' + str(CommonConfig.BACKEND_PORT) + api_name
        result = self.send_request.send_request(api_url, data_body, method=method)
        end = time.time()
        log.info(f'前后端交互接口耗时:{end - start}')
        # if result is None:
        #     self.algorithm_alarm("0", "100001", "100015", "1", 'signalHistoryBatch接口超时', '1', CommonConfig.NOID)
        return result












