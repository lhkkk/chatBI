#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
属性提取服务：从用户查询中提取12个关键属性
"""

import re
import json
from typing import List, Dict, Any, Optional

# 检查是否安装了LangChain，如果没有则使用回退方案
try:
    from langchain.chains import LLMChain
    from langchain.prompts import ChatPromptTemplate
    from langchain.schema import SystemMessage, HumanMessage
    from langchain_community.chat_models import ChatTongyi
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

class AttributeExtractor:
    """属性提取器，用于从用户查询中提取12个关键属性"""
    
    def __init__(self, api_key: str = None, model_name: str = "qwen-max"):
        # 初始化正则表达式和关键词
        self.ip_pattern = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
        self.cidr_pattern = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}")
        self.time_pattern = re.compile(r"(\d{4}[-.]\d{1,2}[-.]\d{1,2})|(\d{4}[年](\d{1,2}[月])?(\d{1,2}[日])?)|(\d+[年]\d{1,2}[月]到\d+[年]\d{1,2}[月])|(\d{1,2}[月]\d{1,2}[日]到\d{1,2}[月]\d{1,2}[日])|(\d{1,2}[月]到\d{1,2}[月])|(\d+\s*(天|日|月|小时|星期|周))|(近\d+\s*(天|日|月|小时|星期|周))|(第\d+季度)|(过去\d+\s*(天|日|月|小时|星期|周))|(上季度|本季度|下季度)|(去年|今年|前年)|(上月|本月|下月)|(上周|本周|下周)|(昨天|今天|明天)|(本月至今)|(今年至今)")
        
        # LLM配置
        self.api_key = api_key
        self.model_name = model_name
        self.llm_chain = None
        if api_key:
            self.llm_chain = self._build_llm_chain(api_key, model_name)
        
        # 时间粒度关键词
        self.time_granularity_keywords = {
            "全部": ["结算", "结算详情"],
            "月": ["按月", "每月", "月均", "月统计"],
            "天": ["按天", "每天", "日均", "日统计"],
            "逐时": ["按小时", "每小时", "小时统计"],
            "季度": ["按季度", "季度统计", r"第(\d+)季度"]
        }
        
        # 数据类型关键词
        self.data_type_keywords = {
            "流量总值": ["结算", "结算详情", "总值"],
            "95峰值": ["95峰值", "95峰", "95th", "95%"],
            "流量均值": ["均值", "月均", "日均", "小时均"],
            "占比": ["占比", "比例"],
            "排名": ["top", "topip", "top10", "top20", r"前(\d+)", r"top(\d+)", "topn"],
            "明细": ["明细", "详情", "清单", "报表", "报表汇总"]
        }
        
        # 流向关键词
        self.direction_keywords = {
            "流出": ["流出", "出省", "出口", "流出到"],
            "流入": ["流入", "进省", "入口", "流入到"],
            "流入流出": ["双向", "流入流出", "交互"]
        }
        
        # 上行下行关键词
        self.up_down_keywords = {
            "上行": ["上行", "ut"],
            "下行": ["下行", "dt", "下行口", "下行端口"]
        }
        
    def extract_attributes(self, query: str, history: List[dict] = None) -> Dict[str, Any]:
        """提取12个关键属性
        
        Args:
            query: 用户查询文本
            history: 历史对话记录
            
        Returns:
            包含12个属性的字典
        """
        if history is None:
            history = []
            
        # 初始化结果字典
        result = {
            "源端": "",
            "对端": "",
            "源端类型": "",
            "对端类型": "",
            "时间": "",
            "时间粒度": "",
            "流向": "",
            "数据类型": "",
            "剔除条件": [],
            "模糊匹配": False,
            "上行下行": "",
            "补充信息": ""
        }
        
        # 转换为小写便于匹配
        query_lower = query.lower()
        
        # 步骤1：提取必要属性
        # 优先从二级场景结果中获取源端和对端，避免重复提取
        source_from_scene = ""
        destination_from_scene = ""
        
        # 查找历史中的二级场景结果
        for item in reversed(history):
            if isinstance(item, dict) and "intermediate_result" in item:
                ir = item["intermediate_result"]
                # 优先从新的attributes结构中获取
                if "attributes" in ir:
                    attributes = ir["attributes"]
                    source_from_scene = attributes.get("源端", "")
                    destination_from_scene = attributes.get("对端", "")
                    break
                # 兼容旧的source和destination字段
                elif "source" in ir or "destination" in ir:
                    source_from_scene = ir.get("source", "")
                    destination_from_scene = ir.get("destination", "")
                    break
        
        # 如果二级场景没有识别出，才进行提取
        if not source_from_scene:
            result["源端"] = self._extract_source_end(query, query_lower, history)
        else:
            result["源端"] = source_from_scene
            
        if not destination_from_scene:
            result["对端"] = self._extract_destination_end(query, query_lower, history)
        else:
            result["对端"] = destination_from_scene
            
        result["时间"] = self._extract_time_range_enhanced(query, history)
        
        # 步骤2：提取业务类型属性
        result["源端类型"] = self._extract_source_type(result["源端"], query_lower)
        result["对端类型"] = self._extract_destination_type(result["对端"], query_lower)
        
        # 步骤3：提取默认属性
        result["时间粒度"] = self._extract_time_granularity(query_lower)
        result["流向"] = self._extract_flow_direction(query_lower)
        result["数据类型"] = self._extract_data_type(query_lower)
        result["上行下行"] = self._extract_up_down(query_lower)
        
        # 步骤4：提取条件属性
        result["剔除条件"] = self._extract_exclusion_conditions(query_lower)
        result["模糊匹配"] = self._extract_fuzzy_matching(query_lower)
        
        # 步骤5：提取补充信息
        result["补充信息"] = self._extract_supplementary_info(query)
        
        return result
    
    def check_necessary_attributes(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """检查必要属性是否完整，并生成智能引导问题
        
        Args:
            attributes: 已提取的属性字典
            
        Returns:
            包含缺失属性、提示信息和是否有缺失的字典
        """
        missing_attributes = []
        prompts = []
        
        # 检查源端
        if not attributes.get("源端", "").strip():
            missing_attributes.append("源端")
            # 根据不同场景生成不同的引导问题
            if any(keyword in attributes.get("数据类型", "").lower() for keyword in ["ai", "AI"]):
                prompts.append("麻烦补充下源端信息（AI对应IP具体是哪些？）")
            else:
                prompts.append("请补充源端信息")
        
        # 检查对端
        if not attributes.get("对端", "").strip():
            missing_attributes.append("对端")
            # 根据不同场景生成不同的引导问题
            if any(keyword in attributes.get("数据类型", "").lower() for keyword in ["流量", "流速"]):
                prompts.append("麻烦补充下对端信息（如：省外、省内、或特定对象）")
            elif any(keyword in attributes.get("数据类型", "").lower() for keyword in ["ip", "网段"]):
                prompts.append("麻烦补充下对端信息（源端IP段）")
            else:
                prompts.append("麻烦补充下对端信息")
        
        # 检查时间范围
        if not attributes.get("时间", "").strip():
            missing_attributes.append("时间范围")
            # 检查是否有部分时间信息，如"3号到5号"但缺少月份和年份
            query_content = attributes.get("源端", "") + attributes.get("对端", "")
            if re.search(r"\d{1,2}[号日]到\d{1,2}[号日]", query_content):
                prompts.append("请输入具体的月份和年份")
            elif re.search(r"\d{1,2}月到\d{1,2}月", query_content):
                prompts.append("请输入具体的年份")
            elif re.search(r"(第\d+季度)", query_content):
                prompts.append("请输入具体的年份")
            elif re.search(r"(1月份|2月份|3月份|4月份|5月份|6月份|7月份|8月份|9月份|10月份|11月份|12月份)", query_content):
                prompts.append("请输入具体的年份")
            else:
                prompts.append("请输入你要查询的时间范围")
        
        # 检查源端类型 - 对于地域类型默认为IDC+MAN，其他类型可为空，不要求补充
        if not attributes.get("源端类型", "").strip():
            source = attributes.get("源端", "")
            # 检查是否为地域场景（包含类别词或具体省份名称或地市名称）
            is_geographic = False
            if source:
                # 检查类别词
                category_keywords = ["地市", "各地市", "省份", "省", "市", "地区", "省内", "省外", "省际", "跨省", "外省", "本省", 
                            "国际", "海外", "全国", "全网", "各地", "全国各省", "全国地市", "as", "AS", "地市路由"]
                # 检查具体省份名称
                province_names = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏", "浙江", 
                            "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西", "海南", "重庆", 
                            "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆", "台湾", "香港", "澳门"]
                # 检查具体地市名称
                city_names = ["南京", "杭州", "苏州", "无锡", "常州", "镇江", "扬州", "南通", "泰州", "徐州", "淮安", "盐城", 
                         "连云港", "宿迁", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山", "台州", "丽水",
                         "合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州",
                         "六安", "亳州", "池州", "宣城", "福州", "厦门", "莆田", "三明", "泉州", "漳州", "南平", "龙岩",
                         "宁德", "南昌", "景德镇", "萍乡", "九江", "新余", "鹰潭", "赣州", "吉安", "宜春", "抚州", "上饶",
                         "济南", "青岛", "淄博", "枣庄", "东营", "烟台", "潍坊", "济宁", "泰安", "威海", "日照", "临沂",
                         "德州", "聊城", "滨州", "菏泽", "郑州", "开封", "洛阳", "平顶山", "安阳", "鹤壁", "新乡", "焦作",
                         "濮阳", "许昌", "漯河", "三门峡", "南阳", "商丘", "信阳", "周口", "驻马店", "武汉", "黄石", "十堰",
                         "宜昌", "襄阳", "鄂州", "荆门", "孝感", "荆州", "黄冈", "咸宁", "随州", "恩施", "长沙", "株洲",
                         "湘潭", "衡阳", "邵阳", "岳阳", "常德", "张家界", "益阳", "郴州", "永州", "怀化", "娄底", "湘西",
                         "广州", "韶关", "深圳", "珠海", "汕头", "佛山", "江门", "湛江", "茂名", "肇庆", "惠州", "梅州",
                         "汕尾", "河源", "阳江", "清远", "东莞", "中山", "潮州", "揭阳", "云浮", "南宁", "柳州", "桂林",
                         "梧州", "北海", "防城港", "钦州", "贵港", "玉林", "百色", "贺州", "河池", "来宾", "崇左", "海口",
                         "三亚", "成都", "自贡", "攀枝花", "泸州", "德阳", "绵阳", "广元", "遂宁", "内江", "乐山", "南充",
                         "眉山", "宜宾", "广安", "达州", "雅安", "巴中", "资阳", "贵阳", "六盘水", "遵义", "安顺", "毕节",
                         "铜仁", "昆明", "曲靖", "玉溪", "保山", "昭通", "丽江", "普洱", "临沧", "拉萨", "日喀则", "昌都",
                         "林芝", "山南", "那曲", "西安", "铜川", "宝鸡", "咸阳", "渭南", "延安", "汉中", "榆林", "安康",
                         "商洛", "兰州", "嘉峪关", "金昌", "白银", "天水", "武威", "张掖", "平凉", "酒泉", "庆阳", "定西",
                         "陇南", "西宁", "银川", "石嘴山", "吴忠", "固原", "中卫", "乌鲁木齐", "克拉玛依", "吐鲁番", "哈密"]
                
                if (any(keyword in source for keyword in category_keywords) or 
                    any(province in source for province in province_names) or
                    any(city in source for city in city_names)):
                    is_geographic = True
            
            # 对于地域场景，源端类型默认为IDC+MAN，不提示
            if is_geographic:
                pass
            # 对于客户/IP相关对象，按照框架规则默认留空，不提示
            elif any(keyword in str(source).lower() for keyword in ["客户", "账号", "用户", "家宽", "企宽", "宽带", "ip", "ip地址", "网段", "地址"]):
                pass
            # 对于其他类型（如IP地址、客户等），默认为空，不要求补充
            else:
                pass
        
        # 检查对端类型 - 对于地域类型默认为IDC+MAN，其他类型可为空，不要求补充
        if not attributes.get("对端类型", "").strip():
            destination = attributes.get("对端", "")
            # 检查是否为地域场景（包含类别词或具体省份名称或地市名称）
            is_geographic = False
            if destination:
                # 检查类别词
                category_keywords = ["地市", "各地市", "省份", "省", "市", "地区", "省内", "省外", "省际", "跨省", "外省", "本省", 
                            "国际", "海外", "全国", "全网", "各地", "全国各省", "全国地市", "as", "AS", "地市路由"]
                # 检查具体省份名称
                province_names = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏", "浙江", 
                            "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西", "海南", "重庆", 
                            "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆", "台湾", "香港", "澳门"]
                # 检查具体地市名称
                city_names = ["南京", "杭州", "苏州", "无锡", "常州", "镇江", "扬州", "南通", "泰州", "徐州", "淮安", "盐城", 
                         "连云港", "宿迁", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山", "台州", "丽水",
                         "合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州",
                         "六安", "亳州", "池州", "宣城", "福州", "厦门", "莆田", "三明", "泉州", "漳州", "南平", "龙岩",
                         "宁德", "南昌", "景德镇", "萍乡", "九江", "新余", "鹰潭", "赣州", "吉安", "宜春", "抚州", "上饶",
                         "济南", "青岛", "淄博", "枣庄", "东营", "烟台", "潍坊", "济宁", "泰安", "威海", "日照", "临沂",
                         "德州", "聊城", "滨州", "菏泽", "郑州", "开封", "洛阳", "平顶山", "安阳", "鹤壁", "新乡", "焦作",
                         "濮阳", "许昌", "漯河", "三门峡", "南阳", "商丘", "信阳", "周口", "驻马店", "武汉", "黄石", "十堰",
                         "宜昌", "襄阳", "鄂州", "荆门", "孝感", "荆州", "黄冈", "咸宁", "随州", "恩施", "长沙", "株洲",
                         "湘潭", "衡阳", "邵阳", "岳阳", "常德", "张家界", "益阳", "郴州", "永州", "怀化", "娄底", "湘西",
                         "广州", "韶关", "深圳", "珠海", "汕头", "佛山", "江门", "湛江", "茂名", "肇庆", "惠州", "梅州",
                         "汕尾", "河源", "阳江", "清远", "东莞", "中山", "潮州", "揭阳", "云浮", "南宁", "柳州", "桂林",
                         "梧州", "北海", "防城港", "钦州", "贵港", "玉林", "百色", "贺州", "河池", "来宾", "崇左", "海口",
                         "三亚", "成都", "自贡", "攀枝花", "泸州", "德阳", "绵阳", "广元", "遂宁", "内江", "乐山", "南充",
                         "眉山", "宜宾", "广安", "达州", "雅安", "巴中", "资阳", "贵阳", "六盘水", "遵义", "安顺", "毕节",
                         "铜仁", "昆明", "曲靖", "玉溪", "保山", "昭通", "丽江", "普洱", "临沧", "拉萨", "日喀则", "昌都",
                         "林芝", "山南", "那曲", "西安", "铜川", "宝鸡", "咸阳", "渭南", "延安", "汉中", "榆林", "安康",
                         "商洛", "兰州", "嘉峪关", "金昌", "白银", "天水", "武威", "张掖", "平凉", "酒泉", "庆阳", "定西",
                         "陇南", "西宁", "银川", "石嘴山", "吴忠", "固原", "中卫", "乌鲁木齐", "克拉玛依", "吐鲁番", "哈密"]
                
                if (any(keyword in destination for keyword in category_keywords) or 
                    any(province in destination for province in province_names) or
                    any(city in destination for city in city_names)):
                    is_geographic = True
            
            # 对于地域场景，对端类型默认为IDC+MAN，不提示
            if is_geographic:
                pass
            # 对于客户/IP相关对象，按照框架规则默认留空，不提示
            elif any(keyword in str(destination).lower() for keyword in ["客户", "账号", "用户", "家宽", "企宽", "宽带", "ip", "ip地址", "网段", "地址"]):
                pass
            # 对于其他类型（如IP地址、客户等），默认为空，不要求补充
            else:
                pass
        
        return {
            "missing": missing_attributes,
            "prompt": "。".join(prompts) + "。" if prompts else "",
            "has_missing": len(missing_attributes) > 0
        }
    
    def _extract_source_end(self, query: str, query_lower: str, history: List[dict]) -> str:
        """提取源端"""
        # 处理查询文本，去除开头的查询词
        processed_query = query
        if processed_query.startswith("查询"):
            processed_query = processed_query[2:].strip()
        if processed_query.startswith("请查询"):
            processed_query = processed_query[3:].strip()
        if processed_query.startswith("告诉我"):
            processed_query = processed_query[3:].strip()
        
        # 1. 检查是否有账号ID相关信息
        account_pattern = re.compile(r"账号id是?(\d+)|账号为?(\d+)|账号id:(\d+)")
        account_match = account_pattern.search(processed_query)
        if account_match:
            # 返回账号ID作为源端
            return f"账号id {account_match.group(1) or account_match.group(2) or account_match.group(3)}"
        
        # 2. 去除开头的模糊匹配标记
        if processed_query.startswith("模糊匹配"):
            processed_query = processed_query[4:].strip()
        
        # 3. 检查是否有多个IP地址列表，如"1.2.3.4、23.4.5.6还有172.4.3.4"
        ip_matches = self.ip_pattern.findall(processed_query)
        if ip_matches and len(ip_matches) >= 2:
            # 如果有多个IP地址，返回所有IP地址的列表形式
            return f"[{', '.join(ip_matches)}]"
        elif ip_matches:
            # 单个IP地址
            return ip_matches[0]
        
        # 4. 检查是否有IP范围，如"172.168.22.159到170"
        ip_range_pattern = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3})\.(\d{1,3})到(\d{1,3})")
        ip_range_match = ip_range_pattern.search(processed_query)
        if ip_range_match:
            prefix = ip_range_match.group(1)
            start = ip_range_match.group(2)
            end = ip_range_match.group(3)
            return f"{prefix}.{start}至{prefix}.{end}"
        
        # 5. 检查是否有客户名称（如【杭州市司法局】）
        customer_pattern = re.compile(r"【(.*?)】")
        customer_match = customer_pattern.search(processed_query)
        if customer_match:
            return customer_match.group(1)
        
        # 5. 检查是否有"源端类型+源端"的格式，如"家宽IP-172.34.5.44"
        source_type_source_pattern = re.compile(r"([^-]+)-(.*?)(?=流出|流入|流向|$)")
        source_type_source_match = source_type_source_pattern.search(processed_query)
        if source_type_source_match:
            return source_type_source_match.group(2).strip()
        
        # 6. 检查是否有客户/账号相关关键词
        customer_keywords = ["客户", "终端用户", "家宽账号", "企宽账号", "宽带账号", "账号", "用户", "用户名"]
        for keyword in customer_keywords:
            if keyword in processed_query:
                # 提取包含该关键词的短语
                customer_pattern = re.compile(r"(.*?" + keyword + ".*?)(?=流出|流入|流向|$|\s+的|\s+下)")
                customer_match = customer_pattern.search(processed_query)
                if customer_match:
                    return customer_match.group(1).strip()
        
        # 7. 特殊处理：如"徐州云游四海这个客户下22个下行端口流量详情"
        if "下" in processed_query and any(kw in processed_query for kw in ["客户", "账号"]):
            # 提取"下"前面的内容作为源端
            before_down = processed_query.split("下")[0].strip()
            if before_down and before_down not in ["流入", "流出", "流向", "到", "流出到", "流入到", "流速", "流量", "统计", "分析"]:
                return before_down
        
        # 7. 提取查询中的名词短语作为源端，排除纯时间、纯数字和纯时间单位的情况
        # 首先移除时间范围
        time_range = self._extract_time_range(query, query_lower)
        if time_range:
            processed_query = processed_query.replace(time_range, "").strip()
        
        # 然后移除时间粒度
        time_granularity = self._extract_time_granularity(query_lower)
        for granularity_keyword in self.time_granularity_keywords.get(time_granularity, []):
            if granularity_keyword in processed_query:
                processed_query = processed_query.replace(granularity_keyword, "").strip()
        
        # 移除流向关键词
        for direction_keywords_list in self.direction_keywords.values():
            for keyword in direction_keywords_list:
                if keyword in processed_query:
                    processed_query = processed_query.replace(keyword, "").strip()
        
        # 移除数据类型关键词
        for data_type_keywords_list in self.data_type_keywords.values():
            for keyword in data_type_keywords_list:
                if keyword in processed_query:
                    processed_query = processed_query.replace(keyword, "").strip()
        
        # 移除上行下行关键词
        for up_down_keywords_list in self.up_down_keywords.values():
            for keyword in up_down_keywords_list:
                if keyword in processed_query:
                    processed_query = processed_query.replace(keyword, "").strip()
        
        # 移除流速相关关键词
        flow_rate_keywords = ["流速", "流量", "统计", "分析"]
        for keyword in flow_rate_keywords:
            if keyword in processed_query:
                processed_query = processed_query.replace(keyword, "").strip()
        
        if processed_query and processed_query not in ["流入", "流出", "流向", "到", "流出到", "流入到", "流速", "流量", "统计", "分析"]:
            return processed_query
        
        # 8. 从历史中获取源端
        for item in history:
            if isinstance(item, dict) and "intermediate_result" in item:
                ir = item["intermediate_result"]
                # 优先从新的attributes结构中获取
                if "attributes" in ir and ir["attributes"].get("源端"):
                    return str(ir["attributes"]["源端"])
                # 兼容旧的source字段
                elif "source" in ir and ir["source"]:
                    return str(ir["source"])
        
        # 9. 默认返回空
        return ""
    

    
    def _extract_destination_end(self, query: str, query_lower: str, history: List[dict]) -> str:
        """提取对端"""
        # 1. 检查是否有明确的对端信息在补充回答中
        for item in history:
            if isinstance(item, str) and "对端是" in item:
                # 从补充回答中提取对端信息
                end_part = item.split("对端是")[-1].strip()
                if end_part:
                    return end_part
        
        # 2. 检查是否为时间范围查询，如果是则不提取对端
        time_patterns = [
            r"(从\s*.*?\s*到\s*.*?)(?=流量|统计|分析|数据|$)",
            r"(\d{4}\.\d{1,2}\.\d{1,2}\s*到\s*\d{4}\.\d{1,2}\.\d{1,2})",
            r"(\d{4}-\d{1,2}-\d{1,2}\s*到\s*\d{4}-\d{1,2}-\d{1,2})",
            r"(\d{1,2}月\d{1,2}日\s*到\s*\d{1,2}月\d{1,2}日)"
        ]
        # 检查是否包含时间范围
        has_time_range = False
        for pattern in time_patterns:
            time_match = re.search(pattern, query)
            if time_match:
                has_time_range = True
                break
        
        # 3. 提取"到"、"流向"、"流出到"、"流入到"等关键词后的内容
        direction_markers = ["流出到", "流入到", "流向", "到"]
        for marker in direction_markers:
            if marker in query:
                parts = query.split(marker)
                if len(parts) >= 2:
                    destination = parts[1].strip()
                    
                    # 检查是否为日期范围，如果是则不提取作为对端
                    date_patterns = [
                        r"^\d+\.\d+\.\d+$|^\d{4}-\d{2}-\d{2}$",
                        r"^\d{1,2}月\d{1,2}日",
                        r"^\d{1,2}日\s*账号",
                        r"^\d{1,2}日\s*的"  # 处理"30日的"格式
                    ]
                    
                    is_date = any(re.match(pattern, destination) for pattern in date_patterns)
                    
                    if is_date or has_time_range:
                        return ""
                        
                    # 去除后续的修饰词和条件
                    destination = re.split(r"[,，。！？]|\s+流量|\s+统计|\s+分析|\s+数据|\s+且|\s+并|\s+剔除|\s+按|\s+要求|\s+流速|\s+流量值|\s+均值|\s+峰值", destination)[0].strip()
                    if destination and destination not in ["流入", "流出", "流量", "统计", "分析", "数据", "且", "并", "剔除", "按", "要求", "到", "流向", "流出到", "流入到", "流速", "流量值", "均值", "峰值"]:
                        return destination
        
        # 4. 检查是否有明确的流向关键词，如"流出到外省"中的"外省"
        if any(keyword in query_lower for keyword in ["流入", "流出", "双向"]):
            # 检查是否有多个省内/省外/省际等关键词，如"省外流出，省内流出，省外流入，省内流入"
            province_keywords = ["省外", "省内", "省际", "跨省", "外省", "本省"]
            matched_provinces = [keyword for keyword in province_keywords if keyword in query_lower]
            if matched_provinces and len(matched_provinces) > 1:
                return f"[{', '.join(matched_provinces)}]"
            elif matched_provinces:
                return matched_provinces[0]
            # 检查是否有运营商关键词
            operator_keywords = ["联通", "电信", "移动"]
            operator_matches = [keyword for keyword in operator_keywords if keyword in query_lower]
            if operator_matches:
                return operator_matches[0]
        
        # 5. 检查是否有"流入"或"流出"关键词后的地域信息
        flow_geo_pattern = re.compile(r"(流入|流出)(.*?)(?=流量|统计|分析|数据|$)")
        flow_geo_match = flow_geo_pattern.search(query)
        if flow_geo_match:
            geo_info = flow_geo_match.group(2).strip()
            if geo_info and geo_info not in ["流入", "流出", "流量", "统计", "分析", "数据", "到", "流向", "流出到", "流入到", "流速", "流量值", "均值", "峰值"]:
                return geo_info
        
        # 6. 检查是否有"从...到..."的格式，排除时间范围
        from_to_pattern = re.compile(r"从(.*?)到(.*?)(?=流量|统计|分析|数据|$)")
        from_to_match = from_to_pattern.search(query)
        if from_to_match:
            destination = from_to_match.group(2).strip()
            # 检查是否为日期，如果是则不提取作为对端
            if re.match(r"^\d+\.\d+\.\d+$|^\d{4}-\d{2}-\d{2}$", destination):
                return ""
            if destination and destination not in ["流入", "流出", "流量", "统计", "分析", "数据", "到", "流向", "流出到", "流入到", "流速", "流量值", "均值", "峰值"]:
                return destination
        
        # 7. 从历史中获取对端
        for item in history:
            if isinstance(item, dict) and "intermediate_result" in item:
                ir = item["intermediate_result"]
                # 优先从新的attributes结构中获取
                if "attributes" in ir and ir["attributes"].get("对端"):
                    dest = ir["attributes"]["对端"]
                    if isinstance(dest, list):
                        dest = " ".join([str(d) for d in dest if d])
                    return str(dest)
                # 兼容旧的destination字段
                elif "destination" in ir and ir["destination"]:
                    dest = ir["destination"]
                    if isinstance(dest, list):
                        dest = " ".join([str(d) for d in dest if d])
                    return str(dest)
        
        # 8. 检查查询中是否有"对端"相关词汇
        if "对端" in query_lower:
            # 提取"对端"后的内容
            end_part = query_lower.split("对端")[-1].strip()
            # 去除"是"、"为"等词
            if end_part.startswith("是"):
                end_part = end_part[1:].strip()
            elif end_part.startswith("为"):
                end_part = end_part[1:].strip()
            # 去除后续的修饰词
            end_part = re.split(r"[,，。！？]|\s+流量|\s+统计|\s+分析|\s+数据", end_part)[0].strip()
            if end_part:
                return end_part
        
        # 9. 检查是否有明确的对端关键词
        end_keywords = ["相关网络", "网络", "相关系统", "系统", "相关设备", "设备"]
        for keyword in end_keywords:
            if keyword in query_lower:
                return keyword
        
        # 10. 检查是否为简短的地理位置描述（如用户直接输入"省外"、"江苏"、"南京"等）
        cleaned_query = query.strip()
        if 2 <= len(cleaned_query) <= 4 and not any(char.isdigit() for char in cleaned_query):
            # 检查是否包含常见的地理位置关键词
            geo_indicators = ["省", "市", "区", "县", "外", "内", "际", "国", "海"]
            # 检查是否为具体的省份名称
            province_names = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏", "浙江", 
                            "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西", "海南", "重庆", 
                            "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆", "台湾", "香港", "澳门"]
            # 检查是否为具体的地市名称
            city_names = ["南京", "杭州", "苏州", "无锡", "常州", "镇江", "扬州", "南通", "泰州", "徐州", "淮安", "盐城", 
                         "连云港", "宿迁", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山", "台州", "丽水",
                         "合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州",
                         "六安", "亳州", "池州", "宣城", "福州", "厦门", "莆田", "三明", "泉州", "漳州", "南平", "龙岩",
                         "宁德", "南昌", "景德镇", "萍乡", "九江", "新余", "鹰潭", "赣州", "吉安", "宜春", "抚州", "上饶",
                         "济南", "青岛", "淄博", "枣庄", "东营", "烟台", "潍坊", "济宁", "泰安", "威海", "日照", "临沂",
                         "德州", "聊城", "滨州", "菏泽", "郑州", "开封", "洛阳", "平顶山", "安阳", "鹤壁", "新乡", "焦作",
                         "濮阳", "许昌", "漯河", "三门峡", "南阳", "商丘", "信阳", "周口", "驻马店", "武汉", "黄石", "十堰",
                         "宜昌", "襄阳", "鄂州", "荆门", "孝感", "荆州", "黄冈", "咸宁", "随州", "恩施", "长沙", "株洲",
                         "湘潭", "衡阳", "邵阳", "岳阳", "常德", "张家界", "益阳", "郴州", "永州", "怀化", "娄底", "湘西",
                         "广州", "韶关", "深圳", "珠海", "汕头", "佛山", "江门", "湛江", "茂名", "肇庆", "惠州", "梅州",
                         "汕尾", "河源", "阳江", "清远", "东莞", "中山", "潮州", "揭阳", "云浮", "南宁", "柳州", "桂林",
                         "梧州", "北海", "防城港", "钦州", "贵港", "玉林", "百色", "贺州", "河池", "来宾", "崇左", "海口",
                         "三亚", "成都", "自贡", "攀枝花", "泸州", "德阳", "绵阳", "广元", "遂宁", "内江", "乐山", "南充",
                         "眉山", "宜宾", "广安", "达州", "雅安", "巴中", "资阳", "贵阳", "六盘水", "遵义", "安顺", "毕节",
                         "铜仁", "昆明", "曲靖", "玉溪", "保山", "昭通", "丽江", "普洱", "临沧", "拉萨", "日喀则", "昌都",
                         "林芝", "山南", "那曲", "西安", "铜川", "宝鸡", "咸阳", "渭南", "延安", "汉中", "榆林", "安康",
                         "商洛", "兰州", "嘉峪关", "金昌", "白银", "天水", "武威", "张掖", "平凉", "酒泉", "庆阳", "定西",
                         "陇南", "西宁", "银川", "石嘴山", "吴忠", "固原", "中卫", "乌鲁木齐", "克拉玛依", "吐鲁番", "哈密"]
            
            if (any(indicator in cleaned_query for indicator in geo_indicators) or 
                any(province == cleaned_query for province in province_names) or
                any(city == cleaned_query for city in city_names)):
                return cleaned_query
        
        # 11. 默认返回空
        return ""
    
    def _extract_time_range(self, query: str, query_lower: str) -> str:
        """提取时间范围"""
        # 0. 优先匹配短横线格式，如"3-9号"、"3-9"
        dash_range_pattern = re.compile(r"(\d{1,2}-\d{1,2}[号日]?|\d{1,2}月-\d{1,2}月)")
        dash_range_match = dash_range_pattern.search(query)
        if dash_range_match:
            range_text = dash_range_match.group(0).strip()
            # 标准化格式：将短横线转换为"到"，并确保格式完整
            range_text = range_text.replace("-", "到")
            # 确保格式完整：如"3到9号" → "3号到9号"
            if "号" not in range_text and "日" not in range_text:
                range_text = range_text.replace("到", "号到") + "号"
            # 特殊处理："3-9号" → "3号到9号"
            if "号" in range_text and "到" in range_text:
                parts = range_text.split("到")
                if len(parts) == 2:
                    start_part = parts[0]
                    end_part = parts[1]
                    if "号" not in start_part and "日" not in start_part:
                        start_part = start_part + "号"
                    range_text = start_part + "到" + end_part
            return range_text
        
        # 1. 优先匹配"X号到Y号"格式，如"3号到9号"
        day_range_pattern = re.compile(r"(\d{1,2}[号日]到\d{1,2}[号日])")
        day_range_match = day_range_pattern.search(query)
        if day_range_match:
            return day_range_match.group(0).strip()
        
        # 2. 优先匹配"X月X日到X月X日"格式，如"3月10日到30日"
        month_day_range_pattern = re.compile(r"(\d{1,2}月\d{1,2}日到\d{1,2}月\d{1,2}日|\d{1,2}月\d{1,2}日到\d{1,2}日)")
        month_day_range_match = month_day_range_pattern.search(query)
        if month_day_range_match:
            range_text = month_day_range_match.group(0).strip()
            # 检查月份信息是否完整，如果不完整则补充
            if "月" in range_text.split("到")[0] and "月" not in range_text.split("到")[1]:
                # 补充月份信息，如"3月10日到30日" → "3月10日到3月30日"
                start_month = range_text.split("月")[0] + "月"
                end_part = range_text.split("到")[1]
                if not end_part.startswith(start_month):
                    range_text = range_text.replace("到" + end_part, "到" + start_month + end_part)
            return range_text
        
        # 2.1 处理"X月X日到Y日"格式，如"3月10日到30日"
        month_day_to_day_pattern = re.compile(r"(\d{1,2}月\d{1,2}日到\d{1,2}日)")
        month_day_to_day_match = month_day_to_day_pattern.search(query)
        if month_day_to_day_match:
            range_text = month_day_to_day_match.group(0).strip()
            # 补充月份信息，如"3月10日到30日" → "3月10日到3月30日"
            start_month = range_text.split("月")[0] + "月"
            end_part = range_text.split("到")[1]
            if not end_part.startswith(start_month):
                range_text = range_text.replace("到" + end_part, "到" + start_month + end_part)
            return range_text
        
        # 3. 优先匹配"X月到Y月"格式，如"3月到5月"
        month_range_pattern = re.compile(r"(\d{1,2}月到\d{1,2}月)")
        month_range_match = month_range_pattern.search(query)
        if month_range_match:
            return month_range_match.group(0).strip()
        
        # 4. 优先匹配"X号至Y号"格式，如"3号至9号"
        day_to_pattern = re.compile(r"(\d{1,2}[号日]至\d{1,2}[号日])")
        day_to_match = day_to_pattern.search(query)
        if day_to_match:
            range_text = day_to_match.group(0).strip()
            # 标准化格式：将"至"转换为"到"
            range_text = range_text.replace("至", "到")
            return range_text
        
        # 5. 处理"X到Y号"格式，如"3到9号"
        day_to_day_pattern = re.compile(r"(\d{1,2}到\d{1,2}[号日])")
        day_to_day_match = day_to_day_pattern.search(query)
        if day_to_day_match:
            range_text = day_to_day_match.group(0).strip()
            # 标准化格式："3到9号" → "3号到9号"
            range_text = range_text.replace("到", "号到")
            return range_text
        
        # 6. 处理相对时间表达，如"最近一周"、"过去两个月"
        relative_time_patterns = [
            (r"最近\s*(\d+|一|两|几)\s*(天|周|星期|月|年)", "最近{0}{1}"),
            (r"过去\s*(\d+|一|两|几)\s*(天|周|星期|月|年)", "过去{0}{1}"),
            (r"上(周|月|季度|年)", "上{0}"),
            (r"本(周|月|季度|年)", "本{0}"),
            (r"这(周|月|季度|年)", "这{0}"),
            (r"近(\d+|一|两|几)\s*(天|周|星期|月|年)", "近{0}{1}"),  # 保持原始：近一星期 → 近一星期
        ]
        
        for pattern, template in relative_time_patterns:
            relative_match = re.search(pattern, query)
            if relative_match:
                groups = relative_match.groups()
                if len(groups) == 1:
                    return template.format(groups[0])
                elif len(groups) == 2:
                    return template.format(groups[0], groups[1])
        
        # 7. 处理"从...到..."的复杂时间范围，如"从上周三到这周三"
        from_to_complex_pattern = re.compile(r"(从\s*[上下本这]?[周月季年]?[一二三四五六日天]?到[上下本这]?[周月季年]?[一二三四五六日天])")
        from_to_complex_match = from_to_complex_pattern.search(query)
        if from_to_complex_match:
            return from_to_complex_match.group(0).strip()
        
        # 7.1 更精确的复杂时间范围匹配
        complex_time_patterns = [
            (r"从上周三到这周三", "上周三到这周三"),
            (r"从上周三到本周三", "上周三到本周三"),
            (r"从上周三到周三", "上周三到周三"),
            (r"从上周一到这周五", "上周一到这周五"),
            (r"从上周一到周五", "上周一到周五"),
            (r"从上周一到本周五", "上周一到本周五"),
        ]
        
        for pattern, replacement in complex_time_patterns:
            if re.search(pattern, query):
                return replacement
        
        # 8. 处理常见相对时间短语
        common_relative_patterns = [
            (r"最近一周", "最近一周"),
            (r"最近一星期", "最近一星期"),
            (r"近一周", "近一周"),
            (r"近一星期", "近一星期"),
            (r"最近一个月", "最近一个月"),
            (r"最近三个月", "最近三个月"),
            (r"过去一周", "过去一周"),
            (r"过去一星期", "过去一星期"),
            (r"过去一个月", "过去一个月"),
            (r"过去三个月", "过去三个月"),
        ]
        
        for pattern, replacement in common_relative_patterns:
            if re.search(pattern, query_lower):
                return replacement
        
        # 9. 处理简单的日期格式，如"4号"、"3月"等（降低优先级）
        simple_date_pattern = re.compile(r"(\d{1,2}[号日]|\d{1,2}月)")
        simple_date_match = simple_date_pattern.search(query)
        if simple_date_match:
            return simple_date_match.group(0).strip()
        
        # 10. 优先匹配完整的时间范围格式，如"2025.10.1到2025.11.29"
        complete_time_pattern = re.compile(r"(\d{4}\.\d{1,2}\.\d{1,2}\s*到\s*\d{4}\.\d{1,2}\.\d{1,2})")
        complete_time_match = complete_time_pattern.search(query)
        if complete_time_match:
            time_range = complete_time_match.group(0).strip()
            # 标准化日期格式，将.转换为-
            time_range = re.sub(r"(\d+)\.(\d+)\.(\d+)", r"\1-\2-\3", time_range)
            return time_range
        
        # 11. 匹配简写年份格式，如"25年3月到4月"
        short_year_pattern = re.compile(r"(\d{2})年(\d{1,2}月)到(\d{1,2}月)")
        short_year_match = short_year_pattern.search(query)
        if short_year_match:
            year = short_year_match.group(1)
            start_month = short_year_match.group(2)
            end_month = short_year_match.group(3)
            return f"20{year}年{start_month}到20{year}年{end_month}"
        
        # 12. 匹配完整的"从...到..."格式
        from_to_pattern = re.compile(r"(从\s*\d{4}\.\d{1,2}\.\d{1,2}\s*到\s*\d{4}\.\d{1,2}\.\d{1,2})")
        from_to_match = from_to_pattern.search(query)
        if from_to_match:
            time_range = from_to_match.group(0).strip()
            time_range = re.sub(r"(\d+)\.(\d+)\.(\d+)", r"\1-\2-\3", time_range)
            return time_range
        
        # 13. 匹配常见时间短语，如"过去两个月"、"近三个月"、"最近一个月"等
        common_time_pattern = re.compile(r"(过去\d+[个两]?月|过去\d+天|过去\d+小时|近\d+[个两]?月|近\d+天|近\d+小时|最近\d+[个两]?月|最近\d+天|最近\d+小时|前\d+[个两]?月|前\d+天|前\d+小时)")
        common_time_match = common_time_pattern.search(query_lower)
        if common_time_match:
            time_text = common_time_match.group(0).strip()
            # 标准化：近三个月 → 最近三个月
            if time_text.startswith("近"):
                time_text = "最近" + time_text[1:]
            return time_text
        
        # 14. 特殊处理常见时间短语
        special_time_phrases = ["过去两个月", "近两个月", "最近两个月", "过去三个月", "近三个月", "最近三个月"]
        for phrase in special_time_phrases:
            if phrase in query_lower:
                # 标准化：近三个月 → 最近三个月
                if phrase.startswith("近"):
                    return "最近" + phrase[1:]
                return phrase
        
        # 15. 匹配季度格式，如"第三季度"
        quarter_pattern = re.compile(r"(第\d+季度)")
        quarter_match = quarter_pattern.search(query)
        if quarter_match:
            return quarter_match.group(0)
        
        # 16. 使用正则表达式匹配各种时间格式
        time_match = self.time_pattern.search(query)
        if time_match:
            time_range = time_match.group(0).strip()
            # 标准化日期格式，将.转换为-
            time_range = re.sub(r"(\d+)\.(\d+)\.(\d+)", r"\1-\2-\3", time_range)
            return time_range
        
        # 17. 检查是否有明确的时间短语，如"上月"、"本月"等
        time_phrases = [
            r"(上月|本月|第三季度|第二季度|第一季度|今年|去年|前年|本周|上周|下周|昨天|今天|明天)(\s+.*?)?(?=流量|统计|分析|数据|$)"
        ]
        for pattern in time_phrases:
            time_match = re.search(pattern, query)
            if time_match:
                return time_match.group(0).strip()
        
        # 18. 默认返回空
        return ""
    
    def _extract_source_type(self, source: str, query_lower: str) -> str:
        """提取源端类型"""
        if not source:
            return ""
        
        # 1. 检查源端是否为地市、省份、国际、全国等相关
        # 按照框架规则：如果源端是地市/省份/国际等，默认源端业务类型是IDC+MAN
        location_keywords = ["地市", "各地市", "省份", "省", "市", "地区", "省内", "省外", "省际", "跨省", "外省", "本省", 
                           "国际", "海外", "全国", "全网", "各地", "全国各省", "全国地市", "as", "AS", "地市路由"]
        province_names = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏", "浙江", 
                        "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西", "海南", "重庆", 
                        "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆", "台湾", "香港", "澳门"]
        
        if any(keyword in source for keyword in location_keywords) or any(province in source for province in province_names):
            return "IDC+MAN"
        
        # 2. 检查是否有明确的类型说明，如"浙江各地市idc"中的"idc"
        # 按照场景分类框架：如果明确提到IDC或MAN，则返回相应类型
        if "idc" in query_lower or "IDC" in query_lower:
            return "IDC"
        elif "man" in query_lower or "MAN" in query_lower or "城域网" in query_lower:
            return "MAN"
        
        # 3. 检查是否有"源端类型+源端"的格式，如"家宽IP-172.34.5.44"
        source_type_pattern = re.compile(r"([^-]+)-(.*?)(?=流出|流入|流向|$)")
        source_type_match = source_type_pattern.search(query_lower)
        if source_type_match:
            source_type = source_type_match.group(1).strip()
            if "idc" in source_type.lower():
                return "IDC"
            elif "man" in source_type.lower() or "城域网" in source_type.lower():
                return "MAN"
        
        # 4. 按照框架规则：如果是客户/IP相关对象，默认留空
        customer_keywords = ["客户", "账号", "用户", "家宽", "企宽", "宽带"]
        if any(keyword in query_lower for keyword in customer_keywords):
            return ""
        
        # 5. 检查是否为结算详情数据
        if "结算" in query_lower or "结算详情" in query_lower:
            return "IDC+MAN"
        
        # 6. 默认返回空
        return ""
    
    def _extract_destination_type(self, destination: str, query_lower: str) -> str:
        """提取对端类型"""
        if not destination:
            return ""
        
        # 1. 检查对端是否为地市、省份、国际、全国等相关
        # 按照框架规则：如果对端是地市/省份/国际等，默认对端业务类型是IDC+MAN
        location_keywords = ["地市", "各地市", "省份", "省", "市", "地区", "省内", "省外", "省际", "跨省", "外省", "本省", 
                           "国际", "海外", "全国", "全网", "各地", "全国各省", "全国地市", "as", "AS", "地市路由"]
        province_names = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏", "浙江", 
                        "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西", "海南", "重庆", 
                        "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆", "台湾", "香港", "澳门"]
        city_names = ["南京", "杭州", "苏州", "无锡", "常州", "镇江", "扬州", "南通", "泰州", "徐州", "淮安", "盐城", 
                     "连云港", "宿迁", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山", "台州", "丽水",
                     "合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州",
                     "六安", "亳州", "池州", "宣城", "福州", "厦门", "莆田", "三明", "泉州", "漳州", "南平", "龙岩",
                     "宁德", "南昌", "景德镇", "萍乡", "九江", "新余", "鹰潭", "赣州", "吉安", "宜春", "抚州", "上饶",
                     "济南", "青岛", "淄博", "枣庄", "东营", "烟台", "潍坊", "济宁", "泰安", "威海", "日照", "临沂",
                     "德州", "聊城", "滨州", "菏泽", "郑州", "开封", "洛阳", "平顶山", "安阳", "鹤壁", "新乡", "焦作",
                     "濮阳", "许昌", "漯河", "三门峡", "南阳", "商丘", "信阳", "周口", "驻马店", "武汉", "黄石", "十堰",
                     "宜昌", "襄阳", "鄂州", "荆门", "孝感", "荆州", "黄冈", "咸宁", "随州", "恩施", "长沙", "株洲",
                     "湘潭", "衡阳", "邵阳", "岳阳", "常德", "张家界", "益阳", "郴州", "永州", "怀化", "娄底", "湘西",
                     "广州", "韶关", "深圳", "珠海", "汕头", "佛山", "江门", "湛江", "茂名", "肇庆", "惠州", "梅州",
                     "汕尾", "河源", "阳江", "清远", "东莞", "中山", "潮州", "揭阳", "云浮", "南宁", "柳州", "桂林",
                     "梧州", "北海", "防城港", "钦州", "贵港", "玉林", "百色", "贺州", "河池", "来宾", "崇左", "海口",
                     "三亚", "成都", "自贡", "攀枝花", "泸州", "德阳", "绵阳", "广元", "遂宁", "内江", "乐山", "南充",
                     "眉山", "宜宾", "广安", "达州", "雅安", "巴中", "资阳", "贵阳", "六盘水", "遵义", "安顺", "毕节",
                     "铜仁", "昆明", "曲靖", "玉溪", "保山", "昭通", "丽江", "普洱", "临沧", "拉萨", "日喀则", "昌都",
                     "林芝", "山南", "那曲", "西安", "铜川", "宝鸡", "咸阳", "渭南", "延安", "汉中", "榆林", "安康",
                     "商洛", "兰州", "嘉峪关", "金昌", "白银", "天水", "武威", "张掖", "平凉", "酒泉", "庆阳", "定西",
                     "陇南", "西宁", "银川", "石嘴山", "吴忠", "固原", "中卫", "乌鲁木齐", "克拉玛依", "吐鲁番", "哈密"]
        
        if (any(keyword in destination for keyword in location_keywords) or 
            any(province in destination for province in province_names) or
            any(city in destination for city in city_names)):
            return "IDC+MAN"
        
        # 2. 检查是否有明确的类型说明，如"浙江各地市idc"中的"idc"
        # 按照场景分类框架：如果明确提到IDC或MAN，则返回相应类型
        if "idc" in query_lower or "IDC" in query_lower:
            return "IDC"
        elif "man" in query_lower or "MAN" in query_lower or "城域网" in query_lower:
            return "MAN"
        
        # 3. 检查对端是否包含运营商关键词
        operator_keywords = ["联通", "电信", "移动"]
        if any(keyword in destination for keyword in operator_keywords):
            return "IDC+MAN"  # 运营商按框架规则属于IDC+MAN
        
        # 4. 检查是否为结算详情数据
        if "结算" in query_lower or "结算详情" in query_lower:
            return "IDC+MAN"
        
        # 5. 按照框架规则：如果是客户/IP相关对象，默认留空
        customer_keywords = ["客户", "账号", "用户", "家宽", "企宽", "宽带"]
        if any(keyword in query_lower for keyword in customer_keywords):
            return ""
        
        # 6. 默认返回空
        return ""
    
    def _extract_time_granularity(self, query_lower: str) -> str:
        """提取时间粒度"""
        # 1. 检查关键词
        for granularity, keywords in self.time_granularity_keywords.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return granularity
        
        # 2. 默认逐时
        return "逐时"
    
    def _extract_flow_direction(self, query_lower: str) -> str:
        """提取流向"""
        # 1. 检查关键词
        for direction, keywords in self.direction_keywords.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return direction
        
        # 2. 默认流出
        return "流出"
    
    def _extract_data_type(self, query_lower: str) -> str:
        """提取数据类型"""
        # 1. 检查关键词
        for data_type, keywords in self.data_type_keywords.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return data_type
        
        # 2. 默认流量均值
        return "流量均值"
    
    def _extract_exclusion_conditions(self, query_lower: str) -> List[str]:
        """提取剔除条件"""
        exclusion_conditions = []
        
        # 检查"剔除"或"排除"关键字
        exclusion_keywords = ["剔除", "排除", "除了", "不含"]
        for keyword in exclusion_keywords:
            if keyword in query_lower:
                idx = query_lower.index(keyword)
                # 提取后续内容，直到遇到标点、流量关键词或结束
                exclusion_part = query_lower[idx+len(keyword):]
                # 分割多个剔除条件
                # 停止条件：遇到标点、流量相关关键词或其他条件关键词
                stop_pattern = r"[,，。！？]|\s+流量|\s+统计|\s+分析|\s+数据|\s+且|\s+并|\s+按|\s+要求"
                # 只提取第一个停止条件之前的内容
                exclusion_part = re.split(stop_pattern, exclusion_part)[0].strip()
                if exclusion_part:
                    # 分割多个剔除条件，使用和、或、顿号等分隔符
                    conditions = re.split(r"和|或|、|，", exclusion_part)
                    for cond in conditions:
                        cond = cond.strip()
                        if cond:
                            # 去除条件中的"了"、"的"等助词
                            cond = re.sub(r"[了的]", "", cond)
                            exclusion_conditions.append(cond)
                break
        
        return exclusion_conditions
    
    def _extract_fuzzy_matching(self, query_lower: str) -> bool:
        """提取模糊匹配标志"""
        return "模糊匹配" in query_lower
    
    def _extract_up_down(self, query_lower: str) -> str:
        """提取上行下行"""
        # 1. 检查关键词
        for up_down, keywords in self.up_down_keywords.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return up_down
        
        # 2. 默认上行
        return "上行"
    
    def _extract_supplementary_info(self, query: str) -> str:
        """提取补充信息"""
        supplementary_info = []
        query_lower = query.lower()
        
        # 检查排名要求
        rank_pattern = re.compile(r"(top\d+|前\d+|top\d+ip|top\d+客户|top\d+账号)", re.IGNORECASE)
        rank_match = rank_pattern.search(query)
        if rank_match:
            supplementary_info.append(rank_match.group(0).upper())
        
        # 检查特殊输出要求
        output_keywords = ["清单", "报表汇总", "详情数据", "明细数据", "汇总", "分布", "报表", "详情", "清单"]
        for keyword in output_keywords:
            if keyword in query_lower:
                supplementary_info.append(keyword)
                break
        
        # 检查特殊细分要求
        breakdown_keywords = ["细化", "细分", "区分", "分别统计"]
        for keyword in breakdown_keywords:
            if keyword in query_lower:
                supplementary_info.append(keyword)
                break
        
        # 检查特殊处理说明
        special_keywords = ["最新的ip+username", "对应拉流客户名称", "对应的cdntype", "对应的拉流ip", "经过的cr路由器", "下行端口及其流出流量"]
        for keyword in special_keywords:
            if keyword in query_lower:
                supplementary_info.append(keyword)
        
        # 检查特殊场景
        special_scenarios = {
            "3a查询": ["3a查询", "最新的ip+username"],
            "PCDN查询": ["pcdn", "域名"],
            "拉流查询": ["拉流", "被拉流"]
        }
        for scenario, keywords in special_scenarios.items():
            if any(keyword in query_lower for keyword in keywords):
                supplementary_info.append(scenario)
        
        return ",".join(supplementary_info)

    def smart_merge_attributes(self, existing_attributes: Dict[str, Any], user_input: str, history: List[dict] = None) -> Dict[str, Any]:
        """智能合并属性：只更新用户补充的属性，保留已有属性
        
        Args:
            existing_attributes: 已有的属性字典
            user_input: 用户补充的输入
            history: 历史对话记录
            
        Returns:
            智能合并后的属性字典
        """
        if history is None:
            history = []
            
        # 1. 智能识别用户补充的属性类型
        merged_attributes = existing_attributes.copy()
        
        # 2. 分析历史对话，确定系统要求补充的属性
        requested_attributes = self._get_requested_attributes_from_history(history)
        
        # 3. 根据用户输入内容，智能判断补充的属性类型
        supplemented_attributes = self._identify_supplemented_attributes(user_input, history)
        
        # 4. 只更新用户明确补充的属性
        for key in supplemented_attributes:
            # 从用户输入中提取该属性的值
            if key == "时间":
                value = self._extract_time_range(user_input, user_input.lower())
            elif key == "源端":
                value = self._extract_source_end(user_input, user_input.lower(), history)
            elif key == "对端":
                value = self._extract_destination_end(user_input, user_input.lower(), history)
            elif key == "时间粒度":
                value = self._extract_time_granularity(user_input.lower())
            elif key == "剔除条件":
                value = self._extract_exclusion_conditions(user_input.lower())
            else:
                # 对于其他属性，使用完整的提取方法
                temp_attrs = self.extract_attributes(user_input, history)
                value = temp_attrs.get(key, "")
            
            # 只有当提取到有效值时才更新
            if value and value != existing_attributes.get(key, ""):
                # 特殊处理列表类型的属性（如剔除条件）
                if key == "剔除条件" and isinstance(value, list):
                    existing_conditions = existing_attributes.get("剔除条件", [])
                    merged_conditions = list(set(existing_conditions + value))
                    merged_attributes[key] = merged_conditions
                else:
                    merged_attributes[key] = value
                    
                    # 特殊处理：当源端被更新时，自动设置源端类型
                    if key == "源端" and value:
                        source_type = self._extract_source_type(value, user_input.lower())
                        if source_type:
                            merged_attributes["源端类型"] = source_type
                    
                    # 特殊处理：当对端被更新时，自动设置对端类型
                    if key == "对端" and value:
                        destination_type = self._extract_destination_type(value, user_input.lower())
                        if destination_type:
                            merged_attributes["对端类型"] = destination_type
        
        return merged_attributes
    
    def _is_explicit_supplement(self, key: str, new_value: str, user_input: str, history: List[dict]) -> bool:
        """判断是否是用户明确补充的属性"""
        # 检查历史对话中是否有系统请求该属性的记录
        for item in reversed(history):
            if isinstance(item, dict) and "analysis_result" in item:
                prompt = item.get("analysis_result", "")
                # 如果系统提示中包含该属性的关键词，说明用户是在补充
                if key == "时间" and any(word in prompt for word in ["时间", "月份", "年份", "日期"]):
                    return True
                if key == "源端" and any(word in prompt for word in ["源端", "源", "来源"]):
                    return True
                if key == "对端" and any(word in prompt for word in ["对端", "目标", "目的地"]):
                    return True
        
        # 如果用户输入很短且明确，也认为是补充
        if len(user_input.strip()) <= 10 and new_value:
            return True
            
        return False
    
    def _contains_time_info(self, user_input: str) -> bool:
        """检查用户输入是否包含时间信息"""
        time_patterns = [
            r"\d{1,2}[月月]",
            r"\d{1,2}[号日]",
            r"\d{4}[年]",
            r"第\d+季度",
            r"近(\d+|一|两|几)",
            r"过去(\d+|一|两|几)",
            r"最近(\d+|一|两|几)",
            r"本月|上月|下月",
            r"本周|上周|下周",
            r"今天|昨天|明天",
            r"近一星期|近一周|最近一星期|最近一周"
        ]
        
        for pattern in time_patterns:
            if re.search(pattern, user_input):
                return True
        return False
    
    def _contains_source_info(self, user_input: str) -> bool:
        """检查用户输入是否包含源端信息"""
        source_keywords = ["源端", "源", "来源", "从", "由"]
        return any(keyword in user_input for keyword in source_keywords)
    
    def _get_requested_attributes_from_history(self, history: List[dict]) -> List[str]:
        """从历史对话中分析系统要求补充的属性"""
        requested_attributes = []
        
        for item in reversed(history):
            if isinstance(item, dict) and "analysis_result" in item:
                prompt = item.get("analysis_result", "")
                
                # 分析提示词，确定要求补充的属性
                if any(word in prompt for word in ["时间", "月份", "年份", "日期", "时间范围"]):
                    requested_attributes.append("时间")
                if any(word in prompt for word in ["源端", "源", "来源", "源端信息"]):
                    requested_attributes.append("源端")
                if any(word in prompt for word in ["对端", "目标", "目的地", "对端信息"]):
                    requested_attributes.append("对端")
                if any(word in prompt for word in ["时间粒度", "统计粒度", "按什么时间"]):
                    requested_attributes.append("时间粒度")
                if any(word in prompt for word in ["剔除", "排除", "过滤"]):
                    requested_attributes.append("剔除条件")
                
                # 如果找到了要求，就停止搜索更早的历史
                if requested_attributes:
                    break
        
        return list(set(requested_attributes))
    
    def _identify_supplemented_attributes(self, user_input: str, history: List[dict]) -> List[str]:
        """智能识别用户补充的属性类型"""
        supplemented_attributes = []
        
        # 1. 首先检查历史对话中系统要求补充的属性
        requested_attributes = self._get_requested_attributes_from_history(history)
        
        # 2. 检查用户输入是否包含对应属性的信息
        for attr in requested_attributes:
            if self._contains_attribute_info(attr, user_input):
                supplemented_attributes.append(attr)
        
        # 3. 如果没有明确的历史要求，根据内容智能判断
        if not supplemented_attributes:
            # 检查时间信息
            if self._contains_time_info(user_input):
                supplemented_attributes.append("时间")
            
            # 检查源端信息
            if self._contains_source_info(user_input):
                supplemented_attributes.append("源端")
            
            # 检查对端信息
            if self._contains_destination_info(user_input):
                supplemented_attributes.append("对端")
            
            # 检查时间粒度
            if self._contains_time_granularity_info(user_input):
                supplemented_attributes.append("时间粒度")
        
        return supplemented_attributes
    
    def _contains_attribute_info(self, attribute: str, user_input: str) -> bool:
        """检查用户输入是否包含特定属性的信息"""
        if attribute == "时间":
            return self._contains_time_info(user_input)
        elif attribute == "源端":
            return self._contains_source_info(user_input)
        elif attribute == "对端":
            return self._contains_destination_info(user_input)
        elif attribute == "时间粒度":
            return self._contains_time_granularity_info(user_input)
        elif attribute == "剔除条件":
            return any(word in user_input for word in ["剔除", "排除", "过滤", "去掉", "不要"])
        return False
    
    def _contains_time_granularity_info(self, user_input: str) -> bool:
        """检查用户输入是否包含时间粒度信息"""
        granularity_keywords = ["按月", "按天", "按小时", "逐时", "月均", "日均", "小时均"]
        return any(keyword in user_input for keyword in granularity_keywords)
    
    def _contains_time_info(self, user_input: str) -> bool:
        """检查用户输入是否包含时间信息"""
        time_patterns = [
            r"\d{1,2}[月月]",
            r"\d{1,2}[号日]",
            r"\d{4}[年]",
            r"第\d+季度",
            r"近(\d+|一|两|几)",
            r"过去(\d+|一|两|几)",
            r"最近(\d+|一|两|几)",
            r"本月|上月|下月",
            r"本周|上周|下周",
            r"今天|昨天|明天",
            r"近一星期|近一周|最近一星期|最近一周"
        ]
        
        for pattern in time_patterns:
            if re.search(pattern, user_input):
                return True
        return False
    
    def _contains_source_info(self, user_input: str) -> bool:
        """检查用户输入是否包含源端信息"""
        source_keywords = ["源端", "源", "来源", "从", "由"]
        return any(keyword in user_input for keyword in source_keywords)
    
    def _contains_destination_info(self, user_input: str) -> bool:
        """检查用户输入是否包含对端信息"""
        # 1. 检查方向性关键词
        destination_keywords = ["对端", "目标", "目的地", "到", "向"]
        if any(keyword in user_input for keyword in destination_keywords):
            return True
        
        # 2. 检查常见的地区/地域信息（如省外、省内、地市、省份等）
        region_keywords = ["省外", "省内", "地市", "省份", "省际", "各地市", "全国", "国际", "海外"]
        if any(keyword in user_input for keyword in region_keywords):
            return True
            
        # 3. 检查是否为简短的地理位置描述（通常1-4个字符）
        # 如"省外"、"省内"、"北京"、"上海"等
        cleaned_input = user_input.strip()
        if 2 <= len(cleaned_input) <= 4 and not any(char.isdigit() for char in cleaned_input):
            # 检查是否包含常见的地理位置关键词
            geo_indicators = ["省", "市", "区", "县", "外", "内", "际"]
            if any(indicator in cleaned_input for indicator in geo_indicators):
                return True
            
            # 4. 检查是否为具体的省份名称
            province_names = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏", "浙江", 
                            "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西", "海南", "重庆", 
                            "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆", "台湾", "香港", "澳门"]
            if any(province == cleaned_input for province in province_names):
                return True
            
            # 5. 检查是否为具体的城市名称
            city_names = ["南京", "杭州", "苏州", "无锡", "常州", "镇江", "扬州", "南通", "泰州", "徐州", "淮安", "盐城", 
                         "连云港", "宿迁", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山", "台州", "丽水",
                         "合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州",
                         "六安", "亳州", "池州", "宣城", "福州", "厦门", "莆田", "三明", "泉州", "漳州", "南平", "龙岩",
                         "宁德", "南昌", "景德镇", "萍乡", "九江", "新余", "鹰潭", "赣州", "吉安", "宜春", "抚州", "上饶",
                         "济南", "青岛", "淄博", "枣庄", "东营", "烟台", "潍坊", "济宁", "泰安", "威海", "日照", "临沂",
                         "德州", "聊城", "滨州", "菏泽", "郑州", "开封", "洛阳", "平顶山", "安阳", "鹤壁", "新乡", "焦作",
                         "濮阳", "许昌", "漯河", "三门峡", "南阳", "商丘", "信阳", "周口", "驻马店", "武汉", "黄石", "十堰",
                         "宜昌", "襄阳", "鄂州", "荆门", "孝感", "荆州", "黄冈", "咸宁", "随州", "恩施", "长沙", "株洲",
                         "湘潭", "衡阳", "邵阳", "岳阳", "常德", "张家界", "益阳", "郴州", "永州", "怀化", "娄底", "湘西",
                         "广州", "韶关", "深圳", "珠海", "汕头", "佛山", "江门", "湛江", "茂名", "肇庆", "惠州", "梅州",
                         "汕尾", "河源", "阳江", "清远", "东莞", "中山", "潮州", "揭阳", "云浮", "南宁", "柳州", "桂林",
                         "梧州", "北海", "防城港", "钦州", "贵港", "玉林", "百色", "贺州", "河池", "来宾", "崇左", "海口",
                         "三亚", "成都", "自贡", "攀枝花", "泸州", "德阳", "绵阳", "广元", "遂宁", "内江", "乐山", "南充",
                         "眉山", "宜宾", "广安", "达州", "雅安", "巴中", "资阳", "贵阳", "六盘水", "遵义", "安顺", "毕节",
                         "铜仁", "昆明", "曲靖", "玉溪", "保山", "昭通", "丽江", "普洱", "临沧", "拉萨", "日喀则", "昌都",
                         "林芝", "山南", "那曲", "西安", "铜川", "宝鸡", "咸阳", "渭南", "延安", "汉中", "榆林", "安康",
                         "商洛", "兰州", "嘉峪关", "金昌", "白银", "天水", "武威", "张掖", "平凉", "酒泉", "庆阳", "定西",
                         "陇南", "西宁", "银川", "石嘴山", "吴忠", "固原", "中卫", "乌鲁木齐", "克拉玛依", "吐鲁番", "哈密"]
            if any(city == cleaned_input for city in city_names):
                return True
        
        return False
    
    def _build_llm_chain(self, api_key: str, model_name: str):
        """构建LLM链用于智能时间信息提取"""
        if not LANGCHAIN_AVAILABLE:
            return None
            
        system_prompt = """你是一个专业的时间信息提取助手。请从用户查询中准确提取时间范围信息。

