# @FileName: CircuitManusCore.py
# @Version: V8.3.2-CamelCaseJSON - Adapted for glm-z1-flash, robust boolean parsing, camelCase JSON keys, Expanded to 10 Tools
# @Author: Your Most Loyal, Dedicated, Meticulous & Now Extremely Cautious Programmer (Enhanced JSON Key Naming for LLM Compatibility & Robust Boolean Parsing, Expanded Toolset)
# @Date: [Current Date] - Implemented camelCase for LLM-generated JSON keys, maintained robust boolean parsing, and expanded toolset to 10.
# @License: MIT License
# @Description:
# ==============================================================================================
#  Manus 系统 V8.3.2-CamelCaseJSON 技术实现说明 (附带10个工具)
# ==============================================================================================
#
# V8.3.2-CamelCaseJSON 核心改动 (基于 V8.3.1-RobustBooleans):
# 1.  **CamelCase JSON Keys for LLM Output**:
#     - All keys in the JSON structure expected from the LLM (and parsed by
#       `OutputParserV8_3_CamelCaseReasoning`) have been changed from snake_case
#       or ALL_CAPS_SNAKE_CASE to camelCase (e.g., `IS_CALL_TOOLS` is now `isCallTools`,
#       `TOOL_CALL_REQUESTS` is now `toolCallRequests`, `request_id` is now `requestId`).
#     - This change is implemented in the OutputParser, the system prompts
#       (schema description and examples), and all relevant Python code that
#       accesses these parsed JSON fields.
#     - This aims to improve compatibility and reliability with LLMs that may
#       handle underscores inconsistently in key names.
# 2.  **Robust Boolean Parsing Maintained**:
#     - The robust boolean parsing for `isCallTools` (formerly `IS_CALL_TOOLS`)
#       is preserved. It correctly interprets string values "true" (case-insensitive)
#       as Python `True`, and "false" (case-insensitive) as Python `False`, in addition
#       to standard JSON boolean literals.
# 3.  **Parser Class Renamed**:
#     - `OutputParserV8_3_Reasoning` has been renamed to
#       `OutputParserV8_3_CamelCaseReasoning` to reflect the new JSON key convention.
# 4.  **Expanded Toolset**:
#     - The number of available tools for the agent has been increased from 4 to 10,
#       providing more granular control and query capabilities over the circuit.
#       New tools include:
#         - `remove_component_tool`
#         - `disconnect_components_tool`
#         - `update_component_value_tool`
#         - `find_component_by_id_tool`
#         - `list_components_by_type_tool`
#         - `get_component_connection_count_tool`
#
# (Inherits all fixes and features from V8.3.1-RobustBooleans)
# ==============================================================================================


# --- 基础库导入 ---
import re
import os
import json
import time
import logging
import sys
import asyncio
import traceback
import inspect
import functools
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Set, Union, Callable, Awaitable
from uuid import uuid4
from zhipuai import ZhipuAI

# --- 全局异步事件循环 ---
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# --- 日志系统配置 ---
LOG_DIR = "WebUIAgentLogs"
try:
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
except OSError as e:
    sys.stderr.write(f"CRITICAL: Could not create log directory '{LOG_DIR}'. Error: {e}\n")
    sys.stderr.write("File logging may be unavailable. Continuing with console logging only.\n")

current_time_for_log = datetime.now()
log_file_name = os.path.join(
    LOG_DIR,
    f"agent_log_v8_3_2_camelcase_10tools_{current_time_for_log.strftime('%Y%m%d_%H%M%S')}_{current_time_for_log.microsecond // 1000:03d}_P{os.getpid()}.log"
)

log_format = '%(asctime)s - %(name)s - %(levelname)s [%(module)s.%(funcName)s:%(lineno)d] - %(message)s'

console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.DEBUG) # Default to DEBUG, will be adjusted by Agent's verbose mode
console_handler.setFormatter(logging.Formatter(log_format))

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

try:
    file_handler = logging.FileHandler(log_file_name, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)
    logger.info(f"Successfully configured file logging. Log messages will also be saved to: {os.path.abspath(log_file_name)}")
except Exception as e:
    logger.error(f"CRITICAL: Failed to configure file logging to '{log_file_name}'. Error: {e}", exc_info=True)
    logger.error("Agent will continue with console logging only.")

logging.getLogger("zhipuai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


# --- 电路元件数据类 ---
class CircuitComponent:
    __slots__ = ['id', 'type', 'value']
    def __init__(self, component_id: str, component_type: str, value: Optional[str] = None):
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError("元件 ID 必须是有效的非空字符串")
        if not isinstance(component_type, str) or not component_type.strip():
            raise ValueError("元件类型必须是有效的非空字符串")
        self.id: str = component_id.strip().upper()
        self.type: str = component_type.strip()
        self.value: Optional[str] = str(value).strip() if value is not None and str(value).strip() else None
    def __str__(self) -> str:
        value_str = f" (值: {self.value})" if self.value else ""
        return f"元件: {self.type} (ID: {self.id}){value_str}"
    def __repr__(self) -> str:
        return f"CircuitComponent(id='{self.id}', type='{self.type}', value={repr(self.value)})"
    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "type": self.type, "value": self.value}

# --- 电路实体类 ---
class Circuit:
    def __init__(self):
        logger.info("[Circuit] 初始化电路实体. ")
        self.components: Dict[str, CircuitComponent] = {}
        self.connections: Set[Tuple[str, str]] = set()
        self._component_counters: Dict[str, int] = {
            'R': 0, 'L': 0, 'B': 0, 'S': 0, 'C': 0, 'V': 0, 'G': 0, 'U': 0, 'O': 0,
            'I': 0, 'A': 0, 'D': 0, 'P': 0, 'F': 0, 'H': 0,
            'T': 0, 'N': 0, 'IN': 0, 'OUT': 0
        }
        logger.info("[Circuit] 电路实体初始化完成. ")

    def add_component(self, component: CircuitComponent):
        if component.id in self.components:
            raise ValueError(f"元件 ID '{component.id}' 已被占用. ")
        self.components[component.id] = component
        logger.debug(f"[Circuit] 元件 '{component.id}' 已添加到电路. ")

    def remove_component(self, component_id: str):
        comp_id_upper = component_id.strip().upper()
        if comp_id_upper not in self.components:
            raise ValueError(f"元件 '{comp_id_upper}' 在电路中不存在. ")
        removed_component_details = self.components[comp_id_upper].to_dict()
        del self.components[comp_id_upper]
        
        connections_to_remove = {conn for conn in self.connections if comp_id_upper in conn}
        removed_connections_count = len(connections_to_remove)
        for conn in connections_to_remove:
            self.connections.remove(conn)
            logger.debug(f"[Circuit] 移除了涉及元件 '{comp_id_upper}' 的连接 {conn}.")
        
        logger.debug(f"[Circuit] 元件 '{comp_id_upper}' 及其相关 {removed_connections_count} 个连接已从电路中移除. ")
        return removed_component_details, removed_connections_count


    def connect_components(self, id1: str, id2: str):
        id1_upper = id1.strip().upper()
        id2_upper = id2.strip().upper()
        if id1_upper == id2_upper: raise ValueError(f"不能将元件 '{id1_upper}' 连接到它自己. ")
        if id1_upper not in self.components: raise ValueError(f"元件 '{id1_upper}' 在电路中不存在. ")
        if id2_upper not in self.components: raise ValueError(f"元件 '{id2_upper}' 在电路中不存在. ")
        connection = tuple(sorted((id1_upper, id2_upper)))
        if connection in self.connections:
             logger.warning(f"[Circuit] 连接 '{id1_upper}' <--> '{id2_upper}' 已存在. ")
             return False
        self.connections.add(connection)
        logger.debug(f"[Circuit] 添加了连接: {id1_upper} <--> {id2_upper}.")
        return True

    def disconnect_components(self, id1: str, id2: str):
        id1_upper = id1.strip().upper()
        id2_upper = id2.strip().upper()
        connection = tuple(sorted((id1_upper, id2_upper)))
        if connection not in self.connections:
             logger.warning(f"[Circuit] 连接 '{id1_upper}' <--> '{id2_upper}' 不存在,无需断开. ")
             return False # Indicate connection didn't exist to be removed
        self.connections.remove(connection)
        logger.debug(f"[Circuit] 断开了连接: {id1_upper} <--> {id2_upper}.")
        return True # Indicate successful removal

    def get_state_description(self) -> str:
        logger.debug("[Circuit] 正在生成电路状态描述...")
        num_components = len(self.components)
        num_connections = len(self.connections)

        if num_components == 0 and num_connections == 0:
            return "【当前电路状态】: 电路为空. "

        desc_lines = ["【当前电路状态】:"]
        desc_lines.append(f"  - 元件 ({num_components}):")
        if self.components:
            sorted_ids = sorted(self.components.keys())
            for cid in sorted_ids:
                desc_lines.append(f"    - {str(self.components[cid])}")
        else:
            desc_lines.append("    (无)")

        desc_lines.append(f"  - 连接 ({num_connections}):")
        if self.connections:
            sorted_connections = sorted(list(self.connections))
            for c1, c2 in sorted_connections:
                desc_lines.append(f"    - {c1} <--> {c2}")
        else:
            desc_lines.append("    (无)")

        description = "\n".join(desc_lines)
        logger.debug("[Circuit] 电路状态描述生成完毕. ")
        return description

    def generate_component_id(self, component_type: str) -> str:
        logger.debug(f"[Circuit] 正在为类型 '{component_type}' 生成唯一 ID...")
        type_map = {
            "resistor": "R", "电阻": "R", "capacitor": "C", "电容": "C",
            "battery": "B", "电池": "B", "voltage source": "V", "voltage": "V",
            "电压源": "V", "电压": "V", "led": "L", "发光二极管": "L", "switch": "S",
            "开关": "S", "ground": "G", "地": "G", "ic": "U", "chip": "U", "芯片": "U",
            "集成电路": "U", "inductor": "I", "电感": "I", "current source": "A",
            "电流源": "A", "diode": "D", "二极管": "D", "potentiometer": "P", "电位器": "P",
            "fuse": "F", "保险丝": "F", "header": "H", "排针": "H",
            "terminal": "T", "端子": "T", "connection point": "P", "连接点": "P", "node": "N", "节点": "N", # Note: 'P' is overloaded, prefer 'T' or 'N' if specific
            "input": "IN", "输入": "IN", "output": "OUT", "输出": "OUT",
            "component": "O", "元件": "O", # Generic fallback
        }

        # Ensure all codes in type_map have a counter
        for code in type_map.values():
            if code not in self._component_counters:
                 self._component_counters[code] = 0

        cleaned_type = component_type.strip().lower()
        type_code = "O" # Default to "Other"
        best_match_len = 0

        # Prioritize specific keywords that might be substrings of others
        if cleaned_type == "input": type_code = "IN"
        elif cleaned_type == "output": type_code = "OUT"
        elif cleaned_type == "ground" or cleaned_type == "地": type_code = "G"
        else:
            # Find the best matching keyword
            for keyword, code in type_map.items():
                if keyword in cleaned_type and len(keyword) > best_match_len:
                    type_code = code
                    best_match_len = len(keyword)

        if type_code == "O" and cleaned_type not in ["component", "元件"]: # Log if using generic for something not explicitly generic
             logger.warning(f"[Circuit] 未找到类型 '{component_type}' 的特定前缀,将使用通用前缀 'O'. ")

        MAX_ID_ATTEMPTS = 10000 # Safety break for ID generation
        for attempt in range(MAX_ID_ATTEMPTS):
            self._component_counters[type_code] += 1
            gen_id = f"{type_code}{self._component_counters[type_code]}"
            if gen_id not in self.components:
                logger.debug(f"[Circuit] 生成唯一 ID: '{gen_id}' (尝试 {attempt + 1})")
                return gen_id
            logger.debug(f"[Circuit] ID '{gen_id}' 已存在,尝试下一个.  (Attempt {attempt + 1})")

        # This should ideally never be reached if component IDs are managed correctly or circuit size is reasonable
        raise RuntimeError(f"未能为类型 '{component_type}' (代码 '{type_code}') 生成唯一 ID ({MAX_ID_ATTEMPTS} 次尝试后). 电路中可能存在大量同类型元件,或ID生成逻辑需要审查. ")

    def clear(self):
        logger.info("[Circuit] 正在清空电路状态...")
        comp_count = len(self.components)
        conn_count = len(self.connections)

        self.components = {}
        self.connections = set()

        # Reset all counters
        self._component_counters = {k: 0 for k in self._component_counters}

        logger.info(f"[Circuit] 电路状态已清空 (移除了 {comp_count} 个元件, {conn_count} 个连接,并重置了所有 ID 计数器). ")

# --- 工具注册装饰器 ---
def register_tool(description: str, parameters: Dict[str, Any]):
    def decorator(func):
        # Store schema information directly on the function object
        func._tool_schema = {"description": description, "parameters": parameters}
        func._is_tool = True # Mark this function as a tool
        @functools.wraps(func) # Preserves original function metadata
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

# --- 模块化组件: MemoryManager ---
class MemoryManager:
    def __init__(self, max_short_term_items: int = 30, max_long_term_items: int = 200):
        logger.info("[MemoryManager] 初始化记忆模块...")
        if max_short_term_items <= 1: # Need at least one system prompt and one user message
            raise ValueError("max_short_term_items 必须大于 1")

        self.max_short_term_items = max_short_term_items
        self.max_long_term_items = max_long_term_items

        self.short_term: List[Dict[str, Any]] = [] # Stores message dicts for LLM
        self.long_term: List[str] = [] # Stores string summaries of important events/learnings

        self.circuit: Circuit = Circuit() # The single source of truth for circuit state

        logger.info(f"[MemoryManager] 记忆模块初始化完成. 短期上限: {max_short_term_items} 条, 长期上限: {max_long_term_items} 条. ")

    def add_to_short_term(self, message: Dict[str, Any]):
        logger.debug(f"[MemoryManager] 添加消息到短期记忆 (Role: {message.get('role', 'N/A')}). 当前数量: {len(self.short_term)}")
        self.short_term.append(message)

        # Enforce short-term memory limit, prioritizing removal of older, non-system messages
        current_size = len(self.short_term)
        if current_size > self.max_short_term_items:
            logger.debug(f"[MemoryManager] 短期记忆超限 ({current_size}/{self.max_short_term_items}),执行修剪...")
            items_to_remove = current_size - self.max_short_term_items

            # Find indices of non-system messages, oldest first
            non_system_indices = [i for i, msg in enumerate(self.short_term) if msg.get("role") != "system"]
            num_to_actually_remove = min(items_to_remove, len(non_system_indices))

            if num_to_actually_remove > 0:
                # Remove the oldest non-system messages
                indices_to_remove_set = set(non_system_indices[:num_to_actually_remove])
                removed_roles = [self.short_term[i].get('role', 'N/A') for i in sorted(list(indices_to_remove_set))] # For logging
                new_short_term = [msg for i, msg in enumerate(self.short_term) if i not in indices_to_remove_set]
                self.short_term = new_short_term
                logger.info(f"[MemoryManager] 短期记忆修剪完成,移除了 {num_to_actually_remove} 条最旧的非系统消息 (Roles: {removed_roles}). ")
            elif items_to_remove > 0: # Still over limit, but only system messages remain (or not enough non-system)
                 logger.warning(f"[MemoryManager] 短期记忆超限 ({current_size}/{self.max_short_term_items}) 但未能找到足够的非系统消息进行移除. 可能需要增加 max_short_term_items 或审查 system 消息的使用. ")
        logger.debug(f"[MemoryManager] 添加后短期记忆数量: {len(self.short_term)}")

    def add_to_long_term(self, knowledge_snippet: str):
        MAX_SNIPPET_LENGTH = 10000 # Prevent excessively long snippets
        if len(knowledge_snippet) > MAX_SNIPPET_LENGTH:
            logger.warning(f"[MemoryManager] 尝试添加的长期记忆片段过长 ({len(knowledge_snippet)} chars),已截断为 {MAX_SNIPPET_LENGTH} 字符. ")
            knowledge_snippet = knowledge_snippet[:MAX_SNIPPET_LENGTH] + "... (截断)"

        logger.debug(f"[MemoryManager] 添加知识到长期记忆: '{knowledge_snippet[:1000]}{'...' if len(knowledge_snippet) > 100 else ''}'. 当前数量: {len(self.long_term)}")
        self.long_term.append(knowledge_snippet)
        if len(self.long_term) > self.max_long_term_items:
            removed = self.long_term.pop(0) # Remove the oldest
            logger.info(f"[MemoryManager] 长期记忆超限 ({self.max_long_term_items}), 移除最旧知识: '{removed[:50]}...'")
        logger.debug(f"[MemoryManager] 添加后长期记忆数量: {len(self.long_term)}")

    def get_circuit_state_description(self) -> str:
        return self.circuit.get_state_description()

    def get_memory_context_for_prompt(self, recent_long_term_count: int = 7) -> str:
        logger.debug("[MemoryManager] 正在格式化记忆上下文用于 Prompt...")
        circuit_desc = self.get_circuit_state_description()
        long_term_str = ""
        if self.long_term:
            actual_count = min(recent_long_term_count, len(self.long_term))
            if actual_count > 0:
                recent_items = self.long_term[-actual_count:] # Get the most recent N items
                long_term_str = "\n\n【近期经验总结 (仅显示最近 N 条,按时间倒序排列,最新在前)】\n" + "\n".join(f"- {item}" for item in reversed(recent_items))
                logger.debug(f"[MemoryManager] 已提取最近 {len(recent_items)} 条长期记忆 (倒序). ")
        long_term_str += "\n(注: 当前仅使用最近期记忆,未来版本将实现基于相关性的检索)" # Placeholder for future improvement

        context = f"{circuit_desc}{long_term_str}".strip()
        logger.debug(f"[MemoryManager] 记忆上下文 (电路+长期) 格式化完成. ")
        return context

# --- 模块化组件: LLMInterface (V8.3.0-Reasoning Model Update) ---
class LLMInterface:
    def __init__(self, agent_instance: 'CircuitAgent', model_name: str = "glm-z1-flash", default_temperature: float = 0.01, default_max_tokens: int = 8190):
        logger.info(f"[LLMInterface V8.3.0] 初始化 LLM 接口,目标模型: {model_name}")
        if not agent_instance or not hasattr(agent_instance, 'api_key'):
             raise ValueError("LLMInterface 需要一个包含 'api_key' 属性的 Agent 实例. ")
        self.agent_instance = agent_instance # To access API key and current_request_id
        api_key = self.agent_instance.api_key
        if not api_key: raise ValueError("智谱 AI API Key 不能为空")
        try:
            self.client = ZhipuAI(api_key=api_key)
            logger.info("[LLMInterface V8.3.0] 智谱 AI 客户端初始化成功. ")
        except Exception as e:
            logger.critical(f"[LLMInterface V8.3.0] 初始化智谱 AI 客户端失败: {e}", exc_info=True)
            raise ConnectionError(f"初始化智谱 AI 客户端失败: {e}") from e

        self.model_name = model_name
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens
        # Stream is False by default for Manus Agent architecture which expects full JSON
        # For V8.3.0, we expect <think> tags then JSON, still as a single response block.
        logger.info(f"[LLMInterface V8.3.0] LLM 接口初始化完成 (Model: {model_name}, Temp: {default_temperature}, MaxTokens: {default_max_tokens}, Stream: False). ")

    async def call_llm(self, messages: List[Dict[str, Any]], execution_phase: str, status_callback: Optional[Callable[[Dict], Awaitable[None]]] = None) -> Any:
        call_args = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens,
            "stream": False, # Manus V8.3.0 expects a single block with <think> and then JSON
        }

        logger.info(f"[LLMInterface V8.3.0] 准备异步调用 LLM ({self.model_name}, Phase: {execution_phase}, Expecting V8.3.0 Reasoning Model Output - <think> then JSON)...")
        logger.debug(f"[LLMInterface V8.3.0] 发送的消息条数: {len(messages)}")
        if logger.isEnabledFor(logging.DEBUG) and len(messages) > 0:
             try:
                 messages_content_for_log = []
                 for m_idx, m in enumerate(messages):
                     role = m.get("role")
                     content = str(m.get("content",""))
                     if role == "system": # System prompts can be very long
                         content_preview = content[:10000] + ("..." if len(content) > 1000 else "")
                     else:
                         content_preview = content[:1000] + ("..." if len(content) > 200 else "")
                     messages_content_for_log.append({"index": m_idx, "role": role, "content_preview_length": len(content), "content_preview": content_preview})
                 messages_summary = json.dumps(messages_content_for_log, ensure_ascii=False, indent=2)
                 logger.debug(f"[LLMInterface V8.3.0] 发送给 LLM 的消息列表 (预览):\n{messages_summary}")
             except Exception as e_json:
                 logger.debug(f"[LLMInterface V8.3.0] 无法序列化消息列表进行调试日志: {e_json}")

        request_id_to_send = self.agent_instance.current_request_id if hasattr(self.agent_instance, 'current_request_id') else None
        if status_callback:
            await status_callback({
                "type": "llm_communication_status",
                "request_id": request_id_to_send,
                "llm_phase": execution_phase,
                "status": "started",
                "message": f"正在与智能大脑 ({self.model_name}) 沟通 ({execution_phase})..."
            })

        response = None
        try:
            start_time = time.monotonic()
            # Use asyncio.to_thread for synchronous SDK calls in an async context
            response = await asyncio.to_thread(self.client.chat.completions.create, **call_args)
            duration = time.monotonic() - start_time
            logger.info(f"[LLMInterface V8.3.0] LLM 异步调用成功. 耗时: {duration:.3f} 秒. ")
            if status_callback:
                await status_callback({
                    "type": "llm_communication_status",
                    "request_id": request_id_to_send,
                    "llm_phase": execution_phase,
                    "status": "completed",
                    "message": f"与智能大脑 ({self.model_name}) 沟通完成 ({execution_phase}). ",
                    "details": {"duration_seconds": duration}
                })

            # Basic validation of response structure
            if response:
                if response.usage: logger.info(f"[LLMInterface V8.3.0] Token 统计: Prompt={response.usage.prompt_tokens}, Completion={response.usage.completion_tokens}, Total={response.usage.total_tokens}")
                if response.choices:
                    finish_reason = response.choices[0].finish_reason
                    logger.info(f"[LLMInterface V8.3.0] 完成原因: {finish_reason}")
                    if finish_reason == 'length': logger.warning("[LLMInterface V8.3.0] LLM 响应因达到最大 token 限制而被截断！这可能导致输出不完整！")
                    raw_llm_content = response.choices[0].message.content
                    logger.debug(f"[LLMInterface V8.3.0] LLM 原始响应内容 (完整):\n{raw_llm_content}") # Log the full content before parsing
                else:
                    logger.warning("[LLMInterface V8.3.0] LLM 响应中缺少 'choices' 字段. ")
            else:
                 logger.error("[LLMInterface V8.3.0] LLM API 调用返回了 None！")
                 raise ConnectionError("LLM API call returned None.")
            return response
        except Exception as e:
            logger.error(f"[LLMInterface V8.3.0] LLM API 异步调用失败: {e}", exc_info=True)
            if status_callback:
                 await status_callback({
                    "type": "llm_communication_status",
                    "request_id": request_id_to_send,
                    "llm_phase": execution_phase,
                    "status": "error",
                    "message": f"与智能大脑 ({self.model_name}) 沟通失败 ({execution_phase}). ",
                    "details": {"error": str(e), "error_type": type(e).__name__}
                 })
            raise

