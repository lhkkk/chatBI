# -*- coding: utf-8 -*-

# @Project    :chatBI_develop_1_0_0
# @Version    :v1.0.0
# @File       :send_request.py
# @Author     :
# @Describe   :
import sys
import time
import requests
import json
import traceback

from config import CommonConfig

sys.path.append("..")


log = CommonConfig.log


class SendRequest():
    def __init__(self):
        pass

    def get_token(self):
        pass

    def send_request(self, url, data_body, method='get', cnt=1, timeout=1200):
        '''
        :param url: 请求的地址
        :param method: 请求的方式
        :param data_body: 发送的数据
        :return:
        '''

        headers = {
            'Accept': "application/json",
            'Content-Type': 'application/json'
        }
        if cnt < 3:
            try:
                request_method = getattr(requests, method)
                if data_body is None:
                    response = request_method(url, headers=headers, timeout=timeout)
                else:
                    response = request_method(url, data=json.dumps(data_body), headers=headers, timeout=timeout)
                if response.status_code != 200:
                    log.info(f'send_request_headers:{headers}')
                    log.info(f'send_request_url:{url}')
                    log.info(f'send_request_data:{data_body}')
                    log.info(f'send_request_response:{response}')
                    cnt += 1
                    time.sleep(1)
                    log.info(f'等1秒钟之后，重新请求')
                    return self.send_request(url, data_body, method=method, cnt=cnt, timeout=timeout)
                try:
                    return_dict = response.json()
                except Exception as e:
                    # 如果响应不是JSON格式，返回包含错误信息的字典
                    log.error(f'解析响应JSON失败: {e}')
                    log.error(f'响应文本: {response.text}')
                    return_dict = {
                        'status_code': response.status_code,
                        'error_message': response.text[:500],  # 只返回前500个字符
                        'success': False
                    }
                if CommonConfig.FULL_LOG_FLAG is True:
                    log.info(f'send_request_headers:{headers}')
                    log.info(f'send_request_url:{url}')
                    log.info(f'send_request_data:{data_body}')
                    log.info(f'send_request_response:{response}')
                    log.info(f'send_request:{return_dict}')
                return return_dict
            except Exception as e:
                log.info(f'第{cnt}次请求失败')
                log.error(traceback.format_exc())
                log.error(e.args[0])
                cnt += 1
                return self.send_request(url, data_body, method=method, cnt=cnt, timeout=timeout)

        else:
            log.info(f'重试次数超过2次,请求失败{url}')
            # 返回包含错误信息的字典
            return {
                'status_code': 500,
                'error_message': '请求超时或重试次数过多',
                'success': False
            }


if __name__ == '__main__':
    for i in range(10):
        ds = SendRequest()
        time.sleep(2)