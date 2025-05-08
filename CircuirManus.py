# -*- coding: utf-8 -*-
# @FileName: openmanus_v7_tech_comments.py
# @Version: V7.1 - Async, Decorator Tools, Technical Comments, Refactored
# @Author: Your Most Loyal & Dedicated Programmer (Refactored & Enhanced)
# @Date: [Current Date] - Refactored Version
# @License: Apache 2.0 (Anticipated)
# @Description:
# ==============================================================================================
#  Manus 系统 V7.1 技术实现说明 (重构与增强版)
# ==============================================================================================
#
# 本脚本实现了一个用于电路设计的异步 Agent。我严格遵循标准的 Agentic 循环：
# 感知 -> 规划 -> 行动 -> 观察 -> 响应生成。
#
# 本次重构的核心改进包括：
# 1.  电路实体类 (`Circuit`): 将电路的元件、连接、ID计数器等状态信息封装到一个独立的 `Circuit` 对象中，使得电路状态管理更加面向对象和结构化。
# 2.  内存管理器 (`MemoryManager`): 我用它来管理短期对话历史（基于数量修剪）、长期知识片段（简单FIFO队列）以及核心的 `Circuit` 对象。
# 3.  LLM 接口 (`LLMInterface`): 我封装了与大语言模型的异步交互，使用 `asyncio.to_thread` 包装同步SDK调用，避免阻塞。
# 4.  输出解析器 (`OutputParser`): 我负责解析 LLM 返回的文本，特别是规划阶段的 `<think>` 和自定义 JSON 计划，以及响应阶段的 `<think>` 和文本回复。对 JSON 提取和验证进行了鲁棒性处理。
# 5.  工具执行器 (`ToolExecutor`): 我按 LLM 规划的顺序异步协调执行内部工具。本次增强了工具级别的重试机制：如果一个工具执行失败，会根据配置重试多次。
# 6.  内部工具 (Action Methods): 使用 `@register_tool` 装饰器动态注册，操作现在直接修改 MemoryManager 持有的 `Circuit` 对象。
# 7.  异步核心 (`Orchestrator` - `process_user_request`): 这是 Agent 的核心，协调整个流程。本次新增了规划失败后的智能重规划机制：如果工具执行过程中发生失败，Agent 会携带失败信息，重新向 LLM 请求生成一个新的执行计划。
#
# 关键技术特性：
# -   全面异步化 (`asyncio`): 核心流程、LLM 调用和工具执行协调都是异步的。
# -   电路状态对象化: 使用 `Circuit` 类更好地管理电路状态。
# -   自定义 JSON 规划: 不依赖 LLM 内置 Function Calling，通过解析特定 JSON 控制规划。
# -   规划重试: LLM 首次规划调用失败时可重试。
# -   工具执行重试: 单个工具执行失败时可重试。
# -   规划失败重规划: 工具执行失败后，Agent 会利用失败信息向 LLM 请求新的规划。
# -   记忆修剪: MemoryManager 自动修剪短期记忆。
# -   动态工具注册: 使用装饰器模式简化工具管理。
# -   鲁棒的解析和错误处理: 对 LLM 输出解析、工具参数、工具执行结果等进行详细验证和错误捕获。
#
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
from typing import List, Dict, Any, Optional, Tuple, Set, Union
from zhipuai import ZhipuAI