# --- 模块化组件: OutputParserV8_3_CamelCaseReasoning (Handles <think> tags, then V8.3.2 CamelCase JSON) ---
class OutputParserV8_3_CamelCaseReasoning:
    def __init__(self, agent_tools_registry: Optional[Dict[str, Dict[str, Any]]] = None):
        logger.info("[OutputParserV8_3_CamelCaseReasoning] 初始化输出解析器 (适配 ManusLLMResponse-V8.3.2 CamelCase JSON结构,提取 <think> 标签,增强布尔解析). ")
        self.agent_tools_registry = agent_tools_registry if agent_tools_registry else {}

    def _validate_tool_arguments(self, tool_name: str, tool_arguments: Dict[str, Any], tool_call_id: str) -> List[Dict[str, str]]:
        validation_errors: List[Dict[str, str]] = []
        if not self.agent_tools_registry or tool_name not in self.agent_tools_registry:
            validation_errors.append({
                "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolName", # camelCase
                "issue_description": f"工具 '{tool_name}' 未在 Agent 的注册表中找到. "
            })
            return validation_errors

        tool_schema = self.agent_tools_registry[tool_name]
        param_schema_props = tool_schema.get("parameters", {}).get("properties", {})
        required_params = tool_schema.get("parameters", {}).get("required", [])

        for req_param in required_params:
            if req_param not in tool_arguments: # tool_arguments keys are per tool schema (e.g., component_type)
                validation_errors.append({
                    "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{req_param}", # camelCase for structure, snake_case for arg key
                    "issue_description": f"工具 '{tool_name}' 的必需参数 '{req_param}' 缺失. "
                })

        for arg_name, arg_value in tool_arguments.items():
            if arg_name not in param_schema_props:
                validation_errors.append({
                    "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 是未在 Schema 中定义的未知参数. "
                })
                continue

            expected_type_str = param_schema_props[arg_name].get("type")
            # Type checking based on schema
            if expected_type_str == "string" and not isinstance(arg_value, str):
                # Allow None if not a required parameter and schema implies optional strings can be null
                is_optional_and_null_like = (arg_name not in required_params) and (arg_value is None)
                if not is_optional_and_null_like:
                    validation_errors.append({
                        "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                        "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是字符串,但得到的是 {type(arg_value).__name__}. "
                    })
            elif expected_type_str == "integer" and not isinstance(arg_value, int):
                 validation_errors.append({
                    "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是整数,但得到的是 {type(arg_value).__name__}. "
                })
            elif expected_type_str == "number" and not isinstance(arg_value, (int, float)):
                 validation_errors.append({
                    "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是数字,但得到的是 {type(arg_value).__name__}. "
                })
            elif expected_type_str == "boolean" and not isinstance(arg_value, bool):
                 validation_errors.append({
                    "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是布尔值,但得到的是 {type(arg_value).__name__}. "
                })
            elif expected_type_str == "object" and not isinstance(arg_value, dict):
                 validation_errors.append({
                    "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是对象(字典),但得到的是 {type(arg_value).__name__}. "
                })
            elif expected_type_str == "array" and not isinstance(arg_value, list):
                 validation_errors.append({
                    "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是数组(列表),但得到的是 {type(arg_value).__name__}. "
                })
        return validation_errors


    def parse_llm_response_to_structured_json(self, llm_api_response_message: Any, execution_phase: str) -> Tuple[Optional[Dict[str, Any]], str, List[Dict[str,str]]]:
        parser_id = f"parse_v832_camelcase_{str(uuid4())[:8]}" # Updated parser_id
        logger.debug(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 开始解析 LLM 响应 (Phase: {execution_phase})...")
        parsed_json_dict: Optional[Dict[str, Any]] = None
        error_message: str = ""
        failed_validation_points_list: List[Dict[str, str]] = [] # Stores dicts with "jsonPath" and "issue_description"
        extracted_thought_process: Optional[str] = None

        if llm_api_response_message is None:
            error_message = "LLM 响应对象 (Message) 为 None. "
            logger.error(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 解析失败: {error_message}")
            return None, error_message, [{"jsonPath": "root", "issue_description": error_message}]

        raw_content = getattr(llm_api_response_message, 'content', None)
        if not raw_content or not raw_content.strip():
            error_message = "LLM 响应内容 (content 字段) 为空或仅包含空白字符. "
            logger.error(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 解析失败: {error_message}")
            return None, error_message, [{"jsonPath": "content", "issue_description": error_message}]

        logger.debug(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 接收到的原始 LLM content (完整):\n{raw_content}")

        # V8.3.0: Extract <think> block first
        content_to_parse_for_json = raw_content
        think_match = re.search(r"<think>(.*?)</think>", raw_content, re.DOTALL | re.IGNORECASE)

        if think_match:
            extracted_thought_process = think_match.group(1).strip()
            content_to_parse_for_json = raw_content[think_match.end():].strip() # Parse what's after <think> block
            logger.info(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 成功提取到 <think>...</think> 内容. ")
            logger.debug(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 提取的思考过程 (预览):\n{extracted_thought_process[:1000]}...")
            logger.debug(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 剩余内容待解析为JSON (预览):\n{content_to_parse_for_json[:1000]}...")
            if not content_to_parse_for_json: # Check if anything remains after <think>
                 error_message = "LLM 响应包含 <think> 块但之后没有内容可解析为 JSON."
                 logger.error(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 解析失败: {error_message}")
                 return None, error_message, [{"jsonPath": "root_after_think_block", "issue_description": error_message}]
        else:
            logger.warning(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 未在LLM响应中找到有效的 <think>...</think> 块,将尝试按旧方式解析整个内容. ")
            # content_to_parse_for_json remains raw_content

        # Attempt to extract JSON from markdown code block or clean up surrounding text
        json_string_to_parse = content_to_parse_for_json.strip()
        match_md_json = re.search(r"```json\s*(.*?)\s*```", json_string_to_parse, re.DOTALL | re.IGNORECASE)
        if match_md_json:
            json_string_to_parse = match_md_json.group(1).strip()
            logger.debug(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 从 Markdown 代码块中提取到 JSON 字符串. ")
        else:
            # Handle cases where LLM might prepend non-JSON text before the first '{'
            first_brace = json_string_to_parse.find('{')
            last_brace = json_string_to_parse.rfind('}') # For basic sanity check
            if first_brace > 0 and (last_brace == -1 or first_brace > last_brace) : # Found '{' but it's not at the start, and it looks like a prefix
                prefix_content = json_string_to_parse[:first_brace].strip()
                logger.warning(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 在预期的 JSON 开头 '{{' 之前检测到非空白内容: '{prefix_content[:1000]}...'. 将尝试从 '{{' 开始解析. ")
                json_string_to_parse = json_string_to_parse[first_brace:]
            elif first_brace == -1 : # No '{' found at all
                error_message = "无法在 LLM 响应内容 (post-<think>或完整) 中找到 JSON 对象的起始 '{'. "
                logger.error(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 解析失败: {error_message} 原始响应预览 (post-<think>或完整): {json_string_to_parse[:1000]}...")
                return None, error_message, [{"jsonPath": "content_for_json_parsing", "issue_description": error_message}]

        logger.debug(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 预处理后,准备解析的 JSON 字符串 (完整):\n{json_string_to_parse}")

        try:
            parsed_json_dict = json.loads(json_string_to_parse)
            logger.info(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] JSON 字符串成功解析为字典. ")
        except json.JSONDecodeError as json_err:
            error_message = f"JSON 解析失败: {json_err}. "
            logger.error(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] {error_message} Raw JSON string (截断): '{json_string_to_parse[:1000]}...'")
            return None, error_message, [{"jsonPath": "root_json_parsing", "issue_description": f"JSONDecodeError: {json_err}"}]
        except Exception as e: # Catch any other unexpected errors during parsing
            error_message = f"解析 LLM 响应时发生未知错误: {e}"
            logger.error(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 解析时未知错误: {error_message}", exc_info=True)
            return None, error_message, [{"jsonPath": "root_json_parsing", "issue_description": f"Unexpected parsing error: {e}"}]

        if not isinstance(parsed_json_dict, dict):
            error_message = "解析后的结果不是一个 JSON 对象 (字典). "
            logger.error(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 结构验证失败: {error_message}")
            return None, error_message, [{"jsonPath": "root_json_parsing", "issue_description": error_message}]

        # V8.3.0: If <think> block was extracted, prioritize it for 'thoughtProcess'
        if extracted_thought_process is not None:
            if "thoughtProcess" in parsed_json_dict and parsed_json_dict["thoughtProcess"] and parsed_json_dict["thoughtProcess"] != extracted_thought_process:
                logger.warning(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] LLM提供了<think>块和JSON内部的thoughtProcess. 将优先使用<think>块内容.")
            parsed_json_dict["thoughtProcess"] = extracted_thought_process # Override or set
            logger.info(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 已将<think>块内容置于parsed_json_dict['thoughtProcess'].")
        elif "thoughtProcess" not in parsed_json_dict or not parsed_json_dict.get("thoughtProcess", "").strip():
             logger.warning(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] LLM未提供<think>块,且JSON内部的thoughtProcess为空或缺失. 思考过程可能不完整.")


        # --- V8.3.2 CamelCase JSON Schema Validation (adapted from V8.2.2 structure) ---
        required_top_level_fields = ["requestId", "llmInteractionId", "timestampUtc", "status", "executionPhase", "thoughtProcess", "decision"]
        for field in required_top_level_fields:
            if field not in parsed_json_dict:
                failed_validation_points_list.append({"jsonPath": field, "issue_description": f"缺少必需的顶级字段 '{field}'."})

        status_val = parsed_json_dict.get("status")
        if status_val not in ["success", "failure"]:
            failed_validation_points_list.append({"jsonPath": "status", "issue_description": f"字段 'status' 的值 '{status_val}' 无效,必须是 'success' 或 'failure'."})

        exec_phase_val = parsed_json_dict.get("executionPhase")
        if exec_phase_val not in ["planning", "response_generation"]:
            failed_validation_points_list.append({"jsonPath": "executionPhase", "issue_description": f"字段 'executionPhase' 的值 '{exec_phase_val}' 无效,必须是 'planning' 或 'response_generation'."})
        elif exec_phase_val != execution_phase: # Check if LLM's phase matches Agent's expectation
             failed_validation_points_list.append({"jsonPath": "executionPhase", "issue_description": f"LLM报告的 'executionPhase' ('{exec_phase_val}') 与 Agent 期望的阶段 ('{execution_phase}') 不匹配. "})

        if status_val == "failure":
            error_details_obj = parsed_json_dict.get("errorDetails")
            if not isinstance(error_details_obj, dict):
                failed_validation_points_list.append({"jsonPath": "errorDetails", "issue_description": "当 'status' 为 'failure' 时, 'errorDetails' 必须是一个对象. "})
            else:
                if not isinstance(error_details_obj.get("errorType"), str) or not error_details_obj.get("errorType","").strip():
                    failed_validation_points_list.append({"jsonPath": "errorDetails.errorType", "issue_description": "'errorDetails' 对象中缺少有效的 'errorType' 字符串. "})
                if not isinstance(error_details_obj.get("errorCode"), str) or not error_details_obj.get("errorCode","").strip():
                    failed_validation_points_list.append({"jsonPath": "errorDetails.errorCode", "issue_description": "'errorDetails' 对象中缺少有效的 'errorCode' 字符串. "})
                if not isinstance(error_details_obj.get("technicalMessage"), str) or not error_details_obj.get("technicalMessage","").strip():
                    failed_validation_points_list.append({"jsonPath": "errorDetails.technicalMessage", "issue_description": "'errorDetails' 对象中缺少有效的 'technicalMessage' 字符串. "})
                if "isDirectLlmFailure" not in error_details_obj or not isinstance(error_details_obj.get("isDirectLlmFailure"), bool):
                    # This is a new field, be a bit lenient for now if LLM forgets, but log a warning
                    logger.warning(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 'errorDetails.isDirectLlmFailure' 字段缺失或类型不为布尔. Agent将假定为False. LLM输出应包含此字段. ")
                    failed_validation_points_list.append({"jsonPath": "errorDetails.isDirectLlmFailure", "issue_description": "'errorDetails' 对象中缺少有效的布尔字段 'isDirectLlmFailure'. "})

        elif status_val == "success" and parsed_json_dict.get("errorDetails") is not None:
             failed_validation_points_list.append({"jsonPath": "errorDetails", "issue_description": "当 'status' 为 'success' 时, 'errorDetails' 字段必须为 null 或不存在. "})

        if not isinstance(parsed_json_dict.get("thoughtProcess"), str): # Allow empty string for thoughtProcess if <think> block was used
            if parsed_json_dict.get("thoughtProcess") is not None: # if it's present but not string
                logger.warning(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 'thoughtProcess' 字段存在但类型不正确 (应为字符串). ")
                failed_validation_points_list.append({"jsonPath": "thoughtProcess", "issue_description": "'thoughtProcess' 字段如果存在,必须是字符串. "})
        elif not parsed_json_dict.get("thoughtProcess","").strip() and extracted_thought_process is None:
            logger.warning(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] LLM未提供<think>块,且JSON内部的thoughtProcess为空或缺失. 思考过程可能不完整.")


        decision_obj = parsed_json_dict.get("decision")
        if not isinstance(decision_obj, dict):
            failed_validation_points_list.append({"jsonPath": "decision", "issue_description": "'decision' 字段必须是一个对象. "})
        else:
            # V8.3.1: Robust boolean parsing for isCallTools (key now camelCase)
            raw_is_call_tools_val = decision_obj.get("isCallTools")
            is_call_tools_val = None # This will store the Python boolean
            if isinstance(raw_is_call_tools_val, bool):
                is_call_tools_val = raw_is_call_tools_val
            elif isinstance(raw_is_call_tools_val, str):
                if raw_is_call_tools_val.lower() == 'true':
                    is_call_tools_val = True
                elif raw_is_call_tools_val.lower() == 'false':
                    is_call_tools_val = False
            
            if is_call_tools_val is None: # If still None, it's an invalid type or unparsable string
                failed_validation_points_list.append({"jsonPath": "decision.isCallTools", "issue_description": f"'decision.isCallTools' 值 '{raw_is_call_tools_val}' 无效. 必须是布尔类型或可解析为布尔的字符串('true'/'false')."})
            else:
                # Update the parsed dict with the Python boolean for downstream use
                decision_obj["isCallTools"] = is_call_tools_val
                logger.debug(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 'isCallTools' (原始: {raw_is_call_tools_val}) 被解析为布尔值: {is_call_tools_val}")


            tool_call_requests = decision_obj.get("toolCallRequests") # camelCase
            if is_call_tools_val is True: # Use the parsed Python boolean
                if not isinstance(tool_call_requests, list):
                    failed_validation_points_list.append({"jsonPath": "decision.toolCallRequests", "issue_description": "当 'isCallTools' 为 True 时, 'toolCallRequests' 必须是一个列表. "})
                elif not tool_call_requests: # Empty list is valid, but potentially a planning issue
                    logger.warning(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] 'isCallTools' 为 True 但 'toolCallRequests' 列表为空. 这可能是一个规划逻辑问题. ")
                elif tool_call_requests: # If list and not empty, validate each item
                    for i, tool_req_item in enumerate(tool_call_requests):
                        item_path_prefix = f"decision.toolCallRequests[{i}]"
                        if not isinstance(tool_req_item, dict):
                            failed_validation_points_list.append({"jsonPath": item_path_prefix, "issue_description": "列表中的每个工具调用请求必须是对象. "}); continue # Skip to next if not dict

                        tool_call_id = tool_req_item.get("toolCallId") # camelCase
                        if not isinstance(tool_call_id, str) or not tool_call_id.strip():
                            failed_validation_points_list.append({"jsonPath": f"{item_path_prefix}.toolCallId", "issue_description": "缺少有效的 'toolCallId' 字符串. "})

                        tool_name = tool_req_item.get("toolName") # camelCase
                        if not isinstance(tool_name, str) or not tool_name.strip():
                            failed_validation_points_list.append({"jsonPath": f"{item_path_prefix}.toolName", "issue_description": "缺少有效的 'toolName' 字符串. "})

                        tool_arguments = tool_req_item.get("toolArguments") # camelCase for this key
                        if not isinstance(tool_arguments, dict): # Content of toolArguments is tool-specific schema
                            failed_validation_points_list.append({"jsonPath": f"{item_path_prefix}.toolArguments", "issue_description": "'toolArguments' 必须是一个对象. "})
                        elif tool_name and isinstance(tool_name, str) and tool_name.strip(): # Only validate arguments if tool_name is valid string
                            arg_validation_errors = self._validate_tool_arguments(tool_name, tool_arguments, tool_call_id if (tool_call_id and isinstance(tool_call_id, str) and tool_call_id.strip()) else f"index_{i}")
                            failed_validation_points_list.extend(arg_validation_errors)

                        ui_hints = tool_req_item.get("uiHints") # camelCase
                        if ui_hints is not None and not isinstance(ui_hints, dict):
                            failed_validation_points_list.append({"jsonPath": f"{item_path_prefix}.uiHints", "issue_description": "'uiHints' 如果存在,必须是一个对象. "})
                        # Further validation of uiHints content can be added here if necessary

            elif is_call_tools_val is False: # Use the parsed Python boolean
                if tool_call_requests is not None and (not isinstance(tool_call_requests, list) or tool_call_requests): # Must be null or empty list
                    failed_validation_points_list.append({"jsonPath": "decision.toolCallRequests", "issue_description": "当 'isCallTools' 为 False 时, 'toolCallRequests' 必须是 null 或空列表 []. "})

            response_user_obj = decision_obj.get("responseToUser") # camelCase
            if not isinstance(response_user_obj, dict):
                failed_validation_points_list.append({"jsonPath": "decision.responseToUser", "issue_description": "'responseToUser' 必须是一个对象. "})
            else:
                if not isinstance(response_user_obj.get("contentType"), str) or not response_user_obj.get("contentType","").strip(): # camelCase
                     failed_validation_points_list.append({"jsonPath": "decision.responseToUser.contentType", "issue_description": "'responseToUser' 对象缺少有效的 'contentType' 字符串. "})

                resp_content = response_user_obj.get("content") # Stays 'content'
                if not isinstance(resp_content, str):
                     failed_validation_points_list.append({"jsonPath": "decision.responseToUser.content", "issue_description": "'responseToUser.content' 必须是字符串. "})

                # If not calling tools, content must be non-empty (unless it's a transitional message in planning phase with tools)
                if is_call_tools_val is False and (not resp_content or resp_content.strip() == ""): # Use parsed boolean
                     if execution_phase == "response_generation": # In final response, content must be there
                         failed_validation_points_list.append({"jsonPath": "decision.responseToUser.content", "issue_description": "在响应生成阶段, 'responseToUser.content' 必须是有效的非空字符串. "})
                     else: # In planning phase, if not calling tools, it's a direct answer, so content needed
                        failed_validation_points_list.append({"jsonPath": "decision.responseToUser.content", "issue_description": "当 'isCallTools' 为 False (直接回复) 时, 'responseToUser.content' 必须是有效的非空字符串. "})


                suggestions = response_user_obj.get("suggestionsForNextSteps") # camelCase
                if suggestions is not None:
                    if not isinstance(suggestions, list):
                        failed_validation_points_list.append({"jsonPath": "decision.responseToUser.suggestionsForNextSteps", "issue_description": "'suggestionsForNextSteps' 如果存在,必须是一个列表. "})
                    else:
                        for j, sugg_item in enumerate(suggestions):
                            sugg_path_prefix = f"decision.responseToUser.suggestionsForNextSteps[{j}]"
                            if not isinstance(sugg_item, dict):
                                failed_validation_points_list.append({"jsonPath": sugg_path_prefix, "issue_description": "列表中的每个建议必须是对象. "}); continue
                            if not isinstance(sugg_item.get("textForUser"), str) or not sugg_item.get("textForUser","").strip(): # camelCase
                                failed_validation_points_list.append({"jsonPath": f"{sugg_path_prefix}.textForUser", "issue_description": "建议对象缺少有效的 'textForUser' 字符串. "})
                            # Further validation of suggestion_id, action_type, action_payload can be added

                clarification_flag = response_user_obj.get("requiresUserClarificationForCurrentRequest") # camelCase
                if clarification_flag is not None and not isinstance(clarification_flag, bool):
                     failed_validation_points_list.append({"jsonPath": "decision.responseToUser.requiresUserClarificationForCurrentRequest", "issue_description": "'requiresUserClarificationForCurrentRequest' 如果存在,必须是布尔类型. "})

        diagnostics_obj = parsed_json_dict.get("diagnostics") # Stays 'diagnostics'
        if diagnostics_obj is not None and not isinstance(diagnostics_obj, dict):
            failed_validation_points_list.append({"jsonPath": "diagnostics", "issue_description": "'diagnostics' 如果存在,必须是一个对象. "})
        # Further validation of diagnostics content can be added if necessary

        if failed_validation_points_list:
            error_message_parts = [f"JSON 结构或内容验证失败 (共 {len(failed_validation_points_list)} 点):"]
            for err_point in failed_validation_points_list:
                error_message_parts.append(f"  -路径 '{err_point['jsonPath']}': {err_point['issue_description']}") # Use jsonPath
            error_message = "\n".join(error_message_parts)

            json_content_for_log = json.dumps(parsed_json_dict, indent=2, ensure_ascii=False) if parsed_json_dict else json_string_to_parse[:1000]
            logger.error(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning]\n{error_message}\nParsed JSON content (可能不完整或无效):\n{json_content_for_log}")
            return None, error_message, failed_validation_points_list

        logger.info(f"[{parser_id}-OutputParserV8_3_CamelCaseReasoning] LLM 响应 (Phase: {execution_phase}, LLM_ID: {parsed_json_dict.get('llmInteractionId', 'N/A')}) 已成功解析并验证为 ManusLLMResponse-V8.3.2-CamelCaseJSON兼容结构 (思考过程源: {'<think> block' if extracted_thought_process else 'JSON field'})！")
        return parsed_json_dict, "", []


# --- 模块化组件: ToolExecutor ---
class ToolExecutor:
    def __init__(self, agent_instance: 'CircuitAgent', max_tool_retries: int = 1, tool_retry_delay_seconds: float = 1.0):
        logger.info("[ToolExecutor] 初始化工具执行器 (支持异步, 重试, 失败中止, UI回调增强 V8.3.0). ")
        if not isinstance(agent_instance, CircuitAgent): # Check type explicitly
            raise TypeError("ToolExecutor 需要一个 CircuitAgent 实例. ")
        self.agent_instance = agent_instance
        if not hasattr(agent_instance, 'memory_manager') or not isinstance(agent_instance.memory_manager, MemoryManager):
            raise TypeError("Agent 实例缺少有效的 MemoryManager. ")

        self.verbose_mode = getattr(agent_instance, 'verbose_mode', True) # Get verbose_mode from agent
        self.max_tool_retries = max(0, max_tool_retries) # Ensure non-negative
        self.tool_retry_delay_seconds = max(0.1, tool_retry_delay_seconds) # Ensure positive delay

        logger.info(f"[ToolExecutor] 工具执行配置: 每个工具最多重试 {self.max_tool_retries} 次,重试间隔 {self.tool_retry_delay_seconds} 秒. Verbose Mode: {self.verbose_mode}")

    async def _send_tool_status_update(
        self,
        status_callback: Optional[Callable[[Dict], Awaitable[None]]],
        tool_call_id: str, # This is toolCallId from LLM JSON
        tool_name: str,    # This is toolName from LLM JSON
        tool_status: str,  # e.g., "running", "succeeded", "failed", "retrying", "aborted_due_to_previous_failure"
        message: str,
        tool_arguments: Optional[Dict] = None, # Parsed tool_arguments (content)
        details: Optional[Dict] = None
    ):
        if status_callback:
            request_id_to_send = self.agent_instance.current_request_id if hasattr(self.agent_instance, 'current_request_id') else None

            arguments_summary_str = "N/A"
            if tool_arguments:
                try:
                    args_parts = []
                    for k, v in tool_arguments.items(): # Keys here are Pythonic (e.g., component_type)
                        v_str = str(v) if v is not None else "None"
                        v_preview = v_str[:30] + '...' if len(v_str) > 30 else v_str
                        args_parts.append(f"{k}: {v_preview}")
                    arguments_summary_str = "; ".join(args_parts)
                    if not arguments_summary_str: arguments_summary_str = "(无参数)"
                except Exception as e_sum:
                    logger.warning(f"生成工具参数摘要时出错: {e_sum}")
                    arguments_summary_str = "(参数摘要生成错误)"

            # Keys in this status update payload are for UI/internal consumption, can remain snake_case
            await status_callback({
                "type": "tool_status_update",
                "request_id": request_id_to_send,
                "tool_call_id": tool_call_id, # Pass the original toolCallId
                "tool_name": tool_name,       # Pass the original toolName
                "tool_arguments_summary_str": arguments_summary_str,
                "status": tool_status,
                "message": message,
                "details": details if details else {}
            })

    async def execute_tool_calls(self, tool_call_requests_from_plan: List[Dict[str, Any]], status_callback: Optional[Callable[[Dict], Awaitable[None]]] = None) -> List[Dict[str, Any]]:
        executor_id = f"exec_v830_{str(uuid4())[:8]}" # Version can stay as V8.3.0 logic-wise for executor
        logger.info(f"[{executor_id}-ToolExecutor] 准备异步执行 {len(tool_call_requests_from_plan)} 个工具调用请求 (V8.3.0)...")
        execution_results_for_llm_history: List[Dict[str, Any]] = []

        if not tool_call_requests_from_plan:
            logger.info(f"[{executor_id}-ToolExecutor] 没有工具需要执行. ")
            return []

        total_tools_in_plan = len(tool_call_requests_from_plan)

        for i, tool_request in enumerate(tool_call_requests_from_plan):
            # LLM provides toolCallId, toolName, toolArguments (camelCase keys for the structure)
            llm_generated_tool_call_id = tool_request.get('toolCallId', f'fallback_tool_id_{str(uuid4())[:8]}')
            python_function_name = tool_request.get('toolName', 'unknown_function') # toolName from LLM maps to python_function_name
            parsed_arguments = tool_request.get('toolArguments', {}) # toolArguments content is tool-specific schema
            ui_hints_from_plan = tool_request.get('uiHints', {})

            # Determine display name for UI updates
            tool_display_name = ui_hints_from_plan.get('displayNameForTool') or python_function_name.replace('_tool', '').replace('_', ' ').title()

            action_result_final_for_tool: Optional[Dict[str, Any]] = None
            tool_succeeded_this_cycle = False

            logger.info(f"[{executor_id}-ToolExecutor] 处理工具调用 {i + 1}/{total_tools_in_plan}: Name='{python_function_name}', LLM_ToolCallID='{llm_generated_tool_call_id}'")
            logger.debug(f"[{executor_id}-ToolExecutor] 待执行工具 '{python_function_name}' 的参数: {parsed_arguments}")

            await self._send_tool_status_update(
                status_callback, llm_generated_tool_call_id, python_function_name,
                "running", f"开始执行操作: {tool_display_name}...",
                tool_arguments=parsed_arguments,
                details={"ui_hints": ui_hints_from_plan}
            )

            tool_action_method = getattr(self.agent_instance, python_function_name, None)
            if not callable(tool_action_method) or not getattr(tool_action_method, '_is_tool', False):
                err_msg_not_found = f"Agent 未实现名为 '{python_function_name}' 的已注册工具方法 (ID: {llm_generated_tool_call_id}). "
                logger.error(f"[{executor_id}-ToolExecutor] 工具未实现或未注册: {err_msg_not_found}")
                action_result_final_for_tool = {"status": "failure", "message": err_msg_not_found, "error": {"error_type": "TOOL_IMPLEMENTATION_ERROR", "error_code": "TOOL_NOT_FOUND_OR_NOT_REGISTERED", "technical_message": f"Action method '{python_function_name}' not found or not a registered tool in Agent."}}
                await self._send_tool_status_update(
                    status_callback, llm_generated_tool_call_id, python_function_name,
                    "failed", f"操作 '{tool_display_name}' 失败: 工具未在Agent中实现或注册. ",
                    details={"error": action_result_final_for_tool["error"]}
                )
                # For LLM history, role "tool" message needs tool_call_id and name (matching LLM's request)
                execution_results_for_llm_history.append({"role": "tool", "tool_call_id": llm_generated_tool_call_id, "name": python_function_name, "content": json.dumps(action_result_final_for_tool, ensure_ascii=False, default=str)})
                break # Abort further tool calls in this sequence if one is not found/registered

            # Retry loop for the current tool
            for retry_attempt in range(self.max_tool_retries + 1): # +1 for initial attempt
                current_attempt_num = retry_attempt + 1
                if retry_attempt > 0: # This is a retry
                    logger.warning(f"[{executor_id}-ToolExecutor] 工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 执行失败,正在进行第 {retry_attempt}/{self.max_tool_retries} 次重试...")
                    await self._send_tool_status_update(
                        status_callback, llm_generated_tool_call_id, python_function_name,
                        "retrying", f"操作 '{tool_display_name}' 失败,等待 {self.tool_retry_delay_seconds} 秒后重试 (尝试 {current_attempt_num})...",
                        tool_arguments=parsed_arguments, details={"retry_count": retry_attempt, "max_retries": self.max_tool_retries, "ui_hints": ui_hints_from_plan}
                    )
                    await asyncio.sleep(self.tool_retry_delay_seconds)

                action_result_this_attempt: Optional[Dict[str, Any]] = None
                try:
                    # The actual tool method is called with the `arguments` dictionary
                    action_result_this_attempt = await asyncio.to_thread(tool_action_method, arguments=parsed_arguments)

                    # Validate the structure of the result returned by the tool method itself
                    if not isinstance(action_result_this_attempt, dict) or 'status' not in action_result_this_attempt or 'message' not in action_result_this_attempt:
                        err_msg_struct = f"工具 '{python_function_name}' 返回的内部结果结构无效. 期望字典包含 'status' 和 'message'. "
                        logger.error(f"[{executor_id}-ToolExecutor] 工具返回结构错误 (Attempt {current_attempt_num}): {err_msg_struct}")
                        action_result_this_attempt = {"status": "failure", "message": f"错误: 工具 '{python_function_name}' 内部返回结果结构无效. ", "error": {"error_type": "TOOL_IMPLEMENTATION_ERROR", "error_code": "INVALID_TOOL_ACTION_RESULT_STRUCTURE", "technical_message": err_msg_struct}}
                    else:
                        logger.info(f"[{executor_id}-ToolExecutor] 工具 '{python_function_name}' 执行完毕 (Attempt {current_attempt_num}). 状态: {action_result_this_attempt.get('status', 'N/A')}")

                    if action_result_this_attempt.get("status") == "success":
                        tool_succeeded_this_cycle = True
                        action_result_final_for_tool = action_result_this_attempt
                        break # Successful execution, exit retry loop

                    # If status is not "success", it's a failure for this attempt
                    logger.warning(f"[{executor_id}-ToolExecutor] 工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 执行失败 (Attempt {current_attempt_num}). ")
                    if retry_attempt == self.max_tool_retries: # Last attempt also failed
                        action_result_final_for_tool = action_result_this_attempt # This will be the final failure result

                except TypeError as te: # Catch argument mismatch specifically
                    err_msg_type = f"调用工具 '{python_function_name}' 时参数不匹配或内部类型错误: {te}."
                    logger.error(f"[{executor_id}-ToolExecutor] 工具调用参数/类型错误 (Attempt {current_attempt_num}): {err_msg_type}", exc_info=True)
                    action_result_this_attempt = {"status": "failure", "message": f"错误: 调用工具 '{python_function_name}' 时参数或内部类型错误. ", "error": {"error_type": "TOOL_EXECUTION_ERROR", "error_code": "ARGUMENT_TYPE_MISMATCH_OR_INTERNAL_TYPE_ERROR", "technical_message": err_msg_type, "exception_details": traceback.format_exc(limit=3)}}
                    action_result_final_for_tool = action_result_this_attempt
                    break # Critical error, no point in retrying
                except Exception as exec_err: # Catch all other errors during tool execution
                    err_msg_exec = f"工具 '{python_function_name}' 执行期间发生意外内部错误 (Attempt {current_attempt_num}): {exec_err}"
                    logger.error(f"[{executor_id}-ToolExecutor] 工具执行内部错误: {err_msg_exec}", exc_info=True)
                    action_result_this_attempt = {"status": "failure", "message": f"错误: 执行工具 '{python_function_name}' 时发生内部错误. ", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "UNEXPECTED_TOOL_EXECUTION_FAILURE", "technical_message": err_msg_exec, "exception_details": traceback.format_exc(limit=3)}}
                    if retry_attempt == self.max_tool_retries: # Last attempt failed with an exception
                        action_result_final_for_tool = action_result_this_attempt

            # After retry loop, action_result_final_for_tool should be set
            if action_result_final_for_tool is None: # Should not happen if logic is correct
                 logger.error(f"[{executor_id}-ToolExecutor] 内部逻辑错误: 工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 未在重试后生成任何最终结果. ")
                 action_result_final_for_tool = {"status": "failure", "message": f"错误: 工具 '{python_function_name}' 未返回结果. ", "error": {"error_type": "TOOL_EXECUTION_ERROR", "error_code": "MISSING_TOOL_RESULT_AFTER_RETRIES", "technical_message": "Tool action_result_final_for_tool remained None after retry loop."}}

            # Send final status for this tool call
            final_tool_status_str_for_cb = "succeeded" if tool_succeeded_this_cycle else "failed"
            status_message_for_cb = action_result_final_for_tool.get('message', '操作完成,无特定消息. ')
            details_for_cb: Dict[str, Any] = {"ui_hints": ui_hints_from_plan}

            if tool_succeeded_this_cycle:
                result_data_summary = action_result_final_for_tool.get("data") # 'data' field from tool's return
                if result_data_summary is not None:
                    try: details_for_cb["result_data_preview"] = json.dumps(result_data_summary, ensure_ascii=False, default=str, indent=None)[:1000]
                    except: details_for_cb["result_data_preview"] = "(数据无法序列化预览)"
            else: # Tool failed
                details_for_cb["error"] = action_result_final_for_tool.get("error", {"error_type": "UNKNOWN_ERROR", "error_code": "GENERIC_FAILURE", "technical_message": "未知工具执行错误"})

            await self._send_tool_status_update(
                status_callback, llm_generated_tool_call_id, python_function_name,
                final_tool_status_str_for_cb, status_message_for_cb,
                details=details_for_cb
            )

            # Prepare the result message for LLM's history
            tool_result_message_for_llm = {
                "role": "tool",
                "tool_call_id": llm_generated_tool_call_id, # This MUST match the ID from LLM's request
                "name": python_function_name,              # This MUST match the name from LLM's request
                "content": json.dumps(action_result_final_for_tool, ensure_ascii=False, default=str) # Content is JSON string of the tool's result
            }
            execution_results_for_llm_history.append(tool_result_message_for_llm)
            logger.debug(f"[{executor_id}-ToolExecutor] 已记录工具 '{llm_generated_tool_call_id}' 的最终执行结果 (状态: {final_tool_status_str_for_cb}) 到LLM历史. ")

            # If this tool failed persistently, abort the rest of the tool chain
            if not tool_succeeded_this_cycle:
                logger.warning(f"[{executor_id}-ToolExecutor] 工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 在所有重试后仍然失败. 中止后续工具执行. ")
                # If there are subsequent tools planned, mark them as aborted
                if i + 1 < total_tools_in_plan:
                    for k in range(i + 1, total_tools_in_plan):
                        aborted_tool_req = tool_call_requests_from_plan[k]
                        aborted_tool_id = aborted_tool_req.get('toolCallId', f'fallback_aborted_id_{str(uuid4())[:8]}')
                        aborted_tool_name = aborted_tool_req.get('toolName', 'unknown_aborted_tool')
                        aborted_ui_hints = aborted_tool_req.get('uiHints', {})
                        aborted_tool_display_name = aborted_ui_hints.get('displayNameForTool') or aborted_tool_name.replace('_tool','').replace('_',' ').title()

                        await self._send_tool_status_update(
                            status_callback, aborted_tool_id, aborted_tool_name,
                            "aborted_due_to_previous_failure",
                            f"操作 '{aborted_tool_display_name}' 已中止,因为先前的工具 '{tool_display_name}' 执行失败. ",
                            details={"reason": f"Aborted due to failure of tool '{python_function_name}' (ID: {llm_generated_tool_call_id})", "ui_hints": aborted_ui_hints}
                        )
                        # Add a simulated failure result for these aborted tools to LLM history
                        aborted_tool_result_for_llm_content = {
                                "status": "failure",
                                "message": f"工具 '{aborted_tool_name}' 未执行,因为前序工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 失败. ",
                                "error": {"error_type": "TOOL_CHAIN_ABORTED", "error_code": "PRECEDING_TOOL_FAILURE", "technical_message": f"Execution of '{aborted_tool_name}' was skipped due to the failure of tool '{python_function_name}' (ID: {llm_generated_tool_call_id})."}
                            }
                        execution_results_for_llm_history.append({
                            "role": "tool", "tool_call_id": aborted_tool_id, "name": aborted_tool_name,
                            "content": json.dumps(aborted_tool_result_for_llm_content, ensure_ascii=False)
                        })
                        logger.info(f"[{executor_id}-ToolExecutor] 为中止的工具 '{aborted_tool_name}' (ID: {aborted_tool_id}) 添加了模拟失败记录到LLM历史. ")
                break # Exit the loop over tool_call_requests_from_plan

        total_processed_tools = len(execution_results_for_llm_history)
        logger.info(f"[{executor_id}-ToolExecutor] 工具执行流程完成. 共处理/记录了 {total_processed_tools}/{total_tools_in_plan} 个计划中的工具调用 (可能因失败提前中止). ")
        return execution_results_for_llm_history

# --- Agent 核心类 (V8.3.2-CamelCaseJSON, 10 Tools) ---
class CircuitAgent:
    def __init__(self, api_key: str, model_name: str = "glm-z1-flash",
                 max_short_term_items: int = 30, max_long_term_items: int = 75,
                 planning_llm_retries: int = 5, max_tool_retries: int = 3,
                 tool_retry_delay_seconds: float = 1.0, max_replanning_attempts: int = 3,
                 verbose: bool = True):
        logger.info(f"\n{'='*30} CircuitAgent 初始化开始 (V8.3.2-CamelCaseJSON, 10 Tools) {'='*30}")
        self.api_key = api_key
        self.verbose_mode = verbose
        self.current_request_id: Optional[str] = None # Set per request

        # Configure console log level based on verbose mode
        global console_handler # Ensure we are using the globally defined handler
        console_log_level = logging.DEBUG if self.verbose_mode else logging.INFO
        if console_handler:
            console_handler.setLevel(console_log_level)
            logger.info(f"[AgentV8_3_2 Init] 控制台日志级别已设置为: {logging.getLevelName(console_log_level)} (Verbose Mode: {self.verbose_mode})")
        else:
            logger.warning("[AgentV8_3_2 Init] Console handler not found,无法动态设置日志级别. ")

        # Tool Registration (dynamic discovery)
        self.tools_registry: Dict[str, Dict[str, Any]] = {}
        logger.info("[AgentV8_3_2 Init] 正在动态发现并注册工具...")
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, '_is_tool') and method._is_tool:
                schema = getattr(method, '_tool_schema', None)
                if schema and isinstance(schema, dict) and 'description' in schema and 'parameters' in schema:
                    self.tools_registry[name] = schema
                    logger.info(f"[AgentV8_3_2 Init] ✓ 已注册工具: '{name}'")
                else:
                    logger.warning(f"[AgentV8_3_2 Init] 发现工具 '{name}' 但其 Schema 结构不完整或无效,已跳过注册. ")
        if not self.tools_registry:
            logger.warning("[AgentV8_3_2 Init] 未发现任何通过 @register_tool 注册的工具！Agent 将主要依赖直接问答. ")
        else:
            logger.info(f"[AgentV8_3_2 Init] 共发现并注册了 {len(self.tools_registry)} 个工具. ")
            if logger.isEnabledFor(logging.DEBUG):
                try: logger.debug(f"[AgentV8_3_2 Init] 工具注册表详情:\n{json.dumps(self.tools_registry, indent=2, ensure_ascii=False)}")
                except Exception as e_dump: logger.debug(f"无法序列化工具注册表进行日志记录: {e_dump}")

        # Initialize core components
        try:
            self.memory_manager = MemoryManager(max_short_term_items, max_long_term_items)
            self.llm_interface = LLMInterface(agent_instance=self, model_name=model_name)
            # V8.3.2: Use the new OutputParser for CamelCase JSON
            self.output_parser = OutputParserV8_3_CamelCaseReasoning(agent_tools_registry=self.tools_registry)
            self.tool_executor = ToolExecutor(
                agent_instance=self,
                max_tool_retries=max_tool_retries,
                tool_retry_delay_seconds=tool_retry_delay_seconds
            )
        except (ValueError, ConnectionError, TypeError) as e: # Catch specific, expected init errors
            logger.critical(f"[AgentV8_3_2 Init] 核心模块初始化失败: {e}", exc_info=True)
            raise # Re-raise to prevent agent from starting in an invalid state

        # Configuration for retry mechanisms
        self.planning_llm_retries = max(0, planning_llm_retries) # For LLM calls during planning
        self.max_replanning_attempts = max(0, max_replanning_attempts) # For the entire planning-execution loop

        logger.info(f"[AgentV8_3_2 Init] 规划LLM重试次数: {self.planning_llm_retries}, 工具执行重试次数: {max_tool_retries}, 最大重规划尝试次数: {self.max_replanning_attempts}")

        logger.info(f"\n{'='*30} CircuitAgent 初始化成功 {'='*30}\n")

    # --- Action Implementations (Tool methods) ---
    @register_tool(
        description="添加一个新的电路元件 (如电阻, 电容, 电池, LED, 开关, 芯片, 地线, 端子/连接点等). 如果用户未指定 ID,会自动生成. ",
        parameters={"type": "object", "properties": {"component_type": {"type": "string", "description": "元件的类型 (例如: '电阻', 'LED', 'Terminal', 'INPUT', 'GND')."}, "component_id": {"type": "string", "description": "可选的用户指定 ID. "}, "value": {"type": "string", "description": "可选的元件值 (例如: '1k', '10uF')."}}, "required": ["component_type"]}
    )
    def add_component_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-AddComponentTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行添加元件操作. ")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}") # arguments keys are snake_case (e.g., component_type)
        component_type = arguments.get("component_type")
        component_id_req = arguments.get("component_id")
        value_req = arguments.get("value")

        if not component_type or not isinstance(component_type, str) or not component_type.strip():
            err_msg = "元件类型是必需的,并且必须是有效的非空字符串. "
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_TYPE", "technical_message": err_msg}}

        target_id_final = None
        id_was_generated_by_system = False
        user_provided_id_was_validated = None

        if component_id_req and isinstance(component_id_req, str) and component_id_req.strip():
            user_provided_id_cleaned = component_id_req.strip().upper() # IDs are stored uppercase
            # Basic validation for user-provided ID format (can be more complex if needed)
            if re.match(r'^[a-zA-Z0-9_][a-zA-Z0-9_-]*$', user_provided_id_cleaned) or user_provided_id_cleaned in ["INPUT", "OUTPUT", "GND"]: # Allow specific functional IDs
                if user_provided_id_cleaned in self.memory_manager.circuit.components:
                    err_msg = f"您提供的元件 ID '{user_provided_id_cleaned}' 已被占用. "
                    logger.error(f"{tool_call_logger_prefix} ID 冲突: {err_msg}")
                    return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "CIRCUIT_STATE_ERROR", "error_code": "COMPONENT_ID_CONFLICT", "technical_message": err_msg, "conflicting_id": user_provided_id_cleaned}}
                else:
                    target_id_final = user_provided_id_cleaned
                    user_provided_id_was_validated = target_id_final
                    logger.debug(f"{tool_call_logger_prefix} 将使用用户提供的有效 ID: '{target_id_final}'.")
            else:
                logger.warning(f"{tool_call_logger_prefix} 用户提供的 ID '{component_id_req}' 格式无效. 将自动生成 ID. ")
                # Fall through to ID generation

        if target_id_final is None: # If no valid user ID or user didn't provide one
            try:
                target_id_final = self.memory_manager.circuit.generate_component_id(component_type)
                id_was_generated_by_system = True
                logger.debug(f"{tool_call_logger_prefix} 已自动为类型 '{component_type}' 生成 ID: '{target_id_final}'.")
            except RuntimeError as e_gen_id: # Catch failure to generate ID
                err_msg = f"无法自动为类型 '{component_type}' 生成唯一 ID: {e_gen_id}"
                logger.error(f"{tool_call_logger_prefix} ID 生成失败: {err_msg}", exc_info=True)
                return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "INTERNAL_AGENT_ERROR", "error_code": "COMPONENT_ID_GENERATION_FAILED", "technical_message": str(e_gen_id)}}

        # Process value (ensure it's a string or None)
        processed_value = str(value_req).strip() if value_req is not None and str(value_req).strip() else None
        if value_req is None and "value" in arguments: # If "value" was explicitly passed as null/None
            processed_value = None


        try:
            if target_id_final is None: # Should not happen due to logic above, but as a safeguard
                raise ValueError("内部错误: 在尝试创建元件之前,未能最终确定有效的元件 ID. ")

            new_component = CircuitComponent(target_id_final, component_type, processed_value)
            self.memory_manager.circuit.add_component(new_component)

            logger.info(f"{tool_call_logger_prefix} 成功添加元件 '{new_component.id}' ({new_component.type}) 到电路. ")

            success_message_parts = [f"操作成功: 已添加元件 {str(new_component)}. "]
            if id_was_generated_by_system:
                success_message_parts.append(f"(系统自动分配 ID '{new_component.id}')")
            elif user_provided_id_was_validated:
                 success_message_parts.append(f"(使用了您指定的 ID '{user_provided_id_was_validated}')")

            final_success_message = " ".join(success_message_parts)

            self.memory_manager.add_to_long_term(f"添加了元件: {str(new_component)} (请求ID: {self.current_request_id or 'N/A'})")

            return {"status": "success", "message": final_success_message, "data": new_component.to_dict()}

        except ValueError as ve_comp: # Catch validation errors from CircuitComponent or circuit.add_component
            err_msg = f"创建或添加元件对象时发生内部验证错误: {ve_comp}"
            logger.error(f"{tool_call_logger_prefix} 元件创建/添加错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": "COMPONENT_CREATION_OR_ADDITION_VALIDATION_FAILED", "technical_message": str(ve_comp)}}
        except Exception as e_add_comp: # Catch-all for unexpected issues
            err_msg = f"添加元件时发生未知的内部错误: {e_add_comp}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 添加元件时发生未知内部错误. ", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "ADD_COMPONENT_UNEXPECTED_FAILURE", "technical_message": str(e_add_comp), "exception_details": traceback.format_exc(limit=3)}}


    @register_tool(
        description="使用两个已存在元件的 ID 将它们连接起来. ",
        parameters={"type": "object", "properties": {"comp1_id": {"type": "string", "description": "第一个元件的 ID. "}, "comp2_id": {"type": "string", "description": "第二个元件的 ID. "}}, "required": ["comp1_id", "comp2_id"]}
    )
    def connect_components_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-ConnectComponentsTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行连接元件操作. ")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}") # arguments keys are comp1_id, comp2_id

        comp1_id_req = arguments.get("comp1_id")
        comp2_id_req = arguments.get("comp2_id")

        # Validate inputs
        if not comp1_id_req or not isinstance(comp1_id_req, str) or not comp1_id_req.strip() or \
           not comp2_id_req or not isinstance(comp2_id_req, str) or not comp2_id_req.strip():
            err_msg = "必须提供两个有效的、非空的元件 ID 字符串. "
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_IDS_FOR_CONNECTION", "technical_message": err_msg}}

        id1_cleaned = comp1_id_req.strip().upper() # IDs are stored uppercase
        id2_cleaned = comp2_id_req.strip().upper()

        try:
            connection_was_new = self.memory_manager.circuit.connect_components(id1_cleaned, id2_cleaned)

            if connection_was_new:
                logger.info(f"{tool_call_logger_prefix} 成功添加新连接: {id1_cleaned} <--> {id2_cleaned}")
                self.memory_manager.add_to_long_term(f"连接了元件: {id1_cleaned} <--> {id2_cleaned} (请求ID: {self.current_request_id or 'N/A'})")
                return {"status": "success", "message": f"操作成功: 已将元件 '{id1_cleaned}' 与 '{id2_cleaned}' 连接起来. ", "data": {"connection": sorted((id1_cleaned, id2_cleaned))}}
            else: # Connection already existed
                msg_exists = f"元件 '{id1_cleaned}' 和 '{id2_cleaned}' 之间已经存在连接. 无需重复操作. "
                logger.info(f"{tool_call_logger_prefix} 连接已存在: {msg_exists}")
                return {"status": "success", "message": f"注意: {msg_exists}", "data": {"connection": sorted((id1_cleaned, id2_cleaned)), "already_existed": True}}

        except ValueError as ve_connect: # Catch specific errors from circuit.connect_components
            err_msg_val = str(ve_connect)
            logger.error(f"{tool_call_logger_prefix} 连接验证错误: {err_msg_val}")
            # Determine a more specific error code based on message content
            error_code_detail = "GENERIC_CIRCUIT_VALIDATION_ERROR"
            if "不存在" in err_msg_val: error_code_detail = "COMPONENT_NOT_FOUND_FOR_CONNECTION"
            elif "连接到它自己" in err_msg_val: error_code_detail = "SELF_CONNECTION_ATTEMPTED"
            return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": error_code_detail, "technical_message": err_msg_val}}
        except Exception as e_connect: # Catch-all for unexpected issues
            err_msg = f"连接元件时发生未知的内部错误: {e_connect}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 连接元件时发生未知内部错误. ", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "CONNECT_COMPONENTS_UNEXPECTED_FAILURE", "technical_message": str(e_connect), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(description="获取当前电路的详细描述. ", parameters={"type": "object", "properties": {}}) # No arguments needed
    def describe_circuit_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-DescribeCircuitTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行描述电路操作. ")
        # arguments dict will be empty, which is fine
        try:
            description = self.memory_manager.circuit.get_state_description()
            logger.info(f"{tool_call_logger_prefix} 成功生成电路描述. ")
            return {"status": "success", "message": "已成功获取当前电路的描述. ", "data": {"description": description}}
        except Exception as e_describe:
            err_msg = f"生成电路描述时发生意外的内部错误: {e_describe}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 获取电路描述时发生未知错误. ", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "DESCRIBE_CIRCUIT_UNEXPECTED_FAILURE", "technical_message": str(e_describe), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(description="彻底清空当前的电路设计,移除所有元件和连接. ", parameters={"type": "object", "properties": {}}) # No arguments
    def clear_circuit_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-ClearCircuitTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行清空电路操作. ")
        try:
            self.memory_manager.circuit.clear()
            logger.info(f"{tool_call_logger_prefix} 电路状态已成功清空. ")
            self.memory_manager.add_to_long_term(f"执行了清空电路操作 (请求ID: {self.current_request_id or 'N/A'}). ")
            return {"status": "success", "message": "操作成功: 当前电路已彻底清空. "}
        except Exception as e_clear:
            err_msg = f"清空电路时发生意外的内部错误: {e_clear}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 清空电路时发生未知错误. ", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "CLEAR_CIRCUIT_UNEXPECTED_FAILURE", "technical_message": str(e_clear), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(
        description="从电路中移除一个指定的元件及其所有连接.",
        parameters={"type": "object", "properties": {"component_id": {"type": "string", "description": "要移除的元件的 ID."}}, "required": ["component_id"]}
    )
    def remove_component_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-RemoveComponentTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行移除元件操作.")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
        component_id_req = arguments.get("component_id")

        if not component_id_req or not isinstance(component_id_req, str) or not component_id_req.strip():
            err_msg = "必须提供一个有效的、非空的元件 ID 字符串."
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_ID_FOR_REMOVAL", "technical_message": err_msg}}

        id_cleaned = component_id_req.strip().upper()
        try:
            removed_comp_details, removed_conn_count = self.memory_manager.circuit.remove_component(id_cleaned)
            logger.info(f"{tool_call_logger_prefix} 成功移除元件 '{id_cleaned}' 及其 {removed_conn_count} 个连接.")
            self.memory_manager.add_to_long_term(f"移除了元件: ID '{id_cleaned}', 类型 '{removed_comp_details.get('type', 'N/A')}' (请求ID: {self.current_request_id or 'N/A'})")
            return {"status": "success", "message": f"操作成功: 已移除元件 '{id_cleaned}' 及其所有 {removed_conn_count} 个连接.", "data": {"removed_component": removed_comp_details, "connections_removed_count": removed_conn_count}}
        except ValueError as ve_remove: # Component not found
            err_msg_val = str(ve_remove)
            logger.error(f"{tool_call_logger_prefix} 移除验证错误: {err_msg_val}")
            return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": "COMPONENT_NOT_FOUND_FOR_REMOVAL", "technical_message": err_msg_val}}
        except Exception as e_remove:
            err_msg = f"移除元件时发生未知的内部错误: {e_remove}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 移除元件时发生未知内部错误.", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "REMOVE_COMPONENT_UNEXPECTED_FAILURE", "technical_message": str(e_remove), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(
        description="断开两个指定元件之间的连接.",
        parameters={"type": "object", "properties": {"comp1_id": {"type": "string", "description": "第一个元件的 ID."}, "comp2_id": {"type": "string", "description": "第二个元件的 ID."}}, "required": ["comp1_id", "comp2_id"]}
    )
    def disconnect_components_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-DisconnectComponentsTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行断开元件连接操作.")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
        comp1_id_req = arguments.get("comp1_id")
        comp2_id_req = arguments.get("comp2_id")

        if not comp1_id_req or not isinstance(comp1_id_req, str) or not comp1_id_req.strip() or \
           not comp2_id_req or not isinstance(comp2_id_req, str) or not comp2_id_req.strip():
            err_msg = "必须提供两个有效的、非空的元件 ID 字符串."
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_IDS_FOR_DISCONNECTION", "technical_message": err_msg}}

        id1_cleaned = comp1_id_req.strip().upper()
        id2_cleaned = comp2_id_req.strip().upper()

        if id1_cleaned == id2_cleaned: # Should be caught by Circuit class, but good to check early
            err_msg = "不能断开一个元件与它自身的连接（它们本来就不可能连接）."
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "SELF_DISCONNECTION_ATTEMPTED", "technical_message": err_msg}}
        
        try:
            # Check if components exist first, as disconnect_components might not check this explicitly
            if id1_cleaned not in self.memory_manager.circuit.components:
                raise ValueError(f"元件 '{id1_cleaned}' 在电路中不存在.")
            if id2_cleaned not in self.memory_manager.circuit.components:
                raise ValueError(f"元件 '{id2_cleaned}' 在电路中不存在.")

            disconnected_successfully = self.memory_manager.circuit.disconnect_components(id1_cleaned, id2_cleaned)
            if disconnected_successfully:
                logger.info(f"{tool_call_logger_prefix} 成功断开连接: {id1_cleaned} <--> {id2_cleaned}")
                self.memory_manager.add_to_long_term(f"断开了元件连接: {id1_cleaned} <--> {id2_cleaned} (请求ID: {self.current_request_id or 'N/A'})")
                return {"status": "success", "message": f"操作成功: 已断开元件 '{id1_cleaned}' 与 '{id2_cleaned}' 之间的连接.", "data": {"disconnected_pair": sorted((id1_cleaned, id2_cleaned))}}
            else:
                msg_not_exist = f"元件 '{id1_cleaned}' 和 '{id2_cleaned}' 之间原本就没有连接,无需断开."
                logger.info(f"{tool_call_logger_prefix} 连接不存在: {msg_not_exist}")
                return {"status": "success", "message": f"注意: {msg_not_exist}", "data": {"disconnected_pair": sorted((id1_cleaned, id2_cleaned)), "already_disconnected_or_not_connected": True}}
        except ValueError as ve_disconnect: # Catches non-existent components
            err_msg_val = str(ve_disconnect)
            logger.error(f"{tool_call_logger_prefix} 断开连接验证错误: {err_msg_val}")
            return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": "COMPONENT_NOT_FOUND_FOR_DISCONNECTION", "technical_message": err_msg_val}}
        except Exception as e_disconnect:
            err_msg = f"断开元件连接时发生未知的内部错误: {e_disconnect}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 断开元件连接时发生未知内部错误.", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "DISCONNECT_COMPONENTS_UNEXPECTED_FAILURE", "technical_message": str(e_disconnect), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(
        description="更新电路中一个已存在元件的值 (例如电阻的欧姆值, 电容的法拉值等).",
        parameters={"type": "object", "properties": {"component_id": {"type": "string", "description": "要更新值的元件的 ID."}, "new_value": {"type": "string", "description": "元件的新值. 如果要清除值,可以传入 null 或空字符串."}}, "required": ["component_id", "new_value"]}
    )
    def update_component_value_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-UpdateComponentValueTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行更新元件值操作.")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
        component_id_req = arguments.get("component_id")
        # new_value can be None if LLM passes null, or a string.
        new_value_req = arguments.get("new_value")

        if not component_id_req or not isinstance(component_id_req, str) or not component_id_req.strip():
            err_msg = "必须提供一个有效的、非空的元件 ID 字符串."
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_ID_FOR_UPDATE", "technical_message": err_msg}}
        
        # new_value is required by schema, but its content can be None (to clear) or string
        if not isinstance(new_value_req, (str, type(None))): # Allow None for clearing
            err_msg = "元件的新值 'new_value' 必须是字符串或 null (用于清除值)."
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "INVALID_NEW_VALUE_TYPE", "technical_message": err_msg}}

        id_cleaned = component_id_req.strip().upper()
        
        # Process new_value: strip if string, else it's None
        final_new_value = str(new_value_req).strip() if new_value_req is not None and str(new_value_req).strip() else None


        try:
            if id_cleaned not in self.memory_manager.circuit.components:
                raise ValueError(f"元件 '{id_cleaned}' 在电路中不存在.")
            
            component_to_update = self.memory_manager.circuit.components[id_cleaned]
            old_value = component_to_update.value
            component_to_update.value = final_new_value
            
            logger.info(f"{tool_call_logger_prefix} 成功更新元件 '{id_cleaned}' 的值从 '{old_value}' 到 '{final_new_value}'.")
            self.memory_manager.add_to_long_term(f"更新了元件 '{id_cleaned}' 的值: 旧值 '{old_value}', 新值 '{final_new_value}' (请求ID: {self.current_request_id or 'N/A'})")
            return {"status": "success", "message": f"操作成功: 元件 '{id_cleaned}' 的值已从 '{old_value if old_value else '(无值)'}' 更新为 '{final_new_value if final_new_value else '(无值)'}'.", "data": component_to_update.to_dict()}
        except ValueError as ve_update: # Component not found
            err_msg_val = str(ve_update)
            logger.error(f"{tool_call_logger_prefix} 更新值验证错误: {err_msg_val}")
            return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": "COMPONENT_NOT_FOUND_FOR_VALUE_UPDATE", "technical_message": err_msg_val}}
        except Exception as e_update:
            err_msg = f"更新元件值时发生未知的内部错误: {e_update}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 更新元件值时发生未知内部错误.", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "UPDATE_COMPONENT_VALUE_UNEXPECTED_FAILURE", "technical_message": str(e_update), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(
        description="根据提供的 ID 查找电路中的一个特定元件,并返回其详细信息.",
        parameters={"type": "object", "properties": {"component_id": {"type": "string", "description": "要查找的元件的 ID."}}, "required": ["component_id"]}
    )
    def find_component_by_id_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-FindComponentByIdTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行查找元件操作.")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
        component_id_req = arguments.get("component_id")

        if not component_id_req or not isinstance(component_id_req, str) or not component_id_req.strip():
            err_msg = "必须提供一个有效的、非空的元件 ID 字符串."
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_ID_FOR_FIND", "technical_message": err_msg}}

        id_cleaned = component_id_req.strip().upper()
        try:
            if id_cleaned in self.memory_manager.circuit.components:
                component_found = self.memory_manager.circuit.components[id_cleaned]
                logger.info(f"{tool_call_logger_prefix} 成功找到元件 '{id_cleaned}'.")
                return {"status": "success", "message": f"操作成功: 已找到元件 '{id_cleaned}'.", "data": component_found.to_dict()}
            else:
                logger.info(f"{tool_call_logger_prefix} 未找到元件 '{id_cleaned}'.")
                return {"status": "failure", "message": f"错误: 电路中不存在 ID 为 '{id_cleaned}' 的元件.", "error": {"error_type": "CIRCUIT_QUERY_ERROR", "error_code": "COMPONENT_NOT_FOUND_BY_ID", "technical_message": f"Component with ID '{id_cleaned}' not found in circuit."}}
        except Exception as e_find:
            err_msg = f"查找元件时发生未知的内部错误: {e_find}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 查找元件时发生未知内部错误.", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "FIND_COMPONENT_UNEXPECTED_FAILURE", "technical_message": str(e_find), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(
        description="列出电路中所有属于指定类型的元件.",
        parameters={"type": "object", "properties": {"component_type": {"type": "string", "description": "要筛选的元件类型 (例如: '电阻', 'LED')."}}, "required": ["component_type"]}
    )
    def list_components_by_type_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-ListComponentsByTypeTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行按类型列出元件操作.")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
        component_type_req = arguments.get("component_type")

        if not component_type_req or not isinstance(component_type_req, str) or not component_type_req.strip():
            err_msg = "必须提供一个有效的、非空的元件类型字符串."
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_TYPE_FOR_LIST", "technical_message": err_msg}}
        
        type_cleaned = component_type_req.strip() # Case-sensitive match as types are stored as provided
        
        try:
            found_components = []
            for comp in self.memory_manager.circuit.components.values():
                # Perform a case-insensitive comparison if desired, or exact match
                # For this implementation, let's assume the stored type is what we match against directly.
                # If type_cleaned is "Resistor" and component.type is "resistor", they won't match.
                # LLM should be consistent or we need a mapping here.
                # For now, let's do a case-insensitive comparison for robustness.
                if comp.type.lower() == type_cleaned.lower():
                    found_components.append(comp.to_dict())
            
            if found_components:
                logger.info(f"{tool_call_logger_prefix} 成功找到 {len(found_components)} 个类型为 '{type_cleaned}' 的元件.")
                return {"status": "success", "message": f"操作成功: 找到 {len(found_components)} 个类型为 '{type_cleaned}' 的元件.", "data": {"components": found_components, "count": len(found_components)}}
            else:
                logger.info(f"{tool_call_logger_prefix} 未找到类型为 '{type_cleaned}' 的元件.")
                return {"status": "success", "message": f"提示: 电路中没有找到类型为 '{type_cleaned}' 的元件.", "data": {"components": [], "count": 0}} # Success, but empty result
        except Exception as e_list:
            err_msg = f"按类型列出元件时发生未知的内部错误: {e_list}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 按类型列出元件时发生未知内部错误.", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "LIST_COMPONENTS_UNEXPECTED_FAILURE", "technical_message": str(e_list), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(
        description="获取指定元件连接到其他元件的数量.",
        parameters={"type": "object", "properties": {"component_id": {"type": "string", "description": "要查询连接数量的元件的 ID."}}, "required": ["component_id"]}
    )
    def get_component_connection_count_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-GetComponentConnectionCountTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行获取元件连接数操作.")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
        component_id_req = arguments.get("component_id")

        if not component_id_req or not isinstance(component_id_req, str) or not component_id_req.strip():
            err_msg = "必须提供一个有效的、非空的元件 ID 字符串."
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_ID_FOR_CONNECTION_COUNT", "technical_message": err_msg}}

        id_cleaned = component_id_req.strip().upper()
        try:
            if id_cleaned not in self.memory_manager.circuit.components:
                raise ValueError(f"元件 '{id_cleaned}' 在电路中不存在,无法查询其连接数.")
            
            connection_count = 0
            for conn_pair in self.memory_manager.circuit.connections:
                if id_cleaned in conn_pair:
                    connection_count += 1
            
            logger.info(f"{tool_call_logger_prefix} 元件 '{id_cleaned}' 有 {connection_count} 个连接.")
            return {"status": "success", "message": f"操作成功: 元件 '{id_cleaned}' 当前有 {connection_count} 个连接.", "data": {"component_id": id_cleaned, "connection_count": connection_count}}
        except ValueError as ve_count: # Component not found
            err_msg_val = str(ve_count)
            logger.error(f"{tool_call_logger_prefix} 获取连接数验证错误: {err_msg_val}")
            return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_QUERY_ERROR", "error_code": "COMPONENT_NOT_FOUND_FOR_CONNECTION_COUNT", "technical_message": err_msg_val}}
        except Exception as e_count:
            err_msg = f"获取元件连接数时发生未知的内部错误: {e_count}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 获取元件连接数时发生未知内部错误.", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "GET_CONNECTION_COUNT_UNEXPECTED_FAILURE", "technical_message": str(e_count), "exception_details": traceback.format_exc(limit=3)}}


    # --- Orchestration Layer Method (V8.3.2-CamelCaseJSON) ---
    async def process_user_request(self, user_request: str, status_callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        request_start_time = time.monotonic()
        self.current_request_id = f"req_{str(uuid4())[:12]}"

        final_llm_camelcase_json_for_reply: Optional[Dict[str, Any]] = None # V8.3.2: This will store the camelCased JSON
        final_reply_for_user: str = "抱歉,处理您的请求时发生未知错误. "
        final_llm_interaction_id_for_user: Optional[str] = None
        active_llm_interaction_id: Optional[str] = None # Tracks the ID from the most recent LLM call

        logger.info(f"\n{'='*25} CircuitAgent 开始处理用户请求 (ReqID: {self.current_request_id}) {'='*25}")
        logger.info(f"[OrchestratorV8_3_2] 收到用户指令: \"{user_request}\"")

        try:
            if not user_request or user_request.isspace():
                logger.info(f"[OrchestratorV8_3_2 - ReqID:{self.current_request_id}] 用户指令为空. ")
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "ignored", "message": "用户输入为空,已忽略. "})
                # V8.3.2: Construct an error JSON with camelCase keys
                empty_input_err_json = {
                    "requestId": self.current_request_id,
                    "llmInteractionId": f"agent_input_err_{str(uuid4())[:6]}",
                    "timestampUtc": datetime.now(timezone.utc).isoformat(),
                    "status": "failure",
                    "errorDetails": {
                        "errorType": "USER_INPUT_ERROR",
                        "errorCode": "EMPTY_USER_REQUEST",
                        "messageToUser": "您的指令似乎是空的,请重新输入！",
                        "technicalMessage": "User request was empty or whitespace.",
                        "isDirectLlmFailure": False
                    },
                    "executionPhase": "planning", # Still considered planning phase for consistency
                    "thoughtProcess": "Agent检测到用户输入为空或仅包含空白字符,无需进一步处理. ",
                    "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content": "您的指令似乎是空的,请重新输入！"}}
                }
                await status_callback({"type": "final_response", "request_id": self.current_request_id, "llm_interaction_id": empty_input_err_json["llmInteractionId"], "content": empty_input_err_json["decision"]["responseToUser"]["content"], "final_v8_3_2_camelcase_json_if_success": None})
                return

            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "received", "message": "收到用户指令,开始处理...", "details": {"user_request_preview": user_request[:1000]}})
            try:
                self.memory_manager.add_to_short_term({"role": "user", "content": user_request})
            except Exception as e_mem_user:
                logger.error(f"[OrchestratorV8_3_2 - ReqID:{self.current_request_id}] 添加用户消息到短期记忆时出错: {e_mem_user}", exc_info=True)
                err_msg_mem = f"记录用户指令时发生内部记忆错误: {e_mem_user}"
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "error", "message": err_msg_mem})
                # V8.3.2: Construct an error JSON with camelCase keys
                mem_err_json = {
                    "requestId": self.current_request_id, "llmInteractionId": f"agent_mem_err_{str(uuid4())[:6]}",
                    "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure",
                    "errorDetails": {"errorType": "INTERNAL_AGENT_ERROR", "errorCode": "MEMORY_ADD_USER_MSG_FAILED", "messageToUser": f"抱歉,我在记录您的指令时遇到了内部问题 ({e_mem_user})！请稍后重试. ", "technicalMessage": err_msg_mem, "isDirectLlmFailure": False },
                    "executionPhase": "planning", "thoughtProcess": "Agent在将用户消息添加到短期记忆时遇到错误. ",
                    "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content": f"抱歉,我在记录您的指令时遇到了内部问题 ({e_mem_user})！请稍后重试. " }}
                }
                await status_callback({"type": "final_response", "request_id": self.current_request_id, "llm_interaction_id": mem_err_json["llmInteractionId"], "content": mem_err_json["decision"]["responseToUser"]["content"], "final_v8_3_2_camelcase_json_if_success": None})
                return

            # --- Main Replanning Loop (V8.2.2 logic, adapted for V8.3.2 camelCase JSON) ---
            replanning_loop_count = 0
            current_llm_plan_camelcase_json_obj: Optional[Dict[str, Any]] = None
            tool_execution_results_for_llm_history: List[Dict[str, Any]] = [] # Stores 'tool' role messages
            agent_accepted_latest_plan_for_action = False # Flag if current plan is good to go

            while replanning_loop_count <= self.max_replanning_attempts:
                current_planning_attempt_num = replanning_loop_count + 1
                log_prefix = f"[OrchestratorV8_3_2 - PlanAttempt {current_planning_attempt_num} - ReqID: {self.current_request_id}]"
                logger.info(f"\n--- {log_prefix} 开始 ---")

                is_currently_replanning = (replanning_loop_count > 0)
                status_msg_planning_start = "正在分析指令并制定计划..." if not is_currently_replanning else f"正在尝试第 {replanning_loop_count}/{self.max_replanning_attempts} 次重规划..."
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "started", "message": status_msg_planning_start, "details": {"attempt_number": current_planning_attempt_num, "max_replanning_attempts": self.max_replanning_attempts}})

                # Prepare for LLM call (planning phase)
                memory_context = self.memory_manager.get_memory_context_for_prompt()
                tool_schemas = self._get_tool_schemas_for_prompt() # Still returns Pythonic tool schemas
                system_prompt_planning = self._get_planning_prompt_v8_3_2_camelcase_reasoning(tool_schemas, memory_context, is_currently_replanning, self.current_request_id)
                messages_for_planning = [{"role": "system", "content": system_prompt_planning}] + self.memory_manager.short_term # Add history

                llm_call_attempt_inner = 0 # Retries for the current planning LLM call
                parsed_plan_camelcase_json_this_llm_call: Optional[Dict[str, Any]] = None
                parser_error_msg_this_llm_call: str = ""
                parsed_failed_validation_points_this_llm_call: List[Dict[str,str]] = []
                agent_accepted_latest_plan_for_action = False # Reset for this planning attempt

                while llm_call_attempt_inner <= self.planning_llm_retries:
                    logger.info(f"{log_prefix} 调用规划 LLM (LLM Call Attempt {llm_call_attempt_inner + 1} of {self.planning_llm_retries + 1})...")
                    try:
                        llm_response_planning_raw = await self.llm_interface.call_llm(messages_for_planning, "planning", status_callback)
                        if not llm_response_planning_raw or not llm_response_planning_raw.choices:
                            raise ConnectionError("LLM规划响应无效或缺少choices. 这是LLMInterface层面的问题. ")

                        llm_msg_obj_planning = llm_response_planning_raw.choices[0].message
                        # Parse with V8.3.2 CamelCase parser
                        parsed_plan_camelcase_json_this_llm_call, parser_error_msg_this_llm_call, parsed_failed_validation_points_this_llm_call = \
                            self.output_parser.parse_llm_response_to_structured_json(llm_msg_obj_planning, "planning")

                        if parsed_plan_camelcase_json_this_llm_call:
                            active_llm_interaction_id = parsed_plan_camelcase_json_this_llm_call.get("llmInteractionId")
                            current_thought_process = parsed_plan_camelcase_json_this_llm_call.get("thoughtProcess")
                            if current_thought_process: # Send <think> block or JSON's thoughtProcess
                                await status_callback({"type": "thinking_log", "request_id": self.current_request_id, "llm_interaction_id": active_llm_interaction_id, "stage": "planning", "content": current_thought_process})

                        if parsed_plan_camelcase_json_this_llm_call and not parser_error_msg_this_llm_call and not parsed_failed_validation_points_this_llm_call:
                            if parsed_plan_camelcase_json_this_llm_call.get("status") == "success":
                                logger.info(f"{log_prefix} 成功解析并验证V8.3.2-CamelCaseJSON计划. LLM报告状态为 'success' (LLM_ID: {active_llm_interaction_id}). Agent采纳此计划. ")
                                agent_accepted_latest_plan_for_action = True
                            # V8.2.2 Logic: If replanning, LLM might provide new tools but mark status as failure. Agent should still try.
                            elif is_currently_replanning and \
                                 parsed_plan_camelcase_json_this_llm_call.get("decision", {}).get("isCallTools") is True and \
                                 isinstance(parsed_plan_camelcase_json_this_llm_call.get("decision", {}).get("toolCallRequests"), list) and \
                                 parsed_plan_camelcase_json_this_llm_call.get("decision", {}).get("toolCallRequests"): # Has new tools
                                logger.warning(f"{log_prefix} LLM在重规划时提供了新的工具调用计划,但可能将其顶层status标记为 'failure' (LLM_ID: {active_llm_interaction_id}). Agent将审慎采纳此新计划以尝试修正. LLM报告的错误(如有): {parsed_plan_camelcase_json_this_llm_call.get('errorDetails')}")
                                agent_accepted_latest_plan_for_action = True # Accept this plan to try the new tools
                            else: # LLM reported status: "failure" and it's not a replan with new tools
                                error_detail_from_llm = parsed_plan_camelcase_json_this_llm_call.get("errorDetails", {}).get("technicalMessage", "LLM规划指示内部错误,但JSON结构有效. ")
                                logger.warning(f"{log_prefix} LLM报告的V8.3.2-CamelCaseJSON计划状态为 'failure': {error_detail_from_llm} (LLM_ID: {active_llm_interaction_id}). Agent将不采纳此计划,并尝试让LLM修正(如果还有LLM调用重试次数). ")
                                parser_error_msg_this_llm_call = f"LLM主动报告规划失败: {error_detail_from_llm}" # This will trigger retry if possible

                            if agent_accepted_latest_plan_for_action:
                                current_llm_plan_camelcase_json_obj = parsed_plan_camelcase_json_this_llm_call
                                try: self.memory_manager.add_to_short_term(llm_msg_obj_planning.model_dump(exclude_unset=True))
                                except Exception as e_mem_add: logger.error(f"{log_prefix} 添加LLM规划响应到记忆失败: {e_mem_add}")
                                break # Break from inner LLM call retry loop

                        # If plan not accepted and can retry LLM call for planning
                        if not agent_accepted_latest_plan_for_action and llm_call_attempt_inner < self.planning_llm_retries:
                            error_to_report_cb = parser_error_msg_this_llm_call or "V8.3.2-CamelCaseJSON结构或内容校验失败. "
                            if parsed_failed_validation_points_this_llm_call:
                                error_to_report_cb += " 失败点: " + json.dumps(parsed_failed_validation_points_this_llm_call[:2], ensure_ascii=False)
                            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "llm_retry_needed", "message": f"大脑计划处理遇到问题,尝试重新沟通 ({error_to_report_cb[:1000]})", "details": {"llm_call_attempt": llm_call_attempt_inner + 1, "parser_error": parser_error_msg_this_llm_call, "validation_failures": parsed_failed_validation_points_this_llm_call}})
                            # Add context of failure to memory for LLM to correct
                            if parsed_plan_camelcase_json_this_llm_call and parsed_plan_camelcase_json_this_llm_call.get("status") == "failure":
                                try: self.memory_manager.add_to_short_term(llm_msg_obj_planning.model_dump(exclude_unset=True)) # Add LLM's own failure message
                                except Exception as e_mem_add_fail: logger.error(f"{log_prefix} 添加LLM失败规划到记忆失败: {e_mem_add_fail}")
                            elif parser_error_msg_this_llm_call or parsed_failed_validation_points_this_llm_call: # Agent-side parsing/validation error
                                 sim_err_plan_content = { # V8.3.2: camelCase keys
                                    "requestId": self.current_request_id, "llmInteractionId": f"agent_parser_err_{active_llm_interaction_id or str(uuid4())[:6]}",
                                    "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure",
                                    "errorDetails": {"errorType": "LLM_OUTPUT_VALIDATION_ERROR", "errorCode": "V8_CAMELCASE_JSON_VALIDATION_FAILED", "technicalMessage": parser_error_msg_this_llm_call, "isDirectLlmFailure": False, "failedValidationPoints": parsed_failed_validation_points_this_llm_call },
                                    "executionPhase": "planning", "thoughtProcess": "Agent在解析或验证LLM上一次规划输出时发现以下问题,将请求LLM修正. ",
                                    "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content":""}}
                                 }
                                 try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(sim_err_plan_content, ensure_ascii=False)})
                                 except Exception as e_mem_add_parse_err: logger.error(f"{log_prefix} 添加Agent解析错误到记忆失败: {e_mem_add_parse_err}")

                    except Exception as e_llm_call_level: # Serious error in LLM call itself or unexpected parser error
                        logger.error(f"{log_prefix} LLM调用或规划解析时发生严重错误 (LLM Call Attempt {llm_call_attempt_inner + 1}): {e_llm_call_level}", exc_info=True)
                        parser_error_msg_this_llm_call = f"LLM调用/解析严重错误: {str(e_llm_call_level)[:1000]}"
                        parsed_failed_validation_points_this_llm_call = [{"jsonPath":"root", "issue_description": parser_error_msg_this_llm_call}]
                        if llm_call_attempt_inner < self.planning_llm_retries:
                             await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "llm_error_retrying", "message": f"与大脑沟通时发生严重错误,尝试重新连接 ({parser_error_msg_this_llm_call})", "details": {"llm_call_attempt": llm_call_attempt_inner + 1}})
                    # --- End of LLM call try-except ---

                    llm_call_attempt_inner += 1
                    if agent_accepted_latest_plan_for_action: break # Exit inner LLM call loop
                # --- End of inner LLM call retry loop ---

                if not agent_accepted_latest_plan_for_action: # Failed to get a usable plan even after LLM retries
                    error_summary_final_planning_llm_attempt = parser_error_msg_this_llm_call or "在多次LLM调用尝试后,未能从LLM获取可接受的V8.3.2-CamelCaseJSON规划. "
                    if parsed_failed_validation_points_this_llm_call:
                         error_summary_final_planning_llm_attempt += " 最后一次校验失败点: " + json.dumps(parsed_failed_validation_points_this_llm_call[:2], ensure_ascii=False)

                    await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "failed_after_llm_retries", "message": f"规划失败 (在第 {current_planning_attempt_num} 次规划尝试中,LLM调用重试均失败): {error_summary_final_planning_llm_attempt}", "details": {"final_parser_error": parser_error_msg_this_llm_call, "final_validation_failures": parsed_failed_validation_points_this_llm_call, "thinking_log_from_last_attempt": parsed_plan_camelcase_json_this_llm_call.get("thoughtProcess") if parsed_plan_camelcase_json_this_llm_call else "无有效思考过程"}})

                    if replanning_loop_count >= self.max_replanning_attempts: # Max replanning attempts reached
                        logger.critical(f"{log_prefix} 已达最大重规划尝试次数 ({self.max_replanning_attempts}),且本次规划尝试在LLM调用/解析层面最终失败. 中止处理. ")
                        final_reply_for_user = f"抱歉,即使经过多次尝试与智能大脑沟通,也未能为您的请求 '{user_request[:50]}...' 制定出有效的执行计划. 错误详情: {error_summary_final_planning_llm_attempt}"
                        final_llm_interaction_id_for_user = active_llm_interaction_id or f"error_plan_max_replan_llm_fail_{str(uuid4())[:6]}"
                        final_llm_camelcase_json_for_reply = None # No valid JSON to return
                        break # Exit main replanning loop
                    else: # Can still try replanning (outer loop)
                        # Add a message to memory indicating failure of this planning attempt to guide next replan
                        sim_fail_plan_content_for_replan = { # V8.3.2: camelCase
                            "requestId": self.current_request_id, "llmInteractionId": f"agent_replan_trigger_{active_llm_interaction_id or str(uuid4())[:6]}",
                            "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure",
                            "errorDetails": {"errorType": "LLM_OUTPUT_VALIDATION_ERROR", "errorCode": "V8_CAMELCASE_JSON_VALIDATION_FAILED_IN_PLAN_ATTEMPT", "technicalMessage": error_summary_final_planning_llm_attempt, "isDirectLlmFailure": False, "failedValidationPoints": parsed_failed_validation_points_this_llm_call },
                            "executionPhase": "planning", "thoughtProcess": f"Agent在第 {current_planning_attempt_num} 次规划尝试的LLM调用/解析阶段遇到问题,将进行重规划. 错误: {error_summary_final_planning_llm_attempt}",
                            "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content":""}}
                        }
                        try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(sim_fail_plan_content_for_replan, ensure_ascii=False)})
                        except Exception as e_mem_add_replan_trigger: logger.error(f"{log_prefix} 添加重规划触发信息到记忆出错: {e_mem_add_replan_trigger}")
                        replanning_loop_count += 1
                        continue # Continue to next iteration of main replanning loop
                # --- End of if not agent_accepted_latest_plan_for_action ---

                # If we reach here, a valid plan (current_llm_plan_camelcase_json_obj) was accepted
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "completed_and_validated", "message": "规划完成并通过验证,准备执行或直接回复. ", "details": {"plan_llm_id": current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else None}})

                # Extract tool requests for UI display (if any)
                tool_requests_from_plan = current_llm_plan_camelcase_json_obj.get("decision", {}).get("toolCallRequests", []) if current_llm_plan_camelcase_json_obj else []
                if isinstance(tool_requests_from_plan, list) and current_llm_plan_camelcase_json_obj:
                    plan_details_for_ui = []
                    for req_idx, tool_req in enumerate(tool_requests_from_plan):
                        plan_details_for_ui.append({ # Keys for UI can be snake_case
                            "tool_call_id": tool_req.get("toolCallId"),
                            "tool_name": tool_req.get("toolName"),
                            "tool_arguments": tool_req.get("toolArguments", {}), # Content is tool-specific
                            "ui_hints": tool_req.get("uiHints", {}),
                            "status": "pending", # Initial status for UI
                            "order": req_idx + 1
                        })
                    await status_callback({
                        "type": "plan_details",
                        "request_id": self.current_request_id,
                        "llm_interaction_id": current_llm_plan_camelcase_json_obj.get("llmInteractionId"),
                        "plan": plan_details_for_ui
                    })

                decision_from_plan = current_llm_plan_camelcase_json_obj.get("decision", {}) if current_llm_plan_camelcase_json_obj else {}
                should_call_tools = decision_from_plan.get("isCallTools", False) # This is already a Python boolean due to robust parsing
                response_user_obj_from_plan = decision_from_plan.get("responseToUser")

                if should_call_tools:
                    tool_count_in_plan = len(tool_requests_from_plan) if isinstance(tool_requests_from_plan, list) else 0
                    logger.info(f"{log_prefix} 决策: 执行 {tool_count_in_plan} 个工具. ")
                    await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "action_execution", "status": "started", "message": f"开始执行 {tool_count_in_plan} 个计划操作...", "details": {"tool_count": tool_count_in_plan}})

                    # Provide transitional reply if available
                    if isinstance(response_user_obj_from_plan, dict) and response_user_obj_from_plan.get("content","").strip():
                        transitional_reply_content = response_user_obj_from_plan["content"]
                        await status_callback({"type": "interim_response", "request_id": self.current_request_id, "llm_interaction_id": current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else None, "content": transitional_reply_content})

                    # Sanity check: isCallTools is True, but toolCallRequests is empty/invalid (should be caught by parser)
                    if not isinstance(tool_requests_from_plan, list) or not tool_requests_from_plan:
                        err_msg_list_tools_critical = "内部规划错误: isCallTools为True但toolCallRequests列表无效或为空. OutputParser应已校验. "
                        logger.error(f"{log_prefix} {err_msg_list_tools_critical}")
                        # Simulate a tool failure for LLM history to trigger replan
                        tool_execution_results_for_llm_history = [{"role":"tool", "tool_call_id":f"plan_integrity_err_{str(uuid4())[:6]}", "name":"plan_integrity_checker", "content":json.dumps({"status":"failure", "message":err_msg_list_tools_critical, "error": {"error_type":"INTERNAL_AGENT_ERROR", "error_code":"INVALID_TOOL_REQUEST_LIST_POST_VALIDATION", "technical_message": err_msg_list_tools_critical}})}]
                        try: self.memory_manager.add_to_short_term(tool_execution_results_for_llm_history[0])
                        except Exception as e_mem_add_integrity_err: logger.error(f"{log_prefix} 添加规划完整性错误到记忆失败: {e_mem_add_integrity_err}")

                        if replanning_loop_count >= self.max_replanning_attempts:
                            final_reply_for_user = f"抱歉,系统在准备执行操作时遇到内部规划结构问题. 请稍后重试或联系技术支持. 错误: {err_msg_list_tools_critical}"
                            final_llm_interaction_id_for_user = current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id
                            final_llm_camelcase_json_for_reply = None
                            break # Exit main replanning loop
                        else: # Trigger replan
                            replanning_loop_count += 1; agent_accepted_latest_plan_for_action = False; continue

                    # Execute tools
                    current_tool_exec_results_for_llm_hist = await self.tool_executor.execute_tool_calls(tool_requests_from_plan, status_callback)
                    tool_execution_results_for_llm_history = current_tool_exec_results_for_llm_hist # Accumulate results

                    # Add tool execution results to short-term memory
                    if tool_execution_results_for_llm_history:
                        for res_msg_tool in tool_execution_results_for_llm_history:
                            try: self.memory_manager.add_to_short_term(res_msg_tool)
                            except Exception as e_mem_add_tool_res: logger.error(f"{log_prefix} 添加工具结果 {res_msg_tool.get('tool_call_id')} 到记忆失败: {e_mem_add_tool_res}")

                    # Check if any tool failed persistently
                    any_tool_failed_persistently = False
                    last_failed_tool_message_for_user = "一个或多个操作未能成功完成. " # Default message
                    if tool_execution_results_for_llm_history:
                        for tool_res_for_hist in tool_execution_results_for_llm_history:
                            try:
                                tool_res_content_dict = json.loads(tool_res_for_hist.get("content","{}"))
                                if tool_res_content_dict.get("status") != "success":
                                    any_tool_failed_persistently = True
                                    last_failed_tool_message_for_user = tool_res_content_dict.get("message", last_failed_tool_message_for_user) # Get specific error
                            except json.JSONDecodeError: # Should not happen if tools return valid JSON string
                                logger.error(f"{log_prefix} 无法解析工具结果的content JSON: {tool_res_for_hist.get('content')}")
                                any_tool_failed_persistently = True
                                last_failed_tool_message_for_user = "一个操作的结果格式不正确. "

                    if any_tool_failed_persistently:
                        logger.warning(f"{log_prefix} 工具执行过程中发生了一个或多个持久性失败. ")
                        await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "action_execution", "status": "tool_failure_detected", "message": "部分操作失败,准备评估是否重规划. ", "details": {"last_error_message": last_failed_tool_message_for_user}})
                        if replanning_loop_count < self.max_replanning_attempts:
                            replanning_loop_count += 1; agent_accepted_latest_plan_for_action = False; continue # Trigger replan
                        else: # Max replans reached, and tools still failed
                            logger.critical(f"{log_prefix} 已达最大重规划尝试次数 ({self.max_replanning_attempts}),但工具执行仍有失败. 中止处理. ")
                            final_reply_for_user = f"抱歉,在执行您的请求时,即使经过多次尝试,仍遇到问题: {last_failed_tool_message_for_user} 请检查您的指令或稍后再试. "
                            final_llm_interaction_id_for_user = current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id
                            final_llm_camelcase_json_for_reply = None
                            break # Exit main replanning loop
                    else: # All tools succeeded
                        logger.info(f"{log_prefix} 所有计划中的工具均成功执行. 准备生成最终回复. ")
                        final_llm_camelcase_json_for_reply = current_llm_plan_camelcase_json_obj # This plan led to successful tool exec
                        break # Exit replanning loop, proceed to response generation

                else: # No tools to call (isCallTools is False)
                    logger.info(f"{log_prefix} 决策: 直接回复 (V8.3.2-CamelCaseJSON). 无需工具调用. ")
                    # This means the planning phase decided to directly answer.
                    # The content for the user should be in current_llm_plan_camelcase_json_obj.decision.responseToUser.content
                    if isinstance(response_user_obj_from_plan, dict) and response_user_obj_from_plan.get("content","").strip():
                        tool_execution_results_for_llm_history = [] # No tools were called
                        final_llm_camelcase_json_for_reply = current_llm_plan_camelcase_json_obj # This plan IS the final response
                        logger.info(f"{log_prefix} 规划阶段决定直接回复,内容有效. 将使用此V8.3.2-CamelCaseJSON作为最终输出. LLM_ID: {final_llm_camelcase_json_for_reply.get('llmInteractionId')}")
                        break # Exit replanning loop, this IS the final answer.
                    else: # isCallTools is False, but content is empty (should be caught by parser)
                        err_msg_direct_content_critical = "内部规划错误: isCallTools为False但responseToUser.content无效或为空. OutputParser应已校验. "
                        logger.error(f"{log_prefix} {err_msg_direct_content_critical}")
                        # Simulate an "error" to potentially trigger replan if LLM made a mistake
                        tool_execution_results_for_llm_history = [{"role":"tool", "tool_call_id":f"direct_reply_integrity_err_{str(uuid4())[:6]}", "name":"direct_reply_integrity_checker", "content":json.dumps({"status":"failure", "message":err_msg_direct_content_critical, "error": {"error_type":"INTERNAL_AGENT_ERROR", "error_code":"INVALID_DIRECT_RESPONSE_CONTENT_POST_VALIDATION", "technical_message": err_msg_direct_content_critical}})}]
                        try: self.memory_manager.add_to_short_term(tool_execution_results_for_llm_history[0])
                        except Exception as e_mem_add_direct_reply_err: logger.error(f"{log_prefix} 添加直接回复完整性错误到记忆失败: {e_mem_add_direct_reply_err}")

                        if replanning_loop_count >= self.max_replanning_attempts:
                            final_reply_for_user = f"抱歉,系统在准备直接回复时遇到内部规划结构问题. 请稍后重试或联系技术支持. 错误: {err_msg_direct_content_critical}"
                            final_llm_interaction_id_for_user = current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id
                            final_llm_camelcase_json_for_reply = None
                            break # Exit replanning loop
                        else: # Trigger replan
                            replanning_loop_count += 1; agent_accepted_latest_plan_for_action = False; continue
                # --- End of if should_call_tools ---
            # --- End of Main Replanning Loop ---
            logger.debug(f"[OrchestratorV8_3_2 - ReqID:{self.current_request_id}] Replanning loop ended. Accepted plan: {agent_accepted_latest_plan_for_action}, Replan count: {replanning_loop_count}, Final LLM JSON for reply is set: {final_llm_camelcase_json_for_reply is not None}")
            
            # If max replans reached and still no accepted plan (e.g., last plan attempt failed LLM call retries)
            if not agent_accepted_latest_plan_for_action and replanning_loop_count > self.max_replanning_attempts:
                logger.error(f"[OrchestratorV8_3_2 - FinalPrep - ReqID:{self.current_request_id}] 已达最大重规划次数,且最终规划尝试仍失败. 将使用上次记录的错误信息. ")
                # final_reply_for_user and final_llm_interaction_id_for_user should be set from the failure path within the loop.
                # final_llm_camelcase_json_for_reply remains None.
            
            logger.debug(f"[OrchestratorV8_3_2 - ReqID:{self.current_request_id}] Before response gen check. Final JSON status: {final_llm_camelcase_json_for_reply.get('status') if final_llm_camelcase_json_for_reply else 'N/A'}, isCallTools: {final_llm_camelcase_json_for_reply.get('decision', {}).get('isCallTools') if final_llm_camelcase_json_for_reply else 'N/A'}")

            # If plan was to call tools AND tools executed successfully, we need to call LLM for a final response.
            if final_llm_camelcase_json_for_reply and \
               final_llm_camelcase_json_for_reply.get("status") == "success" and \
               final_llm_camelcase_json_for_reply.get("decision",{}).get("isCallTools") is True: # isCallTools from robust parsing
                logger.info(f"[OrchestratorV8_3_2 - ReqID:{self.current_request_id}] 工具执行成功,开始生成最终响应...")
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "response_generation", "status": "started", "message": "正在总结操作结果并生成最终回复...", "details": {"reason": "Tool execution completed successfully. Generating final summary."}})

                system_prompt_resp_gen = self._get_response_generation_prompt_v8_3_2_camelcase_reasoning(
                    self.memory_manager.get_memory_context_for_prompt(), # Fresh context
                    self._get_tool_schemas_for_prompt(),
                    self.current_request_id
                )
                messages_for_resp_gen = [{"role": "system", "content": system_prompt_resp_gen}] + self.memory_manager.short_term # Full history including tool results

                try:
                    llm_response_final_gen_raw = await self.llm_interface.call_llm(messages_for_resp_gen, "response_generation", status_callback)
                    if not llm_response_final_gen_raw or not llm_response_final_gen_raw.choices: raise ConnectionError("LLM最终响应生成阶段的响应无效或缺少choices. ")

                    llm_msg_obj_final_gen = llm_response_final_gen_raw.choices[0].message
                    parsed_final_camelcase_resp_json, final_parser_err_resp, final_validation_failures_resp = \
                        self.output_parser.parse_llm_response_to_structured_json(llm_msg_obj_final_gen, "response_generation")

                    if parsed_final_camelcase_resp_json:
                        active_llm_interaction_id = parsed_final_camelcase_resp_json.get("llmInteractionId")
                        final_resp_thought_process = parsed_final_camelcase_resp_json.get("thoughtProcess")
                        if final_resp_thought_process:
                             await status_callback({"type": "thinking_log", "request_id": self.current_request_id, "llm_interaction_id": active_llm_interaction_id, "stage": "response_generation", "content": final_resp_thought_process})

                    if parsed_final_camelcase_resp_json and not final_parser_err_resp and not final_validation_failures_resp and parsed_final_camelcase_resp_json.get("status") == "success":
                        final_llm_camelcase_json_for_reply = parsed_final_camelcase_resp_json # This is the definitive final JSON
                        final_llm_interaction_id_for_user = active_llm_interaction_id
                        logger.info(f"[OrchestratorV8_3_2 - ReqID:{self.current_request_id}] 成功解析并验证最终响应V8.3.2-CamelCaseJSON (LLM_ID: {final_llm_interaction_id_for_user}). ")
                        try: self.memory_manager.add_to_short_term(llm_msg_obj_final_gen.model_dump(exclude_unset=True))
                        except Exception as e_mem_add_final_resp: logger.error(f"添加最终LLM响应到记忆失败: {e_mem_add_final_resp}")
                    else: # Failed to get a valid JSON for final response
                        err_msg_final_resp_gen = final_parser_err_resp or "V8.3.2-CamelCaseJSON最终响应JSON校验失败. "
                        if final_validation_failures_resp: err_msg_final_resp_gen += " 失败点: " + json.dumps(final_validation_failures_resp[:2], ensure_ascii=False)
                        elif parsed_final_camelcase_resp_json and parsed_final_camelcase_resp_json.get("status") == "failure": # LLM itself reported failure
                             err_msg_final_resp_gen = parsed_final_camelcase_resp_json.get("errorDetails",{}).get("technicalMessage", err_msg_final_resp_gen)

                        logger.error(f"[OrchestratorV8_3_2 - ReqID:{self.current_request_id}] LLM未能生成有效V8.3.2-CamelCaseJSON最终回复: {err_msg_final_resp_gen}")
                        final_reply_for_user = f"抱歉,在总结操作结果时发生了一些问题. 错误: {err_msg_final_resp_gen[:1000]}... "
                        # Use the LLM ID from this failed attempt, or fallback to previous planning ID
                        final_llm_interaction_id_for_user = active_llm_interaction_id or (final_llm_camelcase_json_for_reply.get("llmInteractionId") if final_llm_camelcase_json_for_reply else f"error_resp_gen_{str(uuid4())[:6]}")
                        final_llm_camelcase_json_for_reply = None # Mark as no valid final JSON
                except Exception as e_llm_final_gen_call: # Severe error in LLM call for response gen
                    logger.critical(f"[OrchestratorV8_3_2 - ReqID:{self.current_request_id}] LLM最终响应调用或处理失败: {e_llm_final_gen_call}", exc_info=True)
                    final_reply_for_user = f"抱歉,系统在为您准备最终报告时遇到了严重的内部错误: {str(e_llm_final_gen_call)[:1000]}... "
                    final_llm_interaction_id_for_user = (final_llm_camelcase_json_for_reply.get("llmInteractionId") if final_llm_camelcase_json_for_reply else active_llm_interaction_id or f"critical_err_resp_gen_{str(uuid4())[:6]}")
                    final_llm_camelcase_json_for_reply = None # Mark as no valid final JSON
            
            # Case: Planning phase decided on a direct reply (isCallTools was False)
            elif final_llm_camelcase_json_for_reply and \
                 final_llm_camelcase_json_for_reply.get("status") == "success" and \
                 final_llm_camelcase_json_for_reply.get("decision",{}).get("isCallTools") is False:
                logger.info(f"[OrchestratorV8_3_2 - ReqID:{self.current_request_id}] 使用规划阶段的直接回复V8.3.2-CamelCaseJSON作为最终输出. ")
                final_llm_interaction_id_for_user = final_llm_camelcase_json_for_reply.get("llmInteractionId")
                # final_llm_camelcase_json_for_reply is already set correctly.

            # Case: Processing failed before a final JSON could be established
            elif not final_llm_camelcase_json_for_reply :
                 logger.error(f"[OrchestratorV8_3_2 - ReqID:{self.current_request_id}] 流程结束时,final_llm_camelcase_json_for_reply 为空,表明处理失败. 将使用之前记录的错误信息 (final_reply_for_user). ")
                 # final_reply_for_user and final_llm_interaction_id_for_user should have been set in the failure path.

            # --- Prepare final user-facing response from the determined JSON or error message ---
            user_facing_thought_process_final_summary = "综合思考过程已在之前的日志中发送. " # Default if no better found
            if final_llm_camelcase_json_for_reply and final_llm_camelcase_json_for_reply.get("status") == "success":
                # Extract thought process and content from the final successful JSON
                user_facing_thought_process_final_summary = final_llm_camelcase_json_for_reply.get("thoughtProcess", user_facing_thought_process_final_summary)
                resp_user_obj_final = final_llm_camelcase_json_for_reply.get("decision", {}).get("responseToUser", {})
                final_reply_for_user = resp_user_obj_final.get("content", final_reply_for_user) # Use content from JSON if available
            
            # Send final status and response to UI/callback
            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "finalization", "status": "completed" if (final_llm_camelcase_json_for_reply and final_llm_camelcase_json_for_reply.get("status") == "success") else "failed", "message": "请求处理流程已结束." })
            await status_callback({
                "type": "final_response",
                "request_id": self.current_request_id,
                "llm_interaction_id": final_llm_interaction_id_for_user,
                "content": final_reply_for_user.strip() if final_reply_for_user else "抱歉,未能生成有效的回复. ", # Ensure some content
                "final_v8_3_2_camelcase_json_if_success": final_llm_camelcase_json_for_reply # Pass the final JSON (or None if failed)
            })

            # If the overall process resulted in a failure (no successful final JSON), add a synthetic error message to memory
            if not (final_llm_camelcase_json_for_reply and final_llm_camelcase_json_for_reply.get("status") == "success"):
                final_assistant_synthetic_error_message_camelcase_json = { # V8.3.2: camelCase
                    "requestId": self.current_request_id,
                    "llmInteractionId": final_llm_interaction_id_for_user or f"agent_synth_final_err_{str(uuid4())[:6]}",
                    "timestampUtc": datetime.now(timezone.utc).isoformat(),
                    "status": "failure",
                    "errorDetails": {"errorType": "AGENT_PROCESSING_FAILURE", "errorCode": "OVERALL_REQUEST_HANDLING_FAILED", "messageToUser": final_reply_for_user, "technicalMessage": "Agent failed to successfully complete the user request after all attempts.", "isDirectLlmFailure": False },
                    "executionPhase": "final_error_synthesis",
                    "thoughtProcess": user_facing_thought_process_final_summary or "Agent 最终处理失败,未能生成详细思考过程. ",
                    "decision": {"isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content": final_reply_for_user}}
                }
                try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(final_assistant_synthetic_error_message_camelcase_json, ensure_ascii=False)})
                except Exception as e_mem_add_synth_err: logger.error(f"添加Agent合成的最终错误助手消息到记忆失败: {e_mem_add_synth_err}")

        except Exception as e_process_top_level: # Catch-all for any unhandled exceptions in the main flow
            request_id_for_fatal = self.current_request_id or f"fatal_err_no_req_id_{str(uuid4())[:6]}"
            logger.critical(f"[OrchestratorV8_3_2 - ReqID:{request_id_for_fatal}] 处理用户请求 '{user_request[:1000]}' 时发生顶层未捕获异常: {e_process_top_level}", exc_info=True)
            error_msg_for_user_fatal = f"抱歉,处理您的请求 ('{user_request[:30]}...') 时发生严重的、未预期的内部系统错误. 请稍后再试或联系技术支持. "
            tb_str_for_thinking_log_fatal = traceback.format_exc().replace('\n', ' | ') # Compact traceback for log
            thinking_log_content_fatal = f"请求处理流程中发生顶层致命错误: {e_process_top_level}. Traceback (部分): {tb_str_for_thinking_log_fatal[:1000]}..."

            fatal_llm_interaction_id = f"fatal_agent_err_{str(uuid4())[:6]}"
            # Send detailed error info via callbacks
            await status_callback({"type": "thinking_log", "request_id": request_id_for_fatal, "llm_interaction_id": fatal_llm_interaction_id, "stage": "fatal_error_capture", "content": thinking_log_content_fatal})
            await status_callback({"type": "general_status", "request_id": request_id_for_fatal, "stage": "fatal_error_handler", "status": "error", "message": f"请求处理失败,发生致命内部错误: {str(e_process_top_level)[:1000]}", "details": {"error_type": type(e_process_top_level).__name__, "full_error_message": str(e_process_top_level)}})
            await status_callback({"type": "final_response", "request_id": request_id_for_fatal, "llm_interaction_id": fatal_llm_interaction_id, "content": error_msg_for_user_fatal, "final_v8_3_2_camelcase_json_if_success": None})
        finally:
            request_end_time = time.monotonic()
            duration_total = request_end_time - request_start_time
            logger.info(f"\n{'='*25} CircuitAgent 请求处理完毕 (ReqID: {self.current_request_id or 'N/A'}, 总耗时: {duration_total:.3f} 秒) {'='*25}\n")
            self.current_request_id = None # Clear request ID for next run


    # --- Helper Methods for Prompts (V8.3.2-CamelCaseJSON - Adapted for <think> tags and glm-z1-flash) ---
    def _get_tool_schemas_for_prompt(self) -> str:
        if not self.tools_registry: return "  (当前无可用工具)"
        tool_schemas_parts = []
        # Sort tools by name for consistent prompt generation
        sorted_tool_names = sorted(self.tools_registry.keys())

        for tool_name in sorted_tool_names:
            schema = self.tools_registry[tool_name]
            desc = schema.get('description', '无描述. ')
            params_schema = schema.get('parameters', {}) # This is the schema for tool_arguments content
            props_schema = params_schema.get('properties', {}) # e.g., {"component_type": ..., "component_id": ...}
            req_params = params_schema.get('required', []) # e.g., ["component_type"]

            param_desc_segments = []
            if props_schema:
                # Sort parameter names for consistent prompt generation
                sorted_param_names = sorted(props_schema.keys())
                for param_name in sorted_param_names: 
                    param_details_dict = props_schema[param_name]
                    param_type = param_details_dict.get('type','any')
                    is_required_str = "必须 (required)" if param_name in req_params else "可选 (optional)"
                    param_description = param_details_dict.get('description','无参数描述')
                    enum_values = param_details_dict.get('enum')
                    enum_desc = f" 可选值: {enum_values}." if enum_values and isinstance(enum_values, list) else ""
                    # LLM should use these snake_case names (e.g. component_type) *inside* the toolArguments object
                    param_desc_segments.append(f"    - 参数名 `{param_name}`:\n      - 类型: `{param_type}`\n      - 是否必需: {is_required_str}\n      - 描述: {param_description}{enum_desc}")
            elif params_schema.get("type") == "object" and not props_schema : # Tool takes an empty {}
                 param_desc_segments = ["    - 此工具不接受任何参数(参数对象 `toolArguments` 应为空对象 `{}`). "]
            else: # Should not happen for well-defined tools
                 param_desc_segments = ["    - (此工具的参数定义似乎不完整或无参数)"]

            # Tool name in prompt (for LLM to use in toolName field) should match Python function name
            tool_schemas_parts.append(f"  - 工具名称: `{tool_name}`\n    工具描述: {desc}\n  工具参数详情 (这些参数应放在 `toolArguments` 对象内部):\n{chr(10).join(param_desc_segments)}")
        return "\n\n".join(tool_schemas_parts)

    def _get_planning_prompt_v8_3_2_camelcase_reasoning(self, tool_schemas_desc: str, memory_context: str,
                                is_replanning: bool = False, request_id: Optional[str] = None) -> str:
        current_timestamp_utc = datetime.now(timezone.utc).isoformat()
        llm_interaction_id_example_plan_prefix = f"plan_ex_llm_id_{str(uuid4())[:6]}"
        example_prev_tool_call_id = f"tc_ex_prev_fail_{str(uuid4())[:6]}" # This example ID is camelCase as it would be in LLM's JSON output

        reasoning_model_instructions = (
            "\n【重要: Reasoning Model 输出规范 (V8.3.2-CamelCaseJSON)】\n" # Updated version
            "1.  **思考过程**: 您的详细思考过程、分析、逐步推理和决策逻辑【必须】包含在 `<think>...</think>` 标签内,并放在您回复的最开始部分。\n"
            "2.  **JSON 输出**: 在 `</think>` 标签之后,您【必须】输出一个严格符合下面描述的V8.3.2-CamelCaseJSON格式的单个JSON对象。此JSON对象应被三个反引号和'json'标记包围 (即 ```json ... ```)。JSON中所有key【必须】使用camelCase (例如: `isCallTools`, `toolCallRequests`, `requestId`).\n"
            "3.  **`thoughtProcess` 字段 (in JSON)**: JSON对象内部的 `thoughtProcess` 字段现在是次要的。它可以是一个简短的总结或留空 ( `\"\"` ),因为您的主要思考过程已在 `<think>...</think>` 块中。Agent将优先使用 `<think>` 块中的内容作为思考日志。\n"
        )

        replanning_guidance_v8_3_2 = "" # Adapted for camelCase
        if is_replanning:
            replanning_guidance_v8_3_2 = (
                "\n【重要: 重规划指示 (V8.3.2-CamelCaseJSON - Reasoning Model)】\n"
                "您当前正在进行重规划。这意味着您之前的规划或工具执行遇到了问题。请在您的 `<think>...</think>` 块中：\n"
                "1.  **仔细分析失败原因**: 详细检查对话历史中的 `role: tool` 消息 (`content` JSON内的 `status: \"failure\"`, `message`, `errorDetails`) 和 `role: assistant` 消息中可能的Agent解析/校验错误 (`errorDetails.failedValidationPoints`)。\n"
                "2.  **参考当前电路状态**: 【务必】仔细查阅 `memory_context` 中的【当前电路状态】。您的新计划【必须】基于当前实际存在的元件和连接。不要不必要地重新添加已存在的元件。\n"
                "3.  **处理抽象节点**: 若涉及连接到 'INPUT', 'OUTPUT', 'GND' 等未作为元件存在的抽象节点失败,优先规划使用 `add_component_tool` (如 `component_type: 'Terminal'`) 创建它们,然后再连接。\n"
                "4.  **制定修正计划**: 基于以上分析,制定一个【全新的、修正了先前问题的计划】。这应在您的 `<think>...</think>` 块中清晰阐述。\n"
                "然后,在 `</think>` 之后输出符合V8.3.2-CamelCaseJSON规范的JSON。如果这个【新JSON本身的顶层 `status` 字段必须设置为 `'success'`】(因为您成功地为【当前这次思考和规划】输出了一个结构完整且逻辑合理的V8.3.2-CamelCaseJSON JSON)。\n"
                "5.  **无法解决的情况**: 如果分析后认为无法完成用户核心请求,则在 `<think>...</think>` 中解释,并在 `</think>` 后的JSON中制定一个【直接回复用户并解释情况的计划】 (`status: 'success'`, `isCallTools: False`).\n"
                "6.  **真正意义上的规划失败**: 只有当您在【当前这次重规划尝试中】,由于自身的理解困难、无法形成任何有效的 `<think>...</think>` 块或后续的V8.3.2-CamelCaseJSON JSON结构时,才应将后续JSON的顶层 `status` 字段设为 `'failure'`。\n"
                "**核心原则**: 不要因为*过去*的工具执行失败,就将您*当前新制定*的计划的JSON标记为 `status: 'failure'`. `status` 反映的是您【当前这次生成JSON这个行为本身】的成功与否。\n"
            )

        v8_3_2_camelcase_json_schema_description_for_prompt = """
```json
{
  "requestId": "string_or_null_current_user_request_cycle_id_echo_this_value_from_system_prompt_s_context_information_if_provided_otherwise_null",
  "llmInteractionId": "string_MUST_BE_UNIQUE_id_for_this_llm_response_e.g.,_plan_llm_id_followed_by_8_random_chars_like_plan_llm_id_a1b2c3d4",
  "timestampUtc": "string_current_utc_timestamp_in_iso_8601_format_e.g.,_2024-07-16T12:00:00.000Z",
  "status": "string_MUST_BE_either_'success'_or_'failure'._Indicates_if_THIS_SPECIFIC_JSON_OUTPUT_was_successfully_generated_by_LLM_for_the_current_phase.",
  "errorDetails": { // Null if status is 'success'
    "errorType": "string_enum_HIGH_LEVEL_ERROR_CATEGORY_e.g._PLANNING_ERROR_LLM_OUTPUT_VALIDATION_ERROR_INTERNAL_LOGIC_ERROR",
    "errorCode": "string_SPECIFIC_ERROR_CODE_e.g._JSON_MALFORMED_MISSING_REQUIRED_FIELD_TOOL_PARAMS_INVALID_REPLAN_MAX_ATTEMPTS_REACHED",
    "messageToUser": "string_A_user_friendly_explanation_if_this_error_is_directly_related_to_user_action_or_if_a_user_facing_message_is_appropriate_otherwise_generic_agent_error_message.",
    "technicalMessage": "string_Detailed_technical_error_message_for_logging_and_debugging_This_is_what_LLM_thinks_went_wrong_with_its_OWN_output_generation_process.",
    "isDirectLlmFailure": "boolean_True_if_LLM_explicitly_states_it_cannot_fulfill_request_or_generate_valid_JSON_FOR_THIS_ATTEMPT_False_if_error_is_due_to_Agent_side_validation_of_an_otherwise_syntactically_valid_LLM_JSON_output_or_if_LLM_is_reporting_a_logical_failure_in_a_well_formed_JSON.",
    "failedValidationPoints": [ // Optional, list of validation issues found by Agent if LLM is correcting its own previous output based on Agent feedback
      {
        "jsonPath": "string_e.g._decision.toolCallRequests[0].toolArguments.component_id", // Note: component_id itself is snake_case as per tool schema
        "issue_description": "string_e.g._Required_field_missing_or_Value_must_be_a_string_but_got_integer"
      }
    ]
  },
  "executionPhase": "string_MUST_BE_'planning'_for_this_task",
  "thoughtProcess": "string_THIS_FIELD_IS_NOW_SECONDARY_Your_primary_detailed_reasoning_MUST_be_in_the_initial_`<think>...</think>`_block_This_JSON_field_can_be_a_brief_summary_or_empty_The_Agent_will_prioritize_the_`<think>`_block_content.",
  "decision": {
    "isCallTools": "boolean_True_if_tools_are_to_be_called_False_otherwise_Accepts_string_true_false_case_insensitive_as_well",
    "toolCallRequests": [ // Null or empty list if isCallTools is False
      {
        "toolCallId": "string_UNIQUE_ID_generated_by_YOU_for_this_specific_tool_call_e.g._tc_add_resistor_xyz123",
        "toolName": "string_name_of_the_tool_to_be_called_from_available_list (e.g., add_component_tool)",
        "toolArguments": { 
            Content of this object is tool-specific, keys here (e.g. component_type, value)
            should match the snake_case names from the '可用工具列表与参数规范' section.
            Example: "component_type": "电阻", "value": "1k"
        },
        "uiHints": { // Optional
            "displayNameForTool": "string_optional_A_more_user_friendly_name_for_this_tool_call_e.g._Adding_Resistor_R1",
            "estimatedDurationCategory": "string_enum_optional_short_medium_long_very_long",
            "showProgressGranularly": "boolean_optional_If_True_UI_might_expect_finer_grained_progress_if_tool_supports_it_Default_False"
        },
        "estimatedComplexityOrNotes": "string_optional_LLMs_internal_notes_dependencies_or_confidence_level_for_this_call."
      }
    ],
    "responseToUser": {
      "contentType": "string_e.g._text/plain_or_application/markdown",
      "content": "string_If_isCallTools_is_False_this_is_your_direct_and_complete_reply_to_the_user_It_MUST_NOT_be_empty_If_isCallTools_is_True_this_SHOULD_BE_a_meaningful_transitional_message_reflecting_the_planned_actions_e.g._Okay_I_will_add_component_X_and_then_connect_it_to_Y_It_can_be_an_empty_string_if_no_transitional_message_is_truly_needed_but_a_good_one_is_preferred_for_UX.",
      "suggestionsForNextSteps": [ // Optional
        {
          "suggestionId": "string_optional_unique_id_for_this_suggestion_e.g._sugg_ask_about_led_color",
          "textForUser": "string_The_suggestion_text_to_display_to_the_user_e.g._Would_you_like_to_specify_the_LED_color",
          "actionType": "string_enum_optional_USER_INPUT_EXPECTED_or_PREDEFINED_AGENT_ACTION_or_UI_NAVIGATION",
          "actionPayload": "object_or_string_optional_If_PREDEFINED_AGENT_ACTION_this_could_be_a_simplified_request_object_or_command_string_for_the_agent_to_process_if_selected_by_user"
        }
      ],
      "requiresUserClarificationForCurrentRequest": "boolean_optional_Set_to_True_if_the_current_request_cannot_proceed_without_further_input_from_the_user_and_the_content_is_asking_for_that_clarification_Default_False"
    }
  },
  "diagnostics": { // Optional
      "llmConfidenceScoreForThisOutput": "float_optional_0.0_to_1.0_LLMs_self_assessed_confidence_in_the_correctness_and_completeness_of_THIS_JSON_output",
      "alternativePlansConsideredCount": "integer_optional_If_LLM_considered_multiple_plans_before_settling_on_this_one",
      "parsingFeedbackFromPreviousAttemptId": "string_or_null_If_this_is_a_correction_to_a_previously_malformed_JSON_this_is_the_llmInteractionId_of_that_failed_attempt"
  },
  "usageMetadata": null // Typically not set by LLM, reserved for system
}
```
"""

        direct_qa_example_v8_3_2 = ( # camelCase example
            "\n【通用示例1: 直接回答用户问题 (无需工具) - V8.3.2-CamelCaseJSON Reasoning Model Output】\n"
            "如果用户问: “你好,什么是电容？”\n"
            "您的输出应类似 (ID和时间戳会变化): \n"
            "<think>\n"
            "用户询问电容的定义. 这是一个概念性问题,不需要调用任何电路设计工具,我可以根据我的知识库直接回答. 我将提供一个关于电容基本作用、单位和常见类型的解释,并给出下一步建议. 我的回答将是清晰和直接的.\n"
            "</think>\n"
            "```json\n"
            "{\n"
            "  \"requestId\": \"" + (request_id or "userReqExampleId123") + "\",\n"
            "  \"llmInteractionId\": \"" + llm_interaction_id_example_plan_prefix + "_directQaCap\",\n"
            "  \"timestampUtc\": \"" + current_timestamp_utc + "\",\n"
            "  \"status\": \"success\",\n"
            "  \"errorDetails\": null,\n"
            "  \"executionPhase\": \"planning\",\n"
            "  \"thoughtProcess\": \"用户询问电容定义,直接回答. (Primary thinking in <think> block)\",\n"
            "  \"decision\": {\n"
            "    \"isCallTools\": false,\n"
            "    \"toolCallRequests\": [],\n"
            "    \"responseToUser\": {\n"
            "      \"contentType\": \"text/plain\",\n"
            "      \"content\": \"电容是一种能够储存电荷的电子元件,由两块导体板中间夹一层绝缘介质构成. 它的主要特性是电容量,单位是法拉(F),常用单位有微法(μF)、纳法(nF)和皮法(pF). 电容在电路中常用于滤波、耦合、隔直流、储能等. \",\n"
            "      \"suggestionsForNextSteps\": [\n"
            "        {\"textForUser\": \"您想了解电容在具体电路中的应用吗？\", \"actionType\": \"USER_INPUT_EXPECTED\"},\n"
            "        {\"textForUser\": \"需要我帮您在当前电路中添加一个电容吗？\", \"actionType\": \"USER_INPUT_EXPECTED\", \"actionPayload\": \"请帮我添加一个10uF的电解电容\"}\n"
            "      ],\n"
            "      \"requiresUserClarificationForCurrentRequest\": false\n"
            "    }\n"
            "  },\n"
            "  \"diagnostics\": {\"llmConfidenceScoreForThisOutput\": 0.95},\n"
            "  \"usageMetadata\": null\n"
            "}\n"
            "```\n"
        )

        tool_call_example_v8_3_2 = ( # camelCase example
            "\n【通用示例2: 需要调用工具时的输出V8.3.2-CamelCaseJSON Reasoning Model Output】\n"
            "如果用户说: “帮我加一个1k欧姆的电阻R1,再加一个3V的电池B1,然后把它们连起来. ”\n"
            "您的输出应类似 (ID和时间戳会变化,每个toolCallId必须唯一,由您生成): \n"
            "<think>\n"
            "用户需要执行三个操作: 1. 添加电阻R1 (1kΩ). 2. 添加电池B1 (3V). 3. 连接R1和B1. 我将按顺序规划这三个工具调用. 确保为每个工具调用生成唯一的toolCallId. 并为用户提供一个过渡性的回复,表明我理解了请求并正在处理. 电路状态目前为空,所有元件都可以直接添加.\n"
            "</think>\n"
            "```json\n"
            "{\n"
            "  \"requestId\": \"" + (request_id or "userReqExampleId456") + "\",\n"
            "  \"llmInteractionId\": \"" + llm_interaction_id_example_plan_prefix + "_multiToolRc\",\n"
            "  \"timestampUtc\": \"" + current_timestamp_utc + "\",\n"
            "  \"status\": \"success\",\n"
            "  \"errorDetails\": null,\n"
            "  \"executionPhase\": \"planning\",\n"
            "  \"thoughtProcess\": \"规划添加R1, B1并连接. (Primary thinking in <think> block)\",\n"
            "  \"decision\": {\n"
            "    \"isCallTools\": true,\n"
            "    \"toolCallRequests\": [\n"
            "      {\n"
            "        \"toolCallId\": \"tc_add_r1_" + str(uuid4())[:8] + "\",\n"
            "        \"toolName\": \"add_component_tool\",\n"
            "        \"toolArguments\": {\"component_type\": \"电阻\", \"component_id\": \"R1\", \"value\": \"1kΩ\"},\n"
            "        \"uiHints\": {\"displayNameForTool\": \"添加电阻 R1 (1kΩ)\"}\n"
            "      },\n"
            "      {\n"
            "        \"toolCallId\": \"tc_add_b1_" + str(uuid4())[:8] + "\",\n"
            "        \"toolName\": \"add_component_tool\",\n"
            "        \"toolArguments\": {\"component_type\": \"电池\", \"component_id\": \"B1\", \"value\": \"3V\"},\n"
            "        \"uiHints\": {\"displayNameForTool\": \"添加电池 B1 (3V)\"}\n"
            "      },\n"
            "      {\n"
            "        \"toolCallId\": \"tc_conn_r1b1_" + str(uuid4())[:8] + "\",\n"
            "        \"toolName\": \"connect_components_tool\",\n"
            "        \"toolArguments\": {\"comp1_id\": \"R1\", \"comp2_id\": \"B1\"},\n"
            "        \"uiHints\": {\"displayNameForTool\": \"连接 R1 与 B1\"}\n"
            "      }\n"
            "    ],\n"
            "    \"responseToUser\": {\n"
            "      \"contentType\": \"text/plain\",\n"
            "      \"content\": \"好的,我正在为您添加电阻R1 (1kΩ)、电池B1 (3V),并将它们连接起来. 请稍候...\",\n"
            "      \"suggestionsForNextSteps\": []\n"
            "    }\n"
            "  },\n"
            "  \"diagnostics\": null,\n"
            "  \"usageMetadata\": null\n"
            "}\n"
            "```\n"
        )
        
        replan_example_v8_3_2 = "" # camelCase example
        if is_replanning:
            replan_example_v8_3_2 = (
                "\n【重规划示例 (V8.3.2-CamelCaseJSON Reasoning Model Output): 工具失败后,成功重规划并调用新/修正的工具】\n"
                "假设历史记录中有如下用户请求和失败的工具调用: \n"
                "  User: \"连接 R10 和 C5\"\n"
                "  Assistant (Previous Plan JSON): ... (Planned connect_components_tool for R10, C5, llmInteractionId: " + example_prev_tool_call_id + "_plan) ...\n"
                "  Tool (connect_components_tool, toolCallId: " + example_prev_tool_call_id + "_tool, name: connect_components_tool) result (in history): { \"role\": \"tool\", ..., \"content\": \"{\\\"status\\\": \\\"failure\\\", \\\"message\\\": \\\"错误: 元件 'R10' 在电路中不存在. \\\", \\\"error\\\": { \\\"error_type\\\": \\\"CIRCUIT_OPERATION_ERROR\\\", \\\"error_code\\\": \\\"COMPONENT_NOT_FOUND_FOR_CONNECTION\\\", ... }}\" }\n" # Note: internal error JSON can be snake_case, tool result 'content' is a string.
                "  Current Circuit State (in memory_context): (R10 does not exist, C5 exists)\n"
                "您在【当前重规划】时,您的新V8.3.2-CamelCaseJSON 输出应类似: \n"
                "<think>\n"
                "重规划开始. 分析历史: 用户想连接R10和C5. 上一个计划 (llmInteractionId: " + example_prev_tool_call_id + "_plan) 中调用connect_components_tool (toolCallId: " + example_prev_tool_call_id + "_tool) 失败了,工具报告原因是元件 'R10' 在电路中不存在. 当前电路状态也确认R10不在电路中，但C5存在。因此,我的新计划是首先添加R10 (用户未指定类型或值,我将默认为电阻,并提供一个常用值如1kΩ). 然后再调用connect_components_tool连接新创建的R10和已存在的C5. 本次规划逻辑清晰，后续的JSON应标记为status: 'success'.\n"
                "</think>\n"
                "```json\n"
                "{\n"
                "  \"requestId\": \"" + (request_id or "userReqExampleId789Replan") + "\",\n"
                "  \"llmInteractionId\": \"" + llm_interaction_id_example_plan_prefix + "_replanAddConnect\",\n"
                "  \"timestampUtc\": \"" + current_timestamp_utc + "\",\n"
                "  \"status\": \"success\",\n"
                "  \"errorDetails\": null,\n"
                "  \"executionPhase\": \"planning\",\n"
                "  \"thoughtProcess\": \"R10不存在,先添加再连接. (Primary thinking in <think> block)\",\n"
                "  \"decision\": {\n"
                "    \"isCallTools\": true,\n"
                "    \"toolCallRequests\": [\n"
                "      {\n"
                "        \"toolCallId\": \"tc_replan_add_r10_" + str(uuid4())[:8] + "\",\n"
                "        \"toolName\": \"add_component_tool\",\n"
                "        \"toolArguments\": {\"component_type\": \"电阻\", \"component_id\": \"R10\", \"value\": \"1k\"},\n"
                "        \"uiHints\": {\"displayNameForTool\": \"(修正) 添加电阻 R10 (1kΩ)\"}\n"
                "      },\n"
                "      {\n"
                "        \"toolCallId\": \"tc_replan_connect_r10c5_" + str(uuid4())[:8] + "\",\n"
                "        \"toolName\": \"connect_components_tool\",\n"
                "        \"toolArguments\": {\"comp1_id\": \"R10\", \"comp2_id\": \"C5\"},\n"
                "        \"uiHints\": {\"displayNameForTool\": \"(修正) 连接 R10 与 C5\"}\n"
                "      }\n"
                "    ],\n"
                "    \"responseToUser\": {\n"
                "      \"contentType\": \"text/plain\",\n"
                "      \"content\": \"检测到元件R10之前不存在. 我将先为您添加一个1kΩ的电阻R10,然后再将它与C5连接. \",\n"
                "      \"suggestionsForNextSteps\": [\n"
                "        {\"textForUser\": \"操作完成后显示电路状态. \"}\n"
                "      ],\n"
                "      \"requiresUserClarificationForCurrentRequest\": false\n"
                "    }\n"
                "  },\n"
                "  \"diagnostics\": {\"parsingFeedbackFromPreviousAttemptId\": \"" + example_prev_tool_call_id + "_plan\"},\n"
                "  \"usageMetadata\": null\n"
                "}\n"
                "```\n"
            )

        prompt_parts = [
            "您是一位顶尖的、极其严谨的电路设计编程助理 (Agent Version V8.3.2-CamelCaseJSON, 10 Tools). 您的行为必须专业、精确,并严格遵循指令. \n", # Indicate 10 tools
            reasoning_model_instructions,
            "\n【核心任务: 规划阶段 (V8.3.2-CamelCaseJSON)】\n"
            "请首先在 `<think>...</think>` 标签内深入分析用户的最新指令、完整的对话历史、当前的电路状态和记忆. 然后,在 `</think>` 标签之后,生成一个符合V8.3.2-CamelCaseJSON规范的JSON对象作为您的行动计划或直接回复. JSON中所有key【必须】使用camelCase (例如: `isCallTools`, `toolCallRequests`, `requestId`).\n",
            replanning_guidance_v8_3_2 if is_replanning else "",
            "【V8.3.2-CamelCaseJSON 输出格式规范 (在</think>之后输出, 必须严格遵守)】:\n",
            v8_3_2_camelcase_json_schema_description_for_prompt,
            "\n【重要指令与检查清单 (V8.3.2-CamelCaseJSON - Planning)】:\n"
            "1.  **`<think>` Block First**: Your detailed step-by-step reasoning **MUST** be in `<think>...</think>` tags at the beginning.\n"
            "2.  **JSON After `</think>`**: The V8.3.2-CamelCaseJSON object (wrapped in ```json ... ```) **MUST** follow the `</think>` tag. All keys in this JSON MUST be camelCase (e.g., `requestId`, `isCallTools`, `toolCallRequests`). Keys *inside* `toolArguments` (e.g., `component_type`) should match the snake_case names provided in the tool schemas below.\n"
            "3.  **JSON `thoughtProcess` Field**: This JSON field is now secondary. It can be a brief summary or empty string `\"\"`. The content from the `<think>...</think>` block is primary.\n"
            "4.  **`decision.isCallTools`**: This field in the JSON **MUST** be a boolean (`true` or `false`). Strings like \"True\" or \"true\" (case-insensitive) are also acceptable and will be parsed as booleans by the Agent.\n"
            "5.  **Other JSON fields**: Follow the V8.3.2-CamelCaseJSON schema precisely for the JSON part.\n"
            "6.  **Circuit State Awareness**: Before planning tool calls for existing components, verify their existence in the `memory_context` (current circuit state). If abstract nodes like 'INPUT' need connection and don't exist as components, plan to add them first (e.g., as 'Terminal').\n\n",
            direct_qa_example_v8_3_2,
            tool_call_example_v8_3_2,
        ]
        if is_replanning:
            prompt_parts.append(replan_example_v8_3_2)

        prompt_parts.extend([
            "\n【可用工具列表与参数规范 (V8.3.2 - 10 Tools)】:\n", # Indicate 10 tools
            tool_schemas_desc,
            "\n\n【当前上下文信息 (V8.3.2-CamelCaseJSON)】:\n"
            f"Current Request ID (if available, echo in your JSON's requestId field): {request_id or 'N/A_NOT_PROVIDED_IN_PROMPT_SET_TO_NULL'}\n"
            f"Current UTC Time (for your reference when generating timestampUtc): {current_timestamp_utc}\n"
            f"当前电路与记忆摘要:\n{memory_context}\n\n"
            "【最后再次强调】: 您的输出【必须】以 `<think>...</think>` 块开始,后跟一个被 ```json ... ``` 包围的、严格符合上述V8.3.2-CamelCaseJSON规范 (所有key使用camelCase) 的单个JSON对象. JSON对象之外不应有任何其他文本. 请务必仔细检查 `<think>` 块的使用以及JSON的语法和所有字段的类型及条件要求！"
        ])
        return "".join(prompt_parts)

    def _get_response_generation_prompt_v8_3_2_camelcase_reasoning(self, memory_context: str, tool_schemas_desc: str, request_id: Optional[str] = None) -> str:
        current_timestamp_utc = datetime.now(timezone.utc).isoformat()
        llm_interaction_id_example_resp_prefix = f"resp_ex_llm_id_{str(uuid4())[:6]}"

        reasoning_model_instructions_resp_phase = (
            "\n【重要: Reasoning Model 输出规范 (V8.3.2-CamelCaseJSON - Response Generation)】\n"
            "1.  **思考过程**: 您的详细思考过程 (how you analyzed tool results or decided on the direct reply, and formulated the final response) 【必须】包含在 `<think>...</think>` 标签内,并放在您回复的最开始部分。\n"
            "2.  **JSON 输出**: 在 `</think>` 标签之后,您【必须】输出一个严格符合下面描述的V8.3.2-CamelCaseJSON格式的单个JSON对象。此JSON对象应被三个反引号和'json'标记包围 (即 ```json ... ```)。JSON中所有key【必须】使用camelCase.\n"
            "3.  **`thoughtProcess` 字段 (in JSON)**: JSON对象内部的 `thoughtProcess` 字段现在是次要的。它可以是一个简短的总结或留空 ( `\"\"` ),因为您的主要思考过程已在 `<think>...</think>` 块中。Agent将优先使用 `<think>` 块中的内容作为思考日志。\n"
        )
        
        # The schema description is the same as for planning, just with executionPhase fixed
        v8_3_2_camelcase_json_schema_description_for_resp_phase = """
```json
{
  "requestId": "string_or_null_current_user_request_cycle_id_echo_this_value_from_system_prompt_s_context_information_if_provided_otherwise_null",
  "llmInteractionId": "string_MUST_BE_UNIQUE_id_for_this_llm_response_e.g.,_resp_llm_id_followed_by_8_random_chars_like_resp_llm_id_e5f6g7h8",
  "timestampUtc": "string_current_utc_timestamp_in_iso_8601_format_e.g.,_2024-07-16T12:05:00.000Z",
  "status": "string_MUST_BE_either_'success'_or_'failure'_indicates_if_YOU_successfully_generated_this_final_response_json_FOR_THIS_ATTEMPT_If_you_cannot_formulate_a_proper_summary_or_response_NOW_then_set_to_failure",
  "errorDetails": { /* ... same as planning phase ... */ },
  "executionPhase": "string_MUST_BE_'response_generation'_for_this_task",
  "thoughtProcess": "string_THIS_FIELD_IS_NOW_SECONDARY_Your_primary_detailed_reasoning_MUST_be_in_the_initial_`<think>...</think>`_block_This_JSON_field_can_be_a_brief_summary_or_empty_The_Agent_will_prioritize_the_`<think>`_block_content.",
  "decision": {
    "isCallTools": "boolean_MUST_BE_false_in_this_response_generation_phase_Accepts_string_true_false_case_insensitive_as_well",
    "toolCallRequests": [], // MUST BE empty list or null
    "responseToUser": {
      "contentType": "string_e.g._text/plain_or_application/markdown",
      "content": "string_This_is_your_FINAL_and_COMPLETE_reply_to_the_user_It_MUST_NOT_be_empty_It_should_summarize_actions_taken_report_results_and_address_the_user_s_original_request_based_on_tool_outputs_or_your_direct_knowledge_if_no_tools_were_called_in_the_first_place_This_content_is_what_the_user_will_see",
      "suggestionsForNextSteps": [ /* ... same as planning phase ... */ ],
      "requiresUserClarificationForCurrentRequest": "boolean_optional_Set_to_True_if_the_current_request_cannot_proceed_without_further_input_from_the_user_and_the_content_is_asking_for_that_clarification_Default_False"
    }
  },
  "diagnostics": { /* ... same as planning phase ... */ },
  "usageMetadata": null
}
```
""".replace("{ /* ... same as planning phase ... */ }", """{
    "errorType": "string_enum_e.g._RESPONSE_GENERATION_ERROR_LLM_OUTPUT_VALIDATION_ERROR",
    "errorCode": "string_e.g._JSON_MALFORMED_SUMMARY_LOGIC_ERROR",
    "messageToUser": "string_optional_user_friendly_message_if_applicable",
    "technicalMessage": "string_Detailed_technical_error_message_for_THIS_response_generation_attempt.",
    "isDirectLlmFailure": "boolean_True_if_LLM_explicitly_states_it_cannot_fulfill_request_or_generate_valid_JSON_FOR_THIS_ATTEMPT_False_if_error_is_due_to_Agent_side_validation_of_an_otherwise_syntactically_valid_LLM_JSON_output_or_if_LLM_is_reporting_a_logical_failure_in_a_well_formed_JSON.",
    "failedValidationPoints": [ { "jsonPath": "...", "issue_description": "..." } ]
  }""").replace("[ /* ... same as planning phase ... */ ]", """[
        {
          "suggestionId": "string_optional_unique_id_for_this_suggestion_e.g._sugg_ask_about_led_color",
          "textForUser": "string_The_suggestion_text_to_display_to_the_user_e.g._Would_you_like_to_specify_the_LED_color",
          "actionType": "string_enum_optional_USER_INPUT_EXPECTED_or_PREDEFINED_AGENT_ACTION_or_UI_NAVIGATION",
          "actionPayload": "object_or_string_optional_If_PREDEFINED_AGENT_ACTION_this_could_be_a_simplified_request_object_or_command_string_for_the_agent_to_process_if_selected_by_user"
        }
      ]""").replace("diagnostics\": { /* ... same as planning phase ... */ }", """diagnostics": {
      "llmConfidenceScoreForThisOutput": "float_optional_0.0_to_1.0",
      "alternativePlansConsideredCount": "integer_optional",
      "parsingFeedbackFromPreviousAttemptId": "string_or_null"
  }""")


        response_gen_example_v8_3_2 = ( # camelCase example
            "\n【示例 (V8.3.2-CamelCaseJSON Reasoning Model Output): 总结工具结果并生成最终回复】\n"
            "假设对话历史中包含以下工具执行结果 (Tool Message 1 success, Tool Message 2 failure):\n"
            "  Tool Message 1 (for toolCallId: tc_xyz_add_r1): { \"role\": \"tool\", ..., \"content\": \"{\\\"status\\\": \\\"success\\\", ...}\" }\n"
            "  Tool Message 2 (for toolCallId: tc_abc_add_b1): { \"role\": \"tool\", ..., \"content\": \"{\\\"status\\\": \\\"failure\\\", ...ID 'B1' 已被占用...}\" }\n"
            "您的输出V8.3.2-CamelCaseJSON JSON应类似 (ID和时间戳会变化): \n"
            "<think>\n"
            "回顾工具执行结果: add_component_tool (toolCallId: tc_xyz_add_r1) 成功添加了电阻R1 (1kΩ). 然而, add_component_tool (toolCallId: tc_abc_add_b1) 在尝试添加电池B1时,由于ID冲突导致失败. 我需要向用户清晰地报告这两个结果,并解释B1添加失败的原因. 我将建议用户为B1尝试使用不同的ID,并在建议中提供可操作的选项. 最终的回复将整合这些信息,保持友好和乐于助人的语气.\n"
            "</think>\n"
            "```json\n"
            "{\n"
            "  \"requestId\": \"" + (request_id or "userReqExampleIdResp123") + "\",\n"
            "  \"llmInteractionId\": \"" + llm_interaction_id_example_resp_prefix + "_finalSummaryRb\",\n"
            "  \"timestampUtc\": \"" + current_timestamp_utc + "\",\n"
            "  \"status\": \"success\",\n"
            "  \"errorDetails\": null,\n"
            "  \"executionPhase\": \"response_generation\",\n"
            "  \"thoughtProcess\": \"总结R1添加成功,B1添加失败. (Primary thinking in <think> block)\",\n"
            "  \"decision\": {\n"
            "    \"isCallTools\": false, \n"
            "    \"toolCallRequests\": [], \n"
            "    \"responseToUser\": {\n"
            "      \"contentType\": \"text/plain\",\n"
            "      \"content\": \"您好,我已经成功为您添加了电阻R1 (1kΩ). 但是在尝试添加电池B1时遇到了问题,提示ID 'B1' 已被占用,因此未能添加成功. \",\n"
            "      \"suggestionsForNextSteps\": [\n"
            "        {\"suggestionId\": \"sugg_retry_b1_new_id\", \"textForUser\": \"为电池B1尝试一个新ID (例如 B2) 并重新添加\", \"actionType\": \"USER_INPUT_EXPECTED\", \"actionPayload\": \"帮我添加一个3V电池B2\"},\n"
            "        {\"suggestionId\": \"sugg_view_circuit\", \"textForUser\": \"查看当前电路中已有的元件列表. \", \"actionType\": \"USER_INPUT_EXPECTED\", \"actionPayload\": \"当前电路什么样\"}\n"
            "      ],\n"
            "      \"requiresUserClarificationForCurrentRequest\": true \n"
            "    }\n"
            "  },\n"
            "  \"diagnostics\": {\"llmConfidenceScoreForThisOutput\": 0.98},\n"
            "  \"usageMetadata\": null\n"
            "}\n"
            "```\n"
        )

        return (
            "您是一位顶尖的电路设计编程助理 (Agent Version V8.3.2-CamelCaseJSON, 10 Tools), 经验丰富,技术精湛,并且极其擅长清晰、准确、诚实地汇报工作结果. \n" # Indicate 10 tools
            f"{reasoning_model_instructions_resp_phase}\n"
            "【核心任务: 响应生成阶段 (V8.3.2-CamelCaseJSON)】\n"
            "您当前的任务是: 基于到目前为止的【完整对话历史】(包括用户最初的指令、您在规划阶段生成的V8.3.2-CamelCaseJSON计划、以及所有【已执行工具的结果详情】,这些工具结果是以 'role: tool', 'toolCallId: ...', 'name: ...', 'content: JSON_string_of_tool_output' 的格式存在于历史记录中的), 首先在 `<think>...</think>` 标签内进行思考和总结, 然后在 `</think>` 之后生成【最终的、面向用户的V8.3.2-CamelCaseJSON回复】. JSON中所有key【必须】使用camelCase.\n\n"
            "【V8.3.2-CamelCaseJSON 输出格式规范 (在</think>之后输出, 与规划阶段结构相同,但有特定值要求 - 再次强调)】:\n"
            f"{v8_3_2_camelcase_json_schema_description_for_resp_phase}\n"
            "【重要指令与检查清单 (V8.3.2-CamelCaseJSON - 响应生成阶段特定要求)】:\n"
            "1.  **`<think>` Block First**: Your detailed analysis of tool results and response formulation **MUST** be in `<think>...</think>` tags.\n"
            "2.  **JSON After `</think>`**: The V8.3.2-CamelCaseJSON object (wrapped in ```json ... ```) **MUST** follow the `</think>` tag. All keys in this JSON MUST be camelCase.\n"
            "3.  **`executionPhase`**: 在此阶段,此值【必须】是 `\"response_generation\"`. \n"
            "4.  **`decision.isCallTools`**: 在此响应生成阶段,此值【必须】为 `false` (或可解析为`false`的字符串). \n"
            "5.  **`decision.toolCallRequests`**: 在此响应生成阶段,此列表【必须】为 `[]` (空数组) 或 `null`. \n"
            "6.  **`decision.responseToUser.content`**: 这是您基于所有先前步骤生成的【最终、完整、友好】的文本回复. 它【不能】为空字符串或仅包含空白. \n"
            "7.  **回顾工具结果**: 仔细检查对话历史中 `role: tool` 的消息. 您的最终回复必须准确反映这些结果. \n\n"
            f"{response_gen_example_v8_3_2}\n"
            "【上下文参考信息 (仅供你回顾 - V8.3.2-CamelCaseJSON)】:\n"
            f"Current Request ID (if available, echo in your JSON's requestId field): {request_id or 'N/A_NOT_PROVIDED_IN_PROMPT_SET_TO_NULL'}\n"
            f"Current UTC Time (for your reference when generating timestampUtc): {current_timestamp_utc}\n"
            f"当前电路与记忆摘要:\n{memory_context}\n"
            f"我的可用工具列表 (共10个, 仅供你参考,此阶段不应再调用它们):\n{tool_schemas_desc}\n\n" # Indicate 10 tools
            "【最后再次强调】: 您的输出【必须】以 `<think>...</think>` 块开始,后跟一个被 ```json ... ``` 包围的、严格符合上述V8.3.2-CamelCaseJSON规范 (所有key使用camelCase) 的单个JSON对象. 在这个阶段,您【绝对不能】再请求调用任何新工具. 您的任务是总结并回复. "
        )

