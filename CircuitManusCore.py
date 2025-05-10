
# @FileName: CircuitManus.py
# @Version: V8.2.2-ThoughtfulUI-Fix - Enhanced Replanning & Abstract Node Handling
# @Author: Your Most Loyal, Dedicated, Meticulous & Now Extremely Cautious Programmer (Corrected Prompt Omission, Enhanced Replanning Logic)
# @Date: [Current Date] - Improved replanning prompt and abstract node handling.
# @License: MIT License
# @Description:
# ==============================================================================================
#  Manus 系统 V8.2.2-ThoughtfulUI-Fix 技术实现说明
# ==============================================================================================
#
# V8.2.2-ThoughtfulUI-Fix 核心改动 (基于 V8.1.1-WS-PJS-FIXED):
# 1.  **增强 `_get_planning_prompt_v8_1` 中的重规划提示 (`replanning_guidance_v8_1`)**:
#     - 明确指示LLM在重规划时，必须仔细分析历史记录中 `role: tool` 消息的 `content` 字段 (特别是其内嵌JSON的 `status` 和 `error` 或 `message` 字段)，以准确理解工具失败的【根本原因】。
#     - 强烈要求LLM在生成新计划前，必须参考 `memory_context` 中的【当前电路状态】，避免不必要地重新添加已存在的元件。
#     - 针对抽象节点 (如 "INPUT", "OUTPUT") 连接失败的情况，指导LLM应优先规划使用 `add_component_tool` 创建一个例如 "Terminal" 类型的元件来代表该抽象节点，然后再进行连接。
# 2.  **在 `Circuit.generate_component_id` 和 `_component_counters` 中增加对 "Terminal" 及常用抽象节点 (INPUT, OUTPUT, GND) 的类型映射**:
#     - 允许通过 `add_component_tool` 创建如 `IN1`, `OUT1`, `GND1`, `T1` 等代表连接点或抽象节点的元件。
# 3.  **细化 `_get_planning_prompt_v8_1` 中关于 `error_details.is_direct_llm_failure` 字段的说明**:
#     - 进一步澄清此字段的语义，帮助LLM更准确地设置它。
# 4.  **保持版本号与前端UI一致性 (V8.2.2 ThoughtfulUI)**，并在日志和注释中体现。
#
# (继承 V8.1.1-WS-PJS-FIXED 的所有特性)
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
from datetime import datetime, timezone # V8.1 uses timezone
from typing import List, Dict, Any, Optional, Tuple, Set, Union, Callable, Awaitable
from uuid import uuid4 # V8.1 uses uuid4
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
    f"agent_log_v8_2_2_thoughtful_ui_fix_{current_time_for_log.strftime('%Y%m%d_%H%M%S')}_{current_time_for_log.microsecond // 1000:03d}_P{os.getpid()}.log" # Corrected microsecond formatting
)

log_format = '%(asctime)s - %(name)s - %(levelname)s [%(module)s.%(funcName)s:%(lineno)d] - %(message)s'

console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.DEBUG)
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
            'T': 0, 'N': 0, 'IN': 0, 'OUT': 0 # V8.2.2 Added counters for new types
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
        del self.components[comp_id_upper]
        connections_to_remove = {conn for conn in self.connections if comp_id_upper in conn}
        for conn in connections_to_remove:
            self.connections.remove(conn)
            logger.debug(f"[Circuit] 移除了涉及元件 '{comp_id_upper}' 的连接 {conn}.")
        logger.debug(f"[Circuit] 元件 '{comp_id_upper}' 及其相关连接已从电路中移除. ")

    def connect_components(self, id1: str, id2: str):
        id1_upper = id1.strip().upper()
        id2_upper = id2.strip().upper()
        if id1_upper == id2_upper: raise ValueError(f"不能将元件 '{id1_upper}' 连接到它自己. ") # Corrected to id1_upper
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
             return False
        self.connections.remove(connection)
        logger.debug(f"[Circuit] 断开了连接: {id1_upper} <--> {id2_upper}.")
        return True

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
            "terminal": "T", "端子": "T", "connection point": "P", "连接点": "P", "node": "N", "节点": "N", # V8.2.2 Added Terminal and common node types
            "input": "IN", "输入": "IN", "output": "OUT", "输出": "OUT", # V8.2.2 More specific common nodes
            "component": "O", "元件": "O",
        }

        for code in type_map.values():
            if code not in self._component_counters:
                 self._component_counters[code] = 0

        cleaned_type = component_type.strip().lower()
        type_code = "O"
        best_match_len = 0

        # Prioritize exact matches for input/output/gnd first
        if cleaned_type == "input": type_code = "IN"
        elif cleaned_type == "output": type_code = "OUT"
        elif cleaned_type == "ground" or cleaned_type == "地": type_code = "G"
        else: # Fallback to keyword matching for other types
            for keyword, code in type_map.items():
                if keyword in cleaned_type and len(keyword) > best_match_len:
                    type_code = code
                    best_match_len = len(keyword)

        if type_code == "O" and cleaned_type not in ["component", "元件"]:
             logger.warning(f"[Circuit] 未找到类型 '{component_type}' 的特定前缀,将使用通用前缀 'O'. ")

        MAX_ID_ATTEMPTS = 10000
        for attempt in range(MAX_ID_ATTEMPTS):
            self._component_counters[type_code] += 1
            gen_id = f"{type_code}{self._component_counters[type_code]}"
            if gen_id not in self.components:
                logger.debug(f"[Circuit] 生成唯一 ID: '{gen_id}' (尝试 {attempt + 1})")
                return gen_id
            logger.debug(f"[Circuit] ID '{gen_id}' 已存在,尝试下一个.  (Attempt {attempt + 1})")

        raise RuntimeError(f"未能为类型 '{component_type}' (代码 '{type_code}') 生成唯一 ID ({MAX_ID_ATTEMPTS} 次尝试后). 电路中可能存在大量同类型元件,或ID生成逻辑需要审查. ")

    def clear(self):
        logger.info("[Circuit] 正在清空电路状态...")
        comp_count = len(self.components)
        conn_count = len(self.connections)

        self.components = {}
        self.connections = set()

        self._component_counters = {k: 0 for k in self._component_counters}

        logger.info(f"[Circuit] 电路状态已清空 (移除了 {comp_count} 个元件, {conn_count} 个连接,并重置了所有 ID 计数器). ")

# --- 工具注册装饰器 ---
def register_tool(description: str, parameters: Dict[str, Any]):
    def decorator(func):
        func._tool_schema = {"description": description, "parameters": parameters}
        func._is_tool = True
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

# --- 模块化组件: MemoryManager ---
class MemoryManager:
    def __init__(self, max_short_term_items: int = 30, max_long_term_items: int = 75):
        logger.info("[MemoryManager] 初始化记忆模块...")
        if max_short_term_items <= 1:
            raise ValueError("max_short_term_items 必须大于 1")

        self.max_short_term_items = max_short_term_items
        self.max_long_term_items = max_long_term_items

        self.short_term: List[Dict[str, Any]] = []
        self.long_term: List[str] = []

        self.circuit: Circuit = Circuit()

        logger.info(f"[MemoryManager] 记忆模块初始化完成. 短期上限: {max_short_term_items} 条, 长期上限: {max_long_term_items} 条. ")

    def add_to_short_term(self, message: Dict[str, Any]):
        logger.debug(f"[MemoryManager] 添加消息到短期记忆 (Role: {message.get('role', 'N/A')}). 当前数量: {len(self.short_term)}")
        self.short_term.append(message)

        current_size = len(self.short_term)
        if current_size > self.max_short_term_items:
            logger.debug(f"[MemoryManager] 短期记忆超限 ({current_size}/{self.max_short_term_items}),执行修剪...")
            items_to_remove = current_size - self.max_short_term_items

            non_system_indices = [i for i, msg in enumerate(self.short_term) if msg.get("role") != "system"]
            num_to_actually_remove = min(items_to_remove, len(non_system_indices))

            if num_to_actually_remove > 0:
                indices_to_remove_set = set(non_system_indices[:num_to_actually_remove])
                removed_roles = [self.short_term[i].get('role', 'N/A') for i in sorted(list(indices_to_remove_set))]
                new_short_term = [msg for i, msg in enumerate(self.short_term) if i not in indices_to_remove_set]
                self.short_term = new_short_term
                logger.info(f"[MemoryManager] 短期记忆修剪完成,移除了 {num_to_actually_remove} 条最旧的非系统消息 (Roles: {removed_roles}). ")
            elif items_to_remove > 0:
                 logger.warning(f"[MemoryManager] 短期记忆超限 ({current_size}/{self.max_short_term_items}) 但未能找到足够的非系统消息进行移除. 可能需要增加 max_short_term_items 或审查 system 消息的使用. ")
        logger.debug(f"[MemoryManager] 添加后短期记忆数量: {len(self.short_term)}")

    def add_to_long_term(self, knowledge_snippet: str):
        MAX_SNIPPET_LENGTH = 10000
        if len(knowledge_snippet) > MAX_SNIPPET_LENGTH:
            logger.warning(f"[MemoryManager] 尝试添加的长期记忆片段过长 ({len(knowledge_snippet)} chars),已截断为 {MAX_SNIPPET_LENGTH} 字符. ")
            knowledge_snippet = knowledge_snippet[:MAX_SNIPPET_LENGTH] + "... (截断)"

        logger.debug(f"[MemoryManager] 添加知识到长期记忆: '{knowledge_snippet[:100]}{'...' if len(knowledge_snippet) > 100 else ''}'. 当前数量: {len(self.long_term)}") # Corrected preview length
        self.long_term.append(knowledge_snippet)
        if len(self.long_term) > self.max_long_term_items:
            removed = self.long_term.pop(0)
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
                recent_items = self.long_term[-actual_count:]
                long_term_str = "\n\n【近期经验总结 (仅显示最近 N 条,按时间倒序排列,最新在前)】\n" + "\n".join(f"- {item}" for item in reversed(recent_items))
                logger.debug(f"[MemoryManager] 已提取最近 {len(recent_items)} 条长期记忆 (倒序). ")
        long_term_str += "\n(注: 当前仅使用最近期记忆,未来版本将实现基于相关性的检索)"

        context = f"{circuit_desc}{long_term_str}".strip()
        logger.debug(f"[MemoryManager] 记忆上下文 (电路+长期) 格式化完成. ")
        return context

# --- 模块化组件: LLMInterface ---
class LLMInterface:
    def __init__(self, agent_instance: 'CircuitAgent', model_name: str = "glm-4-flash", default_temperature: float = 0.01, default_max_tokens: int = 8190): # Updated default model
        logger.info(f"[LLMInterface] 初始化 LLM 接口,目标模型: {model_name}")
        if not agent_instance or not hasattr(agent_instance, 'api_key'):
             raise ValueError("LLMInterface 需要一个包含 'api_key' 属性的 Agent 实例. ")
        self.agent_instance = agent_instance
        api_key = self.agent_instance.api_key
        if not api_key: raise ValueError("智谱 AI API Key 不能为空")
        try:
            self.client = ZhipuAI(api_key=api_key)
            logger.info("[LLMInterface] 智谱 AI 客户端初始化成功. ")
        except Exception as e:
            logger.critical(f"[LLMInterface] 初始化智谱 AI 客户端失败: {e}", exc_info=True)
            raise ConnectionError(f"初始化智谱 AI 客户端失败: {e}") from e

        self.model_name = model_name
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

        logger.info(f"[LLMInterface] LLM 接口初始化完成 (Model: {model_name}, Temp: {default_temperature}, MaxTokens: {default_max_tokens}). ")

    async def call_llm(self, messages: List[Dict[str, Any]], execution_phase: str, status_callback: Optional[Callable[[Dict], Awaitable[None]]] = None) -> Any:
        call_args = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens,
        }

        logger.info(f"[LLMInterface] 准备异步调用 LLM ({self.model_name}, Phase: {execution_phase}, Expecting V8.2.2 JSON)...")
        logger.debug(f"[LLMInterface] 发送的消息条数: {len(messages)}")
        if logger.isEnabledFor(logging.DEBUG) and len(messages) > 0:
             try:
                 messages_content_for_log = []
                 for m_idx, m in enumerate(messages):
                     role = m.get("role")
                     content = str(m.get("content",""))
                     if role == "system":
                         content_preview = content[:1000] + ("..." if len(content) > 1000 else "") # Reduced preview for system
                     else:
                         content_preview = content[:200] + ("..." if len(content) > 200 else "") # Reduced preview for others
                     messages_content_for_log.append({"index": m_idx, "role": role, "content_preview_length": len(content), "content_preview": content_preview})
                 messages_summary = json.dumps(messages_content_for_log, ensure_ascii=False, indent=2)
                 logger.debug(f"[LLMInterface] 发送给 LLM 的消息列表 (预览):\n{messages_summary}")
             except Exception as e_json:
                 logger.debug(f"[LLMInterface] 无法序列化消息列表进行调试日志: {e_json}")

        request_id_to_send = self.agent_instance.current_request_id if hasattr(self.agent_instance, 'current_request_id') else None
        if status_callback:
            await status_callback({
                "type": "llm_communication_status",
                "request_id": request_id_to_send,
                "llm_phase": execution_phase,
                "status": "started",
                "message": f"正在与智能大脑沟通 ({execution_phase})..."
            })

        response = None
        try:
            start_time = time.monotonic()
            response = await asyncio.to_thread(self.client.chat.completions.create, **call_args)
            duration = time.monotonic() - start_time
            logger.info(f"[LLMInterface] LLM 异步调用成功. 耗时: {duration:.3f} 秒. ")
            if status_callback:
                await status_callback({
                    "type": "llm_communication_status",
                    "request_id": request_id_to_send,
                    "llm_phase": execution_phase,
                    "status": "completed",
                    "message": f"与智能大脑沟通完成 ({execution_phase}). ",
                    "details": {"duration_seconds": duration}
                })

            if response:
                if response.usage: logger.info(f"[LLMInterface] Token 统计: Prompt={response.usage.prompt_tokens}, Completion={response.usage.completion_tokens}, Total={response.usage.total_tokens}")
                if response.choices:
                    finish_reason = response.choices[0].finish_reason
                    logger.info(f"[LLMInterface] 完成原因: {finish_reason}")
                    if finish_reason == 'length': logger.warning("[LLMInterface] LLM 响应因达到最大 token 限制而被截断！这可能导致JSON不完整！")
                    raw_llm_content = response.choices[0].message.content
                    logger.debug(f"[LLMInterface] LLM 原始响应内容 (完整):\n{raw_llm_content}")
                else:
                    logger.warning("[LLMInterface] LLM 响应中缺少 'choices' 字段. ")
            else:
                 logger.error("[LLMInterface] LLM API 调用返回了 None！")
                 raise ConnectionError("LLM API call returned None.")
            return response
        except Exception as e:
            logger.error(f"[LLMInterface] LLM API 异步调用失败: {e}", exc_info=True)
            if status_callback:
                 await status_callback({
                    "type": "llm_communication_status",
                    "request_id": request_id_to_send,
                    "llm_phase": execution_phase,
                    "status": "error",
                    "message": f"与智能大脑沟通失败 ({execution_phase}). ",
                    "details": {"error": str(e), "error_type": type(e).__name__}
                 })
            raise