# --- 全局异步事件循环 ---
# 确保在不同环境（脚本、Jupyter）中都能获取或创建事件循环
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# --- 日志系统配置 ---
logging.basicConfig(
    level=logging.DEBUG, # 开发时设为 DEBUG，生产环境可调高
    format='%(asctime)s - %(name)s - %(levelname)s [%(module)s.%(funcName)s:%(lineno)d] - %(message)s',
    stream=sys.stderr # 日志输出到 stderr，避免干扰 stdout 的用户交互
)
logger = logging.getLogger(__name__)
# 降低依赖库的日志级别，避免过多无关信息
logging.getLogger("zhipuai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# --- 异步友好的打印函数 ---
async def async_print(message: str, end: str = '\n', flush: bool = True):
    """在异步环境中安全地打印到标准输出，避免潜在的交错问题。"""
    # 对于简单的命令行应用，直接写 sys.stdout 通常可以接受。
    # 在高并发或复杂 GUI/Web 应用中，可能需要更复杂的日志或队列机制。
    sys.stdout.write(message + end)
    if flush:
        sys.stdout.flush()

# --- 电路元件数据类 ---
class CircuitComponent:
    """我定义了这个类来标准化电路元件的数据结构，并进行基本的输入验证。"""
    __slots__ = ['id', 'type', 'value'] # 使用 slots 优化内存占用
    def __init__(self, component_id: str, component_type: str, value: Optional[str] = None):
        # 我对 ID 和类型执行非空字符串检查
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError("元件 ID 必须是有效的非空字符串")
        if not isinstance(component_type, str) or not component_type.strip():
            raise ValueError("元件类型必须是有效的非空字符串")
        # ID 统一转为大写，去除首尾空格
        self.id: str = component_id.strip().upper()
        # 类型去除首尾空格
        self.type: str = component_type.strip()
        # 值转换为字符串并去除空格，如果值为 None 或空字符串，则设为 None
        self.value: Optional[str] = str(value).strip() if value is not None and str(value).strip() else None
        logger.debug(f"成功创建元件对象: {self}")
    def __str__(self) -> str:
        # 定义对象的字符串表示形式，用于日志和描述
        value_str = f" (值: {self.value})" if self.value else ""
        return f"元件: {self.type} (ID: {self.id}){value_str}"
    def __repr__(self) -> str:
        # 定义对象的开发者友好表示形式
        return f"CircuitComponent(id='{self.id}', type='{self.type}', value={repr(self.value)})"
    def to_dict(self) -> Dict[str, Any]:
        """将元件对象转换为字典，便于序列化或显示。"""
        return {"id": self.id, "type": self.type, "value": self.value}


# --- 电路实体类 ---
class Circuit:
    """
    电路实体类。我封装了所有与电路状态相关的逻辑和数据。
    现在 `MemoryManager` 只管理一个 `Circuit` 类的实例。
    """
    def __init__(self):
        logger.info("[Circuit] 初始化电路实体。")
        # 存储 {component_id: CircuitComponent 对象}
        self.components: Dict[str, CircuitComponent] = {}
        # 存储排序后的元件 ID 对元组 (id1, id2)，确保连接的唯一性 (A-B 和 B-A 视为同一连接)
        self.connections: Set[Tuple[str, str]] = set()
        # 为常见元件类型维护 ID 生成计数器
        self._component_counters: Dict[str, int] = {
            'R': 0, 'L': 0, 'B': 0, 'S': 0, 'C': 0, 'V': 0, 'G': 0, 'U': 0, 'O': 0,
            'I': 0, 'A': 0, 'D': 0, 'P': 0, 'F': 0, 'H': 0 # 涵盖更多类型
        }
        logger.info("[Circuit] 电路实体初始化完成。")

    def add_component(self, component: CircuitComponent):
        """添加一个 CircuitComponent 对象到电路。"""
        if component.id in self.components:
            raise ValueError(f"元件 ID '{component.id}' 已被占用。")
        self.components[component.id] = component
        logger.debug(f"[Circuit] 元件 '{component.id}' 已添加到电路。")

    def remove_component(self, component_id: str):
        """从电路中移除一个元件及其所有相关连接。"""
        comp_id_upper = component_id.strip().upper()
        if comp_id_upper not in self.components:
            raise ValueError(f"元件 '{comp_id_upper}' 在电路中不存在。")
        del self.components[comp_id_upper]
        # 移除所有涉及该元件的连接
        connections_to_remove = {conn for conn in self.connections if comp_id_upper in conn}
        for conn in connections_to_remove:
            self.connections.remove(conn)
            logger.debug(f"[Circuit] 移除了涉及元件 '{comp_id_upper}' 的连接 {conn}.")
        logger.debug(f"[Circuit] 元件 '{comp_id_upper}' 及其相关连接已从电路中移除。")


    def connect_components(self, id1: str, id2: str):
        """连接两个元件。执行前检查元件是否存在并避免自连接和重复连接。"""
        id1_upper = id1.strip().upper()
        id2_upper = id2.strip().upper()

        if id1_upper == id2_upper:
            raise ValueError(f"不能将元件 '{id1}' 连接到它自己。")
        if id1_upper not in self.components:
             raise ValueError(f"元件 '{id1}' 在电路中不存在。")
        if id2_upper not in self.components:
             raise ValueError(f"元件 '{id2}' 在电路中不存在。")

        # 使用排序后的 ID 元组作为连接的唯一标识
        connection = tuple(sorted((id1_upper, id2_upper)))
        if connection in self.connections:
             logger.warning(f"[Circuit] 连接 '{id1_upper}' <--> '{id2_upper}' 已存在。")
             # 对于已存在的连接，我们认为操作本身是成功的，只是状态没有变化。
             # 可以在调用层判断并返回不同的消息。
             return False # 返回 False 表示连接已存在

        self.connections.add(connection)
        logger.debug(f"[Circuit] 添加了连接: {id1_upper} <--> {id2_upper}.")
        return True # 返回 True 表示连接成功添加

    def disconnect_components(self, id1: str, id2: str):
        """断开两个元件的连接。"""
        id1_upper = id1.strip().upper()
        id2_upper = id2.strip().upper()
        connection = tuple(sorted((id1_upper, id2_upper)))

        if connection not in self.connections:
             logger.warning(f"[Circuit] 连接 '{id1_upper}' <--> '{id2_upper}' 不存在，无需断开。")
             return False # 返回 False 表示连接不存在

        self.connections.remove(connection)
        logger.debug(f"[Circuit] 断开了连接: {id1_upper} <--> {id2_upper}.")
        return True # 返回 True 表示连接成功断开

    def get_state_description(self) -> str:
        """生成当前电路状态的文本描述。"""
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
        """
        为给定类型的元件生成唯一的 ID。
        我维护一个类型到前缀的映射，并为每个前缀维护一个计数器，以生成如 "R1", "R2", "C1" 等 ID。
        我对输入类型进行了清理和最长匹配，以提高鲁棒性。
        """
        logger.debug(f"[Circuit] 正在为类型 '{component_type}' 生成唯一 ID...")
        type_map = {
            "resistor": "R", "电阻": "R", "capacitor": "C", "电容": "C",
            "battery": "B", "电池": "B", "voltage source": "V", "voltage": "V",
            "电压源": "V", "电压": "V", "led": "L", "发光二极管": "L", "switch": "S",
            "开关": "S", "ground": "G", "地": "G", "ic": "U", "chip": "U", "芯片": "U",
            "集成电路": "U", "inductor": "I", "电感": "I", "current source": "A",
            "电流源": "A", "diode": "D", "二极管": "D", "potentiometer": "P", "电位器": "P",
            "fuse": "F", "保险丝": "F", "header": "H", "排针": "H",
            "component": "O", "元件": "O", # 其他/未知类型使用 'O'
        }
        # 确保所有映射中的代码都在计数器字典中有初始值
        for code in type_map.values():
            if code not in self._component_counters:
                 self._component_counters[code] = 0

        cleaned_type = component_type.strip().lower() # 清理输入类型
        type_code = "O" # 默认前缀
        best_match_len = 0
        # 我采用最长匹配原则来确定类型代码，避免如 "voltage source" 被错误匹配为 "S" (source)
        for keyword, code in type_map.items():
            if keyword in cleaned_type and len(keyword) > best_match_len:
                type_code = code
                best_match_len = len(keyword)

        # 如果没有找到特定匹配且输入不是通用类型，发出警告
        if type_code == "O" and cleaned_type not in ["component", "元件"]:
             logger.warning(f"[Circuit] 未找到类型 '{component_type}' 的特定前缀，将使用通用前缀 'O'。")

        MAX_ID_ATTEMPTS = 100 # 设置尝试上限，防止因意外情况导致无限循环
        for attempt in range(MAX_ID_ATTEMPTS):
            # 递增对应类型的计数器
            self._component_counters[type_code] += 1
            # 生成 ID
            gen_id = f"{type_code}{self._component_counters[type_code]}"
            # 检查 ID 是否已存在
            if gen_id not in self.components:
                logger.debug(f"[Circuit] 生成唯一 ID: '{gen_id}' (尝试 {attempt + 1})")
                return gen_id # 找到可用 ID，返回
            logger.warning(f"[Circuit] ID '{gen_id}' 已存在，尝试下一个。")

        # 如果达到尝试上限仍未找到可用 ID，则抛出运行时错误
        raise RuntimeError(f"未能为类型 '{component_type}' (代码 '{type_code}') 生成唯一 ID ({MAX_ID_ATTEMPTS} 次尝试后)。电路中可能存在大量冲突的 ID。")

    def clear(self):
        """清空当前电路的所有元件和连接，并将所有 ID 计数器重置为 0。"""
        logger.info("[Circuit] 正在清空电路状态...")
        comp_count = len(self.components)
        conn_count = len(self.connections)
        self.components = {}
        self.connections = set()
        # 重置所有类型的 ID 计数器
        self._component_counters = {k: 0 for k in self._component_counters}
        logger.info(f"[Circuit] 电路状态已清空 (移除了 {comp_count} 个元件, {conn_count} 个连接，并重置了所有 ID 计数器)。")

# --- 工具注册装饰器 ---
def register_tool(description: str, parameters: Dict[str, Any]):
    """
    我创建了这个装饰器，用于标记 Agent 的某个方法为可调用工具。
    它接收工具的描述和参数 Schema（类 OpenAI Function Calling 格式），
    并将这些信息附加到被装饰的方法上，以便 Agent 初始化时自动发现。
    """
    def decorator(func):
        # 我将 Schema 信息存储在函数对象的自定义属性中
        func._tool_schema = {"description": description, "parameters": parameters}
        func._is_tool = True # 添加一个标记，方便识别
        # 我使用 functools.wraps 来保留原始函数的名称、文档字符串等元信息，这对于调试和文档生成很有帮助
        @functools.wraps(func)
        def wrapper(*args, kwargs):
            # 这个包装器实际上不修改原函数的行为，只是附加元数据
            return func(*args, kwargs)
        return wrapper
    return decorator


# --- 模块化组件：MemoryManager ---
class MemoryManager:
    """
    记忆管理器。我负责存储和管理 Agent 的所有记忆信息。
    这包括：短期对话历史（用于 LLM 上下文）、长期知识片段（未来可用于 RAG）
    以及核心的电路知识 (现在是一个 Circuit 对象)。
    """
    def __init__(self, max_short_term_items: int = 20, max_long_term_items: int = 50):
        logger.info("[MemoryManager] 初始化记忆模块...")
        if max_short_term_items <= 1:
            raise ValueError("max_short_term_items 必须大于 1")
        self.max_short_term_items = max_short_term_items
        self.max_long_term_items = max_long_term_items
        # 短期记忆：存储对话消息对象的列表
        self.short_term: List[Dict[str, Any]] = []
        # 长期记忆：存储知识片段字符串的列表（当前实现为简单队列）
        self.long_term: List[str] = []
        # 电路知识库：现在是 Circuit 类的实例
        self.circuit: Circuit = Circuit() # 持有一个 Circuit 对象

        logger.info(f"[MemoryManager] 记忆模块初始化完成。短期上限: {max_short_term_items} 条, 长期上限: {max_long_term_items} 条。")

    def add_to_short_term(self, message: Dict[str, Any]):
        """
        添加消息到短期记忆，并执行修剪。
        我实现了基于消息数量的短期记忆修剪。如果超出限制，我会移除最旧的非系统消息，
        以保持上下文窗口大小可控。这是一种基础策略，更精确的基于 Token 的修剪是未来的优化方向。
        """
        logger.debug(f"[MemoryManager] 添加消息到短期记忆 (Role: {message.get('role', 'N/A')}). 当前数量: {len(self.short_term)}")
        self.short_term.append(message)

        # 检查是否超出限制，并执行修剪
        current_size = len(self.short_term)
        if current_size > self.max_short_term_items:
            logger.debug(f"[MemoryManager] 短期记忆超限 ({current_size}/{self.max_short_term_items})，执行修剪...")
            items_to_remove = current_size - self.max_short_term_items
            removed_count = 0
            indices_to_remove = []

            # 我查找最旧的非系统消息（通常是 user 或 assistant 消息）进行移除
            # 系统消息（通常在索引 0）需要保留，因为它定义了 Agent 的行为
            # 同时，如果Tool执行失败导致重规划，新加入的Tool和Assistant消息也需要保留给LLM看到
            # 一个简单的策略是只移除最旧的 User/Assistant 消息，保留最新的 Tool 消息
            # 更高级的策略需要根据Token、消息类型优先级进行复杂判断
            # 当前实现：保留System消息，移除最旧的User/Assistant消息直到符合限制
            non_system_indices = [i for i, msg in enumerate(self.short_term) if msg.get("role") != "system"]
            indices_to_remove = non_system_indices[:items_to_remove] # 移除最前面的（最旧的）非系统消息

            if indices_to_remove:
                # 使用列表推导构建新列表，避免在循环中修改
                removed_roles = [self.short_term[i].get('role', 'N/A') for i in indices_to_remove]
                self.short_term = [msg for i, msg in enumerate(self.short_term) if i not in set(indices_to_remove)]
                removed_count = len(indices_to_remove)
                logger.info(f"[MemoryManager] 短期记忆修剪完成，移除了 {removed_count} 条最旧的非系统消息 (Roles: {removed_roles})。")
            else:
                 # 如果 max_short_term_items <= 1，可能无法找到非系统消息
                 logger.warning("[MemoryManager] 短期记忆超限但未能找到足够的非系统消息进行移除。请检查 max_short_term_items 设置。")


        logger.debug(f"[MemoryManager] 添加后短期记忆数量: {len(self.short_term)}")

    def add_to_long_term(self, knowledge_snippet: str):
        """添加知识片段到长期记忆。当前采用 FIFO 策略进行修剪。"""
        logger.debug(f"[MemoryManager] 添加知识到长期记忆: '{knowledge_snippet[:100]}{'...' if len(knowledge_snippet) > 100 else ''}'. 当前数量: {len(self.long_term)}")
        self.long_term.append(knowledge_snippet)
        if len(self.long_term) > self.max_long_term_items:
            removed = self.long_term.pop(0)
            logger.info(f"[MemoryManager] 长期记忆超限 ({self.max_long_term_items}), 移除最旧知识: '{removed[:50]}...'")
        logger.debug(f"[MemoryManager] 添加后长期记忆数量: {len(self.long_term)}")

    def get_circuit_state_description(self) -> str:
        """调用 Circuit 对象的方法生成当前电路状态的文本描述。"""
        return self.circuit.get_state_description()

    def get_memory_context_for_prompt(self, recent_long_term_count: int = 5) -> str:
        """
        格式化非对话历史的记忆上下文（电路状态 + 近期长期记忆）用于注入 LLM Prompt。
        短期对话历史由 Orchestrator 直接管理和传递。
        当前实现仅使用最近 N 条长期记忆，这是一个基础策略。更高级的实现应基于当前查询
        使用 RAG (Retrieval-Augmented Generation) 技术检索相关的长期记忆。
        """
        logger.debug("[MemoryManager] 正在格式化记忆上下文用于 Prompt...")
        circuit_desc = self.get_circuit_state_description()

        long_term_str = ""
        if self.long_term:
            actual_count = min(recent_long_term_count, len(self.long_term))
            if actual_count > 0:
                recent_items = self.long_term[-actual_count:]
                long_term_str = "\n\n【近期经验总结 (仅显示最近 N 条)】\n" + "\n".join(f"- {item}" for item in recent_items)
                logger.debug(f"[MemoryManager] 已提取最近 {len(recent_items)} 条长期记忆 (基础模式)。")

        long_term_str += "\n(注: 当前仅使用最近期记忆，未来版本将实现基于相关性的检索)"

        context = f"{circuit_desc}{long_term_str}".strip()
        logger.debug(f"[MemoryManager] 记忆上下文 (电路+长期) 格式化完成。")
        return context

    # MemoryManager 不再直接提供电路操作方法，而是通过 .circuit 访问
    # 例如: self.memory_manager.circuit.add_component(...)
    # 例如: self.memory_manager.circuit.generate_component_id(...)
    # 例如: self.memory_manager.circuit.clear()

# --- 模块化组件：LLMInterface ---
class LLMInterface:
    """
    封装与大语言模型 (LLM) 的异步交互。
    我负责处理与 LLM API 的通信细节，例如认证、请求构建和响应处理。
    目前我使用智谱 AI 的 SDK。
    """
    def __init__(self, api_key: str, model_name: str = "glm-4-flash-250414", default_temperature: float = 0.1, default_max_tokens: int = 4095):
        logger.info(f"[LLMInterface] 初始化 LLM 接口，目标模型: {model_name}")
        if not api_key: raise ValueError("智谱 AI API Key 不能为空")
        try:
            self.client = ZhipuAI(api_key=api_key)
            logger.info("[LLMInterface] 智谱 AI 客户端初始化成功。")
        except Exception as e:
            logger.critical(f"[LLMInterface] 初始化智谱 AI 客户端失败: {e}", exc_info=True)
            raise ConnectionError(f"初始化智谱 AI 客户端失败: {e}") from e
        self.model_name = model_name
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens
        logger.info(f"[LLMInterface] LLM 接口初始化完成 (Model: {model_name}, Temp: {default_temperature}, MaxTokens: {default_max_tokens})。")

    async def call_llm(self, messages: List[Dict[str, Any]], use_tools: bool = False, tool_choice: Optional[str] = None) -> Any:
        """
        异步调用 LLM API。
        在当前 Agent 架构中，我通常不使用 SDK 的 `tools` 参数进行规划（`use_tools=False`），
        因为规划是通过解析 LLM 输出的自定义 JSON 实现的。
        `use_tools=True` 的分支保留，可能用于未来需要 SDK 管理工具调用的场景。
        """
        call_args = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens,
            # 明确禁止 SDK 的 tool_calls 功能，强制 LLM 按 Prompt 要求输出自定义 JSON
            # 注意：不同的 LLM 可能对 system prompt 中的指令遵循度不同。
            # 通过参数强制禁用通常更可靠。
            # 但请注意，glm-4-flash-250414 通常会严格遵循prompt的格式指令。
            # "tools": None, # 确保不发送工具定义
            # "tool_choice": "none", # 确保不使用工具调用
        }

        logger.info(f"[LLMInterface] 准备异步调用 LLM ({self.model_name}，自定义 JSON/无内置工具模式)...")
        logger.debug(f"[LLMInterface] 发送的消息条数: {len(messages)}")
        # logger.debug(f"[LLMInterface] 消息列表: {messages}") # 仅在深度调试时取消注释

        try:
            start_time = time.monotonic()
            # 使用 asyncio.to_thread 包装同步 SDK 调用
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                call_args
            )
            duration = time.monotonic() - start_time
            logger.info(f"[LLMInterface] LLM 异步调用成功。耗时: {duration:.3f} 秒。")

            if response:
                if response.usage:
                    logger.info(f"[LLMInterface] Token 统计: Prompt={response.usage.prompt_tokens}, Completion={response.usage.completion_tokens}, Total={response.usage.total_tokens}")
                if response.choices:
                    finish_reason = response.choices[0].finish_reason
                    logger.info(f"[LLMInterface] 完成原因: {finish_reason}")
                    # 检查是否因达到最大 token 限制而中断，这可能影响 JSON 完整性
                    if finish_reason == 'length':
                        logger.warning("[LLMInterface] LLM 响应因达到最大 token 限制而被截断！这可能导致 JSON 格式不完整。")
                else:
                     logger.warning("[LLMInterface] LLM 响应中缺少 'choices' 字段，可能表示请求失败或响应格式异常。")
            else:
                 logger.error("[LLMInterface] LLM API 调用返回了 None！")
                 raise ConnectionError("LLM API call returned None.")

            return response
        except Exception as e:
            logger.error(f"[LLMInterface] LLM API 异步调用失败: {e}", exc_info=True)
            raise