# --- Main entry point for testing (Optional) ---
async def main_test_flow(agent: CircuitAgent, user_query: str):
    """Simple async test flow for the agent."""
    logger.info(f"\n\n>>>>>>>>> 测试开始: 用户查询: '{user_query}' <<<<<<<<<<")

    async def mock_status_callback(status_update: Dict[str, Any]):
        # Pretty print JSON parts of the status update for readability
        if "final_v8_3_2_camelcase_json_if_success" in status_update and status_update["final_v8_3_2_camelcase_json_if_success"]:
            # Make a copy to modify for printing
            printable_update = status_update.copy()
            try:
                printable_update["final_v8_3_2_camelcase_json_if_success"] = json.loads(json.dumps(status_update["final_v8_3_2_camelcase_json_if_success"], indent=2, ensure_ascii=False))
            except: # In case it's already a string or not serializable
                pass
            logger.info(f"[StatusCallback] {json.dumps(printable_update, indent=2, ensure_ascii=False, default=str)}")
        elif "plan" in status_update and isinstance(status_update["plan"], list):
            printable_update = status_update.copy()
            try:
                printable_update["plan"] = json.loads(json.dumps(status_update["plan"], indent=2, ensure_ascii=False))
            except:
                pass
            logger.info(f"[StatusCallback] {json.dumps(printable_update, indent=2, ensure_ascii=False, default=str)}")
        else:
            logger.info(f"[StatusCallback] {json.dumps(status_update, ensure_ascii=False, default=str)}")


    await agent.process_user_request(user_query, mock_status_callback)
    logger.info(f">>>>>>>>>> 测试结束: 用户查询: '{user_query}' <<<<<<<<<<\n")

