# @FileName: openmanus_v7_tech_comments_boss_approved.py # 文件名加了点喜庆
# @Version: V7.2.1 - Async, Decorator Tools, Technical Comments, Refactored, File Logging, Enhanced Q&A Handling
# @Author: Your Most Loyal & Dedicated Programmer (Refactored & Enhanced)
# @Date: [Current Date] - Refactored Version with File Logging & Enhanced Q&A
# @License: Apache 2.0 (Anticipated)
# @Description:
# ==============================================================================================
#  Manus 系统 V7.2.1 技术实现说明 (重构、增强、文件日志、强化问答处理)
# ==============================================================================================
#
# 本脚本实现了一个用于电路设计的异步 Agent。我严格遵循标准的 Agentic 循环：
# 感知 -> 规划 -> 行动 -> 观察 -> 响应生成。
#
# 本次 V7.2.1 的核心改进 (在 V7.2 基础上):
# 1.  强化规划提示 (_get_planning_prompt_v7): 针对用户直接提问或请求概念解释时，
#     明确指导 LLM 必须返回包含 `is_tool_calls: false` 和 `direct_reply` 的 JSON 计划，
#     而不是直接输出文本答案。这解决了先前版本中处理此类问题时因 LLM 未按预期格式
#     输出 JSON 而导致的规划失败。
#
# 重申 V7.2 的核心改进：
# 1.  文件日志记录: 每次 Agent 运行时，所有日志输出都会被保存到 `agent_logs` 目录。
#
# 重申 V7.1 的核心改进：
# 1.  电路实体类 (`Circuit`): 封装电路状态。
# 2.  内存管理器 (`MemoryManager`): 管理短期历史、长期知识及 `Circuit` 对象。
# 3.  LLM 接口 (`LLMInterface`): 封装与 LLM 的异步交互。
# 4.  输出解析器 (`OutputParser`): 解析 LLM 返回的 `<think>` 和自定义 JSON。
# 5.  工具执行器 (`ToolExecutor`): 异步协调工具执行，支持重试和失败中止。
# 6.  内部工具 (Action Methods): 使用 `@register_tool` 动态注册。
# 7.  异步核心 (`Orchestrator`): 协调流程，支持规划失败后的重规划。
#
# 关键技术特性：
# -   文件日志记录
# -   全面异步化 (`asyncio`)
# -   电路状态对象化
# -   自定义 JSON 规划 (强化对直接回复场景的处理)
# -   规划重试, 工具执行重试, 规划失败重规划
# -   记忆修剪, 动态工具注册, 鲁棒的解析和错误处理
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
from datetime import datetime # 用于生成带时间戳的日志文件名
from typing import List, Dict, Any, Optional, Tuple, Set, Union
from zhipuai import ZhipuAI

# --- 全局异步事件循环 ---
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# --- 日志系统配置 ---
LOG_DIR = "agent_logs"
try:
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
except OSError as e:
    sys.stderr.write(f"CRITICAL: Could not create log directory '{LOG_DIR}'. Error: {e}\n")
    sys.stderr.write("File logging may be unavailable. Continuing with console logging only.\n")

current_time_for_log = datetime.now()
log_file_name = os.path.join(
    LOG_DIR,
    f"agent_log_{current_time_for_log.strftime('%Y%m%d_%H%M%S')}_{current_time_for_log.microsecond // 1000:03d}_P{os.getpid()}.log"
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


# --- 异步友好的打印函数 ---
async def async_print(message: str, end: str = '\n', flush: bool = True):
    """异步环境安全打印"""
    sys.stdout.write(message + end)
    if flush:
        sys.stdout.flush()

# --- 电路元件数据类 ---
class CircuitComponent:
    """电路元件的数据结构及基本验证"""
    __slots__ = ['id', 'type', 'value'] # 优化内存
    def __init__(self, component_id: str, component_type: str, value: Optional[str] = None):
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError("元件 ID 必须是有效的非空字符串")
        if not isinstance(component_type, str) or not component_type.strip():
            raise ValueError("元件类型必须是有效的非空字符串")
        self.id: str = component_id.strip().upper()
        self.type: str = component_type.strip()
        self.value: Optional[str] = str(value).strip() if value is not None and str(value).strip() else None
        logger.debug(f"成功创建元件对象: {self}")
    def __str__(self) -> str:
        value_str = f" (值: {self.value})" if self.value else ""
        return f"元件: {self.type} (ID: {self.id}){value_str}"
    def __repr__(self) -> str:
        return f"CircuitComponent(id='{self.id}', type='{self.type}', value={repr(self.value)})"
    def to_dict(self) -> Dict[str, Any]:
        """将元件对象转换为字典"""
        return {"id": self.id, "type": self.type, "value": self.value}


# --- 电路实体类 ---
class Circuit:
    """封装所有电路状态相关的逻辑和数据"""
    def __init__(self):
        logger.info("[Circuit] 初始化电路实体。")
        self.components: Dict[str, CircuitComponent] = {} # 元件字典
        self.connections: Set[Tuple[str, str]] = set() # 连接集合
        self._component_counters: Dict[str, int] = { # ID生成计数器
            'R': 0, 'L': 0, 'B': 0, 'S': 0, 'C': 0, 'V': 0, 'G': 0, 'U': 0, 'O': 0,
            'I': 0, 'A': 0, 'D': 0, 'P': 0, 'F': 0, 'H': 0
        }
        logger.info("[Circuit] 电路实体初始化完成。")

    def add_component(self, component: CircuitComponent):
        """添加元件到电路"""
        if component.id in self.components:
            raise ValueError(f"元件 ID '{component.id}' 已被占用。")
        self.components[component.id] = component
        logger.debug(f"[Circuit] 元件 '{component.id}' 已添加到电路。")

    def remove_component(self, component_id: str):
        """移除元件及其相关连接"""
        comp_id_upper = component_id.strip().upper()
        if comp_id_upper not in self.components:
            raise ValueError(f"元件 '{comp_id_upper}' 在电路中不存在。")
        del self.components[comp_id_upper]
        connections_to_remove = {conn for conn in self.connections if comp_id_upper in conn}
        for conn in connections_to_remove:
            self.connections.remove(conn)
            logger.debug(f"[Circuit] 移除了涉及元件 '{comp_id_upper}' 的连接 {conn}.")
        logger.debug(f"[Circuit] 元件 '{comp_id_upper}' 及其相关连接已从电路中移除。")


    def connect_components(self, id1: str, id2: str):
        """连接两个元件"""
        id1_upper = id1.strip().upper()
        id2_upper = id2.strip().upper()

        if id1_upper == id2_upper:
            raise ValueError(f"不能将元件 '{id1}' 连接到它自己。")
        if id1_upper not in self.components:
             raise ValueError(f"元件 '{id1}' 在电路中不存在。")
        if id2_upper not in self.components:
             raise ValueError(f"元件 '{id2}' 在电路中不存在。")

        connection = tuple(sorted((id1_upper, id2_upper)))
        if connection in self.connections:
             logger.warning(f"[Circuit] 连接 '{id1_upper}' <--> '{id2_upper}' 已存在。")
             return False # 连接已存在

        self.connections.add(connection)
        logger.debug(f"[Circuit] 添加了连接: {id1_upper} <--> {id2_upper}.")
        return True # 连接成功添加

    def disconnect_components(self, id1: str, id2: str):
        """断开两个元件的连接"""
        id1_upper = id1.strip().upper()
        id2_upper = id2.strip().upper()
        connection = tuple(sorted((id1_upper, id2_upper)))

        if connection not in self.connections:
             logger.warning(f"[Circuit] 连接 '{id1_upper}' <--> '{id2_upper}' 不存在，无需断开。")
             return False # 连接不存在

        self.connections.remove(connection)
        logger.debug(f"[Circuit] 断开了连接: {id1_upper} <--> {id2_upper}.")
        return True # 连接成功断开

    def get_state_description(self) -> str:
        """生成当前电路状态的文本描述"""
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
        """为给定类型的元件生成唯一的 ID"""
        logger.debug(f"[Circuit] 正在为类型 '{component_type}' 生成唯一 ID...")
        type_map = {
            "resistor": "R", "电阻": "R", "capacitor": "C", "电容": "C",
            "battery": "B", "电池": "B", "voltage source": "V", "voltage": "V",
            "电压源": "V", "电压": "V", "led": "L", "发光二极管": "L", "switch": "S",
            "开关": "S", "ground": "G", "地": "G", "ic": "U", "chip": "U", "芯片": "U",
            "集成电路": "U", "inductor": "I", "电感": "I", "current source": "A",
            "电流源": "A", "diode": "D", "二极管": "D", "potentiometer": "P", "电位器": "P",
            "fuse": "F", "保险丝": "F", "header": "H", "排针": "H",
            "component": "O", "元件": "O",
        }
        for code in type_map.values():
            if code not in self._component_counters:
                 self._component_counters[code] = 0

        cleaned_type = component_type.strip().lower()
        type_code = "O"
        best_match_len = 0
        for keyword, code in type_map.items():
            if keyword in cleaned_type and len(keyword) > best_match_len:
                type_code = code
                best_match_len = len(keyword)

        if type_code == "O" and cleaned_type not in ["component", "元件"]:
             logger.warning(f"[Circuit] 未找到类型 '{component_type}' 的特定前缀，将使用通用前缀 'O'。")

        MAX_ID_ATTEMPTS = 100
        for attempt in range(MAX_ID_ATTEMPTS):
            self._component_counters[type_code] += 1
            gen_id = f"{type_code}{self._component_counters[type_code]}"
            if gen_id not in self.components:
                logger.debug(f"[Circuit] 生成唯一 ID: '{gen_id}' (尝试 {attempt + 1})")
                return gen_id
            logger.warning(f"[Circuit] ID '{gen_id}' 已存在，尝试下一个。")

        raise RuntimeError(f"未能为类型 '{component_type}' (代码 '{type_code}') 生成唯一 ID ({MAX_ID_ATTEMPTS} 次尝试后)。")

    def clear(self):
        """清空当前电路的所有元件和连接"""
        logger.info("[Circuit] 正在清空电路状态...")
        comp_count = len(self.components)
        conn_count = len(self.connections)
        self.components = {}
        self.connections = set()
        self._component_counters = {k: 0 for k in self._component_counters}
        logger.info(f"[Circuit] 电路状态已清空 (移除了 {comp_count} 个元件, {conn_count} 个连接，并重置了所有 ID 计数器)。")

# --- 工具注册装饰器 ---
def register_tool(description: str, parameters: Dict[str, Any]):
    """装饰器，用于标记 Agent 方法为可调用工具，并附加 Schema 信息"""
    def decorator(func):
        func._tool_schema = {"description": description, "parameters": parameters}
        func._is_tool = True
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


# --- 模块化组件：MemoryManager ---
class MemoryManager:
    """记忆管理器，负责存储和管理 Agent 的所有记忆信息"""
    def __init__(self, max_short_term_items: int = 20, max_long_term_items: int = 50):
        logger.info("[MemoryManager] 初始化记忆模块...")
        if max_short_term_items <= 1:
            raise ValueError("max_short_term_items 必须大于 1")
        self.max_short_term_items = max_short_term_items
        self.max_long_term_items = max_long_term_items
        self.short_term: List[Dict[str, Any]] = [] # 短期对话历史
        self.long_term: List[str] = [] # 长期知识片段
        self.circuit: Circuit = Circuit() # 电路对象实例

        logger.info(f"[MemoryManager] 记忆模块初始化完成。短期上限: {max_short_term_items} 条, 长期上限: {max_long_term_items} 条。")

    def add_to_short_term(self, message: Dict[str, Any]):
        """添加消息到短期记忆，并执行修剪"""
        logger.debug(f"[MemoryManager] 添加消息到短期记忆 (Role: {message.get('role', 'N/A')}). 当前数量: {len(self.short_term)}")
        self.short_term.append(message)

        current_size = len(self.short_term)
        if current_size > self.max_short_term_items:
            logger.debug(f"[MemoryManager] 短期记忆超限 ({current_size}/{self.max_short_term_items})，执行修剪...")
            items_to_remove = current_size - self.max_short_term_items
            
            non_system_indices = [i for i, msg in enumerate(self.short_term) if msg.get("role") != "system"]
            num_to_actually_remove = min(items_to_remove, len(non_system_indices))
            
            if num_to_actually_remove > 0:
                indices_to_remove_set = set(non_system_indices[:num_to_actually_remove])
                removed_roles = [self.short_term[i].get('role', 'N/A') for i in sorted(list(indices_to_remove_set))]
                new_short_term = [msg for i, msg in enumerate(self.short_term) if i not in indices_to_remove_set]
                self.short_term = new_short_term
                logger.info(f"[MemoryManager] 短期记忆修剪完成，移除了 {num_to_actually_remove} 条最旧的非系统消息 (Roles: {removed_roles})。")
            elif items_to_remove > 0:
                 logger.warning(f"[MemoryManager] 短期记忆超限 ({current_size}/{self.max_short_term_items}) 但未能找到足够的非系统消息进行移除。")

        logger.debug(f"[MemoryManager] 添加后短期记忆数量: {len(self.short_term)}")

    def add_to_long_term(self, knowledge_snippet: str):
        """添加知识片段到长期记忆，FIFO 策略修剪"""
        logger.debug(f"[MemoryManager] 添加知识到长期记忆: '{knowledge_snippet[:100]}{'...' if len(knowledge_snippet) > 100 else ''}'. 当前数量: {len(self.long_term)}")
        self.long_term.append(knowledge_snippet)
        if len(self.long_term) > self.max_long_term_items:
            removed = self.long_term.pop(0)
            logger.info(f"[MemoryManager] 长期记忆超限 ({self.max_long_term_items}), 移除最旧知识: '{removed[:50]}...'")
        logger.debug(f"[MemoryManager] 添加后长期记忆数量: {len(self.long_term)}")

    def get_circuit_state_description(self) -> str:
        """获取当前电路状态的文本描述"""
        return self.circuit.get_state_description()

    def get_memory_context_for_prompt(self, recent_long_term_count: int = 5) -> str:
        """格式化非对话历史的记忆上下文（电路状态 + 近期长期记忆）"""
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

# --- 模块化组件：LLMInterface ---
class LLMInterface:
    """封装与大语言模型 (LLM) 的异步交互"""
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

    async def _dynamic_llm_wait_indicator(self, stop_event: asyncio.Event, initial_message: str = "正在与智能大脑沟通"):
        """
        老板，这是新增的内部异步函数，用于在等待LLM时显示动态提示！
        它会持续打印旋转的短划线，直到 stop_event 被设置。
        """
        animation_chars = ['|', '/', '-', '\\']
        idx = 0
        padding = " " * 20 # 用于覆盖可能残留的字符
        try:
            # 首先打印初始消息
            await async_print(f"\r{initial_message} {animation_chars[idx % len(animation_chars)]}{padding}", end="")
            while not stop_event.is_set():
                await asyncio.sleep(0.15) # 动画更新频率
                if stop_event.is_set(): # 在睡眠后再次检查，避免在事件刚设置后还打印一次
                    break
                idx += 1
                await async_print(f"\r{initial_message} {animation_chars[idx % len(animation_chars)]}{padding}", end="")
        except asyncio.CancelledError:
            # 任务被取消时，优雅退出
            pass
        finally:
            # 确保最后清除动态提示，为后续输出腾出空间
            await async_print(f"\r{' ' * (len(initial_message) + 2 + len(padding))}\r", end="") # 清除行

    async def call_llm(self, messages: List[Dict[str, Any]], use_tools: bool = False, tool_choice: Optional[str] = None) -> Any:
        """异步调用 LLM API (当前Agent不使用SDK的tools参数进行规划)"""
        call_args = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens,
        }

        logger.info(f"[LLMInterface] 准备异步调用 LLM ({self.model_name}，自定义 JSON/无内置工具模式)...")
        logger.debug(f"[LLMInterface] 发送的消息条数: {len(messages)}")
        if logger.isEnabledFor(logging.DEBUG) and len(messages) > 0:
             try:
                 messages_summary = json.dumps([{"role": m.get("role"), "content_preview": str(m.get("content"))[:100] + "..." if len(str(m.get("content", ""))) > 100 else str(m.get("content"))} for m in messages[-3:]], ensure_ascii=False, indent=2)
                 logger.debug(f"[LLMInterface] 最新消息列表 (预览): \n{messages_summary}")
             except Exception as e_json:
                 logger.debug(f"[LLMInterface] 无法序列化消息列表进行调试日志: {e_json}")

        # ===================================================================================
        # 老板，这里是实现动态等待提示的核心改动！
        # ===================================================================================
        stop_indicator_event = asyncio.Event()
        indicator_task = None
        initial_prompt_for_indicator = "🧠 正在思考请稍候" # 可以根据规划阶段或响应阶段传递不同提示
        
        # 我们可以根据 messages 的内容判断是规划阶段还是响应生成阶段，来定制提示信息
        # 这是一个简单的判断，您可以根据需要做得更复杂
        is_planning_phase = True # 默认是规划
        if len(messages) > 1 and messages[-1].get("role") == "user": # 如果最后一条是用户消息，通常是规划
            pass # is_planning_phase 保持 True
        elif any(msg.get("role") == "tool" for msg in messages): # 如果历史中有tool消息，通常是响应生成
            is_planning_phase = False
            initial_prompt_for_indicator = "📝 正在生成回复"


        indicator_task = asyncio.create_task(self._dynamic_llm_wait_indicator(stop_indicator_event, initial_prompt_for_indicator))
        # ===================================================================================
        # 动态等待提示改动结束
        # ===================================================================================

        response = None # 初始化 response
        try:
            start_time = time.monotonic()
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                **call_args
            )
            duration = time.monotonic() - start_time
            logger.info(f"[LLMInterface] LLM 异步调用成功。耗时: {duration:.3f} 秒。")

            if response:
                if response.usage:
                    logger.info(f"[LLMInterface] Token 统计: Prompt={response.usage.prompt_tokens}, Completion={response.usage.completion_tokens}, Total={response.usage.total_tokens}")
                if response.choices:
                    finish_reason = response.choices[0].finish_reason
                    logger.info(f"[LLMInterface] 完成原因: {finish_reason}")
                    if finish_reason == 'length':
                        logger.warning("[LLMInterface] LLM 响应因达到最大 token 限制而被截断！这可能导致 JSON 格式不完整。")
                else:
                     logger.warning("[LLMInterface] LLM 响应中缺少 'choices' 字段。")
            else:
                 logger.error("[LLMInterface] LLM API 调用返回了 None！")
                 raise ConnectionError("LLM API call returned None.")
            return response # 返回成功的响应
        except Exception as e:
            logger.error(f"[LLMInterface] LLM API 异步调用失败: {e}", exc_info=True)
            raise # 重新抛出异常，让上层处理
        finally:
            # ===================================================================================
            # 老板，确保无论成功失败，动态提示都会停止并清理
            # ===================================================================================
            stop_indicator_event.set() # 通知动态提示任务停止
            if indicator_task:
                try:
                    await indicator_task # 等待任务结束（它会自行清理打印）
                except asyncio.CancelledError:
                    logger.debug("[LLMInterface] 动态提示任务被取消 (可能在主任务异常时)。")
                except Exception as e_indicator_cleanup:
                    logger.error(f"[LLMInterface] 清理动态提示任务时出错: {e_indicator_cleanup}", exc_info=True)
            # ===================================================================================
            # 清理结束
            # ===================================================================================