# --- 模块化组件：OutputParser ---
class OutputParser:
    """
    负责解析 LLM 返回的响应。
    我的主要任务是从 LLM 的原始文本输出中提取结构化信息，
    特别是规划阶段的 `<think>` 块和自定义 JSON 计划，以及最终响应阶段的 `<think>` 和文本回复。
    """
    def __init__(self):
        logger.info("[OutputParser] 初始化输出解析器 (用于自定义 JSON 和文本解析)。")

    def parse_planning_response(self, response_message: Any) -> Tuple[str, Optional[Dict[str, Any]], str]:
        """
        解析第一次 LLM 调用（规划阶段）的响应。
        我需要严格遵循 `<think>...</think> JSON_OBJECT` 的格式，
        并对提取出的 JSON 对象进行结构验证。我对 JSON 的提取做了鲁棒性处理，
        尝试找到第一个 `{` 或 `[` 并匹配到对应的 `}` 或 `]`，以应对 LLM 可能在 JSON 前后添加额外文本的情况。

        Args:
            response_message: LLM 返回的 Message 对象 (Pydantic 模型或类似结构)。

        Returns:
            Tuple[str, Optional[Dict[str, Any]], str]: 思考过程、解析并验证后的 JSON 计划 (失败则为 None)、错误信息。
        """
        logger.debug("[OutputParser] 开始解析规划响应 (自定义 JSON 模式)...")
        thinking_process = "未能提取思考过程。"
        plan = None
        error_message = ""

        if response_message is None:
            error_message = "LLM 响应对象为 None。"
            logger.error(f"[OutputParser] 解析失败: {error_message}")
            return thinking_process, None, error_message

        raw_content = getattr(response_message, 'content', None)

        if not raw_content or not raw_content.strip():
            tool_calls = getattr(response_message, 'tool_calls', None)
            if tool_calls:
                 error_message = "LLM 响应内容为空，但意外地包含了 tool_calls。"
            else:
                 error_message = "LLM 响应内容为空或仅包含空白字符。"
            logger.error(f"[OutputParser] 解析失败: {error_message}")
            return thinking_process, None, error_message

        # --- 提取 <think> 块 ---
        think_match = re.search(r'<think>(.*?)</think>', raw_content, re.IGNORECASE | re.DOTALL)
        json_part_start_index = 0
        if think_match:
            thinking_process = think_match.group(1).strip()
            json_part_start_index = think_match.end()
            logger.debug("[OutputParser] 成功提取 <think> 内容。")
        else:
            thinking_process = "警告：未找到 <think> 标签，将尝试解析后续内容为 JSON。"
            logger.warning(f"[OutputParser] {thinking_process}")
            json_part_start_index = 0

        # --- 提取并解析 JSON 部分 (鲁棒性改进) ---
        potential_json_part = raw_content[json_part_start_index:].strip()
        logger.debug(f"[OutputParser] 提取出的待解析 JSON 字符串 (前 500 字符): >>>\n{potential_json_part[:500]}{'...' if len(potential_json_part) > 500 else ''}\n<<<")

        if not potential_json_part:
            error_message = "提取出的潜在 JSON 内容为空。"
            logger.error(f"[OutputParser] 解析失败: {error_message}")
            return thinking_process, None, error_message

        final_json_string = ""
        try:
            # 预处理：尝试去除常见的 Markdown 代码块标记
            json_string_to_parse = potential_json_part
            if json_string_to_parse.startswith("```json"):
                json_string_to_parse = json_string_to_parse[len("```json"):].strip()
            if json_string_to_parse.startswith("```"):
                json_string_to_parse = json_string_to_parse[len("```"):].strip()
            if json_string_to_parse.endswith("```"):
                json_string_to_parse = json_string_to_parse[:-len("```")].strip()

            # 鲁棒的 JSON 查找逻辑：通过跟踪括号层级找到准确的 JSON 边界
            json_start = -1
            json_end = -1
            brace_level = 0
            square_level = 0
            in_string = False
            string_char = ''
            possible_start = -1

            first_brace = json_string_to_parse.find('{')
            first_square = json_string_to_parse.find('[')

            if first_brace != -1 and (first_square == -1 or first_brace < first_square):
                possible_start = first_brace
            elif first_square != -1 and (first_brace == -1 or first_square < first_brace):
                 possible_start = first_square

            if possible_start == -1:
                raise json.JSONDecodeError("无法在文本中定位 JSON 对象或数组的起始。", json_string_to_parse, 0)

            json_start = possible_start
            start_char = json_string_to_parse[json_start]

            for i in range(json_start, len(json_string_to_parse)):
                char = json_string_to_parse[i]
                # 处理转义字符
                if in_string and char == string_char and (i == json_start or json_string_to_parse[i-1] != '\\'):
                    in_string = False
                elif not in_string and (char == '"' or char == "'"):
                    in_string = True
                    string_char = char
                elif not in_string: # 仅在不在字符串内部时处理括号
                    if char == '{' and start_char == '{': brace_level += 1
                    elif char == '}' and start_char == '{': brace_level -= 1
                    elif char == '[' and start_char == '[': square_level += 1
                    elif char == ']' and start_char == '[': square_level -= 1

                # 检查是否找到匹配的结束括号且所有层级归零
                if not in_string:
                    if start_char == '{' and brace_level == 0 and char == '}':
                        json_end = i + 1
                        break
                    elif start_char == '[' and square_level == 0 and char == ']':
                         json_end = i + 1
                         break

            if json_end == -1:
                raise json.JSONDecodeError("无法在文本中找到匹配的 JSON 结束符。JSON 可能不完整或格式错误。", json_string_to_parse, len(json_string_to_parse)-1)

            final_json_string = json_string_to_parse[json_start:json_end]
            logger.debug(f"[OutputParser] 精准提取的 JSON 字符串: >>>\n{final_json_string}\n<<<")

            parsed_json = json.loads(final_json_string)
            logger.debug("[OutputParser] JSON 字符串解析成功。")

            # --- 严格验证 JSON 结构 ---
            if not isinstance(parsed_json, dict): raise ValueError("解析结果不是一个 JSON 对象 (字典)。")
            if "is_tool_calls" not in parsed_json or not isinstance(parsed_json["is_tool_calls"], bool): raise ValueError("JSON 对象缺少必需的布尔字段 'is_tool_calls'。")
            tool_list = parsed_json.get("tool_list")
            if parsed_json["is_tool_calls"]:
                if not isinstance(tool_list, list): raise ValueError("当 'is_tool_calls' 为 true 时, 'tool_list' 字段必须是一个列表。")
                if not tool_list: logger.warning("[OutputParser] 验证警告: 'is_tool_calls' 为 true 但 'tool_list' 列表为空。这通常是不希望的。") # 不是错误，只是警告
                indices_set = set()
                for i, tool_item in enumerate(tool_list):
                    if not isinstance(tool_item, dict): raise ValueError(f"'tool_list' 中索引 {i} 的元素不是字典。")
                    if not tool_item.get("toolname") or not isinstance(tool_item["toolname"], str): raise ValueError(f"'tool_list' 中索引 {i} 缺少有效的 'toolname' 字符串。")
                    if "params" not in tool_item or not isinstance(tool_item["params"], dict): raise ValueError(f"'tool_list' 中索引 {i} 缺少 'params' 字典 (如果无参数，应为空对象 {{}})。")
                    if not tool_item.get("index") or not isinstance(tool_item["index"], int) or tool_item["index"] <= 0: raise ValueError(f"'tool_list' 中索引 {i} 缺少有效正整数 'index'。")
                    if tool_item['index'] in indices_set: raise ValueError(f"'tool_list' 中索引 {i} 的 'index' 值 {tool_item['index']} 与之前的重复。")
                    indices_set.add(tool_item['index'])
                max_index = max(indices_set) if indices_set else 0
                if len(indices_set) != max_index or set(range(1, max_index + 1)) != indices_set:
                     logger.warning(f"[OutputParser] 验证警告: 'tool_list' 中的 'index' ({sorted(list(indices_set))}) 不连续或不从 1 开始。Agent 仍会按 index 排序执行。")
            else:
                if tool_list is not None and not isinstance(tool_list, list): raise ValueError("当 'is_tool_calls' 为 false 时, 'tool_list' 字段必须是 null 或列表。")
                if isinstance(tool_list, list) and tool_list: raise ValueError("当 'is_tool_calls' 为 false 时, 'tool_list' 必须为空列表 [] 或 null。")

            direct_reply = parsed_json.get("direct_reply")
            if not parsed_json["is_tool_calls"]:
                if not isinstance(direct_reply, str) or not direct_reply.strip():
                    # 这是一个重要的验证：不调用工具时，必须提供回复
                    raise ValueError("当 'is_tool_calls' 为 false 时, 必须提供有效的非空 'direct_reply' 字符串。")
            else:
                if direct_reply is not None and not isinstance(direct_reply, str): raise ValueError("当 'is_tool_calls' 为 true 时, 'direct_reply' 字段必须是 null 或字符串。")

            plan = parsed_json
            logger.info("[OutputParser] 自定义 JSON 计划解析和验证成功！")

        except json.JSONDecodeError as json_err:
            error_message = f"解析 JSON 失败: {json_err}。请检查 LLM 输出的 JSON 部分是否符合标准。Raw JSON string (截断): '{potential_json_part[:200]}...'"
            logger.error(f"[OutputParser] JSON 解析失败: {error_message}")
        except ValueError as validation_err:
            error_message = f"JSON 结构验证失败: {validation_err}。"
            logger.error(f"[OutputParser] JSON 结构验证失败: {error_message} JSON content (可能不完整): {final_json_string if final_json_string else potential_json_part[:200]}")
        except Exception as e:
            error_message = f"解析规划响应时发生未知错误: {e}"
            logger.error(f"[OutputParser] 解析时未知错误: {error_message}", exc_info=True)

        return thinking_process, plan, error_message

    def _parse_llm_text_content(self, text_content: str) -> Tuple[str, str]:
        """
        从 LLM 的最终文本响应中解析思考过程 (<think>...</think>) 和正式回复。
        这个方法比较简单，主要用于处理第二次 LLM 调用的输出。
        """
        logger.debug("[OutputParser._parse_llm_text_content] 正在解析最终文本内容...")
        if not text_content: return "思考过程为空。", "回复内容为空。"

        thinking_process = "未能提取思考过程。"
        formal_reply = text_content.strip()

        think_match = re.search(r'<think>(.*?)</think>', text_content, re.IGNORECASE | re.DOTALL)
        if think_match:
            thinking_process = think_match.group(1).strip()
            formal_reply = text_content[think_match.end():].strip()
            content_before_think = text_content[:think_match.start()].strip()
            if content_before_think:
                logger.warning(f"[OutputParser._parse_llm_text_content] 在 <think> 标签之前检测到非空白内容: '{content_before_think[:50]}...'。这部分内容已被忽略。")
        else:
            logger.warning("[OutputParser._parse_llm_text_content] 未找到 <think>...</think> 标签。将整个内容视为正式回复。")
            thinking_process = "未能提取思考过程 - LLM 可能未按预期包含<think>标签。"

        thinking_process = thinking_process if thinking_process else "提取的思考过程为空白。"
        formal_reply = formal_reply if formal_reply else "LLM 未生成最终报告内容。"

        logger.debug(f"[OutputParser._parse_llm_text_content] 解析结果 - 思考长度: {len(thinking_process)}, 回复长度: {len(formal_reply)}")
        return thinking_process, formal_reply