# --- 模块化组件: OutputParserV8_1 (名称保持,内部适配V8.2.2/ThoughtfulUI JSON) ---
class OutputParserV8_1: # Renaming might be too broad a change if other V8.1 structures exist. Internal logic adapted.
    def __init__(self, agent_tools_registry: Optional[Dict[str, Dict[str, Any]]] = None):
        logger.info("[OutputParserV8_1-Adapter] 初始化输出解析器 (适配 ManusLLMResponse-V8.2.2-ThoughtfulUI JSON结构). ")
        self.agent_tools_registry = agent_tools_registry if agent_tools_registry else {}


    def _validate_tool_arguments(self, tool_name: str, tool_arguments: Dict[str, Any], tool_call_id: str) -> List[Dict[str, str]]:
        validation_errors: List[Dict[str, str]] = []
        if not self.agent_tools_registry or tool_name not in self.agent_tools_registry:
            validation_errors.append({
                "json_path": f"decision.TOOL_CALL_REQUESTS[tool_call_id={tool_call_id}].tool_name",
                "issue_description": f"工具 '{tool_name}' 未在 Agent 的注册表中找到. "
            })
            return validation_errors

        tool_schema = self.agent_tools_registry[tool_name]
        param_schema_props = tool_schema.get("parameters", {}).get("properties", {})
        required_params = tool_schema.get("parameters", {}).get("required", [])

        for req_param in required_params:
            if req_param not in tool_arguments:
                validation_errors.append({
                    "json_path": f"decision.TOOL_CALL_REQUESTS[tool_call_id={tool_call_id}].tool_arguments.{req_param}",
                    "issue_description": f"工具 '{tool_name}' 的必需参数 '{req_param}' 缺失. "
                })

        for arg_name, arg_value in tool_arguments.items():
            if arg_name not in param_schema_props:
                validation_errors.append({
                    "json_path": f"decision.TOOL_CALL_REQUESTS[tool_call_id={tool_call_id}].tool_arguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 是未在 Schema 中定义的未知参数. "
                })
                continue

            expected_type_str = param_schema_props[arg_name].get("type")
            if expected_type_str == "string" and not isinstance(arg_value, str):
                validation_errors.append({
                    "json_path": f"decision.TOOL_CALL_REQUESTS[tool_call_id={tool_call_id}].tool_arguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是字符串,但得到的是 {type(arg_value).__name__}. "
                })
            elif expected_type_str == "integer" and not isinstance(arg_value, int):
                 validation_errors.append({
                    "json_path": f"decision.TOOL_CALL_REQUESTS[tool_call_id={tool_call_id}].tool_arguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是整数,但得到的是 {type(arg_value).__name__}. "
                })
            elif expected_type_str == "number" and not isinstance(arg_value, (int, float)):
                 validation_errors.append({
                    "json_path": f"decision.TOOL_CALL_REQUESTS[tool_call_id={tool_call_id}].tool_arguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是数字,但得到的是 {type(arg_value).__name__}. "
                })
            elif expected_type_str == "boolean" and not isinstance(arg_value, bool):
                 validation_errors.append({
                    "json_path": f"decision.TOOL_CALL_REQUESTS[tool_call_id={tool_call_id}].tool_arguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是布尔值,但得到的是 {type(arg_value).__name__}. "
                })
            elif expected_type_str == "object" and not isinstance(arg_value, dict):
                 validation_errors.append({
                    "json_path": f"decision.TOOL_CALL_REQUESTS[tool_call_id={tool_call_id}].tool_arguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是对象(字典),但得到的是 {type(arg_value).__name__}. "
                })
            elif expected_type_str == "array" and not isinstance(arg_value, list):
                 validation_errors.append({
                    "json_path": f"decision.TOOL_CALL_REQUESTS[tool_call_id={tool_call_id}].tool_arguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是数组(列表),但得到的是 {type(arg_value).__name__}. "
                })
        return validation_errors


    def parse_llm_response_to_structured_json(self, llm_api_response_message: Any, execution_phase: str) -> Tuple[Optional[Dict[str, Any]], str, List[Dict[str,str]]]:
        parser_id = f"parse_v822_{str(uuid4())[:8]}"
        logger.debug(f"[{parser_id}-OutputParserV8_1-Adapter] 开始解析 LLM 响应 (Phase: {execution_phase})...")
        parsed_json_dict: Optional[Dict[str, Any]] = None
        error_message: str = ""
        failed_validation_points_list: List[Dict[str, str]] = []

        if llm_api_response_message is None:
            error_message = "LLM 响应对象 (Message) 为 None. "
            logger.error(f"[{parser_id}-OutputParserV8_1-Adapter] 解析失败: {error_message}")
            return None, error_message, [{"json_path": "root", "issue_description": error_message}]

        raw_content = getattr(llm_api_response_message, 'content', None)
        if not raw_content or not raw_content.strip():
            error_message = "LLM 响应内容 (content 字段) 为空或仅包含空白字符. "
            logger.error(f"[{parser_id}-OutputParserV8_1-Adapter] 解析失败: {error_message}")
            return None, error_message, [{"json_path": "content", "issue_description": error_message}]

        logger.debug(f"[{parser_id}-OutputParserV8_1-Adapter] 接收到的原始 LLM content (完整):\n{raw_content}")

        json_string_to_parse = raw_content.strip()
        match_md_json = re.search(r"```json\s*(.*?)\s*```", json_string_to_parse, re.DOTALL | re.IGNORECASE)
        if match_md_json:
            json_string_to_parse = match_md_json.group(1).strip()
            logger.debug(f"[{parser_id}-OutputParserV8_1-Adapter] 从 Markdown 代码块中提取到 JSON 字符串. ")
        else:
            first_brace = json_string_to_parse.find('{')
            if first_brace > 0:
                prefix_content = json_string_to_parse[:first_brace].strip()
                logger.warning(f"[{parser_id}-OutputParserV8_1-Adapter] 在预期的 JSON 开头 '{{' 之前检测到非空白内容: '{prefix_content[:100]}...'. 将尝试从 '{{' 开始解析. ") # Reduced preview
                json_string_to_parse = json_string_to_parse[first_brace:]
            elif first_brace == -1 :
                error_message = "无法在 LLM 响应内容中找到 JSON 对象的起始 '{'. "
                logger.error(f"[{parser_id}-OutputParserV8_1-Adapter] 解析失败: {error_message} 原始响应预览: {raw_content[:100]}...") # Reduced preview
                return None, error_message, [{"json_path": "content", "issue_description": error_message}]

        logger.debug(f"[{parser_id}-OutputParserV8_1-Adapter] 预处理后,准备解析的 JSON 字符串 (完整):\n{json_string_to_parse}")

        try:
            parsed_json_dict = json.loads(json_string_to_parse)
            logger.info(f"[{parser_id}-OutputParserV8_1-Adapter] JSON 字符串成功解析为字典. ")
        except json.JSONDecodeError as json_err:
            error_message = f"JSON 解析失败: {json_err}. "
            logger.error(f"[{parser_id}-OutputParserV8_1-Adapter] {error_message} Raw JSON string (截断): '{json_string_to_parse[:200]}...'") # Reduced preview
            return None, error_message, [{"json_path": "root", "issue_description": f"JSONDecodeError: {json_err}"}]
        except Exception as e:
            error_message = f"解析 LLM 响应时发生未知错误: {e}"
            logger.error(f"[{parser_id}-OutputParserV8_1-Adapter] 解析时未知错误: {error_message}", exc_info=True)
            return None, error_message, [{"json_path": "root", "issue_description": f"Unexpected parsing error: {e}"}]

        if not isinstance(parsed_json_dict, dict):
            error_message = "解析后的结果不是一个 JSON 对象 (字典). "
            logger.error(f"[{parser_id}-OutputParserV8_1-Adapter] 结构验证失败: {error_message}")
            return None, error_message, [{"json_path": "root", "issue_description": error_message}]

        required_top_level_fields = ["request_id", "llm_interaction_id", "timestamp_utc", "status", "execution_phase", "thought_process", "decision"]
        for field in required_top_level_fields:
            if field not in parsed_json_dict:
                failed_validation_points_list.append({"json_path": field, "issue_description": f"缺少必需的顶级字段 '{field}'."})

        status_val = parsed_json_dict.get("status")
        if status_val not in ["success", "failure"]:
            failed_validation_points_list.append({"json_path": "status", "issue_description": f"字段 'status' 的值 '{status_val}' 无效,必须是 'success' 或 'failure'."})

        exec_phase_val = parsed_json_dict.get("execution_phase")
        if exec_phase_val not in ["planning", "response_generation"]:
            failed_validation_points_list.append({"json_path": "execution_phase", "issue_description": f"字段 'execution_phase' 的值 '{exec_phase_val}' 无效,必须是 'planning' 或 'response_generation'."})
        elif exec_phase_val != execution_phase:
             failed_validation_points_list.append({"json_path": "execution_phase", "issue_description": f"LLM报告的 'execution_phase' ('{exec_phase_val}') 与 Agent 期望的阶段 ('{execution_phase}') 不匹配. "})

        if status_val == "failure":
            error_details_obj = parsed_json_dict.get("error_details")
            if not isinstance(error_details_obj, dict):
                failed_validation_points_list.append({"json_path": "error_details", "issue_description": "当 'status' 为 'failure' 时, 'error_details' 必须是一个对象. "})
            else:
                if not isinstance(error_details_obj.get("error_type"), str) or not error_details_obj.get("error_type","").strip(): # Added strip check
                    failed_validation_points_list.append({"json_path": "error_details.error_type", "issue_description": "'error_details' 对象中缺少有效的 'error_type' 字符串. "})
                if not isinstance(error_details_obj.get("error_code"), str) or not error_details_obj.get("error_code","").strip(): # Added strip check
                    failed_validation_points_list.append({"json_path": "error_details.error_code", "issue_description": "'error_details' 对象中缺少有效的 'error_code' 字符串. "})
                if not isinstance(error_details_obj.get("technical_message"), str) or not error_details_obj.get("technical_message","").strip(): # Added strip check
                    failed_validation_points_list.append({"json_path": "error_details.technical_message", "issue_description": "'error_details' 对象中缺少有效的 'technical_message' 字符串. "})
                # V8.2.2 Fix: Check for is_direct_llm_failure field, it can be optional (if not provided, assumed False by Agent). Log if missing.
                if "is_direct_llm_failure" not in error_details_obj or not isinstance(error_details_obj.get("is_direct_llm_failure"), bool):
                    logger.warning(f"[{parser_id}-OutputParserV8_1-Adapter] 'error_details.is_direct_llm_failure' 字段缺失或类型不为布尔. Agent将假定为false. LLM输出应包含此字段. ")
                    # Do not add to failed_validation_points_list if optional, but log it. If strictly required, then add.
                    # For robust parsing, if it's missing, we can default it to False agent-side later, but LLM should be prompted to include it.
                    # The log shows this was a validation failure point, so we keep it as a failure point for strictness.
                    failed_validation_points_list.append({"json_path": "error_details.is_direct_llm_failure", "issue_description": "'error_details' 对象中缺少有效的布尔字段 'is_direct_llm_failure'. "})

        elif status_val == "success" and parsed_json_dict.get("error_details") is not None:
             failed_validation_points_list.append({"json_path": "error_details", "issue_description": "当 'status' 为 'success' 时, 'error_details' 字段必须为 null 或不存在. "})

        if not isinstance(parsed_json_dict.get("thought_process"), str) or not parsed_json_dict.get("thought_process","").strip():
            logger.warning(f"[{parser_id}-OutputParserV8_1-Adapter] 'thought_process' 字段为空或类型不正确,但仍会接受. LLM Prompt 应强调其重要性. ")

        decision_obj = parsed_json_dict.get("decision")
        if not isinstance(decision_obj, dict):
            failed_validation_points_list.append({"json_path": "decision", "issue_description": "'decision' 字段必须是一个对象. "})
        else:
            is_call_tools_val = decision_obj.get("IS_CALL_TOOLS")
            if not isinstance(is_call_tools_val, bool):
                failed_validation_points_list.append({"json_path": "decision.IS_CALL_TOOLS", "issue_description": "'decision.IS_CALL_TOOLS' 必须是布尔类型. "})

            tool_call_requests = decision_obj.get("TOOL_CALL_REQUESTS")
            if is_call_tools_val is True:
                if not isinstance(tool_call_requests, list):
                    failed_validation_points_list.append({"json_path": "decision.TOOL_CALL_REQUESTS", "issue_description": "当 'IS_CALL_TOOLS' 为 true 时, 'TOOL_CALL_REQUESTS' 必须是一个列表. "})
                elif not tool_call_requests:
                    logger.warning(f"[{parser_id}-OutputParserV8_1-Adapter] 'IS_CALL_TOOLS' 为 true 但 'TOOL_CALL_REQUESTS' 列表为空. 这可能是一个规划逻辑问题. ")
                elif tool_call_requests:
                    for i, tool_req_item in enumerate(tool_call_requests):
                        item_path_prefix = f"decision.TOOL_CALL_REQUESTS[{i}]"
                        if not isinstance(tool_req_item, dict):
                            failed_validation_points_list.append({"json_path": item_path_prefix, "issue_description": "列表中的每个工具调用请求必须是对象. "}); continue

                        tool_call_id = tool_req_item.get("tool_call_id")
                        if not isinstance(tool_call_id, str) or not tool_call_id.strip():
                            failed_validation_points_list.append({"json_path": f"{item_path_prefix}.tool_call_id", "issue_description": "缺少有效的 'tool_call_id' 字符串. "})

                        tool_name = tool_req_item.get("tool_name")
                        if not isinstance(tool_name, str) or not tool_name.strip():
                            failed_validation_points_list.append({"json_path": f"{item_path_prefix}.tool_name", "issue_description": "缺少有效的 'tool_name' 字符串. "})

                        tool_arguments = tool_req_item.get("tool_arguments")
                        if not isinstance(tool_arguments, dict):
                            failed_validation_points_list.append({"json_path": f"{item_path_prefix}.tool_arguments", "issue_description": "'tool_arguments' 必须是一个对象. "})
                        elif tool_name:
                            arg_validation_errors = self._validate_tool_arguments(tool_name, tool_arguments, tool_call_id if tool_call_id else f"index_{i}")
                            failed_validation_points_list.extend(arg_validation_errors)

                        ui_hints = tool_req_item.get("ui_hints")
                        if ui_hints is not None and not isinstance(ui_hints, dict):
                            failed_validation_points_list.append({"json_path": f"{item_path_prefix}.ui_hints", "issue_description": "'ui_hints' 如果存在,必须是一个对象. "})

            elif is_call_tools_val is False:
                if tool_call_requests is not None and (not isinstance(tool_call_requests, list) or tool_call_requests):
                    failed_validation_points_list.append({"json_path": "decision.TOOL_CALL_REQUESTS", "issue_description": "当 'IS_CALL_TOOLS' 为 false 时, 'TOOL_CALL_REQUESTS' 必须是 null 或空列表 []. "})

            response_user_obj = decision_obj.get("RESPONSE_TO_USER")
            if not isinstance(response_user_obj, dict):
                failed_validation_points_list.append({"json_path": "decision.RESPONSE_TO_USER", "issue_description": "'RESPONSE_TO_USER' 必须是一个对象. "})
            else:
                if not isinstance(response_user_obj.get("content_type"), str) or not response_user_obj.get("content_type","").strip():
                     failed_validation_points_list.append({"json_path": "decision.RESPONSE_TO_USER.content_type", "issue_description": "'RESPONSE_TO_USER' 对象缺少有效的 'content_type' 字符串. "})

                resp_content = response_user_obj.get("content")
                if not isinstance(resp_content, str):
                     failed_validation_points_list.append({"json_path": "decision.RESPONSE_TO_USER.content", "issue_description": "'RESPONSE_TO_USER.content' 必须是字符串. "})

                if is_call_tools_val is False and (not resp_content or resp_content.strip() == ""):
                     failed_validation_points_list.append({"json_path": "decision.RESPONSE_TO_USER.content", "issue_description": "当 'IS_CALL_TOOLS' 为 false (直接回复) 时, 'RESPONSE_TO_USER.content' 必须是有效的非空字符串. "})

                suggestions = response_user_obj.get("suggestions_for_next_steps")
                if suggestions is not None:
                    if not isinstance(suggestions, list):
                        failed_validation_points_list.append({"json_path": "decision.RESPONSE_TO_USER.suggestions_for_next_steps", "issue_description": "'suggestions_for_next_steps' 如果存在,必须是一个列表. "})
                    else:
                        for j, sugg_item in enumerate(suggestions):
                            sugg_path_prefix = f"decision.RESPONSE_TO_USER.suggestions_for_next_steps[{j}]"
                            if not isinstance(sugg_item, dict):
                                failed_validation_points_list.append({"json_path": sugg_path_prefix, "issue_description": "列表中的每个建议必须是对象. "}); continue
                            if not isinstance(sugg_item.get("text_for_user"), str) or not sugg_item.get("text_for_user","").strip():
                                failed_validation_points_list.append({"json_path": f"{sugg_path_prefix}.text_for_user", "issue_description": "建议对象缺少有效的 'text_for_user' 字符串. "})

                clarification_flag = response_user_obj.get("requires_user_clarification_for_current_request")
                if clarification_flag is not None and not isinstance(clarification_flag, bool):
                     failed_validation_points_list.append({"json_path": "decision.RESPONSE_TO_USER.requires_user_clarification_for_current_request", "issue_description": "'requires_user_clarification_for_current_request' 如果存在,必须是布尔类型. "})

        diagnostics_obj = parsed_json_dict.get("diagnostics")
        if diagnostics_obj is not None and not isinstance(diagnostics_obj, dict):
            failed_validation_points_list.append({"json_path": "diagnostics", "issue_description": "'diagnostics' 如果存在,必须是一个对象. "})

        if failed_validation_points_list:
            error_message_parts = [f"JSON 结构或内容验证失败 (共 {len(failed_validation_points_list)} 点):"]
            for err_point in failed_validation_points_list:
                error_message_parts.append(f"  -路径 '{err_point['json_path']}': {err_point['issue_description']}")
            error_message = "\n".join(error_message_parts)

            json_content_for_log = json.dumps(parsed_json_dict, indent=2, ensure_ascii=False) if parsed_json_dict else json_string_to_parse[:200] # Reduced preview
            logger.error(f"[{parser_id}-OutputParserV8_1-Adapter]\n{error_message}\nParsed JSON content (可能不完整或无效):\n{json_content_for_log}")
            return None, error_message, failed_validation_points_list

        logger.info(f"[{parser_id}-OutputParserV8_1-Adapter] LLM 响应 (Phase: {execution_phase}, LLM_ID: {parsed_json_dict.get('llm_interaction_id', 'N/A')}) 已成功解析并验证为 ManusLLMResponse-V8.2.2-ThoughtfulUI JSON结构！")
        return parsed_json_dict, "", []


