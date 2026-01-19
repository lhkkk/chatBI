import os
import json
from pathlib import Path
from typing import Dict, Any, List
 
from autointent import Dataset, Pipeline
from autointent.configs import LoggingConfig, DataConfig
 
# 修复OpenMP问题
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
 
 
class TwoLevelIntentClassifier:
    """二级意图分类器 - 使用AutoIntent简化版本"""
    
    def __init__(self, model_dir: str = "./models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        
        # 一级分类器：4个大类
        self.primary_pipeline = None
        
        # 二级分类器：每个大类对应的子分类器
        self.secondary_pipelines = {
            "traffic_flow": None,      # 流量流向分析
            "anomaly": None,           # 异常流量分析  
            "composition": None,       # 流量成分分析
            "chat": None               # 闲聊
        }
        
        # 标签映射
        self.primary_labels = {
            0: "traffic_flow",      # 流量流向分析
            1: "anomaly",           # 异常流量分析
            2: "composition",       # 流量成分分析
            3: "chat"               # 闲聊
        }
        
        self.secondary_labels = {
            "traffic_flow": {
                0: "地域流量分析",
                1: "客户流量分析", 
                2: "IP流量分析"
            },
            "anomaly": {
                0: "PCDN流量分析",
                1: "白手套流量分析",
                2: "拉流流量分析"
            },
            "composition": {
                0: "应用流量分析",
                1: "云业务流量分析",
                2: "异网IDC资源分析", 
                3: "客户流量成分分析"
            },
            "chat": {
                0: "问候类",
                1: "其他闲聊"
            }
        }
    
    def prepare_data(self):
        """准备训练数据"""
        
        # 一级分类数据：4个大类
        primary_data = {
            "train": [
                # 流量流向分析 (Label 0) - 25个样本
                {"utterance": "广东IP在指定时间段内的跨省均值流速情况（单位Mbps），对端限制IDC+MAN，细分省内流出、省外流出、外省流入、本省流入", "label": 0},
                {"utterance": "指定外省网段和广东城域网交互流量统计", "label": 0},
                {"utterance": "指定时间段内，按月统计广东各个地市流出外省均值流速情况（单位Gbps），细分广东IDC流出外省IDC、广东IDC流出外省MAN、广东MAN流出外省IDC、广东MAN流出外省MAN、广东IDC流出外省IDC+MAN、广东MAN流出外省IDC+MAN", "label": 0},
                {"utterance": "指定时间段内，按天统计广东各个地市流出外省均值流速情况（单位Gbps），细分广东IDC流出外省IDC、广东IDC流出外省MAN、广东MAN流出外省IDC、广东MAN流出外省MAN、广东IDC流出外省IDC+MAN、广东MAN流出外省IDC+MAN", "label": 0},
                {"utterance": "统计指定时间段内广东各个地市流出外省均值流速情况（单位Gbps），细分广东IDC流出外省IDC、广东IDC流出外省MAN、广东MAN流出外省IDC、广东MAN流出外省MAN、广东IDC流出外省IDC+MAN、广东MAN流出外省IDC+MAN", "label": 0},
                {"utterance": "统计指定时间段外省、异网、省内专线、省内城域网、省内IDC分别流入广东家企宽均值流速情况", "label": 0},
                {"utterance": "查询指定ip指定时间段从下行口流入ip路由、端口详情数据", "label": 0},
                {"utterance": "徐州云游四海查询22个下行端口流量详情", "label": 0},
                {"utterance": "扬州客户需要IP省内省际流入流出报表汇总", "label": 0},
                {"utterance": "指定时间段按as和地市路由统计跨省流量", "label": 0},
                {"utterance": "idc剔除天翼云的ip流出", "label": 0},
                {"utterance": "查询指定时间段指定ip省外流出，省内流出，省外流入，省内流入", "label": 0},
                {"utterance": "查询指定个ip段的省外流出流量", "label": 0},
                {"utterance": "模糊匹配固定客户分时间段流量统计,省外流出，省内流出，省外流入，省内流入", "label": 0},
                {"utterance": "模糊匹配固定客户分时间段流量统计,省外流出，省内流出，省外流入，省内流入", "label": 0},
                {"utterance": "查询指定时间段指定客户id下设计的ipv4和ipv6网段的省外流出，省内流出，省外流入，省内流入", "label": 0},
                {"utterance": "河南man省外流出，省内流出，省外流入，省内流入", "label": 0},
                {"utterance": "指定时间段指定家宽IP流出到外省TOPIP清单", "label": 0},
                {"utterance": "指定时间段内，浙江流出到联通TOPIP清单", "label": 0},
                {"utterance": "查询指定时间段台州宽带账号流入流出流量", "label": 0},
                {"utterance": "杭州家宽账号流出省外Top1000", "label": 0},
                {"utterance": "指定时间段内指定家宽账号每天的均值流速，细化省外上下行，总上下行", "label": 0},
                {"utterance": "查询浙江各地市idc省内流出流入的月均流量，剔除天翼云和天翼看家", "label": 0},
                {"utterance": "查询指定时间段，外省城域网流入到浙江各地市IDC且剔除天翼云的月均流量", "label": 0},
                {"utterance": "查询指定时间段剔除天翼云和天翼看家后省内各地市结算详情数据", "label": 0},
                
                # 异常流量分析 (Label 1) - 15个样本
                {"utterance": "外省拉流扬州客户IP", "label": 1},
                {"utterance": "查询指定时间段内指定拉流IP的所属地市，所属IDC客户", "label": 1},
                {"utterance": "查询指定日期江苏ip拉流外省，对应拉流客户名称", "label": 1},
                {"utterance": "查询指定日期江苏被外省拉流IP对应客户名称", "label": 1},
                {"utterance": "查询指定日期指定地市的家宽账号访问PCDN域名的清单", "label": 1},
                {"utterance": "指定日期指定地市家宽账号访问PCDN域名数TOPIP清单", "label": 1},
                {"utterance": "查询指定时间段内指定地市被拉流TOPIP及对应的CDNType", "label": 1},
                {"utterance": "查询指定时间段内指定被拉流IP对应拉流IP明细数据", "label": 1},
                {"utterance": "查询指定时间段指定账号每小时的流出流速", "label": 1},
                {"utterance": "查询指定时间段指定账号每小时的流入流速", "label": 1},
                {"utterance": "3a查询指定时间段指定账号最新的ip+username", "label": 1},
                {"utterance": "查找指定时间段指定IP经过的CR路由器下行端口及其流出流量", "label": 1},
                {"utterance": "查询指定时间段AI对应IP流入流量统计", "label": 1},
                {"utterance": "查询指定自定义/IDC客户月均流量数据", "label": 1},
                {"utterance": "查询某个idc客户在指定时间段按月统计流入流出95峰值流量", "label": 1},
                
                # 流量成分分析 (Label 2) - 10个样本
                {"utterance": "top20客户-终端用户流出流量占比详情", "label": 2},
                {"utterance": "查询指定日期指定地市的家宽账号访问PCDN域名的清单", "label": 2},
                {"utterance": "指定日期指定地市家宽账号访问PCDN域名数TOPIP清单", "label": 2},
                {"utterance": "查询浙江各地市idc省内流出流入的月均流量，剔除天翼云和天翼看家", "label": 2},
                {"utterance": "查询指定时间段，外省城域网流入到浙江各地市IDC且剔除天翼云的月均流量", "label": 2},
                {"utterance": "查询指定时间段剔除天翼云和天翼看家后省内各地市结算详情数据", "label": 2},
                {"utterance": "idc剔除天翼云的ip流出", "label": 2},
                {"utterance": "查询指定时间段指定ip省外流出，省内流出，省外流入，省内流入", "label": 2},
                {"utterance": "查询指定个ip段的省外流出流量", "label": 2},
                {"utterance": "模糊匹配固定客户分时间段流量统计,省外流出，省内流出，省外流入，省内流入", "label": 2},
                
                # 闲聊 (Label 3) - 10个样本
                {"utterance": "你好", "label": 3},
                {"utterance": "在吗", "label": 3},
                {"utterance": "今天天气怎么样", "label": 3},
                {"utterance": "今天几号", "label": 3},
                {"utterance": "你是谁", "label": 3},
                {"utterance": "你好啊", "label": 3},
                {"utterance": "在不在", "label": 3},
                {"utterance": "哈喽", "label": 3},
                {"utterance": "谢谢", "label": 3},
                {"utterance": "再见", "label": 3},
            ],
            "validation": [
                {"utterance": "查询指定时间段指定账号每小时的流出流速", "label": 0},
                {"utterance": "查询指定时间段指定账号每小时的流入流速", "label": 0},
                {"utterance": "外省拉流扬州客户IP", "label": 1},
                {"utterance": "查询指定时间段内指定拉流IP的所属地市，所属IDC客户", "label": 1},
                {"utterance": "top20客户-终端用户流出流量占比详情", "label": 2},
                {"utterance": "查询某个idc客户在指定时间段按月统计流入流出95峰值流量", "label": 2},
                {"utterance": "早上好", "label": 3},
                {"utterance": "抱歉", "label": 3},
            ]
        }

        # 二级分类数据
        secondary_data = {
            "traffic_flow": { # 流量流向分析的一级分类下的二级分类
                "train": [
                    # 地域流量分析 (Label 0)
                    {"utterance": "指定时间段内，按月统计广东各个地市流出外省均值流速情况（单位Gbps），细分广东IDC流出外省IDC、广东IDC流出外省MAN、广东MAN流出外省IDC、广东MAN流出外省MAN、广东IDC流出外省IDC+MAN、广东MAN流出外省IDC+MAN", "label": 0},
                    {"utterance": "指定时间段内，按天统计广东各个地市流出外省均值流速情况（单位Gbps），细分广东IDC流出外省IDC、广东IDC流出外省MAN、广东MAN流出外省IDC、广东MAN流出外省MAN、广东IDC流出外省IDC+MAN、广东MAN流出外省IDC+MAN", "label": 0},
                    {"utterance": "统计指定时间段内广东各个地市流出外省均值流速情况（单位Gbps），细分广东IDC流出外省IDC、广东IDC流出外省MAN、广东MAN流出外省IDC、广东MAN流出外省MAN、广东IDC流出外省IDC+MAN、广东MAN流出外省IDC+MAN", "label": 0},
                    {"utterance": "统计指定时间段外省、异网、省内专线、省内城域网、省内IDC分别流入广东家企宽均值流速情况", "label": 0},
                    {"utterance": "指定时间段按as和地市路由统计跨省流量", "label": 0},
                    {"utterance": "河南man省外流出，省内流出，省外流入，省内流入", "label": 0},
                    {"utterance": "查询浙江各地市idc省内流出流入的月均流量，剔除天翼云和天翼看家", "label": 0},
                    {"utterance": "查询指定时间段，外省城域网流入到浙江各地市IDC且剔除天翼云的月均流量", "label": 0},
                    {"utterance": "查询指定时间段剔除天翼云和天翼看家后省内各地市结算详情数据", "label": 0},
                    
                    # 客户流量分析 (Label 1)
                    {"utterance": "徐州云游四海查询22个下行端口流量详情", "label": 1},
                    {"utterance": "扬州客户需要IP省内省际流入流出报表汇总", "label": 1},
                    {"utterance": "模糊匹配固定客户分时间段流量统计,省外流出，省内流出，省外流入，省内流入", "label": 1},
                    {"utterance": "模糊匹配固定客户分时间段流量统计,省外流出，省内流出，省外流入，省内流入", "label": 1},
                    {"utterance": "查询指定时间段指定客户id下设计的ipv4和ipv6网段的省外流出，省内流出，省外流入，省内流入", "label": 1},
                    {"utterance": "查询指定时间段台州宽带账号流入流出流量", "label": 1},
                    {"utterance": "杭州家宽账号流出省外Top1000", "label": 1},
                    {"utterance": "指定时间段内指定家宽账号每天的均值流速，细化省外上下行，总上下行", "label": 1},
                    {"utterance": "查询指定自定义/IDC客户月均流量数据", "label": 1},
                    {"utterance": "查询某个idc客户在指定时间段按月统计流入流出95峰值流量", "label": 1},
                    
                    # IP流量分析 (Label 2)
                    {"utterance": "广东IP在指定时间段内的跨省均值流速情况（单位Mbps），对端限制IDC+MAN，细分省内流出、省外流出、外省流入、本省流入", "label": 2},
                    {"utterance": "指定外省网段和广东城域网交互流量统计", "label": 2},
                    {"utterance": "查询指定ip指定时间段从下行口流入ip路由、端口详情数据", "label": 2},
                    {"utterance": "idc剔除天翼云的ip流出", "label": 2},
                    {"utterance": "查询指定时间段指定ip省外流出，省内流出，省外流入，省内流入", "label": 2},
                    {"utterance": "查询指定个ip段的省外流出流量", "label": 2},
                    {"utterance": "指定时间段指定家宽IP流出到外省TOPIP清单", "label": 2},
                    {"utterance": "指定时间段内，浙江流出到联通TOPIP清单", "label": 2},
                    {"utterance": "查找指定时间段指定IP经过的CR路由器下行端口及其流出流量", "label": 2},
                    {"utterance": "查询指定时间段AI对应IP流入流量统计", "label": 2},
                ],
                "validation": [
                    {"utterance": "查询指定时间段指定账号每小时的流出流速", "label": 1},
                    {"utterance": "查询指定时间段指定账号每小时的流入流速", "label": 1},
                    {"utterance": "查询浙江各地市idc省内流出流入的月均流量，剔除天翼云和天翼看家", "label": 0},
                    {"utterance": "查询指定时间段指定ip省外流出，省内流出，省外流入，省内流入", "label": 2},
                ]
            },
            "anomaly": { # 异常流量分析的一级分类下的二级分类
                "train": [
                    # 拉流流量分析 (Label 0)
                    {"utterance": "外省拉流扬州客户IP", "label": 0},
                    {"utterance": "查询指定时间段内指定拉流IP的所属地市，所属IDC客户", "label": 0},
                    {"utterance": "查询指定日期江苏ip拉流外省，对应拉流客户名称", "label": 0},
                    {"utterance": "查询指定日期江苏被外省拉流IP对应客户名称", "label": 0},
                    {"utterance": "查询指定时间段内指定地市被拉流TOPIP及对应的CDNType", "label": 0},
                    {"utterance": "查询指定时间段内指定被拉流IP对应拉流IP明细数据", "label": 0},
                    
                    # PCDN流量分析 (Label 1)
                    {"utterance": "查询指定日期指定地市的家宽账号访问PCDN域名的清单", "label": 1},
                    {"utterance": "指定日期指定地市家宽账号访问PCDN域名数TOPIP清单", "label": 1},
                    {"utterance": "查询PCDN域名访问流量异常情况", "label": 1},  # 新增
                    {"utterance": "检测家宽账号PCDN访问异常流量", "label": 1},  # 新增
                    
                    # 异常客户流量分析 (Label 2)
                    {"utterance": "查询指定时间段指定账号每小时的流出流速", "label": 2},
                    {"utterance": "查询指定时间段指定账号每小时的流入流速", "label": 2},
                    {"utterance": "3a查询指定时间段指定账号最新的ip+username", "label": 2},
                    {"utterance": "监控客户账号流量异常波动", "label": 2},  # 新增
                    
                    # 异常IP流量分析 (Label 3)
                    {"utterance": "查找指定时间段指定IP经过的CR路由器下行端口及其流出流量", "label": 3},
                    {"utterance": "查询指定时间段AI对应IP流入流量统计", "label": 3},
                    {"utterance": "查询指定自定义/IDC客户月均流量数据", "label": 3},
                    {"utterance": "查询某个idc客户在指定时间段按月统计流入流出95峰值流量", "label": 3},
                ],
                "validation": [
                    {"utterance": "外省拉流扬州客户IP", "label": 0},
                    {"utterance": "查询指定时间段内指定拉流IP的所属地市，所属IDC客户", "label": 0},
                    {"utterance": "查询指定日期指定地市的家宽账号访问PCDN域名的清单", "label": 1},
                    {"utterance": "查询指定时间段指定账号每小时的流出流速", "label": 2},
                    {"utterance": "查询某个idc客户在指定时间段按月统计流入流出95峰值流量", "label": 3},
                ]
            },
            "composition": { # 流量成分分析的一级分类下的二级分类
                "train": [
                    # 客户流量成分分析 (Label 0) - 增加到6个样本
                    {"utterance": "top20客户-终端用户流出流量占比详情", "label": 0},
                    {"utterance": "杭州家宽账号流出省外Top1000", "label": 0},
                    {"utterance": "查询指定时间段指定账号每小时的流出流速", "label": 0},
                    {"utterance": "查询指定时间段指定账号每小时的流入流速", "label": 0},
                    {"utterance": "3a查询指定时间段指定账号最新的ip+username", "label": 0},
                    {"utterance": "指定时间段内指定家宽账号每天的均值流速，细化省外上下行，总上下行", "label": 0},
                    
                    # 应用流量分析 (Label 1) - 增加到4个样本
                    {"utterance": "查询指定日期指定地市的家宽账号访问PCDN域名的清单", "label": 1},
                    {"utterance": "指定日期指定地市家宽账号访问PCDN域名数TOPIP清单", "label": 1},
                    {"utterance": "分析PCDN应用流量占比和分布情况", "label": 1},
                    {"utterance": "查询各类应用流量成分占比统计", "label": 1},
                    
                    # 云业务流量分析 (Label 2) - 增加到4个样本
                    {"utterance": "查询某个idc客户在指定时间段按月统计流入流出95峰值流量", "label": 2},
                    {"utterance": "查询指定自定义/IDC客户月均流量数据", "label": 2},
                    {"utterance": "查询指定时间段AI对应IP流入流量统计", "label": 2},
                    {"utterance": "分析云业务流量在各客户间的分布情况", "label": 2},
                    
                    # 地域流量成分分析 (Label 3) - 增加到4个样本
                    {"utterance": "查询浙江各地市idc省内流出流入的月均流量，剔除天翼云和天翼看家", "label": 3},
                    {"utterance": "查询指定时间段，外省城域网流入到浙江各地市IDC且剔除天翼云的月均流量", "label": 3},
                    {"utterance": "查询指定时间段剔除天翼云和天翼看家后省内各地市结算详情数据", "label": 3},
                    {"utterance": "分析各地市流量成分占比和流向分布", "label": 3},
                    
                    # IP流量成分分析 (Label 4) - 保持4个样本
                    {"utterance": "idc剔除天翼云的ip流出", "label": 4},
                    {"utterance": "查询指定时间段指定ip省外流出，省内流出，省外流入，省内流入", "label": 4},
                    {"utterance": "查询指定个ip段的省外流出流量", "label": 4},
                    {"utterance": "模糊匹配固定客户分时间段流量统计,省外流出，省内流出，省外流入，省内流入", "label": 4},
                ],
                "validation": [
                    {"utterance": "top20客户-终端用户流出流量占比详情", "label": 0},
                    {"utterance": "查询某个idc客户在指定时间段按月统计流入流出95峰值流量", "label": 2},
                    {"utterance": "查询浙江各地市idc省内流出流入的月均流量，剔除天翼云和天翼看家", "label": 3},
                    {"utterance": "idc剔除天翼云的ip流出", "label": 4},
                    {"utterance": "指定日期指定地市家宽账号访问PCDN域名数TOPIP清单", "label": 1},
                ]
            },
        "chat": { # 闲聊的一级分类下的二级分类
            "train": [
                # 基本问候 (Label 0) - 增加到6个样本
                {"utterance": "你好", "label": 0},
                {"utterance": "在吗", "label": 0},
                {"utterance": "你好啊", "label": 0},
                {"utterance": "在不在", "label": 0},
                {"utterance": "哈喽", "label": 0},
                {"utterance": "嗨", "label": 0},
                {"utterance": "早上好", "label": 0},
                
                # 日常交流 (Label 1) - 增加到6个样本
                {"utterance": "今天天气怎么样", "label": 1},
                {"utterance": "今天几号", "label": 1},
                {"utterance": "你是谁", "label": 1},
                {"utterance": "现在几点", "label": 1},
                {"utterance": "最近怎么样", "label": 1},
                {"utterance": "吃饭了吗", "label": 1},
                
                # 礼貌用语 (Label 2) - 增加到6个样本
                {"utterance": "谢谢", "label": 2},
                {"utterance": "再见", "label": 2},
                {"utterance": "不客气", "label": 2},
                {"utterance": "抱歉", "label": 2},
                {"utterance": "不好意思", "label": 2},
                {"utterance": "麻烦你了", "label": 2},
            ],
            "validation": [
                {"utterance": "晚上好", "label": 0},
                {"utterance": "下午好", "label": 0},
                {"utterance": "今天天气", "label": 1},
                {"utterance": "你是做什么的", "label": 1},
                {"utterance": "非常感谢", "label": 2},
                {"utterance": "对不起", "label": 2},
            ]
        }

        }
                
        return primary_data, secondary_data
    
    def train_primary(self, primary_data: Dict[str, Any]):
        print("开始训练一级分类器...")
        
        # 将数据加载到 AutoIntent
        dataset = Dataset.from_dict(primary_data)
        print(f"一级数据集加载完成: {dataset}")
        
        # 初始化并训练 AutoML 管道 - 使用类似示例的简洁方法
        self.primary_pipeline = Pipeline.from_preset("classic-light")
        print("一级分类器Pipeline创建完成")
        
        # 训练
        print("开始训练一级分类器...")
        context = self.primary_pipeline.fit(dataset)
        print("一级分类器训练完成")
        
        # 保存模型
        primary_path = self.model_dir / "primary"
        self.primary_pipeline.dump(primary_path)
        print(f"一级分类器已保存到: {primary_path}")
    
    def train_secondary(self, secondary_data: Dict[str, Dict[str, Any]]):
        print("开始训练二级分类器...")
        
        for category, data in secondary_data.items():
            print(f"训练 {category} 二级分类器...")
            
            # 将数据加载到 AutoIntent
            dataset = Dataset.from_dict(data)
            print(f"{category} 数据集加载完成")
            
            # 初始化并训练 AutoML 管道
            pipeline = Pipeline.from_preset("classic-light")
            print(f"{category} Pipeline创建完成")
            
            # 训练
            print(f"开始训练 {category} 二级分类器...")
            pipeline.fit(dataset)
            print(f"{category} 二级分类器训练完成")
            
            # 保存模型
            secondary_path = self.model_dir / "secondary" / category
            secondary_path.parent.mkdir(exist_ok=True)
            pipeline.dump(secondary_path)
            print(f"{category} 二级分类器已保存到: {secondary_path}")
            
            self.secondary_pipelines[category] = pipeline
    
    def predict(self, utterance: str) -> Dict[str, str]:
        """预测意图"""
        # 一级分类
        primary_pred = self.primary_pipeline.predict([utterance])[0]
        primary_category = self.primary_labels[primary_pred]
        
        # 如果是闲聊，直接返回
        if primary_category == "chat":
            return {
                "primary": "闲聊",
                "secondary": "闲聊",
                "category": primary_category
            }
        
        # 二级分类
        secondary_pipeline = self.secondary_pipelines[primary_category]
        if secondary_pipeline is None:
            return {
                "primary": self._get_primary_name(primary_category),
                "secondary": "未分类",
                "category": primary_category
            }
        
        secondary_pred = secondary_pipeline.predict([utterance])[0]
        secondary_label = self.secondary_labels[primary_category][secondary_pred]
        
        return {
            "primary": self._get_primary_name(primary_category),
            "secondary": secondary_label,
            "category": primary_category
        }
    
    def _get_primary_name(self, category: str) -> str:
        """获取一级分类名称"""
        names = {
            "traffic_flow": "流量流向分析",
            "anomaly": "异常流量分析",
            "composition": "流量成分分析",
            "chat": "闲聊"
        }
        return names.get(category, category)
    
    def batch_predict(self, utterances: List[str]) -> List[Dict[str, str]]:
        """批量预测"""
        return [self.predict(utterance) for utterance in utterances]
    
    def save_config(self):
        """保存配置"""
        config = {
            "primary_labels": self.primary_labels,
            "secondary_labels": self.secondary_labels
        }
        
        config_path = self.model_dir / "config.json"
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"配置已保存到: {config_path}")
    
    def load_models(self):
        """加载已训练的模型"""
        print("加载已训练的模型...")
        
        # 加载一级分类器
        primary_path = self.model_dir / "primary"
        if primary_path.exists():
            self.primary_pipeline = Pipeline.load(primary_path)
            print("一级分类器加载成功")
        
        # 加载二级分类器
        for category in self.secondary_pipelines.keys():
            secondary_path = self.model_dir / "secondary" / category
            if secondary_path.exists():
                self.secondary_pipelines[category] = Pipeline.load(secondary_path)
                print(f"{category} 二级分类器加载成功")
        
        # 加载配置
        config_path = self.model_dir / "config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.primary_labels = config.get("primary_labels", self.primary_labels)
                self.secondary_labels = config.get("secondary_labels", self.secondary_labels)
            print("配置加载成功")
 
 
def main():
    """主函数"""
    # 创建分类器
    classifier = TwoLevelIntentClassifier()
    
    # 准备数据
    primary_data, secondary_data = classifier.prepare_data()
    
    # 训练模型
    classifier.train_primary(primary_data)
    classifier.train_secondary(secondary_data)
    
    # 保存配置
    classifier.save_config()
    
    # 测试预测
    test_utterances = [
    "查询指定时间段内，按月统计广东各个地市流出外省均值流速情况（单位Gbps），细分广东IDC流出外省IDC、广东IDC流出外省MAN、广东MAN流出外省IDC、广东MAN流出外省MAN、广东IDC流出外省IDC+MAN、广东MAN流出外省IDC+MAN",
    "外省拉流扬州客户IP",
    "top20客户-终端用户流出流量占比详情",
    "你好，今天天气怎么样"
]
    
    print("\n=== 预测结果 ===")
    for utterance in test_utterances:
        result = classifier.predict(utterance)
        print(f"输入: '{utterance}'")
        print(f"预测: 一级={result['primary']}, 二级={result['secondary']}")
        print()
 
 
if __name__ == "__main__":
    main()