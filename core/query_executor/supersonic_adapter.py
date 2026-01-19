# -*- coding: utf-8 -*-

# @Project    :chatBI_develop_1_0_0
# @Version    :v1.0.0
# @File       :supersonic_adapter.py
# @Author     :
# @Describe   :Supersonic平台适配器
import requests
import jwt
import time
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SuperSonicConfig:
    base_url: str
    username: str
    password: str
    secret_key: str = "WIaO9YRRVt+7QtpPvyWsARFngnEcbaKBk783uGFwMrbJBaochsqCH62L4Kijcb0sZCYoSsiKGV/zPml5MnZ3uQ=="


class CompleteSuperSonicClient:
    def __init__(self, config: SuperSonicConfig):
        self.config = config
        self.session = requests.Session()
        self.jwt_token = None

    def generate_jwt_token(self) -> str:
        """生成JWT令牌用于API认证"""
        exp = time.time() + 100000
        token = jwt.encode({
            "token_user_name": self.config.username,
            "exp": exp
        }, self.config.secret_key, algorithm="HS512")
        return token

        # ==================== 1. 用户认证与权限管理 ====================

    def login(self) -> Dict:
        """用户登录"""
        self.jwt_token = self.generate_jwt_token()
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        response = self.session.get(
            f"{self.config.base_url}/api/auth/user/getCurrentUser",
            headers=headers
        )
        return response.json()

    def register_user(self, user_data: Dict) -> Dict:
        """用户注册"""
        headers = {"Content-Type": "application/json"}
        response = self.session.post(
            f"{self.config.base_url}/api/auth/user/register",
            headers=headers,
            json=user_data
        )
        return response.json()

    def generate_access_token(self, name: str, expire_time: int) -> Dict:
        """生成访问令牌"""
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        data = {"name": name, "expireTime": expire_time}
        response = self.session.post(
            f"{self.config.base_url}/api/auth/user/generateToken",
            headers=headers,
            json=data
        )
        return response.json()

    def get_user_tokens(self) -> Dict:
        """获取用户令牌列表"""
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        response = self.session.get(
            f"{self.config.base_url}/api/auth/user/getUserTokens",
            headers=headers
        )
        return response.json()

    def delete_user_token(self, token_id: int) -> Dict:
        """删除访问令牌"""
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        response = self.session.post(
            f"{self.config.base_url}/api/auth/user/deleteUserToken?tokenId={token_id}",
            headers=headers
        )
        return response.json()

        # ==================== 2. 代理系统管理 ====================

    def get_agent_list(self) -> Dict:
        """获取代理列表"""
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        response = self.session.get(
            f"{self.config.base_url}/api/chat/agent/getAgentList",
            headers=headers
        )
        return response.json()

    def create_agent(self, agent_data: Dict) -> Dict:
        """创建代理"""
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        response = self.session.post(
            f"{self.config.base_url}/api/chat/agent/createAgent",
            headers=headers,
            json=agent_data
        )
        return response.json()

    def update_agent(self, agent_data: Dict) -> Dict:
        """更新代理配置"""
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        response = self.session.put(
            f"{self.config.base_url}/api/chat/agent/updateAgent",
            headers=headers,
            json=agent_data
        )
        return response.json()

        # ==================== 3. 搜索推荐 ====================

    def search_recommendations(self, query_text: str, agent_id: int) -> Dict:
        """搜索推荐 - 获取相关实体和推荐"""
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        data = {
            "queryText": query_text,
            "agentId": agent_id,
            "chatId": -1
        }
        response = self.session.post(
            f"{self.config.base_url}/api/chat/query/search",
            headers=headers,
            json=data
        )
        return response.json()

        # ==================== 4. 语义映射 - 实体识别与提取 ====================

    def semantic_mapping(self, query_text: str, data_set_ids: List[int]) -> Dict:
        """语义映射 - 实体识别与提取"""
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        data = {
            "queryText": query_text,
            "dataSetIds": data_set_ids
        }
        response = self.session.post(
            f"{self.config.base_url}/api/semantic/query/chat/map",
            headers=headers,
            json=data
        )
        return response.json()

        # ==================== 5. 语义解析 - 生成候选查询和Score计算 ====================

    def semantic_parsing(self, query_text: str, data_set_ids: List[int]) -> Dict:
        """语义解析 - 生成候选查询和Score计算"""
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        data = {
            "queryText": query_text,
            "dataSetIds": data_set_ids
        }
        response = self.session.post(
            f"{self.config.base_url}/api/semantic/query/chat/parse",
            headers=headers,
            json=data
        )
        return response.json()

        # ==================== 6. 聊天查询解析 ====================

    def chat_query_parse(self, query_text: str, agent_id: int, chat_id: int = -1) -> Dict:
        """聊天查询解析 - 综合解析接口"""
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        data = {
            "queryText": query_text,
            "agentId": agent_id,
            "chatId": chat_id
        }
        response = self.session.post(
            f"{self.config.base_url}/api/chat/query/parse",
            headers=headers,
            json=data
        )
        return response.json()

        # ==================== 7. SQL检验与修正 ====================

    def validate_sql(self, sql: str, data_set_id: int) -> Dict:
        """SQL检验"""
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        data = {
            "sql": sql,
            "dataSetId": data_set_id
        }
        response = self.session.post(
            f"{self.config.base_url}/api/semantic/query/validate",
            headers=headers,
            json=data
        )
        return response.json()

    def validate_and_query(self, sqls: List[str], data_set_id: int) -> Dict:
        """验证并查询"""
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        data = {
            "sqls": sqls,
            "dataSetId": data_set_id
        }
        response = self.session.post(
            f"{self.config.base_url}/api/semantic/query/validateAndQuery",
            headers=headers,
            json=data
        )
        return response.json()

        # ==================== 8. SQL翻译 ====================

    def translate_semantic(self, query_req: Dict) -> Dict:
        """SQL翻译"""
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        response = self.session.post(
            f"{self.config.base_url}/api/semantic/translate",
            headers=headers,
            json=query_req
        )
        return response.json()

        # ==================== 9. SQL执行 ====================

    def execute_sql(self, sql: str, data_set_id: int) -> Dict:
        """SQL执行"""
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        data = {
            "sql": sql,
            "dataSetId": data_set_id
        }
        response = self.session.post(
            f"{self.config.base_url}/api/semantic/query/sql",
            headers=headers,
            json=data
        )
        return response.json()

    def execute_multiple_sqls(self, sqls: List[str], data_set_id: int) -> Dict:
        """批量SQL执行"""
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        data = {
            "sqls": sqls,
            "dataSetId": data_set_id
        }
        response = self.session.post(
            f"{self.config.base_url}/api/semantic/query/sqls",
            headers=headers,
            json=data
        )
        return response.json()

        # ==================== 10. 聊天查询执行 ====================

    def chat_query_execute(self, query_id: int, parse_id: int, agent_id: int, chat_id: int = -1) -> Dict:
        """聊天查询执行"""
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        data = {
            "queryId": query_id,
            "parseId": parse_id,
            "agentId": agent_id,
            "chatId": chat_id,
            "saveAnswer": True
        }
        response = self.session.post(
            f"{self.config.base_url}/api/chat/query/execute",
            headers=headers,
            json=data
        )
        return response.json()

        # ==================== 11. 一体化查询接口 ====================

    def query_complete_flow(self, query_text: str, agent_id: int, chat_id: int = -1) -> Dict:
        """一体化查询接口 - 完整流程"""
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        data = {
            "queryText": query_text,
            "agentId": agent_id,
            "chatId": chat_id
        }
        response = self.session.post(
            f"{self.config.base_url}/api/chat/query/",
            headers=headers,
            json=data
        )
        return response.json()

        # ==================== 12. 完整的分步骤流程 ====================


    def execute_complete_workflow(self, query_text: str, agent_id: int) -> Dict:
        """执行完整的分步骤工作流程"""
        results = {
            "query_text": query_text,
            "agent_id": agent_id,
            "workflow_steps": {},
            "final_result": None,
            "errors": []
        }

        try:
            # 步骤1: 用户认证
            print("🔐 步骤1: 用户认证...")
            login_result = self.login()
            results["workflow_steps"]["1_authentication"] = {
                "step": "用户认证",
                "status": "success" if login_result.get("code") == 200 else "failed",
                "result": login_result
            }

            if login_result.get("code") != 200:
                results["errors"].append("用户认证失败")
                return results

                # 步骤2: 获取代理列表
            print(results)
            print("🤖 步骤2: 获取代理列表...")
            agents = self.get_agent_list()
            results["workflow_steps"]["2_agent_list"] = {
                "step": "获取代理列表",
                "status": "success" if agents.get("code") == 200 else "failed",
                "result": agents
            }

            # 获取数据集ID
            data_set_ids = [1]  # 默认数据集ID
            if agents.get("code") == 200 and agents.get("data"):
                agent_data = next((a for a in agents["data"] if a.get("id") == agent_id), None)
                if agent_data and agent_data.get("dataSetIds"):
                    data_set_ids = agent_data["dataSetIds"]

                    # 步骤3: 搜索推荐
            print(agents)
            print("🔍 步骤3: 搜索推荐...")
            search_result = self.search_recommendations(query_text, agent_id)
            results["workflow_steps"]["3_search_recommendations"] = {
                "step": "搜索推荐",
                "status": "success" if search_result.get("code") == 200 else "failed",
                "result": search_result
            }
            print(search_result)
            # 步骤4: 语义映射 - 实体识别与提取
            print("🎯 步骤4: 语义映射 - 实体识别与提取...")
            mapping_result = self.semantic_mapping(query_text, data_set_ids)
            results["workflow_steps"]["4_semantic_mapping"] = {
                "step": "语义映射",
                "status": "success" if mapping_result.get("code") == 200 else "failed",
                "result": mapping_result
            }
            print(mapping_result)

            # 步骤5: 语义解析 - 生成候选查询和Score计算
            print("⚡ 步骤5: 语义解析 - 生成候选查询...")
            parsing_result = self.semantic_parsing(query_text, data_set_ids)
            results["workflow_steps"]["5_semantic_parsing"] = {
                "step": "语义解析",
                "status": "success" if parsing_result.get("selectedParses") else "failed",
                "result": parsing_result
            }
            print(parsing_result)

            # 步骤6: 聊天查询解析（综合解析）
            print("💬 步骤6: 聊天查询解析...")
            chat_parse_result = self.chat_query_parse(query_text, agent_id)
            results["workflow_steps"]["6_chat_query_parse"] = {
                "step": "聊天查询解析",
                "status": "success" if chat_parse_result.get("code") == 200 else "failed",
                "result": chat_parse_result
            }
            print(chat_parse_result)

            # 检查是否有可用的解析结果
            selected_parses = None
            if chat_parse_result.get("code") == 200 and chat_parse_result.get("data", {}).get("selectedParses"):
                selected_parses = chat_parse_result["data"]["selectedParses"]
            elif parsing_result.get("selectedParses"):
                selected_parses = parsing_result["selectedParses"]

            if not selected_parses:
                results["errors"].append("没有生成有效的解析结果")
                return results

                # 使用第一个解析结果继续后续步骤
            selected_parse = selected_parses[0]
            sql_info = selected_parse.get("sqlInfo", {})
            data_set_id = selected_parse.get("dataSetId", data_set_ids[0])

            # 步骤7: SQL检验与修正
            if sql_info.get("correctedS2SQL"):
                sql = sql_info["correctedS2SQL"]

                print("🔍 步骤7: SQL检验...")
                validate_result = self.validate_sql(sql, data_set_id)
                results["workflow_steps"]["7_sql_validation"] = {
                    "step": "SQL检验",
                    "status": "success" if validate_result.get("code") == 200 else "failed",
                    "result": validate_result
                }
                print(validate_result)

                # 步骤8: SQL翻译
                print("🔄 步骤8: SQL翻译...")
                translate_req = {
                    "sql": sql,
                    "dataSetId": data_set_id,
                    "queryMode": selected_parse.get("queryMode", "METRIC_QUERY")
                }
                translate_result = self.translate_semantic(translate_req)
                results["workflow_steps"]["8_sql_translation"] = {
                    "step": "SQL翻译",
                    "status": "success" if translate_result.get("code") == 200 else "failed",
                    "result": translate_result
                }
                print(translate_result)

                # 步骤9: SQL执行
                print("⚡ 步骤9: SQL执行...")
                final_sql = translate_result.get("querySQL") or sql
                execute_result = self.execute_sql(final_sql, data_set_id)
                results["workflow_steps"]["9_sql_execution"] = {
                    "step": "SQL执行",
                    "status": "success" if execute_result.get("code") == 200 else "failed",
                    "result": execute_result
                }
                print(execute_result)

                # 设置最终结果
                results["final_result"] = execute_result

                # 步骤10: 结果后处理（可选）
                print("📊 步骤10: 结果后处理...")
                if execute_result.get("code") == 200:
                    # 这里可以添加结果格式化、推荐等后处理逻辑
                    processed_result = {
                        "original_query": query_text,
                        "generated_sql": final_sql,
                        "execution_result": execute_result,
                        "parse_info": selected_parse,
                        "workflow_summary": {
                            "total_steps": len(results["workflow_steps"]),
                            "successful_steps": sum(1 for step in results["workflow_steps"].values()
                                                    if step["status"] == "success"),
                            "errors": results["errors"]
                        }
                    }
                    results["workflow_steps"]["10_result_processing"] = {
                        "step": "结果后处理",
                        "status": "success",
                        "result": processed_result
                    }
                    results["final_result"] = processed_result

            else:
                results["errors"].append("未找到有效的SQL信息")

            print("✅ 工作流程执行完成!")
            return results

        except Exception as e:
            error_msg = f"工作流程执行过程中出现错误: {str(e)}"
            print(f"❌ {error_msg}")
            results["errors"].append(error_msg)
            return results

        # ==================== 13. 简化的一体化流程对比 ====================


    def execute_simple_workflow(self, query_text: str, agent_id: int) -> Dict:
        """执行简化的一体化工作流程（用于对比）"""
        try:
            # 用户认证
            login_result = self.login()
            if login_result.get("code") != 200:
                return {"error": "认证失败", "result": login_result}

                # 一体化查询
            result = self.query_complete_flow(query_text, agent_id)
            return {"type": "simple_workflow", "result": result}

        except Exception as e:
            return {"error": f"简化流程执行失败: {str(e)}"}

        # ==================== 14. 使用示例和主函数 ====================


