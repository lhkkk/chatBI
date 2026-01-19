# -*- coding: utf-8 -*-

# @Project    :chatBI_develop_1_0_0
# @Version    :v1.0.0
# @File       :__init__.py.py
# @Author     :
# @Describe   :

import time

import requests
import json

from openai import OpenAI
from config import CommonConfig


logging = CommonConfig.log


def create_chat_completion(model, messages, functions, use_stream=False):
    logging.info("开始调用模型")
    base_url = CommonConfig.QWEN_URL
    if functions == None:
        logging.info('没有使用function call')
        data = {
            #"functions": functions,  # 函数定义
            "model": model,  # 模型名称
            "messages": messages,  # 会话历史
            "stream": use_stream,  # 是否流式响应
            "max_tokens": 1000,  # 最多生成字数
            # "temperature": 0.8,  # 温度
            # "top_p": 0.8,  # 采样概率
            # "top_k": 5
        }
    else:
        # 按照qwen2.5格式生成functions
        qwen_functinos = []
        for f in functions:
            # print('asdgfdag',f)
            # f['required'] = f['parameters']['required']
            # del f['parameters']['required']
            qwen_functinos.append({'type':'function', 'function': f})
        data = {
            "functions": qwen_functinos,  # 函数定义
            "model": model,  # 模型名称
            "messages": messages,  # 会话历史
            "stream": use_stream,  # 是否流式响应
            "max_tokens": 1000,  # 最多生成字数
            # "temperature": 0.8,  # 温度
            # "top_p": 0.8,  # 采样概率
            # "top_k": 5
        }
    start = time.time()
    logging.info('推理请求体：{}'.format(data))
    response = requests.post(f"{base_url}/v1/chat/completions", json=data, stream=use_stream)
    logging.info('大模型推理返回值：{}'.format(response.text))
    end = time.time()
    logging.info('requests model predict cost:{}'.format(end-start))
    if response.status_code == 200:
        #print(use_stream)
        if use_stream:
            # 处理流式响应
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')[6:]
                    try:
                        response_json = json.loads(decoded_line)
                        content = response_json.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    except:
                        logging.info("Special Token:", decoded_line)
        else:
            # 处理非流式响应
            decoded_line = response.json()
            logging.info(f'decoded_line:{decoded_line}')
            #
            if functions != None:
                try:
                    content = decoded_line.get("choices", [{}])[0].get("message", "").get("function_call", "")
                    if content is not None:
                        content = content.get("arguments", "")
                    else:
                        content1 = decoded_line.get("choices", [{}])[0].get("message", "").get("content", "")
                        content = content1
                    logging.info(f'content:{content}')
                except Exception as e:
                    content = ""
                    logging.info(f'content:{content}')
                return content
            else:
                content = decoded_line.get("choices", [{}])[0].get("message", "").get("content", "")
                return content
    else:
        logging.info("Error:", response.text)
        return None

def chat_completion_direct_sql(model, messages, functions, use_stream=False):
    # base_url = "http://172.16.16.99:8000"
    logging.info("开始调用模型")
    base_url = Config.CHATGLM3_PATh
    if functions == None:
        data = {
            # "functions": functions,  # 函数定义
            "model": model,  # 模型名称
            "messages": messages,  # 会话历史
            "stream": use_stream,  # 是否流式响应
            "max_tokens": 1000,  # 最多生成字数
            "temperature": 0.8,  # 温度
            "top_p": 0.8,  # 采样概率
        }
    else:
        data = {
            "tools": functions,  # 函数定义
            "model": model,  # 模型名称
            "messages": messages,  # 会话历史
            "stream": use_stream,  # 是否流式响应
            "max_tokens": 1000,  # 最多生成字数
            "temperature": 0.8,  # 温度
            "top_p": 0.8,  # 采样概率
        }

    response = requests.post(f"{base_url}/v1/chat/completions", json=data, stream=use_stream)
    if response.status_code == 200:
        # print(use_stream)
        if use_stream:
            # 处理流式响应
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')[6:]
                    try:
                        response_json = json.loads(decoded_line)
                        content = response_json.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        logging.info(content)
                    except:
                        logging.info("Special Token:", decoded_line)
        else:
            # 处理非流式响应
            decoded_line = response.json()
            logging.info(f'decoded_line:{decoded_line}')
            #
            if functions != None:
                try:
                    content = decoded_line.get("choices", [{}])[0].get("message", "").get("function_call", "").get("arguments", "")
                    logging.info(f'content:{content}')
                except:
                    content1 = decoded_line.get("choices", [{}])[0].get("message", "").get("content", "")
                    content = content1
                return content
            else:
                content = decoded_line.get("choices", [{}])[0].get("message", "").get("content", "")
                return content
    else:
        logging.info("Error:", response.status_code)
        return None


