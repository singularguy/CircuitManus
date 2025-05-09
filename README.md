# CircuitManus - 智能电路设计与交互平台 (V8.3.2)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Frontend Tech](https://img.shields.io/badge/frontend-FastAPI%20%7C%20WebSocket%20%7C%20JS-brightgreen.svg)]()
[![Status](https://img.shields.io/badge/status-持续迭代中-green.svg)]()
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/singularguy/CircuitManus)


**CircuitManus** (内部代号 OpenManus Agent) 是一个专为电路设计任务构建的、基于 Python 的高级异步智能体，现已集成 FastAPI WebSocket 服务器和现代化 Web UI，提供一个完整的智能交互平台。它利用大语言模型（LLM，当前集成智谱 AI `glm-z1-flash`）的强大理解和规划能力，结合一系列内部精确执行的工具（现已扩展至10个），来自动化和辅助完成电路设计相关的操作。其核心架构严格遵循经典的 **感知 -> 规划 -> 行动 -> 观察 -> 响应生成** 的智能体循环模型，并具备强大的容错和自我修正能力，特别针对LLM输出的JSON采用`camelCase`键名以提升兼容性。

**平台通过 WebSocket 实现后端 Agent 核心与前端 Web 界面的无缝实时交互。**

---

## ✨ 核心特性

*   **🌐 现代化 Web 用户界面:**
    *   **实时交互:** 基于 FastAPI 和 WebSocket，与 Agent 核心流畅、实时双向通信。
    *   **精致设计:** 美观、清晰、响应式的用户界面，支持浅色/深色/自动主题切换。
    *   **会话管理:** 创建、切换、命名和删除多个独立的聊天会话，数据持久化于浏览器 `localStorage`。
    *   **动态状态展示:** 实时显示 Agent 的处理阶段、思考过程摘要、工具执行详情。
    *   **统一的思考与回复:** Agent 的思考过程（`<think>`标签内容）与其最终回复一同展示在聊天气泡中，增强透明度（可配置）。
    *   **增强的消息区分:** 通过头像和样式清晰区分用户与 Agent 消息。
    *   **文件上传预览 (概念):** 支持文件附件，并在发送前进行预览。
    *   **可配置体验:** 提供设置模态框，调整主题、字号、动画级别、自动滚动等。
    *   **详细处理日志:** UI 内嵌可折叠的处理日志区域，完整记录 Agent 状态更新。

*   **🧠 智能规划与重规划 (Agent 核心 - V8.3.2 CamelCase JSON):**
    *   **LLM驱动的规划:** 利用 `glm-z1-flash` 理解复杂指令，生成包含工具调用或直接回复的结构化 `camelCase` JSON 计划。
    *   **失败后自动重规划:** 当工具执行失败时，Agent 将失败信息反馈给 LLM，请求生成修正后的新计划。
    *   **LLM规划调用重试:** 在与 LLM 沟通不畅时自动重试。
    *   **鲁棒布尔值解析:** 增强对 LLM 输出中布尔值（如 `isCallTools`）的解析。

*   **🛠️ 精确工具执行与容错 (Agent 核心 - 10个工具):**
    *   **动态工具注册:** 通过 `@register_tool` 装饰器为 Agent 添加新功能。
    *   **异步工具执行:** 工具按计划顺序异步执行，支持工具级重试。
    *   **执行失败中止:** 单个工具在重试后仍失败时，会中止当前计划的后续步骤。

*   **💡 增强的 Agent 逻辑 (Agent 核心):**
    *   **强化直接问答处理:** 即使对于概念性问题或普通对话，Agent 也能正确理解并（通过规划）直接生成回复。
    *   **回调驱动的状态更新:** Agent 核心通过回调函数将所有处理阶段的状态异步发送给服务器。
    *   **思考内容分离:** Agent 的思考过程（`<think>`标签内容）从最终回复中逻辑分离，通过专门的状态回调消息发送。

*   **💾 状态与记忆管理 (Agent 核心):**
    *   **对象化电路状态 (`Circuit` 类):** 封装电路元件、连接和ID生成逻辑。
    *   **多层记忆系统 (`MemoryManager` 类):** 短期记忆（对话历史）、长期记忆（关键操作记录）、统一管理 `Circuit` 对象。

*   **🔧 工程实践 (Agent 核心 & 服务器):**
    *   **异步核心 (`asyncio`):** FastAPI 与 Agent 核心均充分利用异步特性。
    *   **模块化设计:** Agent 核心代码结构清晰（Orchestrator, MemoryManager, LLMInterface, OutputParserV8_3_CamelCaseReasoning, ToolExecutor 等）。
    *   **详细文件日志:** Agent 每次运行自动在 `WebUIAgentLogs` 目录下生成带时间戳和 PID 的日志文件。

---

## 🚀 快速开始

### 环境要求

*   Python 3.8+
*   现代 Web 浏览器 (Chrome, Firefox, Edge, Safari 最新版)
*   智谱 AI API 密钥

### 安装与运行步骤

1.  **克隆仓库：**
    ```bash
    git clone <your-repository-url> # 请替换为您的实际仓库地址
    cd CircuitManus
    ```

2.  **后端 (Python Agent) 设置：**
    *   **安装依赖：**
        核心依赖: `zhipuai>=2.0`, `fastapi`, `uvicorn`, `websockets`.
        ```bash
        pip install "zhipuai>=2.0" fastapi uvicorn websockets
        ```
        *建议使用 `requirements.txt`。*

    *   **配置 API 密钥：**
        设置环境变量 `ZHIPUAI_API_KEY` 为您的智谱 AI API Key。

3.  **启动服务器：**
    ```bash
    uvicorn server:app --host 127.0.0.1 --port 8000 --reload
    ```

4.  **访问 Web UI：**
    打开浏览器，访问 `http://127.0.0.1:8000`。

### Web UI 交互示例

*   **初始化:** 页面加载后自动连接 WebSocket。
*   **发送消息:** 输入指令 (例如："帮我加一个1k欧姆的电阻R10，再加一个5V电池BAT1，然后把它们连起来")，点击发送。
*   **查看状态与回复:**
    *   **处理日志:** 实时显示 Agent 的规划、工具调用、思考等步骤。
    *   **聊天区域:** 您的消息在右侧，Agent 回复在左侧（可配置显示其思考过程）。
        例如，Agent 回复可能包含：
        ```
        [Agent Avatar]
        [思考过程] 用户要求添加R10和BAT1并连接。将调用 add_component_tool 两次，然后 connect_components_tool。
        --------------------
        好的，我正在为您添加电阻 R10 (1kΩ)、电池 BAT1 (5V)，并将它们连接起来。
        ```
*   **会话管理:** 创建、切换、命名会话。
*   **设置:** 调整主题、字号、动画、思考显示等。

---

## 🛠️ Agent 可用工具 (10个)

Agent 通过调用内部注册的工具来执行具体操作：

1.  **`add_component_tool`**: 添加新电路元件 (如电阻, 电容, 电池)。
2.  **`connect_components_tool`**: 连接两个已存在的元件。
3.  **`describe_circuit_tool`**: 获取当前电路的详细描述。
4.  **`clear_circuit_tool`**: 彻底清空当前电路。
5.  **`remove_component_tool`**: 移除指定元件及其所有连接。
6.  **`disconnect_components_tool`**: 断开两个指定元件间的连接。
7.  **`update_component_value_tool`**: 更新已存在元件的值。
8.  **`find_component_by_id_tool`**: 根据 ID 查找元件并返回其信息。
9.  **`list_components_by_type_tool`**: 列出所有指定类型的元件。
10. **`get_component_connection_count_tool`**: 获取指定元件的连接数量。

*开发者可通过 `@register_tool` 装饰器在 `CircuitManusCore.py` 中添加更多工具。*

---

## 📁 项目结构

```
CircuitManus/
├── WebUIAgentLogs/         # Agent 核心运行日志 (自动生成)
├── static/                 # 前端静态文件
│   ├── style.css           # UI 样式表
│   ├── script.js           # UI 交互逻辑
│   └── index.html          # Web UI 入口页面
├── CircuitManusCore.py     # Agent 核心逻辑 (V8.3.2)
├── server.py               # FastAPI WebSocket 服务器
└── README.md               # 本文件
```

---

## 💡 技术栈

*   **后端 (Agent & Server):** Python 3.8+, FastAPI, Uvicorn, ZhipuAI SDK (`glm-z1-flash`), Asyncio.
*   **前端 (Web UI):** HTML5, CSS3, JavaScript (原生 ES6+), Font Awesome, Animate.css.
*   **核心概念:** Agentic Loop, LLM-based Planning (CamelCase JSON), Tool Use, WebSocket Real-time Communication.

---

## 📜 开源协议

本项目基于 **MIT 许可证** 开源。

---

## 🤝 贡献与反馈

欢迎通过 GitHub Issues 报告 Bug、提出功能建议或提交代码改进 (Pull Request)。

---

*CircuitManus - 驱动智能，点亮电路设计的未来！*