提取规则：
1. 优先提取明确的时间范围，如"3号到9号"、"3月10日到30日"
2. 处理相对时间，如"上周"、"过去两个月"、"最近一周"
3. 处理模糊时间，如"本月"、"今年"、"本季度"
4. 结合上下文理解时间范围
5. 如果用户输入中没有明确时间信息，返回空字符串

请严格按照以下JSON格式输出：
{
  "time_range": "提取的时间范围字符串",
  "confidence": 0.0-1.0之间的置信度,
  "reasoning": "提取依据和推理过程"
}

不要输出任何非JSON内容。"""
        
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            HumanMessagePromptTemplate.from_template("用户查询: {query}\n历史对话: {history}")
        ])
        
        llm = ChatTongyi(temperature=0, model_name=model_name, dashscope_api_key=api_key)
        return LLMChain(llm=llm, prompt=prompt)
    
    def _extract_time_with_llm(self, query: str, history: List[dict]) -> str:
        """使用LLM智能提取时间信息（兜底方案）"""
        if not self.llm_chain:
            return ""
        
        try:
            # 准备历史对话文本
            history_text = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" 
                for msg in history[-5:]  # 只使用最近5条历史记录
            ]) if history else "无历史对话"
            
            # 调用LLM
            result = self.llm_chain.run({
                "query": query,
                "history": history_text
            })
            
            # 解析JSON结果
            parsed_result = json.loads(result)
            time_range = parsed_result.get("time_range", "")
            confidence = parsed_result.get("confidence", 0.0)
            
            # 只有当置信度足够高时才使用LLM结果
            if confidence >= 0.7 and time_range:
                return time_range
            
        except Exception as e:
            # LLM调用失败时回退到规则方法
            pass
        
        return ""
    
    def _extract_time_range_enhanced(self, query: str, history: List[dict] = None) -> str:
        """增强的时间范围提取：规则优先 + LLM兜底"""
        if history is None:
            history = []
        
        # 1. 规则优先：使用正则表达式快速匹配常见格式
        rule_based_time = self._extract_time_range(query, query.lower())
        
        # 如果规则方法已经找到有效时间，直接返回
        if rule_based_time:
            return rule_based_time
        
        # 2. LLM兜底：处理复杂、模糊、相对时间表达
        llm_time = self._extract_time_with_llm(query, history)
        
        return llm_time

# 示例用法
if __name__ == "__main__":
    extractor = AttributeExtractor()
    
    # 测试用例
    test_queries = [
        "top20客户-终端用户流出流量占比详情",
        "查询浙江各地市idc省内流出流入的月均流量，剔除天翼云和天翼看家",
        "过去两个月，外省城域网流入到浙江各地市IDC且剔除天翼云的月均流量",
        "查询2025.10.1到2025.11.29剔除天翼云和天翼看家后省内各地市结算详情数据",
        "告诉我最近3天台州宽带账号流入流出流量",
        "家宽IP-172.34.5.44流出到外省TOPIP清单"
    ]
    
    for query in test_queries:
        print(f"\n=== 查询: {query} ===")
        attributes = extractor.extract_attributes(query)
        for attr, value in attributes.items():
            print(f"{attr}: {value}")