# --- 模块化组件：OutputParser ---
class OutputParser:
    """负责解析 LLM 返回的响应，特别是规划阶段的 `<think>` 块和自定义 JSON 计划"""
    def __init__(self):
        logger.info("[OutputParser] 初始化输出解析器 (用于自定义 JSON 和文本解析)。")

    def parse_planning_response(self, response_message: Any) -> Tuple[str, Optional[Dict[str, Any]], str]:
        """解析规划阶段LLM响应，提取思考和JSON计划"""
        logger.debug("[OutputParser] 开始解析规划响应 (自定义 JSON 模式)...")
        thinking_process = "未能提取思考过程。"
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

        think_match = re.search(r'<think>(.*?)</think>', raw_content, re.IGNORECASE | re.DOTALL)
        json_part_start_index = 0
        if think_match:
            thinking_process = think_match.group(1).strip()
            json_part_start_index = think_match.end()
            logger.debug("[OutputParser] 成功提取 <think> 内容。")
        else:
            thinking_process = "警告：未找到 <think> 标签，将尝试解析后续内容为 JSON。"
            logger.warning(f"[OutputParser] {thinking_process}")

        potential_json_part = raw_content[json_part_start_index:].strip()
        logger.debug(f"[OutputParser] 提取出的待解析 JSON 字符串 (前 500 字符): >>>\n{potential_json_part[:500]}{'...' if len(potential_json_part) > 500 else ''}\n<<<")

        if not potential_json_part:
            if think_match:
                error_message = "在 <think> 标签后未找到 JSON 内容。"
            else:
                error_message = "提取出的潜在 JSON 内容为空。"
            logger.error(f"[OutputParser] 解析失败: {error_message}")
            return thinking_process, None, error_message

        final_json_string = ""
        parsed_json_plan = None
        try:
            json_string_to_parse = potential_json_part
            if json_string_to_parse.startswith("```json"):
                json_string_to_parse = json_string_to_parse[len("```json"):].strip()
            if json_string_to_parse.startswith("```"):
                json_string_to_parse = json_string_to_parse[len("```"):].strip()
            if json_string_to_parse.endswith("```"):
                json_string_to_parse = json_string_to_parse[:-len("```")].strip()

            json_start_char_index = -1
            json_end_char_index = -1
            first_brace = json_string_to_parse.find('{')
            first_square = json_string_to_parse.find('[')
            start_char_type = ''

            if first_brace != -1 and (first_square == -1 or first_brace < first_square):
                json_start_char_index = first_brace
                start_char_type = '{'
            elif first_square != -1 and (first_brace == -1 or first_square < first_brace):
                 json_start_char_index = first_square
                 start_char_type = '['
            
            if json_start_char_index == -1:
                raise json.JSONDecodeError("无法在文本中定位 JSON 对象或数组的起始 ('{' 或 '[')。", json_string_to_parse, 0)

            brace_level = 0
            square_level = 0
            in_string = False
            string_char = ''
            escape_next = False

            for i in range(json_start_char_index, len(json_string_to_parse)):
                char = json_string_to_parse[i]
                if escape_next: escape_next = False; continue
                if char == '\\': escape_next = True; continue
                if in_string:
                    if char == string_char: in_string = False
                else:
                    if char == '"' or char == "'": in_string = True; string_char = char
                    elif start_char_type == '{':
                        if char == '{': brace_level += 1
                        elif char == '}': brace_level -= 1
                    elif start_char_type == '[':
                        if char == '[': square_level += 1
                        elif char == ']': square_level -= 1
                if not in_string:
                    if start_char_type == '{' and char == '}' and brace_level == 0: json_end_char_index = i + 1; break
                    elif start_char_type == '[' and char == ']' and square_level == 0: json_end_char_index = i + 1; break
            
            if json_end_char_index == -1:
                raise json.JSONDecodeError(f"无法在文本中找到匹配的 JSON 结束符 ('{ '}' if start_char_type == '{' else ']' }').", json_string_to_parse, len(json_string_to_parse) -1)

            final_json_string = json_string_to_parse[json_start_char_index:json_end_char_index]
            logger.debug(f"[OutputParser] 精准提取的 JSON 字符串: >>>\n{final_json_string}\n<<<")
            parsed_json_plan = json.loads(final_json_string)
            logger.debug("[OutputParser] JSON 字符串解析成功。")

            if not isinstance(parsed_json_plan, dict): raise ValueError("解析结果不是一个 JSON 对象 (字典)。")
            if "is_tool_calls" not in parsed_json_plan or not isinstance(parsed_json_plan["is_tool_calls"], bool): raise ValueError("JSON 对象缺少必需的布尔字段 'is_tool_calls'。")
            
            tool_list = parsed_json_plan.get("tool_list")
            if parsed_json_plan["is_tool_calls"]:
                if not isinstance(tool_list, list): raise ValueError("当 'is_tool_calls' 为 true 时, 'tool_list' 字段必须是一个列表。")
                if not tool_list: logger.warning("[OutputParser] 验证警告: 'is_tool_calls' 为 true 但 'tool_list' 列表为空。")
                
                indices_set = set()
                for i, tool_item in enumerate(tool_list):
                    if not isinstance(tool_item, dict): raise ValueError(f"'tool_list' 中索引 {i} 的元素不是字典。")
                    if not tool_item.get("toolname") or not isinstance(tool_item["toolname"], str) or not tool_item["toolname"].strip(): raise ValueError(f"'tool_list' 中索引 {i} 缺少有效的非空 'toolname' 字符串。")
                    if "params" not in tool_item or not isinstance(tool_item["params"], dict): raise ValueError(f"'tool_list' 中索引 {i} 缺少 'params' 字典。")
                    if not isinstance(tool_item.get("index"), int) or tool_item.get("index", 0) <= 0: raise ValueError(f"'tool_list' 中索引 {i} 缺少有效正整数 'index'。")
                    current_index = tool_item["index"]
                    if current_index in indices_set: raise ValueError(f"'tool_list' 中索引 {i} 的 'index' 值 {current_index} 与之前的重复。")
                    indices_set.add(current_index)
                if tool_list:
                    max_index = max(indices_set) if indices_set else 0
                    if len(indices_set) != max_index or set(range(1, max_index + 1)) != indices_set:
                         logger.warning(f"[OutputParser] 验证警告: 'tool_list' 中的 'index' ({sorted(list(indices_set))}) 不连续或不从 1 开始。")
            else:
                if tool_list is not None and (not isinstance(tool_list, list) or tool_list):
                    raise ValueError("当 'is_tool_calls' 为 false 时, 'tool_list' 字段必须是 null 或一个空列表 []。")

            direct_reply = parsed_json_plan.get("direct_reply")
            if not parsed_json_plan["is_tool_calls"]:
                if not isinstance(direct_reply, str) or not direct_reply.strip():
                    raise ValueError("当 'is_tool_calls' 为 false 时, 必须提供有效的非空 'direct_reply' 字符串。")
            else:
                if direct_reply is not None and (not isinstance(direct_reply, str) or direct_reply.strip()):
                     raise ValueError("当 'is_tool_calls' 为 true 时, 'direct_reply' 字段必须是 null。")
            logger.info("[OutputParser] 自定义 JSON 计划解析和验证成功！")

        except json.JSONDecodeError as json_err:
            parsed_json_plan = None
            error_message = f"解析 JSON 失败: {json_err}。请检查 LLM 输出的 JSON 部分是否符合标准。Raw JSON string (截断): '{potential_json_part[:200]}...'"
            logger.error(f"[OutputParser] JSON 解析失败: {error_message}")
        except ValueError as validation_err:
            parsed_json_plan = None
            error_message = f"JSON 结构验证失败: {validation_err}。"
            json_content_for_log = final_json_string if final_json_string else potential_json_part[:200] + ('...' if len(potential_json_part) > 200 else '')
            logger.error(f"[OutputParser] JSON 结构验证失败: {error_message} JSON content (可能不完整): {json_content_for_log}")
        except Exception as e:
            parsed_json_plan = None
            error_message = f"解析规划响应时发生未知错误: {e}"
            logger.error(f"[OutputParser] 解析时未知错误: {error_message}", exc_info=True)

        return thinking_process, parsed_json_plan, error_message

    def _parse_llm_text_content(self, text_content: str) -> Tuple[str, str]:
        """从 LLM 的最终文本响应中解析思考过程和正式回复"""
        logger.debug("[OutputParser._parse_llm_text_content] 正在解析最终文本内容...")
        if not text_content: 
            logger.warning("[OutputParser._parse_llm_text_content] 接收到空的文本内容。")
            return "思考过程提取失败 (输入为空)。", "回复内容提取失败 (输入为空)。"

        thinking_process = "未能提取思考过程。"
        formal_reply = text_content.strip()

        think_match = re.search(r'<think>(.*?)</think>', text_content, re.IGNORECASE | re.DOTALL)
        if think_match:
            thinking_process = think_match.group(1).strip()
            formal_reply = text_content[think_match.end():].strip()
            content_before_think = text_content[:think_match.start()].strip()
            if content_before_think:
                logger.warning(f"[OutputParser._parse_llm_text_content] 在 <think> 标签之前检测到非空白内容: '{content_before_think[:50]}...'。")
        else:
            logger.warning("[OutputParser._parse_llm_text_content] 未找到 <think>...</think> 标签。将整个内容视为正式回复，思考过程标记为提取失败。")
            thinking_process = "未能提取思考过程 - LLM 可能未按预期包含<think>标签。"

        thinking_process = thinking_process if thinking_process else "提取的思考过程为空白。"
        formal_reply = formal_reply if formal_reply else "LLM 未生成最终报告内容。"

        logger.debug(f"[OutputParser._parse_llm_text_content] 解析结果 - 思考长度: {len(thinking_process)}, 回复长度: {len(formal_reply)}")
        return thinking_process, formal_reply

