# -*- coding: utf-8 -*-
import json
# @Project    :chatBI_develop_1_0_0
# @Version    :v1.0.0
# @File       :config.py
# @Author     :
# @Describe   :

import os

from configparser import RawConfigParser
from utils.logger import MYLOG


# 通用配置类
class CommonConfig(object):
    log = MYLOG("ecs", "access").getLogger()
    # 配置地址
    CONFIG_NAME = "common_config.ini"
    config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), CONFIG_NAME)
    cfg = RawConfigParser()
    cfg.read(config_path, encoding="utf-8")
    # 后端接口地址
    BACKEND_URL = cfg.get('BACKEND_API', 'backend_url')
    FULL_LOG_FLAG = cfg.getboolean('BACKEND_API', 'full_log_flag')

    # 大模型地址
    DP_API_KEY = cfg.get('LLM', 'dp_api_key')
    DP_URL = cfg.get('LLM', 'dp_url')
    QWEN_URL = cfg.get('LLM', 'qwen_url')

    # 后端服务地址
    BACKEND_HOST = cfg.get('BACKEND_SERVER', 'backend_host')
    BACKEND_PORT = cfg.getint('BACKEND_SERVER', 'backend_port')

    # 算法服务地址
    ALGO_HOST = cfg.get('ALGO_SERVER', 'algo_host')
    ALGO_PORT = cfg.getint('ALGO_SERVER', 'algo_port')

    # 通用配置
    STATUS_CODE = eval(cfg.get('COMMON', 'status_code'))
    SCENE_MAPPING = eval(cfg.get('COMMON', 'scene_mapping'))
    CUSTOMER_MAPPING = json.loads(cfg.get('COMMON', 'customer_mapping'))
