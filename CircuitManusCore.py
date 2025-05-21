
# @FileName: circuitmanus.py
# @Version: V1.0.0 - 核心电路交互逻辑与DuckDuckGo搜索工具集 (深化修复ToolExecutor异步调用新)
# @Author: 您的专属程序员 (致力于构建稳定、清晰、可扩展的智能助手核心)
# @Date: [当前日期] - 深化修复ToolExecutor对异步工具的调用，确保协程被正确await。
# @License: MIT License
# @Description:
# ==============================================================================================
#  Manus 系统 V1.0.0 技术实现说明 (附带11个工具)
# ==============================================================================================
# (V1.0.0 变更日志:
#  - 针对ToolExecutor中异步工具返回协程对象而非执行结果的问题，进行了更直接的await调用修复。
#  - 强化日志，在ToolExecutor调用工具前后打印更多关于工具方法类型和返回类型的信息。
#  - 确保duckduckgo_search_tool的返回结构在所有路径下都符合预期。)
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
import httpx
from duckduckgo_search import DDGS

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
    sys.stderr.write(f"严重错误: 无法创建日志目录 '{LOG_DIR}'. 错误信息: {e}\n")
    sys.stderr.write("文件日志功能可能不可用。程序将仅使用控制台日志继续运行。\n")

current_time_for_log = datetime.now()
# 更新日志文件名以反映版本
log_file_name = os.path.join(
    LOG_DIR,
    f"agent_log_v1_1_3_async_call_fix_{current_time_for_log.strftime('%Y%m%d_%H%M%S')}_{current_time_for_log.microsecond // 1000:03d}_P{os.getpid()}.log"
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
    logger.info(f"文件日志配置成功。日志消息也将保存至: {os.path.abspath(log_file_name)}")
except Exception as e:
    logger.error(f"严重错误: 配置日志文件到 '{log_file_name}' 失败。错误信息: {e}", exc_info=True)
    logger.error("Agent 将仅使用控制台日志继续运行。")

logging.getLogger("zhipuai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("duckduckgo_search").setLevel(logging.WARNING)


# --- 电路元件数据类 ---
class CircuitComponent:
    __slots__ = ['id', 'type', 'value']
    def __init__(self, component_id: str, component_type: str, value: Optional[str] = None):
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError("元件 ID 必须是有效的非空字符串。")
        if not isinstance(component_type, str) or not component_type.strip():
            raise ValueError("元件类型必须是有效的非空字符串。")
        
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
        logger.info("[Circuit] 初始化电路实体...")
        self.components: Dict[str, CircuitComponent] = {}
        self.connections: Set[Tuple[str, str]] = set()
        self._component_counters: Dict[str, int] = {
            'R': 0, 'L': 0, 'B': 0, 'S': 0, 'C': 0, 'V': 0, 'G': 0, 'U': 0, 'O': 0,
            'I': 0, 'A': 0, 'D': 0, 'P': 0, 'F': 0, 'H': 0,
            'T': 0, 'N': 0, 'IN': 0, 'OUT': 0,
            'SRCH': 0 
        }
        logger.info("[Circuit] 电路实体初始化完成。")

    def add_component(self, component: CircuitComponent):
        if component.id in self.components:
            raise ValueError(f"元件 ID '{component.id}' 已被占用。")
        self.components[component.id] = component
        logger.debug(f"[Circuit] 元件 '{component.id}' ({component.type}) 已添加到电路。")

    def remove_component(self, component_id: str) -> Tuple[Dict[str, Any], int]:
        comp_id_upper = component_id.strip().upper()
        if comp_id_upper not in self.components:
            raise ValueError(f"元件 '{comp_id_upper}' 在电路中不存在。")
        
        removed_component_details = self.components[comp_id_upper].to_dict()
        del self.components[comp_id_upper]
        
        connections_to_remove = {conn for conn in self.connections if comp_id_upper in conn}
        removed_connections_count = len(connections_to_remove)
        for conn in connections_to_remove:
            self.connections.remove(conn)
            logger.debug(f"[Circuit] 移除了涉及元件 '{comp_id_upper}' 的连接 {conn}。")
        
        logger.debug(f"[Circuit] 元件 '{comp_id_upper}' 及其相关 {removed_connections_count} 个连接已从电路中移除。")
        return removed_component_details, removed_connections_count


    def connect_components(self, id1: str, id2: str) -> bool:
        id1_upper = id1.strip().upper()
        id2_upper = id2.strip().upper()
        if id1_upper == id2_upper: raise ValueError(f"不能将元件 '{id1_upper}' 连接到它自己。")
        if id1_upper not in self.components: raise ValueError(f"元件 '{id1_upper}' 在电路中不存在。")
        if id2_upper not in self.components: raise ValueError(f"元件 '{id2_upper}' 在电路中不存在。")
        
        connection = tuple(sorted((id1_upper, id2_upper)))
        if connection in self.connections:
             logger.warning(f"[Circuit] 连接 '{id1_upper}' <--> '{id2_upper}' 已存在。")
             return False
        self.connections.add(connection)
        logger.debug(f"[Circuit] 添加了连接: {id1_upper} <--> {id2_upper}。")
        return True

    def disconnect_components(self, id1: str, id2: str) -> bool:
        id1_upper = id1.strip().upper()
        id2_upper = id2.strip().upper()
        connection = tuple(sorted((id1_upper, id2_upper)))
        if connection not in self.connections:
             logger.warning(f"[Circuit] 连接 '{id1_upper}' <--> '{id2_upper}' 不存在,无需断开。")
             return False
        self.connections.remove(connection)
        logger.debug(f"[Circuit] 断开了连接: {id1_upper} <--> {id2_upper}。")
        return True

    def get_state_description(self) -> str:
        logger.debug("[Circuit] 正在生成电路状态描述...")
        num_components = len(self.components)
        num_connections = len(self.connections)

        if num_components == 0 and num_connections == 0:
            return "【当前电路状态】: 电路为空。"

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
        logger.debug("[Circuit] 电路状态描述生成完毕。")
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
            "terminal": "T", "端子": "T", "connection point": "P", "连接点": "P",
            "node": "N", "节点": "N",
            "input": "IN", "输入": "IN", "output": "OUT", "输出": "OUT",
            "search_record": "SRCH", "搜索记录": "SRCH", 
            "component": "O", "元件": "O",
        }

        for code in type_map.values():
            if code not in self._component_counters:
                 self._component_counters[code] = 0

        cleaned_type = component_type.strip().lower()
        type_code = "O"
        best_match_len = 0

        if cleaned_type == "input": type_code = "IN"
        elif cleaned_type == "output": type_code = "OUT"
        elif cleaned_type == "ground" or cleaned_type == "地": type_code = "G"
        else:
            for keyword, code in type_map.items():
                if keyword in cleaned_type and len(keyword) > best_match_len:
                    type_code = code
                    best_match_len = len(keyword)

        if type_code == "O" and cleaned_type not in ["component", "元件"]:
             logger.warning(f"[Circuit] 未找到类型 '{component_type}' 的特定前缀,将使用通用前缀 'O'。")

        MAX_ID_ATTEMPTS = 10000
        for attempt in range(MAX_ID_ATTEMPTS):
            self._component_counters[type_code] += 1
            gen_id = f"{type_code}{self._component_counters[type_code]}"
            if gen_id not in self.components:
                logger.debug(f"[Circuit] 生成唯一 ID: '{gen_id}' (尝试 {attempt + 1})。")
                return gen_id
            logger.debug(f"[Circuit] ID '{gen_id}' 已存在,尝试下一个。(尝试 {attempt + 1})。")

        raise RuntimeError(f"未能为类型 '{component_type}' (代码 '{type_code}') 生成唯一 ID ({MAX_ID_ATTEMPTS} 次尝试后)。")

    def clear(self):
        logger.info("[Circuit] 正在清空电路状态...")
        comp_count = len(self.components)
        conn_count = len(self.connections)

        self.components = {}
        self.connections = set()
        self._component_counters = {k: 0 for k in self._component_counters}

        logger.info(f"[Circuit] 电路状态已清空 (移除了 {comp_count} 个元件, {conn_count} 个连接,并重置了所有 ID 计数器)。")

# --- 工具注册装饰器 ---
def register_tool(description: str, parameters: Dict[str, Any]):
    def decorator(func):
        func._tool_schema = {"description": description, "parameters": parameters}
        func._is_tool = True
        # functools.wraps is important to preserve metadata, especially for inspect.iscoroutinefunction
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs): # if original func is async
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs): # if original func is sync
            return func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator

# --- 模块化组件: MemoryManager (记忆管理器) ---
class MemoryManager:
    def __init__(self, max_short_term_items: int = 30, max_long_term_items: int = 200):
        logger.info("[MemoryManager] 初始化记忆模块...")
        if max_short_term_items <= 1:
            raise ValueError("参数 'max_short_term_items' 必须大于 1。")

        self.max_short_term_items = max_short_term_items
        self.max_long_term_items = max_long_term_items
        self.short_term: List[Dict[str, Any]] = []
        self.long_term: List[str] = []
        self.circuit: Circuit = Circuit()

        logger.info(f"[MemoryManager] 记忆模块初始化完成。短期记忆上限: {max_short_term_items} 条, 长期记忆上限: {max_long_term_items} 条。")

    def add_to_short_term(self, message: Dict[str, Any]):
        logger.debug(f"[MemoryManager] 添加消息到短期记忆 (Role: {message.get('role', 'N/A')})。当前数量: {len(self.short_term)}。")
        self.short_term.append(message)
        current_size = len(self.short_term)
        if current_size > self.max_short_term_items:
            logger.debug(f"[MemoryManager] 短期记忆超限 ({current_size}/{self.max_short_term_items}),执行修剪...")
            items_to_remove_count = current_size - self.max_short_term_items
            non_system_indices = [i for i, msg in enumerate(self.short_term) if msg.get("role") != "system"]
            num_to_actually_remove = min(items_to_remove_count, len(non_system_indices))

            if num_to_actually_remove > 0:
                indices_to_remove_set = set(non_system_indices[:num_to_actually_remove])
                removed_roles = [self.short_term[i].get('role', 'N/A') for i in sorted(list(indices_to_remove_set))]
                new_short_term = [msg for i, msg in enumerate(self.short_term) if i not in indices_to_remove_set]
                self.short_term = new_short_term
                logger.info(f"[MemoryManager] 短期记忆修剪完成,移除了 {num_to_actually_remove} 条最旧的非系统消息 (角色: {removed_roles})。")
            elif items_to_remove_count > 0:
                 logger.warning(f"[MemoryManager] 短期记忆超限 ({current_size}/{self.max_short_term_items}) 但未能找到足够的非系统消息进行移除。")
        logger.debug(f"[MemoryManager] 添加后短期记忆数量: {len(self.short_term)}。")

    def add_to_long_term(self, knowledge_snippet: str):
        MAX_SNIPPET_LENGTH = 10000
        if len(knowledge_snippet) > MAX_SNIPPET_LENGTH:
            logger.warning(f"[MemoryManager] 尝试添加的长期记忆片段过长 ({len(knowledge_snippet)} 字符),已截断为 {MAX_SNIPPET_LENGTH} 字符。")
            knowledge_snippet = knowledge_snippet[:MAX_SNIPPET_LENGTH] + "... (已截断)"

        logger.debug(f"[MemoryManager] 添加知识到长期记忆: '{knowledge_snippet[:1000]}{'...' if len(knowledge_snippet) > 100 else ''}'。当前数量: {len(self.long_term)}。")
        self.long_term.append(knowledge_snippet)
        if len(self.long_term) > self.max_long_term_items:
            removed_snippet = self.long_term.pop(0)
            logger.info(f"[MemoryManager] 长期记忆超限 ({self.max_long_term_items}), 移除最旧知识: '{removed_snippet[:50]}...'。")
        logger.debug(f"[MemoryManager] 添加后长期记忆数量: {len(self.long_term)}。")

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
                logger.debug(f"[MemoryManager] 已提取最近 {len(recent_items)} 条长期记忆 (倒序)。")
        long_term_str += "\n(注: 当前仅使用最近期记忆,未来版本将实现基于相关性的检索。)"
        context = f"{circuit_desc}{long_term_str}".strip()
        logger.debug(f"[MemoryManager] 记忆上下文 (电路+长期) 格式化完成。")
        return context

# --- 模块化组件: LLMInterface (LLM 交互接口) ---
class LLMInterface:
    def __init__(self, agent_instance: 'CircuitAgent', model_name: str = "glm-z1-flash", default_temperature: float = 0.01, default_max_tokens: int = 8190):
        logger.info(f"[LLMInterface V1.0.0] 初始化 LLM 接口,目标模型: {model_name}。")
        if not agent_instance or not hasattr(agent_instance, 'api_key'):
             raise ValueError("LLMInterface 需要一个包含 'api_key' 属性的 Agent 实例。")
        self.agent_instance = agent_instance
        api_key = self.agent_instance.api_key
        if not api_key: raise ValueError("智谱 AI API Key 不能为空。")
        try:
            self.client = ZhipuAI(api_key=api_key)
            logger.info("[LLMInterface V1.0.0] 智谱 AI 客户端初始化成功。")
        except Exception as e:
            logger.critical(f"[LLMInterface V1.0.0] 初始化智谱 AI 客户端失败: {e}", exc_info=True)
            raise ConnectionError(f"初始化智谱 AI 客户端失败: {e}") from e

        self.model_name = model_name
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens
        logger.info(f"[LLMInterface V1.0.0] LLM 接口初始化完成 (模型: {model_name}, 温度: {default_temperature}, 最大Token数: {default_max_tokens}, 流式输出: False)。")

    async def call_llm(self, messages: List[Dict[str, Any]], execution_phase: str, status_callback: Optional[Callable[[Dict], Awaitable[None]]] = None) -> Any:
        call_args = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens,
            "stream": False,
        }

        logger.info(f"[LLMInterface V1.0.0] 准备异步调用 LLM ({self.model_name}, 阶段: {execution_phase}, 期望输出格式: <think> 标签后跟 JSON)...")
        logger.debug(f"[LLMInterface V1.0.0] 发送的消息条数: {len(messages)}。")
        if logger.isEnabledFor(logging.DEBUG) and len(messages) > 0:
             try:
                 messages_content_for_log = []
                 for m_idx, m in enumerate(messages):
                     role = m.get("role")
                     content = str(m.get("content",""))
                     if role == "system":
                         content_preview = content[:10000] + ("..." if len(content) > 10000 else "")
                     else:
                         content_preview = content[:1000] + ("..." if len(content) > 200 else "")
                     messages_content_for_log.append({"index": m_idx, "role": role, "content_preview_length": len(content), "content_preview": content_preview})
                 messages_summary = json.dumps(messages_content_for_log, ensure_ascii=False, indent=2)
                 logger.debug(f"[LLMInterface V1.0.0] 发送给 LLM 的消息列表 (预览):\n{messages_summary}")
             except Exception as e_json:
                 logger.debug(f"[LLMInterface V1.0.0] 无法序列化消息列表进行调试日志: {e_json}")

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
            response = await asyncio.to_thread(self.client.chat.completions.create, **call_args)
            duration = time.monotonic() - start_time
            logger.info(f"[LLMInterface V1.0.0] LLM 异步调用成功。耗时: {duration:.3f} 秒。")
            if status_callback:
                await status_callback({
                    "type": "llm_communication_status",
                    "request_id": request_id_to_send,
                    "llm_phase": execution_phase,
                    "status": "completed",
                    "message": f"与智能大脑 ({self.model_name}) 沟通完成 ({execution_phase})。",
                    "details": {"duration_seconds": duration}
                })

            if response:
                if response.usage: logger.info(f"[LLMInterface V1.0.0] Token 统计: Prompt={response.usage.prompt_tokens}, Completion={response.usage.completion_tokens}, Total={response.usage.total_tokens}")
                if response.choices:
                    finish_reason = response.choices[0].finish_reason
                    logger.info(f"[LLMInterface V1.0.0] 完成原因: {finish_reason}")
                    if finish_reason == 'length': logger.warning("[LLMInterface V1.0.0] LLM 响应因达到最大 token 限制而被截断！这可能导致输出不完整！")
                    raw_llm_content = response.choices[0].message.content
                    logger.debug(f"[LLMInterface V1.0.0] LLM 原始响应内容 (完整):\n{raw_llm_content}")
                else:
                    logger.warning("[LLMInterface V1.0.0] LLM 响应中缺少 'choices' 字段。")
            else:
                 logger.error("[LLMInterface V1.0.0] LLM API 调用返回了 None！")
                 raise ConnectionError("LLM API call returned None.")
            return response
        except Exception as e:
            logger.error(f"[LLMInterface V1.0.0] LLM API 异步调用失败: {e}", exc_info=True)
            if status_callback:
                 await status_callback({
                    "type": "llm_communication_status",
                    "request_id": request_id_to_send,
                    "llm_phase": execution_phase,
                    "status": "error",
                    "message": f"与智能大脑 ({self.model_name}) 沟通失败 ({execution_phase})。",
                    "details": {"error": str(e), "error_type": type(e).__name__}
                 })
            raise