# --- 模块化组件：ToolExecutor ---
class ToolExecutor:
    """负责执行 Agent 的内部工具，支持重试和失败中止"""
    def __init__(self, agent_instance: 'CircuitDesignAgentV7', max_tool_retries: int = 2, tool_retry_delay_seconds: float = 1.0):
        logger.info("[ToolExecutor] 初始化工具执行器 (支持异步, 重试, 失败中止)。")
        if not isinstance(agent_instance, CircuitDesignAgentV7):
            raise TypeError("ToolExecutor 需要一个 CircuitDesignAgentV7 实例。")
        self.agent_instance = agent_instance
        if not hasattr(agent_instance, 'memory_manager') or not isinstance(agent_instance.memory_manager, MemoryManager):
            raise TypeError("Agent 实例缺少有效的 MemoryManager。")

        self.max_tool_retries = max(0, max_tool_retries)
        self.tool_retry_delay_seconds = max(0.1, tool_retry_delay_seconds)
        logger.info(f"[ToolExecutor] 工具执行配置: 每个工具最多重试 {self.max_tool_retries} 次，重试间隔 {self.tool_retry_delay_seconds} 秒。")


    async def execute_tool_calls(self, mock_tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按顺序异步协调执行工具调用列表"""
        logger.info(f"[ToolExecutor] 准备异步执行最多 {len(mock_tool_calls)} 个工具调用 (按顺序，支持重试，失败中止)...")
        execution_results = []

        if not mock_tool_calls:
            logger.info("[ToolExecutor] 没有工具需要执行。")
            return []

        total_tools = len(mock_tool_calls)
        for i, mock_call in enumerate(mock_tool_calls):
            current_tool_index_in_plan = i + 1
            function_name = "unknown_function"
            tool_call_id_from_mock = mock_call.get('id', f'mock_id_fallback_{i}')
            action_result_final_for_tool = None
            parsed_arguments = {}
            tool_display_name = "未知工具"
            tool_succeeded_after_all_retries = False

            try:
                func_info = mock_call.get('function')
                if not isinstance(func_info, dict) or 'name' not in func_info or 'arguments' not in func_info:
                     err_msg = f"模拟 ToolCall 对象结构无效 (ID: {tool_call_id_from_mock})。"
                     logger.error(f"[ToolExecutor] {err_msg}")
                     action_result_final_for_tool = {"status": "failure", "message": "错误: 内部工具调用结构无效。", "error": {"type": "MalformedMockCall", "details": err_msg}}
                     execution_results.append({"tool_call_id": tool_call_id_from_mock, "result": action_result_final_for_tool})
                     await async_print(f"  ❌ [{current_tool_index_in_plan}/{total_tools}] 内部错误: 工具调用结构无效。已中止后续。")
                     break

                function_name = func_info['name']
                function_args_str = func_info['arguments']
                tool_display_name = function_name.replace('_tool', '').replace('_', ' ').title()
                
                logger.info(f"[ToolExecutor] 处理工具调用 {current_tool_index_in_plan}/{total_tools}: Name='{function_name}', MockID='{tool_call_id_from_mock}'")
                logger.debug(f"[ToolExecutor] 原始参数 JSON 字符串: '{function_args_str}'")
                await async_print(f"  [{current_tool_index_in_plan}/{total_tools}] 准备执行: {tool_display_name}...")

                try:
                    parsed_arguments = json.loads(function_args_str) if function_args_str and function_args_str.strip() else {}
                    if not isinstance(parsed_arguments, dict):
                         raise TypeError(f"参数必须是 JSON 对象，实际得到: {type(parsed_arguments)}")
                    logger.debug(f"[ToolExecutor] 参数解析成功: {parsed_arguments}")
                except (json.JSONDecodeError, TypeError) as json_err:
                    err_msg = f"工具 '{function_name}' (ID: {tool_call_id_from_mock}) 的参数 JSON 解析失败: {json_err}."
                    logger.error(f"[ToolExecutor] 参数解析错误: {err_msg}", exc_info=True)
                    action_result_final_for_tool = {"status": "failure", "message": f"错误: 工具 '{function_name}' 的参数格式错误。", "error": {"type": "ArgumentParsing", "details": err_msg}}
                    await async_print(f"  ❌ [{current_tool_index_in_plan}/{total_tools}] 操作失败: {tool_display_name}. 错误: 参数解析失败。已中止后续。")
                    execution_results.append({"tool_call_id": tool_call_id_from_mock, "result": action_result_final_for_tool})
                    break

                tool_action_method = getattr(self.agent_instance, function_name, None)
                if not callable(tool_action_method):
                    err_msg = f"Agent 未实现名为 '{function_name}' 的工具方法 (ID: {tool_call_id_from_mock})。"
                    logger.error(f"[ToolExecutor] 工具未实现: {err_msg}")
                    action_result_final_for_tool = {"status": "failure", "message": f"错误: {err_msg}", "error": {"type": "NotImplemented", "details": f"Action method '{function_name}' not found."}}
                    await async_print(f"  ❌ [{current_tool_index_in_plan}/{total_tools}] 操作失败: {tool_display_name}. 错误: 工具未实现。已中止后续。")
                    execution_results.append({"tool_call_id": tool_call_id_from_mock, "result": action_result_final_for_tool})
                    break

                for retry_attempt in range(self.max_tool_retries + 1):
                    current_attempt_num = retry_attempt + 1
                    if retry_attempt > 0:
                        logger.warning(f"[ToolExecutor] 工具 '{function_name}' (ID: {tool_call_id_from_mock}) 执行失败，正在进行第 {retry_attempt}/{self.max_tool_retries} 次重试...")
                        await async_print(f"  🔄 [{current_tool_index_in_plan}/{total_tools}] 操作 '{tool_display_name}' 失败，等待 {self.tool_retry_delay_seconds} 秒后重试 (尝试 {current_attempt_num})...")
                        await asyncio.sleep(self.tool_retry_delay_seconds)
                        await async_print(f"  🔄 [{current_tool_index_in_plan}/{total_tools}] 正在进行第 {retry_attempt} 次重试执行 '{tool_display_name}'...")

                    logger.debug(f"[ToolExecutor] >>> 正在调用 Action 方法: '{function_name}' (ID: {tool_call_id_from_mock}, Attempt {current_attempt_num})")
                    action_result_this_attempt = None
                    try:
                        action_result_this_attempt = await asyncio.to_thread(tool_action_method, arguments=parsed_arguments)
                        if not isinstance(action_result_this_attempt, dict) or 'status' not in action_result_this_attempt or 'message' not in action_result_this_attempt:
                            err_msg_struct = f"Action '{function_name}' 返回的结构无效。"
                            logger.error(f"[ToolExecutor] Action 返回结构错误 (Attempt {current_attempt_num}): {err_msg_struct}")
                            action_result_this_attempt = {"status": "failure", "message": f"错误: 工具 '{function_name}' 返回结果结构无效。", "error": {"type": "InvalidActionResult", "details": err_msg_struct}}
                        else:
                             logger.info(f"[ToolExecutor] Action '{function_name}' (ID: {tool_call_id_from_mock}) 执行完毕 (Attempt {current_attempt_num})。状态: {action_result_this_attempt.get('status', 'N/A')}")

                        if action_result_this_attempt.get("status") == "success":
                            tool_succeeded_after_all_retries = True
                            action_result_final_for_tool = action_result_this_attempt
                            break
                        if retry_attempt < self.max_tool_retries:
                             logger.warning(f"[ToolExecutor] Action '{function_name}' (ID: {tool_call_id_from_mock}) 执行失败 (Attempt {current_attempt_num})。将重试。")
                        else:
                             logger.error(f"[ToolExecutor] Action '{function_name}' (ID: {tool_call_id_from_mock}) 在所有 {self.max_tool_retries + 1} 次尝试后仍失败。")
                             action_result_final_for_tool = action_result_this_attempt
                    except TypeError as te:
                        err_msg_type = f"调用 Action '{function_name}' 时参数不匹配或内部类型错误 (Attempt {current_attempt_num}): {te}."
                        logger.error(f"[ToolExecutor] Action 调用参数/类型错误: {err_msg_type}", exc_info=True)
                        action_result_this_attempt = {"status": "failure", "message": f"错误: 调用工具 '{function_name}' 时参数或内部类型错误。", "error": {"type": "ArgumentOrInternalTypeError", "details": err_msg_type}}
                        action_result_final_for_tool = action_result_this_attempt
                        if retry_attempt == self.max_tool_retries: break
                    except Exception as exec_err:
                        err_msg_exec = f"Action '{function_name}' 执行期间发生意外内部错误 (Attempt {current_attempt_num}): {exec_err}"
                        logger.error(f"[ToolExecutor] Action 执行内部错误: {err_msg_exec}", exc_info=True)
                        action_result_this_attempt = {"status": "failure", "message": f"错误: 执行工具 '{function_name}' 时发生内部错误。", "error": {"type": "ExecutionError", "details": str(exec_err)}}
                        action_result_final_for_tool = action_result_this_attempt
                        if retry_attempt == self.max_tool_retries: break
                
                if action_result_final_for_tool is None:
                     logger.error(f"[ToolExecutor] 内部逻辑错误: 工具 '{function_name}' 未在重试后生成任何最终结果。")
                     action_result_final_for_tool = {"status": "failure", "message": f"错误: 工具 '{function_name}' 未返回结果。", "error": {"type": "MissingResult"}}

                execution_results.append({"tool_call_id": tool_call_id_from_mock, "result": action_result_final_for_tool})
                logger.debug(f"[ToolExecutor] 已记录工具 '{tool_call_id_from_mock}' 的最终执行结果 (状态: {action_result_final_for_tool.get('status')}).")

                status_icon = "✅" if tool_succeeded_after_all_retries else "❌"
                msg_preview = action_result_final_for_tool.get('message', '无消息')[:80] + ('...' if len(action_result_final_for_tool.get('message', '')) > 80 else '')
                await async_print(f"  {status_icon} [{current_tool_index_in_plan}/{total_tools}] 操作完成: {tool_display_name}. 结果: {msg_preview}")

                if not tool_succeeded_after_all_retries:
                    logger.warning(f"[ToolExecutor] 工具 '{function_name}' (Mock ID: {tool_call_id_from_mock}) 在所有重试后仍然失败。中止后续工具执行。")
                    await async_print(f"  ⚠️ 由于工具 '{tool_display_name}' 在重试后仍然失败，本次计划中的后续操作已中止。")
                    break
            except Exception as outer_err:
                 err_msg_outer = f"处理工具调用 '{function_name}' (Mock ID: {tool_call_id_from_mock}) 时发生顶层意外错误: {outer_err}"
                 logger.error(f"[ToolExecutor] 处理工具调用时顶层错误: {err_msg_outer}", exc_info=True)
                 action_result_final_for_tool = {"status": "failure", "message": f"错误: 处理工具 '{tool_display_name or function_name}' 时发生未知内部错误。", "error": {"type": "UnexpectedToolSetupError", "details": str(outer_err)}}
                 execution_results.append({"tool_call_id": tool_call_id_from_mock, "result": action_result_final_for_tool})
                 await async_print(f"  ❌ [{current_tool_index_in_plan}/{total_tools}] 操作失败: {tool_display_name or function_name}. 错误: 未知内部错误。已中止后续。")
                 break

        total_executed_or_attempted = len(execution_results)
        logger.info(f"[ToolExecutor] 所有 {total_executed_or_attempted}/{total_tools} 个计划中的工具调用已处理 (可能因失败提前中止)。")
        return execution_results

# --- Agent 核心类 (Orchestrator) ---
class CircuitDesignAgentV7:
    """电路设计 Agent V7.2.1 - 异步协调器, 带文件日志, 强化问答处理"""
    def __init__(self, api_key: str, model_name: str = "glm-4-flash-250414",
                 max_short_term_items: int = 25, max_long_term_items: int = 50,
                 planning_llm_retries: int = 1, max_tool_retries: int = 2,
                 tool_retry_delay_seconds: float = 1.0, max_replanning_attempts: int = 2):
        logger.info(f"\n{'='*30} Agent V7.2.1 初始化开始 (Async, Decorator Tools, File Logging, Enhanced Q&A) {'='*30}") # 版本号更新
        logger.info("[Agent Init] 正在启动电路设计助理 V7.2.1...")

        try:
            self.memory_manager = MemoryManager(max_short_term_items, max_long_term_items)
            self.llm_interface = LLMInterface(api_key=api_key, model_name=model_name)
            self.output_parser = OutputParser()
            self.tool_executor = ToolExecutor(
                agent_instance=self,
                max_tool_retries=max_tool_retries,
                tool_retry_delay_seconds=tool_retry_delay_seconds
            )
        except (ValueError, ConnectionError, TypeError) as e:
            logger.critical(f"[Agent Init] 核心模块初始化失败: {e}", exc_info=True)
            sys.stderr.write(f"\n🔴 Agent 核心模块初始化失败: {e}\n请检查配置或依赖！程序无法启动。\n")
            sys.stderr.flush()
            raise

        self.planning_llm_retries = max(0, planning_llm_retries)
        self.max_replanning_attempts = max(0, max_replanning_attempts)
        logger.info(f"[Agent Init] 规划 LLM 调用失败时将重试 {self.planning_llm_retries} 次。")
        logger.info(f"[Agent Init] 工具执行失败后，最多允许重规划 {self.max_replanning_attempts} 次。")

        self.tools_registry: Dict[str, Dict[str, Any]] = {}
        logger.info("[Agent Init] 正在动态发现并注册已标记的工具...")
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, '_is_tool') and method._is_tool:
                schema = getattr(method, '_tool_schema', None)
                if schema and isinstance(schema, dict) and 'description' in schema and 'parameters' in schema:
                    self.tools_registry[name] = schema
                    logger.info(f"[Agent Init] ✓ 已注册工具: '{name}'")
                else:
                    logger.warning(f"[Agent Init] 发现工具 '{name}' 但其 Schema 结构不完整或无效，已跳过。")
        if not self.tools_registry:
            logger.warning("[Agent Init] 未发现任何通过 @register_tool 注册的工具！")
        else:
            logger.info(f"[Agent Init] 共发现并注册了 {len(self.tools_registry)} 个工具。")
            if logger.isEnabledFor(logging.DEBUG):
                try:
                    logger.debug(f"[Agent Init] 工具注册表详情:\n{json.dumps(self.tools_registry, indent=2, ensure_ascii=False)}")
                except Exception: pass

        logger.info(f"\n{'='*30} Agent V7.2.1 初始化成功 {'='*30}\n") # 版本号更新
        print("我是电路设计编程助理 V7.2.1！") # 版本号更新
        print("已准备好接收指令。采用异步核心，增强重试、重规划机制，并记录详细文件日志。")
        print(f"日志文件位于: {os.path.abspath(log_file_name)}")
        print("-" * 70)
        sys.stdout.flush()


    # --- Action Implementations (工具实现) ---
    @register_tool(
        description="添加一个新的电路元件 (如电阻, 电容, 电池, LED, 开关, 芯片, 地线等)。如果用户未指定 ID，会自动生成。",
        parameters={
            "type": "object",
            "properties": {
                "component_type": {"type": "string", "description": "元件的类型 (例如: '电阻', 'LED')."},
                "component_id": {"type": "string", "description": "可选的用户指定 ID。"},
                "value": {"type": "string", "description": "可选的元件值 (例如: '1k', '10uF')."}
            },
            "required": ["component_type"]
        }
    )
    def add_component_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Action: 添加元件"""
        logger.info("[Action: AddComponent] 执行添加元件操作。")
        logger.debug(f"[Action: AddComponent] 收到参数: {arguments}")
        component_type = arguments.get("component_type")
        component_id_req = arguments.get("component_id")
        value_req = arguments.get("value")
        logger.info(f"[Action: AddComponent] 参数解析: Type='{component_type}', Requested ID='{component_id_req}', Value='{value_req}'")

        if not component_type or not isinstance(component_type, str) or not component_type.strip():
            msg="元件类型是必需的，并且必须是有效的非空字符串。"
            logger.error(f"[Action: AddComponent] 输入验证失败: {msg}")
            return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "InvalidInput", "details": msg}}

        target_id_final = None
        id_was_generated_by_system = False
        user_provided_id_was_validated = None

        if component_id_req and isinstance(component_id_req, str) and component_id_req.strip():
            user_provided_id_cleaned = component_id_req.strip().upper()
            if re.match(r'^[a-zA-Z0-9_][a-zA-Z0-9_-]*$', user_provided_id_cleaned):
                if user_provided_id_cleaned in self.memory_manager.circuit.components:
                    msg=f"您提供的元件 ID '{user_provided_id_cleaned}' 已被占用。"
                    logger.error(f"[Action: AddComponent] ID 冲突: {msg}")
                    return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "IDConflict", "details": msg}}
                else:
                    target_id_final = user_provided_id_cleaned
                    user_provided_id_was_validated = target_id_final
                    logger.debug(f"[Action: AddComponent] 将使用用户提供的有效 ID: '{target_id_final}'.")
            else:
                logger.warning(f"[Action: AddComponent] 用户提供的 ID '{component_id_req}' 格式无效。将自动生成 ID。")

        if target_id_final is None:
            try:
                target_id_final = self.memory_manager.circuit.generate_component_id(component_type)
                id_was_generated_by_system = True
                logger.debug(f"[Action: AddComponent] 已自动为类型 '{component_type}' 生成 ID: '{target_id_final}'.")
            except RuntimeError as e_gen_id:
                msg=f"无法自动为类型 '{component_type}' 生成唯一 ID: {e_gen_id}"
                logger.error(f"[Action: AddComponent] ID 生成失败: {msg}", exc_info=True)
                return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "IDGenerationFailed", "details": str(e_gen_id)}}

        processed_value = str(value_req).strip() if value_req is not None and str(value_req).strip() else None

        try:
            if target_id_final is None: raise ValueError("内部错误：未能最终确定元件 ID。") 
            new_component = CircuitComponent(target_id_final, component_type, processed_value)
            self.memory_manager.circuit.add_component(new_component)
            logger.info(f"[Action: AddComponent] 成功添加元件 '{new_component.id}' ({new_component.type}) 到电路。")
            success_message_parts = [f"操作成功: 已添加元件 {str(new_component)}。"]
            if id_was_generated_by_system: success_message_parts.append(f"(系统自动分配 ID '{new_component.id}')")
            elif user_provided_id_was_validated: success_message_parts.append(f"(使用了您指定的 ID '{user_provided_id_was_validated}')")
            final_success_message = " ".join(success_message_parts)
            self.memory_manager.add_to_long_term(f"添加了元件: {str(new_component)}")
            return {"status": "success", "message": final_success_message, "data": new_component.to_dict()}
        except ValueError as ve_comp:
            msg=f"创建或添加元件对象时发生内部验证错误: {ve_comp}"
            logger.error(f"[Action: AddComponent] 元件创建/添加错误: {msg}", exc_info=True)
            return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "ComponentOperationError", "details": str(ve_comp)}}
        except Exception as e_add_comp:
            msg=f"添加元件时发生未知的内部错误: {e_add_comp}"
            logger.error(f"[Action: AddComponent] 未知错误: {msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 添加元件时发生未知内部错误。", "error": {"type": "Unexpected", "details": str(e_add_comp)}}

    @register_tool(
        description="使用两个已存在元件的 ID 将它们连接起来。",
        parameters={
            "type": "object",
            "properties": {
                "comp1_id": {"type": "string", "description": "第一个元件的 ID。"},
                "comp2_id": {"type": "string", "description": "第二个元件的 ID。"}
            },
            "required": ["comp1_id", "comp2_id"]
        }
    )
    def connect_components_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Action: 连接两个元件"""
        logger.info("[Action: ConnectComponents] 执行连接元件操作。")
        logger.debug(f"[Action: ConnectComponents] 收到参数: {arguments}")
        comp1_id_req = arguments.get("comp1_id")
        comp2_id_req = arguments.get("comp2_id")
        logger.info(f"[Action: ConnectComponents] 参数解析: Comp1='{comp1_id_req}', Comp2='{comp2_id_req}'")

        if not comp1_id_req or not isinstance(comp1_id_req, str) or not comp1_id_req.strip() or \
           not comp2_id_req or not isinstance(comp2_id_req, str) or not comp2_id_req.strip():
            msg="必须提供两个有效的、非空的元件 ID 字符串。"
            logger.error(f"[Action: ConnectComponents] 输入验证失败: {msg}")
            return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "InvalidInput", "details": msg}}

        id1_cleaned = comp1_id_req.strip().upper()
        id2_cleaned = comp2_id_req.strip().upper()

        try:
            connection_was_new = self.memory_manager.circuit.connect_components(id1_cleaned, id2_cleaned)
            if connection_was_new:
                logger.info(f"[Action: ConnectComponents] 成功添加新连接: {id1_cleaned} <--> {id2_cleaned}")
                self.memory_manager.add_to_long_term(f"连接了元件: {id1_cleaned} <--> {id2_cleaned}")
                return {"status": "success", "message": f"操作成功: 已将元件 '{id1_cleaned}' 与 '{id2_cleaned}' 连接起来。", "data": {"connection": sorted((id1_cleaned, id2_cleaned))}}
            else:
                msg_exists = f"元件 '{id1_cleaned}' 和 '{id2_cleaned}' 之间已经存在连接。无需重复操作。"
                logger.info(f"[Action: ConnectComponents] 连接已存在: {msg_exists}")
                return {"status": "success", "message": f"注意: {msg_exists}", "data": {"connection": sorted((id1_cleaned, id2_cleaned)), "already_existed": True}}
        except ValueError as ve_connect:
            msg_val_err =f"连接元件时验证失败: {ve_connect}"
            logger.error(f"[Action: ConnectComponents] 连接验证错误: {msg_val_err}")
            error_type_detail = "CircuitValidationError"
            if "不存在" in str(ve_connect): error_type_detail = "ComponentNotFound"
            elif "连接到它自己" in str(ve_connect): error_type_detail = "SelfConnection"
            return {"status": "failure", "message": f"错误: {msg_val_err}", "error": {"type": error_type_detail, "details": str(ve_connect)}}
        except Exception as e_connect:
            msg_unexpected =f"连接元件时发生未知的内部错误: {e_connect}"
            logger.error(f"[Action: ConnectComponents] 未知错误: {msg_unexpected}", exc_info=True)
            return {"status": "failure", "message": "错误: 连接元件时发生未知内部错误。", "error": {"type": "Unexpected", "details": str(e_connect)}}

    @register_tool(
        description="获取当前电路的详细描述。",
        parameters={"type": "object", "properties": {}}
    )
    def describe_circuit_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Action: 描述当前电路"""
        logger.info("[Action: DescribeCircuit] 执行描述电路操作。")
        logger.debug(f"[Action: DescribeCircuit] 收到参数: {arguments}")
        try:
            description = self.memory_manager.circuit.get_state_description()
            logger.info("[Action: DescribeCircuit] 成功生成电路描述。")
            return {"status": "success", "message": "已成功获取当前电路的描述。", "data": {"description": description}}
        except Exception as e_describe:
            msg=f"生成电路描述时发生意外的内部错误: {e_describe}"
            logger.error(f"[Action: DescribeCircuit] 未知错误: {msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 获取电路描述时发生未知错误。", "error": {"type": "Unexpected", "details": str(e_describe)}}

    @register_tool(
        description="彻底清空当前的电路设计。",
        parameters={"type": "object", "properties": {}}
    )
    def clear_circuit_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Action: 清空电路"""
        logger.info("[Action: ClearCircuit] 执行清空电路操作。")
        logger.debug(f"[Action: ClearCircuit] 收到参数: {arguments}")
        try:
            self.memory_manager.circuit.clear()
            logger.info("[Action: ClearCircuit] 电路状态已成功清空。")
            self.memory_manager.add_to_long_term("执行了清空电路操作。")
            return {"status": "success", "message": "操作成功: 当前电路已彻底清空。"}
        except Exception as e_clear:
            msg=f"清空电路时发生意外的内部错误: {e_clear}"
            logger.error(f"[Action: ClearCircuit] 未知错误: {msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 清空电路时发生未知错误。", "error": {"type": "Unexpected", "details": str(e_clear)}}

    # --- Orchestration Layer Method (核心流程) ---
    async def process_user_request(self, user_request: str) -> str:
        """处理用户请求的核心异步流程"""
        request_start_time = time.monotonic()
        logger.info(f"\n{'='*25} V7.2.1 开始处理用户请求 {'='*25}") # 版本号更新
        logger.info(f"[Orchestrator] 收到用户指令: \"{user_request}\"")

        if not user_request or user_request.isspace():
            logger.info("[Orchestrator] 用户指令为空或仅包含空白。")
            await async_print("\n您的指令似乎是空的，请重新输入！")
            return "<think>用户输入为空或空白，无需处理。</think>\n\n请输入您的指令！"
        try:
            self.memory_manager.add_to_short_term({"role": "user", "content": user_request})
            logger.info("[Orchestrator] 用户指令已记录并添加到短期记忆。")
        except Exception as e_mem_user:
            logger.error(f"[Orchestrator] 添加用户消息到短期记忆时出错: {e_mem_user}", exc_info=True)
            await async_print(f"\n🔴 抱歉，我在记录您的指令时遇到了内部问题 ({e_mem_user})！请稍后重试。")
            return f"<think>添加用户消息到短期记忆失败: {e_mem_user}</think>\n\n抱歉，我在处理您的指令时遇到了内部记忆错误。"

        replanning_loop_count = 0
        final_plan_from_llm = None 
        final_tool_execution_results = [] 
        llm_thinking_process_from_planning = "未能提取思考过程 (初始)。"
        
        while replanning_loop_count <= self.max_replanning_attempts:
            current_planning_attempt_num = replanning_loop_count + 1
            logger.info(f"\n--- [规划/重规划阶段] 尝试第 {current_planning_attempt_num}/{self.max_replanning_attempts + 1} 次规划 ---")
            planning_phase_type_log_prefix = f"[Orchestrator - Planning Attempt {current_planning_attempt_num}]"

            if replanning_loop_count > 0:
                 await async_print(f"--- 由于之前的操作失败，正在尝试第 {replanning_loop_count}/{self.max_replanning_attempts} 次重规划... ---")
            else:
                 await async_print("--- 正在请求智能大脑分析指令并生成执行计划 (JSON)... ---")

            memory_context_for_prompt = self.memory_manager.get_memory_context_for_prompt()
            tool_schemas_for_llm_prompt = self._get_tool_schemas_for_prompt()
            system_prompt_for_planning = self._get_planning_prompt_v7(
                tool_schemas_for_llm_prompt, memory_context_for_prompt,
                is_replanning=(replanning_loop_count > 0)
            )
            messages_for_llm_planning = [{"role": "system", "content": system_prompt_for_planning}] + self.memory_manager.short_term

            llm_call_attempt_for_planning = 0
            parsed_plan_this_cycle = None
            parser_error_msg_this_cycle = ""

            while llm_call_attempt_for_planning <= self.planning_llm_retries:
                current_llm_call_num = llm_call_attempt_for_planning + 1
                logger.info(f"{planning_phase_type_log_prefix} 调用规划 LLM (LLM Call Attempt {current_llm_call_num}/{self.planning_llm_retries + 1})...")
                if current_llm_call_num > 1: await async_print(f"    (与大脑沟通尝试 {current_llm_call_num}/{self.planning_llm_retries + 1})...")

                try:
                    llm_response_for_planning = await self.llm_interface.call_llm(messages=messages_for_llm_planning, use_tools=False)
                    logger.info(f"{planning_phase_type_log_prefix} LLM 调用完成 (LLM Call Attempt {current_llm_call_num}).")
                    if not llm_response_for_planning or not llm_response_for_planning.choices: raise ConnectionError("LLM 响应无效。")
                    llm_message_obj = llm_response_for_planning.choices[0].message
                    logger.info(f"{planning_phase_type_log_prefix} 解析 LLM 的规划响应...")
                    temp_thinking, temp_plan, temp_parser_error = self.output_parser.parse_planning_response(llm_message_obj)
                    llm_thinking_process_from_planning = temp_thinking
                    parsed_plan_this_cycle = temp_plan
                    parser_error_msg_this_cycle = temp_parser_error

                    if parsed_plan_this_cycle is not None and not parser_error_msg_this_cycle:
                        logger.info(f"{planning_phase_type_log_prefix} 成功解析并验证自定义 JSON 计划！")
                        try:
                            self.memory_manager.add_to_short_term(llm_message_obj.model_dump(exclude_unset=True))
                            logger.debug(f"{planning_phase_type_log_prefix} LLM 的原始规划响应已添加至短期记忆。")
                        except Exception as mem_err_plan: logger.error(f"{planning_phase_type_log_prefix} 添加 LLM 规划响应到短期记忆失败: {mem_err_plan}", exc_info=True)
                        break 
                    else:
                        logger.warning(f"{planning_phase_type_log_prefix} 解析 JSON 失败: {parser_error_msg_this_cycle}. 尝试重试 LLM 调用。")
                        if llm_call_attempt_for_planning < self.planning_llm_retries: await async_print(f"    (解析大脑计划失败，尝试重新沟通...)")
                except ConnectionError as conn_err_llm:
                    logger.error(f"{planning_phase_type_log_prefix} LLM 调用失败 (连接/API错误): {conn_err_llm}", exc_info=True)
                    parser_error_msg_this_cycle = f"LLM 调用连接/API错误: {conn_err_llm}"
                    if llm_call_attempt_for_planning < self.planning_llm_retries: await async_print(f"    (与大脑连接失败，尝试重新连接...)")
                except Exception as e_llm_call:
                    logger.error(f"{planning_phase_type_log_prefix} LLM 调用或规划解析过程中发生严重错误: {e_llm_call}", exc_info=True)
                    parser_error_msg_this_cycle = f"LLM 调用或响应解析时发生错误: {e_llm_call}"
                    if llm_call_attempt_for_planning < self.planning_llm_retries: await async_print(f"    (大脑处理计划失败，尝试重新沟通...)")
                llm_call_attempt_for_planning += 1
            
            final_plan_from_llm = parsed_plan_this_cycle

            if final_plan_from_llm is None:
                logger.error(f"{planning_phase_type_log_prefix} 规划失败：所有 LLM 调用尝试后，未能获取有效 JSON 计划。最终解析错误: {parser_error_msg_this_cycle}")
                if replanning_loop_count >= self.max_replanning_attempts:
                     logger.critical(f"{planning_phase_type_log_prefix} 已达最大重规划尝试次数，仍无法获得有效计划。中止处理。")
                     break
                else:
                     logger.warning(f"{planning_phase_type_log_prefix} 规划失败，将在下一轮尝试重规划。")
                     replanning_loop_count += 1
                     continue

            logger.info(f"{planning_phase_type_log_prefix} 成功获取并验证自定义 JSON 计划。")
            if logger.isEnabledFor(logging.DEBUG):
                try: logger.debug(f"{planning_phase_type_log_prefix} 解析出的计划详情: {json.dumps(final_plan_from_llm, indent=2, ensure_ascii=False)}")
                except Exception: pass

            should_call_tools = final_plan_from_llm.get("is_tool_calls", False)
            tool_list_in_plan = final_plan_from_llm.get("tool_list")
            direct_reply_in_plan = final_plan_from_llm.get("direct_reply")

            if should_call_tools:
                logger.info(f"{planning_phase_type_log_prefix} 决策：根据 JSON 计划执行工具。")
                if not isinstance(tool_list_in_plan, list) or not tool_list_in_plan:
                    err_msg_bad_list = "'is_tool_calls' 为 true 但 'tool_list' 不是有效的非空列表！"
                    logger.error(f"{planning_phase_type_log_prefix} 规划错误: {err_msg_bad_list}")
                    final_tool_execution_results = [{"tool_call_id": "internal_planning_error_bad_tool_list", "result": {"status": "failure", "message": f"错误: 计划要求调用工具，但工具列表无效或为空。", "error": {"type": "MalformedPlanToolList", "details": err_msg_bad_list}}}]
                    try: self.memory_manager.add_to_short_term({"role": "tool", "tool_call_id": "internal_planning_error_bad_tool_list", "content": json.dumps(final_tool_execution_results[0]['result'], default=str)})
                    except Exception as mem_err_sim: logger.error(f"{planning_phase_type_log_prefix} 添加模拟规划错误工具结果到记忆失败: {mem_err_sim}")
                    if replanning_loop_count >= self.max_replanning_attempts: break
                    else: replanning_loop_count += 1; continue

                mock_tool_calls_for_executor = []
                param_conversion_issues = False
                for tool_item_from_plan in tool_list_in_plan:
                    tool_name = tool_item_from_plan.get("toolname")
                    params_dict = tool_item_from_plan.get("params", {})
                    index_from_plan = tool_item_from_plan.get("index")
                    try: params_hash_str = format(hash(json.dumps(params_dict, sort_keys=True, ensure_ascii=False)) & 0xFFFF, 'x')
                    except Exception: params_hash_str = "nohash"
                    mock_tool_call_id = f"call_{index_from_plan}_{tool_name[:10].replace('_','-')}_{params_hash_str}"
                    try: params_json_str = json.dumps(params_dict, ensure_ascii=False)
                    except TypeError: param_conversion_issues = True; params_json_str = "{}"
                    mock_tool_calls_for_executor.append({"id": mock_tool_call_id, "type": "function", "function": {"name": tool_name, "arguments": params_json_str}})
                if param_conversion_issues: logger.warning(f"{planning_phase_type_log_prefix} 注意: 转换工具列表时部分参数序列化遇到问题。")
                logger.info(f"{planning_phase_type_log_prefix} 成功将自定义工具列表转换为 {len(mock_tool_calls_for_executor)} 个模拟 ToolCall 对象。")

                logger.info(f"\n--- [行动阶段 - 尝试 {current_planning_attempt_num}] 执行工具 ---")
                num_tools_in_current_plan = len(mock_tool_calls_for_executor)
                await async_print(f"--- 正在按计划执行 {num_tools_in_current_plan} 个操作... ---")
                current_execution_results = []
                try:
                    current_execution_results = await self.tool_executor.execute_tool_calls(mock_tool_calls_for_executor)
                    num_actually_attempted_by_executor = len(current_execution_results)
                    logger.info(f"[Orchestrator - Action Phase] ToolExecutor 完成了 {num_actually_attempted_by_executor}/{num_tools_in_current_plan} 个工具执行。")
                    if num_actually_attempted_by_executor < num_tools_in_current_plan: logger.warning(f"[Orchestrator - Action Phase] 由于中途失败，后续 {num_tools_in_current_plan - num_actually_attempted_by_executor} 个工具未执行。")
                    await async_print(f"--- {num_actually_attempted_by_executor}/{num_tools_in_current_plan} 个操作已执行 ---")
                except Exception as e_tool_exec_top:
                     logger.error(f"[Orchestrator - Action Phase] ToolExecutor 执行过程中发生顶层意外错误: {e_tool_exec_top}", exc_info=True)
                     current_execution_results = [{"tool_call_id": "executor_internal_error", "result": {"status": "failure", "message": f"错误: 工具执行器层面发生严重错误: {e_tool_exec_top}", "error": {"type": "ToolExecutorError"}}}]
                final_tool_execution_results = current_execution_results

                logger.info(f"\n--- [观察阶段 - 尝试 {current_planning_attempt_num}] 处理工具结果并更新记忆 ---")
                num_tool_results_added_to_memory = 0
                if final_tool_execution_results:
                    for tool_exec_res in final_tool_execution_results:
                        tool_call_id_for_mem = tool_exec_res.get('tool_call_id', 'unknown_mock_id')
                        result_dict_for_mem = tool_exec_res.get('result', {"status": "unknown", "message": "结果丢失"})
                        if not isinstance(result_dict_for_mem, dict): result_dict_for_mem = {"status": "unknown_format", "message": "非字典格式结果", "raw": str(result_dict_for_mem)}
                        try: result_content_json_str = json.dumps(result_dict_for_mem, ensure_ascii=False, default=str)
                        except Exception as json_dump_err_observe: result_content_json_str = f'{{"status": "serialization_error_observe", "message": "序列化结果失败: {json_dump_err_observe}"}}'
                        tool_message_for_memory = {"role": "tool", "tool_call_id": tool_call_id_for_mem, "content": result_content_json_str}
                        try: self.memory_manager.add_to_short_term(tool_message_for_memory); num_tool_results_added_to_memory += 1
                        except Exception as mem_err_tool_res: logger.error(f"[Orchestrator - Observe] 添加工具 {tool_call_id_for_mem} 结果到记忆失败: {mem_err_tool_res}")
                logger.info(f"[Orchestrator - Observe] {num_tool_results_added_to_memory}/{len(final_tool_execution_results)} 个工具执行结果已添加至短期记忆。")

                any_tool_failed_in_this_run = any(res.get('result', {}).get('status') != 'success' for res in final_tool_execution_results) if final_tool_execution_results else False
                if any_tool_failed_in_this_run:
                    logger.warning(f"[Orchestrator - Observe] 检测到有工具执行失败。检查是否需要重规划。")
                    if replanning_loop_count < self.max_replanning_attempts:
                        logger.info(f"[Orchestrator - Observe] 将进行第 {replanning_loop_count + 1}/{self.max_replanning_attempts} 次重规划。")
                        replanning_loop_count += 1
                        continue
                    else:
                        logger.critical(f"[Orchestrator - Observe] 已达最大重规划尝试次数，工具执行仍有失败。中止。")
                        break
                else:
                    logger.info(f"[Orchestrator - Observe] 所有已执行工具操作均成功。流程成功。")
                    break
            else: # 计划是直接回复
                logger.info(f"{planning_phase_type_log_prefix} 决策：根据 JSON 计划直接回复，不执行工具。")
                await async_print("--- 大脑认为无需执行操作，将直接回复... ---")
                if direct_reply_in_plan and isinstance(direct_reply_in_plan, str) and direct_reply_in_plan.strip():
                    logger.info(f"{planning_phase_type_log_prefix} 使用计划中提供的 'direct_reply' 作为最终回复。")
                    break
                else:
                    err_msg_bad_direct_reply = "'is_tool_calls' 为 false 但 'direct_reply' 无效或缺失！"
                    logger.error(f"{planning_phase_type_log_prefix} 规划错误: {err_msg_bad_direct_reply}")
                    final_tool_execution_results = [{"tool_call_id": "internal_planning_error_bad_direct_reply", "result": {"status": "failure", "message": f"错误: 计划指示直接回复，但回复内容无效。", "error": {"type": "MalformedPlanDirectReply"}}}]
                    try: self.memory_manager.add_to_short_term({"role": "tool", "tool_call_id": "internal_planning_error_bad_direct_reply", "content": json.dumps(final_tool_execution_results[0]['result'], default=str)})
                    except Exception as mem_err_sim_direct: logger.error(f"{planning_phase_type_log_prefix} 添加模拟直接回复错误到记忆失败: {mem_err_sim_direct}")
                    if replanning_loop_count >= self.max_replanning_attempts: break
                    else: replanning_loop_count += 1; continue
        
        final_agent_response_str = ""
        overall_success = False
        if final_plan_from_llm:
            if not final_plan_from_llm.get("is_tool_calls", False):
                if final_plan_from_llm.get("direct_reply","").strip(): overall_success = True
            else:
                if final_tool_execution_results:
                    all_attempted_tools_succeeded = not any(res.get('result', {}).get('status') != 'success' for res in final_tool_execution_results)
                    if all_attempted_tools_succeeded: overall_success = True
                elif not final_plan_from_llm.get("tool_list"): overall_success = True
        
        if final_plan_from_llm is None:
            thinking_summary_for_report = llm_thinking_process_from_planning + f"\n最终规划失败。原因: {parser_error_msg_this_cycle}"
            reply_text_for_report = f"抱歉，经过 {replanning_loop_count + 1} 次尝试，我还是无法从智能大脑获取一个有效的执行计划 ({parser_error_msg_this_cycle})。"
            await async_print("\n🔴 最终规划失败，无法继续。")
            final_agent_response_str = f"<think>{thinking_summary_for_report}</think>\n\n{reply_text_for_report}".rstrip()
        elif final_plan_from_llm.get("is_tool_calls") and not overall_success:
            thinking_summary_for_report = llm_thinking_process_from_planning + f"\n工具执行过程中发生了失败，或计划本身存在问题，且已达到最大重规划尝试次数。"
            failure_details = "具体失败信息请参考日志。"
            if final_tool_execution_results:
                failed_tool_messages = [f"工具 '{res.get('tool_call_id','N/A').split('_')[2] if '_' in res.get('tool_call_id','N/A') else 'N/A'}': {res.get('result',{}).get('message','No message')}" for res in final_tool_execution_results if res.get('result',{}).get('status') != 'success']
                if failed_tool_messages: failure_details = "最后一次尝试中失败的操作包括：\n- " + "\n- ".join(failed_tool_messages)
            reply_text_for_report = f"抱歉，在执行您的指令时遇到了问题。部分操作未能成功完成，且经过 {self.max_replanning_attempts + 1} 次尝试后仍然无法解决。\n{failure_details}"
            await async_print("\n🔴 工具执行失败或规划错误，且重规划未成功。")
            logger.info("\n--- [响应生成 - 失败报告] 请求 LLM 总结失败情况 ---")
            system_prompt_for_failure_report = self._get_response_generation_prompt_v7(self.memory_manager.get_memory_context_for_prompt(), self._get_tool_schemas_for_prompt(), tools_were_skipped_or_failed=True)
            messages_for_llm_failure_report = [{"role": "system", "content": system_prompt_for_failure_report}] + self.memory_manager.short_term
            try:
                 llm_response_for_failure_report = await self.llm_interface.call_llm(messages=messages_for_llm_failure_report, use_tools=False)
                 if llm_response_for_failure_report and llm_response_for_failure_report.choices and llm_response_for_failure_report.choices[0].message and llm_response_for_failure_report.choices[0].message.content:
                     raw_final_content_from_llm = llm_response_for_failure_report.choices[0].message.content
                     final_thinking_from_llm, final_reply_from_llm = self.output_parser._parse_llm_text_content(raw_final_content_from_llm)
                     try: self.memory_manager.add_to_short_term(llm_response_for_failure_report.choices[0].message.model_dump(exclude_unset=True))
                     except Exception as mem_err_fail_rep: logger.error(f"[Orchestrator] 添加 LLM 失败报告到记忆失败: {mem_err_fail_rep}")
                     final_agent_response_str = f"<think>{final_thinking_from_llm}</think>\n\n{final_reply_from_llm}".rstrip()
                     logger.info("[Orchestrator] 已通过 LLM 生成失败情况的总结报告。")
                 else:
                     logger.error("[Orchestrator] 请求 LLM 生成失败报告时响应无效。使用预设备用报告。")
                     final_agent_response_str = f"<think>{thinking_summary_for_report}\nLLM未能生成规范的失败报告。</think>\n\n{reply_text_for_report}".rstrip()
            except Exception as e_llm_fail_report:
                 logger.critical(f"[Orchestrator] 请求 LLM 生成失败报告时发生严重错误: {e_llm_fail_report}", exc_info=True)
                 final_agent_response_str = f"<think>{thinking_summary_for_report}\n生成失败报告时出错: {e_llm_fail_report}</think>\n\n{reply_text_for_report}".rstrip()
        else: # overall_success is True
            logger.info("[Orchestrator] 流程成功完成。准备生成最终报告。")
            if final_plan_from_llm.get("is_tool_calls"):
                logger.info("\n--- [响应生成 - 成功报告] 请求 LLM 总结成功结果 ---")
                system_prompt_for_success_report = self._get_response_generation_prompt_v7(self.memory_manager.get_memory_context_for_prompt(), self._get_tool_schemas_for_prompt(), tools_were_skipped_or_failed=False)
                messages_for_llm_success_report = [{"role": "system", "content": system_prompt_for_success_report}] + self.memory_manager.short_term
                try:
                    llm_response_for_success_report = await self.llm_interface.call_llm(messages=messages_for_llm_success_report, use_tools=False)
                    logger.info("[Orchestrator] 第二次 LLM 调用完成 (生成成功报告)。")
                    await async_print("--- 大脑已生成最终报告 ---")
                    if not llm_response_for_success_report or not llm_response_for_success_report.choices or not llm_response_for_success_report.choices[0].message or not llm_response_for_success_report.choices[0].message.content:
                        logger.error("[Orchestrator] 第二次 LLM 响应无效或内容为空 (成功报告)。")
                        final_agent_response_str = f"<think>{llm_thinking_process_from_planning}\n第二次 LLM 响应无效。</think>\n\n所有操作均已成功执行，但我无法从智能大脑获取规范的总结报告。"
                    else:
                         final_response_message_obj = llm_response_for_success_report.choices[0].message
                         final_thinking_from_llm, final_reply_from_llm = self.output_parser._parse_llm_text_content(final_response_message_obj.content)
                         try: self.memory_manager.add_to_short_term(final_response_message_obj.model_dump(exclude_unset=True))
                         except Exception as mem_err_succ_rep: logger.error(f"[Orchestrator] 添加最终成功回复到记忆失败: {mem_err_succ_rep}")
                         final_agent_response_str = f"<think>{final_thinking_from_llm}</think>\n\n{final_reply_from_llm}".rstrip()
                         logger.info("[Orchestrator] 已通过 LLM 生成操作成功的总结报告。")
                except Exception as e_llm_succ_report:
                     logger.critical(f"[Orchestrator] 第二次 LLM 调用或最终成功报告处理失败: {e_llm_succ_report}", exc_info=True)
                     final_agent_response_str = f"<think>{llm_thinking_process_from_planning}\n第二次 LLM 调用失败: {e_llm_succ_report}</think>\n\n所有操作均已成功执行，但在为您准备最终报告时遇到了严重的内部错误！"
            else:
                direct_reply_content = final_plan_from_llm.get("direct_reply", "未能获取直接回复内容。")
                final_agent_response_str = f"<think>{llm_thinking_process_from_planning}</think>\n\n{direct_reply_content}".rstrip()
                logger.info("[Orchestrator] 流程通过直接回复成功完成。")

        request_end_time = time.monotonic()
        total_duration_seconds = request_end_time - request_start_time
        logger.info(f"\n{'='*25} V7.2.1 请求处理完毕 (总耗时: {total_duration_seconds:.3f} 秒) {'='*25}\n") # 版本号更新
        return final_agent_response_str


    # --- Helper Methods for Prompts (辅助生成提示) ---
    def _get_tool_schemas_for_prompt(self) -> str:
        """根据工具注册表动态生成工具描述字符串"""
        if not self.tools_registry: return "  (无可用工具)"
        tool_schemas_parts = []
        for tool_name, schema in self.tools_registry.items():
            desc = schema.get('description', '无描述。')
            params_schema = schema.get('parameters', {})
            props_schema = params_schema.get('properties', {})
            req_params = params_schema.get('required', [])
            param_desc_segments = [f"'{k}': ({v.get('type','any')}, {'必须' if k in req_params else '可选'}) {v.get('description','无描述')}" for k,v in props_schema.items()] if props_schema else ["无参数"]
            tool_schemas_parts.append(f"  - 工具名称: `{tool_name}`\n    描述: {desc}\n    参数: {'; '.join(param_desc_segments)}")
        return "\n".join(tool_schemas_parts)

    def _get_planning_prompt_v7(self, tool_schemas_desc: str, memory_context: str,
                                is_replanning: bool = False, 
                                previous_results: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        构建规划调用的 System Prompt.
        V7.2.1 (老板的指示): 为直接问答/概念解释添加了明确指导和示例。
        """
        replanning_guidance = ""
        if is_replanning:
            replanning_guidance = (
                "\n【重要：重规划指示】\n"
                "这是对您先前规划的修正尝试。上次执行您的计划时，部分或全部工具操作遇到了问题，或者计划本身可能存在缺陷。您必须仔细回顾完整的对话历史，特别是角色为 'tool' 的消息（它们包含了上次工具执行失败的详细原因），以及您自己之前的思考和规划。请基于这些信息：\n"
                "1. 分析失败的根本原因。\n"
                "2. 提出一个能够克服先前问题的、全新的、经过深思熟虑的执行计划。\n"
                "3. 如果您认为用户指令本身有问题、无法通过现有工具完成，或者多次尝试后仍无法成功，您可以在新计划的 JSON 中将 `is_tool_calls` 设置为 `false`，并在 `direct_reply` 字段中提供一个清晰、礼貌的解释性回复给用户，说明情况和您的建议。\n"
                "不要简单重复失败的计划！展现您的智能和适应性。\n"
            )

        # ===================================================================================
        # 老板，这里是为处理概念性问题新增/强化的部分！
        # ===================================================================================
        direct_qa_guidance = (
            "\n【重要：处理直接问答、概念解释或无需工具的请求】\n"
            "当用户的指令是提出一个概念性问题、请求解释、进行一般性对话，或任何你判断【不需要调用任何工具】就能直接回答的情况时，你【仍然必须严格遵循】下面的输出格式要求：\n"
            "1.  `<think>...</think>` 块：如常进行思考，解释你为什么认为这是一个可以直接回答的问题，以及你打算如何回答。\n"
            "2.  紧随其后的 JSON 对象：在此 JSON 对象中：\n"
            "    - `is_tool_calls` 字段【必须】设置为 `false`。\n"
            "    - `direct_reply` 字段【必须】包含你准备提供给用户的【完整、清晰、友好】的文本回答。这个回答应该是最终的，不需要后续处理。\n"
            "    - `tool_list` 字段此时【必须】为 `null` 或者一个空数组 `[]`。\n"
            "简而言之：即使是直接回答，也必须用我们约定的 `<think>` + JSON 结构来包装你的思考和回答内容。\n"
            "例如，如果用户问：“你好吗？”，你的输出应该是类似（仅为格式示例，具体思考和回复内容应根据实际情况）：\n"
            "<think>\n用户在进行日常问候，这是一个可以直接回答的问题，不需要工具。我将礼貌地回复。\n</think>\n"
            "{\n"
            "  \"is_tool_calls\": false,\n"
            "  \"tool_list\": null,\n" # 或者 [] 也可以，但 null 更简洁
            "  \"direct_reply\": \"您好！我目前一切正常，随时准备为您服务。有什么可以帮您的吗？\"\n"
            "}\n"
        )
        # ===================================================================================
        # 新增/强化部分结束
        # ===================================================================================

        return (
            "你是一位顶尖的、极其严谨的电路设计编程助理。你的行为必须专业、精确，并严格遵循指令。\n"
            "你的核心任务是：深入分析用户的最新指令、完整的对话历史（包括你之前的思考、规划以及所有工具执行结果），以及当前的电路状态。然后，你必须严格按照下面描述的固定格式，生成一个包含你行动计划的 JSON 对象。\n"
            f"{replanning_guidance}"
            f"{direct_qa_guidance}"  # <--- 老板，新的指导说明已加入！
            "【输出格式总览】\n"
            "你的输出必须由两部分组成，且严格按此顺序：\n"
            "1.  `<think>...</think>` XML 块：在此块中，详细阐述你的思考过程。这应包括：\n"
            "    - 对用户最新指令的精确理解。\n"
            "    - 对当前电路状态、历史对话和记忆的综合分析。\n"
            "    - 明确决定是否需要调用工具。如果需要，调用哪些工具，为什么，以及参数如何从指令中提取。如果不需要调用工具，则说明原因并准备直接回复。\n"
            "    - 规划具体的执行步骤和顺序（如果调用工具），或规划直接回复的内容（如果不调用工具）。\n"
            "    - 对潜在问题的评估和预案。\n"
            "    - 如果是重规划，必须详细分析之前工具失败的原因或计划缺陷，并清晰说明新计划如何修正这些问题。\n"
            "2.  紧随其后，不加任何其他文字、解释或注释，必须是一个单一的、格式完全正确的 JSON 对象。此 JSON 对象代表你最终的执行计划或直接回复。\n\n"
            "【JSON 对象格式规范 (必须严格遵守)】\n"
            "该 JSON 对象必须包含以下顶级字段：\n"
            "  A. `is_tool_calls` (boolean): 【必需】\n"
            "     - `true`: 如果分析后认为需要执行一个或多个工具操作来满足用户请求。\n"
            "     - `false`: 如果不需要执行任何工具（例如，可以直接回答问题、进行确认、或认为请求无法处理/需要澄清，此时答案放在`direct_reply`中）。\n"
            "  B. `tool_list` (array<object> | null): 【必需】其内容严格依赖于 `is_tool_calls` 的值：\n"
            "     - 当 `is_tool_calls` 为 `true` 时: 此字段【必须】是一个包含一个或多个“工具调用对象”的【数组】。数组中的对象必须按照你期望的执行顺序列出。\n"
            "     - 当 `is_tool_calls` 为 `false` 时: 此字段【必须】是 `null` 值或者一个【空数组 `[]`】。\n"
            "     【工具调用对象】结构 (如果 `tool_list` 非空):\n"
            "       1. `toolname` (string): 【必需】要调用的工具的精确名称。\n"
            "       2. `params` (object): 【必需】一个包含调用该工具所需参数的 JSON 对象。如果无参数，则为空对象 `{}`。\n"
            "       3. `index` (integer): 【必需】表示此工具调用在当前规划批次中的执行顺序，从 `1` 开始的正整数，且连续。\n"
            "  C. `direct_reply` (string | null): 【必需】其内容严格依赖于 `is_tool_calls` 的值：\n"
            "     - 当 `is_tool_calls` 为 `false` 时: 此字段【必须】包含你准备直接回复给用户的最终、完整、友好的文本内容。回复内容【禁止】为空字符串或仅包含空白。\n"
            "     - 当 `is_tool_calls` 为 `true` 时: 此字段【必须】是 `null` 值。\n\n"
            "【可用工具列表与参数规范】:\n"
            f"{tool_schemas_desc}\n\n"
            "【当前上下文信息】:\n"
            f"当前电路与记忆摘要:\n{memory_context}\n\n"
            "【最后再次强调】：你的回复格式必须严格是 `<think>思考过程</think>` 后面紧跟着一个符合上述所有规范的 JSON 对象。不允许有任何偏差！"
        )

    def _get_response_generation_prompt_v7(self, memory_context: str, tool_schemas_desc: str, tools_were_skipped_or_failed: bool) -> str:
        """构建最终响应生成调用的 System Prompt"""
        skipped_or_failed_guidance = ""
        if tools_were_skipped_or_failed:
            skipped_or_failed_guidance = (
                "\n【重要：处理失败或跳过的工具】\n"
                "在之前的工具执行过程中，可能由于某个工具最终失败，导致了后续工具被中止执行；或者计划本身存在缺陷。请在你的最终报告中：\n"
                "1. 明确指出哪些操作成功了，哪些失败了。\n"
                "2. 对于失败的操作，根据 'tool' 消息中的信息，向用户清晰、诚实地解释失败的原因及其影响。\n"
                "3. 如果有任务因此未能完成或被跳过，请明确说明。\n"
            )
        else:
             skipped_or_failed_guidance = (
                "\n【提示：总结成功操作】\n"
                "之前计划的所有工具操作（如果有的话）均已成功执行。请仔细阅读对话历史中角色为 'tool' 的消息，它们包含了每个已执行工具的详细结果。您应该：\n"
                "1. 根据这些成功结果，向用户确认所有操作均已按预期完成。\n"
                "2. 综合所有操作的结果，形成一个连贯、完整的最终回复。\n"
            )
        return (
            "你是一位顶尖的电路设计编程助理，经验丰富，技术精湛，并且极其擅长清晰、准确、诚实地汇报工作结果。\n"
            "你当前的核心任务是：基于到目前为止的【完整对话历史】（包括用户最初的指令、你之前的思考和规划、以及所有【已执行工具的结果详情】），生成最终的、面向用户的文本回复。\n"
            "【关键信息来源】: 角色为 'tool' 的消息，其 `content` 字段的 JSON 字符串包含了工具执行的 `status`, `message`, 和可能的 `error`。\n"
            "你的最终报告输出【必须】严格遵循以下两部分格式：\n"
            "1.  `<think>...</think>` XML 块：进行详细的【反思和报告组织思路】。\n"
            f"    {skipped_or_failed_guidance}"
            "2.  正式回复文本: 在 `</think>` 标签【之后】，紧跟着面向用户的【正式文本回复】。此回复应直接基于你在 `<think>` 块中的分析和规划。\n"
            "【最终输出格式示例 (必须严格遵守)】:\n"
            "`<think>\n在这里详细地写下你的思考过程...\n</think>\n\n您好！我已经成功为您完成了操作...`\n"
            "(注意：`</think>` 标签后必须恰好是【两个换行符 `\\n\\n`】，然后直接是正式回复文本。)\n"
            "【重要】：在这个阶段，你【绝对不能】再生成任何工具调用或 JSON 对象。\n\n"
            "【上下文参考信息 (仅供你回顾)】:\n"
            f"当前电路与记忆摘要:\n{memory_context}\n"
            f"我的可用工具列表 (仅供你参考):\n{tool_schemas_desc}\n"
            "请务必生成高质量、信息完整、格式正确的回复。"
        )