# --- 模块化组件：ToolExecutor ---
class ToolExecutor:
    """
    负责执行 Agent 的内部工具 (Action)。
    我接收一个按顺序排列的模拟工具调用列表（由 Orchestrator 根据 LLM 的 JSON 计划生成），
    然后异步地、按顺序地执行它们。
    本次增强了工具级别的重试机制。如果一个工具执行失败，我会根据配置重试多次。
    一个关键设计是：如果一个工具即使在重试后也最终执行失败（其 Action 方法返回 `status != 'success'`），
    我会立即停止执行本次计划中后续剩余的工具（提前中止），并将所有已执行（或失败后终止）的结果返回。
    """
    def __init__(self, agent_instance: 'CircuitDesignAgentV7', max_tool_retries: int = 2, tool_retry_delay_seconds: float = 1.0):
        logger.info("[ToolExecutor] 初始化工具执行器 (支持异步, 重试, 失败中止)。")
        if not isinstance(agent_instance, CircuitDesignAgentV7):
            raise TypeError("ToolExecutor 需要一个 CircuitDesignAgentV7 实例。")
        self.agent_instance = agent_instance
        if not hasattr(agent_instance, 'memory_manager') or not isinstance(agent_instance.memory_manager, MemoryManager):
            raise TypeError("Agent 实例缺少有效的 MemoryManager。")
        # self.memory_manager = agent_instance.memory_manager # 可以存储引用，如果需要直接访问

        # 配置工具执行的重试机制
        self.max_tool_retries = max(0, max_tool_retries) # 每个工具最多重试次数 (0 表示不重试)
        self.tool_retry_delay_seconds = max(0.1, tool_retry_delay_seconds) # 重试之间的等待时间
        logger.info(f"[ToolExecutor] 工具执行配置: 每个工具最多重试 {self.max_tool_retries} 次，重试间隔 {self.tool_retry_delay_seconds} 秒。")


    async def execute_tool_calls(self, mock_tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        按顺序异步协调执行列表中的所有工具调用。
        如果一个工具执行失败，会根据配置进行重试。如果重试后仍失败，则中止后续工具的执行。

        Args:
            mock_tool_calls: 模拟的 ToolCall 对象列表，每个包含 'id', 'function' {'name', 'arguments'}。
                             'arguments' 是一个 JSON 字符串。

        Returns:
            包含实际执行了的工具结果的列表。每个结果项包含 'tool_call_id' 和 'result' 字典。
            'result' 字典应包含 'status' 和 'message' 字段。
        """
        logger.info(f"[ToolExecutor] 准备异步执行最多 {len(mock_tool_calls)} 个工具调用 (按顺序，支持重试，失败中止)...")
        execution_results = [] # 存储每个已执行工具的结果

        if not mock_tool_calls:
            logger.info("[ToolExecutor] 没有工具需要执行。")
            return []

        total_tools = len(mock_tool_calls)

        for i, mock_call in enumerate(mock_tool_calls):
            current_tool_index = i + 1
            function_name = "unknown_function"
            tool_call_id = mock_call.get('id', f'mock_id_{i}')
            action_result = None
            arguments = {}
            tool_display_name = "未知工具"
            tool_succeeded_after_retries = False # 标志当前工具是否最终成功

            # --- 1. 解析模拟 ToolCall 对象结构 ---
            try:
                func_info = mock_call.get('function')
                if not isinstance(func_info, dict) or 'name' not in func_info or 'arguments' not in func_info:
                     err_msg = f"模拟 ToolCall 对象结构无效。缺少 'function' 或其 'name'/'arguments'。对象: {mock_call}"
                     logger.error(f"[ToolExecutor] {err_msg}")
                     action_result = {"status": "failure", "message": "错误: 内部工具调用结构无效。", "error": {"type": "MalformedMockCall", "details": err_msg}}
                     execution_results.append({"tool_call_id": tool_call_id, "result": action_result})
                     await async_print(f"  ❌ [{current_tool_index}/{total_tools}] 内部错误: 工具调用结构无效。已中止后续。")
                     break # 结构错误是致命的，中止整个计划

                function_name = func_info['name']
                function_args_str = func_info['arguments']
                tool_display_name = function_name.replace('_tool', '').replace('_', ' ').title()
                logger.info(f"[ToolExecutor] 处理工具调用 {current_tool_index}/{total_tools}: Name='{function_name}', MockID='{tool_call_id}'")
                logger.debug(f"[ToolExecutor] 参数 JSON 字符串: '{function_args_str}'")

                await async_print(f"  [{current_tool_index}/{total_tools}] 准备执行: {tool_display_name}...")

                # --- 2. 解析参数 JSON 字符串 (在重试循环外执行，因为参数解析只发生一次) ---
                try:
                    arguments = json.loads(function_args_str) if function_args_str else {}
                    if not isinstance(arguments, dict):
                         raise TypeError("参数必须是 JSON 对象 (字典)")
                    logger.debug(f"[ToolExecutor] 参数解析成功: {arguments}")
                except (json.JSONDecodeError, TypeError) as json_err:
                    err_msg = f"工具 '{function_name}' 的参数 JSON 解析失败: {json_err}. Raw: '{function_args_str}'"
                    logger.error(f"[ToolExecutor] 参数解析错误: {err_msg}", exc_info=True)
                    action_result = {"status": "failure", "message": f"错误: 工具 '{function_name}' 的参数格式错误。", "error": {"type": "ArgumentParsing", "details": err_msg}}
                    await async_print(f"  ❌ [{current_tool_index}/{total_tools}] 操作失败: {tool_display_name}. 错误: 参数解析失败。已中止后续。")
                    execution_results.append({"tool_call_id": tool_call_id, "result": action_result})
                    break # 参数解析失败是致命的，中止整个计划

                # --- 3. 查找对应的 Action 方法 (也在重试循环外执行) ---
                tool_action_method = getattr(self.agent_instance, function_name, None)
                if not callable(tool_action_method):
                    err_msg = f"Agent 未实现名为 '{function_name}' 的工具方法。"
                    logger.error(f"[ToolExecutor] 工具未实现: {err_msg}")
                    action_result = {"status": "failure", "message": f"错误: {err_msg}", "error": {"type": "NotImplemented", "details": f"Action method '{function_name}' not found."}}
                    await async_print(f"  ❌ [{current_tool_index}/{total_tools}] 操作失败: {tool_display_name}. 错误: 工具未实现。已中止后续。")
                    execution_results.append({"tool_call_id": tool_call_id, "result": action_result})
                    break # 工具方法不存在是致命的，中止整个计划


                # --- 4. 执行 Action 方法 (带重试循环) ---
                for retry_attempt in range(self.max_tool_retries + 1): # 总尝试次数 = 1 (首次) + max_retries
                    if retry_attempt > 0:
                        logger.warning(f"[ToolExecutor] 工具 '{function_name}' 执行失败，正在进行第 {retry_attempt}/{self.max_tool_retries} 次重试...")
                        await async_print(f"  🔄 [{current_tool_index}/{total_tools}] 操作 '{tool_display_name}' 失败，等待 {self.tool_retry_delay_seconds} 秒后重试...")
                        await asyncio.sleep(self.tool_retry_delay_seconds) # 等待一段时间再重试
                        await async_print(f"  🔄 [{current_tool_index}/{total_tools}] 正在进行第 {retry_attempt} 次重试...")

                    logger.debug(f"[ToolExecutor] >>> 正在调用 Action 方法: '{function_name}' (Attempt {retry_attempt + 1})")
                    try:
                        # Action 方法现在也是异步友好的，理论上可以直接 await，但为了兼容性，
                        # 如果 Action 本身不是 async，仍使用 to_thread。
                        # 更好的做法是强制 Action 必须是 async def。
                        # 这里假设 Action 是同步方法，用 to_thread 包装。
                        action_result = await asyncio.to_thread(tool_action_method, arguments=arguments)

                        # 严格检查 Action 方法的返回结构
                        if not isinstance(action_result, dict) or 'status' not in action_result or 'message' not in action_result:
                            err_msg = f"Action '{function_name}' 返回的结构无效 (缺少 'status' 或 'message'): {str(action_result)[:200]}... 将强制标记为失败。"
                            logger.error(f"[ToolExecutor] Action 返回结构错误 (Attempt {retry_attempt + 1}): {err_msg}")
                            action_result = {"status": "failure", "message": f"错误: 工具 '{function_name}' 返回结果结构无效。", "error": {"type": "InvalidActionResult", "details": err_msg}}
                        else:
                             logger.info(f"[ToolExecutor] Action '{function_name}' 执行完毕 (Attempt {retry_attempt + 1})。状态: {action_result.get('status', 'N/A')}")

                        # 检查本次尝试是否成功
                        if action_result.get("status") == "success":
                            tool_succeeded_after_retries = True # 标记当前工具最终成功
                            break # 工具执行成功，跳出重试循环

                        # 如果本次尝试失败，但还有重试机会，继续重试循环
                        if retry_attempt < self.max_tool_retries:
                             logger.warning(f"[ToolExecutor] Action '{function_name}' 执行失败 (Attempt {retry_attempt + 1})。")
                        else:
                             # 所有重试都失败了
                             logger.error(f"[ToolExecutor] Action '{function_name}' 在所有 {self.max_tool_retries + 1} 次尝试后仍失败。")

                    except TypeError as te:
                        # 捕获调用 Action 方法时因参数不匹配导致的 TypeError
                        err_msg = f"调用 Action '{function_name}' 时参数不匹配 (Attempt {retry_attempt + 1}): {te}. 传入参数: {arguments}"
                        logger.error(f"[ToolExecutor] Action 调用参数错误: {err_msg}", exc_info=True)
                        action_result = {"status": "failure", "message": f"错误: 调用工具 '{function_name}' 时参数错误。", "error": {"type": "ArgumentMismatch", "details": err_msg}}
                        # 参数错误通常是规划问题，重试意义不大，但为了逻辑一致性，还是走完重试次数
                        if retry_attempt == self.max_tool_retries: break # 最后一次尝试失败，跳出重试

                    except Exception as exec_err:
                        # 捕获 Action 方法在执行过程中抛出的其他所有未预料到的异常
                        err_msg = f"Action '{function_name}' 执行期间发生意外错误 (Attempt {retry_attempt + 1}): {exec_err}"
                        logger.error(f"[ToolExecutor] Action 执行内部错误: {err_msg}", exc_info=True)
                        action_result = {"status": "failure", "message": f"错误: 执行工具 '{function_name}' 时发生内部错误。", "error": {"type": "ExecutionError", "details": str(exec_err)}}
                        # 意外错误，也走完重试次数
                        if retry_attempt == self.max_tool_retries: break # 最后一次尝试失败，跳出重试

                # --- 重试循环结束 ---

                # 确保 action_result 不为 None (理论上所有代码路径都应在重试结束后赋值)
                if action_result is None:
                     logger.error(f"[ToolExecutor] 内部逻辑错误: 工具 '{function_name}' (Mock ID: {tool_call_id}) 未在重试后生成任何结果。标记为失败。")
                     action_result = {"status": "failure", "message": f"错误: 工具 '{function_name}' 未返回结果。", "error": {"type": "MissingResult", "details": "Execution pipeline failed to produce a result."}}

                # 记录当前工具（可能经过重试）的最终结果
                execution_results.append({"tool_call_id": tool_call_id, "result": action_result})
                logger.debug(f"[ToolExecutor] 已记录工具 '{tool_call_id}' 的执行结果 (最终状态: {action_result.get('status')}).")

                # 根据当前工具的最终执行状态，决定是否中止后续工具执行
                status_icon = "✅" if action_result.get("status") == "success" else "❌"
                msg_preview = action_result.get('message', '无消息')[:80] + ('...' if len(action_result.get('message', '')) > 80 else '')
                await async_print(f"  {status_icon} [{current_tool_index}/{total_tools}] 操作完成: {tool_display_name}. 结果: {msg_preview}")

                if not tool_succeeded_after_retries: # 如果当前工具最终失败
                    logger.warning(f"[ToolExecutor] 工具 '{function_name}' (Mock ID: {tool_call_id}) 在所有重试后仍然失败。中止本次计划中后续工具的执行。")
                    await async_print(f"  ⚠️ 由于工具 '{tool_display_name}' 在重试后仍然失败，本次计划中的后续操作已中止。")
                    break # 跳出外层 for 循环，不再处理剩余工具

            except Exception as outer_err:
                 # 捕获处理单个工具调用过程中的顶层意外错误（例如在解析 mock_call 结构之后、执行 Action 之前/之间）
                 err_msg = f"处理工具调用 '{function_name}' (Mock ID: {tool_call_id}) 时发生顶层意外错误: {outer_err}"
                 logger.error(f"[ToolExecutor] 处理工具调用时顶层错误: {err_msg}", exc_info=True)
                 action_result = {"status": "failure", "message": f"错误: 处理工具 '{function_name}' 时发生未知内部错误。", "error": {"type": "Unexpected", "details": str(outer_err)}}
                 execution_results.append({"tool_call_id": tool_call_id, "result": action_result})
                 await async_print(f"  ❌ [{current_tool_index}/{total_tools}] 操作失败: {tool_display_name or function_name}. 错误: 未知内部错误。已中止后续。")
                 break # 顶层错误，中止整个计划


        total_executed = len(execution_results)
        logger.info(f"[ToolExecutor] 所有 {total_executed}/{total_tools} 个工具调用处理完毕 (可能因失败提前中止)。")
        return execution_results

# --- Agent 核心类 (Orchestrator) ---
class CircuitDesignAgentV7:
    """
    电路设计 Agent V7.1 - 异步协调器，使用装饰器注册工具，增强重试与重规划。
    我是系统的核心控制器，负责编排整个 Agent 的工作流程：
    接收用户请求 -> 更新记忆 -> 调用 LLM 进行规划 -> (如果需要)执行工具 (带重试) ->
    观察工具结果 (带失败中止) -> 如果工具执行失败，则重规划 -> 再次调用 LLM 生成响应 -> 返回结果给用户。
    我利用 `asyncio` 实现异步操作，通过 `@register_tool` 动态管理可用工具，并协调增强的 `ToolExecutor` 和 LLM 调用。
    """
    def __init__(self, api_key: str, model_name: str = "glm-4-flash-250414",
                 max_short_term_items: int = 25, max_long_term_items: int = 50,
                 planning_llm_retries: int = 1, max_tool_retries: int = 2,
                 tool_retry_delay_seconds: float = 1.0, max_replanning_attempts: int = 2):
        logger.info(f"\n{'='*30} Agent V7.1 初始化开始 (Async, Decorator Tools, Enhanced) {'='*30}")
        logger.info("[Agent Init] 正在启动电路设计助理 V7.1...")

        try:
            self.memory_manager = MemoryManager(max_short_term_items, max_long_term_items)
            self.llm_interface = LLMInterface(api_key=api_key, model_name=model_name)
            self.output_parser = OutputParser()
            # 初始化 ToolExecutor 时传入重试参数
            self.tool_executor = ToolExecutor(
                agent_instance=self,
                max_tool_retries=max_tool_retries,
                tool_retry_delay_seconds=tool_retry_delay_seconds
            )
        except (ValueError, ConnectionError, TypeError) as e:
            logger.critical(f"[Agent Init] 核心模块初始化失败: {e}", exc_info=True)
            sys.stderr.write(f"\n🔴 Agent 核心模块初始化失败: {e}\n请检查配置或依赖！程序无法启动。\n")
            sys.stderr.flush()
            sys.exit(1)

        # 配置 Agent 整体流程的重试和重规划参数
        self.planning_llm_retries = max(0, planning_llm_retries)
        self.max_replanning_attempts = max(0, max_replanning_attempts)
        logger.info(f"[Agent Init] 规划 LLM 调用失败时将重试 {self.planning_llm_retries} 次。")
        logger.info(f"[Agent Init] 工具执行失败后，最多允许重规划 {self.max_replanning_attempts} 次。")


        # --- 动态发现并注册工具 ---
        self.tools_registry: Dict[str, Dict[str, Any]] = {}
        logger.info("[Agent Init] 正在动态发现并注册已标记的工具...")
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, '_is_tool') and method._is_tool:
                schema = getattr(method, '_tool_schema', None)
                if schema and isinstance(schema, dict):
                    if 'description' in schema and 'parameters' in schema:
                        self.tools_registry[name] = schema
                        logger.info(f"[Agent Init] ✓ 已注册工具: '{name}'")
                    else:
                        logger.warning(f"[Agent Init] 发现工具 '{name}' 但其 Schema 结构不完整，已跳过。Schema: {schema}")
                else:
                    logger.warning(f"[Agent Init] 发现工具标记 '{name}' 但未能获取有效的 Schema，已跳过。")

        if not self.tools_registry:
            logger.warning("[Agent Init] 未发现任何通过 @register_tool 注册的工具！Agent 将无法执行任何工具操作。")
        else:
            logger.info(f"[Agent Init] 共发现并注册了 {len(self.tools_registry)} 个工具。")
            logger.debug(f"[Agent Init] 工具注册表详情:\n{json.dumps(self.tools_registry, indent=2, ensure_ascii=False)}")

        logger.info(f"\n{'='*30} Agent V7.1 初始化成功 {'='*30}\n")
        print("我是电路设计编程助理 V7.1！")
        print("已准备好接收指令。采用异步核心，增强重试和重规划机制。")
        print("-" * 70)
        sys.stdout.flush()


    # --- Action Implementations (Decorated & Standardized Output) ---
    # 下面是我定义的 Agent 可以执行的具体操作（Action）。
    # 每个方法都使用 `@register_tool` 装饰器来声明其功能和参数。
    # 这些方法目前是同步的（由 ToolExecutor 放入线程池执行），
    # 并且必须返回一个包含 `status` 和 `message` 键的字典。

    @register_tool(
        description="添加一个新的电路元件 (如电阻, 电容, 电池, LED, 开关, 芯片, 地线等)。如果用户未指定 ID，我会自动生成。元件值是可选的。",
        parameters={
            "type": "object",
            "properties": {
                "component_type": {"type": "string", "description": "元件的类型 (例如: '电阻', 'LED', '9V 电池')."},
                "component_id": {"type": "string", "description": "可选的用户指定 ID。如果省略会自动生成。请勿臆造不存在的 ID。"},
                "value": {"type": "string", "description": "可选的元件值 (例如: '1k', '10uF', '9V'). 如果未指定则省略。"}
            },
            "required": ["component_type"]
        }
    )
    def add_component_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Action 实现：添加元件。
        我负责处理参数验证、ID 生成（如果用户未提供或提供无效 ID）、
        创建 `CircuitComponent` 对象，并将其添加到 `MemoryManager` 持有的 `Circuit` 对象中。
        同时，我也会将此操作记录到长期记忆。
        """
        logger.info("[Action: AddComponent] 执行添加元件操作。")
        logger.debug(f"[Action: AddComponent] 收到参数: {arguments}")
        component_type = arguments.get("component_type")
        component_id_req = arguments.get("component_id")
        value = arguments.get("value")
        logger.info(f"[Action: AddComponent] 参数解析: Type='{component_type}', Requested ID='{component_id_req}', Value='{value}'")

        if not component_type or not isinstance(component_type, str) or not component_type.strip():
            msg="元件类型是必需的，并且必须是有效的字符串。"
            logger.error(f"[Action: AddComponent] 输入验证失败: {msg}")
            return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "InvalidInput", "details": msg}}

        target_id = None
        id_was_generated = False
        user_provided_id_validated = None

        # --- ID 处理逻辑 ---
        if component_id_req and isinstance(component_id_req, str) and component_id_req.strip():
            user_provided_id = component_id_req.strip().upper()
            if re.match(r'^[a-zA-Z0-9_][a-zA-Z0-9_-]*$', user_provided_id):
                # 检查 ID 是否已存在于电路中（通过 Circuit 对象检查）
                if user_provided_id in self.memory_manager.circuit.components:
                    msg=f"元件 ID '{user_provided_id}' 已被占用，请选择其他 ID。"
                    logger.error(f"[Action: AddComponent] ID 冲突: {msg}")
                    return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "IDConflict", "details": msg}}
                else:
                    target_id = user_provided_id
                    user_provided_id_validated = target_id
                    logger.debug(f"[Action: AddComponent] 验证通过，将使用用户提供的 ID: '{target_id}'.")
            else:
                logger.warning(f"[Action: AddComponent] 用户提供的 ID '{component_id_req}' 格式无效，将自动生成 ID。")

        if target_id is None:
            try:
                # 调用 Circuit 对象的方法生成 ID
                target_id = self.memory_manager.circuit.generate_component_id(component_type)
                id_was_generated = True
                logger.debug(f"[Action: AddComponent] 已自动生成 ID: '{target_id}'.")
            except RuntimeError as e:
                msg=f"无法自动为类型 '{component_type}' 生成唯一 ID: {e}"
                logger.error(f"[Action: AddComponent] ID 生成失败: {msg}", exc_info=True)
                return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "IDGenerationFailed", "details": str(e)}}

        processed_value = str(value).strip() if value is not None and str(value).strip() else None

        # --- 创建并存储元件对象 ---
        try:
            if target_id is None: raise ValueError("内部错误：未能最终确定元件 ID。") # 防御性检查

            new_component = CircuitComponent(target_id, component_type, processed_value)
            # 将新元件添加到 Circuit 对象中
            self.memory_manager.circuit.add_component(new_component)
            logger.info(f"[Action: AddComponent] 成功添加元件 '{new_component.id}' 到电路。")

            success_message = f"操作成功: 已添加元件 {str(new_component)}。"
            if id_was_generated:
                success_message += f" (系统自动分配 ID '{new_component.id}')"
            elif user_provided_id_validated:
                success_message += f" (使用了您指定的 ID '{user_provided_id_validated}')"

            self.memory_manager.add_to_long_term(f"添加了元件: {str(new_component)}")

            return {
                "status": "success",
                "message": success_message,
                "data": {"id": new_component.id, "type": new_component.type, "value": new_component.value}
            }
        except ValueError as ve:
            msg=f"创建或添加元件对象时发生内部错误: {ve}"
            logger.error(f"[Action: AddComponent] 元件创建/添加错误: {msg}", exc_info=True)
            return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "ComponentOperationError", "details": str(ve)}}
        except Exception as e:
            msg=f"添加元件时发生未知的内部错误: {e}"
            logger.error(f"[Action: AddComponent] 未知错误: {msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 添加元件时发生未知内部错误。", "error": {"type": "Unexpected", "details": str(e)}}

    @register_tool(
        description="使用两个已存在元件的 ID 将它们连接起来。执行前我会检查元件是否存在。",
        parameters={
            "type": "object",
            "properties": {
                "comp1_id": {"type": "string", "description": "第一个元件的 ID (通常大写)。"},
                "comp2_id": {"type": "string", "description": "第二个元件的 ID (通常大写)。"}
            },
            "required": ["comp1_id", "comp2_id"]
        }
    )
    def connect_components_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Action 实现：连接两个元件。
        我调用 `MemoryManager` 持有的 `Circuit` 对象的方法来执行连接。
        """
        logger.info("[Action: ConnectComponents] 执行连接元件操作。")
        logger.debug(f"[Action: ConnectComponents] 收到参数: {arguments}")
        comp1_id_req = arguments.get("comp1_id")
        comp2_id_req = arguments.get("comp2_id")
        logger.info(f"[Action: ConnectComponents] 参数解析: Comp1='{comp1_id_req}', Comp2='{comp2_id_req}'")

        if not comp1_id_req or not isinstance(comp1_id_req, str) or not comp1_id_req.strip() or \
           not comp2_id_req or not isinstance(comp2_id_req, str) or not comp2_id_req.strip():
            msg="必须提供两个有效的、非空的元件 ID 字符串才能进行连接。"
            logger.error(f"[Action: ConnectComponents] 输入验证失败: {msg}")
            return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "InvalidInput", "details": msg}}

        id1 = comp1_id_req.strip().upper()
        id2 = comp2_id_req.strip().upper()

        try:
            # 调用 Circuit 对象的方法进行连接
            success = self.memory_manager.circuit.connect_components(id1, id2)

            if success:
                logger.info(f"[Action: ConnectComponents] 成功添加连接: {id1} <--> {id2}")
                self.memory_manager.add_to_long_term(f"连接了元件: {id1} <--> {id2}")
                success_message = f"操作成功: 已将元件 '{id1}' 与 '{id2}' 连接起来。"
                return {"status": "success", "message": success_message, "data": {"connection": sorted((id1, id2))}}
            else:
                # connect_components 返回 False 表示连接已存在
                msg = f"元件 '{id1}' 和 '{id2}' 之间已经存在连接。"
                logger.info(f"[Action: ConnectComponents] 连接已存在: {msg}")
                # 返回成功状态，但附带信息说明连接已存在
                return {"status": "success", "message": f"注意: {msg}", "data": {"connection": sorted((id1, id2))}}

        except ValueError as ve:
            # Circuit 的 connect_components 会抛出 ValueError 表示元件不存在或自连接
            msg=f"连接元件时验证失败: {ve}"
            logger.error(f"[Action: ConnectComponents] 连接验证错误: {msg}", exc_info=True)
            # 根据 Circuit 抛出的 ValueError 内容判断是哪个具体的错误类型
            error_type = "CircuitValidationError"
            if "不存在" in str(ve): error_type = "ComponentNotFound"
            elif "连接到它自己" in str(ve): error_type = "SelfConnection"
            return {"status": "failure", "message": f"错误: {msg}", "error": {"type": error_type, "details": str(ve)}}
        except Exception as e:
            msg=f"连接元件时发生未知的内部错误: {e}"
            logger.error(f"[Action: ConnectComponents] 未知错误: {msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 连接元件时发生未知内部错误。", "error": {"type": "Unexpected", "details": str(e)}}

    @register_tool(
        description="获取当前电路的详细描述，包括所有已添加的元件及其值（如果有）和所有连接。",
        parameters={"type": "object", "properties": {}}
    )
    def describe_circuit_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Action 实现：描述当前电路。
        我调用 `MemoryManager` 持有的 `Circuit` 对象的方法来获取描述。
        """
        logger.info("[Action: DescribeCircuit] 执行描述电路操作。")
        logger.debug(f"[Action: DescribeCircuit] 收到参数: {arguments} (应为空)")

        try:
            # 调用 Circuit 对象的方法获取描述
            description = self.memory_manager.circuit.get_state_description()
            logger.info("[Action: DescribeCircuit] 成功生成电路描述。")
            return {"status": "success", "message": "已成功获取当前电路的描述。", "data": {"description": description}}
        except Exception as e:
            msg=f"生成电路描述时发生意外的内部错误: {e}"
            logger.error(f"[Action: DescribeCircuit] 未知错误: {msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 获取电路描述时发生未知错误。", "error": {"type": "Unexpected", "details": str(e)}}

    @register_tool(
        description="彻底清空当前的电路设计，移除所有已添加的元件和它们之间的连接，并重置所有 ID 计数器。",
        parameters={"type": "object", "properties": {}}
    )
    def clear_circuit_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Action 实现：清空电路。
        我调用 `MemoryManager` 持有的 `Circuit` 对象的方法来执行实际的清空操作。
        """
        logger.info("[Action: ClearCircuit] 执行清空电路操作。")
        logger.debug(f"[Action: ClearCircuit] 收到参数: {arguments} (应为空)")

        try:
            # 调用 Circuit 对象的方法执行清空
            self.memory_manager.circuit.clear()
            logger.info("[Action: ClearCircuit] 电路状态已成功清空。")
            self.memory_manager.add_to_long_term("执行了清空电路操作。")
            success_message = "操作成功: 当前电路已彻底清空。所有元件、连接和 ID 计数器均已重置。"
            return {"status": "success", "message": success_message}
        except Exception as e:
            msg=f"清空电路时发生意外的内部错误: {e}"
            logger.error(f"[Action: ClearCircuit] 未知错误: {msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 清空电路时发生未知错误。", "error": {"type": "Unexpected", "details": str(e)}}

    # 可以根据需要添加其他 Action 方法，例如移除元件、断开连接等

    # --- Orchestration Layer Method ---
    async def process_user_request(self, user_request: str) -> str:
        """
        处理用户请求的核心异步流程 (Agentic Loop)。
        我负责协调整个过程，包括规划失败后的重规划循环：
        接收用户请求 -> (如果不是重规划) 更新记忆 (用户输入) ->
        [开始规划/重规划循环]
            调用 LLM 进行规划 (带重试，提供当前记忆和工具结果) ->
            解析 LLM 规划 ->
            (如果规划成功) 执行工具 (带重试，失败中止) ->
            观察工具结果 ->
            如果工具执行失败且未达重规划上限，则继续循环到规划阶段 (带失败信息)
        [结束规划/重规划循环]
        如果规划或执行最终失败，生成错误报告；否则，调用 LLM 生成最终响应 -> 返回结果。
        """
        request_start_time = time.monotonic()
        logger.info(f"\n{'='*25} V7.1 开始处理用户请求 {'='*25}")
        logger.info(f"[Orchestrator] 收到用户指令: \"{user_request}\"")

        if not user_request or user_request.isspace():
            logger.info("[Orchestrator] 用户指令为空或仅包含空白。")
            await async_print("\n您的指令似乎是空的，请重新输入！")
            return "<think>用户输入为空或空白，无需处理。</think>\n\n请输入您的指令！"

        # --- 0. 将用户请求添加到短期记忆 (仅在首次处理新请求时添加) ---
        # 在重规划循环内部，我们不重复添加用户请求，只添加LLM规划和工具结果
        try:
            # 在进入重规划循环前添加用户请求
            self.memory_manager.add_to_short_term({"role": "user", "content": user_request})
            logger.info("[Orchestrator] 用户指令已记录并添加到短期记忆。")
        except Exception as e:
            logger.error(f"[Orchestrator] 添加用户消息到短期记忆时出错: {e}", exc_info=True)
            await async_print(f"\n🔴 抱歉，我在记录您的指令时遇到了内部问题 ({e})！请稍后重试。")
            return f"<think>添加用户消息到短期记忆失败: {e}</think>\n\n抱歉，我在处理您的指令时遇到了内部记忆错误，请稍后再试。"

        # --- 规划与行动的重规划循环 ---
        replanning_count = 0 # 初始化重规划计数器
        plan_dict = None # 最终成功解析的计划
        tool_execution_results = [] # 最后一次工具执行的结果

        while replanning_count <= self.max_replanning_attempts:
            logger.info(f"\n--- [规划/重规划阶段] 尝试第 {replanning_count + 1}/{self.max_replanning_attempts + 1} 次规划 ---")
            if replanning_count > 0:
                 await async_print(f"--- 由于之前的操作失败，正在尝试第 {replanning_count}/{self.max_replanning_attempts} 次重规划... ---")
                 # 在重规划尝试中，需要明确告知 LLM 这是重试，并且提供上一次工具执行的结果作为上下文
                 # 可以通过在消息列表中加入一个特殊的 system message 来实现，
                 # 或者依赖于 short_term 中已经包含的 tool messages。
                 # 考虑到 short_term 已经包含了 tool messages，修改 system prompt 更明确。
                 planning_attempt_type = "re-planning" # 标记当前是重规划尝试
            else:
                 await async_print("--- 正在请求智能大脑分析指令并生成执行计划 (JSON)... ---")
                 planning_attempt_type = "initial-planning" # 标记当前是首次规划

            # 准备传递给 LLM 的上下文信息
            memory_context = self.memory_manager.get_memory_context_for_prompt()
            tool_schemas_for_prompt = self._get_tool_schemas_for_prompt()

            # 构建规划阶段的 System Prompt
            # 提示词需要能够引导 LLM 理解之前的工具执行结果（通过历史消息中的 tool messages）
            # 并在失败时生成修正后的计划。
            system_prompt_planning = self._get_planning_prompt_v7(
                tool_schemas_for_prompt,
                memory_context,
                is_replanning=replanning_count > 0, # 告知 LLM 是否是重规划
                previous_results=tool_execution_results # 传递上次的工具执行结果 (仅用于提示词，实际数据在记忆中)
            )

            # 构建发送给 LLM 的完整消息列表
            # 包含 System Prompt 和短期记忆中的所有消息（包括用户请求、上次规划、上次工具结果等）
            messages_for_llm1 = [{"role": "system", "content": system_prompt_planning}] + \
                               self.memory_manager.short_term # 包含所有历史消息

            # --- LLM 规划调用与解析 (带重试) ---
            planning_llm_attempt = 0
            plan_dict = None # 重置计划结果
            thinking_process = "未能提取思考过程。" # 重置思考过程
            parser_error_msg = "" # 重置解析错误信息

            while planning_llm_attempt <= self.planning_llm_retries:
                planning_llm_attempt += 1
                log_prefix = f"[Orchestrator - {planning_attempt_type.capitalize()} Attempt {replanning_count + 1}/{self.max_replanning_attempts + 1}, LLM Call {planning_llm_attempt}/{self.planning_llm_retries + 1}]"
                logger.info(f"{log_prefix} 调用规划 LLM...")
                if planning_llm_attempt > 1:
                     await async_print(f"    (LLM 沟通尝试 {planning_llm_attempt}/{self.planning_llm_retries + 1})...")

                try:
                    first_llm_response = await self.llm_interface.call_llm(
                        messages=messages_for_llm1,
                        use_tools=False
                    )
                    logger.info(f"{log_prefix} LLM 调用完成。")

                    # --- 解析自定义 JSON 规划响应 ---
                    logger.info(f"{log_prefix} 解析 LLM 的规划响应...")
                    response_message = first_llm_response.choices[0].message
                    # 使用 OutputParser 解析
                    thinking_process, plan_dict, parser_error_msg = self.output_parser.parse_planning_response(response_message)

                    if plan_dict is not None and not parser_error_msg:
                        logger.info(f"{log_prefix} 成功解析并验证自定义 JSON 计划！")
                        # 将 LLM 的原始规划响应添加到短期记忆 (不论是否重规划)
                        try:
                            if first_llm_response and first_llm_response.choices:
                                assistant_plan_message = first_llm_response.choices[0].message
                                assistant_raw_response_for_memory = assistant_plan_message.model_dump(exclude_unset=True)
                                self.memory_manager.add_to_short_term(assistant_raw_response_for_memory)
                                logger.debug(f"{log_prefix} LLM 的原始规划响应 (Message Dump) 已添加至短期记忆。")
                        except Exception as mem_err:
                            logger.error(f"{log_prefix} 添加 LLM 规划响应到短期记忆失败: {mem_err}", exc_info=True)
                        break # 规划成功，跳出 LLM 调用重试循环
                    else:
                        logger.warning(f"{log_prefix} 解析 JSON 失败: {parser_error_msg}. 尝试重试 LLM 调用。")
                        # 如果解析或验证失败，并且还有 LLM 调用重试次数，继续内层循环
                        if planning_llm_attempt <= self.planning_llm_retries:
                            await async_print(f"    (解析大脑计划失败，尝试重新沟通...)")
                            # 失败的解析结果和思考过程会保留，下次 LLM 调用时会在历史中看到，希望 LLM 能自我修正。
                        else:
                            logger.error(f"{log_prefix} LLM 规划调用及解析在所有 {self.planning_llm_retries + 1} 次尝试后均失败。")
                            # 所有 LLM 调用重试都失败了，跳出内层循环
                            break

                except ConnectionError as conn_err:
                    logger.error(f"{log_prefix} LLM 调用失败 (连接错误): {conn_err}", exc_info=True)
                    parser_error_msg = f"LLM 调用连接错误: {conn_err}"
                    if planning_llm_attempt <= self.planning_llm_retries:
                         logger.warning(f"{log_prefix} LLM 调用失败，尝试重试...")
                         await async_print(f"    (与大脑连接失败，尝试重新连接...)")
                    else:
                         logger.critical(f"{log_prefix} LLM 调用在所有 {self.planning_llm_retries + 1} 次尝试后均因连接错误等失败。")
                         break # 所有 LLM 调用重试都失败了，跳出内层循环

                except Exception as e:
                    logger.error(f"{log_prefix} LLM 调用或解析过程中发生严重错误: {e}", exc_info=True)
                    parser_error_msg = f"LLM 调用或响应解析时发生错误: {e}"
                    if planning_llm_attempt <= self.planning_llm_retries:
                         logger.warning(f"{log_prefix} LLM 调用或解析失败，尝试重试...")
                         await async_print(f"    (大脑处理失败，尝试重新沟通...)")
                    else:
                         logger.critical(f"{log_prefix} LLM 调用及解析在所有 {self.planning_llm_retries + 1} 次尝试后均失败。")
                         break # 所有 LLM 调用重试都失败了，跳出内层循环

            # --- LLM 规划调用重试循环结束 ---

            # 检查是否成功获取了计划
            if plan_dict is None:
                logger.error(f"[Orchestrator] 规划失败 (尝试 {replanning_count + 1}/{self.max_replanning_attempts + 1})：未能成功获取有效的 JSON 计划。最终解析错误: {parser_error_msg}")
                # 如果是重规划尝试，且重规划次数已满，则跳出重规划循环
                if replanning_count >= self.max_replanning_attempts:
                     logger.critical(f"[Orchestrator] 已达最大重规划尝试次数 ({self.max_replanning_attempts + 1} 次总尝试)，仍无法获得有效计划。中止处理。")
                     break # 跳出外层重规划循环
                else:
                     # 规划失败，但还有重规划机会，记录错误信息，继续外层循环进行下一次重规划
                     logger.warning(f"[Orchestrator] 规划失败，将在下一轮尝试重规划。当前重规划次数: {replanning_count + 1}")
                     replanning_count += 1 # 增加重规划计数
                     # 这里的错误信息 (parser_error_msg) 会在 messages_for_llm1 中被 LLM 看到
                     continue # 继续外层 while 循环进行重规划

            # --- 规划成功 ---
            logger.info("[Orchestrator] 成功获取并验证自定义 JSON 计划。")
            logger.debug(f"[Orchestrator] 解析出的计划详情: {json.dumps(plan_dict, indent=2, ensure_ascii=False)}")

            # --- 决策：根据计划执行工具或直接回复 ---
            is_tool_calls = plan_dict.get("is_tool_calls", False)
            tool_list_from_plan = plan_dict.get("tool_list")
            direct_reply_from_plan = plan_dict.get("direct_reply")

            if is_tool_calls:
                # --- 情况 A: 需要执行工具 ---
                logger.info("[Orchestrator] 决策：根据 JSON 计划执行工具。")

                # 再次验证 tool_list 是否有效 (防御性编程)
                if not isinstance(tool_list_from_plan, list) or not tool_list_from_plan:
                     err_msg = "'is_tool_calls' 为 true 但 'tool_list' 不是有效的非空列表！"
                     logger.error(f"[Orchestrator] 规划错误: {err_msg}")
                     # 生成一个工具执行失败的模拟结果，添加到 results 中以便 LLM 看到
                     tool_execution_results = [{"tool_call_id": "planning_error", "result": {"status": "failure", "message": f"错误: 计划要求调用工具，但工具列表无效或为空。", "error": {"type": "MalformedPlan", "details": err_msg}}}]
                     # 将这个失败结果添加到记忆
                     try: self.memory_manager.add_to_short_term({"role": "tool", "tool_call_id": "planning_error", "content": json.dumps(tool_execution_results[0]['result'], default=str)})
                     except Exception as mem_err: logger.error(f"[Orchestrator] 添加规划错误工具结果到记忆失败: {mem_err}")

                     # 检查是否可以重规划
                     if replanning_count >= self.max_replanning_attempts:
                         logger.critical(f"[Orchestrator] 已达最大重规划尝试次数 ({self.max_replanning_attempts + 1} 次总尝试)，计划仍然无效。中止处理。")
                         break # 跳出外层重规划循环
                     else:
                         logger.warning(f"[Orchestrator] 计划无效，将在下一轮尝试重规划。当前重规划次数: {replanning_count + 1}")
                         replanning_count += 1 # 增加重规划计数
                         continue # 继续外层 while 循环进行重规划

                # --- 将自定义工具列表转换为模拟 ToolCall 列表 ---
                mock_tool_calls_for_executor = []
                conversion_successful = True
                for tool_item in tool_list_from_plan:
                    tool_name = tool_item.get("toolname")
                    params_dict = tool_item.get("params", {})
                    index = tool_item.get("index")
                    params_hash = hash(json.dumps(params_dict, sort_keys=True)) & 0xffff
                    mock_id = f"call_{index}_{tool_name[:8]}_{params_hash:x}"

                    try: params_str = json.dumps(params_dict)
                    except TypeError as json_dump_err:
                        logger.error(f"转换工具 {tool_name} (index {index}) 的参数字典为 JSON 字符串失败: {json_dump_err}. Params: {params_dict}", exc_info=True)
                        conversion_successful = False
                        params_str = "{}"

                    mock_call = {"id": mock_id, "type": "function", "function": {"name": tool_name, "arguments": params_str}}
                    mock_tool_calls_for_executor.append(mock_call)

                if not conversion_successful:
                     logger.warning("[Orchestrator] 注意: 转换自定义工具列表时遇到参数序列化问题。")
                logger.info(f"[Orchestrator] 成功将自定义工具列表转换为 {len(mock_tool_calls_for_executor)} 个模拟 ToolCall 对象，准备执行。")

                # --- 阶段 4: 行动执行 (调用 ToolExecutor - 异步 & 失败中止) ---
                logger.info("\n--- [行动阶段] 执行工具 ---")
                num_tools_to_run = len(mock_tool_calls_for_executor)
                await async_print(f"--- 正在按计划执行 {num_tools_to_run} 个操作 (带重试，若最终失败则中止后续)... ---")

                tool_execution_results = [] # 清空上次的结果，准备接收本次执行结果
                try:
                    # 异步调用 ToolExecutor
                    tool_execution_results = await self.tool_executor.execute_tool_calls(mock_tool_calls_for_executor)
                    num_actually_executed = len(tool_execution_results)
                    logger.info(f"[Orchestrator] ToolExecutor 完成了 {num_actually_executed}/{num_tools_to_run} 个工具执行尝试。")
                    if num_actually_executed < num_tools_to_run:
                         logger.warning(f"[Orchestrator] 由于中途有工具最终失败，计划中的后续 {num_tools_to_run - num_actually_executed} 个工具未执行。")
                    await async_print(f"--- {num_actually_executed}/{num_tools_to_run} 个操作已执行 ---")
                except Exception as e:
                     logger.error(f"[Orchestrator] ToolExecutor 执行过程中发生顶层意外错误: {e}", exc_info=True)
                     await async_print(f"\n🔴 抱歉，执行工具时系统发生严重错误 ({e})！")
                     # 如果 ToolExecutor 本身出错，模拟一个整体失败结果
                     tool_execution_results = [{"tool_call_id": "executor_error", "result": {"status": "failure", "message": f"错误: 工具执行器层面发生严重错误: {e}", "error": {"type": "ExecutorError", "details": str(e)}}}]


                # --- 阶段 5: 观察 (处理工具结果并更新记忆) ---
                logger.info("\n--- [观察阶段] 处理工具结果并更新记忆 ---")
                num_tool_results_added = 0
                # 我将每个工具的执行结果添加到短期记忆
                if tool_execution_results: # 只有当有结果返回时才处理
                    for exec_result in tool_execution_results:
                        tool_call_id_for_memory = exec_result.get('tool_call_id', 'unknown_mock_id')
                        result_dict = exec_result.get('result', {"status": "unknown", "message": "执行结果丢失"})
                        if not isinstance(result_dict, dict):
                            logger.warning(f"工具 {tool_call_id_for_memory} 的结果不是字典格式，尝试包装。原始结果: {result_dict}")
                            result_dict = {"status": "unknown", "message": "非字典格式的工具结果", "raw_result": str(result_dict)}

                        try: result_content_str = json.dumps(result_dict, indent=2, ensure_ascii=False, default=str)
                        except Exception as json_dump_error:
                            logger.error(f"序列化工具 {tool_call_id_for_memory} 的结果字典失败: {json_dump_error}. Result: {result_dict}")
                            result_content_str = f'{{"status": "serialization_error", "message": "Failed to serialize result dict: {json_dump_error}", "original_result_repr": "{repr(result_dict)[:100]}..."}}'

                        tool_message = {"role": "tool", "tool_call_id": tool_call_id_for_memory, "content": result_content_str}
                        try:
                            self.memory_manager.add_to_short_term(tool_message)
                            num_tool_results_added += 1
                        except Exception as mem_err: logger.error(f"添加工具 {tool_call_id_for_memory} 结果到短期记忆失败: {mem_err}", exc_info=True)

                logger.info(f"[Orchestrator] {num_tool_results_added}/{len(tool_execution_results)} 个工具执行结果已添加至短期记忆。")

                # 检查是否有工具执行失败 (status != success)
                any_tool_failed = any(res['result'].get('status') != 'success' for res in tool_execution_results)

                if any_tool_failed:
                    logger.warning("[Orchestrator] 检测到有工具执行失败。检查是否需要重规划。")
                    # 如果有工具失败，并且未达到最大重规划次数
                    if replanning_count < self.max_replanning_attempts:
                        logger.info(f"[Orchestrator] 将进行第 {replanning_count + 1}/{self.max_replanning_attempts} 次重规划。")
                        replanning_count += 1 # 增加重规划计数
                        # 继续外层 while 循环，LLM 会在下一轮看到包含失败工具结果的完整历史
                        continue # 回到规划阶段

                    else:
                        logger.critical(f"[Orchestrator] 已达最大重规划尝试次数 ({self.max_replanning_attempts + 1} 次总尝试)，工具执行仍有失败。中止处理。")
                        # 所有重规划尝试都失败了，跳出重规划循环，进入最终报告阶段（失败报告）
                        break # 跳出外层重规划循环
                else:
                    # 所有计划中的工具都成功执行了 (或者没有工具需要执行)
                    logger.info("[Orchestrator] 所有已执行工具操作均成功。")
                    break # 跳出外层重规划循环，进入最终报告阶段（成功报告）

            else: # is_tool_calls is False
                # --- 情况 B: 计划不需要执行工具，直接回复 ---
                logger.info("[Orchestrator] 决策：根据 JSON 计划直接回复，不执行工具。")
                await async_print("--- 大脑认为无需执行操作，将直接回复... ---")

                # 我直接使用第一次 LLM 调用（规划阶段）生成的 'direct_reply'
                if direct_reply_from_plan and isinstance(direct_reply_from_plan, str) and direct_reply_from_plan.strip():
                    logger.info("[Orchestrator] 使用计划中提供的 'direct_reply' 作为最终回复。")
                    final_thinking = thinking_process # 复用第一次 LLM 的思考过程
                    final_reply = direct_reply_from_plan
                    # 在这种情况下，没有工具结果需要添加到记忆，也没有第二次 LLM 调用
                    # 第一次 LLM 的规划响应（包含 direct_reply）已经在本函数前面添加到记忆中了
                    # 成功处理，跳出重规划循环 (尽管没有重规划发生，但逻辑上在这里结束)
                    break
                else:
                    # 如果 is_tool_calls 为 false，但 direct_reply 无效或缺失，这是一个规划错误
                    err_msg = "'is_tool_calls' 为 false 但 'direct_reply' 无效或缺失！"
                    logger.error(f"[Orchestrator] 规划错误: {err_msg}")
                    # 生成一个包含错误信息的报告，并添加到记忆
                    final_thinking = thinking_process + f"\n规划错误：{err_msg}"
                    final_reply = "我理解现在不需要执行操作，但是智能大脑没有提供相应的回复。这可能是一个规划错误，请您澄清指令或重试。"
                    try: self.memory_manager.add_to_short_term({"role": "assistant", "content": f"<think>{final_thinking}</think>\n\n{final_reply}"})
                    except Exception as mem_err: logger.error(f"[Orchestrator] 添加直接回复错误信息到记忆失败: {mem_err}")

                    # 检查是否可以重规划 (理论上 direct_reply 规划失败不需要重规划，但为了逻辑统一，可以处理)
                    # 当前设计：如果计划是直接回复但内容有问题，不尝试重规划，直接返回错误报告。
                    break # 跳出重规划循环，进入最终报告阶段（错误报告）

        # --- 重规划循环结束 ---

        # --- 最终报告生成或错误处理 ---
        final_report = ""
        # 检查最终状态：是成功完成了规划和行动，还是在重规划循环中失败了？
        any_tool_failed_after_retries = any(res['result'].get('status') != 'success' for res in tool_execution_results) if tool_execution_results else False

        if plan_dict is None:
            # 未能成功规划 (即使重试后也失败)
            final_thinking_summary = thinking_process + f"\n最终规划失败。原因: {parser_error_msg}"
            final_reply_text = f"抱歉，经过 {replanning_count + 1} 次尝试，我还是无法从智能大脑获取一个有效的执行计划 ({parser_error_msg})。请检查您的指令或稍后再试。"
            await async_print("\n🔴 规划失败，无法继续。")
            final_report = f"<think>{final_thinking_summary}</think>\n\n{final_reply_text}".rstrip()
        elif is_tool_calls and any_tool_failed_after_retries:
            # 规划成功，但工具执行最终失败 (即使重试后也失败)，并且已达重规划上限
            final_thinking_summary = thinking_process + f"\n工具执行过程中发生了失败，且已达到最大重规划尝试次数 ({self.max_replanning_attempts + 1} 次)。"
            final_reply_text = "抱歉，在执行您的指令时遇到了问题。部分操作未能成功完成，且经过多次尝试重规划后仍然无法克服这些问题。您可以参考上面的操作日志了解哪些步骤失败了。请尝试简化指令或联系技术支持。"
            await async_print("\n🔴 工具执行失败，且重规划未成功。")
            # 第二次 LLM 调用 (生成失败报告)
            logger.info("\n--- [响应生成 - 失败报告] 请求 LLM 总结失败情况 ---")
            # 提供包含失败工具结果的完整历史给 LLM
            messages_for_llm2 = [{"role": "system", "content": self._get_response_generation_prompt_v7(
                self.memory_manager.get_memory_context_for_prompt(),
                self._get_tool_schemas_for_prompt(),
                tools_were_skipped=True # 标记有工具被跳过或失败
            )}] + self.memory_manager.short_term
            try:
                 second_llm_response = await self.llm_interface.call_llm(messages=messages_for_llm2, use_tools=False)
                 if second_llm_response and second_llm_response.choices and second_llm_response.choices[0].message and second_llm_response.choices[0].message.content:
                     raw_final_content = second_llm_response.choices[0].message.content
                     final_thinking_from_llm, final_reply_from_llm = self.output_parser._parse_llm_text_content(raw_final_content)
                     # 将 LLM 生成的报告添加到记忆
                     try: self.memory_manager.add_to_short_term(second_llm_response.choices[0].message.model_dump(exclude_unset=True))
                     except Exception as mem_err: logger.error(f"[Orchestrator] 添加 LLM 失败报告到记忆失败: {mem_err}")
                     final_report = f"<think>{final_thinking_from_llm}</think>\n\n{final_reply_from_llm}".rstrip()
                     logger.info("[Orchestrator] 已通过 LLM 生成失败报告。")
                 else:
                     logger.error("[Orchestrator] 请求 LLM 生成失败报告时响应无效或内容为空。")
                     final_report = f"<think>{final_thinking_summary}</think>\n\n{final_reply_text}".rstrip() # 使用备用错误报告
            except Exception as e:
                 logger.critical(f"[Orchestrator] 请求 LLM 生成失败报告时发生严重错误: {e}", exc_info=True)
                 final_report = f"<think>{final_thinking_summary}\n生成失败报告时出错: {e}</think>\n\n{final_reply_text}".rstrip() # 使用包含额外错误信息的备用报告

        else:
            # 规划成功，且所有执行的工具都成功了 (包括直接回复的情况)
            logger.info("[Orchestrator] 流程成功完成。准备生成最终报告。")
            # 如果是工具调用路径，且所有工具成功，需要调用 LLM 生成最终报告
            if is_tool_calls:
                logger.info("\n--- [响应生成] 请求 LLM 总结成功结果 ---")
                # 提供包含成功工具结果的完整历史给 LLM
                messages_for_llm2 = [{"role": "system", "content": self._get_response_generation_prompt_v7(
                    self.memory_manager.get_memory_context_for_prompt(),
                    self._get_tool_schemas_for_prompt(),
                    tools_were_skipped=False # 标记没有工具被跳过或失败
                )}] + self.memory_manager.short_term

                try:
                    second_llm_response = await self.llm_interface.call_llm(messages=messages_for_llm2, use_tools=False)
                    logger.info("[Orchestrator] 第二次 LLM 调用完成 (生成报告)。")
                    await async_print("--- 大脑已生成最终报告 ---")

                    logger.info("\n--- [报告解析] 解析最终报告 ---")
                    if not second_llm_response or not second_llm_response.choices or not second_llm_response.choices[0].message or not second_llm_response.choices[0].message.content:
                        logger.error("[Orchestrator] 第二次 LLM 响应无效或内容为空。无法生成最终报告。")
                        final_thinking_from_llm = "第二次 LLM 响应无效或内容为空。"
                        final_reply_from_llm = "抱歉，我在总结结果时遇到了问题，智能大脑没有返回有效的报告内容。请参考之前的操作日志了解详情。"
                        final_report = f"<think>{final_thinking_from_llm}</think>\n\n{final_reply_from_llm}".rstrip()
                        await async_print("\n🔴 抱歉，大脑未能生成最终报告！")
                    else:
                         final_response_message = second_llm_response.choices[0].message
                         final_thinking_from_llm, final_reply_from_llm = self.output_parser._parse_llm_text_content(final_response_message.content)
                         try: self.memory_manager.add_to_short_term(final_response_message.model_dump(exclude_unset=True))
                         except Exception as mem_err: logger.error(f"[Orchestrator] 添加最终回复到记忆失败: {mem_err}")
                         final_report = f"<think>{final_thinking_from_llm}</think>\n\n{final_reply_from_llm}".rstrip()

                except Exception as e:
                     logger.critical(f"[Orchestrator] 第二次 LLM 调用或最终报告处理失败: {e}", exc_info=True)
                     fallback_thinking = f"第二次 LLM 调用或最终报告处理失败: {e}"
                     fallback_reply = f"抱歉，在为您准备最终报告时遇到了严重的内部错误 ({e})！请参考日志获取技术详情。"
                     try: self.memory_manager.add_to_short_term({"role": "assistant", "content": f"<think>{fallback_thinking}</think>\n\n{fallback_reply}"})
                     except Exception: pass
                     final_report = f"<think>{fallback_thinking}</think>\n\n{fallback_reply}".rstrip()
                     await async_print(f"\n🔴 抱歉，生成最终报告时发生严重错误 ({e})！")

            else:
                # 规划是直接回复 (is_tool_calls is False)，已经在规划阶段获取了 direct_reply
                # 此时 final_report 变量应该还没有被上面任一失败路径覆盖
                final_report = f"<think>{thinking_process}</think>\n\n{direct_reply_from_plan}".rstrip()
                logger.info("[Orchestrator] 流程通过直接回复完成。")


        request_end_time = time.monotonic()
        logger.info(f"\n{'='*25} V7.1 请求处理完毕 (总耗时: {request_end_time - request_start_time:.3f} 秒) {'='*25}\n")
        return final_report


    # --- Helper Methods for Prompts ---
    def _get_tool_schemas_for_prompt(self) -> str:
        """
        根据 `self.tools_registry` 中的信息动态生成工具描述字符串，用于注入 LLM Prompt。
        这样我就不必在 Prompt 中硬编码工具列表了。
        """
        if not self.tools_registry:
            return "  (无可用工具)"

        tool_schemas = []
        for name, schema in self.tools_registry.items():
            desc = schema.get('description', '无描述。')
            params = schema.get('parameters', {})
            props = params.get('properties', {})
            req = params.get('required', [])
            param_desc_parts = []
            if props:
                for k, v in props.items():
                    p_type = v.get('type', 'any')
                    p_desc = v.get('description', '')
                    p_req = '(必须)' if k in req else '(可选)'
                    param_desc_parts.append(f"{k}: {p_type} {p_req} '{p_desc}'")
                param_desc_str = "; ".join(param_desc_parts)
            else:
                param_desc_str = "无参数"
            tool_schemas.append(f"  - `{name}`: {desc} (参数: {param_desc_str})")
        return "\n".join(tool_schemas)

    def _get_planning_prompt_v7(self, tool_schemas_desc: str, memory_context: str,
                                is_replanning: bool = False, previous_results: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        构建规划调用的 System Prompt。
        在重规划时，增加额外信息告知 LLM 之前的失败情况。
        核心要求是 LLM 严格按照 `<think>...</think> JSON_OBJECT` 格式输出。
        """
        replanning_intro = ""
        if is_replanning:
            replanning_intro = (
                "\n重要提示： 这是对您之前规划的重新尝试。上次执行您的计划时，部分工具操作遇到了问题。您应该仔细回顾对话历史中角色为 'tool' 的消息，了解哪些工具执行失败了及其原因。请根据这些失败信息，生成一个修正后的、能够克服之前问题的执行计划。如果您认为之前的计划有根本性错误，可以提出一个新的方案。如果您认为用户指令本身有问题导致无法执行，或者无法通过现有工具完成，您可以在 JSON 中设置 `is_tool_calls` 为 false 并提供一个解释性回复。\n"
            )
            # 虽然 tool 结果已经添加到记忆中，但这里再次提及，增强 LLM 注意
            if previous_results:
                 replanning_intro += f"\n上次工具执行结果概述 (详细信息请查看历史消息中的 'tool' 角色):\n{json.dumps(previous_results, indent=2, ensure_ascii=False)[:500]}...\n" # 仅提供一个概览片段


        return (
            "你是一位顶尖的、极其严谨的电路设计编程助理。你的行为必须专业、精确，并严格遵循指令。\n"
            "你的任务是：分析用户的最新指令、完整的对话历史以及当前的电路状态，然后严格按照下面描述的固定格式生成一个包含执行计划的 JSON 对象。\n"
            f"{replanning_intro}" # 插入重规划提示（如果适用）
            "绝对禁止使用任何形式的 Function Calling 或生成 `tool_calls` 字段。你的唯一输出必须由两部分组成：\n"
            "1.  一个 `<think>...</think>` XML 块：在其中详细阐述你的思考过程。这应包括：对用户指令的理解，对当前电路状态和记忆的分析，决定是否需要调用工具以及调用哪些工具，如何从指令中提取参数，规划具体的执行步骤，以及对潜在问题的评估。如果是重规划，必须分析之前工具失败的原因并说明如何修正计划。\n"
            "2.  紧随其后，必须是一个单一的、格式完全正确的 JSON 对象：这个 JSON 对象代表了你最终的执行计划或直接回复。不允许在 JSON 对象的前面或后面添加任何额外的文字、解释或注释！\n\n"
            "JSON 对象格式规范 (必须严格遵守):\n"
            "该 JSON 对象必须包含以下字段：\n"
            "  - `is_tool_calls` (boolean): 必须字段。如果分析后认为需要执行一个或多个工具操作来满足用户请求，则设为 `true`。如果不需要执行任何工具（例如，可以直接回答问题、进行确认、或者认为请求无法处理），则设为 `false`。\n"
            "  - `tool_list` (array<object> | null): 必须字段。行为取决于 `is_tool_calls` 的值：\n"
            "     - 当 `is_tool_calls` 为 `true` 时: 必须是一个包含一个或多个工具调用对象的数组。数组中的对象必须按照你期望的执行顺序列出。\n"
            "     - 当 `is_tool_calls` 为 `false` 时: 此字段必须是 `null` 值或者一个空数组 `[]`。\n"
            "     每个工具调用对象（如果存在）必须包含以下字段：\n"
            "       - `toolname` (string): 必须。要调用的工具的精确名称。你必须从下面提供的“可用工具列表”中选择一个有效的名称。\n"
            "       - `params` (object): 必须。一个包含调用该工具所需参数的 JSON 对象。你必须严格根据该工具的参数规范，从用户指令或对话历史中提取参数值。如果某个工具不需要参数，则提供一个空对象 `{}`。\n"
            "       - `index` (integer): 必须。表示此工具调用在你本次规划中的执行顺序。必须是一个从 `1` 开始的正整数。如果本次规划包含多个工具调用，它们的 `index` 值必须是连续的（例如 1, 2, 3）。\n"
            "  - `direct_reply` (string | null): 必须字段。行为取决于 `is_tool_calls` 的值：\n"
            "     - 当 `is_tool_calls` 为 `false` 时: 这里必须包含你准备直接回复给用户的最终、完整、友好的文本内容。回复内容不能为空字符串。\n"
            "     - 当 `is_tool_calls` 为 `true` 时: 此字段必须是 `null` 值。（因为后续会通过执行工具并再次调用你来生成最终回复）。\n\n"
            "可用工具列表与参数规范:\n"
            f"{tool_schemas_desc}\n\n"
            "当前电路状态与记忆:\n"
            f"{memory_context}\n\n"
            "最后再次强调：你的回复格式必须严格是 `<think>思考过程</think>` 后面紧跟着一个符合上述规范的 JSON 对象。不允许有任何偏差！ JSON 的语法（括号、引号、逗号、数据类型）和结构（必需字段、条件字段）都必须完全正确，否则后续处理会失败。"
        )

    def _get_response_generation_prompt_v7(self, memory_context: str, tool_schemas_desc: str, tools_were_skipped: bool) -> str:
        """
        构建最终响应生成调用的 System Prompt。
        此时，LLM 已经看到了用户请求、它的规划、以及所有已执行工具的结果（在 'tool' 消息中）。
        这个 Prompt 的核心任务是要求 LLM 基于所有这些信息，生成一个最终的、面向用户的回复。
        我特别强调了 LLM 需要理解 'tool' 消息中的 `status` 字段，并能在报告中反映工具执行的成功与失败，
        以及解释为何某些计划中的步骤（如果 `tools_were_skipped` 为 true）没有执行。
        """
        skipped_info = ""
        if tools_were_skipped:
            skipped_info = "\n重要提示： 在之前的工具执行过程中，由于某个工具最终失败（即使重试后），本次计划中的后续一个或多个工具已被中止执行。请在你的最终报告中明确说明操作结果（包括哪些成功、哪些失败），并解释哪些任务（如果有的话）因此未能完成，以及对用户请求的最终处理状态。"
        else:
             # 如果没有工具失败，但也需要强调检查结果
             skipped_info = "\n提示： 请仔细阅读对话历史中角色为 'tool' 的消息，它们包含了每个已执行工具的详细结果 (`status` 和 `message` 字段)。您应该根据这些结果来总结操作情况，并向用户汇报所有操作都已成功完成。"


        return (
            "你是一位顶尖的电路设计编程助理，经验丰富，技术精湛，并且擅长清晰地汇报工作结果。\n"
            "你的当前任务是：基于到目前为止的完整对话历史（包括用户最初的指令、你之前的思考和规划、以及所有已执行工具的结果），生成最终的、面向用户的文本回复。\n"
            "关键信息来源是角色为 'tool' 的消息: 每条 'tool' 消息都对应一个之前执行的工具调用（通过 `tool_call_id` 关联）。其 `content` 字段是一个 JSON 字符串，包含了该工具执行的关键信息，特别是 `status` 字段（指示 'success' 或 'failure'）和 `message` 字段（描述结果或错误）。可能还包含 `error` 字段提供失败的详细技术信息。\n"
            "你的报告必须：\n"
            "1.  仔细阅读并理解所有历史消息，特别是要解析每条 'tool' 消息中的 JSON 内容，准确把握每个已执行工具的最终状态 (`status`) 和结果 (`message`)。也要考虑是否有工具因为前面的工具失败而被跳过。\n"
            "2.  清晰地向用户总结所有已执行工具操作的结果：\n"
            "    - 对于成功的操作 (`status: \"success\"`)，进行简要的确认。\n"
            "    - 对于失败的操作 (`status: \"failure\"`)，必须诚恳地向用户说明操作失败了，并根据 `message` 和可能的 `error` 字段解释失败的原因及其对整体任务的影响。不要隐藏失败。\n"
            f"{skipped_info}\n" # 插入关于跳过/失败的提示
            "3.  综合以上信息，回答用户最初的问题或确认任务的完成情况。如果任务因工具失败而未能完全完成，请明确说明当前的状态和局限性。\n"
            "4.  严格按照以下固定格式生成你的回复：\n"
            "   a. 思考过程: 首先，在 `<think>` 和 `</think>` 标签之间，详细阐述你的反思和报告组织思路。回顾用户的原始请求、你的规划、并重点分析所有已执行工具的 `status` 和 `message`。评估任务的整体完成度。必须明确说明是否有工具失败或被跳过。最后，规划如何将这些信息整合，组织成清晰、友好、诚实地向用户汇报最终结果。\n"
            "   b. 正式回复: 在 `</think>` 标签之后，紧跟着面向用户的正式文本回复。这个回复应该基于你的思考过程，清晰、简洁、友好地总结情况，重点突出已完成和未完成的操作，以及任务的最终状态。\n"
            "最终输出格式必须严格是:\n"
            "`<think>你的详细思考过程</think>\n\n你的正式回复文本`\n"
            "(注意：`</think>` 标签后必须恰好是两个换行符 `\\n\\n`，然后直接是正式回复文本。)\n"
            "重要： 在这个阶段，你绝对不能再生成任何工具调用或 JSON 对象。你的唯一输出应该是包含 `<think>` 块和正式回复文本的字符串。"
            "\n\n"
            "上下文参考信息:\n"
            "【当前电路状态与记忆】\n"
            f"{memory_context}\n"
            "【我的可用工具列表 (仅供你参考，不应再次调用)】\n"
            f"{tool_schemas_desc}\n"
        )