if __name__ == "__main__":
    logger.info("========== CircuitAgent V8.3.2-CamelCaseJSON (10 Tools) - 命令行测试模式 ==========")
    
    # IMPORTANT: Replace with your actual ZHIPU AI API Key
    zhipu_api_key = os.environ.get("ZHIPUAI_API_KEY")
    if not zhipu_api_key:
        logger.critical("CRITICAL: ZHIPUAI_API_KEY environment variable not set. Agent cannot function.")
        sys.exit("ZHIPUAI_API_KEY not set. Please set it before running.")

    try:
        # Initialize Agent with high verbosity for testing
        test_agent = CircuitAgent(
            api_key=zhipu_api_key,
            model_name="glm-z1-flash", # Using the specified model
            verbose=True,
            max_short_term_items=20, # Smaller for testing if needed
            planning_llm_retries=1,  # Fewer retries for faster tests
            max_tool_retries=1,
            max_replanning_attempts=1
        )
        logger.info("CircuitAgent V8.3.2 (10 Tools) 初始化成功,准备接收测试指令.")
    except Exception as e_init:
        logger.critical(f"Agent 初始化失败: {e_init}", exc_info=True)
        sys.exit(f"Agent initialization failed: {e_init}")

    # --- Test Scenarios ---
    test_queries = [
        # Basic interactions
        "你好",
        "当前电路什么样?",
        # Add components
        "帮我添加一个10k的电阻R10.",
        "再添加一个名为LED1的发光二极管,不需要指定ID.",
        "添加一个5V电池,ID是BAT1.",
        "Current circuit status, please.", # English test
        # Connect components
        "把R10和LED1连起来.",
        "Connect R10 and BAT1.",
        # Update component value
        "把R10的值改成5k欧姆.",
        "我想把BAT1的电压值清除掉.",
        # Find component
        "查找一下元件R10的详细信息.",
        "元件X99存在吗?",
        # List by type
        "列出所有电阻类型的元件.",
        "电路里有哪些电池?",
        # Connection count
        "R10现在有多少个连接?",
        "BAT1连接了几个东西?",
        # Remove components
        "移除LED1.",
        # Disconnect
        "断开R10和BAT1的连接.",
        # Complex command involving multiple new tools
        "帮我把R10的值更新为2k, 然后查一下R10有几个连接, 最后再移除R10.",
        # Error handling: connect non-existent
        "连接R10和R999.",
        # Clear circuit
        "清空电路.",
        "电路现在是空的吗?",
        # Replanning scenario: Try to add existing ID, then re-plan
        "添加一个电阻R1.", # Assume R1 might exist from a previous run if not cleared
        "再添加一个电阻R1.", # This should trigger a problem if R1 exists
        "现在添加一个电阻R2,值为100欧姆,然后把它和GND连接起来.", # Test adding terminal if GND is abstract
    ]

    async def run_all_tests():
        for i, query in enumerate(test_queries):
            logger.info(f"\n--- Test Case {i+1}/{len(test_queries)} ---")
            await main_test_flow(test_agent, query)
            logger.info(f"--- Test Case {i+1} Completed ---\n")
            if i < len(test_queries) - 1: # Pause between tests
                 await asyncio.sleep(2) # Brief pause

    try:
        loop.run_until_complete(run_all_tests())
    except KeyboardInterrupt:
        logger.info("测试被用户中断.")
    except Exception as e_main_run:
        logger.critical(f"运行测试时发生未处理的异常: {e_main_run}", exc_info=True)
    finally:
        if loop.is_running():
            loop.close()
        logger.info("========== CircuitAgent V8.3.2 (10 Tools) - 命令行测试结束 ==========")