# --- 异步主函数 (应用程序入口) ---
async def main():
    """异步主函数，初始化 Agent 并启动主交互循环"""
    await async_print("=" * 70)
    await async_print("🚀 启动 OpenManus 电路设计 Agent (V7.2.1 Refactored with File Logging & Enhanced Q&A) 🚀") # 版本号更新
    await async_print("   特性: 异步核心, 对象化电路状态, 动态工具注册, LLM规划重试, 工具执行重试,")
    await async_print("         规划失败重规划, 内存修剪, 详细文件日志记录, 强化问答处理。") # 版本号更新
    await async_print("=" * 70)
    logger.info("[Main] 开始 Agent 初始化 (V7.2.1)...") # 版本号更新

    api_key_env = os.environ.get("ZHIPUAI_API_KEY")
    if not api_key_env:
        logger.warning("[Main] 环境变量 ZHIPUAI_API_KEY 未设置。将提示用户输入。")
        await async_print("\n为了连接智能大脑，我需要您的智谱AI API Key。")
        try: api_key_input = input("👉 请在此输入您的智谱AI API Key: ").strip()
        except (EOFError, KeyboardInterrupt): await async_print("\nAPI Key 输入被中断。程序退出。"); return
        if not api_key_input: await async_print("\n错误：未提供 API Key。程序退出。"); return
        final_api_key = api_key_input
        logger.info("[Main] 已通过手动输入获取 API Key。")
    else:
        final_api_key = api_key_env
        logger.info("[Main] 已从环境变量 ZHIPUAI_API_KEY 获取 API Key。")

    agent_instance = None
    try:
        agent_instance = CircuitDesignAgentV7(
            api_key=final_api_key,
            model_name="glm-4-flash-250414", # 常用模型，可以考虑配置化
            planning_llm_retries=1, max_tool_retries=2,
            tool_retry_delay_seconds=0.5, max_replanning_attempts=2,
            max_short_term_items=25
        )
        await async_print("\n🎉 Agent V7.2.1 初始化成功！已准备就绪。") # 版本号更新
        await async_print(f"ℹ️  提示: 详细日志正被记录到文件: {os.path.abspath(log_file_name)}")
        await async_print("\n您可以尝试以下指令:")
        await async_print("  - '给我加个1k电阻R1和3V电池B1'")
        await async_print("  - '连接R1和B1'")
        await async_print("  - '电路现在什么样？'")
        await async_print("  - '这个电路是如何实现功能的？'  <- 老板，这个现在应该能正确处理了！")
        await async_print("  - '清空电路'")
        await async_print("  - 输入 '退出' 来结束程序")
        await async_print("-" * 70)
    except Exception as e_agent_init:
        logger.critical(f"[Main] Agent V7.2.1 初始化失败: {e_agent_init}", exc_info=True) # 版本号更新
        error_msg_init = f"\n🔴 Agent 初始化失败！错误: {e_agent_init}。程序退出。"
        await async_print(error_msg_init)
        sys.stderr.write(error_msg_init + "\n"); sys.stderr.flush()
        return

    try:
        while True:
            user_input_str = ""
            try: user_input_str = input("用户 > ").strip()
            except KeyboardInterrupt: await async_print("\n用户中断输入。输入 '退出' 以结束。"); continue
            except EOFError: await async_print("\n输入流结束。正在退出..."); break

            if user_input_str.lower() in ['退出', 'quit', 'exit', '再见', '结束', 'bye']:
                await async_print("\n收到退出指令。感谢您的使用！👋"); break
            if not user_input_str: continue

            start_process_time_mono = time.monotonic()
            agent_response_str = ""
            try: agent_response_str = await agent_instance.process_user_request(user_input_str)
            except KeyboardInterrupt:
                await async_print("\n用户操作被中断。")
                logger.warning(f"[Main Loop] 用户中断了对指令 '{user_input_str[:50]}...' 的处理。")
                agent_response_str = "<think>用户中断了当前请求的处理。</think>\n\n操作已取消。"
            except Exception as e_process_req:
                logger.error(f"[Main Loop] 处理指令 '{user_input_str[:50]}...' 时发生意外错误: {e_process_req}", exc_info=True)
                tb_str_for_think = traceback.format_exc().replace('\n', ' | ')
                agent_response_str = f"<think>处理指令时发生内部错误: {e_process_req}. Traceback: {tb_str_for_think[:500]}...</think>\n\n抱歉，我在执行您的指令时遇到了意外问题！"
            
            process_duration_sec = time.monotonic() - start_process_time_mono
            await async_print(f"\n📝 Agent 回复 (总耗时: {process_duration_sec:.3f} 秒):")
            await async_print(agent_response_str)
            await async_print("-" * 70)
    except Exception as outer_loop_err:
        logger.critical(f"[Main Loop] 主交互循环外发生未处理异常: {outer_loop_err}", exc_info=True)
        await async_print(f"\n🔴 严重系统错误导致交互循环终止: {outer_loop_err}。")
    finally:
        logger.info("[Main] 主交互循环结束。")
        await async_print("\n正在关闭 Agent V7.2.1...") # 版本号更新