# --- 模块化组件: ToolExecutor ---
class ToolExecutor:
    def __init__(self, agent_instance: 'CircuitAgent', max_tool_retries: int = 1, tool_retry_delay_seconds: float = 1.0):
        logger.info("[ToolExecutor] 初始化工具执行器 (支持异步, 重试, 失败中止, UI回调增强 V8.2.2). ")
        if not isinstance(agent_instance, CircuitAgent):
            raise TypeError("ToolExecutor 需要一个 CircuitAgent 实例. ")
        self.agent_instance = agent_instance
        if not hasattr(agent_instance, 'memory_manager') or not isinstance(agent_instance.memory_manager, MemoryManager):
            raise TypeError("Agent 实例缺少有效的 MemoryManager. ")

        self.verbose_mode = getattr(agent_instance, 'verbose_mode', True)
        self.max_tool_retries = max(0, max_tool_retries)
        self.tool_retry_delay_seconds = max(0.1, tool_retry_delay_seconds)

        logger.info(f"[ToolExecutor] 工具执行配置: 每个工具最多重试 {self.max_tool_retries} 次,重试间隔 {self.tool_retry_delay_seconds} 秒. Verbose Mode: {self.verbose_mode}")

    async def _send_tool_status_update(
        self,
        status_callback: Optional[Callable[[Dict], Awaitable[None]]],
        tool_call_id: str,
        tool_name: str,
        tool_status: str,
        message: str,
        tool_arguments: Optional[Dict] = None,
        details: Optional[Dict] = None
    ):
        if status_callback:
            request_id_to_send = self.agent_instance.current_request_id if hasattr(self.agent_instance, 'current_request_id') else None

            arguments_summary_str = "N/A"
            if tool_arguments:
                try:
                    args_parts = []
                    for k, v in tool_arguments.items():
                        v_str = str(v) if v is not None else "None"
                        v_preview = v_str[:30] + '...' if len(v_str) > 30 else v_str
                        args_parts.append(f"{k}: {v_preview}")
                    arguments_summary_str = "; ".join(args_parts)
                    if not arguments_summary_str: arguments_summary_str = "(无参数)"
                except Exception as e_sum:
                    logger.warning(f"生成工具参数摘要时出错: {e_sum}")
                    arguments_summary_str = "(参数摘要生成错误)"

            await status_callback({
                "type": "tool_status_update",
                "request_id": request_id_to_send,
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "tool_arguments_summary_str": arguments_summary_str,
                "status": tool_status,
                "message": message,
                "details": details if details else {}
            })

    async def execute_tool_calls(self, tool_call_requests_from_plan: List[Dict[str, Any]], status_callback: Optional[Callable[[Dict], Awaitable[None]]] = None) -> List[Dict[str, Any]]:
        executor_id = f"exec_v822_{str(uuid4())[:8]}"
        logger.info(f"[{executor_id}-ToolExecutor] 准备异步执行 {len(tool_call_requests_from_plan)} 个工具调用请求 (V8.2.2)...")
        execution_results_for_llm_history: List[Dict[str, Any]] = []

        if not tool_call_requests_from_plan:
            logger.info(f"[{executor_id}-ToolExecutor] 没有工具需要执行. ")
            return []

        total_tools_in_plan = len(tool_call_requests_from_plan)

        for i, tool_request in enumerate(tool_call_requests_from_plan):
            llm_generated_tool_call_id = tool_request.get('tool_call_id', f'fallback_tool_id_{str(uuid4())[:8]}')
            function_name = tool_request.get('tool_name', 'unknown_function')
            parsed_arguments = tool_request.get('tool_arguments', {})
            ui_hints_from_plan = tool_request.get('ui_hints', {})

            tool_display_name = ui_hints_from_plan.get('display_name_for_tool') or function_name.replace('_tool', '').replace('_', ' ').title()

            action_result_final_for_tool: Optional[Dict[str, Any]] = None
            tool_succeeded_this_cycle = False

            logger.info(f"[{executor_id}-ToolExecutor] 处理工具调用 {i + 1}/{total_tools_in_plan}: Name='{function_name}', LLM_ToolCallID='{llm_generated_tool_call_id}'")
            logger.debug(f"[{executor_id}-ToolExecutor] 待执行工具 '{function_name}' 的参数: {parsed_arguments}")

            await self._send_tool_status_update(
                status_callback, llm_generated_tool_call_id, function_name,
                "running", f"开始执行操作: {tool_display_name}...",
                tool_arguments=parsed_arguments,
                details={"ui_hints": ui_hints_from_plan}
            )

            tool_action_method = getattr(self.agent_instance, function_name, None)
            if not callable(tool_action_method) or not getattr(tool_action_method, '_is_tool', False):
                err_msg_not_found = f"Agent 未实现名为 '{function_name}' 的已注册工具方法 (ID: {llm_generated_tool_call_id}). "
                logger.error(f"[{executor_id}-ToolExecutor] 工具未实现或未注册: {err_msg_not_found}")
                action_result_final_for_tool = {"status": "failure", "message": err_msg_not_found, "error": {"error_type": "TOOL_IMPLEMENTATION_ERROR", "error_code": "TOOL_NOT_FOUND_OR_NOT_REGISTERED", "technical_message": f"Action method '{function_name}' not found or not a registered tool in Agent."}}
                await self._send_tool_status_update(
                    status_callback, llm_generated_tool_call_id, function_name,
                    "failed", f"操作 '{tool_display_name}' 失败: 工具未在Agent中实现或注册. ",
                    details={"error": action_result_final_for_tool["error"]}
                )
                execution_results_for_llm_history.append({"role": "tool", "tool_call_id": llm_generated_tool_call_id, "name": function_name, "content": json.dumps(action_result_final_for_tool, ensure_ascii=False, default=str)})
                break

            for retry_attempt in range(self.max_tool_retries + 1):
                current_attempt_num = retry_attempt + 1
                if retry_attempt > 0:
                    logger.warning(f"[{executor_id}-ToolExecutor] 工具 '{function_name}' (ID: {llm_generated_tool_call_id}) 执行失败,正在进行第 {retry_attempt}/{self.max_tool_retries} 次重试...")
                    await self._send_tool_status_update(
                        status_callback, llm_generated_tool_call_id, function_name,
                        "retrying", f"操作 '{tool_display_name}' 失败,等待 {self.tool_retry_delay_seconds} 秒后重试 (尝试 {current_attempt_num})...",
                        tool_arguments=parsed_arguments, details={"retry_count": retry_attempt, "max_retries": self.max_tool_retries, "ui_hints": ui_hints_from_plan}
                    )
                    await asyncio.sleep(self.tool_retry_delay_seconds)

                action_result_this_attempt: Optional[Dict[str, Any]] = None
                try:
                    action_result_this_attempt = await asyncio.to_thread(tool_action_method, arguments=parsed_arguments)

                    if not isinstance(action_result_this_attempt, dict) or 'status' not in action_result_this_attempt or 'message' not in action_result_this_attempt:
                        err_msg_struct = f"工具 '{function_name}' 返回的内部结果结构无效. 期望字典包含 'status' 和 'message'. "
                        logger.error(f"[{executor_id}-ToolExecutor] 工具返回结构错误 (Attempt {current_attempt_num}): {err_msg_struct}")
                        action_result_this_attempt = {"status": "failure", "message": f"错误: 工具 '{function_name}' 内部返回结果结构无效. ", "error": {"error_type": "TOOL_IMPLEMENTATION_ERROR", "error_code": "INVALID_TOOL_ACTION_RESULT_STRUCTURE", "technical_message": err_msg_struct}}
                    else:
                        logger.info(f"[{executor_id}-ToolExecutor] 工具 '{function_name}' 执行完毕 (Attempt {current_attempt_num}). 状态: {action_result_this_attempt.get('status', 'N/A')}")

                    if action_result_this_attempt.get("status") == "success":
                        tool_succeeded_this_cycle = True
                        action_result_final_for_tool = action_result_this_attempt
                        break

                    logger.warning(f"[{executor_id}-ToolExecutor] 工具 '{function_name}' (ID: {llm_generated_tool_call_id}) 执行失败 (Attempt {current_attempt_num}). ")
                    if retry_attempt == self.max_tool_retries:
                        action_result_final_for_tool = action_result_this_attempt

                except TypeError as te:
                    err_msg_type = f"调用工具 '{function_name}' 时参数不匹配或内部类型错误: {te}."
                    logger.error(f"[{executor_id}-ToolExecutor] 工具调用参数/类型错误 (Attempt {current_attempt_num}): {err_msg_type}", exc_info=True)
                    action_result_this_attempt = {"status": "failure", "message": f"错误: 调用工具 '{function_name}' 时参数或内部类型错误. ", "error": {"error_type": "TOOL_EXECUTION_ERROR", "error_code": "ARGUMENT_TYPE_MISMATCH_OR_INTERNAL_TYPE_ERROR", "technical_message": err_msg_type, "exception_details": traceback.format_exc(limit=3)}}
                    action_result_final_for_tool = action_result_this_attempt
                    break
                except Exception as exec_err:
                    err_msg_exec = f"工具 '{function_name}' 执行期间发生意外内部错误 (Attempt {current_attempt_num}): {exec_err}"
                    logger.error(f"[{executor_id}-ToolExecutor] 工具执行内部错误: {err_msg_exec}", exc_info=True)
                    action_result_this_attempt = {"status": "failure", "message": f"错误: 执行工具 '{function_name}' 时发生内部错误. ", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "UNEXPECTED_TOOL_EXECUTION_FAILURE", "technical_message": err_msg_exec, "exception_details": traceback.format_exc(limit=3)}}
                    if retry_attempt == self.max_tool_retries:
                        action_result_final_for_tool = action_result_this_attempt

            if action_result_final_for_tool is None:
                 logger.error(f"[{executor_id}-ToolExecutor] 内部逻辑错误: 工具 '{function_name}' (ID: {llm_generated_tool_call_id}) 未在重试后生成任何最终结果. ")
                 action_result_final_for_tool = {"status": "failure", "message": f"错误: 工具 '{function_name}' 未返回结果. ", "error": {"error_type": "TOOL_EXECUTION_ERROR", "error_code": "MISSING_TOOL_RESULT_AFTER_RETRIES", "technical_message": "Tool action_result_final_for_tool remained None after retry loop."}}

            final_tool_status_str_for_cb = "succeeded" if tool_succeeded_this_cycle else "failed"
            status_message_for_cb = action_result_final_for_tool.get('message', '操作完成,无特定消息. ')
            details_for_cb: Dict[str, Any] = {"ui_hints": ui_hints_from_plan}

            if tool_succeeded_this_cycle:
                result_data_summary = action_result_final_for_tool.get("data")
                if result_data_summary is not None:
                    try: details_for_cb["result_data_preview"] = json.dumps(result_data_summary, ensure_ascii=False, default=str, indent=None)[:200] # Reduced preview
                    except: details_for_cb["result_data_preview"] = "(数据无法序列化预览)"
            else:
                details_for_cb["error"] = action_result_final_for_tool.get("error", {"error_type": "UNKNOWN_ERROR", "error_code": "GENERIC_FAILURE", "technical_message": "未知工具执行错误"})

            await self._send_tool_status_update(
                status_callback, llm_generated_tool_call_id, function_name,
                final_tool_status_str_for_cb, status_message_for_cb,
                details=details_for_cb
            )

            tool_result_message_for_llm = {
                "role": "tool",
                "tool_call_id": llm_generated_tool_call_id,
                "name": function_name,
                "content": json.dumps(action_result_final_for_tool, ensure_ascii=False, default=str)
            }
            execution_results_for_llm_history.append(tool_result_message_for_llm)
            logger.debug(f"[{executor_id}-ToolExecutor] 已记录工具 '{llm_generated_tool_call_id}' 的最终执行结果 (状态: {final_tool_status_str_for_cb}) 到LLM历史. ")

            if not tool_succeeded_this_cycle:
                logger.warning(f"[{executor_id}-ToolExecutor] 工具 '{function_name}' (ID: {llm_generated_tool_call_id}) 在所有重试后仍然失败. 中止后续工具执行. ")
                if i + 1 < total_tools_in_plan:
                    for k in range(i + 1, total_tools_in_plan):
                        aborted_tool_req = tool_call_requests_from_plan[k]
                        aborted_tool_id = aborted_tool_req.get('tool_call_id', f'fallback_aborted_id_{str(uuid4())[:8]}')
                        aborted_tool_name = aborted_tool_req.get('tool_name', 'unknown_aborted_tool')
                        aborted_ui_hints = aborted_tool_req.get('ui_hints', {})
                        aborted_tool_display_name = aborted_ui_hints.get('display_name_for_tool') or aborted_tool_name.replace('_tool','').replace('_',' ').title()

                        await self._send_tool_status_update(
                            status_callback, aborted_tool_id, aborted_tool_name,
                            "aborted_due_to_previous_failure",
                            f"操作 '{aborted_tool_display_name}' 已中止,因为先前的工具 '{tool_display_name}' 执行失败. ",
                            details={"reason": f"Aborted due to failure of tool '{function_name}' (ID: {llm_generated_tool_call_id})", "ui_hints": aborted_ui_hints}
                        )
                        aborted_tool_result_for_llm_content = {
                                "status": "failure",
                                "message": f"工具 '{aborted_tool_name}' 未执行,因为前序工具 '{function_name}' (ID: {llm_generated_tool_call_id}) 失败. ",
                                "error": {"error_type": "TOOL_CHAIN_ABORTED", "error_code": "PRECEDING_TOOL_FAILURE", "technical_message": f"Execution of '{aborted_tool_name}' was skipped due to the failure of tool '{function_name}' (ID: {llm_generated_tool_call_id})."}
                            }
                        execution_results_for_llm_history.append({
                            "role": "tool", "tool_call_id": aborted_tool_id, "name": aborted_tool_name,
                            "content": json.dumps(aborted_tool_result_for_llm_content, ensure_ascii=False)
                        })
                        logger.info(f"[{executor_id}-ToolExecutor] 为中止的工具 '{aborted_tool_name}' (ID: {aborted_tool_id}) 添加了模拟失败记录到LLM历史. ")
                break

        total_processed_tools = len(execution_results_for_llm_history)
        logger.info(f"[{executor_id}-ToolExecutor] 工具执行流程完成. 共处理/记录了 {total_processed_tools}/{total_tools_in_plan} 个计划中的工具调用 (可能因失败提前中止). ")
        return execution_results_for_llm_history

