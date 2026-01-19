# 提问交互接口
chat_request =  {
	'chat_id': '1906888040751751169',  # 会话id
    'user_id': 'user_12345',          # 用户id
	'role': 'user',                   # 角色，默认是用户
	'content': [{
		'segmentId': 'seg1906888046486360064',
		'question': '提取6到11月的广东各个地市流出情况，源端和目标端均区分IDC、城域网',
	}],
	'history': [
		{'role': 'assistant', 'content': '有什么可以帮你的吗？'},
		{'role': 'user', 'content': '你好'}]
}


# 会话状态存储
state_storage_json = {
  # ====== 会话元数据 ====== 
  "session_id": "sess_20250715_001",      # 会话id
  "user_id": "user_12345",                # 用户id
  "created_at": "2025-07-17 12:00:00",    # 新会话记录
  "last_updated": "2025-07-18 11:00:00",  # 每次状态更新时刷新

  # ====== 任务状态 ======
  "task_id": "task_20250715_001",         # 新任务开始时生成
  "task_status": "awaiting_field",        # 任务状态机变化时更新 new_chat、new_task、scene_completion、task_completion、end

  # ====== 场景分类 ======
  "primary_scene": "省间流量查询",            # 一级分类完成后设置
  "primary_score": 0.92,                    # 一级分类时计算
  "candidate_primary": [{"name": "拉流", "score": 0.65}],    # 一级场景低于阈值，提供候选，比如阈值0.7，默认为空
  "primary_"
  "secondary_scene": "topIP场景",            # 二级分类完成后设置
  "secondary_score": 0.85,                  # 二级分类时计算
  "candidate_secondary": [{"level": "secondary", "name": "IDC客户流量分析", "score": 0.45}],
  "scene_confirmed": False,               # 用户确认后设为true

  # ====== 字段状态 ======
  "final_scene": "TopIP",
  "confirmed_fields": {                   # 字段确认后更新
    "time_range": {                       # 时间范围字段
      "value": "last_30_days", 
      "source": "user_input",             # user_input/system_inferred
    },
    "metrics": ["流量"],                   # 指标列表
    "dimensions": ["山东省", "江苏省"],     # 维度列表
    "region_scope": ["IDC", "MAN", "流出"]       # 场景特有字段
  },
  "pending_fields": ["TOPN"],     # 缺失字段列表（字段检查后设置）
  "final_question": "近30天山东IDC流出到江苏MAN的TOP3的IP以及流量",

  # ====== 对话上下文 ======
  "last_user_input": "前3个",    # 每次用户输入后更新
  "last_system_response": "请告诉我想查询Top几的IP呢", # 每次系统响应后更新
  "history": [],                   # 完整的历史对话问答对

  # ====== 执行状态 ======
  "execute": {
    "execution_method": "mcp_api",          # 执行决策后设置: text2sql/mcp_api
    "execution_status": "pending",          # 执行状态: pending/running/completed/failed
    "result_metadata": {                    # 查询完成后更新
    "result": "",                           # 记录结果，可视化展示等
  },
  }
}


# 状态流转流程
# 1.新会话开始
begin = {
  "session_metadata": {
    "session_id": "sess_001",
    "user_id": "user_123",
    "session_status": "active"
  },
  "current_task": {
    "task_id": "task_001",
    "task_status": "new"
  }
}

# 2.用户输入
input = {
  "scene_classification": {
    "primary": {
      "scene_name": "销售分析",
      "confidence": 0.95
    }
  },
  "confirmed_fields": {
    "common_fields": {
      "time_range": {
        "value": "last_month",
        "source": "user_input"
      },
      "metrics": ["销售额"]
    },
    "specific_fields": {
      "region_scope": {
        "value": ["华东"],
        "confirmed": True
      }
    }
  }
}

# 3.发现缺失需要补全
pending_action = {
  "pending_actions": {
    "awaiting_type": "field_supplement",
    "target": "product_category",
    "prompt": "请选择产品类别",
    "options": ["手机", "电脑", "配件"]
  },
  "current_task": {
    "task_status": "awaiting_field"
  }
}

# 4.用户响应
confimed_field = {
  "confirmed_fields": {
    "specific_fields": {
      "product_category": {
        "value": ["手机", "电脑"],
        "confirmed": True
      }
    }
  },
  "pending_actions": None, # 清除待处理动作
  "context": {
    "last_user_input": "手机和电脑",
    "last_system_response": "请选择产品类别"
  }
}

# 5.查询
execute = {
  "execution_state": {
    "structured_query": {
      "metrics": ["sales_amount"],
      "filters": [
        {"field": "region", "values": ["east"]},
        {"field": "product_category", "values": ["phone", "computer"]},
        {"field": "date", "range": ["2025-06-01", "2025-06-30"]}
      ]
    },
    "execution_method": "mcp_api",
    "execution_status": "completed"
  },
  "current_task": {
    "task_status": "completed"
  }
}