# --- 模块化组件: OutputParser (输出解析器) ---
class OutputParser:
    def __init__(self, agent_tools_registry: Optional[Dict[str, Dict[str, Any]]] = None):
        logger.info("[OutputParser] 初始化输出解析器 (适配 ManusLLMResponse-V1.0.0 CamelCase JSON结构,提取 <think> 标签,增强布尔解析)。")
        self.agent_tools_registry = agent_tools_registry if agent_tools_registry else {}

    def _validate_tool_arguments(self, tool_name: str, tool_arguments: Dict[str, Any], tool_call_id: str) -> List[Dict[str, str]]:
        validation_errors: List[Dict[str, str]] = []
        if not self.agent_tools_registry or tool_name not in self.agent_tools_registry:
            validation_errors.append({
                "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolName",
                "issue_description": f"工具 '{tool_name}' 未在 Agent 的注册表中找到。"
            })
            return validation_errors

        tool_schema = self.agent_tools_registry[tool_name]
        param_schema_props = tool_schema.get("parameters", {}).get("properties", {})
        required_params = tool_schema.get("parameters", {}).get("required", [])

        for req_param in required_params:
            if req_param not in tool_arguments:
                validation_errors.append({
                    "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{req_param}",
                    "issue_description": f"工具 '{tool_name}' 的必需参数 '{req_param}' 缺失。"
                })

        for arg_name, arg_value in tool_arguments.items():
            if arg_name not in param_schema_props:
                validation_errors.append({
                    "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 是未在 Schema 中定义的未知参数。"
                })
                continue

            expected_type_str = param_schema_props[arg_name].get("type")
            is_optional_and_null_like = (arg_name not in required_params) and (arg_value is None)

            if expected_type_str == "string" and not isinstance(arg_value, str):
                if not is_optional_and_null_like:
                    validation_errors.append({
                        "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                        "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是字符串,但得到的是 {type(arg_value).__name__}。"
                    })
            elif expected_type_str == "integer" and not isinstance(arg_value, int):
                 if not (is_optional_and_null_like and expected_type_str == "integer"): 
                    validation_errors.append({
                        "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                        "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是整数,但得到的是 {type(arg_value).__name__}。"
                    })
            elif expected_type_str == "number" and not isinstance(arg_value, (int, float)):
                 if not (is_optional_and_null_like and expected_type_str == "number"):
                    validation_errors.append({
                        "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                        "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是数字,但得到的是 {type(arg_value).__name__}。"
                    })
            elif expected_type_str == "boolean" and not isinstance(arg_value, bool):
                 validation_errors.append({
                    "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是布尔值,但得到的是 {type(arg_value).__name__}。"
                })
            elif expected_type_str == "object" and not isinstance(arg_value, dict):
                 validation_errors.append({
                    "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是对象(字典),但得到的是 {type(arg_value).__name__}。"
                })
            elif expected_type_str == "array" and not isinstance(arg_value, list):
                 validation_errors.append({
                    "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是数组(列表),但得到的是 {type(arg_value).__name__}。"
                })
        return validation_errors


    def parse_llm_response_to_structured_json(self, llm_api_response_message: Any, execution_phase: str) -> Tuple[Optional[Dict[str, Any]], str, List[Dict[str,str]]]:
        parser_id = f"parse{str(uuid4())[:8]}"
        logger.debug(f"[{parser_id}-OutputParser] 开始解析 LLM 响应 (阶段: {execution_phase})...")
        parsed_json_dict: Optional[Dict[str, Any]] = None
        error_message: str = ""
        failed_validation_points_list: List[Dict[str, str]] = []
        extracted_thought_process: Optional[str] = None

        if llm_api_response_message is None:
            error_message = "LLM 响应对象 (Message) 为 None。"
            logger.error(f"[{parser_id}-OutputParser] 解析失败: {error_message}")
            return None, error_message, [{"jsonPath": "root", "issue_description": error_message}]

        raw_content = getattr(llm_api_response_message, 'content', None)
        if not raw_content or not raw_content.strip():
            error_message = "LLM 响应内容 (content 字段) 为空或仅包含空白字符。"
            logger.error(f"[{parser_id}-OutputParser] 解析失败: {error_message}")
            return None, error_message, [{"jsonPath": "content", "issue_description": error_message}]

        logger.debug(f"[{parser_id}-OutputParser] 接收到的原始 LLM content (完整):\n{raw_content}")

        content_to_parse_for_json = raw_content
        think_match = re.search(r"<think>(.*?)</think>", raw_content, re.DOTALL | re.IGNORECASE)

        if think_match:
            extracted_thought_process = think_match.group(1).strip()
            content_to_parse_for_json = raw_content[think_match.end():].strip()
            logger.info(f"[{parser_id}-OutputParser] 成功提取到 <think>...</think> 内容。")
            logger.debug(f"[{parser_id}-OutputParser] 提取的思考过程 (预览):\n{extracted_thought_process[:1000]}...")
            logger.debug(f"[{parser_id}-OutputParser] 剩余内容待解析为JSON (预览):\n{content_to_parse_for_json[:1000]}...")
            if not content_to_parse_for_json:
                 error_message = "LLM 响应包含 <think> 块但之后没有内容可解析为 JSON。"
                 logger.error(f"[{parser_id}-OutputParser] 解析失败: {error_message}")
                 return None, error_message, [{"jsonPath": "root_after_think_block", "issue_description": error_message}]
        else:
            logger.warning(f"[{parser_id}-OutputParser] 未在LLM响应中找到有效的 <think>...</think> 块,将尝试按旧方式解析整个内容。")

        json_string_to_parse = content_to_parse_for_json.strip()
        match_md_json = re.search(r"```json\s*(.*?)\s*```", json_string_to_parse, re.DOTALL | re.IGNORECASE)
        if match_md_json:
            json_string_to_parse = match_md_json.group(1).strip()
            logger.debug(f"[{parser_id}-OutputParser] 从 Markdown 代码块中提取到 JSON 字符串。")
        else:
            first_brace = json_string_to_parse.find('{')
            last_brace = json_string_to_parse.rfind('}')
            if first_brace > 0 and (last_brace == -1 or first_brace > last_brace) :
                prefix_content = json_string_to_parse[:first_brace].strip()
                logger.warning(f"[{parser_id}-OutputParser] 在预期的 JSON 开头 '{{' 之前检测到非空白内容: '{prefix_content[:1000]}...'。将尝试从 '{{' 开始解析。")
                json_string_to_parse = json_string_to_parse[first_brace:]
            elif first_brace == -1 :
                error_message = "无法在 LLM 响应内容 (post-<think>或完整) 中找到 JSON 对象的起始 '{'。"
                logger.error(f"[{parser_id}-OutputParser] 解析失败: {error_message} 原始响应预览 (post-<think>或完整): {json_string_to_parse[:1000]}...")
                return None, error_message, [{"jsonPath": "content_for_json_parsing", "issue_description": error_message}]

        logger.debug(f"[{parser_id}-OutputParser] 预处理后,准备解析的 JSON 字符串 (完整):\n{json_string_to_parse}")

        try:
            parsed_json_dict = json.loads(json_string_to_parse)
            logger.info(f"[{parser_id}-OutputParser] JSON 字符串成功解析为字典。")
        except json.JSONDecodeError as json_err:
            error_message = f"JSON 解析失败: {json_err}。"
            logger.error(f"[{parser_id}-OutputParser] {error_message} Raw JSON string (截断): '{json_string_to_parse[:1000]}...'")
            return None, error_message, [{"jsonPath": "root_json_parsing", "issue_description": f"JSONDecodeError: {json_err}"}]
        except Exception as e:
            error_message = f"解析 LLM 响应时发生未知错误: {e}"
            logger.error(f"[{parser_id}-OutputParser] 解析时未知错误: {error_message}", exc_info=True)
            return None, error_message, [{"jsonPath": "root_json_parsing", "issue_description": f"Unexpected parsing error: {e}"}]

        if not isinstance(parsed_json_dict, dict):
            error_message = "解析后的结果不是一个 JSON 对象 (字典)。"
            logger.error(f"[{parser_id}-OutputParser] 结构验证失败: {error_message}")
            return None, error_message, [{"jsonPath": "root_json_parsing", "issue_description": error_message}]

        if extracted_thought_process is not None:
            if "thoughtProcess" in parsed_json_dict and parsed_json_dict["thoughtProcess"] and parsed_json_dict["thoughtProcess"] != extracted_thought_process:
                logger.warning(f"[{parser_id}-OutputParser] LLM提供了<think>块和JSON内部的thoughtProcess。将优先使用<think>块内容。")
            parsed_json_dict["thoughtProcess"] = extracted_thought_process
            logger.info(f"[{parser_id}-OutputParser] 已将<think>块内容置于parsed_json_dict['thoughtProcess']。")
        elif "thoughtProcess" not in parsed_json_dict or not parsed_json_dict.get("thoughtProcess", "").strip():
             logger.warning(f"[{parser_id}-OutputParser] LLM未提供<think>块,且JSON内部的thoughtProcess为空或缺失。思考过程可能不完整。")

        required_top_level_fields = ["requestId", "llmInteractionId", "timestampUtc", "status", "executionPhase", "thoughtProcess", "decision"]
        for field in required_top_level_fields:
            if field not in parsed_json_dict:
                failed_validation_points_list.append({"jsonPath": field, "issue_description": f"缺少必需的顶级字段 '{field}'。"})

        status_val = parsed_json_dict.get("status")
        if status_val not in ["success", "failure"]:
            failed_validation_points_list.append({"jsonPath": "status", "issue_description": f"字段 'status' 的值 '{status_val}' 无效,必须是 'success' 或 'failure'。"})

        exec_phase_val = parsed_json_dict.get("executionPhase")
        if exec_phase_val not in ["planning", "response_generation"]:
            failed_validation_points_list.append({"jsonPath": "executionPhase", "issue_description": f"字段 'executionPhase' 的值 '{exec_phase_val}' 无效,必须是 'planning' 或 'response_generation'。"})
        elif exec_phase_val != execution_phase:
             failed_validation_points_list.append({"jsonPath": "executionPhase", "issue_description": f"LLM报告的 'executionPhase' ('{exec_phase_val}') 与 Agent 期望的阶段 ('{execution_phase}') 不匹配。"})

        if status_val == "failure":
            error_details_obj = parsed_json_dict.get("errorDetails")
            if not isinstance(error_details_obj, dict):
                failed_validation_points_list.append({"jsonPath": "errorDetails", "issue_description": "当 'status' 为 'failure' 时, 'errorDetails' 必须是一个对象。"})
            else:
                if not isinstance(error_details_obj.get("errorType"), str) or not error_details_obj.get("errorType","").strip():
                    failed_validation_points_list.append({"jsonPath": "errorDetails.errorType", "issue_description": "'errorDetails' 对象中缺少有效的 'errorType' 字符串。"})
                if not isinstance(error_details_obj.get("errorCode"), str) or not error_details_obj.get("errorCode","").strip():
                    failed_validation_points_list.append({"jsonPath": "errorDetails.errorCode", "issue_description": "'errorDetails' 对象中缺少有效的 'errorCode' 字符串。"})
                if not isinstance(error_details_obj.get("technicalMessage"), str) or not error_details_obj.get("technicalMessage","").strip():
                    failed_validation_points_list.append({"jsonPath": "errorDetails.technicalMessage", "issue_description": "'errorDetails' 对象中缺少有效的 'technicalMessage' 字符串。"})
                if "isDirectLlmFailure" not in error_details_obj or not isinstance(error_details_obj.get("isDirectLlmFailure"), bool):
                    logger.warning(f"[{parser_id}-OutputParser] 'errorDetails.isDirectLlmFailure' 字段缺失或类型不为布尔。Agent将假定为False。LLM输出应包含此字段。")
                    failed_validation_points_list.append({"jsonPath": "errorDetails.isDirectLlmFailure", "issue_description": "'errorDetails' 对象中缺少有效的布尔字段 'isDirectLlmFailure'。"})
        elif status_val == "success" and parsed_json_dict.get("errorDetails") is not None:
             failed_validation_points_list.append({"jsonPath": "errorDetails", "issue_description": "当 'status' 为 'success' 时, 'errorDetails' 字段必须为 null 或不存在。"})

        if not isinstance(parsed_json_dict.get("thoughtProcess"), str):
            if parsed_json_dict.get("thoughtProcess") is not None:
                logger.warning(f"[{parser_id}-OutputParser] 'thoughtProcess' 字段存在但类型不正确 (应为字符串)。")
                failed_validation_points_list.append({"jsonPath": "thoughtProcess", "issue_description": "'thoughtProcess' 字段如果存在,必须是字符串。"})
        elif not parsed_json_dict.get("thoughtProcess","").strip() and extracted_thought_process is None:
            logger.warning(f"[{parser_id}-OutputParser] LLM未提供<think>块,且JSON内部的thoughtProcess为空或缺失。思考过程可能不完整。")

        decision_obj = parsed_json_dict.get("decision")
        if not isinstance(decision_obj, dict):
            failed_validation_points_list.append({"jsonPath": "decision", "issue_description": "'decision' 字段必须是一个对象。"})
        else:
            raw_is_call_tools_val = decision_obj.get("isCallTools")
            is_call_tools_val = None
            if isinstance(raw_is_call_tools_val, bool):
                is_call_tools_val = raw_is_call_tools_val
            elif isinstance(raw_is_call_tools_val, str):
                if raw_is_call_tools_val.lower() == 'true':
                    is_call_tools_val = True
                elif raw_is_call_tools_val.lower() == 'false':
                    is_call_tools_val = False
            
            if is_call_tools_val is None:
                failed_validation_points_list.append({"jsonPath": "decision.isCallTools", "issue_description": f"'decision.isCallTools' 值 '{raw_is_call_tools_val}' 无效。必须是布尔类型或可解析为布尔的字符串('true'/'false')。"})
            else:
                decision_obj["isCallTools"] = is_call_tools_val
                logger.debug(f"[{parser_id}-OutputParser] 'isCallTools' (原始值: {raw_is_call_tools_val}) 被解析为布尔值: {is_call_tools_val}。")

            tool_call_requests = decision_obj.get("toolCallRequests")
            if is_call_tools_val is True:
                if not isinstance(tool_call_requests, list):
                    failed_validation_points_list.append({"jsonPath": "decision.toolCallRequests", "issue_description": "当 'isCallTools' 为 True 时, 'toolCallRequests' 必须是一个列表。"})
                elif not tool_call_requests:
                    logger.warning(f"[{parser_id}-OutputParser] 'isCallTools' 为 True 但 'toolCallRequests' 列表为空。这可能是一个规划逻辑问题。")
                elif tool_call_requests:
                    for i, tool_req_item in enumerate(tool_call_requests):
                        item_path_prefix = f"decision.toolCallRequests[{i}]"
                        if not isinstance(tool_req_item, dict):
                            failed_validation_points_list.append({"jsonPath": item_path_prefix, "issue_description": "列表中的每个工具调用请求必须是对象。"}); continue

                        tool_call_id = tool_req_item.get("toolCallId")
                        if not isinstance(tool_call_id, str) or not tool_call_id.strip():
                            failed_validation_points_list.append({"jsonPath": f"{item_path_prefix}.toolCallId", "issue_description": "缺少有效的 'toolCallId' 字符串。"})

                        tool_name = tool_req_item.get("toolName")
                        if not isinstance(tool_name, str) or not tool_name.strip():
                            failed_validation_points_list.append({"jsonPath": f"{item_path_prefix}.toolName", "issue_description": "缺少有效的 'toolName' 字符串。"})

                        tool_arguments = tool_req_item.get("toolArguments")
                        if not isinstance(tool_arguments, dict):
                            failed_validation_points_list.append({"jsonPath": f"{item_path_prefix}.toolArguments", "issue_description": "'toolArguments' 必须是一个对象。"})
                        elif tool_name and isinstance(tool_name, str) and tool_name.strip():
                            arg_validation_errors = self._validate_tool_arguments(tool_name, tool_arguments, tool_call_id if (tool_call_id and isinstance(tool_call_id, str) and tool_call_id.strip()) else f"index_{i}")
                            failed_validation_points_list.extend(arg_validation_errors)

                        ui_hints = tool_req_item.get("uiHints")
                        if ui_hints is not None and not isinstance(ui_hints, dict):
                            failed_validation_points_list.append({"jsonPath": f"{item_path_prefix}.uiHints", "issue_description": "'uiHints' 如果存在,必须是一个对象。"})

            elif is_call_tools_val is False:
                if tool_call_requests is not None and (not isinstance(tool_call_requests, list) or tool_call_requests):
                    failed_validation_points_list.append({"jsonPath": "decision.toolCallRequests", "issue_description": "当 'isCallTools' 为 False 时, 'toolCallRequests' 必须是 null 或空列表 []。"})

            response_user_obj = decision_obj.get("responseToUser")
            if not isinstance(response_user_obj, dict):
                failed_validation_points_list.append({"jsonPath": "decision.responseToUser", "issue_description": "'responseToUser' 必须是一个对象。"})
            else:
                if not isinstance(response_user_obj.get("contentType"), str) or not response_user_obj.get("contentType","").strip():
                     failed_validation_points_list.append({"jsonPath": "decision.responseToUser.contentType", "issue_description": "'responseToUser' 对象缺少有效的 'contentType' 字符串。"})

                resp_content = response_user_obj.get("content")
                if not isinstance(resp_content, str):
                     failed_validation_points_list.append({"jsonPath": "decision.responseToUser.content", "issue_description": "'responseToUser.content' 必须是字符串。"})

                if is_call_tools_val is False and (not resp_content or resp_content.strip() == ""):
                     if execution_phase == "response_generation":
                         failed_validation_points_list.append({"jsonPath": "decision.responseToUser.content", "issue_description": "在响应生成阶段,当不调用工具时, 'responseToUser.content' 必须是有效的非空字符串。"})
                     else:
                        failed_validation_points_list.append({"jsonPath": "decision.responseToUser.content", "issue_description": "当 'isCallTools' 为 False (直接回复) 时, 'responseToUser.content' 必须是有效的非空字符串。"})

                suggestions = response_user_obj.get("suggestionsForNextSteps")
                if suggestions is not None:
                    if not isinstance(suggestions, list):
                        failed_validation_points_list.append({"jsonPath": "decision.responseToUser.suggestionsForNextSteps", "issue_description": "'suggestionsForNextSteps' 如果存在,必须是一个列表。"})
                    else:
                        for j, sugg_item in enumerate(suggestions):
                            sugg_path_prefix = f"decision.responseToUser.suggestionsForNextSteps[{j}]"
                            if not isinstance(sugg_item, dict):
                                failed_validation_points_list.append({"jsonPath": sugg_path_prefix, "issue_description": "列表中的每个建议必须是对象。"}); continue
                            if not isinstance(sugg_item.get("textForUser"), str) or not sugg_item.get("textForUser","").strip():
                                failed_validation_points_list.append({"jsonPath": f"{sugg_path_prefix}.textForUser", "issue_description": "建议对象缺少有效的 'textForUser' 字符串。"})

                clarification_flag = response_user_obj.get("requiresUserClarificationForCurrentRequest")
                if clarification_flag is not None and not isinstance(clarification_flag, bool):
                     failed_validation_points_list.append({"jsonPath": "decision.responseToUser.requiresUserClarificationForCurrentRequest", "issue_description": "'requiresUserClarificationForCurrentRequest' 如果存在,必须是布尔类型。"})

        diagnostics_obj = parsed_json_dict.get("diagnostics")
        if diagnostics_obj is not None and not isinstance(diagnostics_obj, dict):
            failed_validation_points_list.append({"jsonPath": "diagnostics", "issue_description": "'diagnostics' 如果存在,必须是一个对象。"})

        if failed_validation_points_list:
            error_message_parts = [f"JSON 结构或内容验证失败 (共 {len(failed_validation_points_list)} 点):"]
            for err_point in failed_validation_points_list:
                error_message_parts.append(f"  -路径 '{err_point['jsonPath']}': {err_point['issue_description']}")
            error_message = "\n".join(error_message_parts)

            json_content_for_log = json.dumps(parsed_json_dict, indent=2, ensure_ascii=False) if parsed_json_dict else json_string_to_parse[:1000]
            logger.error(f"[{parser_id}-OutputParser]\n{error_message}\n解析的 JSON 内容 (可能不完整或无效):\n{json_content_for_log}")
            return None, error_message, failed_validation_points_list

        logger.info(f"[{parser_id}-OutputParser] LLM 响应 (阶段: {execution_phase}, LLM_ID: {parsed_json_dict.get('llmInteractionId', 'N/A')}) 已成功解析并验证为 ManusLLMResponse-V1.0.0兼容结构 (思考过程来源: {'<think> block' if extracted_thought_process else 'JSON field'})！")
        return parsed_json_dict, "", []