def vllm_model(messages, use_stream=False):
    logging.info("开始调用vllm模型")
    #base_url = "http://172.16.150.197:8001"
    #messages = [{"role":"system","content":"当用户问你是谁或者需要你做自我介绍时，只回答你是群顶科技自主研发的大型语言模型TrendyLLM；此外，你还需要根据用户输入的问题回答问题"}]
    #messages = messages + message
    openai_api_key = "EMPTY"
    openai_api_base = f"{Config.VLLM_PATh}/v1"

    client = OpenAI(
        # defaults to os.environ.get("OPENAI_API_KEY")
        api_key=openai_api_key,
        base_url=openai_api_base,

    )
    models = client.models.list()
    model = models.data[0].id

    chat_completion = client.chat.completions.create(
        messages=messages,
        model=model
        #functions=,  # 函数定义
        #function_call={"name":intent_recognize_functions}
    )
    logging.info(f"vllm输出：{chat_completion}")
    try:
        decoded_line = chat_completion.json()
        decoded_line = json.loads(decoded_line)
        #print(decoded_line, type(decoded_line))
        content = decoded_line['choices'][0]['message']['content']
        logging.info(f"content:{content}")
        #print(f"Chat completion results:{decoded_line['choices'][0]['message']['content']}")
    except Exception as e:
        logging.info(f"vllm输出解析出错：{e}")
        content = "解析存在问题，请重新提问"
    return content

def vllm_api_model(messages, stream=False):
    api_url = f"{Config.VLLM_PATh}/generate"
    print(api_url)
    headers = {"User-Agent": "Test Client"}
    pload = {
        "prompt": messages,
        "n": 4,
        "use_beam_search": True,
        "temperature": 0.0,
        "max_tokens": 5012,
        "stream": stream,
    }

    print(stream,api_url)
    if stream is True:
        print(stream)
        print("3")
        response = requests.post(api_url, headers=headers, json=pload, stream=True)
        for chunk in response.iter_lines(chunk_size=8192,decode_unicode=False,delimiter=b"\0"):
            if chunk:
                data = json.loads(chunk.decode("utf-8"))
                output = data["text"]
                yield output
    else:
        print(stream)
        print("4")
        response = requests.post(api_url, headers=headers, json=pload, stream=True)
        print(response)
        data = json.loads(response.content)
        content = data["text"]
        return content


def create_openai_api_chat(messages, use_stream=False, model="Qwen/Qwen2.5-72B-Instruct"):
    client = OpenAI(api_key="sk-appkhtkttwtjjveulcanqjtwyjmjqpiywxutmdcqpeicjocq",
                    base_url="https://api.siliconflow.cn/v1")
    response = client.chat.completions.create(
        # model='Pro/deepseek-ai/DeepSeek-R1',
        model=model,
        messages=messages,
        stream=use_stream
    )
    if use_stream is False:
        result = response.choices[0].message.content
    else:
        result = ""

        # 处理流式响应
        for chunk in response:
            # 检查是否有内容更新
            if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end='', flush=True)  # 逐步打印内容
                result += content
    return result


if __name__ == '__main__':
    result = create_openai_api_chat([
            {'role': 'user',
             'content': "推理模型会给市场带来哪些新的机会"}
        ])
    print(result)