# --- 异步主函数 (应用程序入口) ---
async def main():
    """
    异步主函数。我负责初始化 Agent 并启动主交互循环，处理用户输入。
    """
    await async_print("=" * 70)
    await async_print("🚀 启动 OpenManus 电路设计 Agent (V7.1 Refactored) 🚀")
    await async_print("   特性: 异步核心, 对象化电路状态, 动态工具注册, LLM规划重试, 工具执行重试, 规划失败重规划, 内存修剪")
    await async_print("=" * 70)
    logger.info("[Main] 开始 Agent 初始化...")

    # --- 获取 API Key ---
    api_key = os.environ.get("ZHIPUAI_API_KEY")
    if not api_key:
        logger.warning("[Main] 环境变量 ZHIPUAI_API_KEY 未设置。")
        await async_print("\n为了连接智能大脑，我需要您的智谱AI API Key。")
        try:
            api_key = input("👉 请在此输入您的智谱AI API Key: ").strip()
        except (EOFError, KeyboardInterrupt):
            await async_print("\n输入被中断。程序即将退出。")
            logger.info("[Main] 用户中断了 API Key 输入。")
            return
        if not api_key:
            await async_print("\n错误：未提供 API Key。程序无法启动，即将退出。")
            logger.critical("[Main] 用户未提供 API Key。")
            return
        logger.info("[Main] 已通过手动输入获取 API Key。")
        await async_print("API Key 已获取。")

    # --- 初始化 Agent ---
    agent = None
    try:
        agent = CircuitDesignAgentV7(
            api_key=api_key,
            model_name="glm-4-flash-250414",
            planning_llm_retries=1,         # LLM 规划调用失败重试 1 次
            max_tool_retries=2,             # 单个工具执行失败重试 2 次
            tool_retry_delay_seconds=0.5,   # 工具重试间隔 0.5 秒
            max_replanning_attempts=2,      # 工具执行失败后，最多尝试重规划 2 次
            max_short_term_items=25         # 短期记忆最大条目数
        )
        await async_print("\n🎉 Agent V7.1 Refactored 初始化成功！已准备就绪。")
        await async_print("\n您可以尝试以下指令:")
        await async_print("  - '给我加个1k电阻R1和3V电池B1'")
        await async_print("  - '连接R1和B1'")
        await async_print("  - '电路现在什么样？'")
        await async_print("  - '尝试连接 R1 和一个不存在的元件 XYZ'") # 测试工具失败和提前中止
        await async_print("  - '连接 B1 和它自己'") # 测试工具内部验证错误
        await async_print("  - '清空电路'")
        await async_print("  - '你好，今天天气怎么样？'") # 测试不需要工具的直接回复
        await async_print("  - 输入 '退出' 来结束程序")
        await async_print("-" * 70)
    except Exception as e:
        logger.critical(f"[Main] Agent V7.1 Refactored 初始化失败: {e}", exc_info=True)
        await async_print(f"\n🔴 Agent 初始化失败！错误: {e}。请检查日志和配置。程序即将退出。")
        return

    # --- 主交互循环 ---
    try:
        while True:
            try:
                user_input = ""
                try:
                    user_input = input("用户 > ").strip()
                except (EOFError, KeyboardInterrupt):
                    raise

                if user_input.lower() in ['退出', 'quit', 'exit', '再见', '结束', 'bye']:
                    await async_print("\n收到退出指令。感谢您的使用！👋")
                    logger.info("[Main] 收到退出指令，结束交互循环。")
                    break

                if not user_input:
                    continue

                start_process_time = time.monotonic()
                response = await agent.process_user_request(user_input)
                process_duration = time.monotonic() - start_process_time

                await async_print(f"\n📝 Agent 回复 (总耗时: {process_duration:.3f} 秒):")
                await async_print(response)
                await async_print("-" * 70)

            except KeyboardInterrupt:
                await async_print("\n用户操作被中断。")
                logger.info("[Main] 用户中断了当前请求的处理。")
                break
            except EOFError:
                await async_print("\n输入流意外结束。")
                logger.info("[Main] 输入流结束 (EOF)。")
                break
            except Exception as loop_err:
                logger.error(f"[Main] 处理指令 '{user_input[:50]}...' 时发生意外错误: {loop_err}", exc_info=True)
                await async_print(f"\n🔴 Agent 运行时错误:")
                error_report = f"<think>处理指令 '{user_input[:50]}...' 时发生内部错误: {loop_err}\n{traceback.format_exc()}</think>\n\n抱歉，我在执行您的指令时遇到了意外问题 ({loop_err})！我已经记录了详细的技术信息。请尝试其他指令或检查日志。"
                await async_print(error_report)
                await async_print("-" * 70)
                continue

    except Exception as outer_loop_err:
        logger.critical(f"[Main] 主交互循环外发生未处理异常: {outer_loop_err}", exc_info=True)
        await async_print(f"\n🔴 严重系统错误导致交互循环终止: {outer_loop_err}。")
    finally:
        logger.info("[Main] 主交互循环结束。")
        await async_print("\n正在关闭 Agent V7.1 Refactored...")


