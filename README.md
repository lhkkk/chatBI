# chatBI - 对话式商业智能系统

chatBI是一个基于大模型的对话式商业智能系统，通过自然语言交互实现数据分析和查询功能。

## 项目概述

chatBI旨在让用户通过自然语言与系统交互，自动识别业务场景、收集必要信息，并最终执行数据查询，从而大大降低了非技术用户进行数据分析的门槛。

## 核心组件架构

### 1. Web前端界面 (`web.py`)
- 基于Streamlit构建的Web界面
- 提供用户友好的聊天界面
- 处理用户输入并展示查询结果

### 2. 后端服务 (`backend_server.py`)
- 基于Flask的应用，提供REST API接口
- 管理会话状态和业务流程控制
- 协调各个核心组件协同工作

### 3. 核心模块

#### 状态机管理 (`core/state_machine/`)
- **状态处理器** (`state_handlers.py`): 处理不同状态码的业务逻辑
- **状态转移** (`state_transitions.py`): 管理状态之间的流转规则
- 状态码范围: 100-600，分别对应不同的业务阶段：
  - 100-200: 会话初始化和场景识别
  - 200-300: 信息收集和确认
  - 300-400: 查询执行
  - 400-500: 闲聊处理
  - 500+: 异常处理

#### 会话管理 (`core/session_manager/`)
- **上下文构建** (`context_builder.py`): 构建和维护对话上下文
- **会话存储** (`session_store.py`): 管理会话历史记录，支持内存存储

#### 算法适配器 (`core/algorithm_adapter/`)
- **场景分类**: 一级/二级场景识别
- **冲突检测**: 处理状态冲突和异常情况
- **字段提取**: 从用户输入中提取关键字段信息

#### 查询执行器 (`core/query_executor/`)
- **MCP客户端**: 调用MCP接口执行数据查询
- **Supersonic适配器**: 与Supersonic平台集成，扩展查询能力

### 4. 服务层 (`service/`)

#### NLP处理 (`algorithm_service.py`)
- 集成jieba分词、hanlp自然语言处理库
- 提供文本分析和语义理解功能

#### 场景分类 (`primary_scene_classification.py`, `third_scene_classification_service.py`)
- 一级场景分类: 固定返回"流量流向分析"
- 三级场景分类: 支持IP流量分析、客户流量分析、地域流量分析等细粒度分类

#### 模板填充 (`fill_template_pipeline_service.py`)
- 问题模板填充流水线
- 支持规则抽取和LLM抽取两种字段提取方式
- 生成相似问题以优化用户体验

#### 记忆系统 (`memos_service.py`, `memu_service.py`)
- 集成MemOS和Memu记忆系统
- 管理对话历史和用户个性化信息

## 业务流程

1. **用户输入**: 用户通过Web界面输入自然语言查询
2. **场景识别**: 系统识别查询所属的业务场景
3. **信息补全**: 通过多轮对话引导用户补全查询所需字段
4. **用户确认**: 用户确认查询条件的准确性
5. **查询执行**: 调用MCP或Supersonic执行数据查询
6. **结果返回**: 将查询结果以可视化方式返回给用户

## 技术栈

- **前端**: Streamlit
- **后端**: Flask
- **NLP**: jieba, hanlp, fuzzywuzzy
- **大模型**: 集成大模型API
- **数据查询**: MCP平台、Supersonic平台
- **配置管理**: TOML格式配置文件

## 目录结构

```
chatBI/
├── core/                  # 核心模块
│   ├── algorithm_adapter/ # 算法适配器
│   ├── query_executor/    # 查询执行器
│   ├── session_manager/   # 会话管理
│   └── state_machine/     # 状态机管理
├── service/               # 服务层
├── models/                # 模型接口
├── prompts/               # 提示词模板
├── web.py                 # Web前端
├── backend_server.py      # 后端服务
└── defaults.toml          # 默认配置
```

## 部署说明

1. 安装依赖:
   ```bash
   pip install -r requirements
   ```

2. 配置环境变量和配置文件

3. 启动后端服务:
   ```bash
   python backend_server.py
   ```

4. 启动Web界面:
   ```bash
   streamlit run web.py
   ```

## 使用说明

1. 在Web界面中输入自然语言查询
2. 根据系统提示补充必要的查询条件
3. 确认查询信息后等待系统返回结果
4. 查看并分析返回的数据结果

## 开发指南

### 添加新的业务场景

1. 在`service/`目录下创建新的场景分类服务
2. 更新状态机中的状态转移规则
3. 添加相应的提示词模板

### 扩展查询平台

1. 在`core/query_executor/`中添加新的查询客户端
2. 更新后端服务以支持新的查询方式

## 贡献

欢迎提交Issue和Pull Request来改进chatBI系统。

## 许可证

[待定]