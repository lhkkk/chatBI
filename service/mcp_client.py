#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import asyncio
import os
import json
from typing import List, Dict, Any
from contextlib import AsyncExitStack
from dotenv import load_dotenv

# 导入MCP相关库
from mcp.client.sse import sse_client
from mcp import ClientSession
from openai import OpenAI

# 设置环境变量
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'


class MCPClientWithSiliconFlow:
    def __init__(self, mcp_server_url: str, silicon_flow_api_key: str):
        """
        初始化 MCP 客户端与硅基流动集成
        
        :param mcp_server_url: MCP服务器SSE地址
        :param silicon_flow_api_key: 硅基流动API密钥
        """
        self.mcp_server_url = mcp_server_url
        self.silicon_flow_api_key = silicon_flow_api_key
        self.sessions = {}
        self.tool_mapping = {}
        self.tool_descriptions = {}  # 存储工具详细描述
        self.exit_stack = AsyncExitStack()
        
        # 初始化硅基流动客户端
        self.silicon_flow_client = OpenAI(
            base_url="https://api.siliconflow.cn/v1",
            api_key=self.silicon_flow_api_key
        )

    async def initialize_mcp_session(self):
        """初始化与MCP服务器的连接并获取工具列表"""
        try:
            # 创建SSE客户端并建立连接
            async with sse_client(url=self.mcp_server_url, timeout=60, sse_read_timeout=60*5) as streams:
                async with ClientSession(*streams) as session:
                    # 初始化会话
                    await session.initialize()
                    
                    # 获取可用的工具列表
                    tools_response = await session.list_tools()
                    self.sessions["mcp_server"] = session
                    
                    # 构建工具映射和详细描述
                    for tool in tools_response.tools:
                        self.tool_mapping[tool.name] = (session, tool.name)
                        # 存储工具的描述信息
                        self.tool_descriptions[tool.name] = {
                            "name": tool.name,
                            "description": tool.description or f"工具: {tool.name}",
                            "inputSchema": tool.inputSchema
                        }
                    
                    print(f"已成功连接到MCP服务器，可用工具: {[tool.name for tool in tools_response.tools]}")
                    # 打印工具详情
                    for tool_name, desc in self.tool_descriptions.items():
                        print(f"工具 '{tool_name}': {desc['description']}")
                        if desc['inputSchema']:
                            print(f"  参数schema: {json.dumps(desc['inputSchema'], ensure_ascii=False, indent=2)}")
                    return True
            
        except Exception as e:
            print(f"连接MCP服务器失败: {e}")
            return False

    async def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """调用MCP工具"""
        if tool_name not in self.tool_mapping:
            return f"错误: 工具 '{tool_name}' 不存在"
        
        try:
            session, original_tool_name = self.tool_mapping[tool_name]
            print(f"正在调用工具 '{tool_name}'，参数: {arguments}")
            result = await session.call_tool(original_tool_name, arguments)
            print(f"工具调用结果: {result.content}")
            return result.content
        except Exception as e:
            error_msg = f"调用工具 '{tool_name}' 时出错: {e}"
            print(error_msg)
            return error_msg

    def call_silicon_flow_api(self, messages: List[Dict], tools: List[Dict] = None) -> Dict:
        """
        调用硅基流动大模型API
        
        :param messages: 消息列表
        :param tools: 可用的工具列表
        :return: API响应
        """
        try:
            params = {
                "model": "deepseek-ai/DeepSeek-R1",
                "messages": messages,
                "max_tokens": 2000
            }
            
            if tools:
                params["tools"] = tools
                params["tool_choice"] = "auto"
            
            response = self.silicon_flow_client.chat.completions.create(**params)
            return response.choices[0].message
            
        except Exception as e:
            print(f"调用硅基流动API失败: {e}")
            return None

    def build_tools_description(self) -> List[Dict]:
        """构建详细的工具描述供大模型使用"""
        tools = []
        for tool_name, tool_info in self.tool_descriptions.items():
            tool_param = {
                "type": "function",
                "function": {
                    "name": tool_info["name"],
                    "description": tool_info["description"],
                    "parameters": tool_info["inputSchema"] or {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": True
                    }
                }
            }
            tools.append(tool_param)
        return tools

    async def process_user_query_with_tools(self, user_question: str) -> str:
        """
        处理用户问题：使用工具描述让大模型构建参数并调用工具
        
        :param user_question: 用户问题
        :return: 最终回答
        """
        # 构建详细的工具描述
        available_tools = self.build_tools_description()
        
        # 初始消息 - 指导大模型如何构建参数
        system_message = """你是一个AI助手，可以调用各种工具来帮助用户解决问题。

请仔细分析用户的问题，根据可用的工具和其参数要求，构建正确的参数来调用工具。
调用工具后，分析工具返回的结果，为用户提供清晰、有用的回答。

重要：在调用工具时，请确保参数格式正确，符合工具的参数要求。"""
        
        messages = [
            {
                "role": "system", 
                "content": system_message
            },
            {
                "role": "user", 
                "content": user_question
            }
        ]
        
        print(f"\n用户问题: {user_question}")
        print("正在分析问题并选择工具...")
        
        # 第一次调用：让大模型选择工具并构建参数
        response = self.call_silicon_flow_api(messages, available_tools)
        
        if not response:
            return "抱歉，调用大模型服务失败。"
        
        final_response = ""
        
        # 检查是否需要调用工具
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    print(f"大模型选择的工具: {tool_name}")
                    print(f"大模型构建的参数: {arguments}")
                except Exception as e:
                    print(f"解析参数失败: {e}")
                    arguments = {}
                
                # 将工具调用添加到消息历史
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tool_call]
                })
                
                # 执行工具调用
                print(f"正在调用工具 '{tool_name}'...")
                tool_result = await self.call_mcp_tool(tool_name, arguments)
                
                # 将工具结果添加到消息中
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })
                
                print("工具调用完成，正在分析结果...")
                
                # 再次调用大模型处理工具结果并生成最终回答
                final_response_msg = self.call_silicon_flow_api(messages)
                if final_response_msg and final_response_msg.content:
                    final_response = final_response_msg.content
                else:
                    final_response = f"工具 '{tool_name}' 返回结果: {tool_result}"
        else:
            # 如果没有工具调用，直接使用大模型的回复
            final_response = response.content if response.content else "未能生成有效回答"
        
        return final_response

    async def process_user_query(self, user_question: str) -> str:
        """
        处理用户问题的主函数
        """
        try:
            return await self.process_user_query_with_tools(user_question)
        except Exception as e:
            print(f"处理用户查询时出错: {e}")
            return f"处理请求时出现错误: {e}"

async def get_mcp_result(user_input: str):
    # 加载环境变量
    load_dotenv()
    
    # 配置参数
    MCP_SERVER_URL = "http://192.168.36.204:8081/mcp/book-service-2/sse"
    SILICON_FLOW_API_KEY = "sk-pblhdnsnlscxvpkjcjblmanqkxsyphomjepyidcuraggypkd"
    
    if not SILICON_FLOW_API_KEY:
        print("请设置硅基流动API密钥")
        return
    
    # 创建客户端实例
    client = MCPClientWithSiliconFlow(MCP_SERVER_URL, SILICON_FLOW_API_KEY)
    
    try:
        # 初始化MCP连接
        success = await client.initialize_mcp_session()
        if not success:
            print("初始化MCP连接失败，请检查服务器地址和网络连接")
            return
        
        # 处理用户查询
        result = await client.process_user_query(user_input)
        print(f"\n最终回答: {result}")
        
    except Exception as e:
        print(f"程序运行出错: {e}")

if __name__ == "__main__":
    # 运行主程序
    user_question = "查询源端地址为10.10.10.10的所有流量"
    asyncio.run(get_mcp_result(user_question))