# --- 用于 Jupyter/IPython 环境的辅助函数 ---
async def run_agent_in_jupyter():
    """
    在 Jupyter/IPython 环境中安全启动 Agent 交互循环的辅助函数。
    你应该在 Notebook cell 中使用 `await run_agent_in_jupyter()` 来调用它。
    """
    print("正在尝试以 Jupyter/IPython 兼容模式启动 Agent V7.1 Refactored...")
    print("请在下方的输入提示处输入指令。输入 '退出' 结束。")
    try:
        await main()
    except Exception as e:
        print(f"\n🔴 Agent 在 Jupyter 模式下运行时遇到错误: {e}")
        logger.error(f"在 Jupyter 模式下运行 Agent 时出错: {e}", exc_info=True)
    finally:
        print("Agent 交互已结束 (Jupyter 模式)。")


# --- 标准 Python 脚本入口点 ---
if __name__ == "__main__":
    try:
        # 尝试获取 IPython Shell，如果存在则判断类型
        shell = None
        try:
            shell = get_ipython().__class__.__name__
        except NameError:
            pass # 不在 IPython 环境

        if shell == 'ZMQInteractiveShell':
            print("检测到 Jupyter/IPython (ZMQ) 环境。")
            print("请在 Notebook cell 中执行 `await run_agent_in_jupyter()` 来启动 Agent 交互。")
            # 在 Notebook 中，我们不自动启动 main，等待用户调用 run_agent_in_jupyter
        else:
            # 在标准 Python 解释器或 Terminal IPython 中运行
            print("正在以标准 Python 脚本模式启动 Agent V7.1 Refactored...")
            try:
                asyncio.run(main())
            except KeyboardInterrupt:
                print("\n程序被用户强制退出 (KeyboardInterrupt)。")
                logger.info("[Main Script] 程序被 KeyboardInterrupt 中断。")
            except Exception as e:
                print(f"\n程序因顶层错误而意外退出: {e}")
                logger.critical(f"脚本执行期间发生顶层异常: {e}", exc_info=True)
            finally:
                print("Agent V7.1 Refactored 程序已关闭。")

    except Exception as e:
        # 捕获 IPython 检测本身可能出现的错误
        print(f"启动环境检测或初始化时发生错误: {e}")
        logger.critical(f"启动环境检测或初始化时发生错误: {e}", exc_info=True)