def main():
    """主函数 - 演示完整的工作流程"""
    # 配置信息
    config = SuperSonicConfig(
        base_url="http://192.168.36.58:19080/",  # 替换为您的SuperSonic地址
        username="admin",
        password="123456"
    )

    # 创建客户端
    client = CompleteSuperSonicClient(config)

    # 测试查询
    test_queries = [
        "我想了解最近30天河南省内的IDC和MAN网络，分别向本省和省外其他地区流出和流入的均值流速，请按区域类型和流向进行细分",
    ]

    for query in test_queries:
        print(f"\n{'=' * 60}")
        print(f"🚀 开始执行查询: {query}")
        print(f"{'=' * 60}")

        # 执行完整工作流程
        workflow_result = client.execute_complete_workflow(query, agent_id=5)

        # 输出结果摘要
        print(f"\n📋 工作流程摘要:")
        print(f"   查询文本: {workflow_result['query_text']}")
        print(f"   代理ID: {workflow_result['agent_id']}")
        print(f"   执行步骤: {len(workflow_result['workflow_steps'])}")
        print(f"   错误数量: {len(workflow_result['errors'])}")

        if workflow_result['errors']:
            print(f"   错误信息: {workflow_result['errors']}")

        if workflow_result['final_result']:
            print(f"   最终状态: 成功")
        else:
            print(f"   最终状态: 失败")

            # 详细结果（可选）
        print(f"\n📄 详细结果:")
        print(workflow_result)
        # print(json.dumps(workflow_result, indent=2, ensure_ascii=False))

        print(f"\n{'=' * 60}")


if __name__ == "__main__":
    main()