# --- Agent 核心类 (V8.2.2-ThoughtfulUI-Fix) ---
class CircuitAgent:
    def __init__(self, api_key: str, model_name: str = "glm-4-flash", # Updated default model
                 max_short_term_items: int = 30, max_long_term_items: int = 75,
                 planning_llm_retries: int = 5, max_tool_retries: int = 3,
                 tool_retry_delay_seconds: float = 1.0, max_replanning_attempts: int = 3,
                 verbose: bool = True):
        logger.info(f"\n{'='*30} CircuitAgent 初始化开始 (V8.2.2-ThoughtfulUI-Fix Core) {'='*30}")
        self.api_key = api_key
        self.verbose_mode = verbose
        self.current_request_id: Optional[str] = None

        global console_handler
        console_log_level = logging.DEBUG if self.verbose_mode else logging.INFO
        if console_handler:
            console_handler.setLevel(console_log_level)
            logger.info(f"[AgentV8_2_2_WS Init] 控制台日志级别已设置为: {logging.getLevelName(console_log_level)} (Verbose Mode: {self.verbose_mode})")
        else:
            logger.warning("[AgentV8_2_2_WS Init] Console handler not found,无法动态设置日志级别. ")

        self.tools_registry: Dict[str, Dict[str, Any]] = {}
        logger.info("[AgentV8_2_2_WS Init] 正在动态发现并注册工具...")
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, '_is_tool') and method._is_tool:
                schema = getattr(method, '_tool_schema', None)
                if schema and isinstance(schema, dict) and 'description' in schema and 'parameters' in schema:
                    self.tools_registry[name] = schema
                    logger.info(f"[AgentV8_2_2_WS Init] ✓ 已注册工具: '{name}'")
                else:
                    logger.warning(f"[AgentV8_2_2_WS Init] 发现工具 '{name}' 但其 Schema 结构不完整或无效,已跳过注册. ")
        if not self.tools_registry:
            logger.warning("[AgentV8_2_2_WS Init] 未发现任何通过 @register_tool 注册的工具！Agent 将主要依赖直接问答. ")
        else:
            logger.info(f"[AgentV8_2_2_WS Init] 共发现并注册了 {len(self.tools_registry)} 个工具. ")
            if logger.isEnabledFor(logging.DEBUG):
                try: logger.debug(f"[AgentV8_2_2_WS Init] 工具注册表详情:\n{json.dumps(self.tools_registry, indent=2, ensure_ascii=False)}")
                except Exception as e_dump: logger.debug(f"无法序列化工具注册表进行日志记录: {e_dump}")

        try:
            self.memory_manager = MemoryManager(max_short_term_items, max_long_term_items)
            self.llm_interface = LLMInterface(agent_instance=self, model_name=model_name)
            self.output_parser = OutputParserV8_1(agent_tools_registry=self.tools_registry) # Uses the adapted parser
            self.tool_executor = ToolExecutor(
                agent_instance=self,
                max_tool_retries=max_tool_retries,
                tool_retry_delay_seconds=tool_retry_delay_seconds
            )
        except (ValueError, ConnectionError, TypeError) as e:
            logger.critical(f"[AgentV8_2_2_WS Init] 核心模块初始化失败: {e}", exc_info=True)
            raise

        self.planning_llm_retries = max(0, planning_llm_retries)
        self.max_replanning_attempts = max(0, max_replanning_attempts)

        logger.info(f"[AgentV8_2_2_WS Init] 规划LLM重试次数: {self.planning_llm_retries}, 工具执行重试次数: {max_tool_retries}, 最大重规划尝试次数: {self.max_replanning_attempts}")

        logger.info(f"\n{'='*30} CircuitAgent 初始化成功 {'='*30}\n")

    # --- Action Implementations ---
    @register_tool(
        description="添加一个新的电路元件 (如电阻, 电容, 电池, LED, 开关, 芯片, 地线, 端子/连接点等). 如果用户未指定 ID,会自动生成. ",
        parameters={"type": "object", "properties": {"component_type": {"type": "string", "description": "元件的类型 (例如: '电阻', 'LED', 'Terminal', 'INPUT', 'GND')."}, "component_id": {"type": "string", "description": "可选的用户指定 ID. "}, "value": {"type": "string", "description": "可选的元件值 (例如: '1k', '10uF')."}}, "required": ["component_type"]}
    )
    def add_component_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-AddComponentTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行添加元件操作. ")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
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
            user_provided_id_cleaned = component_id_req.strip().upper()
            # V8.2.2 Allow more flexible IDs like INPUT, OUTPUT, GND
            if re.match(r'^[a-zA-Z0-9_][a-zA-Z0-9_-]*$', user_provided_id_cleaned) or user_provided_id_cleaned in ["INPUT", "OUTPUT", "GND"]:
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

        if target_id_final is None:
            try:
                target_id_final = self.memory_manager.circuit.generate_component_id(component_type)
                id_was_generated_by_system = True
                logger.debug(f"{tool_call_logger_prefix} 已自动为类型 '{component_type}' 生成 ID: '{target_id_final}'.")
            except RuntimeError as e_gen_id:
                err_msg = f"无法自动为类型 '{component_type}' 生成唯一 ID: {e_gen_id}"
                logger.error(f"{tool_call_logger_prefix} ID 生成失败: {err_msg}", exc_info=True)
                return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "INTERNAL_AGENT_ERROR", "error_code": "COMPONENT_ID_GENERATION_FAILED", "technical_message": str(e_gen_id)}}

        processed_value = str(value_req).strip() if value_req is not None and str(value_req).strip() else None

        try:
            if target_id_final is None:
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

        except ValueError as ve_comp:
            err_msg = f"创建或添加元件对象时发生内部验证错误: {ve_comp}"
            logger.error(f"{tool_call_logger_prefix} 元件创建/添加错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": "COMPONENT_CREATION_OR_ADDITION_VALIDATION_FAILED", "technical_message": str(ve_comp)}}
        except Exception as e_add_comp:
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
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")

        comp1_id_req = arguments.get("comp1_id")
        comp2_id_req = arguments.get("comp2_id")

        if not comp1_id_req or not isinstance(comp1_id_req, str) or not comp1_id_req.strip() or \
           not comp2_id_req or not isinstance(comp2_id_req, str) or not comp2_id_req.strip():
            err_msg = "必须提供两个有效的、非空的元件 ID 字符串. "
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_IDS_FOR_CONNECTION", "technical_message": err_msg}}

        id1_cleaned = comp1_id_req.strip().upper()
        id2_cleaned = comp2_id_req.strip().upper()

        try:
            connection_was_new = self.memory_manager.circuit.connect_components(id1_cleaned, id2_cleaned)

            if connection_was_new:
                logger.info(f"{tool_call_logger_prefix} 成功添加新连接: {id1_cleaned} <--> {id2_cleaned}")
                self.memory_manager.add_to_long_term(f"连接了元件: {id1_cleaned} <--> {id2_cleaned} (请求ID: {self.current_request_id or 'N/A'})")
                return {"status": "success", "message": f"操作成功: 已将元件 '{id1_cleaned}' 与 '{id2_cleaned}' 连接起来. ", "data": {"connection": sorted((id1_cleaned, id2_cleaned))}}
            else:
                msg_exists = f"元件 '{id1_cleaned}' 和 '{id2_cleaned}' 之间已经存在连接. 无需重复操作. "
                logger.info(f"{tool_call_logger_prefix} 连接已存在: {msg_exists}")
                return {"status": "success", "message": f"注意: {msg_exists}", "data": {"connection": sorted((id1_cleaned, id2_cleaned)), "already_existed": True}}

        except ValueError as ve_connect:
            err_msg_val = str(ve_connect)
            logger.error(f"{tool_call_logger_prefix} 连接验证错误: {err_msg_val}")
            error_code_detail = "GENERIC_CIRCUIT_VALIDATION_ERROR"
            if "不存在" in err_msg_val: error_code_detail = "COMPONENT_NOT_FOUND_FOR_CONNECTION"
            elif "连接到它自己" in err_msg_val: error_code_detail = "SELF_CONNECTION_ATTEMPTED"
            return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": error_code_detail, "technical_message": err_msg_val}}
        except Exception as e_connect:
            err_msg = f"连接元件时发生未知的内部错误: {e_connect}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 连接元件时发生未知内部错误. ", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "CONNECT_COMPONENTS_UNEXPECTED_FAILURE", "technical_message": str(e_connect), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(description="获取当前电路的详细描述. ", parameters={"type": "object", "properties": {}})
    def describe_circuit_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-DescribeCircuitTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行描述电路操作. ")
        try:
            description = self.memory_manager.circuit.get_state_description()
            logger.info(f"{tool_call_logger_prefix} 成功生成电路描述. ")
            return {"status": "success", "message": "已成功获取当前电路的描述. ", "data": {"description": description}}
        except Exception as e_describe:
            err_msg = f"生成电路描述时发生意外的内部错误: {e_describe}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 获取电路描述时发生未知错误. ", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "DESCRIBE_CIRCUIT_UNEXPECTED_FAILURE", "technical_message": str(e_describe), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(description="彻底清空当前的电路设计,移除所有元件和连接. ", parameters={"type": "object", "properties": {}})
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

    # --- Orchestration Layer Method (V8.2.2-ThoughtfulUI-Fix Core Logic) ---
    async def process_user_request(self, user_request: str, status_callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        request_start_time = time.monotonic()
        self.current_request_id = f"req_{str(uuid4())[:12]}"

        final_llm_v8_1_json_output_for_user_facing_reply: Optional[Dict[str, Any]] = None
        final_reply_for_user: str = "抱歉,处理您的请求时发生未知错误. "
        final_llm_interaction_id_for_user: Optional[str] = None
        active_llm_interaction_id: Optional[str] = None

        logger.info(f"\n{'='*25} CircuitAgent 开始处理用户请求 (ReqID: {self.current_request_id}) {'='*25}")
        logger.info(f"[OrchestratorV8_2_2_WS] 收到用户指令: \"{user_request}\"")

        try:
            if not user_request or user_request.isspace():
                logger.info(f"[OrchestratorV8_2_2_WS - ReqID:{self.current_request_id}] 用户指令为空. ")
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "ignored", "message": "用户输入为空,已忽略. "})
                empty_input_err_json = {
                    "request_id": self.current_request_id,
                    "llm_interaction_id": f"agent_input_err_{str(uuid4())[:6]}",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "status": "failure",
                    "error_details": {
                        "error_type": "USER_INPUT_ERROR",
                        "error_code": "EMPTY_USER_REQUEST",
                        "message_to_user": "您的指令似乎是空的,请重新输入！",
                        "technical_message": "User request was empty or whitespace.",
                        "is_direct_llm_failure": False
                    },
                    "execution_phase": "planning",
                    "thought_process": "Agent检测到用户输入为空或仅包含空白字符,无需进一步处理. ",
                    "decision": { "IS_CALL_TOOLS": False, "TOOL_CALL_REQUESTS": [], "RESPONSE_TO_USER": {"content_type":"text/plain", "content": "您的指令似乎是空的,请重新输入！"}}
                }
                await status_callback({"type": "final_response", "request_id": self.current_request_id, "llm_interaction_id": empty_input_err_json["llm_interaction_id"], "content": empty_input_err_json["decision"]["RESPONSE_TO_USER"]["content"], "final_v8_1_json_if_success": None}) # V8.1 JSON
                return

            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "received", "message": "收到用户指令,开始处理...", "details": {"user_request_preview": user_request[:100]}}) # Reduced preview
            try:
                self.memory_manager.add_to_short_term({"role": "user", "content": user_request})
            except Exception as e_mem_user:
                logger.error(f"[OrchestratorV8_2_2_WS - ReqID:{self.current_request_id}] 添加用户消息到短期记忆时出错: {e_mem_user}", exc_info=True)
                err_msg_mem = f"记录用户指令时发生内部记忆错误: {e_mem_user}"
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "error", "message": err_msg_mem})
                mem_err_json = {
                    "request_id": self.current_request_id, "llm_interaction_id": f"agent_mem_err_{str(uuid4())[:6]}",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(), "status": "failure",
                    "error_details": {"error_type": "INTERNAL_AGENT_ERROR", "error_code": "MEMORY_ADD_USER_MSG_FAILED", "message_to_user": f"抱歉,我在记录您的指令时遇到了内部问题 ({e_mem_user})！请稍后重试. ", "technical_message": err_msg_mem, "is_direct_llm_failure": False },
                    "execution_phase": "planning", "thought_process": "Agent在将用户消息添加到短期记忆时遇到错误. ",
                    "decision": { "IS_CALL_TOOLS": False, "TOOL_CALL_REQUESTS": [], "RESPONSE_TO_USER": {"content_type":"text/plain", "content": f"抱歉,我在记录您的指令时遇到了内部问题 ({e_mem_user})！请稍后重试. " }}
                }
                await status_callback({"type": "final_response", "request_id": self.current_request_id, "llm_interaction_id": mem_err_json["llm_interaction_id"], "content": mem_err_json["decision"]["RESPONSE_TO_USER"]["content"], "final_v8_1_json_if_success": None}) # V8.1 JSON
                return

            replanning_loop_count = 0
            current_llm_plan_v8_1_obj: Optional[Dict[str, Any]] = None
            tool_execution_results_for_llm_history: List[Dict[str, Any]] = []
            agent_accepted_latest_plan_for_action = False

            while replanning_loop_count <= self.max_replanning_attempts:
                current_planning_attempt_num = replanning_loop_count + 1
                log_prefix = f"[OrchestratorV8_2_2_WS - PlanAttempt {current_planning_attempt_num} - ReqID: {self.current_request_id}]"
                logger.info(f"\n--- {log_prefix} 开始 ---")

                is_currently_replanning = (replanning_loop_count > 0)
                status_msg_planning_start = "正在分析指令并制定计划..." if not is_currently_replanning else f"正在尝试第 {replanning_loop_count}/{self.max_replanning_attempts} 次重规划..."
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "started", "message": status_msg_planning_start, "details": {"attempt_number": current_planning_attempt_num, "max_replanning_attempts": self.max_replanning_attempts}})

                memory_context = self.memory_manager.get_memory_context_for_prompt()
                tool_schemas = self._get_tool_schemas_for_prompt()
                system_prompt_planning = self._get_planning_prompt_v8_1(tool_schemas, memory_context, is_currently_replanning, self.current_request_id)
                messages_for_planning = [{"role": "system", "content": system_prompt_planning}] + self.memory_manager.short_term

                llm_call_attempt_inner = 0
                parsed_plan_v8_1_this_llm_call: Optional[Dict[str, Any]] = None
                parser_error_msg_this_llm_call: str = ""
                parsed_failed_validation_points_this_llm_call: List[Dict[str,str]] = []
                agent_accepted_latest_plan_for_action = False

                while llm_call_attempt_inner <= self.planning_llm_retries:
                    logger.info(f"{log_prefix} 调用规划 LLM (LLM Call Attempt {llm_call_attempt_inner + 1} of {self.planning_llm_retries + 1})...")
                    try:
                        llm_response_planning_raw = await self.llm_interface.call_llm(messages_for_planning, "planning", status_callback)
                        if not llm_response_planning_raw or not llm_response_planning_raw.choices:
                            raise ConnectionError("LLM规划响应无效或缺少choices. 这是LLMInterface层面的问题. ")

                        llm_msg_obj_planning = llm_response_planning_raw.choices[0].message
                        parsed_plan_v8_1_this_llm_call, parser_error_msg_this_llm_call, parsed_failed_validation_points_this_llm_call = \
                            self.output_parser.parse_llm_response_to_structured_json(llm_msg_obj_planning, "planning")

                        if parsed_plan_v8_1_this_llm_call:
                            active_llm_interaction_id = parsed_plan_v8_1_this_llm_call.get("llm_interaction_id")
                            current_thought_process = parsed_plan_v8_1_this_llm_call.get("thought_process")
                            if current_thought_process:
                                await status_callback({"type": "thinking_log", "request_id": self.current_request_id, "llm_interaction_id": active_llm_interaction_id, "stage": "planning", "content": current_thought_process})

                        if parsed_plan_v8_1_this_llm_call and not parser_error_msg_this_llm_call and not parsed_failed_validation_points_this_llm_call:
                            if parsed_plan_v8_1_this_llm_call.get("status") == "success":
                                logger.info(f"{log_prefix} 成功解析并验证V8.2.2 JSON计划. LLM报告状态为 'success' (LLM_ID: {active_llm_interaction_id}). Agent采纳此计划. ")
                                agent_accepted_latest_plan_for_action = True
                            elif is_currently_replanning and \
                                 parsed_plan_v8_1_this_llm_call.get("decision", {}).get("IS_CALL_TOOLS") is True and \
                                 isinstance(parsed_plan_v8_1_this_llm_call.get("decision", {}).get("TOOL_CALL_REQUESTS"), list) and \
                                 parsed_plan_v8_1_this_llm_call.get("decision", {}).get("TOOL_CALL_REQUESTS"):
                                logger.warning(f"{log_prefix} LLM在重规划时提供了新的工具调用计划,但可能将其顶层status标记为 'failure' (LLM_ID: {active_llm_interaction_id}). Agent将审慎采纳此新计划以尝试修正. LLM报告的错误(如有): {parsed_plan_v8_1_this_llm_call.get('error_details')}")
                                agent_accepted_latest_plan_for_action = True
                            else:
                                error_detail_from_llm = parsed_plan_v8_1_this_llm_call.get("error_details", {}).get("technical_message", "LLM规划指示内部错误,但JSON结构有效. ")
                                logger.warning(f"{log_prefix} LLM报告的V8.2.2 JSON计划状态为 'failure': {error_detail_from_llm} (LLM_ID: {active_llm_interaction_id}). Agent将不采纳此计划,并尝试让LLM修正(如果还有LLM调用重试次数). ")
                                parser_error_msg_this_llm_call = f"LLM主动报告规划失败: {error_detail_from_llm}"

                            if agent_accepted_latest_plan_for_action:
                                current_llm_plan_v8_1_obj = parsed_plan_v8_1_this_llm_call
                                try: self.memory_manager.add_to_short_term(llm_msg_obj_planning.model_dump(exclude_unset=True))
                                except Exception as e_mem_add: logger.error(f"{log_prefix} 添加LLM规划响应到记忆失败: {e_mem_add}")
                                break

                        if not agent_accepted_latest_plan_for_action and llm_call_attempt_inner < self.planning_llm_retries:
                            error_to_report_cb = parser_error_msg_this_llm_call or "V8.2.2 JSON结构或内容校验失败. "
                            if parsed_failed_validation_points_this_llm_call:
                                error_to_report_cb += " 失败点: " + json.dumps(parsed_failed_validation_points_this_llm_call[:2], ensure_ascii=False)
                            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "llm_retry_needed", "message": f"大脑计划处理遇到问题,尝试重新沟通 ({error_to_report_cb[:100]})", "details": {"llm_call_attempt": llm_call_attempt_inner + 1, "parser_error": parser_error_msg_this_llm_call, "validation_failures": parsed_failed_validation_points_this_llm_call}}) # Reduced preview
                            if parsed_plan_v8_1_this_llm_call and parsed_plan_v8_1_this_llm_call.get("status") == "failure":
                                try: self.memory_manager.add_to_short_term(llm_msg_obj_planning.model_dump(exclude_unset=True))
                                except Exception as e_mem_add_fail: logger.error(f"{log_prefix} 添加LLM失败规划到记忆失败: {e_mem_add_fail}")
                            elif parser_error_msg_this_llm_call or parsed_failed_validation_points_this_llm_call:
                                 sim_err_plan_content = {
                                    "request_id": self.current_request_id, "llm_interaction_id": f"agent_parser_err_{active_llm_interaction_id or str(uuid4())[:6]}",
                                    "timestamp_utc": datetime.now(timezone.utc).isoformat(), "status": "failure",
                                    "error_details": {"error_type": "LLM_OUTPUT_VALIDATION_ERROR", "error_code": "V8_JSON_VALIDATION_FAILED", "technical_message": parser_error_msg_this_llm_call, "is_direct_llm_failure": False, "failed_validation_points": parsed_failed_validation_points_this_llm_call }, # V8_JSON generic error code
                                    "execution_phase": "planning", "thought_process": "Agent在解析或验证LLM上一次规划输出时发现以下问题,将请求LLM修正. ",
                                    "decision": { "IS_CALL_TOOLS": False, "TOOL_CALL_REQUESTS": [], "RESPONSE_TO_USER": {"content_type":"text/plain", "content":""}}
                                 }
                                 try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(sim_err_plan_content, ensure_ascii=False)})
                                 except Exception as e_mem_add_parse_err: logger.error(f"{log_prefix} 添加Agent解析错误到记忆失败: {e_mem_add_parse_err}")

                    except Exception as e_llm_call_level:
                        logger.error(f"{log_prefix} LLM调用或规划解析时发生严重错误 (LLM Call Attempt {llm_call_attempt_inner + 1}): {e_llm_call_level}", exc_info=True)
                        parser_error_msg_this_llm_call = f"LLM调用/解析严重错误: {str(e_llm_call_level)[:100]}" # Reduced preview
                        parsed_failed_validation_points_this_llm_call = [{"json_path":"root", "issue_description": parser_error_msg_this_llm_call}]
                        if llm_call_attempt_inner < self.planning_llm_retries:
                             await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "llm_error_retrying", "message": f"与大脑沟通时发生严重错误,尝试重新连接 ({parser_error_msg_this_llm_call})", "details": {"llm_call_attempt": llm_call_attempt_inner + 1}})

                    llm_call_attempt_inner += 1
                    if agent_accepted_latest_plan_for_action: break

                if not agent_accepted_latest_plan_for_action:
                    error_summary_final_planning_llm_attempt = parser_error_msg_this_llm_call or "在多次LLM调用尝试后,未能从LLM获取可接受的V8.2.2规划JSON. "
                    if parsed_failed_validation_points_this_llm_call:
                         error_summary_final_planning_llm_attempt += " 最后一次校验失败点: " + json.dumps(parsed_failed_validation_points_this_llm_call[:2], ensure_ascii=False)

                    await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "failed_after_llm_retries", "message": f"规划失败 (在第 {current_planning_attempt_num} 次规划尝试中,LLM调用重试均失败): {error_summary_final_planning_llm_attempt}", "details": {"final_parser_error": parser_error_msg_this_llm_call, "final_validation_failures": parsed_failed_validation_points_this_llm_call, "thinking_log_from_last_attempt": parsed_plan_v8_1_this_llm_call.get("thought_process") if parsed_plan_v8_1_this_llm_call else "无有效思考过程"}})

                    if replanning_loop_count >= self.max_replanning_attempts:
                        logger.critical(f"{log_prefix} 已达最大重规划尝试次数 ({self.max_replanning_attempts}),且本次规划尝试在LLM调用/解析层面最终失败. 中止处理. ")
                        final_reply_for_user = f"抱歉,即使经过多次尝试与智能大脑沟通,也未能为您的请求 '{user_request[:50]}...' 制定出有效的执行计划. 错误详情: {error_summary_final_planning_llm_attempt}"
                        final_llm_interaction_id_for_user = active_llm_interaction_id or f"error_plan_max_replan_llm_fail_{str(uuid4())[:6]}"
                        final_llm_v8_1_json_output_for_user_facing_reply = None
                        break
                    else:
                        sim_fail_plan_content_for_replan = {
                            "request_id": self.current_request_id, "llm_interaction_id": f"agent_replan_trigger_{active_llm_interaction_id or str(uuid4())[:6]}",
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(), "status": "failure",
                            "error_details": {"error_type": "LLM_OUTPUT_VALIDATION_ERROR", "error_code": "V8_JSON_VALIDATION_FAILED_IN_PLAN_ATTEMPT", "technical_message": error_summary_final_planning_llm_attempt, "is_direct_llm_failure": False, "failed_validation_points": parsed_failed_validation_points_this_llm_call },
                            "execution_phase": "planning", "thought_process": f"Agent在第 {current_planning_attempt_num} 次规划尝试的LLM调用/解析阶段遇到问题,将进行重规划. 错误: {error_summary_final_planning_llm_attempt}",
                            "decision": { "IS_CALL_TOOLS": False, "TOOL_CALL_REQUESTS": [], "RESPONSE_TO_USER": {"content_type":"text/plain", "content":""}}
                        }
                        try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(sim_fail_plan_content_for_replan, ensure_ascii=False)})
                        except Exception as e_mem_add_replan_trigger: logger.error(f"{log_prefix} 添加重规划触发信息到记忆出错: {e_mem_add_replan_trigger}")
                        replanning_loop_count += 1
                        continue

                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "completed_and_validated", "message": "规划完成并通过验证,准备执行或直接回复. ", "details": {"plan_llm_id": current_llm_plan_v8_1_obj.get("llm_interaction_id") if current_llm_plan_v8_1_obj else None}})

                tool_requests_from_plan = current_llm_plan_v8_1_obj.get("decision", {}).get("TOOL_CALL_REQUESTS", []) if current_llm_plan_v8_1_obj else []
                if isinstance(tool_requests_from_plan, list) and current_llm_plan_v8_1_obj:
                    plan_details_for_ui = []
                    for req_idx, tool_req in enumerate(tool_requests_from_plan):
                        plan_details_for_ui.append({
                            "tool_call_id": tool_req.get("tool_call_id"),
                            "tool_name": tool_req.get("tool_name"),
                            "tool_arguments": tool_req.get("tool_arguments", {}),
                            "ui_hints": tool_req.get("ui_hints", {}),
                            "status": "pending",
                            "order": req_idx + 1
                        })
                    await status_callback({
                        "type": "plan_details",
                        "request_id": self.current_request_id,
                        "llm_interaction_id": current_llm_plan_v8_1_obj.get("llm_interaction_id"),
                        "plan": plan_details_for_ui
                    })

                decision_from_plan = current_llm_plan_v8_1_obj.get("decision", {}) if current_llm_plan_v8_1_obj else {}
                should_call_tools_v8_1 = decision_from_plan.get("IS_CALL_TOOLS", False)
                response_user_obj_v8_1_plan = decision_from_plan.get("RESPONSE_TO_USER")

                if should_call_tools_v8_1:
                    tool_count_in_plan = len(tool_requests_from_plan) if isinstance(tool_requests_from_plan, list) else 0
                    logger.info(f"{log_prefix} 决策: 执行 {tool_count_in_plan} 个工具. ")
                    await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "action_execution", "status": "started", "message": f"开始执行 {tool_count_in_plan} 个计划操作...", "details": {"tool_count": tool_count_in_plan}})

                    if isinstance(response_user_obj_v8_1_plan, dict) and response_user_obj_v8_1_plan.get("content","").strip():
                        transitional_reply_content = response_user_obj_v8_1_plan["content"]
                        await status_callback({"type": "interim_response", "request_id": self.current_request_id, "llm_interaction_id": current_llm_plan_v8_1_obj.get("llm_interaction_id") if current_llm_plan_v8_1_obj else None, "content": transitional_reply_content})

                    if not isinstance(tool_requests_from_plan, list) or not tool_requests_from_plan:
                        err_msg_list_tools_critical = "内部规划错误: IS_CALL_TOOLS为true但TOOL_CALL_REQUESTS列表无效或为空. 这不应发生,因为OutputParserV8_1已校验. "
                        logger.error(f"{log_prefix} {err_msg_list_tools_critical}")
                        tool_execution_results_for_llm_history = [{"role":"tool", "tool_call_id":f"plan_integrity_err_{str(uuid4())[:6]}", "name":"plan_integrity_checker", "content":json.dumps({"status":"failure", "message":err_msg_list_tools_critical, "error": {"error_type":"INTERNAL_AGENT_ERROR", "error_code":"INVALID_TOOL_REQUEST_LIST_POST_VALIDATION", "technical_message": err_msg_list_tools_critical}})}]
                        try: self.memory_manager.add_to_short_term(tool_execution_results_for_llm_history[0])
                        except Exception as e_mem_add_integrity_err: logger.error(f"{log_prefix} 添加规划完整性错误到记忆失败: {e_mem_add_integrity_err}")

                        if replanning_loop_count >= self.max_replanning_attempts:
                            final_reply_for_user = f"抱歉,系统在准备执行操作时遇到内部规划结构问题. 请稍后重试或联系技术支持. 错误: {err_msg_list_tools_critical}"
                            final_llm_interaction_id_for_user = current_llm_plan_v8_1_obj.get("llm_interaction_id") if current_llm_plan_v8_1_obj else active_llm_interaction_id
                            final_llm_v8_1_json_output_for_user_facing_reply = None
                            break
                        else:
                            replanning_loop_count += 1; agent_accepted_latest_plan_for_action = False; continue

                    current_tool_exec_results_for_llm_hist = await self.tool_executor.execute_tool_calls(tool_requests_from_plan, status_callback)
                    tool_execution_results_for_llm_history = current_tool_exec_results_for_llm_hist

                    if tool_execution_results_for_llm_history:
                        for res_msg_tool in tool_execution_results_for_llm_history:
                            try: self.memory_manager.add_to_short_term(res_msg_tool)
                            except Exception as e_mem_add_tool_res: logger.error(f"{log_prefix} 添加工具结果 {res_msg_tool.get('tool_call_id')} 到记忆失败: {e_mem_add_tool_res}")

                    any_tool_failed_persistently = False
                    last_failed_tool_message_for_user = "一个或多个操作未能成功完成. "
                    if tool_execution_results_for_llm_history:
                        for tool_res_for_hist in tool_execution_results_for_llm_history:
                            try:
                                tool_res_content_dict = json.loads(tool_res_for_hist.get("content","{}"))
                                if tool_res_content_dict.get("status") != "success":
                                    any_tool_failed_persistently = True
                                    last_failed_tool_message_for_user = tool_res_content_dict.get("message", last_failed_tool_message_for_user)
                            except json.JSONDecodeError:
                                logger.error(f"{log_prefix} 无法解析工具结果的content JSON: {tool_res_for_hist.get('content')}")
                                any_tool_failed_persistently = True
                                last_failed_tool_message_for_user = "一个操作的结果格式不正确. "

                    if any_tool_failed_persistently:
                        logger.warning(f"{log_prefix} 工具执行过程中发生了一个或多个持久性失败. ")
                        await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "action_execution", "status": "tool_failure_detected", "message": "部分操作失败,准备评估是否重规划. ", "details": {"last_error_message": last_failed_tool_message_for_user}})
                        if replanning_loop_count < self.max_replanning_attempts:
                            replanning_loop_count += 1; agent_accepted_latest_plan_for_action = False; continue
                        else:
                            logger.critical(f"{log_prefix} 已达最大重规划尝试次数 ({self.max_replanning_attempts}),但工具执行仍有失败. 中止处理. ")
                            final_reply_for_user = f"抱歉,在执行您的请求时,即使经过多次尝试,仍遇到问题: {last_failed_tool_message_for_user} 请检查您的指令或稍后再试. "
                            final_llm_interaction_id_for_user = current_llm_plan_v8_1_obj.get("llm_interaction_id") if current_llm_plan_v8_1_obj else active_llm_interaction_id
                            final_llm_v8_1_json_output_for_user_facing_reply = None
                            break
                    else:
                        logger.info(f"{log_prefix} 所有计划中的工具均成功执行. 准备生成最终回复. ")
                        final_llm_v8_1_json_output_for_user_facing_reply = current_llm_plan_v8_1_obj
                        break

                else:
                    logger.info(f"{log_prefix} 决策: 直接回复 (V8.2.2 JSON). 无需工具调用. ")
                    if isinstance(response_user_obj_v8_1_plan, dict) and response_user_obj_v8_1_plan.get("content","").strip():
                        tool_execution_results_for_llm_history = []
                        final_llm_v8_1_json_output_for_user_facing_reply = current_llm_plan_v8_1_obj
                        logger.info(f"{log_prefix} 规划阶段决定直接回复,内容有效. 将使用此V8.2.2 JSON作为最终输出. LLM_ID: {final_llm_v8_1_json_output_for_user_facing_reply.get('llm_interaction_id')}")
                        break
                    else:
                        err_msg_direct_content_critical = "内部规划错误: IS_CALL_TOOLS为false但RESPONSE_TO_USER.content无效或为空. 这不应发生,因为OutputParserV8_1已校验. "
                        logger.error(f"{log_prefix} {err_msg_direct_content_critical}")
                        tool_execution_results_for_llm_history = [{"role":"tool", "tool_call_id":f"direct_reply_integrity_err_{str(uuid4())[:6]}", "name":"direct_reply_integrity_checker", "content":json.dumps({"status":"failure", "message":err_msg_direct_content_critical, "error": {"error_type":"INTERNAL_AGENT_ERROR", "error_code":"INVALID_DIRECT_RESPONSE_CONTENT_POST_VALIDATION", "technical_message": err_msg_direct_content_critical}})}]
                        try: self.memory_manager.add_to_short_term(tool_execution_results_for_llm_history[0])
                        except Exception as e_mem_add_direct_reply_err: logger.error(f"{log_prefix} 添加直接回复完整性错误到记忆失败: {e_mem_add_direct_reply_err}")

                        if replanning_loop_count >= self.max_replanning_attempts:
                            final_reply_for_user = f"抱歉,系统在准备直接回复时遇到内部规划结构问题. 请稍后重试或联系技术支持. 错误: {err_msg_direct_content_critical}"
                            final_llm_interaction_id_for_user = current_llm_plan_v8_1_obj.get("llm_interaction_id") if current_llm_plan_v8_1_obj else active_llm_interaction_id
                            final_llm_v8_1_json_output_for_user_facing_reply = None
                            break
                        else:
                            replanning_loop_count += 1; agent_accepted_latest_plan_for_action = False; continue

            if not agent_accepted_latest_plan_for_action and replanning_loop_count > self.max_replanning_attempts:
                logger.error(f"[OrchestratorV8_2_2_WS - FinalPrep - ReqID:{self.current_request_id}] 已达最大重规划次数,且最终规划尝试仍失败. 将使用上次记录的错误信息. ")
                final_llm_v8_1_json_output_for_user_facing_reply = None
            elif final_llm_v8_1_json_output_for_user_facing_reply and \
               final_llm_v8_1_json_output_for_user_facing_reply.get("decision",{}).get("IS_CALL_TOOLS") is True:
                logger.info(f"[OrchestratorV8_2_2_WS - ReqID:{self.current_request_id}] 工具执行成功,开始生成最终响应...")
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "response_generation", "status": "started", "message": "正在总结操作结果并生成最终回复...", "details": {"reason": "Tool execution completed successfully. Generating final summary."}})

                system_prompt_resp_gen = self._get_response_generation_prompt_v8_1(
                    self.memory_manager.get_memory_context_for_prompt(),
                    self._get_tool_schemas_for_prompt(),
                    self.current_request_id
                )
                messages_for_resp_gen = [{"role": "system", "content": system_prompt_resp_gen}] + self.memory_manager.short_term

                try:
                    llm_response_final_gen_raw = await self.llm_interface.call_llm(messages_for_resp_gen, "response_generation", status_callback)
                    if not llm_response_final_gen_raw or not llm_response_final_gen_raw.choices: raise ConnectionError("LLM最终响应生成阶段的响应无效或缺少choices. ")

                    llm_msg_obj_final_gen = llm_response_final_gen_raw.choices[0].message
                    parsed_final_v8_1_resp_json, final_parser_err_resp, final_validation_failures_resp = \
                        self.output_parser.parse_llm_response_to_structured_json(llm_msg_obj_final_gen, "response_generation")

                    if parsed_final_v8_1_resp_json:
                        active_llm_interaction_id = parsed_final_v8_1_resp_json.get("llm_interaction_id")
                        final_resp_thought_process = parsed_final_v8_1_resp_json.get("thought_process")
                        if final_resp_thought_process:
                             await status_callback({"type": "thinking_log", "request_id": self.current_request_id, "llm_interaction_id": active_llm_interaction_id, "stage": "response_generation", "content": final_resp_thought_process})

                    if parsed_final_v8_1_resp_json and not final_parser_err_resp and not final_validation_failures_resp and parsed_final_v8_1_resp_json.get("status") == "success":
                        final_llm_v8_1_json_output_for_user_facing_reply = parsed_final_v8_1_resp_json
                        final_llm_interaction_id_for_user = active_llm_interaction_id
                        logger.info(f"[OrchestratorV8_2_2_WS - ReqID:{self.current_request_id}] 成功解析并验证最终响应V8.2.2 JSON (LLM_ID: {final_llm_interaction_id_for_user}). ")
                        try: self.memory_manager.add_to_short_term(llm_msg_obj_final_gen.model_dump(exclude_unset=True))
                        except Exception as e_mem_add_final_resp: logger.error(f"添加最终LLM响应到记忆失败: {e_mem_add_final_resp}")
                    else:
                        err_msg_final_resp_gen = final_parser_err_resp or "V8.2.2最终响应JSON校验失败. "
                        if final_validation_failures_resp: err_msg_final_resp_gen += " 失败点: " + json.dumps(final_validation_failures_resp[:2], ensure_ascii=False)
                        elif parsed_final_v8_1_resp_json and parsed_final_v8_1_resp_json.get("status") == "failure":
                             err_msg_final_resp_gen = parsed_final_v8_1_resp_json.get("error_details",{}).get("technical_message", err_msg_final_resp_gen)

                        logger.error(f"[OrchestratorV8_2_2_WS - ReqID:{self.current_request_id}] LLM未能生成有效V8.2.2 JSON最终回复: {err_msg_final_resp_gen}")
                        final_reply_for_user = "抱歉,在总结工具执行结果时发生了一些问题. 您的操作可能已成功完成,但我暂时无法提供详细的总结报告. "
                        final_llm_interaction_id_for_user = active_llm_interaction_id or (final_llm_v8_1_json_output_for_user_facing_reply.get("llm_interaction_id") if final_llm_v8_1_json_output_for_user_facing_reply else f"error_resp_gen_{str(uuid4())[:6]}")
                        final_llm_v8_1_json_output_for_user_facing_reply = None
                except Exception as e_llm_final_gen_call:
                    logger.critical(f"[OrchestratorV8_2_2_WS - ReqID:{self.current_request_id}] LLM最终响应调用或处理失败: {e_llm_final_gen_call}", exc_info=True)
                    final_reply_for_user = "抱歉,系统在为您准备最终报告时遇到了严重的内部错误！您的操作可能已经完成,但报告无法生成. "
                    final_llm_interaction_id_for_user = (final_llm_v8_1_json_output_for_user_facing_reply.get("llm_interaction_id") if final_llm_v8_1_json_output_for_user_facing_reply else active_llm_interaction_id or f"critical_err_resp_gen_{str(uuid4())[:6]}")
                    final_llm_v8_1_json_output_for_user_facing_reply = None
            elif final_llm_v8_1_json_output_for_user_facing_reply and \
                 final_llm_v8_1_json_output_for_user_facing_reply.get("decision",{}).get("IS_CALL_TOOLS") is False:
                logger.info(f"[OrchestratorV8_2_2_WS - ReqID:{self.current_request_id}] 使用规划阶段的直接回复V8.2.2 JSON作为最终输出. ")
                final_llm_interaction_id_for_user = final_llm_v8_1_json_output_for_user_facing_reply.get("llm_interaction_id")

            elif not final_llm_v8_1_json_output_for_user_facing_reply :
                 logger.error(f"[OrchestratorV8_2_2_WS - ReqID:{self.current_request_id}] 流程结束时,final_llm_v8_1_json_output_for_user_facing_reply 为空,表明处理失败. 将使用之前记录的错误信息. ")

            user_facing_thought_process_final_summary = "综合思考过程已在之前的日志中发送. "
            if final_llm_v8_1_json_output_for_user_facing_reply and final_llm_v8_1_json_output_for_user_facing_reply.get("status") == "success":
                user_facing_thought_process_final_summary = final_llm_v8_1_json_output_for_user_facing_reply.get("thought_process", user_facing_thought_process_final_summary)
                resp_user_obj_final = final_llm_v8_1_json_output_for_user_facing_reply.get("decision", {}).get("RESPONSE_TO_USER", {})
                final_reply_for_user = resp_user_obj_final.get("content", final_reply_for_user)

                suggestions_list = resp_user_obj_final.get("suggestions_for_next_steps")
                if suggestions_list and isinstance(suggestions_list, list):
                    suggestion_texts = [sugg.get("text_for_user") for sugg in suggestions_list if isinstance(sugg, dict) and sugg.get("text_for_user","").strip()]
                    if suggestion_texts: # V8.2.2 Using \n\n for better separation in UI
                        final_reply_for_user += "\n\n您可能想尝试: \n- " + "\n- ".join(suggestion_texts)

            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "finalization", "status": "completed" if final_llm_v8_1_json_output_for_user_facing_reply else "failed", "message": "请求处理流程结束. " })
            await status_callback({"type": "final_response", "request_id": self.current_request_id, "llm_interaction_id": final_llm_interaction_id_for_user, "content": final_reply_for_user.strip() if final_reply_for_user else "抱歉,未能生成有效的回复. ", "final_v8_1_json_if_success": final_llm_v8_1_json_output_for_user_facing_reply }) # V8.1 JSON for compatibility

            if not (final_llm_v8_1_json_output_for_user_facing_reply and final_llm_v8_1_json_output_for_user_facing_reply.get("status") == "success"):
                final_assistant_synthetic_error_message_v8_1 = { # V8.1 JSON for compatibility
                    "request_id": self.current_request_id,
                    "llm_interaction_id": final_llm_interaction_id_for_user or f"agent_synth_final_err_{str(uuid4())[:6]}",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "status": "failure",
                    "error_details": {"error_type": "AGENT_PROCESSING_FAILURE", "error_code": "OVERALL_REQUEST_HANDLING_FAILED", "message_to_user": final_reply_for_user, "technical_message": "Agent failed to successfully complete the user request after all attempts.", "is_direct_llm_failure": False },
                    "execution_phase": "final_error_synthesis",
                    "thought_process": user_facing_thought_process_final_summary or "Agent 最终处理失败,未能生成详细思考过程. ",
                    "decision": {"IS_CALL_TOOLS": False, "TOOL_CALL_REQUESTS": [], "RESPONSE_TO_USER": {"content_type":"text/plain", "content": final_reply_for_user}}
                }
                try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(final_assistant_synthetic_error_message_v8_1, ensure_ascii=False)}) # V8.1 JSON
                except Exception as e_mem_add_synth_err: logger.error(f"添加Agent合成的最终错误助手消息到记忆失败: {e_mem_add_synth_err}")

        except Exception as e_process_top_level:
            request_id_for_fatal = self.current_request_id or f"fatal_err_no_req_id_{str(uuid4())[:6]}"
            logger.critical(f"[OrchestratorV8_2_2_WS - ReqID:{request_id_for_fatal}] 处理用户请求 '{user_request[:100]}' 时发生顶层未捕获异常: {e_process_top_level}", exc_info=True) # Reduced preview
            error_msg_for_user_fatal = f"抱歉,处理您的请求 ('{user_request[:30]}...') 时发生严重的、未预期的内部系统错误. 请稍后再试或联系技术支持. "
            tb_str_for_thinking_log_fatal = traceback.format_exc().replace('\n', ' | ')
            thinking_log_content_fatal = f"请求处理流程中发生顶层致命错误: {e_process_top_level}. Traceback (部分): {tb_str_for_thinking_log_fatal[:200]}..." # Reduced preview

            fatal_llm_interaction_id = f"fatal_agent_err_{str(uuid4())[:6]}"
            await status_callback({"type": "thinking_log", "request_id": request_id_for_fatal, "llm_interaction_id": fatal_llm_interaction_id, "stage": "fatal_error_capture", "content": thinking_log_content_fatal})
            await status_callback({"type": "general_status", "request_id": request_id_for_fatal, "stage": "fatal_error_handler", "status": "error", "message": f"请求处理失败,发生致命内部错误: {str(e_process_top_level)[:100]}", "details": {"error_type": type(e_process_top_level).__name__, "full_error_message": str(e_process_top_level)}}) # Reduced preview
            await status_callback({"type": "final_response", "request_id": request_id_for_fatal, "llm_interaction_id": fatal_llm_interaction_id, "content": error_msg_for_user_fatal, "final_v8_1_json_if_success": None}) # V8.1 JSON
        finally:
            request_end_time = time.monotonic()
            duration_total = request_end_time - request_start_time
            logger.info(f"\n{'='*25} CircuitAgent 请求处理完毕 (ReqID: {self.current_request_id or 'N/A'}, 总耗时: {duration_total:.3f} 秒) {'='*25}\n")
            self.current_request_id = None


    # --- Helper Methods for Prompts (V8.2.2-ThoughtfulUI-Fix Versions) ---
    def _get_tool_schemas_for_prompt(self) -> str:
        if not self.tools_registry: return "  (当前无可用工具)"
        tool_schemas_parts = []
        for tool_name, schema in self.tools_registry.items():
            desc = schema.get('description', '无描述. ')
            params_schema = schema.get('parameters', {})
            props_schema = params_schema.get('properties', {})
            req_params = params_schema.get('required', [])

            param_desc_segments = []
            if props_schema:
                for param_name, param_details_dict in props_schema.items():
                    param_type = param_details_dict.get('type','any')
                    is_required_str = "必须 (required)" if param_name in req_params else "可选 (optional)"
                    param_description = param_details_dict.get('description','无参数描述')
                    enum_values = param_details_dict.get('enum')
                    enum_desc = f" 可选值: {enum_values}." if enum_values and isinstance(enum_values, list) else ""
                    param_desc_segments.append(f"    - 参数名 `{param_name}`:\n      - 类型: `{param_type}`\n      - 是否必需: {is_required_str}\n      - 描述: {param_description}{enum_desc}")
            elif params_schema.get("type") == "object" and not props_schema :
                 param_desc_segments = ["    - 此工具不接受任何参数(参数对象 `tool_arguments` 应为空对象 `{}`). "]
            else:
                 param_desc_segments = ["    - (此工具的参数定义似乎不完整或无参数)"]

            tool_schemas_parts.append(f"  - 工具名称: `{tool_name}`\n    工具描述: {desc}\n  工具参数详情:\n{chr(10).join(param_desc_segments)}")
        return "\n\n".join(tool_schemas_parts)

    def _get_planning_prompt_v8_1(self, tool_schemas_desc: str, memory_context: str,
                                is_replanning: bool = False, request_id: Optional[str] = None) -> str:
        current_timestamp_utc = datetime.now(timezone.utc).isoformat()
        llm_interaction_id_example_plan_prefix = f"plan_ex_llm_id_{str(uuid4())[:6]}"
        example_prev_tool_call_id = f"tc_ex_prev_fail_{str(uuid4())[:6]}"

        replanning_guidance_v8_1 = ""
        if is_replanning:
            replanning_guidance_v8_1 = (
                "\n【重要: 重规划指示 (V8.2.2)】\n" # Version bump
                "您当前正在进行重规划。这意味着您之前的规划或工具执行遇到了问题。请：\n"
                "1.  **仔细分析失败原因**: 请详细检查对话历史中的 `role: tool` 消息，特别是其 `content` 字段（这是一个JSON字符串），找到其中的 `status: \"failure\"` 以及对应的 `message` 或 `error_details.technical_message` 字段，以准确理解【工具执行失败的根本原因】。同时，如果历史中存在 `role: assistant` 且其内容是模拟的V8.1.1/V8.2.2 JSON并报告`status: \"failure\"`，那可能包含了Agent对您上一次JSON输出的【解析或校验错误信息】（通常在 `error_details.failed_validation_points`）。\n"
                "2.  **参考当前电路状态**: 【务必】仔细查阅 `memory_context` 中提供的【当前电路状态】。您的新计划【必须】基于当前实际存在的元件和连接。**不要尝试重新添加已经成功创建且仍然存在的元件，除非您的意图是先删除再添加（需要规划 `clear_circuit_tool` 或 `remove_component_tool`）**。\n"
                "3.  **处理抽象节点**: 如果之前的失败涉及连接到如 'INPUT', 'OUTPUT', 'GND' 等抽象节点，而这些节点在电路中并不作为已添加的元件存在，您的新计划应首先考虑使用 `add_component_tool` (例如，`component_type: 'Terminal'`, `component_id: 'INPUT1'` 或 `component_type: 'GND'`, `component_id: 'GND_MAIN'`) 来创建这些节点作为实际元件，然后再进行连接。\n"
                "4.  **生成修正后的新计划**: 基于以上分析，您现在必须生成一个【全新的、修正了先前问题的V8.2.2 JSON计划】。如果您成功地为【当前这次思考和规划】输出了一个结构完整且逻辑合理的V8.2.2 JSON（无论是调用新工具还是直接回复用户），那么这个【新JSON本身的顶层 `status` 字段必须设置为 `'success'`】。在 `thought_process` 字段中详细解释您是如何分析上一次失败、如何利用当前电路状态修正计划、以及为什么新的计划是合理的。\n"
                "5.  **无法解决的情况**: 如果您经过深入分析，认为确实无法通过进一步的工具调用或重规划来完成用户的核心请求（例如，请求本身逻辑矛盾，或多次尝试后依然无法克服工具限制），那么您应该制定一个【直接回复用户并解释情况的计划】。在这种情况下，您的V8.2.2 JSON的顶层 `status` 字段同样应为 `'success'` (因为您成功地决定了如何回复)，`decision.IS_CALL_TOOLS` 应设为 `false`，并在 `decision.RESPONSE_TO_USER.content` 中清晰、礼貌地向用户说明情况和原因。如果需要用户提供更多信息，`decision.RESPONSE_TO_USER.requires_user_clarification_for_current_request` 可设为 `true`。\n"
                "6.  **真正意义上的规划失败**: 只有当您在【当前这次重规划尝试中】，由于自身的理解困难、无法形成任何有效的JSON结构、或遇到无法克服的内部逻辑困境，而【未能成功生成一个符合规范的V8.2.2 JSON输出】时，才应将顶层 `status` 字段设为 `'failure'`，并在 `error_details` 中详细说明您【当前这次规划尝试】失败的具体原因 (包括 `error_type`, `error_code`, `technical_message`, `is_direct_llm_failure` 等)。\n"
                "**核心原则**: 不要因为*过去*的工具执行失败，就将您*当前新制定*的计划标记为 `status: 'failure'`. `status` 反映的是您【当前这次生成JSON这个行为本身】的成功与否。\n"
                "不要简单重复之前失败的计划！您的新计划必须严格符合下面描述的V8.2.2 JSON格式。\n"
            )

        v8_1_json_schema_description_for_prompt = """
```json
{
  "request_id": "string_or_null_current_user_request_cycle_id_echo_this_value_from_system_prompt_s_context_information_if_provided_otherwise_null",
  "llm_interaction_id": "string_MUST_BE_UNIQUE_id_for_this_llm_response_e.g.,_plan_llm_id_followed_by_8_random_chars_like_plan_llm_id_a1b2c3d4",
  "timestamp_utc": "string_current_utc_timestamp_in_iso_8601_format_e.g.,_2024-07-16T12:00:00.000Z",
  "status": "string_MUST_BE_either_'success'_or_'failure'._Indicates_if_THIS_SPECIFIC_JSON_OUTPUT_was_successfully_generated_by_LLM_for_the_current_phase.",
  "error_details": {
    "error_type": "string_enum_HIGH_LEVEL_ERROR_CATEGORY_e.g._PLANNING_ERROR_LLM_OUTPUT_VALIDATION_ERROR_INTERNAL_LOGIC_ERROR",
    "error_code": "string_SPECIFIC_ERROR_CODE_e.g._JSON_MALFORMED_MISSING_REQUIRED_FIELD_TOOL_PARAMS_INVALID_REPLAN_MAX_ATTEMPTS_REACHED",
    "message_to_user": "string_A_user_friendly_explanation_if_this_error_is_directly_related_to_user_action_or_if_a_user_facing_message_is_appropriate_otherwise_generic_agent_error_message.",
    "technical_message": "string_Detailed_technical_error_message_for_logging_and_debugging_This_is_what_LLM_thinks_went_wrong_with_its_OWN_output_generation_process.",
    "is_direct_llm_failure": "boolean_True_if_LLM_explicitly_states_it_cannot_fulfill_request_or_generate_valid_JSON_FOR_THIS_ATTEMPT_False_if_error_is_due_to_Agent_side_validation_of_an_otherwise_syntactically_valid_LLM_JSON_output_or_if_LLM_is_reporting_a_logical_failure_in_a_well_formed_JSON.",
    "failed_validation_points": [
      {
        "json_path": "string_e.g._decision.TOOL_CALL_REQUESTS[0].tool_arguments.component_id",
        "issue_description": "string_e.g._Required_field_missing_or_Value_must_be_a_string_but_got_integer"
      }
    ]
  },
  "execution_phase": "string_MUST_BE_'planning'_for_this_task",
  "thought_process": "string_YOUR_DETAILED_STEP_BY_STEP_REASONING_AS_BEFORE_VERY_IMPORTANT_If_replanning_explain_analysis_of_previous_failure_and_how_new_plan_addresses_it_referencing_current_circuit_state.",
  "decision": {
    "IS_CALL_TOOLS": "boolean_true_if_tools_are_to_be_called_false_otherwise",
    "TOOL_CALL_REQUESTS": [
      {
        "tool_call_id": "string_UNIQUE_ID_generated_by_YOU_for_this_specific_tool_call_e.g._tc_add_resistor_xyz123",
        "tool_name": "string_name_of_the_tool_to_be_called_from_available_list",
        "tool_arguments": { },
        "ui_hints": {
            "display_name_for_tool": "string_optional_A_more_user_friendly_name_for_this_tool_call_e.g._Adding_Resistor_R1",
            "estimated_duration_category": "string_enum_optional_short_medium_long_very_long",
            "show_progress_granularly": "boolean_optional_If_true_UI_might_expect_finer_grained_progress_if_tool_supports_it_Default_false"
        },
        "estimated_complexity_or_notes": "string_optional_LLMs_internal_notes_dependencies_or_confidence_level_for_this_call."
      }
    ],
    "RESPONSE_TO_USER": {
      "content_type": "string_e.g._text/plain_or_application/markdown",
      "content": "string_If_IS_CALL_TOOLS_is_false_this_is_your_direct_and_complete_reply_to_the_user_It_MUST_NOT_be_empty_If_IS_CALL_TOOLS_is_true_this_SHOULD_BE_a_meaningful_transitional_message_reflecting_the_planned_actions_e.g._Okay_I_will_add_component_X_and_then_connect_it_to_Y_It_can_be_an_empty_string_if_no_transitional_message_is_truly_needed_but_a_good_one_is_preferred_for_UX.",
      "suggestions_for_next_steps": [
        {
          "suggestion_id": "string_optional_unique_id_for_this_suggestion_e.g._sugg_ask_about_led_color",
          "text_for_user": "string_The_suggestion_text_to_display_to_the_user_e.g._Would_you_like_to_specify_the_LED_color",
          "action_type": "string_enum_optional_USER_INPUT_EXPECTED_or_PREDEFINED_AGENT_ACTION_or_UI_NAVIGATION",
          "action_payload": "object_or_string_optional_If_PREDEFINED_AGENT_ACTION_this_could_be_a_simplified_request_object_or_command_string_for_the_agent_to_process_if_selected_by_user"
        }
      ],
      "requires_user_clarification_for_current_request": "boolean_optional_Set_to_true_if_the_current_request_cannot_proceed_without_further_input_from_the_user_and_the_content_is_asking_for_that_clarification_Default_false"
    }
  },
  "diagnostics": {
      "llm_confidence_score_for_this_output": "float_optional_0.0_to_1.0_LLMs_self_assessed_confidence_in_the_correctness_and_completeness_of_THIS_JSON_output",
      "alternative_plans_considered_count": "integer_optional_If_LLM_considered_multiple_plans_before_settling_on_this_one",
      "parsing_feedback_from_previous_attempt_id": "string_or_null_If_this_is_a_correction_to_a_previously_malformed_JSON_this_is_the_llm_interaction_id_of_that_failed_attempt"
  },
  "usage_metadata": null
}
```
"""

        direct_qa_example_v8_1 = (
            "\n【通用示例1: 直接回答用户问题 (无需工具) - V8.2.2 JSON】\n"
            "如果用户问: “你好,什么是电容？”\n"
            "您的输出V8.2.2 JSON应类似 (ID和时间戳会变化): \n"
            "```json\n"
            "{\n"
            "  \"request_id\": \"" + (request_id or "user_req_example_id_123") + "\",\n"
            "  \"llm_interaction_id\": \"" + llm_interaction_id_example_plan_prefix + "_direct_qa_cap\",\n"
            "  \"timestamp_utc\": \"" + current_timestamp_utc + "\",\n"
            "  \"status\": \"success\",\n"
            "  \"error_details\": null,\n"
            "  \"execution_phase\": \"planning\",\n"
            "  \"thought_process\": \"用户询问电容的定义. 这是一个概念性问题,不需要调用任何电路设计工具,我可以根据我的知识库直接回答. 我将提供一个关于电容基本作用、单位和常见类型的解释,并给出下一步建议. \",\n"
            "  \"decision\": {\n"
            "    \"IS_CALL_TOOLS\": false,\n"
            "    \"TOOL_CALL_REQUESTS\": [],\n"
            "    \"RESPONSE_TO_USER\": {\n"
            "      \"content_type\": \"text/plain\",\n"
            "      \"content\": \"电容是一种能够储存电荷的电子元件,由两块导体板中间夹一层绝缘介质构成. 它的主要特性是电容量,单位是法拉(F),常用单位有微法(μF)、纳法(nF)和皮法(pF). 电容在电路中常用于滤波、耦合、隔直流、储能等. \",\n"
            "      \"suggestions_for_next_steps\": [\n"
            "        {\"text_for_user\": \"您想了解电容在具体电路中的应用吗？\", \"action_type\": \"USER_INPUT_EXPECTED\"},\n"
            "        {\"text_for_user\": \"需要我帮您在当前电路中添加一个电容吗？\", \"action_type\": \"USER_INPUT_EXPECTED\", \"action_payload\": \"请帮我添加一个10uF的电解电容\"}\n"
            "      ],\n"
            "      \"requires_user_clarification_for_current_request\": false\n"
            "    }\n"
            "  },\n"
            "  \"diagnostics\": {\"llm_confidence_score_for_this_output\": 0.95},\n"
            "  \"usage_metadata\": null\n"
            "}\n"
            "```\n"
        )

        tool_call_example_v8_1 = (
            "\n【通用示例2: 需要调用工具时的输出V8.2.2 JSON】\n"
            "如果用户说: “帮我加一个1k欧姆的电阻R1,再加一个3V的电池B1,然后把它们连起来. ”\n"
            "您的输出V8.2.2 JSON应类似 (ID和时间戳会变化,每个tool_call_id必须唯一,由您生成): \n"
            "```json\n"
            "{\n"
            "  \"request_id\": \"" + (request_id or "user_req_example_id_456") + "\",\n"
            "  \"llm_interaction_id\": \"" + llm_interaction_id_example_plan_prefix + "_multi_tool_rc\",\n"
            "  \"timestamp_utc\": \"" + current_timestamp_utc + "\",\n"
            "  \"status\": \"success\",\n"
            "  \"error_details\": null,\n"
            "  \"execution_phase\": \"planning\",\n"
            "  \"thought_process\": \"用户需要执行三个操作: 1. 添加电阻R1 (1kΩ). 2. 添加电池B1 (3V). 3. 连接R1和B1. 我将按顺序规划这三个工具调用. 确保为每个工具调用生成唯一的tool_call_id. 并为用户提供一个过渡性的回复. \",\n"
            "  \"decision\": {\n"
            "    \"IS_CALL_TOOLS\": true,\n"
            "    \"TOOL_CALL_REQUESTS\": [\n"
            "      {\n"
            "        \"tool_call_id\": \"tc_add_r1_" + str(uuid4())[:8] + "\",\n"
            "        \"tool_name\": \"add_component_tool\",\n"
            "        \"tool_arguments\": {\"component_type\": \"电阻\", \"component_id\": \"R1\", \"value\": \"1kΩ\"},\n"
            "        \"ui_hints\": {\"display_name_for_tool\": \"添加电阻 R1 (1kΩ)\", \"estimated_duration_category\": \"short\"},\n"
            "        \"estimated_complexity_or_notes\": \"标准电阻添加操作,低复杂度. \"\n"
            "      },\n"
            "      {\n"
            "        \"tool_call_id\": \"tc_add_b1_" + str(uuid4())[:8] + "\",\n"
            "        \"tool_name\": \"add_component_tool\",\n"
            "        \"tool_arguments\": {\"component_type\": \"电池\", \"component_id\": \"B1\", \"value\": \"3V\"},\n"
            "        \"ui_hints\": {\"display_name_for_tool\": \"添加电池 B1 (3V)\", \"estimated_duration_category\": \"short\"},\n"
            "        \"estimated_complexity_or_notes\": \"标准电池添加操作,低复杂度. \"\n"
            "      },\n"
            "      {\n"
            "        \"tool_call_id\": \"tc_conn_r1b1_" + str(uuid4())[:8] + "\",\n"
            "        \"tool_name\": \"connect_components_tool\",\n"
            "        \"tool_arguments\": {\"comp1_id\": \"R1\", \"comp2_id\": \"B1\"},\n"
            "        \"ui_hints\": {\"display_name_for_tool\": \"连接 R1 与 B1\", \"estimated_duration_category\": \"short\"},\n"
            "        \"estimated_complexity_or_notes\": \"连接两个已添加的元件,依赖前两个操作成功. \"\n"
            "      }\n"
            "    ],\n"
            "    \"RESPONSE_TO_USER\": {\n"
            "      \"content_type\": \"text/plain\",\n"
            "      \"content\": \"好的,我正在为您添加电阻R1 (1kΩ)、电池B1 (3V),并将它们连接起来. 请稍候...\",\n"
            "      \"suggestions_for_next_steps\": [\n"
            "        {\"text_for_user\": \"操作完成后,您想查看电路图吗？\", \"action_type\": \"USER_INPUT_EXPECTED\"},\n"
            "        {\"text_for_user\": \"需要为这些元件设置其他参数吗？\", \"action_type\": \"USER_INPUT_EXPECTED\"}\n"
            "      ],\n"
            "      \"requires_user_clarification_for_current_request\": false\n"
            "    }\n"
            "  },\n"
            "  \"diagnostics\": {\"llm_confidence_score_for_this_output\": 0.9, \"alternative_plans_considered_count\": 0},\n"
            "  \"usage_metadata\": null\n"
            "}\n"
            "```\n"
        )

        replan_example_v8_1 = ""
        if is_replanning:
            replan_example_v8_1 = (
                "\n【重规划示例 (V8.2.2 JSON): 工具失败后,成功重规划并调用新/修正的工具】\n"
                "假设历史记录中有如下用户请求和失败的工具调用: \n"
                "  User: \"连接 R10 和 C5\"\n"
                "  Assistant (Previous Plan JSON): ... (Planned connect_components_tool for R10, C5, llm_interaction_id: " + example_prev_tool_call_id + "_plan) ...\n"
                "  Tool (connect_components_tool, tool_call_id: " + example_prev_tool_call_id + "_tool, name: connect_components_tool) result (in history): { \"role\": \"tool\", ..., \"content\": \"{\\\"status\\\": \\\"failure\\\", \\\"message\\\": \\\"错误: 元件 'R10' 在电路中不存在. \\\", \\\"error\\\": { \\\"error_type\\\": \\\"CIRCUIT_OPERATION_ERROR\\\", \\\"error_code\\\": \\\"COMPONENT_NOT_FOUND_FOR_CONNECTION\\\", ... }}\" }\n"
                "  Current Circuit State (in memory_context): (R10 does not exist, C5 exists)\n"
                "您在【当前重规划】时,分析后发现R10不存在,需要先添加. 您的新V8.2.2 JSON输出应类似: \n"
                "```json\n"
                "{\n"
                "  \"request_id\": \"" + (request_id or "user_req_example_id_789") + "\",\n"
                "  \"llm_interaction_id\": \"" + llm_interaction_id_example_plan_prefix + "_replan_add_then_connect\",\n"
                "  \"timestamp_utc\": \"" + current_timestamp_utc + "\",\n"
                "  \"status\": \"success\",\n"
                "  \"error_details\": null,\n"
                "  \"execution_phase\": \"planning\",\n"
                "  \"thought_process\": \"重规划开始. 分析历史: 用户想连接R10和C5. 上一个计划 (llm_interaction_id: " + example_prev_tool_call_id + "_plan) 中调用connect_components_tool (tool_call_id: " + example_prev_tool_call_id + "_tool) 失败了,工具报告原因是元件 'R10' 在电路中不存在. 当前电路状态也确认R10不在电路中，但C5存在。因此,我的新计划是首先添加R10 (用户未指定类型或值,我将默认为电阻,并提供一个常用值如1kΩ,或明确标记为'Terminal'如果用途不明). 然后再调用connect_components_tool连接新创建的R10和已存在的C5. 本次规划逻辑清晰，应标记为status: 'success'.\",\n"
                "  \"decision\": {\n"
                "    \"IS_CALL_TOOLS\": true,\n"
                "    \"TOOL_CALL_REQUESTS\": [\n"
                "      {\n"
                "        \"tool_call_id\": \"tc_replan_add_r10_" + str(uuid4())[:8] + "\",\n"
                "        \"tool_name\": \"add_component_tool\",\n"
                "        \"tool_arguments\": {\"component_type\": \"电阻\", \"component_id\": \"R10\", \"value\": \"1k\"},\n"
                "        \"ui_hints\": {\"display_name_for_tool\": \"(修正) 添加电阻 R10 (1kΩ)\"}\n"
                "      },\n"
                "      {\n"
                "        \"tool_call_id\": \"tc_replan_connect_r10c5_" + str(uuid4())[:8] + "\",\n"
                "        \"tool_name\": \"connect_components_tool\",\n"
                "        \"tool_arguments\": {\"comp1_id\": \"R10\", \"comp2_id\": \"C5\"},\n"
                "        \"ui_hints\": {\"display_name_for_tool\": \"(修正) 连接 R10 与 C5\"}\n"
                "      }\n"
                "    ],\n"
                "    \"RESPONSE_TO_USER\": {\n"
                "      \"content_type\": \"text/plain\",\n"
                "      \"content\": \"检测到元件R10之前不存在. 我将先为您添加一个1kΩ的电阻R10,然后再将它与C5连接. \",\n"
                "      \"suggestions_for_next_steps\": [\n"
                "        {\"text_for_user\": \"操作完成后显示电路状态. \"}\n"
                "      ],\n"
                "      \"requires_user_clarification_for_current_request\": false\n"
                "    }\n"
                "  },\n"
                "  \"diagnostics\": {\"parsing_feedback_from_previous_attempt_id\": \"" + example_prev_tool_call_id + "_plan\"},\n"
                "  \"usage_metadata\": null\n"
                "}\n"
                "```\n"
            )

        prompt_parts = [
            "您是一位顶尖的、极其严谨的电路设计编程助理 (Agent Version V8.2.2-ThoughtfulUI-Fix). 您的行为必须专业、精确,并严格遵循指令. 您的输出【必须且只能是】一个符合下述V8.2.2规范的JSON对象,且该JSON对象需要被三个反引号和'json'标记包围 (即 ```json ... ```). JSON对象之外不应有任何其他文本、注释或解释. \n\n"
            "【核心任务: 规划阶段 (V8.2.2)】\n"
            "深入分析用户的最新指令、完整的对话历史(包括您之前的思考、规划以及所有工具执行结果,特别是'tool' role和'assistant' role中可能的错误反馈)、当前的电路状态和记忆. 然后,生成一个符合V8.2.2规范的JSON对象作为您的行动计划或直接回复. \n",
            replanning_guidance_v8_1,
            "【V8.2.2 JSON 输出格式规范 (必须严格遵守)】\n",
            v8_1_json_schema_description_for_prompt, # Schema itself is V8.1 compatible
            "\n【重要指令与检查清单 (V8.2.2)】:\n"
            "1.  **请求ID回显**: 准确复制System Prompt上下文中提供的 `Current Request ID` 到您的JSON输出的 `request_id` 字段. 如果未提供,则设为 `null`. \n"
            "2.  **LLM交互ID**: 【必须】为本次JSON输出生成唯一的 `llm_interaction_id`. \n"
            "3.  **UTC时间戳**: 【必须】提供当前UTC时间的ISO 8601格式 `timestamp_utc`. \n"
            "4.  **顶层 `status`**: (再次强调,请仔细阅读上面对 `status` 的详细说明和重规划指示中的要求)如果您【当前这次】成功生成了符合规范且逻辑合理的V8.2.2 JSON计划,设为 `\"success\"`. 如果您在理解请求或生成计划时遇到【自身】的内部问题,导致无法产出有效JSON,设为 `\"failure\"` 并在 `error_details` 中详细说明原因. \n"
            "5.  **`error_details` 对象**: 仅当顶层 `status` 为 `\"failure\"` 时提供. 否则为 `null`. 确保包含 `error_type`, `error_code`, `technical_message`. `is_direct_llm_failure`字段【必须】是一个布尔值. `message_to_user` 和 `failed_validation_points` 根据情况提供. \n"
            "6.  **`execution_phase`**: 在此阶段,此值【必须】是 `\"planning\"`. \n"
            "7.  **`thought_process`**: 【极其重要】请在此详细记录您的思考步骤. 务必清晰、详尽、符合逻辑。**如果正在重规划，必须解释对先前失败的分析以及新计划如何解决该问题，并明确提及对当前电路状态的参考。**\n"
            "8.  **`decision.IS_CALL_TOOLS`**: 根据您的分析决定是否需要调用工具. \n"
            "9.  **`decision.TOOL_CALL_REQUESTS`**: 如果 `IS_CALL_TOOLS` 为 `true`,此列表包含您计划调用的工具. 每个工具调用对象【必须】包含一个由您生成的唯一的 `tool_call_id` (例如 `tc_` 加上工具名和随机字符),工具名 `tool_name`,以及符合Schema的 `tool_arguments` (空对象 `{}` 如果无参数). 工具按您期望的执行顺序列出. 如果 `IS_CALL_TOOLS` 为 `false`,此字段应为 `[]` (空数组) 或 `null`. \n"
            "10. **`decision.RESPONSE_TO_USER.content`**: \n"
            "    - 如果 `IS_CALL_TOOLS` 为 `false` (直接回复): 此处是您给用户的【完整最终答复】. 它【不能】为空字符串或仅包含空白. \n"
            "    - 如果 `IS_CALL_TOOLS` 为 `true` (调用工具): 此处【应该】是一句【有意义的、能简要预示您接下来计划操作的过渡性】的话. 如果不需要,可为空字符串 `\"\"`. \n"
            "11. **`decision.RESPONSE_TO_USER.suggestions_for_next_steps`**: (可选) 提供结构化的建议列表. \n"
            "12. **`decision.RESPONSE_TO_USER.requires_user_clarification_for_current_request`**: (可选) 如果需要用户澄清,设为 `true`. \n"
            "13. **操作前检查 (重要)**: 在规划涉及操作现有元件的工具调用前,请务必通过 `thought_process` 确认这些元件是否已存在于【当前电路状态】中。如不确定或不存在,优先规划 `add_component_tool` 或 `describe_circuit_tool`. 对于 'INPUT', 'OUTPUT', 'GND' 等抽象节点,如果需要连接而它们未作为元件存在,应先用 `add_component_tool` (如 `component_type: 'Terminal'`, `component_id: 'INPUT_NODE'`)创建它们。\n\n",
            direct_qa_example_v8_1,
            tool_call_example_v8_1,
        ]
        if is_replanning:
            prompt_parts.append(replan_example_v8_1)

        prompt_parts.extend([
            "\n【可用工具列表与参数规范 (V8.2.2)】:\n",
            tool_schemas_desc,
            "\n\n【当前上下文信息 (V8.2.2)】:\n"
            f"Current Request ID (if available, echo in your JSON's request_id field): {request_id or 'N/A_NOT_PROVIDED_IN_PROMPT_SET_TO_NULL'}\n"
            f"Current UTC Time (for your reference when generating timestamp_utc): {current_timestamp_utc}\n"
            f"当前电路与记忆摘要:\n{memory_context}\n\n"
            "【最后再次强调】: 您的输出【必须且只能是】一个被 ```json ... ``` 包围的、严格符合上述V8.2.2规范的单个JSON对象. JSON对象之外不应有任何其他文本. 请务必仔细检查JSON的语法和所有字段的类型及条件要求！任何格式偏差都将导致处理失败！"
        ])
        return "".join(prompt_parts)

    def _get_response_generation_prompt_v8_1(self, memory_context: str, tool_schemas_desc: str, request_id: Optional[str] = None) -> str:
        current_timestamp_utc = datetime.now(timezone.utc).isoformat()
        llm_interaction_id_example_resp_prefix = f"resp_ex_llm_id_{str(uuid4())[:6]}"

        v8_1_json_schema_description_for_resp_phase = """
```json
{
  "request_id": "string_or_null_current_user_request_cycle_id_echo_this_value_from_system_prompt_s_context_information_if_provided_otherwise_null",
  "llm_interaction_id": "string_MUST_BE_UNIQUE_id_for_this_llm_response_e.g.,_resp_llm_id_followed_by_8_random_chars_like_resp_llm_id_e5f6g7h8",
  "timestamp_utc": "string_current_utc_timestamp_in_iso_8601_format_e.g.,_2024-07-16T12:05:00.000Z",
  "status": "string_MUST_BE_either_'success'_or_'failure'_indicates_if_YOU_successfully_generated_this_final_response_json_FOR_THIS_ATTEMPT_If_you_cannot_formulate_a_proper_summary_or_response_NOW_then_set_to_failure",
  "error_details": {
    "error_type": "string_enum_e.g._RESPONSE_GENERATION_ERROR_LLM_OUTPUT_VALIDATION_ERROR",
    "error_code": "string_e.g._JSON_MALFORMED_SUMMARY_LOGIC_ERROR",
    "message_to_user": "string_optional_user_friendly_message_if_applicable",
    "technical_message": "string_Detailed_technical_error_message_for_THIS_response_generation_attempt.",
    "is_direct_llm_failure": "boolean_True_if_LLM_explicitly_states_it_cannot_fulfill_request_or_generate_valid_JSON_FOR_THIS_ATTEMPT_False_if_error_is_due_to_Agent_side_validation_of_an_otherwise_syntactically_valid_LLM_JSON_output_or_if_LLM_is_reporting_a_logical_failure_in_a_well_formed_JSON.",
    "failed_validation_points": [ { "json_path": "...", "issue_description": "..." } ]
  },
  "execution_phase": "string_MUST_BE_'response_generation'_for_this_task",
  "thought_process": "string_YOUR_DETAILED_STEP_BY_STEP_REASONING_Explain_how_you_interpreted_the_tool_results_from_the_history_synthesized_them_and_formulated_the_final_response_to_the_user_If_tools_failed_explain_how_you_are_reporting_this_If_it_was_a_direct_reply_from_planning_reiterate_the_reasoning_for_that_direct_reply_Be_verbose_and_clear_This_is_critical_for_debugging_and_user_understanding",
  "decision": {
    "IS_CALL_TOOLS": "boolean_MUST_BE_false_in_this_response_generation_phase",
    "TOOL_CALL_REQUESTS": [],
    "RESPONSE_TO_USER": {
      "content_type": "string_e.g._text/plain_or_application/markdown",
      "content": "string_This_is_your_FINAL_and_COMPLETE_reply_to_the_user_It_MUST_NOT_be_empty_It_should_summarize_actions_taken_report_results_and_address_the_user_s_original_request_based_on_tool_outputs_or_your_direct_knowledge_if_no_tools_were_called_in_the_first_place_This_content_is_what_the_user_will_see",
      "suggestions_for_next_steps": [
        {
          "suggestion_id": "string_optional_unique_id_for_this_suggestion_e.g._sugg_ask_about_led_color",
          "text_for_user": "string_The_suggestion_text_to_display_to_the_user_e.g._Would_you_like_to_specify_the_LED_color",
          "action_type": "string_enum_optional_USER_INPUT_EXPECTED_or_PREDEFINED_AGENT_ACTION_or_UI_NAVIGATION",
          "action_payload": "object_or_string_optional_If_PREDEFINED_AGENT_ACTION_this_could_be_a_simplified_request_object_or_command_string_for_the_agent_to_process_if_selected_by_user"
        }
      ],
      "requires_user_clarification_for_current_request": "boolean_optional_Set_to_true_if_the_current_request_cannot_proceed_without_further_input_from_the_user_and_the_content_is_asking_for_that_clarification_Default_false"
    }
  },
  "diagnostics": {
      "llm_confidence_score_for_this_output": "float_optional_0.0_to_1.0",
      "alternative_plans_considered_count": "integer_optional",
      "parsing_feedback_from_previous_attempt_id": "string_or_null"
  },
  "usage_metadata": null
}
```
"""

        response_gen_example_v8_1 = (
            "\n【示例 (V8.2.2 JSON): 总结工具结果并生成最终回复】\n"
            "假设对话历史中包含以下工具执行结果 (通常是 'role: tool' messages,其 'content' 字段是一个JSON字符串,包含了工具的输出):\n"
            "  Tool Message 1 (for tool_call_id: tc_xyz_add_r1): { \"role\": \"tool\", \"tool_call_id\": \"tc_xyz_add_r1\", \"name\": \"add_component_tool\", \"content\": \"{\\\"status\\\": \\\"success\\\", \\\"message\\\": \\\"操作成功: 已添加元件 电阻 (ID: R1) (值: 1kΩ). (系统分配ID 'R1')\\\", \\\"data\\\": {\\\"id\\\": \\\"R1\\\", \\\"type\\\": \\\"电阻\\\", \\\"value\\\": \\\"1kΩ\\\"}}\" }\n"
            "  Tool Message 2 (for tool_call_id: tc_abc_add_b1): { \"role\": \"tool\", \"tool_call_id\": \"tc_abc_add_b1\", \"name\": \"add_component_tool\", \"content\": \"{\\\"status\\\": \\\"failure\\\", \\\"message\\\": \\\"错误: ID 'B1' 已被占用. \\\", \\\"error\\\": {\\\"error_type\\\": \\\"CIRCUIT_STATE_ERROR\\\", \\\"error_code\\\": \\\"COMPONENT_ID_CONFLICT\\\", ...}}\" }\n"
            "您的输出V8.2.2 JSON应类似 (ID和时间戳会变化): \n"
            "```json\n"
            "{\n"
            "  \"request_id\": \"" + (request_id or "user_req_example_id_resp_123") + "\",\n"
            "  \"llm_interaction_id\": \"" + llm_interaction_id_example_resp_prefix + "_final_summary_rb\",\n"
            "  \"timestamp_utc\": \"" + current_timestamp_utc + "\",\n"
            "  \"status\": \"success\",\n"
            "  \"error_details\": null,\n"
            "  \"execution_phase\": \"response_generation\",\n"
            "  \"thought_process\": \"用户要求添加R1和B1. 回顾工具执行结果: add_component_tool (ID: tc_xyz_add_r1) 成功添加了电阻R1 (1kΩ). 然而,add_component_tool (ID: tc_abc_add_b1) 在尝试添加电池B1时,由于ID冲突导致失败. 我需要向用户清晰地报告这两个结果,并解释B1添加失败的原因. 我将建议用户为B1尝试使用不同的ID,并在建议中提供可操作的选项. \",\n"
            "  \"decision\": {\n"
            "    \"IS_CALL_TOOLS\": false, \n"
            "    \"TOOL_CALL_REQUESTS\": [], \n"
            "    \"RESPONSE_TO_USER\": {\n"
            "      \"content_type\": \"text/plain\",\n"
            "      \"content\": \"您好,我已经成功为您添加了电阻R1 (1kΩ). 但是在尝试添加电池B1时遇到了问题,提示ID 'B1' 已被占用,因此未能添加成功. \",\n"
            "      \"suggestions_for_next_steps\": [\n"
            "        {\"suggestion_id\": \"sugg_retry_b1_new_id\", \"text_for_user\": \"为电池B1尝试一个新ID (例如 B2) 并重新添加\", \"action_type\": \"USER_INPUT_EXPECTED\", \"action_payload\": \"帮我添加一个3V电池B2\"},\n"
            "        {\"suggestion_id\": \"sugg_view_circuit\", \"text_for_user\": \"查看当前电路中已有的元件列表. \", \"action_type\": \"USER_INPUT_EXPECTED\", \"action_payload\": \"当前电路什么样\"}\n"
            "      ],\n"
            "      \"requires_user_clarification_for_current_request\": true \n"
            "    }\n"
            "  },\n"
            "  \"diagnostics\": {\"llm_confidence_score_for_this_output\": 0.98},\n"
            "  \"usage_metadata\": null\n"
            "}\n"
            "```\n"
        )

        return (
            "您是一位顶尖的电路设计编程助理 (Agent Version V8.2.2-ThoughtfulUI-Fix),经验丰富,技术精湛,并且极其擅长清晰、准确、诚实地汇报工作结果. 您的输出【必须且只能是】一个符合下述V8.2.2规范的JSON对象,且该JSON对象需要被三个反引号和'json'标记包围 (即 ```json ... ```). JSON对象之外不应有任何其他文本、注释或解释. \n\n"
            "【核心任务: 响应生成阶段 (V8.2.2)】\n"
            "您当前的任务是: 基于到目前为止的【完整对话历史】(包括用户最初的指令、您在规划阶段生成的V8.2.2 JSON计划、以及所有【已执行工具的结果详情】,这些工具结果是以 'role: tool', 'tool_call_id: ...', 'name: ...', 'content: JSON_string_of_tool_output' 的格式存在于历史记录中的),生成【最终的、面向用户的V8.2.2 JSON回复】. \n\n"
            "【V8.2.2 JSON 输出格式规范 (与规划阶段结构相同,但有特定值要求 - 再次强调)】\n"
            f"{v8_1_json_schema_description_for_resp_phase}\n" # Schema itself is V8.1 compatible
            "【重要指令与检查清单 (V8.2.2 - 响应生成阶段特定要求)】:\n"
            "1.  **`request_id`, `llm_interaction_id`, `timestamp_utc`, `status`, `error_details`**: 同规划阶段,但 `llm_interaction_id` 应使用新的唯一ID (例如 `resp_llm_id_...`). `error_details.is_direct_llm_failure`【必须】是布尔值。\n"
            "2.  **`execution_phase`**: 在此阶段,此值【必须】是 `\"response_generation\"`. \n"
            "3.  **`thought_process`**: 【极其重要】详细记录您如何分析工具结果(或为何是直接回复),并如何组织最终给用户的答复. 如果工具执行有成功有失败,要清晰说明如何整合这些信息. \n"
            "4.  **`decision.IS_CALL_TOOLS`**: 在此响应生成阶段,此值【必须】为 `false`. \n"
            "5.  **`decision.TOOL_CALL_REQUESTS`**: 在此响应生成阶段,此列表【必须】为 `[]` (空数组) 或 `null`. \n"
            "6.  **`decision.RESPONSE_TO_USER.content`**: 这是您基于所有先前步骤(包括工具执行结果,或规划阶段的直接回复决策)生成的【最终、完整、友好】的文本回复. 它【不能】为空字符串或仅包含空白. 这是用户将看到的最终内容. \n"
            "7.  **`decision.RESPONSE_TO_USER.suggestions_for_next_steps`**: (可选但推荐) 提供结构化的后续操作建议列表. \n"
            "8.  **`decision.RESPONSE_TO_USER.requires_user_clarification_for_current_request`**: (可选) 如果最终回复是在请求用户澄清,设为 `true`. \n"
            "9.  **回顾工具结果**: 仔细检查对话历史中 `role: tool` 的消息. 这些消息的 `content` 字段是一个JSON字符串,包含了对应 `tool_call_id` 的工具执行状态 (`status`)、消息 (`message`) 和可能的错误 (`error`) 或数据 (`data`). 您的最终回复必须准确反映这些结果,对用户透明. \n\n"
            f"{response_gen_example_v8_1}\n"
            "【上下文参考信息 (仅供你回顾 - V8.2.2)】:\n"
            f"Current Request ID (if available, echo in your JSON's request_id field): {request_id or 'N/A_NOT_PROVIDED_IN_PROMPT_SET_TO_NULL'}\n"
            f"Current UTC Time (for your reference when generating timestamp_utc): {current_timestamp_utc}\n"
            f"当前电路与记忆摘要:\n{memory_context}\n"
            f"我的可用工具列表 (仅供你参考,此阶段不应再调用它们):\n{tool_schemas_desc}\n\n"
            "【最后再次强调】: 您的输出【必须且只能是】一个被 ```json ... ``` 包围的、严格符合上述V8.2.2规范的单个JSON对象. 在这个阶段,您【绝对不能】再请求调用任何新工具. 您的任务是总结并回复. "
        )

