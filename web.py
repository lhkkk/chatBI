# -*- coding: utf-8 -*-

# @Project    :chatBI_develop_1_0_0
# @Version    :v1.0.0
# @File       :web.py
# @Author     :
# @Describe   :

from config import CommonConfig
from datetime import datetime
import pytz
import time
import streamlit as st
from prompts import state_prompt
from models import openai_api
from data_source.data_source import DataSource


log = CommonConfig.log

st.set_page_config(
    page_title="ChatApp",
    page_icon=" ",
    layout="wide",
)

# 判断用户是否是第一次访问，第一次访问弹出气球
if "first_visit" not in st.session_state:
    st.session_state.first_visit = True
else:
    st.session_state.first_visit = False
if st.session_state.first_visit:
    # 获取当前的 UTC 时间
    utc_now = datetime.now(tz=pytz.utc)
    # 将 UTC 时间转换为北京时间
    beijing_tz = pytz.timezone("Asia/Shanghai")
    beijing_now = utc_now.astimezone(beijing_tz)

    # 设置 session state 中的 date_time 为北京时间
    st.session_state.date_time = beijing_now
    st.balloons()  # 弹出气球


# model = st.sidebar.selectbox('模型选择', ('TrendyLLM based on LLM',), key="model")
user = st.sidebar.selectbox('角色选择', ('NGFA产品数据分析师',), key="user")
st.sidebar.subheader("我可以帮你解决以下问题：")
background = (
    "我是一个NGFA领域数据分析助手，帮你分析数据~"
)
st.sidebar.markdown(background)
# 导航栏显示日期
st.sidebar.date_input("当前日期：", st.session_state.date_time.date())
st.title('TrendyLLM Analysis For NGFA')
# 显示按钮，并在按钮点击时刷新页面
if st.sidebar.button("刷新"):
    st.write(
        """
        <script>
        window.location.reload();
        </script>
        """,
        unsafe_allow_html=True
    )
    st.session_state.messages = []

# # 历史记录，方便页面展示所有的输入和输出
# if "history" not in st.session_state:
#     st.session_state.history = []

# 检查'session_state'中是否已有'messages'键，如果没有，初始化聊天记录，并设置机器人的问候语
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "有什么可以帮你的吗？"}]


# # 用户的意图，当用户意图确定之后，则不在进行确定，直接进行输入校验，在形成输出后再进行分类
# if "user_intent" not in st.session_state:
#     st.session_state.user_intent = None

# 遍历 session_state 中保存的消息列表
for msg in st.session_state.messages:
    # 根据消息角色 (用户或助手) 创建一个对话框并显示消息内容
    st.chat_message(msg["role"]).write(msg["content"])

start_time = time.time()
if input := st.chat_input('请输入'):
    ## 收集全部的用户输入

    st.chat_message("user").write(input)
    print(st.session_state.messages)
    # 构建请求体，调用后端服务
    # 从历史记录中获取状态码、场景信息等
    status_code = 100  # 默认新会话
    secondary_scene = ""
    third_scene = ""
    intermediate_result = {}
    
    if len(st.session_state.messages) > 1:
        # 从最新的助手回复中获取状态码和场景信息
        last_assistant_msg = st.session_state.messages[-1]['content']
        try:
            # 尝试解析助手回复中的JSON数据
            if isinstance(last_assistant_msg, str) and last_assistant_msg.startswith('{'):
                msg_data = eval(last_assistant_msg)
                status_code = msg_data.get('status_code', 100)
                secondary_scene = msg_data.get('secondary_scene', '')
                third_scene = msg_data.get('third_scene', '')
                intermediate_result = msg_data.get('intermediate_result', {})
        except:
            # 如果解析失败，使用默认值
            pass
    
    request_data = {
        "session_id": "11111111111111",
        "status_code": status_code,
        "user_input": input,
        "history_input": st.session_state.messages,
        "primary_scene": "流量流向分析",
        "secondary_scene": secondary_scene,
        "third_scene": third_scene,
        "intermediate_result": intermediate_result
    }
    # 调用后端接口
    ds = DataSource()
    msg = ds.get_web_data(request_data)

    st.session_state.messages.append({"role": "user", "content": input})

    # # prompt构建
    # llm_prompt = [{"role": "user", "content": state_prompt.prompt.format("任务补充", st.session_state.messages, input)}]
    # # 大模型回答
    # msg = openai_api.create_chat_completion("QWEN2", llm_prompt, None)
    st.session_state.messages.append({"role": "assistant", "content": str(msg)})
    # 显示模型的回应消息
    st.chat_message("assistant").write(msg)


end_time = time.time()
print('cost:{}s'.format(end_time - start_time))