# --- 用于 Jupyter/IPython 环境的辅助函数 ---
async def run_agent_in_jupyter():
    """在 Jupyter/IPython 环境中安全启动 Agent 交互循环"""
    print("正在尝试以 Jupyter/IPython 兼容模式启动 Agent V7.2.1 Refactored...") # 版本号更新
    print("请在下方的输入提示处输入指令。输入 '退出' 结束。")
    print(f"Jupyter 模式下，日志同样会记录到: {os.path.abspath(log_file_name) if 'log_file_name' in globals() else '日志文件路径未确定'}")
    try: await main()
    except Exception as e_jupyter: print(f"\n🔴 Agent 在 Jupyter 模式下运行时遇到错误: {e_jupyter}"); logger.error(f"Jupyter 模式错误: {e_jupyter}", exc_info=True)
    finally: print("Agent 交互已结束 (Jupyter 模式)。")


# --- 标准 Python 脚本入口点 ---
if __name__ == "__main__":
    detected_shell_name = None
    try: detected_shell_name = get_ipython().__class__.__name__
    except NameError: detected_shell_name = "StandardPython"
    except Exception as e_get_ipython: logger.warning(f"检测 IPython 环境出错: {e_get_ipython}."); detected_shell_name = "StandardPython"

    if detected_shell_name == 'ZMQInteractiveShell':
        print("检测到 Jupyter/IPython (ZMQ) 环境。请在 cell 中执行 `await run_agent_in_jupyter()` 启动。")
        logger.info("Jupyter/IPython (ZMQ) 环境检测到。建议用户使用 await run_agent_in_jupyter()。")
    elif detected_shell_name in ['TerminalInteractiveShell', 'StandardPython']:
        if detected_shell_name == 'TerminalInteractiveShell': logger.info("Terminal IPython 环境检测到。标准模式启动。")
        else: logger.info("标准 Python 环境检测到。启动 Agent。")
        try: asyncio.run(main())
        except KeyboardInterrupt: print("\n程序被用户强制退出。"); logger.info("[Main Script] 程序被 KeyboardInterrupt 中断。")
        except Exception as e_top_level: print(f"\n程序因顶层错误而意外退出: {e_top_level}"); logger.critical(f"顶层异常: {e_top_level}", exc_info=True)
        finally: print("Agent V7.2.1 程序已关闭。") # 版本号更新
    else:
        logger.warning(f"检测到未知的 Shell 类型: {detected_shell_name}. 尝试标准模式启动。")
        try: asyncio.run(main())
        except KeyboardInterrupt: print("\n程序被用户强制退出。"); logger.info("[Main Script - Unknown Shell] 程序被 KeyboardInterrupt 中断。")
        except Exception as e_top_level_unknown: print(f"\n程序因顶层错误而意外退出: {e_top_level_unknown}"); logger.critical(f"顶层异常 (未知 Shell): {e_top_level_unknown}", exc_info=True)
        finally: print("Agent V7.2.1 程序已关闭 (未知 Shell 环境)。") # 版本号更新