# --- 模块化组件: ToolExecutor (工具执行器) ---
class ToolExecutor:
    def __init__(self, agent_instance: 'CircuitAgent', max_tool_retries: int = 1, tool_retry_delay_seconds: float = 1.0):
        logger.info("[ToolExecutor] 初始化工具执行器 (支持异步, 重试, 失败中止, UI回调增强 V1.0.0)。") # Version update
        if not isinstance(agent_instance, CircuitAgent):
            raise TypeError("ToolExecutor 需要一个 CircuitAgent 实例。")
        self.agent_instance = agent_instance
        if not hasattr(agent_instance, 'memory_manager') or not isinstance(agent_instance.memory_manager, MemoryManager):
            raise TypeError("Agent 实例缺少有效的 MemoryManager。")

        self.verbose_mode = getattr(agent_instance, 'verbose_mode', True)
        self.max_tool_retries = max(0, max_tool_retries)
        self.tool_retry_delay_seconds = max(0.1, tool_retry_delay_seconds)

        logger.info(f"[ToolExecutor] 工具执行配置: 每个工具最多重试 {self.max_tool_retries} 次,重试间隔 {self.tool_retry_delay_seconds} 秒。详细模式: {self.verbose_mode}。")

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
        executor_id = f"exec_v1_1_3_{str(uuid4())[:8]}" 
        logger.info(f"[{executor_id}-ToolExecutor] 准备异步执行 {len(tool_call_requests_from_plan)} 个工具调用请求 (V1.0.0)...")
        execution_results_for_llm_history: List[Dict[str, Any]] = []

        if not tool_call_requests_from_plan:
            logger.info(f"[{executor_id}-ToolExecutor] 没有工具需要执行。")
            return []

        total_tools_in_plan = len(tool_call_requests_from_plan)

        for i, tool_request in enumerate(tool_call_requests_from_plan):
            llm_generated_tool_call_id = tool_request.get('toolCallId', f'fallback_tool_id_{str(uuid4())[:8]}')
            python_function_name = tool_request.get('toolName', 'unknown_function')
            parsed_arguments = tool_request.get('toolArguments', {})
            ui_hints_from_plan = tool_request.get('uiHints', {})
            tool_display_name = ui_hints_from_plan.get('displayNameForTool') or python_function_name.replace('_tool', '').replace('_', ' ').title()

            action_result_final_for_tool: Optional[Dict[str, Any]] = None
            
            logger.info(f"[{executor_id}-ToolExecutor] 处理工具调用 {i + 1}/{total_tools_in_plan}: Name='{python_function_name}', LLM_ToolCallID='{llm_generated_tool_call_id}'。")
            logger.debug(f"[{executor_id}-ToolExecutor] 待执行工具 '{python_function_name}' 的参数: {parsed_arguments}。")

            await self._send_tool_status_update(
                status_callback, llm_generated_tool_call_id, python_function_name,
                "running", f"开始执行操作: {tool_display_name}...",
                tool_arguments=parsed_arguments,
                details={"ui_hints": ui_hints_from_plan}
            )

            tool_action_method = getattr(self.agent_instance, python_function_name, None)
            
            # 检查工具方法是否存在且可调用
            if not callable(tool_action_method) or not getattr(tool_action_method, '_is_tool', False):
                err_msg_not_found = f"Agent 未实现名为 '{python_function_name}' 的已注册工具方法 (ID: {llm_generated_tool_call_id})。"
                logger.error(f"[{executor_id}-ToolExecutor] 工具未实现或未注册: {err_msg_not_found}")
                action_result_final_for_tool = {"status": "failure", "message": err_msg_not_found, "error": {"error_type": "TOOL_IMPLEMENTATION_ERROR", "error_code": "TOOL_NOT_FOUND_OR_NOT_REGISTERED", "technical_message": f"Action method '{python_function_name}' not found or not a registered tool in Agent."}}
            else: # 工具方法存在且已注册
                for retry_attempt in range(self.max_tool_retries + 1): # +1 to include the initial attempt
                    current_attempt_num = retry_attempt + 1
                    if retry_attempt > 0: # If this is a retry
                        logger.warning(f"[{executor_id}-ToolExecutor] 工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 执行失败,正在进行第 {retry_attempt}/{self.max_tool_retries} 次重试...")
                        await self._send_tool_status_update(
                            status_callback, llm_generated_tool_call_id, python_function_name,
                            "retrying", f"操作 '{tool_display_name}' 失败,等待 {self.tool_retry_delay_seconds} 秒后重试 (尝试 {current_attempt_num})...",
                            tool_arguments=parsed_arguments, details={"retry_count": retry_attempt, "max_retries": self.max_tool_retries, "ui_hints": ui_hints_from_plan}
                        )
                        await asyncio.sleep(self.tool_retry_delay_seconds)

                    action_result_this_attempt: Optional[Dict[str, Any]] = None
                    try:
                        is_coro = inspect.iscoroutinefunction(tool_action_method)
                        logger.debug(f"[{executor_id}-ToolExecutor] (尝试 {current_attempt_num}) 调用工具 '{python_function_name}'. 是否为协程: {is_coro}.")
                        
                        if is_coro:
                            # 直接 await 异步工具方法
                            logger.debug(f"[{executor_id}-ToolExecutor] (尝试 {current_attempt_num}) 直接 awaiting coroutine: {python_function_name}")
                            action_result_this_attempt = await tool_action_method(arguments=parsed_arguments)
                        else:
                            # 在线程中运行同步工具方法
                            logger.debug(f"[{executor_id}-ToolExecutor] (尝试 {current_attempt_num}) running sync tool in thread: {python_function_name}")
                            action_result_this_attempt = await asyncio.to_thread(tool_action_method, arguments=parsed_arguments)
                        
                        logger.debug(f"[{executor_id}-ToolExecutor] (尝试 {current_attempt_num}) 工具 '{python_function_name}' 返回结果类型: {type(action_result_this_attempt)}, 内容预览: {str(action_result_this_attempt)[:500]}...")

                        if not isinstance(action_result_this_attempt, dict) or \
                           'status' not in action_result_this_attempt or \
                           'message' not in action_result_this_attempt:
                            err_msg_struct = f"工具 '{python_function_name}' 返回的内部结果结构无效。期望字典包含 'status' 和 'message'。"
                            logger.error(f"[{executor_id}-ToolExecutor] 工具返回结构错误 (尝试 {current_attempt_num}): {err_msg_struct}. 实际返回类型: {type(action_result_this_attempt)}, 内容(部分): {str(action_result_this_attempt)[:200]}")
                            action_result_this_attempt = { # 强制转换为标准失败结构
                                "status": "failure", 
                                "message": f"错误: 工具 '{python_function_name}' 内部返回结果结构无效。", 
                                "error": {"error_type": "TOOL_IMPLEMENTATION_ERROR", "error_code": "INVALID_TOOL_ACTION_RESULT_STRUCTURE", "technical_message": err_msg_struct, "actual_return_type": str(type(action_result_this_attempt)), "actual_return_preview": str(action_result_this_attempt)[:200]}
                            }
                        else:
                            logger.info(f"[{executor_id}-ToolExecutor] 工具 '{python_function_name}' 执行完毕 (尝试 {current_attempt_num})。状态: {action_result_this_attempt.get('status', 'N/A')}。")

                        if action_result_this_attempt.get("status") == "success":
                            action_result_final_for_tool = action_result_this_attempt
                            break # 成功，退出重试循环
                        else: # status 不是 "success"
                            logger.warning(f"[{executor_id}-ToolExecutor] 工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 执行失败 (尝试 {current_attempt_num})。报告状态: {action_result_this_attempt.get('status')}, 消息: {action_result_this_attempt.get('message')}")
                            action_result_final_for_tool = action_result_this_attempt # 保存本次失败的结果

                    except TypeError as te:
                        err_msg_type = f"调用工具 '{python_function_name}' 时参数不匹配或内部类型错误: {te}。"
                        logger.error(f"[{executor_id}-ToolExecutor] 工具调用参数/类型错误 (尝试 {current_attempt_num}): {err_msg_type}", exc_info=True)
                        action_result_final_for_tool = {"status": "failure", "message": f"错误: 调用工具 '{python_function_name}' 时参数或内部类型错误。", "error": {"error_type": "TOOL_EXECUTION_ERROR", "error_code": "ARGUMENT_TYPE_MISMATCH_OR_INTERNAL_TYPE_ERROR", "technical_message": err_msg_type, "exception_details": traceback.format_exc(limit=3)}}
                        break # 严重错误，无需重试
                    except Exception as exec_err:
                        err_msg_exec = f"工具 '{python_function_name}' 执行期间发生意外内部错误 (尝试 {current_attempt_num}): {exec_err}"
                        logger.error(f"[{executor_id}-ToolExecutor] 工具执行内部错误: {err_msg_exec}", exc_info=True)
                        action_result_final_for_tool = {"status": "failure", "message": f"错误: 执行工具 '{python_function_name}' 时发生内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "UNEXPECTED_TOOL_EXECUTION_FAILURE", "technical_message": err_msg_exec, "exception_details": traceback.format_exc(limit=3)}}
                    
                    # 如果是最后一次尝试，无论结果如何，都将是最终结果
                    if retry_attempt == self.max_tool_retries:
                        # action_result_final_for_tool 已经被设为最后一次尝试的结果
                        break # 退出重试循环

            # 确保 action_result_final_for_tool 有值
            if action_result_final_for_tool is None:
                 logger.error(f"[{executor_id}-ToolExecutor] 内部逻辑错误: 工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 在所有重试后 action_result_final_for_tool 仍为 None。")
                 action_result_final_for_tool = {"status": "failure", "message": f"错误: 工具 '{python_function_name}' 未能确定最终结果。", "error": {"error_type": "TOOL_EXECUTION_ERROR", "error_code": "MISSING_TOOL_RESULT_LOGIC_ERROR", "technical_message": "Tool action_result_final_for_tool was None after retry loop."}}

            tool_succeeded_this_cycle = (action_result_final_for_tool.get("status") == "success")

            final_tool_status_str_for_cb = "succeeded" if tool_succeeded_this_cycle else "failed"
            status_message_for_cb = action_result_final_for_tool.get('message', '操作处理完成,但无特定消息。')
            details_for_cb: Dict[str, Any] = {"ui_hints": ui_hints_from_plan}
            if not tool_succeeded_this_cycle:
                details_for_cb["error"] = action_result_final_for_tool.get("error", {"error_type": "UNKNOWN_FAILURE", "technical_message": "工具最终失败,无详细错误信息。"})
            elif action_result_final_for_tool.get("data") is not None:
                 try: details_for_cb["result_data_preview"] = json.dumps(action_result_final_for_tool["data"], ensure_ascii=False, default=str, indent=None)[:1000]
                 except: details_for_cb["result_data_preview"] = "(数据无法序列化预览)"

            await self._send_tool_status_update(
                status_callback, llm_generated_tool_call_id, python_function_name,
                final_tool_status_str_for_cb, status_message_for_cb,
                details=details_for_cb
            )

            tool_result_message_for_llm = {
                "role": "tool",
                "tool_call_id": llm_generated_tool_call_id,
                "name": python_function_name,
                "content": json.dumps(action_result_final_for_tool, ensure_ascii=False, default=str)
            }
            execution_results_for_llm_history.append(tool_result_message_for_llm)
            logger.debug(f"[{executor_id}-ToolExecutor] 已记录工具 '{llm_generated_tool_call_id}' 的最终执行结果 (状态: {final_tool_status_str_for_cb}) 到LLM历史。")

            if not tool_succeeded_this_cycle:
                logger.warning(f"[{executor_id}-ToolExecutor] 工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 在所有重试后仍然失败。中止后续工具执行。")
                if i + 1 < total_tools_in_plan:
                    for k_aborted in range(i + 1, total_tools_in_plan):
                        aborted_tool_req = tool_call_requests_from_plan[k_aborted]
                        aborted_tool_id = aborted_tool_req.get('toolCallId', f'fallback_aborted_id_{str(uuid4())[:8]}')
                        aborted_tool_name = aborted_tool_req.get('toolName', 'unknown_aborted_tool')
                        aborted_ui_hints = aborted_tool_req.get('uiHints', {})
                        aborted_tool_display_name = aborted_ui_hints.get('displayNameForTool') or aborted_tool_name.replace('_tool','').replace('_',' ').title()

                        await self._send_tool_status_update(
                            status_callback, aborted_tool_id, aborted_tool_name,
                            "aborted_due_to_previous_failure",
                            f"操作 '{aborted_tool_display_name}' 已中止,因为先前的工具 '{tool_display_name}' 执行失败。",
                            details={"reason": f"Aborted due to failure of tool '{python_function_name}' (ID: {llm_generated_tool_call_id})", "ui_hints": aborted_ui_hints}
                        )
                        aborted_tool_result_for_llm_content = {
                                "status": "failure",
                                "message": f"工具 '{aborted_tool_name}' 未执行,因为前序工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 失败。",
                                "error": {"error_type": "TOOL_CHAIN_ABORTED", "error_code": "PRECEDING_TOOL_FAILURE", "technical_message": f"Execution of '{aborted_tool_name}' was skipped due to the failure of tool '{python_function_name}' (ID: {llm_generated_tool_call_id})."}
                            }
                        execution_results_for_llm_history.append({
                            "role": "tool", "tool_call_id": aborted_tool_id, "name": aborted_tool_name,
                            "content": json.dumps(aborted_tool_result_for_llm_content, ensure_ascii=False)
                        })
                        logger.info(f"[{executor_id}-ToolExecutor] 为中止的工具 '{aborted_tool_name}' (ID: {aborted_tool_id}) 添加了模拟失败记录到LLM历史。")
                break 

        total_processed_tools = len(execution_results_for_llm_history)
        logger.info(f"[{executor_id}-ToolExecutor] 工具执行流程完成。共处理/记录了 {total_processed_tools}/{total_tools_in_plan} 个计划中的工具调用 (可能因失败提前中止)。")
        return execution_results_for_llm_history

# --- Agent 核心类 (V1.0.0 - 11 Tools) ---
class CircuitAgent:
    def __init__(self, api_key: str, model_name: str = "glm-z1-flash",
                 max_short_term_items: int = 30, max_long_term_items: int = 75,
                 planning_llm_retries: int = 5, max_tool_retries: int = 3,
                 tool_retry_delay_seconds: float = 1.0, max_replanning_attempts: int = 3,
                 verbose: bool = True):
        logger.info(f"\n{'='*30} CircuitAgent 初始化开始 (V1.0.0 - 11 Tools) {'='*30}") # Version update
        self.api_key = api_key
        self.verbose_mode = verbose
        self.current_request_id: Optional[str] = None

        global console_handler
        console_log_level = logging.DEBUG if self.verbose_mode else logging.INFO
        if console_handler:
            console_handler.setLevel(console_log_level)
            logger.info(f"[AgentV1_1_3 Init] 控制台日志级别已设置为: {logging.getLevelName(console_log_level)} (详细模式: {self.verbose_mode})。")
        else:
            logger.warning("[AgentV1_1_3 Init] 未找到控制台日志处理器,无法动态设置日志级别。")

        self.tools_registry: Dict[str, Dict[str, Any]] = {}
        logger.info("[AgentV1_1_3 Init] 正在动态发现并注册工具...")
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            # 重要: 确保 inspect.ismethod 能正确处理被 @register_tool (特别是被 functools.wraps) 装饰的方法
            if hasattr(method, '_is_tool') and method._is_tool:
                schema = getattr(method, '_tool_schema', None)
                if schema and isinstance(schema, dict) and 'description' in schema and 'parameters' in schema:
                    self.tools_registry[name] = schema
                    # 记录工具是否为异步
                    is_async_tool = inspect.iscoroutinefunction(method)
                    logger.info(f"[AgentV1_1_3 Init] ✓ 已注册工具: '{name}' (异步: {is_async_tool})。")
                else:
                    logger.warning(f"[AgentV1_1_3 Init] 发现工具 '{name}' 但其 Schema 结构不完整或无效,已跳过注册。")
        if not self.tools_registry:
            logger.warning("[AgentV1_1_3 Init] 未发现任何通过 @register_tool 注册的工具！Agent 将主要依赖直接问答。")
        else:
            logger.info(f"[AgentV1_1_3 Init] 共发现并注册了 {len(self.tools_registry)} 个工具。")
            if logger.isEnabledFor(logging.DEBUG):
                try: logger.debug(f"[AgentV1_1_3 Init] 工具注册表详情:\n{json.dumps(self.tools_registry, indent=2, ensure_ascii=False)}")
                except Exception as e_dump: logger.debug(f"无法序列化工具注册表进行日志记录: {e_dump}")

        try:
            self.memory_manager = MemoryManager(max_short_term_items, max_long_term_items)
            self.llm_interface = LLMInterface(agent_instance=self, model_name=model_name)
            self.output_parser = OutputParser(agent_tools_registry=self.tools_registry)
            self.tool_executor = ToolExecutor(
                agent_instance=self,
                max_tool_retries=max_tool_retries,
                tool_retry_delay_seconds=tool_retry_delay_seconds
            )
        except (ValueError, ConnectionError, TypeError) as e:
            logger.critical(f"[AgentV1_1_3 Init] 核心模块初始化失败: {e}", exc_info=True)
            raise

        self.planning_llm_retries = max(0, planning_llm_retries)
        self.max_replanning_attempts = max(0, max_replanning_attempts)
        logger.info(f"[AgentV1_1_3 Init] 规划LLM重试次数: {self.planning_llm_retries}, 工具执行重试次数: {max_tool_retries}, 最大重规划尝试次数: {self.max_replanning_attempts}。")
        logger.info(f"\n{'='*30} CircuitAgent 初始化成功 (V1.0.0 - 11 Tools) {'='*30}\n")

    # --- Action Implementations (Tool methods) ---
    @register_tool(
        description="添加一个新的电路元件 (例如: 电阻, 电容, 电池, LED, 开关, 芯片, 地线, 端子/连接点等)。如果用户未指定 ID,系统会自动为其生成一个。",
        parameters={"type": "object", "properties": {"component_type": {"type": "string", "description": "元件的类型 (例如: '电阻', 'LED', 'Terminal', 'INPUT', 'GND')。"}, "component_id": {"type": "string", "description": "可选的用户为元件指定的ID。如果提供,则使用此ID; 如果不提供或提供格式无效,则由系统自动生成。"}, "value": {"type": "string", "description": "可选的元件值 (例如: '1k', '10uF', '3V')。"}}, "required": ["component_type"]}
    )
    def add_component_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-AddComponentTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行添加元件操作。")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
        
        component_type = arguments.get("component_type")
        component_id_req = arguments.get("component_id")
        value_req = arguments.get("value")

        if not component_type or not isinstance(component_type, str) or not component_type.strip():
            err_msg = "元件类型是必需的,并且必须是有效的非空字符串。"
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_TYPE", "technical_message": err_msg}}

        target_id_final: Optional[str] = None
        id_was_generated_by_system = False
        user_provided_id_was_validated: Optional[str] = None

        if component_id_req and isinstance(component_id_req, str) and component_id_req.strip():
            user_provided_id_cleaned = component_id_req.strip().upper()
            if re.match(r'^[a-zA-Z0-9_][a-zA-Z0-9_-]*$', user_provided_id_cleaned) or user_provided_id_cleaned in ["INPUT", "OUTPUT", "GND"]:
                if user_provided_id_cleaned in self.memory_manager.circuit.components:
                    err_msg = f"您提供的元件 ID '{user_provided_id_cleaned}' 已被占用。"
                    logger.error(f"{tool_call_logger_prefix} ID 冲突: {err_msg}")
                    return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "CIRCUIT_STATE_ERROR", "error_code": "COMPONENT_ID_CONFLICT", "technical_message": err_msg, "conflicting_id": user_provided_id_cleaned}}
                else:
                    target_id_final = user_provided_id_cleaned
                    user_provided_id_was_validated = target_id_final
                    logger.debug(f"{tool_call_logger_prefix} 将使用用户提供的有效 ID: '{target_id_final}'。")
            else:
                logger.warning(f"{tool_call_logger_prefix} 用户提供的 ID '{component_id_req}' 格式无效。将自动生成 ID。")

        if target_id_final is None:
            try:
                target_id_final = self.memory_manager.circuit.generate_component_id(component_type)
                id_was_generated_by_system = True
                logger.debug(f"{tool_call_logger_prefix} 已自动为类型 '{component_type}' 生成 ID: '{target_id_final}'。")
            except RuntimeError as e_gen_id:
                err_msg = f"无法自动为类型 '{component_type}' 生成唯一 ID: {e_gen_id}"
                logger.error(f"{tool_call_logger_prefix} ID 生成失败: {err_msg}", exc_info=True)
                return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "INTERNAL_AGENT_ERROR", "error_code": "COMPONENT_ID_GENERATION_FAILED", "technical_message": str(e_gen_id)}}

        processed_value = str(value_req).strip() if value_req is not None and str(value_req).strip() else None
        if value_req is None and "value" in arguments:
            processed_value = None

        try:
            if target_id_final is None:
                raise ValueError("内部错误: 在尝试创建元件之前,未能最终确定有效的元件 ID。")

            new_component = CircuitComponent(target_id_final, component_type, processed_value)
            self.memory_manager.circuit.add_component(new_component)

            logger.info(f"{tool_call_logger_prefix} 成功添加元件 '{new_component.id}' ({new_component.type}) 到电路。")
            success_message_parts = [f"操作成功: 已添加元件 {str(new_component)}。"]
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
            return {"status": "failure", "message": "错误: 添加元件时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "ADD_COMPONENT_UNEXPECTED_FAILURE", "technical_message": str(e_add_comp), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(
        description="使用两个已存在元件的 ID 将它们连接起来。",
        parameters={"type": "object", "properties": {"comp1_id": {"type": "string", "description": "第一个元件的 ID。"}, "comp2_id": {"type": "string", "description": "第二个元件的 ID。"}}, "required": ["comp1_id", "comp2_id"]}
    )
    def connect_components_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-ConnectComponentsTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行连接元件操作。")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")

        comp1_id_req = arguments.get("comp1_id")
        comp2_id_req = arguments.get("comp2_id")

        if not comp1_id_req or not isinstance(comp1_id_req, str) or not comp1_id_req.strip() or \
           not comp2_id_req or not isinstance(comp2_id_req, str) or not comp2_id_req.strip():
            err_msg = "必须提供两个有效的、非空的元件 ID 字符串。"
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_IDS_FOR_CONNECTION", "technical_message": err_msg}}

        id1_cleaned = comp1_id_req.strip().upper()
        id2_cleaned = comp2_id_req.strip().upper()

        try:
            connection_was_new = self.memory_manager.circuit.connect_components(id1_cleaned, id2_cleaned)
            if connection_was_new:
                logger.info(f"{tool_call_logger_prefix} 成功添加新连接: {id1_cleaned} <--> {id2_cleaned}。")
                self.memory_manager.add_to_long_term(f"连接了元件: {id1_cleaned} <--> {id2_cleaned} (请求ID: {self.current_request_id or 'N/A'})")
                return {"status": "success", "message": f"操作成功: 已将元件 '{id1_cleaned}' 与 '{id2_cleaned}' 连接起来。", "data": {"connection": sorted((id1_cleaned, id2_cleaned))}}
            else:
                msg_exists = f"元件 '{id1_cleaned}' 和 '{id2_cleaned}' 之间已经存在连接。无需重复操作。"
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
            return {"status": "failure", "message": "错误: 连接元件时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "CONNECT_COMPONENTS_UNEXPECTED_FAILURE", "technical_message": str(e_connect), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(description="获取当前电路的详细描述,包括所有元件及其连接情况。", parameters={"type": "object", "properties": {}})
    def describe_circuit_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-DescribeCircuitTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行描述电路操作。")
        try:
            description = self.memory_manager.circuit.get_state_description()
            logger.info(f"{tool_call_logger_prefix} 成功生成电路描述。")
            return {"status": "success", "message": "已成功获取当前电路的描述。", "data": {"description": description}}
        except Exception as e_describe:
            err_msg = f"生成电路描述时发生意外的内部错误: {e_describe}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 获取电路描述时发生未知错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "DESCRIBE_CIRCUIT_UNEXPECTED_FAILURE", "technical_message": str(e_describe), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(description="彻底清空当前的电路设计,移除所有已添加的元件和它们之间的所有连接。此操作不可逆。", parameters={"type": "object", "properties": {}})
    def clear_circuit_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-ClearCircuitTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行清空电路操作。")
        try:
            self.memory_manager.circuit.clear()
            logger.info(f"{tool_call_logger_prefix} 电路状态已成功清空。")
            self.memory_manager.add_to_long_term(f"执行了清空电路操作 (请求ID: {self.current_request_id or 'N/A'})。")
            return {"status": "success", "message": "操作成功: 当前电路已彻底清空。"}
        except Exception as e_clear:
            err_msg = f"清空电路时发生意外的内部错误: {e_clear}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 清空电路时发生未知错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "CLEAR_CIRCUIT_UNEXPECTED_FAILURE", "technical_message": str(e_clear), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(
        description="从电路中移除一个指定的元件及其所有相关的连接。",
        parameters={"type": "object", "properties": {"component_id": {"type": "string", "description": "要移除的元件的 ID。"}}, "required": ["component_id"]}
    )
    def remove_component_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-RemoveComponentTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行移除元件操作。")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
        component_id_req = arguments.get("component_id")

        if not component_id_req or not isinstance(component_id_req, str) or not component_id_req.strip():
            err_msg = "必须提供一个有效的、非空的元件 ID 字符串。"
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_ID_FOR_REMOVAL", "technical_message": err_msg}}

        id_cleaned = component_id_req.strip().upper()
        try:
            removed_comp_details, removed_conn_count = self.memory_manager.circuit.remove_component(id_cleaned)
            logger.info(f"{tool_call_logger_prefix} 成功移除元件 '{id_cleaned}' 及其 {removed_conn_count} 个连接。")
            self.memory_manager.add_to_long_term(f"移除了元件: ID '{id_cleaned}', 类型 '{removed_comp_details.get('type', 'N/A')}' (请求ID: {self.current_request_id or 'N/A'})")
            return {"status": "success", "message": f"操作成功: 已移除元件 '{id_cleaned}' 及其所有 {removed_conn_count} 个连接。", "data": {"removed_component": removed_comp_details, "connections_removed_count": removed_conn_count}}
        except ValueError as ve_remove:
            err_msg_val = str(ve_remove)
            logger.error(f"{tool_call_logger_prefix} 移除验证错误: {err_msg_val}")
            return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": "COMPONENT_NOT_FOUND_FOR_REMOVAL", "technical_message": err_msg_val}}
        except Exception as e_remove:
            err_msg = f"移除元件时发生未知的内部错误: {e_remove}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 移除元件时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "REMOVE_COMPONENT_UNEXPECTED_FAILURE", "technical_message": str(e_remove), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(
        description="断开两个指定元件之间的连接。如果它们之间原本就没有连接,则不执行任何操作。",
        parameters={"type": "object", "properties": {"comp1_id": {"type": "string", "description": "第一个元件的 ID。"}, "comp2_id": {"type": "string", "description": "第二个元件的 ID。"}}, "required": ["comp1_id", "comp2_id"]}
    )
    def disconnect_components_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-DisconnectComponentsTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行断开元件连接操作。")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
        comp1_id_req = arguments.get("comp1_id")
        comp2_id_req = arguments.get("comp2_id")

        if not comp1_id_req or not isinstance(comp1_id_req, str) or not comp1_id_req.strip() or \
           not comp2_id_req or not isinstance(comp2_id_req, str) or not comp2_id_req.strip():
            err_msg = "必须提供两个有效的、非空的元件 ID 字符串。"
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_IDS_FOR_DISCONNECTION", "technical_message": err_msg}}

        id1_cleaned = comp1_id_req.strip().upper()
        id2_cleaned = comp2_id_req.strip().upper()

        if id1_cleaned == id2_cleaned:
            err_msg = "不能断开一个元件与它自身的连接（它们本来就不可能连接）。"
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "SELF_DISCONNECTION_ATTEMPTED", "technical_message": err_msg}}
        
        try:
            if id1_cleaned not in self.memory_manager.circuit.components:
                raise ValueError(f"元件 '{id1_cleaned}' 在电路中不存在。")
            if id2_cleaned not in self.memory_manager.circuit.components:
                raise ValueError(f"元件 '{id2_cleaned}' 在电路中不存在。")

            disconnected_successfully = self.memory_manager.circuit.disconnect_components(id1_cleaned, id2_cleaned)
            if disconnected_successfully:
                logger.info(f"{tool_call_logger_prefix} 成功断开连接: {id1_cleaned} <--> {id2_cleaned}。")
                self.memory_manager.add_to_long_term(f"断开了元件连接: {id1_cleaned} <--> {id2_cleaned} (请求ID: {self.current_request_id or 'N/A'})")
                return {"status": "success", "message": f"操作成功: 已断开元件 '{id1_cleaned}' 与 '{id2_cleaned}' 之间的连接。", "data": {"disconnected_pair": sorted((id1_cleaned, id2_cleaned))}}
            else:
                msg_not_exist = f"元件 '{id1_cleaned}' 和 '{id2_cleaned}' 之间原本就没有连接,无需断开。"
                logger.info(f"{tool_call_logger_prefix} 连接不存在: {msg_not_exist}")
                return {"status": "success", "message": f"注意: {msg_not_exist}", "data": {"disconnected_pair": sorted((id1_cleaned, id2_cleaned)), "already_disconnected_or_not_connected": True}}
        except ValueError as ve_disconnect:
            err_msg_val = str(ve_disconnect)
            logger.error(f"{tool_call_logger_prefix} 断开连接验证错误: {err_msg_val}")
            return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": "COMPONENT_NOT_FOUND_FOR_DISCONNECTION", "technical_message": err_msg_val}}
        except Exception as e_disconnect:
            err_msg = f"断开元件连接时发生未知的内部错误: {e_disconnect}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 断开元件连接时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "DISCONNECT_COMPONENTS_UNEXPECTED_FAILURE", "technical_message": str(e_disconnect), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(
        description="更新电路中一个已存在元件的值 (例如电阻的欧姆值, 电容的法拉值, 电池的电压等)。",
        parameters={"type": "object", "properties": {"component_id": {"type": "string", "description": "要更新值的元件的 ID。"}, "new_value": {"type": "string", "description": "元件的新值。如果想要清除该元件的值,可以传入 null 或一个空字符串。"}}, "required": ["component_id", "new_value"]}
    )
    def update_component_value_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-UpdateComponentValueTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行更新元件值操作。")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
        component_id_req = arguments.get("component_id")
        new_value_req = arguments.get("new_value")

        if not component_id_req or not isinstance(component_id_req, str) or not component_id_req.strip():
            err_msg = "必须提供一个有效的、非空的元件 ID 字符串。"
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_ID_FOR_UPDATE", "technical_message": err_msg}}
        
        if not isinstance(new_value_req, (str, type(None))):
            err_msg = "元件的新值 'new_value' 必须是字符串或 null (用于清除值)。"
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "INVALID_NEW_VALUE_TYPE", "technical_message": err_msg}}

        id_cleaned = component_id_req.strip().upper()
        final_new_value = str(new_value_req).strip() if new_value_req is not None and str(new_value_req).strip() else None

        try:
            if id_cleaned not in self.memory_manager.circuit.components:
                raise ValueError(f"元件 '{id_cleaned}' 在电路中不存在。")
            
            component_to_update = self.memory_manager.circuit.components[id_cleaned]
            old_value = component_to_update.value
            component_to_update.value = final_new_value
            
            logger.info(f"{tool_call_logger_prefix} 成功更新元件 '{id_cleaned}' 的值从 '{old_value}' 到 '{final_new_value}'。")
            self.memory_manager.add_to_long_term(f"更新了元件 '{id_cleaned}' 的值: 旧值 '{old_value}', 新值 '{final_new_value}' (请求ID: {self.current_request_id or 'N/A'})")
            return {"status": "success", "message": f"操作成功: 元件 '{id_cleaned}' 的值已从 '{old_value if old_value else '(无值)'}' 更新为 '{final_new_value if final_new_value else '(无值)'}'。", "data": component_to_update.to_dict()}
        except ValueError as ve_update:
            err_msg_val = str(ve_update)
            logger.error(f"{tool_call_logger_prefix} 更新值验证错误: {err_msg_val}")
            return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": "COMPONENT_NOT_FOUND_FOR_VALUE_UPDATE", "technical_message": err_msg_val}}
        except Exception as e_update:
            err_msg = f"更新元件值时发生未知的内部错误: {e_update}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 更新元件值时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "UPDATE_COMPONENT_VALUE_UNEXPECTED_FAILURE", "technical_message": str(e_update), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(
        description="根据提供的 ID 查找电路中的一个特定元件,并返回其详细信息 (类型、ID、值)。",
        parameters={"type": "object", "properties": {"component_id": {"type": "string", "description": "要查找的元件的 ID。"}}, "required": ["component_id"]}
    )
    def find_component_by_id_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-FindComponentByIdTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行查找元件操作。")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
        component_id_req = arguments.get("component_id")

        if not component_id_req or not isinstance(component_id_req, str) or not component_id_req.strip():
            err_msg = "必须提供一个有效的、非空的元件 ID 字符串。"
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_ID_FOR_FIND", "technical_message": err_msg}}

        id_cleaned = component_id_req.strip().upper()
        try:
            if id_cleaned in self.memory_manager.circuit.components:
                component_found = self.memory_manager.circuit.components[id_cleaned]
                logger.info(f"{tool_call_logger_prefix} 成功找到元件 '{id_cleaned}'。")
                return {"status": "success", "message": f"操作成功: 已找到元件 '{id_cleaned}'。", "data": component_found.to_dict()}
            else:
                logger.info(f"{tool_call_logger_prefix} 未找到元件 '{id_cleaned}'。")
                return {"status": "failure", "message": f"错误: 电路中不存在 ID 为 '{id_cleaned}' 的元件。", "error": {"error_type": "CIRCUIT_QUERY_ERROR", "error_code": "COMPONENT_NOT_FOUND_BY_ID", "technical_message": f"Component with ID '{id_cleaned}' not found in circuit."}}
        except Exception as e_find:
            err_msg = f"查找元件时发生未知的内部错误: {e_find}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 查找元件时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "FIND_COMPONENT_UNEXPECTED_FAILURE", "technical_message": str(e_find), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(
        description="列出电路中所有属于指定类型的元件及其详细信息。",
        parameters={"type": "object", "properties": {"component_type": {"type": "string", "description": "要筛选的元件类型 (例如: '电阻', 'LED', '电池')。此匹配不区分大小写。"}}, "required": ["component_type"]}
    )
    def list_components_by_type_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-ListComponentsByTypeTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行按类型列出元件操作。")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
        component_type_req = arguments.get("component_type")

        if not component_type_req or not isinstance(component_type_req, str) or not component_type_req.strip():
            err_msg = "必须提供一个有效的、非空的元件类型字符串。"
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_TYPE_FOR_LIST", "technical_message": err_msg}}
        
        type_cleaned = component_type_req.strip().lower()
        
        try:
            found_components = []
            for comp in self.memory_manager.circuit.components.values():
                if comp.type.lower() == type_cleaned:
                    found_components.append(comp.to_dict())
            
            if found_components:
                logger.info(f"{tool_call_logger_prefix} 成功找到 {len(found_components)} 个类型为 '{component_type_req}' 的元件。")
                return {"status": "success", "message": f"操作成功: 找到 {len(found_components)} 个类型为 '{component_type_req}' 的元件。", "data": {"components": found_components, "count": len(found_components)}}
            else:
                logger.info(f"{tool_call_logger_prefix} 未找到类型为 '{component_type_req}' 的元件。")
                return {"status": "success", "message": f"提示: 电路中没有找到类型为 '{component_type_req}' 的元件。", "data": {"components": [], "count": 0}}
        except Exception as e_list:
            err_msg = f"按类型列出元件时发生未知的内部错误: {e_list}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 按类型列出元件时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "LIST_COMPONENTS_UNEXPECTED_FAILURE", "technical_message": str(e_list), "exception_details": traceback.format_exc(limit=3)}}

    @register_tool(
        description="获取指定元件当前连接到其他元件的数量。",
        parameters={"type": "object", "properties": {"component_id": {"type": "string", "description": "要查询连接数量的元件的 ID。"}}, "required": ["component_id"]}
    )
    def get_component_connection_count_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool_call_logger_prefix = f"[Action-GetComponentConnectionCountTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行获取元件连接数操作。")
        logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
        component_id_req = arguments.get("component_id")

        if not component_id_req or not isinstance(component_id_req, str) or not component_id_req.strip():
            err_msg = "必须提供一个有效的、非空的元件 ID 字符串。"
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_ID_FOR_CONNECTION_COUNT", "technical_message": err_msg}}

        id_cleaned = component_id_req.strip().upper()
        try:
            if id_cleaned not in self.memory_manager.circuit.components:
                raise ValueError(f"元件 '{id_cleaned}' 在电路中不存在,无法查询其连接数。")
            
            connection_count = 0
            for conn_pair in self.memory_manager.circuit.connections:
                if id_cleaned in conn_pair:
                    connection_count += 1
            
            logger.info(f"{tool_call_logger_prefix} 元件 '{id_cleaned}' 有 {connection_count} 个连接。")
            return {"status": "success", "message": f"操作成功: 元件 '{id_cleaned}' 当前有 {connection_count} 个连接。", "data": {"component_id": id_cleaned, "connection_count": connection_count}}
        except ValueError as ve_count:
            err_msg_val = str(ve_count)
            logger.error(f"{tool_call_logger_prefix} 获取连接数验证错误: {err_msg_val}")
            return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_QUERY_ERROR", "error_code": "COMPONENT_NOT_FOUND_FOR_CONNECTION_COUNT", "technical_message": err_msg_val}}
        except Exception as e_count:
            err_msg = f"获取元件连接数时发生未知的内部错误: {e_count}"
            logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 获取元件连接数时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "GET_CONNECTION_COUNT_UNEXPECTED_FAILURE", "technical_message": str(e_count), "exception_details": traceback.format_exc(limit=3)}}

    # --- DuckDuckGo 搜索工具 (确保返回期望的字典结构) ---
    @register_tool(
        description="使用 DuckDuckGo 搜索引擎在互联网上搜索与给定查询词相关的信息。用于获取通用知识、技术细节或背景资料。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "要搜索的关键词或问题。"},
                "num_results": {"type": "integer", "description": "期望返回的搜索结果数量 (例如: 1 到 5)。如果未提供或无效,默认为3。"}
            },
            "required": ["query"]
        }
    )
    async def duckduckgo_search_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]: # 标记为 async def
        tool_call_logger_prefix = f"[Action-DuckDuckGoSearchTool-ReqID:{self.current_request_id or 'N/A'}]"
        logger.info(f"{tool_call_logger_prefix} 执行 DuckDuckGo 搜索操作。")
        query = arguments.get("query")
        num_results_req = arguments.get("num_results")
        logger.debug(f"{tool_call_logger_prefix} 收到搜索查询: '{query}', 期望结果数 (原始请求): {num_results_req}。")

        # 预定义返回结构，确保status和message存在
        tool_result = {
            "status": "failure",
            "message": "DuckDuckGo 搜索工具初始化失败或发生未知错误。",
            "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "DUCKDUCKGO_UNKNOWN_FAILURE", "technical_message": "Tool did not complete successfully."}
        }

        if not query or not isinstance(query, str) or not query.strip():
            err_msg = "必须提供一个有效的、非空的搜索查询词。"
            logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
            tool_result["message"] = f"错误: {err_msg}"
            tool_result["error"] = {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_SEARCH_QUERY", "technical_message": err_msg}
            return tool_result

        num_results = 3 
        if num_results_req is not None:
            if isinstance(num_results_req, int) and 1 <= num_results_req <= 10:
                num_results = num_results_req
            else:
                logger.warning(f"{tool_call_logger_prefix} num_results 参数 '{num_results_req}' 无效或超出范围(1-10), 将使用默认值 {num_results}。")
        else:
            logger.debug(f"{tool_call_logger_prefix} 未提供 num_results 参数, 将使用默认值 {num_results}。")
            
        search_results_raw_list = []
        try:
            # 将实际的同步DDGS操作封装在一个内部函数中
            def sync_ddgs_operation():
                _internal_results = []
                logger.debug(f"{tool_call_logger_prefix} [sync_op_internal] 开始执行DDGS搜索 for '{query}', max_results={num_results}")
                with DDGS(timeout=20) as ddgs: # 确保每次调用都创建新的DDGS实例
                    # ddgs.text返回一个迭代器，我们需要将其物化为列表来获取所有结果
                    fetched_results = list(ddgs.text(keywords=query, max_results=num_results))
                    logger.debug(f"{tool_call_logger_prefix} [sync_op_internal] DDGS.text 返回了 {len(fetched_results)} 个原始条目。")
                    # 手动限制结果数量，因为max_results在DDGS中可能不是硬限制
                    for r_item in fetched_results[:num_results]:
                        _internal_results.append({
                            "title": r_item.get('title', 'N/A'),
                            "snippet": r_item.get('body', 'N/A'), # DDGS 使用 'body' 作为摘要
                            "link": r_item.get('href', '#')
                        })
                logger.debug(f"{tool_call_logger_prefix} [sync_op_internal] 处理后得到 {len(_internal_results)} 个结果。")
                return _internal_results

            logger.debug(f"{tool_call_logger_prefix} 准备将同步DDGS操作提交到线程池...")
            search_results_raw_list = await asyncio.to_thread(sync_ddgs_operation)
            logger.debug(f"{tool_call_logger_prefix} 同步DDGS操作完成，从线程返回了 {len(search_results_raw_list)} 个结果。")


            search_results_json_str = json.dumps(search_results_raw_list, ensure_ascii=False)
            success_message = f"已成功完成对“{query}”的 DuckDuckGo 搜索,找到 {len(search_results_raw_list)} 条相关信息。"
            logger.info(f"{tool_call_logger_prefix} {success_message}")
            
            self.memory_manager.add_to_long_term(f"执行了 DuckDuckGo 搜索,查询词: '{query}', 返回了 {len(search_results_raw_list)} 条结果 (请求ID: {self.current_request_id or 'N/A'})。")
            
            # 更新为成功的返回字典
            tool_result = {
                "status": "success",
                "message": success_message,
                "data": {
                    "query": query,
                    "num_results_requested": num_results,
                    "num_results_returned": len(search_results_raw_list),
                    "results_json_string": search_results_json_str 
                }
            }
            return tool_result

        except Exception as e_search:
            err_msg = f"使用 DuckDuckGo 搜索时发生错误: {e_search}"
            logger.error(f"{tool_call_logger_prefix} {err_msg}", exc_info=True)
            tool_result["message"] = f"错误: {err_msg}"
            tool_result["error"] = {"error_type": "EXTERNAL_SERVICE_ERROR", "error_code": "DUCKDUCKGO_SEARCH_FAILED", "technical_message": str(e_search), "exception_details": traceback.format_exc(limit=3)}
            return tool_result

    # --- Orchestration Layer Method (V1.0.0 - 核心调度逻辑) ---
    async def process_user_request(self, user_request: str, status_callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        request_start_time = time.monotonic()
        self.current_request_id = f"req_{str(uuid4())[:12]}"

        final_llm_camelcase_json_for_reply: Optional[Dict[str, Any]] = None
        final_reply_for_user: str = "抱歉,处理您的请求时发生未知错误。"
        final_llm_interaction_id_for_user: Optional[str] = None
        active_llm_interaction_id: Optional[str] = None

        logger.info(f"\n{'='*25} CircuitAgent 开始处理用户请求 (ReqID: {self.current_request_id}) {'='*25}")
        logger.info(f"[OrchestratorV1_1_3] 收到用户指令: \"{user_request}\"")

        try:
            if not user_request or user_request.isspace():
                logger.info(f"[OrchestratorV1_1_3 - ReqID:{self.current_request_id}] 用户指令为空。")
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "ignored", "message": "用户输入为空,已忽略。"})
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
                    "executionPhase": "planning",
                    "thoughtProcess": "Agent检测到用户输入为空或仅包含空白字符,无需进一步处理。",
                    "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content": "您的指令似乎是空的,请重新输入！"}}
                }
                await status_callback({"type": "final_response", "request_id": self.current_request_id, "llm_interaction_id": empty_input_err_json["llmInteractionId"], "content": empty_input_err_json["decision"]["responseToUser"]["content"], "finaljson_if_success": None})
                return

            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "received", "message": "收到用户指令,开始处理...", "details": {"user_request_preview": user_request[:1000]}})
            try:
                self.memory_manager.add_to_short_term({"role": "user", "content": user_request})
            except Exception as e_mem_user:
                logger.error(f"[OrchestratorV1_1_3 - ReqID:{self.current_request_id}] 添加用户消息到短期记忆时出错: {e_mem_user}", exc_info=True)
                err_msg_mem = f"记录用户指令时发生内部记忆错误: {e_mem_user}"
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "error", "message": err_msg_mem})
                mem_err_json = {
                    "requestId": self.current_request_id, "llmInteractionId": f"agent_mem_err_{str(uuid4())[:6]}",
                    "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure",
                    "errorDetails": {"errorType": "INTERNAL_AGENT_ERROR", "errorCode": "MEMORY_ADD_USER_MSG_FAILED", "messageToUser": f"抱歉,我在记录您的指令时遇到了内部问题 ({e_mem_user})！请稍后重试。", "technicalMessage": err_msg_mem, "isDirectLlmFailure": False },
                    "executionPhase": "planning", "thoughtProcess": "Agent在将用户消息添加到短期记忆时遇到错误。",
                    "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content": f"抱歉,我在记录您的指令时遇到了内部问题 ({e_mem_user})！请稍后重试。" }}
                }
                await status_callback({"type": "final_response", "request_id": self.current_request_id, "llm_interaction_id": mem_err_json["llmInteractionId"], "content": mem_err_json["decision"]["responseToUser"]["content"], "finaljson_if_success": None})
                return

            replanning_loop_count = 0
            current_llm_plan_camelcase_json_obj: Optional[Dict[str, Any]] = None
            tool_execution_results_for_llm_history: List[Dict[str, Any]] = []
            agent_accepted_latest_plan_for_action = False

            while replanning_loop_count <= self.max_replanning_attempts:
                current_planning_attempt_num = replanning_loop_count + 1
                log_prefix = f"[OrchestratorV1_1_3 - PlanAttempt {current_planning_attempt_num} - ReqID: {self.current_request_id}]"
                logger.info(f"\n--- {log_prefix} 开始 ---")

                is_currently_replanning = (replanning_loop_count > 0)
                status_msg_planning_start = "正在分析指令并制定计划..." if not is_currently_replanning else f"正在尝试第 {replanning_loop_count}/{self.max_replanning_attempts} 次重规划..."
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "started", "message": status_msg_planning_start, "details": {"attempt_number": current_planning_attempt_num, "max_replanning_attempts": self.max_replanning_attempts}})

                memory_context = self.memory_manager.get_memory_context_for_prompt()
                tool_schemas = self._get_tool_schemas_for_prompt()
                system_prompt_planning = self._get_planning_prompt(tool_schemas, memory_context, is_currently_replanning, self.current_request_id)
                messages_for_planning = [{"role": "system", "content": system_prompt_planning}] + self.memory_manager.short_term

                llm_call_attempt_inner = 0
                parsed_plan_camelcase_json_this_llm_call: Optional[Dict[str, Any]] = None
                parser_error_msg_this_llm_call: str = ""
                parsed_failed_validation_points_this_llm_call: List[Dict[str,str]] = []
                agent_accepted_latest_plan_for_action = False

                while llm_call_attempt_inner <= self.planning_llm_retries:
                    logger.info(f"{log_prefix} 调用规划 LLM (LLM Call Attempt {llm_call_attempt_inner + 1} of {self.planning_llm_retries + 1})...")
                    try:
                        llm_response_planning_raw = await self.llm_interface.call_llm(messages_for_planning, "planning", status_callback)
                        if not llm_response_planning_raw or not llm_response_planning_raw.choices:
                            raise ConnectionError("LLM规划响应无效或缺少choices。这是LLMInterface层面的问题。")

                        llm_msg_obj_planning = llm_response_planning_raw.choices[0].message
                        parsed_plan_camelcase_json_this_llm_call, parser_error_msg_this_llm_call, parsed_failed_validation_points_this_llm_call = \
                            self.output_parser.parse_llm_response_to_structured_json(llm_msg_obj_planning, "planning")

                        if parsed_plan_camelcase_json_this_llm_call:
                            active_llm_interaction_id = parsed_plan_camelcase_json_this_llm_call.get("llmInteractionId")
                            current_thought_process = parsed_plan_camelcase_json_this_llm_call.get("thoughtProcess")
                            if current_thought_process:
                                await status_callback({"type": "thinking_log", "request_id": self.current_request_id, "llm_interaction_id": active_llm_interaction_id, "stage": "planning", "content": current_thought_process})

                        if parsed_plan_camelcase_json_this_llm_call and not parser_error_msg_this_llm_call and not parsed_failed_validation_points_this_llm_call:
                            if parsed_plan_camelcase_json_this_llm_call.get("status") == "success":
                                logger.info(f"{log_prefix} 成功解析并验证V1.0-CamelCaseJSON计划。LLM报告状态为 'success' (LLM_ID: {active_llm_interaction_id})。Agent采纳此计划。")
                                agent_accepted_latest_plan_for_action = True
                            elif is_currently_replanning and \
                                 parsed_plan_camelcase_json_this_llm_call.get("decision", {}).get("isCallTools") is True and \
                                 isinstance(parsed_plan_camelcase_json_this_llm_call.get("decision", {}).get("toolCallRequests"), list) and \
                                 parsed_plan_camelcase_json_this_llm_call.get("decision", {}).get("toolCallRequests"):
                                logger.warning(f"{log_prefix} LLM在重规划时提供了新的工具调用计划,但可能将其顶层status标记为 'failure' (LLM_ID: {active_llm_interaction_id})。Agent将审慎采纳此新计划以尝试修正。LLM报告的错误(如有): {parsed_plan_camelcase_json_this_llm_call.get('errorDetails')}")
                                agent_accepted_latest_plan_for_action = True
                            else:
                                error_detail_from_llm = parsed_plan_camelcase_json_this_llm_call.get("errorDetails", {}).get("technicalMessage", "LLM规划指示内部错误,但JSON结构有效。")
                                logger.warning(f"{log_prefix} LLM报告的V1.0-CamelCaseJSON计划状态为 'failure': {error_detail_from_llm} (LLM_ID: {active_llm_interaction_id})。Agent将不采纳此计划,并尝试让LLM修正(如果还有LLM调用重试次数)。")
                                parser_error_msg_this_llm_call = f"LLM主动报告规划失败: {error_detail_from_llm}"

                            if agent_accepted_latest_plan_for_action:
                                current_llm_plan_camelcase_json_obj = parsed_plan_camelcase_json_this_llm_call
                                try:
                                    self.memory_manager.add_to_short_term(llm_msg_obj_planning.model_dump(exclude_unset=True))
                                except Exception as e_mem_add: logger.error(f"{log_prefix} 添加LLM规划响应到记忆失败: {e_mem_add}")
                                break

                        if not agent_accepted_latest_plan_for_action and llm_call_attempt_inner < self.planning_llm_retries:
                            error_to_report_cb = parser_error_msg_this_llm_call or "V1.0.0结构或内容校验失败。"
                            if parsed_failed_validation_points_this_llm_call:
                                error_to_report_cb += " 失败点: " + json.dumps(parsed_failed_validation_points_this_llm_call[:2], ensure_ascii=False)
                            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "llm_retry_needed", "message": f"大脑计划处理遇到问题,尝试重新沟通 ({error_to_report_cb[:1000]})", "details": {"llm_call_attempt": llm_call_attempt_inner + 1, "parser_error": parser_error_msg_this_llm_call, "validation_failures": parsed_failed_validation_points_this_llm_call}})
                            if parsed_plan_camelcase_json_this_llm_call and parsed_plan_camelcase_json_this_llm_call.get("status") == "failure":
                                try: self.memory_manager.add_to_short_term(llm_msg_obj_planning.model_dump(exclude_unset=True))
                                except Exception as e_mem_add_fail: logger.error(f"{log_prefix} 添加LLM失败规划到记忆失败: {e_mem_add_fail}")
                            elif parser_error_msg_this_llm_call or parsed_failed_validation_points_this_llm_call:
                                 sim_err_plan_content = {
                                    "requestId": self.current_request_id, "llmInteractionId": f"agent_parser_err_{active_llm_interaction_id or str(uuid4())[:6]}",
                                    "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure",
                                    "errorDetails": {"errorType": "LLM_OUTPUT_VALIDATION_ERROR", "errorCode": "V1_CAMELCASE_JSON_VALIDATION_FAILED", "technicalMessage": parser_error_msg_this_llm_call, "isDirectLlmFailure": False, "failedValidationPoints": parsed_failed_validation_points_this_llm_call },
                                    "executionPhase": "planning", "thoughtProcess": "Agent在解析或验证LLM上一次规划输出时发现以下问题,将请求LLM修正。",
                                    "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content":""}}
                                 }
                                 try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(sim_err_plan_content, ensure_ascii=False)})
                                 except Exception as e_mem_add_parse_err: logger.error(f"{log_prefix} 添加Agent解析错误到记忆失败: {e_mem_add_parse_err}")

                    except Exception as e_llm_call_level:
                        logger.error(f"{log_prefix} LLM调用或规划解析时发生严重错误 (LLM Call Attempt {llm_call_attempt_inner + 1}): {e_llm_call_level}", exc_info=True)
                        parser_error_msg_this_llm_call = f"LLM调用/解析严重错误: {str(e_llm_call_level)[:1000]}"
                        parsed_failed_validation_points_this_llm_call = [{"jsonPath":"root", "issue_description": parser_error_msg_this_llm_call}]
                        if llm_call_attempt_inner < self.planning_llm_retries:
                             await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "llm_error_retrying", "message": f"与大脑沟通时发生严重错误,尝试重新连接 ({parser_error_msg_this_llm_call})", "details": {"llm_call_attempt": llm_call_attempt_inner + 1}})

                    llm_call_attempt_inner += 1
                    if agent_accepted_latest_plan_for_action: break

                if not agent_accepted_latest_plan_for_action:
                    error_summary_final_planning_llm_attempt = parser_error_msg_this_llm_call or "在多次LLM调用尝试后,未能从LLM获取可接受的V1.0-CamelCaseJSON规划。"
                    if parsed_failed_validation_points_this_llm_call:
                         error_summary_final_planning_llm_attempt += " 最后一次校验失败点: " + json.dumps(parsed_failed_validation_points_this_llm_call[:2], ensure_ascii=False)

                    await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "failed_after_llm_retries", "message": f"规划失败 (在第 {current_planning_attempt_num} 次规划尝试中,LLM调用重试均失败): {error_summary_final_planning_llm_attempt}", "details": {"final_parser_error": parser_error_msg_this_llm_call, "final_validation_failures": parsed_failed_validation_points_this_llm_call, "thinking_log_from_last_attempt": parsed_plan_camelcase_json_this_llm_call.get("thoughtProcess") if parsed_plan_camelcase_json_this_llm_call else "无有效思考过程"}})

                    if replanning_loop_count >= self.max_replanning_attempts:
                        logger.critical(f"{log_prefix} 已达最大重规划尝试次数 ({self.max_replanning_attempts}),且本次规划尝试在LLM调用/解析层面最终失败。中止处理。")
                        final_reply_for_user = f"抱歉,即使经过多次尝试与智能大脑沟通,也未能为您的请求 '{user_request[:50]}...' 制定出有效的执行计划。错误详情: {error_summary_final_planning_llm_attempt}"
                        final_llm_interaction_id_for_user = active_llm_interaction_id or f"error_plan_max_replan_llm_fail_{str(uuid4())[:6]}"
                        final_llm_camelcase_json_for_reply = None
                        break
                    else:
                        sim_fail_plan_content_for_replan = {
                            "requestId": self.current_request_id, "llmInteractionId": f"agent_replan_trigger_{active_llm_interaction_id or str(uuid4())[:6]}",
                            "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure",
                            "errorDetails": {"errorType": "LLM_OUTPUT_VALIDATION_ERROR", "errorCode": "V1_CAMELCASE_JSON_VALIDATION_FAILED_IN_PLAN_ATTEMPT", "technicalMessage": error_summary_final_planning_llm_attempt, "isDirectLlmFailure": False, "failedValidationPoints": parsed_failed_validation_points_this_llm_call },
                            "executionPhase": "planning", "thoughtProcess": f"Agent在第 {current_planning_attempt_num} 次规划尝试的LLM调用/解析阶段遇到问题,将进行重规划。错误: {error_summary_final_planning_llm_attempt}",
                            "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content":""}}
                        }
                        try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(sim_fail_plan_content_for_replan, ensure_ascii=False)})
                        except Exception as e_mem_add_replan_trigger: logger.error(f"{log_prefix} 添加重规划触发信息到记忆出错: {e_mem_add_replan_trigger}")
                        replanning_loop_count += 1
                        continue

                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "completed_and_validated", "message": "规划完成并通过验证,准备执行或直接回复。", "details": {"plan_llm_id": current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else None}})

                tool_requests_from_plan = current_llm_plan_camelcase_json_obj.get("decision", {}).get("toolCallRequests", []) if current_llm_plan_camelcase_json_obj else []
                if isinstance(tool_requests_from_plan, list) and current_llm_plan_camelcase_json_obj:
                    plan_details_for_ui = []
                    for req_idx, tool_req in enumerate(tool_requests_from_plan):
                        plan_details_for_ui.append({
                            "tool_call_id": tool_req.get("toolCallId"),
                            "tool_name": tool_req.get("toolName"),
                            "tool_arguments": tool_req.get("toolArguments", {}),
                            "ui_hints": tool_req.get("uiHints", {}),
                            "status": "pending",
                            "order": req_idx + 1
                        })
                    await status_callback({
                        "type": "plan_details",
                        "request_id": self.current_request_id,
                        "llm_interaction_id": current_llm_plan_camelcase_json_obj.get("llmInteractionId"),
                        "plan": plan_details_for_ui
                    })

                decision_from_plan = current_llm_plan_camelcase_json_obj.get("decision", {}) if current_llm_plan_camelcase_json_obj else {}
                should_call_tools = decision_from_plan.get("isCallTools", False)
                response_user_obj_from_plan = decision_from_plan.get("responseToUser")

                if should_call_tools:
                    tool_count_in_plan = len(tool_requests_from_plan) if isinstance(tool_requests_from_plan, list) else 0
                    logger.info(f"{log_prefix} 决策: 执行 {tool_count_in_plan} 个工具。")
                    await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "action_execution", "status": "started", "message": f"开始执行 {tool_count_in_plan} 个计划操作...", "details": {"tool_count": tool_count_in_plan}})

                    if isinstance(response_user_obj_from_plan, dict) and response_user_obj_from_plan.get("content","").strip():
                        transitional_reply_content = response_user_obj_from_plan["content"]
                        await status_callback({"type": "interim_response", "request_id": self.current_request_id, "llm_interaction_id": current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else None, "content": transitional_reply_content})

                    if not isinstance(tool_requests_from_plan, list) or not tool_requests_from_plan:
                        err_msg_list_tools_critical = "内部规划错误: isCallTools为True但toolCallRequests列表无效或为空。OutputParser应已校验。"
                        logger.error(f"{log_prefix} {err_msg_list_tools_critical}")
                        tool_execution_results_for_llm_history = [{"role":"tool", "tool_call_id":f"plan_integrity_err_{str(uuid4())[:6]}", "name":"plan_integrity_checker", "content":json.dumps({"status":"failure", "message":err_msg_list_tools_critical, "error": {"error_type":"INTERNAL_AGENT_ERROR", "error_code":"INVALID_TOOL_REQUEST_LIST_POST_VALIDATION", "technical_message": err_msg_list_tools_critical}})}]
                        try: self.memory_manager.add_to_short_term(tool_execution_results_for_llm_history[0])
                        except Exception as e_mem_add_integrity_err: logger.error(f"{log_prefix} 添加规划完整性错误到记忆失败: {e_mem_add_integrity_err}")

                        if replanning_loop_count >= self.max_replanning_attempts:
                            final_reply_for_user = f"抱歉,系统在准备执行操作时遇到内部规划结构问题。请稍后重试或联系技术支持。错误: {err_msg_list_tools_critical}"
                            final_llm_interaction_id_for_user = current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id
                            final_llm_camelcase_json_for_reply = None
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
                    last_failed_tool_message_for_user = "一个或多个操作未能成功完成。"
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
                                last_failed_tool_message_for_user = "一个操作的结果格式不正确。"

                    if any_tool_failed_persistently:
                        logger.warning(f"{log_prefix} 工具执行过程中发生了一个或多个持久性失败。")
                        await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "action_execution", "status": "tool_failure_detected", "message": "部分操作失败,准备评估是否重规划。", "details": {"last_error_message": last_failed_tool_message_for_user}})
                        if replanning_loop_count < self.max_replanning_attempts:
                            replanning_loop_count += 1; agent_accepted_latest_plan_for_action = False; continue
                        else:
                            logger.critical(f"{log_prefix} 已达最大重规划尝试次数 ({self.max_replanning_attempts}),但工具执行仍有失败。中止处理。")
                            final_reply_for_user = f"抱歉,在执行您的请求时,即使经过多次尝试,仍遇到问题: {last_failed_tool_message_for_user} 请检查您的指令或稍后再试。"
                            final_llm_interaction_id_for_user = current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id
                            final_llm_camelcase_json_for_reply = None
                            break
                    else:
                        logger.info(f"{log_prefix} 所有计划中的工具均成功执行。准备生成最终回复。")
                        final_llm_camelcase_json_for_reply = current_llm_plan_camelcase_json_obj
                        break

                else:
                    logger.info(f"{log_prefix} 决策: 直接回复 (V1.0.0)。无需工具调用。")
                    if isinstance(response_user_obj_from_plan, dict) and response_user_obj_from_plan.get("content","").strip():
                        tool_execution_results_for_llm_history = []
                        final_llm_camelcase_json_for_reply = current_llm_plan_camelcase_json_obj
                        logger.info(f"{log_prefix} 规划阶段决定直接回复,内容有效。将使用此V1.0-CamelCaseJSON作为最终输出。LLM_ID: {final_llm_camelcase_json_for_reply.get('llmInteractionId')}")
                        break
                    else:
                        err_msg_direct_content_critical = "内部规划错误: isCallTools为False但responseToUser.content无效或为空。OutputParser应已校验。"
                        logger.error(f"{log_prefix} {err_msg_direct_content_critical}")
                        tool_execution_results_for_llm_history = [{"role":"tool", "tool_call_id":f"direct_reply_integrity_err_{str(uuid4())[:6]}", "name":"direct_reply_integrity_checker", "content":json.dumps({"status":"failure", "message":err_msg_direct_content_critical, "error": {"error_type":"INTERNAL_AGENT_ERROR", "error_code":"INVALID_DIRECT_RESPONSE_CONTENT_POST_VALIDATION", "technical_message": err_msg_direct_content_critical}})}]
                        try: self.memory_manager.add_to_short_term(tool_execution_results_for_llm_history[0])
                        except Exception as e_mem_add_direct_reply_err: logger.error(f"{log_prefix} 添加直接回复完整性错误到记忆失败: {e_mem_add_direct_reply_err}")

                        if replanning_loop_count >= self.max_replanning_attempts:
                            final_reply_for_user = f"抱歉,系统在准备直接回复时遇到内部规划结构问题。请稍后重试或联系技术支持。错误: {err_msg_direct_content_critical}"
                            final_llm_interaction_id_for_user = current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id
                            final_llm_camelcase_json_for_reply = None
                            break
                        else:
                            replanning_loop_count += 1; agent_accepted_latest_plan_for_action = False; continue
            
            logger.debug(f"[OrchestratorV1_1_3 - ReqID:{self.current_request_id}] 重规划循环结束。采纳的计划: {agent_accepted_latest_plan_for_action}, 重规划次数: {replanning_loop_count}, 用于回复的最终LLM JSON是否已设置: {final_llm_camelcase_json_for_reply is not None}")
            
            if not agent_accepted_latest_plan_for_action and replanning_loop_count > self.max_replanning_attempts:
                logger.error(f"[OrchestratorV1_1_3 - FinalPrep - ReqID:{self.current_request_id}] 已达最大重规划次数,且最终规划尝试仍失败。将使用上次记录的错误信息。")
            
            logger.debug(f"[OrchestratorV1_1_3 - ReqID:{self.current_request_id}] 响应生成检查前。最终JSON状态: {final_llm_camelcase_json_for_reply.get('status') if final_llm_camelcase_json_for_reply else 'N/A'}, isCallTools: {final_llm_camelcase_json_for_reply.get('decision', {}).get('isCallTools') if final_llm_camelcase_json_for_reply else 'N/A'}")

            if final_llm_camelcase_json_for_reply and \
               final_llm_camelcase_json_for_reply.get("status") == "success" and \
               final_llm_camelcase_json_for_reply.get("decision",{}).get("isCallTools") is True:
                logger.info(f"[OrchestratorV1_1_3 - ReqID:{self.current_request_id}] 工具执行成功,开始生成最终响应...")
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "response_generation", "status": "started", "message": "正在总结操作结果并生成最终回复...", "details": {"reason": "Tool execution completed successfully. Generating final summary."}})

                system_prompt_resp_gen = self._get_response_generation_prompt(
                    self.memory_manager.get_memory_context_for_prompt(),
                    self._get_tool_schemas_for_prompt(),
                    self.current_request_id
                )
                messages_for_resp_gen = [{"role": "system", "content": system_prompt_resp_gen}] + self.memory_manager.short_term

                try:
                    llm_response_final_gen_raw = await self.llm_interface.call_llm(messages_for_resp_gen, "response_generation", status_callback)
                    if not llm_response_final_gen_raw or not llm_response_final_gen_raw.choices: raise ConnectionError("LLM最终响应生成阶段的响应无效或缺少choices。")

                    llm_msg_obj_final_gen = llm_response_final_gen_raw.choices[0].message
                    parsed_final_camelcase_resp_json, final_parser_err_resp, final_validation_failures_resp = \
                        self.output_parser.parse_llm_response_to_structured_json(llm_msg_obj_final_gen, "response_generation")

                    if parsed_final_camelcase_resp_json:
                        active_llm_interaction_id = parsed_final_camelcase_resp_json.get("llmInteractionId")
                        final_resp_thought_process = parsed_final_camelcase_resp_json.get("thoughtProcess")
                        if final_resp_thought_process:
                             await status_callback({"type": "thinking_log", "request_id": self.current_request_id, "llm_interaction_id": active_llm_interaction_id, "stage": "response_generation", "content": final_resp_thought_process})

                    if parsed_final_camelcase_resp_json and not final_parser_err_resp and not final_validation_failures_resp and parsed_final_camelcase_resp_json.get("status") == "success":
                        final_llm_camelcase_json_for_reply = parsed_final_camelcase_resp_json
                        final_llm_interaction_id_for_user = active_llm_interaction_id
                        logger.info(f"[OrchestratorV1_1_3 - ReqID:{self.current_request_id}] 成功解析并验证最终响应V1.0-CamelCaseJSON (LLM_ID: {final_llm_interaction_id_for_user})。")
                        try:
                            self.memory_manager.add_to_short_term(llm_msg_obj_final_gen.model_dump(exclude_unset=True))
                        except Exception as e_mem_add_final_resp: logger.error(f"添加最终LLM响应到记忆失败: {e_mem_add_final_resp}")
                    else:
                        err_msg_final_resp_gen = final_parser_err_resp or "V1.0.0最终响应JSON校验失败。"
                        if final_validation_failures_resp: err_msg_final_resp_gen += " 失败点: " + json.dumps(final_validation_failures_resp[:2], ensure_ascii=False)
                        elif parsed_final_camelcase_resp_json and parsed_final_camelcase_resp_json.get("status") == "failure":
                             err_msg_final_resp_gen = parsed_final_camelcase_resp_json.get("errorDetails",{}).get("technicalMessage", err_msg_final_resp_gen)

                        logger.error(f"[OrchestratorV1_1_3 - ReqID:{self.current_request_id}] LLM未能生成有效V1.0-CamelCaseJSON最终回复: {err_msg_final_resp_gen}")
                        final_reply_for_user = f"抱歉,在总结操作结果时发生了一些问题。错误: {err_msg_final_resp_gen[:1000]}... "
                        final_llm_interaction_id_for_user = active_llm_interaction_id or (final_llm_camelcase_json_for_reply.get("llmInteractionId") if final_llm_camelcase_json_for_reply else f"error_resp_gen_{str(uuid4())[:6]}")
                        final_llm_camelcase_json_for_reply = None
                except Exception as e_llm_final_gen_call:
                    logger.critical(f"[OrchestratorV1_1_3 - ReqID:{self.current_request_id}] LLM最终响应调用或处理失败: {e_llm_final_gen_call}", exc_info=True)
                    final_reply_for_user = f"抱歉,系统在为您准备最终报告时遇到了严重的内部错误: {str(e_llm_final_gen_call)[:1000]}... "
                    final_llm_interaction_id_for_user = (final_llm_camelcase_json_for_reply.get("llmInteractionId") if final_llm_camelcase_json_for_reply else active_llm_interaction_id or f"critical_err_resp_gen_{str(uuid4())[:6]}")
                    final_llm_camelcase_json_for_reply = None
            
            elif final_llm_camelcase_json_for_reply and \
                 final_llm_camelcase_json_for_reply.get("status") == "success" and \
                 final_llm_camelcase_json_for_reply.get("decision",{}).get("isCallTools") is False:
                logger.info(f"[OrchestratorV1_1_3 - ReqID:{self.current_request_id}] 使用规划阶段的直接回复V1.0-CamelCaseJSON作为最终输出。")
                final_llm_interaction_id_for_user = final_llm_camelcase_json_for_reply.get("llmInteractionId")

            elif not final_llm_camelcase_json_for_reply :
                 logger.error(f"[OrchestratorV1_1_3 - ReqID:{self.current_request_id}] 流程结束时,final_llm_camelcase_json_for_reply 为空,表明处理失败。将使用之前记录的错误信息 (final_reply_for_user)。")

            user_facing_thought_process_final_summary = "综合思考过程已在之前的日志中发送。"
            if final_llm_camelcase_json_for_reply and final_llm_camelcase_json_for_reply.get("status") == "success":
                user_facing_thought_process_final_summary = final_llm_camelcase_json_for_reply.get("thoughtProcess", user_facing_thought_process_final_summary)
                resp_user_obj_final = final_llm_camelcase_json_for_reply.get("decision", {}).get("responseToUser", {})
                final_reply_for_user = resp_user_obj_final.get("content", final_reply_for_user)
            
            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "finalization", "status": "completed" if (final_llm_camelcase_json_for_reply and final_llm_camelcase_json_for_reply.get("status") == "success") else "failed", "message": "请求处理流程已结束。"})
            await status_callback({
                "type": "final_response",
                "request_id": self.current_request_id,
                "llm_interaction_id": final_llm_interaction_id_for_user,
                "content": final_reply_for_user.strip() if final_reply_for_user else "抱歉,未能生成有效的回复。",
                "finaljson_if_success": final_llm_camelcase_json_for_reply
            })

            if not (final_llm_camelcase_json_for_reply and final_llm_camelcase_json_for_reply.get("status") == "success"):
                final_assistant_synthetic_error_message_camelcase_json = {
                    "requestId": self.current_request_id,
                    "llmInteractionId": final_llm_interaction_id_for_user or f"agent_synth_final_err_{str(uuid4())[:6]}",
                    "timestampUtc": datetime.now(timezone.utc).isoformat(),
                    "status": "failure",
                    "errorDetails": {"errorType": "AGENT_PROCESSING_FAILURE", "errorCode": "OVERALL_REQUEST_HANDLING_FAILED", "messageToUser": final_reply_for_user, "technicalMessage": "Agent failed to successfully complete the user request after all attempts.", "isDirectLlmFailure": False },
                    "executionPhase": "final_error_synthesis",
                    "thoughtProcess": user_facing_thought_process_final_summary or "Agent 最终处理失败,未能生成详细思考过程。",
                    "decision": {"isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content": final_reply_for_user}}
                }
                try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(final_assistant_synthetic_error_message_camelcase_json, ensure_ascii=False)})
                except Exception as e_mem_add_synth_err: logger.error(f"添加Agent合成的最终错误助手消息到记忆失败: {e_mem_add_synth_err}")

        except Exception as e_process_top_level:
            request_id_for_fatal = self.current_request_id or f"fatal_err_no_req_id_{str(uuid4())[:6]}"
            logger.critical(f"[OrchestratorV1_1_3 - ReqID:{request_id_for_fatal}] 处理用户请求 '{user_request[:1000]}' 时发生顶层未捕获异常: {e_process_top_level}", exc_info=True)
            error_msg_for_user_fatal = f"抱歉,处理您的请求 ('{user_request[:30]}...') 时发生严重的、未预期的内部系统错误。请稍后再试或联系技术支持。"
            tb_str_for_thinking_log_fatal = traceback.format_exc().replace('\n', ' | ')
            thinking_log_content_fatal = f"请求处理流程中发生顶层致命错误: {e_process_top_level}。Traceback (部分): {tb_str_for_thinking_log_fatal[:1000]}..."
            fatal_llm_interaction_id = f"fatal_agent_err_{str(uuid4())[:6]}"
            await status_callback({"type": "thinking_log", "request_id": request_id_for_fatal, "llm_interaction_id": fatal_llm_interaction_id, "stage": "fatal_error_capture", "content": thinking_log_content_fatal})
            await status_callback({"type": "general_status", "request_id": request_id_for_fatal, "stage": "fatal_error_handler", "status": "error", "message": f"请求处理失败,发生致命内部错误: {str(e_process_top_level)[:1000]}", "details": {"error_type": type(e_process_top_level).__name__, "full_error_message": str(e_process_top_level)}})
            await status_callback({"type": "final_response", "request_id": request_id_for_fatal, "llm_interaction_id": fatal_llm_interaction_id, "content": error_msg_for_user_fatal, "finaljson_if_success": None})
        finally:
            request_end_time = time.monotonic()
            duration_total = request_end_time - request_start_time
            logger.info(f"\n{'='*25} CircuitAgent 请求处理完毕 (ReqID: {self.current_request_id or 'N/A'}, 总耗时: {duration_total:.3f} 秒) {'='*25}\n")
            self.current_request_id = None


    # --- Helper Methods for Prompts (V1.0.0 - 辅助方法,用于生成系统提示) ---
    def _get_tool_schemas_for_prompt(self) -> str:
        if not self.tools_registry: return "  (当前无可用工具)"
        tool_schemas_parts = []
        sorted_tool_names = sorted(self.tools_registry.keys())

        for tool_name in sorted_tool_names:
            schema = self.tools_registry[tool_name]
            desc = schema.get('description', '无描述。')
            params_schema = schema.get('parameters', {})
            props_schema = params_schema.get('properties', {})
            req_params = params_schema.get('required', [])

            param_desc_segments = []
            if props_schema:
                sorted_param_names = sorted(props_schema.keys())
                for param_name in sorted_param_names: 
                    param_details_dict = props_schema[param_name]
                    param_type = param_details_dict.get('type','any')
                    is_required_str = "必须 (required)" if param_name in req_params else "可选 (optional)"
                    param_description = param_details_dict.get('description','无参数描述')
                    enum_values = param_details_dict.get('enum')
                    enum_desc = f" 可选值: {enum_values}。" if enum_values and isinstance(enum_values, list) else ""
                    param_desc_segments.append(f"    - 参数名 `{param_name}`:\n      - 类型: `{param_type}`\n      - 是否必需: {is_required_str}\n      - 描述: {param_description}{enum_desc}")
            elif params_schema.get("type") == "object" and not props_schema :
                 param_desc_segments = ["    - 此工具不接受任何参数(参数对象 `toolArguments` 应为空对象 `{}`)。"]
            else:
                 param_desc_segments = ["    - (此工具的参数定义似乎不完整或无参数)"]

            tool_schemas_parts.append(f"  - 工具名称: `{tool_name}`\n    工具描述: {desc}\n  工具参数详情 (这些参数应放在 `toolArguments` 对象内部):\n{chr(10).join(param_desc_segments)}")
        return "\n\n".join(tool_schemas_parts)

    def _get_planning_prompt(self, tool_schemas_desc: str, memory_context: str,
                                is_replanning: bool = False, request_id: Optional[str] = None) -> str:
        current_timestamp_utc = datetime.now(timezone.utc).isoformat()
        llm_interaction_id_example_plan_prefix = f"plan_ex_llm_id_{str(uuid4())[:6]}"
        example_prev_tool_call_id = f"tc_ex_prev_fail_{str(uuid4())[:6]}"

        reasoning_model_instructions = (
            "\n【重要: Reasoning Model 输出规范 (V1.0.0)】\n"
            "1.  **思考过程**: 您的详细思考过程、分析、逐步推理和决策逻辑【必须】包含在 `<think>...</think>` 标签内,并放在您回复的最开始部分。\n"
            "2.  **JSON 输出**: 在 `</think>` 标签之后,您【必须】输出一个严格符合下面描述的V1.0-CamelCaseJSON格式的单个JSON对象。此JSON对象应被三个反引号和'json'标记包围 (即 ```json ... ```)。JSON中所有key【必须】使用camelCase (例如: `isCallTools`, `toolCallRequests`, `requestId`).\n"
            "3.  **`thoughtProcess` 字段 (in JSON)**: JSON对象内部的 `thoughtProcess` 字段现在是次要的。它可以是一个简短的总结或留空 ( `\"\"` ),因为您的主要思考过程已在 `<think>...</think>` 块中。Agent将优先使用 `<think>` 块中的内容作为思考日志。\n"
        )

        replanning_guidance = ""
        if is_replanning:
            replanning_guidance = (
                "\n【重要: 重规划指示 (V1.0.0 - Reasoning Model)】\n"
                "您当前正在进行重规划。这意味着您之前的规划或工具执行遇到了问题。请在您的 `<think>...</think>` 块中：\n"
                "1.  **仔细分析失败原因**: 详细检查对话历史中的 `role: tool` 消息 (`content` JSON内的 `status: \"failure\"`, `message`, `errorDetails`) 和 `role: assistant` 消息中可能的Agent解析/校验错误 (`errorDetails.failedValidationPoints`)。\n"
                "2.  **参考当前电路状态**: 【务必】仔细查阅 `memory_context` 中的【当前电路状态】。您的新计划【必须】基于当前实际存在的元件和连接。不要不必要地重新添加已存在的元件。\n"
                "3.  **处理抽象节点**: 若涉及连接到 'INPUT', 'OUTPUT', 'GND' 等未作为元件存在的抽象节点失败,优先规划使用 `add_component_tool` (如 `component_type: 'Terminal'`) 创建它们,然后再连接。\n"
                "4.  **制定修正计划**: 基于以上分析,制定一个【全新的、修正了先前问题的计划】。这应在您的 `<think>...</think>` 块中清晰阐述。\n"
                "然后,在 `</think>` 之后输出符合V1.0-CamelCaseJSON规范的JSON。如果这个【新JSON本身的顶层 `status` 字段必须设置为 `'success'`】(因为您成功地为【当前这次思考和规划】输出了一个结构完整且逻辑合理的V1.0-CamelCaseJSON JSON)。\n"
                "5.  **无法解决的情况**: 如果分析后认为无法完成用户核心请求,则在 `<think>...</think>` 中解释,并在 `</think>` 后的JSON中制定一个【直接回复用户并解释情况的计划】 (`status: 'success'`, `isCallTools: False`).\n"
                "6.  **真正意义上的规划失败**: 只有当您在【当前这次重规划尝试中】,由于自身的理解困难、无法形成任何有效的 `<think>...</think>` 块或后续的V1.0-CamelCaseJSON JSON结构时,才应将后续JSON的顶层 `status` 字段设为 `'failure'`。\n"
                "**核心原则**: 不要因为*过去*的工具执行失败,就将您*当前新制定*的计划的JSON标记为 `status: 'failure'`. `status` 反映的是您【当前这次生成JSON这个行为本身】的成功与否。\n"
            )

        json_schema_description_for_prompt = """
```json
{
  "requestId": "string_or_null_当前用户请求周期的ID_如果系统提示中提供了此值请原样返回_否则为null",
  "llmInteractionId": "string_必须是本次LLM响应的唯一ID_例如_plan_llm_id_后跟8位随机字符_如_plan_llm_id_a1b2c3d4",
  "timestampUtc": "string_当前UTC时间戳_ISO_8601格式_例如_2024-07-16T12:00:00.000Z",
  "status": "string_必须是 'success' 或 'failure'._表示本次JSON输出是否由LLM为当前阶段成功生成。",
  "errorDetails": { // 如果 status 是 'success',则此字段为 null
    "errorType": "string_enum_高级错误类别_例如_PLANNING_ERROR_LLM_OUTPUT_VALIDATION_ERROR_INTERNAL_LOGIC_ERROR",
    "errorCode": "string_特定错误代码_例如_JSON_MALFORMED_MISSING_REQUIRED_FIELD_TOOL_PARAMS_INVALID",
    "messageToUser": "string_用户友好的解释_如果此错误与用户操作直接相关或适合用户查看。否则为通用Agent错误消息。",
    "technicalMessage": "string_详细的技术错误消息_用于日志记录和调试_这是LLM认为其自身输出生成过程中出现的问题。",
    "isDirectLlmFailure": "boolean_如果LLM明确表示无法完成请求或为本次尝试生成有效JSON则为True。如果错误是由于Agent端对LLM输出的JSON进行校验失败(即使JSON本身语法有效)_或LLM在格式良好的JSON中报告逻辑失败_则为False。",
    "failedValidationPoints": [ // 可选_如果LLM根据Agent反馈修正其先前的输出_则列出Agent发现的校验问题
      {
        "jsonPath": "string_例如_decision.toolCallRequests[0].toolArguments.component_id",
        "issue_description": "string_例如_必需字段缺失_或_值必须是字符串但得到的是整数"
      }
    ]
  },
  "executionPhase": "string_对于此任务_必须是 'planning'",
  "thoughtProcess": "string_此字段现在是次要的_您的主要详细推理必须在初始的 `<think>...</think>` 块中_此JSON字段可以是简短总结或为空_Agent将优先使用 `<think>` 块内容。",
  "decision": {
    "isCallTools": "boolean_如果需要调用工具则为True_否则为False_也接受不区分大小写的字符串 'true'/'false'",
    "toolCallRequests": [ // 如果 isCallTools 为 False, 则为 null 或空列表
      {
        "toolCallId": "string_由您为本次特定工具调用生成的唯一ID_例如_tc_add_resistor_xyz123",
        "toolName": "string_要调用的工具名称_从可用工具列表中选择 (例如 add_component_tool)",
        "toolArguments": { 
            // 此对象的内容是工具特定的_此处的键 (例如 component_type, value)
            // 应与 '可用工具列表与参数规范' 部分提供的 snake_case 名称匹配。
            // 电路工具示例: "component_type": "电阻", "value": "1k"
            // 搜索工具示例: "query": "欧姆定律", "num_results": 2 
        },
        "uiHints": { // 可选
            "displayNameForTool": "string_optional_更用户友好的工具调用名称_例如_添加电阻R1",
            "estimatedDurationCategory": "string_enum_optional_short_medium_long_very_long",
            "showProgressGranularly": "boolean_optional_如果为True_UI可能会显示更细粒度的进度(如果工具支持)_默认为False"
        },
        "estimatedComplexityOrNotes": "string_optional_LLM对此调用的内部注释_依赖关系或置信度。"
      }
    ],
    "responseToUser": {
      "contentType": "string_例如_text/plain_或_application/markdown",
      "content": "string_如果isCallTools为False_这是您对用户的直接且完整的回复_它必须非空。如果isCallTools为True_这应该是一条有意义的过渡消息_反映计划的操作_例如_好的_我将添加元件X然后连接到Y_如果确实不需要过渡消息则可以为空字符串_但为了用户体验首选提供一条好的消息。",
      "suggestionsForNextSteps": [ // 可选
        {
          "suggestionId": "string_optional_此建议的唯一ID_例如_sugg_ask_about_led_color",
          "textForUser": "string_向用户显示的建议文本_例如_您想指定LED颜色吗",
          "actionType": "string_enum_optional_USER_INPUT_EXPECTED_or_PREDEFINED_AGENT_ACTION_or_UI_NAVIGATION",
          "actionPayload": "object_or_string_optional_如果类型是PREDEFINED_AGENT_ACTION_这可能是简化的请求对象或命令字符串_供Agent在用户选择后处理"
        }
      ],
      "requiresUserClarificationForCurrentRequest": "boolean_optional_如果当前请求需要用户进一步输入才能继续_并且content正在请求该澄清_则设置为True_默认为False"
    }
  },
  "diagnostics": { // 可选
      "llmConfidenceScoreForThisOutput": "float_optional_0.0_到_1.0_LLM对此JSON输出的正确性和完整性的自评估置信度",
      "alternativePlansConsideredCount": "integer_optional_如果LLM在确定此计划前考虑了多个计划",
      "parsingFeedbackFromPreviousAttemptId": "string_or_null_如果这是对先前格式错误的JSON的修正_则为该失败尝试的llmInteractionId"
  },
  "usageMetadata": null
}
```
"""
        direct_qa_example = (
            "\n【通用示例1: 直接回答用户问题 (无需工具) - V1.0.0 Reasoning Model Output】\n"
            "如果用户问: “你好,什么是电容？”\n"
            "您的输出应类似 (ID和时间戳会变化): \n"
            "<think>\n"
            "用户询问电容的定义。这是一个概念性问题,不需要调用任何电路设计工具,我可以根据我的知识库直接回答。我将提供一个关于电容基本作用、单位和常见类型的解释,并给出下一步建议。我的回答将是清晰和直接的。\n"
            "</think>\n"
            "```json\n"
            "{\n"
            "  \"requestId\": \"" + (request_id or "userReqExampleId123") + "\",\n"
            "  \"llmInteractionId\": \"" + llm_interaction_id_example_plan_prefix + "_directQaCap\",\n"
            "  \"timestampUtc\": \"" + current_timestamp_utc + "\",\n"
            "  \"status\": \"success\",\n"
            "  \"errorDetails\": null,\n"
            "  \"executionPhase\": \"planning\",\n"
            "  \"thoughtProcess\": \"用户询问电容定义,直接回答。(主要思考过程在 <think> 块中)\",\n"
            "  \"decision\": {\n"
            "    \"isCallTools\": false,\n"
            "    \"toolCallRequests\": [],\n"
            "    \"responseToUser\": {\n"
            "      \"contentType\": \"text/plain\",\n"
            "      \"content\": \"电容是一种能够储存电荷的电子元件,由两块导体板中间夹一层绝缘介质构成。它的主要特性是电容量,单位是法拉(F),常用单位有微法(μF)、纳法(nF)和皮法(pF). 电容在电路中常用于滤波、耦合、隔直流、储能等.\",\n"
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
        tool_call_example = (
            "\n【通用示例2: 需要调用工具时的输出V1.0-CamelCaseJSON Reasoning Model Output】\n"
            "如果用户说: “帮我加一个1k欧姆的电阻R1,再用DuckDuckGo搜索'什么是LED'并返回2条结果,然后把R1连到GND。”\n"
            "您的输出应类似 (ID和时间戳会变化,每个toolCallId必须唯一,由您生成): \n"
            "<think>\n"
            "用户需要执行三个操作: 1. 添加电阻R1 (1kΩ)。 2. 使用DuckDuckGo搜索'什么是LED'并明确要求返回2条结果。3. 添加GND (如果不存在)并连接R1和GND。我将按顺序规划这三个/四个工具调用。确保为每个工具调用生成唯一的toolCallId。并为用户提供一个过渡性的回复,表明我理解了请求并正在处理。电路状态目前为空,元件GND可能需要先添加。\n"
            "</think>\n"
            "```json\n"
            "{\n"
            "  \"requestId\": \"" + (request_id or "userReqExampleId456") + "\",\n"
            "  \"llmInteractionId\": \"" + llm_interaction_id_example_plan_prefix + "_multiToolSearchFix2\",\n"
            "  \"timestampUtc\": \"" + current_timestamp_utc + "\",\n"
            "  \"status\": \"success\",\n"
            "  \"errorDetails\": null,\n"
            "  \"executionPhase\": \"planning\",\n"
            "  \"thoughtProcess\": \"规划添加R1,搜索,连接GND。(主要思考过程在 <think> 块中)\",\n"
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
            "        \"toolCallId\": \"tc_search_led_" + str(uuid4())[:8] + "\",\n"
            "        \"toolName\": \"duckduckgo_search_tool\",\n"
            "        \"toolArguments\": {\"query\": \"什么是LED\", \"num_results\": 2},\n"
            "        \"uiHints\": {\"displayNameForTool\": \"搜索LED定义(2条结果)\"}\n"
            "      },\n"
            "      {\n"
            "        \"toolCallId\": \"tc_add_gnd_" + str(uuid4())[:8] + "\",\n"
            "        \"toolName\": \"add_component_tool\",\n"
            "        \"toolArguments\": {\"component_type\": \"地\", \"component_id\": \"GND\"},\n"
            "        \"uiHints\": {\"displayNameForTool\": \"添加地线 GND (如果需要)\"}\n"
            "      },\n"
            "      {\n"
            "        \"toolCallId\": \"tc_conn_r1gnd_" + str(uuid4())[:8] + "\",\n"
            "        \"toolName\": \"connect_components_tool\",\n"
            "        \"toolArguments\": {\"comp1_id\": \"R1\", \"comp2_id\": \"GND\"},\n"
            "        \"uiHints\": {\"displayNameForTool\": \"连接 R1 与 GND\"}\n"
            "      }\n"
            "    ],\n"
            "    \"responseToUser\": {\n"
            "      \"contentType\": \"text/plain\",\n"
            "      \"content\": \"好的,我正在为您添加电阻R1 (1kΩ),搜索LED的定义(2条结果),并准备连接R1到GND。请稍候...\",\n"
            "      \"suggestionsForNextSteps\": []\n"
            "    }\n"
            "  },\n"
            "  \"diagnostics\": null,\n"
            "  \"usageMetadata\": null\n"
            "}\n"
            "```\n"
        )
        
        replan_example = ""
        if is_replanning:
            replan_example = (
                "\n【重规划示例 (V1.0.0 Reasoning Model Output): 工具失败后,成功重规划并调用新/修正的工具】\n"
                "假设历史记录中有如下用户请求和失败的工具调用: \n"
                "  User: \"连接 R10 和 C5\"\n"
                "  Assistant (Previous Plan JSON): ... (Planned connect_components_tool for R10, C5, llmInteractionId: " + example_prev_tool_call_id + "_plan) ...\n"
                "  Tool (connect_components_tool, toolCallId: " + example_prev_tool_call_id + "_tool, name: connect_components_tool) result (in history): { \"role\": \"tool\", ..., \"content\": \"{\\\"status\\\": \\\"failure\\\", \\\"message\\\": \\\"错误: 元件 'R10' 在电路中不存在. \\\", \\\"error\\\": { \\\"error_type\\\": \\\"CIRCUIT_OPERATION_ERROR\\\", \\\"error_code\\\": \\\"COMPONENT_NOT_FOUND_FOR_CONNECTION\\\", ... }}\" }\n"
                "  Current Circuit State (in memory_context): (R10 does not exist, C5 exists)\n"
                "您在【当前重规划】时,您的新V1.0-CamelCaseJSON 输出应类似: \n"
                "<think>\n"
                "重规划开始。分析历史: 用户想连接R10和C5。上一个计划 (llmInteractionId: " + example_prev_tool_call_id + "_plan) 中调用connect_components_tool (toolCallId: " + example_prev_tool_call_id + "_tool) 失败了,工具报告原因是元件 'R10' 在电路中不存在。当前电路状态也确认R10不在电路中，但C5存在。因此,我的新计划是首先添加R10 (用户未指定类型或值,我将默认为电阻,并提供一个常用值如1kΩ). 然后再调用connect_components_tool连接新创建的R10和已存在的C5。本次规划逻辑清晰，后续的JSON应标记为status: 'success'.\n"
                "</think>\n"
                "```json\n"
                "{\n"
                "  \"requestId\": \"" + (request_id or "userReqExampleId789Replan") + "\",\n"
                "  \"llmInteractionId\": \"" + llm_interaction_id_example_plan_prefix + "_replanAddConnectFix2\",\n"
                "  \"timestampUtc\": \"" + current_timestamp_utc + "\",\n"
                "  \"status\": \"success\",\n"
                "  \"errorDetails\": null,\n"
                "  \"executionPhase\": \"planning\",\n"
                "  \"thoughtProcess\": \"R10不存在,先添加再连接。(主要思考过程在 <think> 块中)\",\n"
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
                "      \"content\": \"检测到元件R10之前不存在。我将先为您添加一个1kΩ的电阻R10,然后再将它与C5连接。\",\n"
                "      \"suggestionsForNextSteps\": [\n"
                "        {\"textForUser\": \"操作完成后显示电路状态.\"}\n"
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
            "您是一位初版电路设计编程助理 (Agent Version V1.0.0, 11 Tools)。您的任务是理解用户指令,并据此规划行动或直接回复。\n", # Version update
            reasoning_model_instructions,
            "\n【核心任务: 规划阶段 (V1.0.0)】\n"
            "请首先在 `<think>...</think>` 标签内深入分析用户的最新指令、完整的对话历史、当前的电路状态和记忆。然后,在 `</think>` 标签之后,生成一个符合V1.0-CamelCaseJSON规范的JSON对象作为您的行动计划或直接回复。JSON中所有key【必须】使用camelCase (例如: `isCallTools`, `toolCallRequests`, `requestId`).\n",
            replanning_guidance if is_replanning else "",
            "【V1.0.0 输出格式规范 (在</think>之后输出, 必须严格遵守)】:\n",
            json_schema_description_for_prompt,
            "\n【重要指令与检查清单 (V1.0.0 - Planning)】:\n"
            "1.  **`<think>` Block First**: 您的详细逐步推理**必须**在 `<think>...</think>` 标签内,并置于回复最开始。\n"
            "2.  **JSON After `</think>`**: V1.0.0 对象 (用 ```json ... ``` 包裹) **必须**紧跟 `</think>` 标签。此JSON中的所有键名必须是 camelCase (例如, `requestId`, `isCallTools`, `toolCallRequests`)。`toolArguments` 内部的键名 (例如, `component_type`) 应遵循下面工具 Schema 中提供的 snake_case 命名。\n"
            "3.  **JSON `thoughtProcess` Field**: 此JSON字段现在是次要的。它可以是简短总结或空字符串 `\"\"`。`<think>...</think>` 块中的内容是主要的思考过程。\n"
            "4.  **`decision.isCallTools`**: JSON中的此字段**必须**是布尔值 (`true` 或 `false`)。大小写不敏感的字符串 \"True\" 或 \"true\" 也可接受,Agent会将其解析为布尔值。\n"
            "5.  **其他 JSON 字段**: 严格遵循V1.0-CamelCaseJSON Schema 的JSON部分。\n"
            "6.  **电路状态感知**: 在规划涉及现有元件的工具调用前,请在 `memory_context` (当前电路状态) 中确认它们的存在。如果需要连接像 'INPUT' 这样的抽象节点而它们并非作为元件存在,请首先规划添加它们 (例如,作为 'Terminal')。\n\n",
            direct_qa_example,
            tool_call_example,
        ]
        if is_replanning:
            prompt_parts.append(replan_example)

        prompt_parts.extend([
            "\n【可用工具列表与参数规范 (V1.0.0 - 11 Tools)】:\n", # Version update
            tool_schemas_desc,
            "\n\n【当前上下文信息 (V1.0.0)】:\n"
            f"Current Request ID (如果可用,请在JSON的requestId字段中原样返回): {request_id or 'N/A_NOT_PROVIDED_IN_PROMPT_SET_TO_NULL'}\n"
            f"Current UTC Time (供您生成timestampUtc参考): {current_timestamp_utc}\n"
            f"当前电路与记忆摘要:\n{memory_context}\n\n"
            "【最后再次强调】: 您的输出【必须】以 `<think>...</think>` 块开始,后跟一个被 ```json ... ``` 包围的、严格符合上述V1.0-CamelCaseJSON规范 (所有key使用camelCase) 的单个JSON对象。JSON对象之外不应有任何其他文本。请务必仔细检查 `<think>` 块的使用以及JSON的语法和所有字段的类型及条件要求！"
        ])
        return "".join(prompt_parts)

    def _get_response_generation_prompt(self, memory_context: str, tool_schemas_desc: str, request_id: Optional[str] = None) -> str:
        current_timestamp_utc = datetime.now(timezone.utc).isoformat()
        llm_interaction_id_example_resp_prefix = f"resp_ex_llm_id_{str(uuid4())[:6]}"

        reasoning_model_instructions_resp_phase = (
            "\n【重要: Reasoning Model 输出规范 (V1.0.0 - Response Generation)】\n"
            "1.  **思考过程**: 您的详细思考过程 (如何分析工具结果或决定直接回复, 以及如何构思最终回复) 【必须】包含在 `<think>...</think>` 标签内,并放在您回复的最开始部分。\n"
            "2.  **JSON 输出**: 在 `</think>` 标签之后,您【必须】输出一个严格符合下面描述的V1.0-CamelCaseJSON格式的单个JSON对象。此JSON对象应被三个反引号和'json'标记包围 (即 ```json ... ```)。JSON中所有key【必须】使用camelCase.\n"
            "3.  **`thoughtProcess` 字段 (in JSON)**: JSON对象内部的 `thoughtProcess` 字段现在是次要的。它可以是一个简短的总结或留空 ( `\"\"` ),因为您的主要思考过程已在 `<think>...</think>` 块中。Agent将优先使用 `<think>` 块中的内容作为思考日志。\n"
        )
        
        json_schema_description_for_resp_phase = """
```json
{
  "requestId": "string_or_null_当前用户请求周期的ID_如果系统提示中提供了此值请原样返回_否则为null",
  "llmInteractionId": "string_必须是本次LLM响应的唯一ID_例如_resp_llm_id_后跟8位随机字符_如_resp_llm_id_e5f6g7h8",
  "timestampUtc": "string_当前UTC时间戳_ISO_8601格式_例如_2024-07-16T12:05:00.000Z",
  "status": "string_必须是 'success' 或 'failure'_表示您是否为本次尝试成功生成了此最终响应JSON_如果您现在无法构思出合适的摘要或回复_则设为failure",
  "errorDetails": {
    "errorType": "string_enum_例如_RESPONSE_GENERATION_ERROR_LLM_OUTPUT_VALIDATION_ERROR",
    "errorCode": "string_例如_JSON_MALFORMED_SUMMARY_LOGIC_ERROR",
    "messageToUser": "string_optional_用户友好的消息_如果适用",
    "technicalMessage": "string_本次响应生成尝试的详细技术错误消息。",
    "isDirectLlmFailure": "boolean_如果LLM明确表示无法完成请求或为本次尝试生成有效JSON则为True。如果错误是由于Agent端对LLM输出的JSON进行校验失败(即使JSON本身语法有效)_或LLM在格式良好的JSON中报告逻辑失败_则为False。",
    "failedValidationPoints": [ { "jsonPath": "...", "issue_description": "..." } ]
  },
  "executionPhase": "string_对于此任务_必须是 'response_generation'",
  "thoughtProcess": "string_此字段现在是次要的_您的主要详细推理必须在初始的 `<think>...</think>` 块中_此JSON字段可以是简短总结或为空_Agent将优先使用 `<think>` 块内容。",
  "decision": {
    "isCallTools": "boolean_在此响应生成阶段必须为false_也接受不区分大小写的字符串 'true'/'false'",
    "toolCallRequests": [],
    "responseToUser": {
      "contentType": "string_例如_text/plain_或_application/markdown",
      "content": "string_这是您对用户的最终且完整的回复_它必须非空。它应总结已采取的操作_报告结果_并根据工具输出(如果最初未调用工具_则根据您的直接知识)回应用户的原始请求。此内容是用户将看到的。",
      "suggestionsForNextSteps": [
        {
          "suggestionId": "string_optional_此建议的唯一ID_例如_sugg_ask_about_led_color",
          "textForUser": "string_向用户显示的建议文本_例如_您想指定LED颜色吗",
          "actionType": "string_enum_optional_USER_INPUT_EXPECTED_or_PREDEFINED_AGENT_ACTION_or_UI_NAVIGATION",
          "actionPayload": "object_or_string_optional_如果类型是PREDEFINED_AGENT_ACTION_这可能是简化的请求对象或命令字符串_供Agent在用户选择后处理"
        }
      ],
      "requiresUserClarificationForCurrentRequest": "boolean_optional_如果当前请求需要用户进一步输入才能继续_并且content正在请求该澄清_则设置为True_默认为False"
    }
  },
  "diagnostics": {
      "llmConfidenceScoreForThisOutput": "float_optional_0.0_到_1.0",
      "alternativePlansConsideredCount": "integer_optional",
      "parsingFeedbackFromPreviousAttemptId": "string_or_null"
  },
  "usageMetadata": null
}
```
"""
        response_gen_example = (
            "\n【示例 (V1.0.0 Reasoning Model Output): 总结工具结果并生成最终回复】\n"
            "假设对话历史中包含以下工具执行结果 (工具1成功, 工具2是搜索工具也成功):\n"
            "  Tool Message 1 (for toolCallId: tc_xyz_add_r1): { \"role\": \"tool\", ..., \"content\": \"{\\\"status\\\": \\\"success\\\", \\\"message\\\": \\\"已添加电阻R1\\\", ...}\" }\n"
            "  Tool Message 2 (for toolCallId: tc_abc_search_led): { \"role\": \"tool\", ..., \"content\": \"{\\\"status\\\": \\\"success\\\", \\\"message\\\": \\\"已完成对'LED'的DuckDuckGo搜索,找到2条相关信息。\\\", \\\"data\\\": {\\\"query\\\": \\\"LED\\\", \\\"num_results_returned\\\": 2, \\\"results_json_string\\\": \\\"[{\\\\\\\"title\\\\\\\":\\\\\\\"LED - Wikipedia\\\\\\\", ...}]\\\"}}\" }\n"
            "您的输出V1.0-CamelCaseJSON JSON应类似 (ID和时间戳会变化): \n"
            "<think>\n"
            "回顾工具执行结果: add_component_tool (toolCallId: tc_xyz_add_r1) 成功添加了电阻R1。duckduckgo_search_tool (toolCallId: tc_abc_search_led) 成功搜索了'LED'并返回了结果。我需要向用户清晰地报告这两个操作的成功,并简要提及搜索到的信息。最终的回复将整合这些信息,保持友好和乐于助人的语气。\n"
            "</think>\n"
            "```json\n"
            "{\n"
            "  \"requestId\": \"" + (request_id or "userReqExampleIdResp123") + "\",\n"
            "  \"llmInteractionId\": \"" + llm_interaction_id_example_resp_prefix + "_finalSummaryRSearchFix2\",\n" 
            "  \"timestampUtc\": \"" + current_timestamp_utc + "\",\n"
            "  \"status\": \"success\",\n"
            "  \"errorDetails\": null,\n"
            "  \"executionPhase\": \"response_generation\",\n"
            "  \"thoughtProcess\": \"总结R1添加成功,LED搜索成功。(主要思考过程在 <think> 块中)\",\n"
            "  \"decision\": {\n"
            "    \"isCallTools\": false, \n"
            "    \"toolCallRequests\": [], \n"
            "    \"responseToUser\": {\n"
            "      \"contentType\": \"text/plain\",\n"
            "      \"content\": \"您好,我已经成功为您添加了电阻R1。关于LED的DuckDuckGo搜索也已完成,我找到了2条相关信息,例如 'LED - Wikipedia'。您想了解更多搜索到的细节吗？\",\n"
            "      \"suggestionsForNextSteps\": [\n"
            "        {\"suggestionId\": \"sugg_show_search_details\", \"textForUser\": \"显示LED搜索结果的详细信息\", \"actionType\": \"USER_INPUT_EXPECTED\"},\n"
            "        {\"suggestionId\": \"sugg_view_circuit\", \"textForUser\": \"查看当前电路中已有的元件列表。\", \"actionType\": \"USER_INPUT_EXPECTED\", \"actionPayload\": \"当前电路什么样\"}\n"
            "      ],\n"
            "      \"requiresUserClarificationForCurrentRequest\": false \n"
            "    }\n"
            "  },\n"
            "  \"diagnostics\": {\"llmConfidenceScoreForThisOutput\": 0.98},\n"
            "  \"usageMetadata\": null\n"
            "}\n"
            "```\n"
        )
        return (
            "您是一位初版电路设计编程助理 (Agent Version V1.0.0, 11 Tools), 经验丰富,技术精湛,并且极其擅长清晰、准确、诚实地汇报工作结果。\n" # Version update
            f"{reasoning_model_instructions_resp_phase}\n"
            "【核心任务: 响应生成阶段 (V1.0.0)】\n"
            "您当前的任务是: 基于到目前为止的【完整对话历史】(包括用户最初的指令、您在规划阶段生成的V1.0-CamelCaseJSON计划、以及所有【已执行工具的结果详情】,这些工具结果是以 'role: tool', 'toolCallId: ...', 'name: ...', 'content: JSON_string_of_tool_output' 的格式存在于历史记录中的), 首先在 `<think>...</think>` 标签内进行思考和总结, 然后在 `</think>` 之后生成【最终的、面向用户的V1.0-CamelCaseJSON回复】。JSON中所有key【必须】使用camelCase.\n\n"
            "【V1.0.0 输出格式规范 (在</think>之后输出, 与规划阶段结构相同,但有特定值要求 - 再次强调)】:\n"
            f"{json_schema_description_for_resp_phase}\n"
            "【重要指令与检查清单 (V1.0.0 - 响应生成阶段特定要求)】:\n"
            "1.  **`<think>` Block First**: 您的详细工具结果分析和回复构思**必须**在 `<think>...</think>` 标签内。\n"
            "2.  **JSON After `</think>`**: V1.0.0 对象 (用 ```json ... ``` 包裹) **必须**紧跟 `</think>` 标签。此JSON中的所有键名必须是 camelCase。\n"
            "3.  **`executionPhase`**: 在此阶段,此值【必须】是 `\"response_generation\"`。\n"
            "4.  **`decision.isCallTools`**: 在此响应生成阶段,此值【必须】为 `false` (或可解析为`false`的字符串)。\n"
            "5.  **`decision.toolCallRequests`**: 在此响应生成阶段,此列表【必须】为 `[]` (空数组) 或 `null`。\n"
            "6.  **`decision.responseToUser.content`**: 这是您基于所有先前步骤生成的【最终、完整、友好】的文本回复。它【不能】为空字符串或仅包含空白。\n"
            "7.  **回顾工具结果**: 仔细检查对话历史中 `role: tool` 的消息。您的最终回复必须准确反映这些结果。\n\n"
            f"{response_gen_example}\n"
            "【上下文参考信息 (仅供你回顾 - V1.0.0)】:\n"
            f"Current Request ID (如果可用,请在JSON的requestId字段中原样返回): {request_id or 'N/A_NOT_PROVIDED_IN_PROMPT_SET_TO_NULL'}\n"
            f"Current UTC Time (供您生成timestampUtc参考): {current_timestamp_utc}\n"
            f"当前电路与记忆摘要:\n{memory_context}\n"
            f"我的可用工具列表 (共11个, 仅供你参考,此阶段不应再调用它们):\n{tool_schemas_desc}\n\n" # Version update
            "【最后再次强调】: 您的输出【必须】以 `<think>...</think>` 块开始,后跟一个被 ```json ... ``` 包围的、严格符合上述V1.0-CamelCaseJSON规范 (所有key使用camelCase) 的单个JSON对象。在这个阶段,您【绝对不能】再请求调用任何新工具。您的任务是总结并回复。"
        )

# --- Main entry point for testing (Optional) ---
async def main_test_flow(agent: CircuitAgent, user_query: str):
    logger.info(f"\n\n>>>>>>>>> 测试开始 (V1.0.0): 用户查询: '{user_query}' <<<<<<<<<<") # Version update

    async def mock_status_callback(status_update: Dict[str, Any]):
        if "finaljson_if_success" in status_update and status_update["finaljson_if_success"]:
            printable_update = status_update.copy()
            try:
                printable_update["finaljson_if_success"] = json.loads(json.dumps(status_update["finaljson_if_success"], indent=2, ensure_ascii=False))
            except:
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
    logger.info(f">>>>>>>>>> 测试结束 (V1.0.0): 用户查询: '{user_query}' <<<<<<<<<<\n") # Version update

if __name__ == "__main__":
    logger.info("========== CircuitAgent V1.0.0 (11 Tools) - 命令行测试模式 ==========") 
    
    zhipu_api_key = os.environ.get("ZHIPUAI_API_KEY")
    if not zhipu_api_key:
        logger.critical("严重错误: ZHIPUAI_API_KEY 环境变量未设置,且代码中也未提供。Agent 无法运行。")
        sys.exit("错误: ZHIPUAI_API_KEY 未设置。请在运行前设置此环境变量。")

    test_agent = None # 初始化为 None
    try:
        test_agent = CircuitAgent(
            api_key=zhipu_api_key,
            model_name="glm-z1-flash",
            verbose=True,
            max_short_term_items=20,
            planning_llm_retries=1, 
            max_tool_retries=0, 
            max_replanning_attempts=1 
        )
        logger.info("CircuitAgent V1.0.0 (11 Tools) 初始化成功,准备接收测试指令。")
    except Exception as e_init:
        logger.critical(f"Agent 初始化失败: {e_init}", exc_info=True)
        sys.exit(f"Agent 初始化失败: {e_init}")

    test_queries = [
        "你好,你是谁？",
        "当前电路是什么样的?",
        "帮我添加一个10k欧姆的电阻,命名为R100。",
        "使用 DuckDuckGo 搜索一下什么是基尔霍夫电流定律。",
        "用 DuckDuckGo 搜索 'Python async library' 并返回2条结果",
        "搜索知乎", 
        "请帮我把R100的电阻值更新为4.7k, 然后查一下R100的连接数量, 接着用DuckDuckGo搜索“运算放大器原理”, 最后再移除R100。",
        "清空整个电路。",
    ]

    async def run_all_tests_main(agent_instance: CircuitAgent): # 修改函数名以示区别
        for i, query in enumerate(test_queries):
            logger.info(f"\n--- 测试用例 {i+1}/{len(test_queries)} (V1.0.0) ---")
            await main_test_flow(agent_instance, query) # 传递 agent_instance
            logger.info(f"--- 测试用例 {i+1} (V1.0.0) 完成 ---\n")
            if i < len(test_queries) - 1:
                 await asyncio.sleep(2)

    # ------------------- 关键修复部分开始 -------------------
    async def cleanup_remaining_tasks(current_loop):
        """Helper coroutine to clean up remaining tasks."""
        active_tasks = [task for task in asyncio.all_tasks(current_loop) if not task.done()]
        if active_tasks:
            logger.info(f"等待 {len(active_tasks)} 个剩余异步任务完成...")
            try:
                # 等待所有当前活动的任务完成，设置一个超时以防万一
                await asyncio.wait_for(asyncio.gather(*active_tasks, return_exceptions=True), timeout=5.0)
                logger.info("所有剩余异步任务已处理。")
            except asyncio.TimeoutError:
                logger.warning("等待剩余异步任务超时。")
                # 对于超时的任务，尝试取消它们
                for task in active_tasks:
                    if not task.done():
                        task.cancel()
                        try:
                            await task # 等待取消完成
                        except asyncio.CancelledError:
                            logger.info(f"任务 {task.get_name()} 已取消。")
                        except Exception as e_cancel:
                            logger.error(f"取消任务 {task.get_name()} 时发生错误: {e_cancel}")
            except Exception as e_gather:
                logger.error(f"处理剩余异步任务时发生错误: {e_gather}", exc_info=True)
    # ------------------- 关键修复部分结束 -------------------

    main_loop_is_running_at_start = loop.is_running()
    try:
        if test_agent: # 确保 agent 实例已创建
            # 如果主循环没有运行 (例如，直接从脚本顶部获取的 loop)，则使用 run_until_complete
            if not main_loop_is_running_at_start:
                loop.run_until_complete(run_all_tests_main(test_agent))
            else:
                # 如果已经在运行的循环中 (不太可能直接运行脚本时发生，但为了健壮性)
                # 我们可以创建一个新任务并等待它，但这会复杂化。
                # 简单起见，假设直接运行脚本时，loop 是由我们控制的。
                # 为了安全，我们还是用 run_until_complete, 它能处理好新旧循环。
                asyncio.run(run_all_tests_main(test_agent)) # 或者 loop.run_until_complete
        else:
            logger.error("Agent 实例未能创建，无法运行测试。")

    except KeyboardInterrupt:
        logger.info("测试被用户中断。")
    except Exception as e_main_run:
        logger.critical(f"运行测试时发生未处理的异常: {e_main_run}", exc_info=True)
    finally:
        # 确保在 finally 块中我们使用的是仍然有效的 loop 引用
        # 并且只在它真的还在运行时尝试关闭它。
        # asyncio.run() 会自己管理循环的关闭。
        # 如果是手动管理的 loop，则需要这里的逻辑。
        
        current_loop_ref = None
        try:
            current_loop_ref = asyncio.get_running_loop()
        except RuntimeError: # No running loop
            current_loop_ref = loop # Fallback to the loop we initially got/created

        if current_loop_ref and not current_loop_ref.is_closed():
            # 使用 run_until_complete 来运行清理协程
            logger.info("开始执行异步清理任务...")
            current_loop_ref.run_until_complete(cleanup_remaining_tasks(current_loop_ref))
            logger.info("异步清理任务完成。")
            
            # 只有当这个循环不是由 asyncio.run() 管理时才手动关闭
            # 如果是手动通过 set_event_loop 和 run_until_complete (针对单个协程) 管理的
            if not main_loop_is_running_at_start and current_loop_ref is loop: # 确保是我们手动启动和停止的循环
                 if not current_loop_ref.is_closed(): # 再次检查，因为cleanup可能已经关闭了某些东西
                    current_loop_ref.close()
                    logger.info("事件循环已关闭。")
            elif current_loop_ref.is_running() and not current_loop_ref.is_closed(): # 如果是其他情况且仍在运行
                logger.warning("事件循环仍在运行但未明确关闭，这可能发生在嵌套的asyncio使用中。")


        logger.info("========== CircuitAgent V1.0.0 (11 Tools) - 命令行测试结束 ==========")