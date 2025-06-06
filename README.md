# CircuitManus - 多功能智能体平台 (V1.0.0 - Refactored)


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows-blue.svg)]()
[![Backend Tech](https://img.shields.io/badge/backend-Python%20%7C%20FastAPI%20%7C%20Asyncio-purple.svg)]() 
[![Frontend Tech](https://img.shields.io/badge/frontend-HTML%20%7C%20CSS%20%7C%20JS%20%7C%20WebSocket-brightgreen.svg)]()
[![LLM Provider](https://img.shields.io/badge/LLM-ZhipuAI%20(GLM)-orange.svg)]() 
[![Status](https://img.shields.io/badge/status-积极开发中-green.svg)]()
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/singularguy/CircuitManus)


**CircuitManus** (内部代号 OpenManus Agent) 是一个基于 Python 构建的、经过**模块化重构**的**通用型高级异步智能体 (Agent) 平台**。它旨在通过集成大语言模型（LLM）和可扩展的工具集，赋能和自动化各类复杂任务。当前版本 (V1.0.0) **首批工具集聚焦于电路设计领域**，但其核心架构具备轻松扩展至其他领域的能力。

平台集成了 FastAPI WebSocket 服务器和现代化 Web UI，提供完整的智能交互体验。其核心 (`circuitmanus`包) 利用大语言模型（当前默认集成智谱 AI `glm-z1-flash`）的强大理解和规划能力，结合一系列内部精确执行的工具（当前包含 **11 个**，涵盖电路操作与网络搜索），来辅助用户完成任务。Agent 核心架构严格遵循经典的 **感知 -> 规划 -> 行动 -> 观察 -> 响应生成** 的智能体循环模型，并具备强大的容错和自我修正能力。LLM交互严格遵循定义的V1.0.0 `camelCase` JSON协议。

**平台通过 WebSocket 实现后端 Agent 核心与前端 Web 界面的无缝实时交互，专为 Windows 环境优化和测试。**

---

## ✨ 核心特性

*   **🌐 现代化 Web 用户界面:**
    *   **实时交互:** 基于 FastAPI 和 WebSocket，与 Agent 核心流畅、实时双向通信。
    *   **精致设计:** 美观、清晰、响应式的用户界面，支持浅色/深色/自动主题切换。
    *   **会话管理:** 创建、切换、命名和删除多个独立的聊天会话，数据持久化于浏览器 `localStorage`。
    *   **动态状态展示:** 实时显示 Agent 的处理阶段、思考过程摘要、工具执行详情。
    *   **统一的思考与回复:** Agent 的思考过程（`<think>`标签内容）与其最终回复一同展示在聊天气泡中，增强透明度。
    *   **可配置体验:** 提供设置模态框，调整主题、字号、动画级别、自动滚动等。

*   **🧠 智能规划与重规划 (Agent 核心 - `circuitmanus.agent`):**
    *   **LLM驱动的规划:** 利用 `glm-z1-flash` (可配置) 理解复杂指令，生成包含工具调用或直接回复的结构化 `camelCase` JSON 计划。
    *   **失败后自动重规划:** 当工具执行失败时，Agent 将失败信息反馈给 LLM，请求生成修正后的新计划。
    *   **LLM规划调用重试:** 在与 LLM 沟通不畅时自动重试。

*   **🛠️ 精确工具执行与容错 (Agent 核心 - `circuitmanus.tools` - **11个工具**):**
    *   **模块化工具定义:** 工具按功能领域分离（如电路操作、网络搜索），易于扩展新领域工具。
    *   **动态工具注册:** 通过 `@register_tool` 装饰器为 Agent 添加新功能，自动发现和绑定。
    *   **异步工具执行:** `ToolExecutor` 智能处理同步和异步工具，确保服务器响应性。
    *   **工具级重试与失败中止:** 支持单个工具重试，并在持久失败后中止后续计划。

*   **💡 通用 Agent 架构 (`circuitmanus.agent`):**
    *   <!-- 要求 2: 突出通用性 -->
    *   **领域无关的核心编排逻辑:** `process_user_request` 流程不与特定工具领域强耦合，易于通过添加新工具模块来扩展 Agent 的能力范围。
    *   **回调驱动的状态更新:** Agent 核心通过异步回调将处理状态发送给服务器。
    *   **思考内容分离:** Agent 的思考过程通过专门的 `thinking_log` 状态回调发送。

*   **💾 状态与记忆管理 (Agent 核心 - `circuitmanus.memory` & `circuitmanus.circuit_domain`):**
    *   **可插拔领域模型:** 当前包含电路领域模型 (`CircuitComponent`, `Circuit` 类)，未来可添加其他领域的数据模型。
    *   **分层记忆系统 (`MemoryManager` 类):** 管理短期对话历史、长期知识片段，并可持有特定领域的状态对象（如当前的 `Circuit` 实例）。

*   **🔧 工程实践 (Agent 核心 & 服务器 - Windows 平台):**
    *   **Pythonic 异步核心 (`asyncio`):** FastAPI 服务器与 `circuitmanus` Agent 核心均充分利用异步特性。
    *   **高度模块化设计:** `circuitmanus`包结构清晰，提升代码可维护性和可扩展性。
    *   **详细分级日志:** Agent 运行自动在 `WebUIAgentLogs` 目录下生成日志。
    *   **清晰的Prompt工程 (`prompts.templates`):** 将LLM系统提示生成逻辑分离。

---

## 🚀 快速开始

### 环境要求

*   **操作系统:** Windows (已在该平台进行主要开发和测试)
*   Python 3.8+ (建议使用虚拟环境)
*   现代 Web 浏览器 (Chrome, Firefox, Edge 最新版)
*   **智谱 AI API 密钥:** 用于 Agent 与 `glm-z1-flash` 模型交互。
    <!-- 要求 3: 注明duckduckgo的问题 然后简要说说如何获取 另一个工具的api -->
*   **（可选）其他第三方服务 API 密钥:** 如需扩展需要认证的在线工具（例如天气查询、股票信息等），可能需要获取相应的API密钥。

### 安装与运行步骤

1.  **克隆仓库：**
    ```bash
    git clone https://github.com/singularguy/CircuitManus
    cd IDT_AGENT_NATIVE 
    ```

2.  **后端 (Python Agent) 设置：**
    *   **创建并激活虚拟环境 (推荐):**
        ```bash
        python -m venv venv
        .\venv\Scripts\activate 
        ```
    *   **安装依赖：**
        核心依赖: `zhipuai>=2.0`, `fastapi`, `uvicorn[standard]`, `websockets`, `python-dotenv`, `httpx`, `duckduckgo-search`。
        建议从 `requirements.txt` 安装：
        ```bash
        pip install -r requirements.txt
        ```
    *   **配置 API 密钥：**
        *   **智谱 AI API Key:** 设置环境变量 `ZHIPUAI_API_KEY`。
            或在项目根目录创建 `.env` 文件，并写入： `ZHIPUAI_API_KEY="YOUR_ZHIPU_API_KEY"`。
        *   <!-- 要求 3: 获取其他工具API的简要说明 -->
        *   **其他工具 API Keys (如需):** 若您计划集成需要 API 密钥的第三方工具（例如特定数据库、付费API服务等），通常步骤如下：
            1.  访问该第三方服务的官方网站。
            2.  注册开发者账户（如果需要）。
            3.  在其开发者门户或API文档中找到关于如何申请和获取API密钥的说明。
            4.  获取到密钥后，建议同样通过环境变量或 `.env` 文件进行管理，并在相应的工具实现中读取和使用。

3.  **启动服务器：**
    确保当前终端目录位于项目根 (`IDT_AGENT_NATIVE`)。
    ```bash
    uvicorn server:app --host 127.0.0.1 --port 8000 --reload
    ```

4.  **访问 Web UI：**
    打开浏览器，访问 `http://127.0.0.1:8000`。

### Web UI 交互示例
<!-- 内容保持不变，因为是UI操作示例 -->
*   **初始化:** 页面加载后自动连接 WebSocket。
*   **发送消息:** 输入指令 (例如："帮我加一个1k欧姆的电阻R10，再加一个5V电池BAT1，然后把它们连起来")，点击发送。
*   **查看状态与回复:**
    *   **处理日志:** 实时显示 Agent 的规划、工具调用、思考等步骤。
    *   **聊天区域:** 您的消息在右侧，Agent 回复在左侧。

---

## 🛠️ Agent 可用工具 (当前共 11 个)

Agent 通过调用内部注册的工具来执行具体操作。当前工具集主要面向电路设计，但 Agent 平台支持扩展。

**电路操作工具 (`circuitmanus.tools.circuit_ops`):**
1.  `add_component_tool`
2.  `connect_components_tool`
3.  `describe_circuit_tool`
4.  `clear_circuit_tool`
5.  `remove_component_tool`
6.  `disconnect_components_tool`
7.  `update_component_value_tool`
8.  `find_component_by_id_tool`
9.  `list_components_by_type_tool`
10. `get_component_connection_count_tool`

**网络搜索工具 (`circuitmanus.tools.web_search`):**
11. `duckduckgo_search_tool`: 使用 DuckDuckGo 搜索引擎进行网络信息查询。
    *   <!-- 要求 3: 注明duckduckgo的问题 -->
    *   **注意:** `duckduckgo-search` 库依赖于对 DuckDuckGo 网站的非官方访问，其稳定性可能受限于 DuckDuckGo 网站的更新或反爬虫策略。在某些网络环境下或 DuckDuckGo 策略变更时，此工具可能无法正常工作或返回结果不理想。如遇问题，可考虑替换为官方提供API的搜索引擎工具（通常需要申请API Key）。

*开发者可通过在 `circuitmanus.tools` 子包中创建新模块或修改现有模块，并使用 `@register_tool` 装饰器来方便地添加更多自定义工具，以扩展 Agent 的能力至不同领域。*

---

## 📁 项目结构 (Refactored)
```
IDT_AGENT_NATIVE/
├── circuitmanus/            # Agent 核心逻辑包 (V1.0.0 Refactored)
│   ├── __init__.py
│   ├── agent.py             # CircuitAgent 主类和核心编排逻辑
│   ├── circuit_domain/      # (示例)电路领域模型
│   ├── memory/              # 通用记忆管理
│   ├── llm/                 # LLM交互与解析
│   ├── tools/               # 工具定义与执行 (可扩展)
│   │   ├── circuit_ops.py   # (示例)电路操作工具
│   │   └── web_search.py    # (示例)网络搜索工具
│   ├── prompts/             # Prompt工程
│   └── utils/               # 通用工具
│
├── static/                 # 前端静态文件
├── WebUIAgentLogs/         # Agent 运行日志
├── tests/                  # 单元测试和集成测试
├── .env                    # 环境变量文件 (示例)
├── requirements.txt        # Python 依赖列表
├── server.py               # FastAPI WebSocket 服务器
└── README.md               # 本文件
```

---

## 💡 技术栈

*   **后端 (Agent & Server):** Python 3.8+ (Windows 环境优化), FastAPI, Uvicorn, ZhipuAI SDK, Asyncio, Websockets, DuckDuckGo Search, HTTPX.
*   **前端 (Web UI):** HTML5, CSS3, JavaScript (原生 ES6+).
*   **核心概念:** 通用智能体 (Agentic Loop), LLM驱动规划 (V1.0.0 CamelCase JSON), 可扩展工具集, 异步架构, WebSocket实时通信, 模块化设计.

---

## 📜 开源协议

本项目基于 **MIT 许可证** 开源。

---

## 🤝 贡献与反馈

欢迎通过 GitHub Issues 报告 Bug、提出功能建议或提交代码改进 (Pull Request)。

---

*CircuitManus - 构建智能，赋能未来！*
