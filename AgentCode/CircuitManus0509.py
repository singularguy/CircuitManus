# @FileName: openmanus_v7_agent_verbose_switch.py # 文件名更新
# @Version: V7.2.3 - Streaming LLM Interaction (Internal), Full Code, Detailed Comments
# @Author: Your Most Loyal & Dedicated Programmer (Refactored & Enhanced with Streaming)
# @Date: [Current Date] - Implemented Internal Streaming for LLM Calls
# @License: MIT License
# @Description:
# ==============================================================================================
#  Manus 系统 V7.2.3 技术实现说明 (新增后台输出详细/简洁切换, LLM内部流式交互)
# ==============================================================================================
#
# 本脚本实现了一个用于电路设计的异步 Agent. 
#
# 本次 V7.2.3 的核心改进 (在 V7.2.2 基础上):
# 1. LLM 交互层实现内部流式接收:
#    - 在调用智谱AI的 chat.completions.create 方法时,设置 stream=True. 
#    - 在 LLMInterface.call_llm 方法内部,异步迭代接收 LLM 返回的每一个数据块 (chunk). 
#    - 将所有数据块中的文本内容 (content) 拼接起来,形成完整的响应文本. 
#    - 在流式接收完成后,将完整的文本内容构建成一个模拟的非流式响应对象,返回给 Agent 的 Orchestrator 层. 
#    - 这种方式使得 Agent 在等待 LLM 响应时能够利用流式特性(例如,如果SDK支持,可以更快收到首个token),同时不改变Agent Orchestrator层对完整响应的需求,最大程度降低了对现有逻辑的侵入. 
#    - 动态等待提示 (Verbose模式下) 在整个流式接收过程中持续显示,直到接收完毕. 
#
# 继承 V7.2.2 的核心改进:
# 1.  后台输出详细/简洁切换: Agent 初始化时可通过 `verbose` 参数控制控制台输出的详细程度. 
#     - `verbose=True` (默认): 显示详细的 DEBUG 日志和内部处理状态打印. 
#     - `verbose=False`: 仅显示 INFO 及以上级别的日志和最终的用户回复,隐藏内部细节. 
#     - 通过动态调整控制台日志处理器级别和条件化打印实现. 
#
# 重申 V7.2.1 的核心改进:
# 1.  强化规划提示,更好地处理直接问答/概念解释. 
# 2.  LLM 调用时显示动态等待提示 (现在受 verbose 控制). 
#
# ... (继承 V7.2 和 V7.1 的所有特性) ...
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
# 导入用于构建模拟响应对象的 Pydantic 模型部分(通常是 SDK 内部使用,这里模拟结构)
# 注意: 我们不需要真的导入SDK的Pydantic模型,只需要知道结构并手动构建字典即可. 
# 为了代码的健壮性和可读性,这里直接构建嵌套字典,模拟API响应的结构. 
# from zhipuai.types.chat.chat_completion import ChatCompletionMessageParam # 仅用于参考结构

# --- 全局异步事件循环 ---
# 尝试获取当前正在运行的事件循环. 
# 如果没有正在运行的循环 (例如,在标准脚本的顶部运行),则创建一个新的事件循环并设置为当前循环. 
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# --- 日志系统配置 ---
LOG_DIR = "agent_logs"
# 创建日志目录,如果不存在的话
try:
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
except OSError as e:
    # 如果创建目录失败,打印关键错误信息到标准错误流,并继续运行但不进行文件日志记录
    sys.stderr.write(f"CRITICAL: Could not create log directory '{LOG_DIR}'. Error: {e}\n")
    sys.stderr.write("File logging may be unavailable. Continuing with console logging only.\n")

# 生成带时间戳和进程 ID 的日志文件名,确保文件名唯一且可追溯
current_time_for_log = datetime.now()
log_file_name = os.path.join(
    LOG_DIR,
    f"agent_log_{current_time_for_log.strftime('%Y%m%d_%H%M%S')}_{current_time_for_log.microsecond // 1000:03d}_P{os.getpid()}.log"
)

# 定义日志格式
log_format = '%(asctime)s - %(name)s - %(levelname)s [%(module)s.%(funcName)s:%(lineno)d] - %(message)s'

# **修改点**: 保留对 console_handler 的引用,以便后续根据 verbose 参数修改级别
console_handler = logging.StreamHandler(sys.stderr)
# **修改点**: 初始级别设为 DEBUG,Agent 初始化时会根据 verbose 参数再调整
# 这样即使在 Agent 初始化前有 DEBUG 级别的日志,它们也会被处理器接收,
# 但实际是否输出取决于处理器的当前级别. 
console_handler.setLevel(logging.DEBUG) 
console_handler.setFormatter(logging.Formatter(log_format))

# 获取根 logger 并设置其级别为最低 (DEBUG),让 Handler 来控制实际输出级别
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG) # 根 logger 级别设为最低,由 handler 控制实际输出
root_logger.addHandler(console_handler) # 添加控制台处理器

# 创建一个特定于本模块的 logger
logger = logging.getLogger(__name__)

# 配置文件日志处理器
try:
    # 使用 'a' 模式表示追加,encoding='utf-8' 支持中文
    file_handler = logging.FileHandler(log_file_name, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG) # 文件日志始终保持 DEBUG 级别,记录所有详细信息
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)
    logger.info(f"Successfully configured file logging. Log messages will also be saved to: {os.path.abspath(log_file_name)}")
except Exception as e:
    # 如果文件日志配置失败,记录关键错误信息到控制台和(如果控制台处理器工作)日志
    logger.error(f"CRITICAL: Failed to configure file logging to '{log_file_name}'. Error: {e}", exc_info=True)
    logger.error("Agent will continue with console logging only.")

# 降低一些库的日志级别,避免它们产生过多的DEBUG/INFO日志干扰 Agent 的核心日志
logging.getLogger("zhipuai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


# --- 异步友好的打印函数 ---
# **修改点**: async_print 现在接受一个可选的 verbose 参数
async def async_print(message: str, end: str = '\n', flush: bool = True, *, verbose_only: bool = False, agent_verbose_flag: bool = True):
    """
    一个在异步环境中安全打印的函数,避免直接使用 print 导致的潜在问题. 
    它通过 asyncio.to_thread 将同步的 sys.stdout.write 放到一个单独的线程中执行. 
    
    新增: verbose_only 参数. 如果设为 True,则只有当 agent_verbose_flag 为 True (Agent 处于详细模式) 时,该消息才会被打印. 
    新增: agent_verbose_flag 参数. 需要从调用方传入 Agent 当前的详细模式设置. 
    这允许我们在详细模式下打印额外的调试信息或过程提示,而在简洁模式下隐藏它们. 
    """
    # 如果 verbose_only 为 True,且 Agent 不处于详细模式,则直接返回,不打印任何内容
    if verbose_only and not agent_verbose_flag:
        return 
        
    # 使用 asyncio.to_thread 安全地执行同步的 sys.stdout.write 和 flush
    # await asyncio.to_thread(sys.stdout.write, message + end) # 原始简化版,flush需要单独处理
    # 更精确地模拟print的行为,包括可选的flush
    await asyncio.to_thread(lambda: (sys.stdout.write(message + end), sys.stdout.flush() if flush else None))


# --- 电路元件数据类 ---
class CircuitComponent:
    """电路元件的数据结构及基本验证"""
    # 使用 __slots__ 优化内存,特别是在有大量元件对象时
    __slots__ = ['id', 'type', 'value'] 
    
    def __init__(self, component_id: str, component_type: str, value: Optional[str] = None):
        # 验证输入参数的基本有效性
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError("元件 ID 必须是有效的非空字符串")
        if not isinstance(component_type, str) or not component_type.strip():
            raise ValueError("元件类型必须是有效的非空字符串")
            
        # 存储处理后的参数,ID 转换为大写以便不区分大小写处理
        self.id: str = component_id.strip().upper()
        self.type: str = component_type.strip()
        # 值可以为 None,如果提供了则去除空白
        self.value: Optional[str] = str(value).strip() if value is not None and str(value).strip() else None
        
        logger.debug(f"成功创建元件对象: {self}")

    def __str__(self) -> str:
        """返回用户友好的元件描述字符串"""
        value_str = f" (值: {self.value})" if self.value else ""
        return f"元件: {self.type} (ID: {self.id}){value_str}"

    def __repr__(self) -> str:
        """返回用于调试的元件对象的表示形式"""
        return f"CircuitComponent(id='{self.id}', type='{self.type}', value={repr(self.value)})"

    def to_dict(self) -> Dict[str, Any]:
        """将元件对象转换为字典,方便序列化或在结果中返回"""
        return {"id": self.id, "type": self.type, "value": self.value}


# --- 电路实体类 ---
class Circuit:
    """封装所有电路状态相关的逻辑和数据"""
    def __init__(self):
        logger.info("[Circuit] 初始化电路实体. ")
        # 存储元件的字典,键是元件 ID,值是 CircuitComponent 对象
        self.components: Dict[str, CircuitComponent] = {} 
        # 存储连接的集合,每个连接是一个包含两个元件 ID 的元组 (排序后),例如 ('R1', 'B1')
        self.connections: Set[Tuple[str, str]] = set() 
        # 存储用于生成唯一元件 ID 的计数器,按类型前缀分类
        self._component_counters: Dict[str, int] = {
            'R': 0, 'L': 0, 'B': 0, 'S': 0, 'C': 0, 'V': 0, 'G': 0, 'U': 0, 'O': 0,
            'I': 0, 'A': 0, 'D': 0, 'P': 0, 'F': 0, 'H': 0
        }
        logger.info("[Circuit] 电路实体初始化完成. ")

    def add_component(self, component: CircuitComponent):
        """添加元件到电路的内部状态"""
        if component.id in self.components:
            # 如果 ID 已存在,抛出错误
            raise ValueError(f"元件 ID '{component.id}' 已被占用. ")
        self.components[component.id] = component
        logger.debug(f"[Circuit] 元件 '{component.id}' 已添加到电路. ")

    def remove_component(self, component_id: str):
        """从电路中移除指定 ID 的元件及其相关的连接"""
        comp_id_upper = component_id.strip().upper()
        if comp_id_upper not in self.components:
            # 如果元件不存在,抛出错误
            raise ValueError(f"元件 '{comp_id_upper}' 在电路中不存在. ")
            
        # 从元件字典中删除
        del self.components[comp_id_upper]
        
        # 查找并移除所有涉及该元件的连接
        connections_to_remove = {conn for conn in self.connections if comp_id_upper in conn}
        for conn in connections_to_remove:
            self.connections.remove(conn)
            logger.debug(f"[Circuit] 移除了涉及元件 '{comp_id_upper}' 的连接 {conn}.")
            
        logger.debug(f"[Circuit] 元件 '{comp_id_upper}' 及其相关连接已从电路中移除. ")


    def connect_components(self, id1: str, id2: str):
        """连接两个指定 ID 的元件"""
        id1_upper = id1.strip().upper()
        id2_upper = id2.strip().upper()

        # 验证两个 ID 是否相同
        if id1_upper == id2_upper:
            raise ValueError(f"不能将元件 '{id1}' 连接到它自己. ")
            
        # 验证两个元件 ID 是否都存在于电路中
        if id1_upper not in self.components:
             raise ValueError(f"元件 '{id1}' 在电路中不存在. ")
        if id2_upper not in self.components:
             raise ValueError(f"元件 '{id2}' 在电路中不存在. ")

        # 创建连接元组,通过 sorted 确保连接顺序不影响识别 (R1, B1) 和 (B1, R1) 是同一个连接
        connection = tuple(sorted((id1_upper, id2_upper)))
        
        if connection in self.connections:
             logger.warning(f"[Circuit] 连接 '{id1_upper}' <--> '{id2_upper}' 已存在. ")
             return False # 连接已存在,无需重复添加

        self.connections.add(connection)
        logger.debug(f"[Circuit] 添加了连接: {id1_upper} <--> {id2_upper}.")
        return True # 连接成功添加

    def disconnect_components(self, id1: str, id2: str):
        """断开两个指定 ID 的元件的连接"""
        id1_upper = id1.strip().upper()
        id2_upper = id2.strip().upper()
        
        # 创建连接元组,用于查找
        connection = tuple(sorted((id1_upper, id2_upper)))

        if connection not in self.connections:
             logger.warning(f"[Circuit] 连接 '{id1_upper}' <--> '{id2_upper}' 不存在,无需断开. ")
             return False # 连接不存在

        self.connections.remove(connection)
        logger.debug(f"[Circuit] 断开了连接: {id1_upper} <--> {id2_upper}.")
        return True # 连接成功断开

    def get_state_description(self) -> str:
        """生成当前电路状态的文本描述,用于提供给 LLM 作为上下文"""
        logger.debug("[Circuit] 正在生成电路状态描述...")
        num_components = len(self.components)
        num_connections = len(self.connections)

        # 如果电路为空,返回简单描述
        if num_components == 0 and num_connections == 0:
            return "【当前电路状态】: 电路为空. "

        desc_lines = ["【当前电路状态】:"]
        desc_lines.append(f"  - 元件 ({num_components}):")
        if self.components:
            # 按 ID 字母顺序排序元件,方便阅读
            sorted_ids = sorted(self.components.keys())
            for cid in sorted_ids:
                desc_lines.append(f"    - {str(self.components[cid])}")
        else:
            desc_lines.append("    (无)")

        desc_lines.append(f"  - 连接 ({num_connections}):")
        if self.connections:
            # 按连接元组排序连接,方便阅读
            sorted_connections = sorted(list(self.connections))
            for c1, c2 in sorted_connections:
                desc_lines.append(f"    - {c1} <--> {c2}")
        else:
            desc_lines.append("    (无)")

        description = "\n".join(desc_lines)
        logger.debug("[Circuit] 电路状态描述生成完毕. ")
        return description

    def generate_component_id(self, component_type: str) -> str:
        """为给定类型的元件生成唯一的 ID (例如 R1, C2, B3)"""
        logger.debug(f"[Circuit] 正在为类型 '{component_type}' 生成唯一 ID...")
        # 定义元件类型到 ID 前缀的映射
        type_map = {
            "resistor": "R", "电阻": "R", "capacitor": "C", "电容": "C",
            "battery": "B", "电池": "B", "voltage source": "V", "voltage": "V",
            "电压源": "V", "电压": "V", "led": "L", "发光二极管": "L", "switch": "S",
            "开关": "S", "ground": "G", "地": "G", "ic": "U", "chip": "U", "芯片": "U",
            "集成电路": "U", "inductor": "I", "电感": "I", "current source": "A",
            "电流源": "A", "diode": "D", "二极管": "D", "potentiometer": "P", "电位器": "P",
            "fuse": "F", "保险丝": "F", "header": "H", "排针": "H",
            "component": "O", "元件": "O", # 默认或未知类型使用 'O'
        }
        
        # 确保所有映射到的前缀都在计数器中初始化
        for code in type_map.values():
            if code not in self._component_counters:
                 self._component_counters[code] = 0

        cleaned_type = component_type.strip().lower()
        type_code = "O" # 默认前缀
        best_match_len = 0 # 用于找到最匹配的前缀(如果用户输入是复合词)
        
        # 根据用户输入的类型,查找最长的匹配关键词,确定 ID 前缀
        for keyword, code in type_map.items():
            if keyword in cleaned_type and len(keyword) > best_match_len:
                type_code = code
                best_match_len = len(keyword)

        # 如果使用了通用前缀,并且用户输入的不是明确的通用词,则发出警告
        if type_code == "O" and cleaned_type not in ["component", "元件"]:
             logger.warning(f"[Circuit] 未找到类型 '{component_type}' 的特定前缀,将使用通用前缀 'O'. ")

        MAX_ID_ATTEMPTS = 100 # 最多尝试生成 ID 的次数,防止死循环
        for attempt in range(MAX_ID_ATTEMPTS):
            self._component_counters[type_code] += 1 # 计数器递增
            gen_id = f"{type_code}{self._component_counters[type_code]}" # 生成新的 ID
            if gen_id not in self.components:
                logger.debug(f"[Circuit] 生成唯一 ID: '{gen_id}' (尝试 {attempt + 1})")
                return gen_id # 找到了一个未被占用的唯一 ID,返回

        # 如果尝试了最大次数仍未能生成唯一 ID,则抛出运行时错误
        raise RuntimeError(f"未能为类型 '{component_type}' (代码 '{type_code}') 生成唯一 ID ({MAX_ID_ATTEMPTS} 次尝试后). ")

    def clear(self):
        """彻底清空当前电路的所有元件和连接,并重置 ID 计数器"""
        logger.info("[Circuit] 正在清空电路状态...")
        comp_count = len(self.components)
        conn_count = len(self.connections)
        
        # 清空元件和连接
        self.components = {}
        self.connections = set()
        
        # 重置所有 ID 计数器为 0
        self._component_counters = {k: 0 for k in self._component_counters}
        
        logger.info(f"[Circuit] 电路状态已清空 (移除了 {comp_count} 个元件, {conn_count} 个连接,并重置了所有 ID 计数器). ")

# --- 工具注册装饰器 ---
def register_tool(description: str, parameters: Dict[str, Any]):
    """
    装饰器,用于标记 Agent 的方法为可调用工具,并附加该工具的 Schema (描述和参数). 
    这些 Schema 会被提供给 LLM,帮助它了解 Agent 有哪些能力以及如何调用. 
    """
    def decorator(func):
        # 将工具的 Schema 和一个标记其为工具的属性附加到函数对象上
        func._tool_schema = {"description": description, "parameters": parameters}
        func._is_tool = True
        
        # functools.wraps 用于保留原始函数的元信息 (如函数名、docstring 等)
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # wrapper 只是简单地调用原始函数
            return func(*args, **kwargs)
        return wrapper
    return decorator


# --- 模块化组件: MemoryManager ---
class MemoryManager:
    """记忆管理器,负责存储和管理 Agent 的所有记忆信息"""
    def __init__(self, max_short_term_items: int = 20, max_long_term_items: int = 50):
        logger.info("[MemoryManager] 初始化记忆模块...")
        # 验证短期记忆上限,确保至少能存储一对用户/Agent 交互
        if max_short_term_items <= 1:
            raise ValueError("max_short_term_items 必须大于 1")
            
        self.max_short_term_items = max_short_term_items # 短期记忆(对话历史)的最大条数
        self.max_long_term_items = max_long_term_items # 长期记忆(知识片段)的最大条数
        
        # 短期记忆: 存储对话历史消息列表,每条消息是一个字典 {"role": ..., "content": ...}
        self.short_term: List[Dict[str, Any]] = [] 
        # 长期记忆: 存储关键的知识片段或经验总结,是一个字符串列表
        self.long_term: List[str] = [] 
        
        # 电路对象实例,表示当前电路的状态,这是 Agent 的核心工作空间
        self.circuit: Circuit = Circuit() 

        logger.info(f"[MemoryManager] 记忆模块初始化完成. 短期上限: {max_short_term_items} 条, 长期上限: {max_long_term_items} 条. ")

    def add_to_short_term(self, message: Dict[str, Any]):
        """
        添加消息到短期记忆 (对话历史),如果超出上限,则移除最旧的非系统消息. 
        System 消息通常包含重要的指令,应尽量保留. 
        """
        logger.debug(f"[MemoryManager] 添加消息到短期记忆 (Role: {message.get('role', 'N/A')}). 当前数量: {len(self.short_term)}")
        self.short_term.append(message)

        current_size = len(self.short_term)
        if current_size > self.max_short_term_items:
            logger.debug(f"[MemoryManager] 短期记忆超限 ({current_size}/{self.max_short_term_items}),执行修剪...")
            items_to_remove = current_size - self.max_short_term_items
            
            # 找出所有非 'system' 消息的索引
            non_system_indices = [i for i, msg in enumerate(self.short_term) if msg.get("role") != "system"]
            # 实际要移除的数量,最多不超过需要移除的总数和非 system 消息的总数
            num_to_actually_remove = min(items_to_remove, len(non_system_indices))
            
            if num_to_actually_remove > 0:
                # 确定要移除的最旧的非 system 消息的索引
                indices_to_remove_set = set(non_system_indices[:num_to_actually_remove])
                # 记录被移除消息的角色,用于日志
                removed_roles = [self.short_term[i].get('role', 'N/A') for i in sorted(list(indices_to_remove_set))]
                # 构建新的短期记忆列表,排除要移除的索引对应的消息
                new_short_term = [msg for i, msg in enumerate(self.short_term) if i not in indices_to_remove_set]
                self.short_term = new_short_term
                logger.info(f"[MemoryManager] 短期记忆修剪完成,移除了 {num_to_actually_remove} 条最旧的非系统消息 (Roles: {removed_roles}). ")
            elif items_to_remove > 0:
                 logger.warning(f"[MemoryManager] 短期记忆超限 ({current_size}/{self.max_short_term_items}) 但未能找到足够的非系统消息进行移除 (可能全部是 system 消息). ")

        logger.debug(f"[MemoryManager] 添加后短期记忆数量: {len(self.short_term)}")

    def add_to_long_term(self, knowledge_snippet: str):
        """
        添加知识片段到长期记忆. 如果超出上限,移除最旧的片段 (FIFO 策略). 
        长期记忆可以存储一些重要的状态变化或用户提供的关键信息总结. 
        """
        logger.debug(f"[MemoryManager] 添加知识到长期记忆: '{knowledge_snippet[:100]}{'...' if len(knowledge_snippet) > 100 else ''}'. 当前数量: {len(self.long_term)}")
        self.long_term.append(knowledge_snippet)
        if len(self.long_term) > self.max_long_term_items:
            removed = self.long_term.pop(0) # 移除列表的第一个元素 (最旧的)
            logger.info(f"[MemoryManager] 长期记忆超限 ({self.max_long_term_items}), 移除最旧知识: '{removed[:50]}...'")
        logger.debug(f"[MemoryManager] 添加后长期记忆数量: {len(self.long_term)}")

    def get_circuit_state_description(self) -> str:
        """获取当前电路状态的文本描述,由 Circuit 对象提供"""
        return self.circuit.get_state_description()

    def get_memory_context_for_prompt(self, recent_long_term_count: int = 5) -> str:
        """
        格式化非对话历史的记忆上下文,用于构建发送给 LLM 的 System Prompt. 
        这包括当前的电路状态描述和最近的长期记忆片段. 
        """
        logger.debug("[MemoryManager] 正在格式化记忆上下文用于 Prompt...")
        circuit_desc = self.get_circuit_state_description()
        long_term_str = ""
        if self.long_term:
            # 只获取最近期的长期记忆片段,限制数量以避免 Prompt 过长
            actual_count = min(recent_long_term_count, len(self.long_term))
            if actual_count > 0:
                recent_items = self.long_term[-actual_count:] # 获取列表末尾的元素
                long_term_str = "\n\n【近期经验总结 (仅显示最近 N 条)】\n" + "\n".join(f"- {item}" for item in recent_items)
                logger.debug(f"[MemoryManager] 已提取最近 {len(recent_items)} 条长期记忆 (基础模式). ")
        
        # 添加一个说明,提示 LLM 当前的长期记忆处理方式
        long_term_str += "\n(注: 当前仅使用最近期记忆,未来版本将实现基于相关性的检索)"
        
        context = f"{circuit_desc}{long_term_str}".strip()
        logger.debug(f"[MemoryManager] 记忆上下文 (电路+长期) 格式化完成. ")
        return context

# --- 模块化组件: LLMInterface ---
class LLMInterface:
    """封装与大语言模型 (LLM) 的异步交互,包括内部流式接收和处理"""
    def __init__(self, agent_instance: 'CircuitDesignAgentV7', model_name: str = "glm-4-flash-250414", default_temperature: float = 0.1, default_max_tokens: int = 4095):
        # **修改点**: 接收 Agent 实例以获取 API Key 和 verbose 设置
        logger.info(f"[LLMInterface] 初始化 LLM 接口,目标模型: {model_name}")
        
        # 验证 Agent 实例是否有效
        if not agent_instance or not hasattr(agent_instance, 'api_key') or not hasattr(agent_instance, 'verbose_mode'):
             raise ValueError("LLMInterface 需要一个包含 'api_key' 和 'verbose_mode' 属性的 Agent 实例. ")
             
        self.agent_instance = agent_instance # 保存 agent 实例引用,用于获取配置和 verbose 状态
        api_key = self.agent_instance.api_key # 从 agent 获取 API key
        if not api_key: raise ValueError("智谱 AI API Key 不能为空")

        try:
            # 初始化智谱 AI 客户端
            self.client = ZhipuAI(api_key=api_key)
            logger.info("[LLMInterface] 智谱 AI 客户端初始化成功. ")
        except Exception as e:
            # 如果客户端初始化失败,记录关键错误并抛出连接错误
            logger.critical(f"[LLMInterface] 初始化智谱 AI 客户端失败: {e}", exc_info=True)
            raise ConnectionError(f"初始化智谱 AI 客户端失败: {e}") from e
            
        self.model_name = model_name
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens
        
        logger.info(f"[LLMInterface] LLM 接口初始化完成 (Model: {model_name}, Temp: {default_temperature}, MaxTokens: {default_max_tokens}). ")

    async def _dynamic_llm_wait_indicator(self, stop_event: asyncio.Event, initial_message: str = "正在与智能大脑沟通"):
        """
        内部异步函数,用于在等待LLM响应时显示动态提示动画(仅在 verbose 模式下有效). 
        这个函数在一个单独的 Task 中运行,直到接收到停止事件. 
        """
        animation_chars = ['|', '/', '-', '\\']
        idx = 0
        padding = " " * 20 # 用于覆盖可能残留的字符,确保动态提示不留痕迹
        
        try:
            # 首次打印动态提示,使用 async_print 并根据 Agent 的 verbose 模式进行控制
            await async_print(f"\r{initial_message} {animation_chars[idx % len(animation_chars)]}{padding}", end="", verbose_only=True, agent_verbose_flag=self.agent_instance.verbose_mode)
            
            # 循环显示动画,直到 stop_event 被设置
            while not stop_event.is_set():
                await asyncio.sleep(0.15) # 控制动画更新速度
                if stop_event.is_set(): # 在睡眠后再次检查事件,避免在事件刚设置后还打印一次
                    break
                idx += 1
                # 更新动态提示,使用 async_print 并根据 Agent 的 verbose 模式进行控制
                await async_print(f"\r{initial_message} {animation_chars[idx % len(animation_chars)]}{padding}", end="", verbose_only=True, agent_verbose_flag=self.agent_instance.verbose_mode)
        except asyncio.CancelledError:
            # Task 被取消时的处理(例如,Agent 退出时可能取消这个 Task)
            logger.debug("[LLMInterface] 动态提示任务被取消. ")
        except Exception as e:
            # 记录动态提示任务中的意外错误
            logger.error(f"[LLMInterface] 动态提示任务发生错误: {e}", exc_info=True)
        finally:
            # 确保最后清除动态提示行,无论任务是正常结束还是被取消/出错
            # 使用 async_print 并根据 Agent 的 verbose 模式进行控制
            await async_print(f"\r{' ' * (len(initial_message) + 2 + len(padding))}\r", end="", verbose_only=True, agent_verbose_flag=self.agent_instance.verbose_mode) # 使用等长空白字符覆盖原提示,然后回车

    # **修改点**: 此方法现在实现了内部的流式接收和完整响应构建
    async def call_llm(self, messages: List[Dict[str, Any]], use_tools: bool = False, tool_choice: Optional[str] = None) -> Any:
        """
        异步调用 LLM API. 
        此实现通过 stream=True 方式调用 API,在内部接收所有流式 chunk,
        拼接完整的响应内容,并构建一个模拟的完整响应对象返回. 
        
        注意: 当前 Agent 的规划和响应生成逻辑依赖于接收完整的文本内容进行自定义解析,
              因此这里的流式处理是在 LLMInterface 内部完成接收和拼接,
              外部调用者 (Orchestrator) 仍然接收一个完整的响应对象. 
              use_tools 和 tool_choice 参数保留但当前 Agent 不通过 SDK 的 tool_calls 字段进行规划解析,
              而是解析 content 字段中的自定义 JSON. 因此,调用时通常传入 use_tools=False. 
        """
        # 构建调用 API 的参数字典
        call_args = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens,
            "stream": True, # <-- 核心改动: 启用流式模式
        }

        logger.info(f"[LLMInterface] 准备异步调用 LLM ({self.model_name},自定义 JSON/无内置工具模式),使用内部流式接收...")
        logger.debug(f"[LLMInterface] 发送的消息条数: {len(messages)}")
        # 记录发送消息的预览 (DEBUG 级别)
        if logger.isEnabledFor(logging.DEBUG) and len(messages) > 0:
             try:
                 # 截断长消息内容,防止日志过长
                 messages_summary = json.dumps([{"role": m.get("role"), "content_preview": str(m.get("content"))[:100] + "..." if len(str(m.get("content", ""))) > 100 else str(m.get("content"))} for m in messages[-3:]], ensure_ascii=False, indent=2)
                 logger.debug(f"[LLMInterface] 最新消息列表 (预览): \n{messages_summary}")
             except Exception as e_json:
                 logger.debug(f"[LLMInterface] 无法序列化消息列表进行调试日志: {e_json}")

        # --- 动态等待提示 ---
        # 创建一个事件对象,用于通知动态提示 Task 停止
        stop_indicator_event = asyncio.Event()
        indicator_task = None
        # **修改点**: 仅在 verbose 模式下启动动态提示 Task
        if self.agent_instance.verbose_mode:
            initial_prompt_for_indicator = "🧠 正在思考请稍候"
            # 根据消息历史判断是规划阶段还是生成最终回复阶段,调整提示信息
            # 如果最新消息是 user,大概率是规划；如果最新消息是 tool,大概率是生成回复
            is_planning_phase = True
            if len(messages) > 1 and messages[-1].get("role") == "user":
                pass # 是规划阶段
            elif any(msg.get("role") == "tool" for msg in messages):
                is_planning_phase = False # 不是规划阶段,可能是生成最终回复
                initial_prompt_for_indicator = "📝 正在生成回复"
            # 创建动态提示的 Task,并在后台运行
            indicator_task = asyncio.create_task(self._dynamic_llm_wait_indicator(stop_indicator_event, initial_prompt_for_indicator))
        # --- 动态等待提示结束 ---

        accumulated_content = "" # 用于拼接流式接收到的文本内容
        final_response_data = {} # 用于存储从流中获取的最终响应信息 (finish_reason, usage等)
        
        try:
            start_time = time.monotonic()
            
            # 使用 asyncio.to_thread 在一个单独的线程中运行同步的 API 调用和流式接收循环
            # 这样做是为了不阻塞主事件循环,因为 ZhipuAI SDK 的迭代器可能是同步的
            stream_response = await asyncio.to_thread(
                self.client.chat.completions.create,
                **call_args
            )
            
            logger.debug("[LLMInterface] 开始异步迭代处理 LLM 流式响应...")
            
            # 迭代处理流式响应的每一个 chunk
            for chunk in stream_response:
                # 检查 chunk 结构是否符合预期
                if not chunk or not chunk.choices or len(chunk.choices) == 0:
                    logger.warning("[LLMInterface] 接收到无效或空 chunk. ")
                    continue
                    
                delta = chunk.choices[0].delta
                
                # 拼接文本内容
                if delta and delta.content:
                    accumulated_content += delta.content
                    logger.debug(f"[LLMInterface] 接收到 content chunk (长度: {len(delta.content)}). 累计长度: {len(accumulated_content)}")
                
                # 捕获 finish_reason 和 usage (通常在最后一个 chunk)
                if chunk.choices[0].finish_reason:
                    final_response_data['finish_reason'] = chunk.choices[0].finish_reason
                    logger.debug(f"[LLMInterface] 接收到 finish_reason: {final_response_data['finish_reason']}")
                
                if chunk.usage:
                    final_response_data['usage'] = chunk.usage
                    logger.debug(f"[LLMInterface] 接收到 usage 信息: {chunk.usage}")
                    
                # TODO: 如果需要处理 tool_calls(尽管当前 Agent 不依赖),需要在此处实现 tool_calls 的累积和合并逻辑

            duration = time.monotonic() - start_time
            logger.info(f"[LLMInterface] LLM 流式接收完成. 耗时: {duration:.3f} 秒. ")
            
            # --- 构建模拟的完整响应对象 ---
            # 构建一个字典,模拟非流式 API 调用返回的 ChatCompletion 对象结构
            # 至少包含 OutputParser 需要访问的路径: .choices[0].message.content, .choices[0].finish_reason, .usage
            # 注意: 这里我们手动构建字典结构,而不是使用 Pydantic 模型,以减少依赖并简化
            mock_response_object = {
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant", # 假设 LLM 响应的角色是 assistant
                            "content": accumulated_content, # 拼接完整的文本内容
                            # 如果将来需要 tool_calls,可以在这里添加
                            # "tool_calls": ... 
                        },
                        "finish_reason": final_response_data.get('finish_reason', 'unknown'),
                    }
                ],
                "model": self.model_name,
                "usage": final_response_data.get('usage'), # 添加 usage 信息
                # 其他可能的字段如 id, created 等这里暂不模拟,如果需要可以从第一个或最后一个 chunk 提取
                "id": getattr(stream_response, 'id', 'mock_id'), # 尝试从流对象本身获取ID,或使用模拟ID
                "created": getattr(stream_response, 'created', int(time.time())), # 尝试获取创建时间,或使用当前时间
                "object": "chat.completion", # 模拟对象类型
            }
            logger.debug("[LLMInterface] 已构建模拟的完整响应对象. ")

            if final_response_data.get('finish_reason') == 'length':
                logger.warning("[LLMInterface] LLM 响应因达到最大 token 限制而被截断!")

            return mock_response_object # 返回模拟的完整响应对象给调用方

        except Exception as e:
            # 如果在调用 API 或处理流的过程中发生任何错误
            logger.error(f"[LLMInterface] LLM API 调用或流式处理失败: {e}", exc_info=True)
            
            # 清理动态提示(确保在错误发生时也停止)
            stop_indicator_event.set()
            if indicator_task:
                try: await indicator_task
                except asyncio.CancelledError: pass # 忽略取消错误
                except Exception as e_indicator_cleanup: logger.error(f"[LLMInterface] 清理动态提示任务时出错: {e_indicator_cleanup}", exc_info=True)

            raise # 重新抛出异常,让上层调用者处理

        finally:
            # --- 清理动态提示 ---
            # 无论成功或失败,都要确保停止动态提示 Task
            stop_indicator_event.set()
            if indicator_task: # 仅当任务被创建时才等待
                try:
                    await indicator_task
                except asyncio.CancelledError:
                    logger.debug("[LLMInterface] 动态提示任务被取消. ")
                except Exception as e_indicator_cleanup:
                    # 记录清理动态提示任务时可能发生的错误
                    logger.error(f"[LLMInterface] 清理动态提示任务时出错: {e_indicator_cleanup}", exc_info=True)
            # --- 清理结束 ---

# --- 模块化组件: OutputParser ---
class OutputParser:
    """
    负责解析 LLM 返回的响应,特别是规划阶段的 `<think>` 块和自定义 JSON 计划,
    以及最终响应阶段的 `<think>` 块和最终回复文本. 
    """
    def __init__(self):
        logger.info("[OutputParser] 初始化输出解析器 (用于自定义 JSON 和文本解析). ")

    def parse_planning_response(self, response_message: Any) -> Tuple[str, Optional[Dict[str, Any]], str]:
        """
        解析规划阶段 LLM 响应,提取 `<think>...</think>` 块内容和紧随其后的自定义 JSON 计划. 
        返回提取的思考过程、解析后的 JSON 字典、以及错误信息(如果解析失败). 
        """
        logger.debug("[OutputParser] 开始解析规划响应 (自定义 JSON 模式)...")
        thinking_process = "未能提取思考过程. " # 默认思考过程
        error_message = "" # 默认错误信息为空

        # 验证输入的响应消息对象是否有效
        if response_message is None:
            error_message = "LLM 响应对象为 None. "
            logger.error(f"[OutputParser] 解析失败: {error_message}")
            return thinking_process, None, error_message

        # 从响应消息对象中获取原始内容字符串
        raw_content = getattr(response_message, 'content', None)

        # 验证原始内容是否存在且不为空
        if not raw_content or not raw_content.strip():
            # 检查是否有 tool_calls,尽管当前 Agent 不依赖,但作为调试信息记录
            tool_calls = getattr(response_message, 'tool_calls', None)
            if tool_calls:
                 error_message = "LLM 响应内容为空,但意外地包含了 tool_calls. "
            else:
                 error_message = "LLM 响应内容为空或仅包含空白字符. "
            logger.error(f"[OutputParser] 解析失败: {error_message}")
            return thinking_process, None, error_message

        # 使用正则表达式查找并提取 <think>...</think> 块的内容
        # re.IGNORECASE 使匹配不区分大小写,re.DOTALL 使 '.' 匹配包括换行符在内的所有字符
        think_match = re.search(r'<think>(.*?)</think>', raw_content, re.IGNORECASE | re.DOTALL)
        
        json_part_start_index = 0 # JSON 部分的起始索引,默认为 0 (如果没找到 <think>)
        if think_match:
            # 如果找到 <think> 块,提取其内容作为思考过程
            thinking_process = think_match.group(1).strip()
            # JSON 部分从 </think> 标签的结束位置开始
            json_part_start_index = think_match.end()
            logger.debug("[OutputParser] 成功提取 <think> 内容. ")
        else:
            # 如果没找到 <think> 块,记录警告,并将整个内容视为潜在的 JSON 部分
            thinking_process = "警告: 未找到 <think> 标签,将尝试解析后续内容为 JSON. "
            logger.warning(f"[OutputParser] {thinking_process}")

        # 提取 <think> 块之后的部分作为潜在的 JSON 字符串
        potential_json_part = raw_content[json_part_start_index:].strip()
        logger.debug(f"[OutputParser] 提取出的待解析 JSON 字符串 (前 500 字符): >>>\n{potential_json_part[:500]}{'...' if len(potential_json_part) > 500 else ''}\n<<<")

        # 如果提取出的潜在 JSON 部分为空,则解析失败
        if not potential_json_part:
            if think_match:
                error_message = "在 <think> 标签后未找到 JSON 内容. "
            else:
                error_message = "提取出的潜在 JSON 内容为空. "
            logger.error(f"[OutputParser] 解析失败: {error_message}")
            return thinking_process, None, error_message

        final_json_string = "" # 用于存储从潜在 JSON 字符串中精准提取的 JSON 部分
        parsed_json_plan = None # 用于存储 json.loads 后的字典对象
        
        try:
            json_string_to_parse = potential_json_part
            # 尝试移除常见的 Markdown JSON 代码块标记 (```json, ```)
            if json_string_to_parse.startswith("```json"):
                json_string_to_parse = json_string_to_parse[len("```json"):].strip()
            if json_string_to_parse.startswith("```"):
                json_string_to_parse = json_string_to_parse[len("```"):].strip()
            if json_string_to_parse.endswith("```"):
                json_string_to_parse = json_string_to_parse[:-len("```")].strip()

            # --- 精准提取最外层 JSON 对象或数组 ---
            # 寻找第一个 '{' 或 '[' 字符,确定 JSON 的起始位置
            json_start_char_index = -1
            json_end_char_index = -1
            first_brace = json_string_to_parse.find('{')
            first_square = json_string_to_parse.find('[')
            start_char_type = '' # 记录 JSON 的起始字符类型 ('{' 或 '[')

            if first_brace != -1 and (first_square == -1 or first_brace < first_square):
                # 如果 '{' 在 '[' 前面或只有 '{'
                json_start_char_index = first_brace
                start_char_type = '{'
            elif first_square != -1 and (first_brace == -1 or first_square < first_brace):
                 # 如果 '[' 在 '{' 前面或只有 '['
                 json_start_char_index = first_square
                 start_char_type = '['
            
            # 如果没有找到 '{' 或 '[',则不是有效的 JSON 开头
            if json_start_char_index == -1:
                raise json.JSONDecodeError("无法在文本中定位 JSON 对象或数组的起始 ('{' 或 '[').", json_string_to_parse, 0)

            # 使用简单的栈逻辑寻找匹配的最外层结束符
            brace_level = 0 # '{' 的嵌套层级
            square_level = 0 # '[' 的嵌套层级
            in_string = False # 是否在字符串内部 (用于忽略字符串中的 {} [] " \)
            string_char = '' # 当前字符串使用的引号类型 ('"' 或 "'")
            escape_next = False # 下一个字符是否是转义字符 '\'

            # 从找到的 JSON 起始位置开始遍历字符串
            for i in range(json_start_char_index, len(json_string_to_parse)):
                char = json_string_to_parse[i]
                
                # 处理转义字符
                if escape_next: 
                    escape_next = False
                    continue # 跳过被转义的字符
                    
                if char == '\\': 
                    escape_next = True
                    continue # 标记下一个字符要转义
                    
                if in_string:
                    # 如果在字符串内部,只关心匹配的引号
                    if char == string_char: 
                        in_string = False # 退出字符串模式
                else:
                    # 如果不在字符串内部,关心引号和括号/方括号
                    if char == '"' or char == "'": 
                        in_string = True
                        string_char = char # 进入字符串模式,记录引号类型
                    elif start_char_type == '{': # 如果 JSON 以 '{' 开头
                        if char == '{': 
                            brace_level += 1 # 遇到 '{',层级加一
                        elif char == '}': 
                            brace_level -= 1 # 遇到 '}',层级减一
                    elif start_char_type == '[': # 如果 JSON 以 '[' 开头
                        if char == '[': 
                            square_level += 1 # 遇到 '[',层级加一
                        elif char == ']': 
                            square_level -= 1 # 遇到 ']',层级减一
                            
                # 检查是否找到了最外层 JSON 的结束位置
                # 必须不在字符串内部,且对应的层级归零
                if not in_string:
                    if start_char_type == '{' and char == '}' and brace_level == 0: 
                        json_end_char_index = i + 1 # 找到匹配的 '}',记录结束位置 (包含结束符)
                        break # 结束查找
                    elif start_char_type == '[' and char == ']' and square_level == 0: 
                        json_end_char_index = i + 1 # 找到匹配的 ']',记录结束位置 (包含结束符)
                        break # 结束查找
            
            # 如果循环结束仍未找到匹配的结束符,则 JSON 结构不完整
            if json_end_char_index == -1:
                raise json.JSONDecodeError(f"无法在文本中找到匹配的 JSON 结束符 ('{ '}' if start_char_type == '{' else ']' }'). JSON 结构可能不完整. ", json_string_to_parse, len(json_string_to_parse) -1)

            # 提取精准的 JSON 字符串
            final_json_string = json_string_to_parse[json_start_char_index:json_end_char_index]
            logger.debug(f"[OutputParser] 精准提取的 JSON 字符串: >>>\n{final_json_string}\n<<<")
            
            # 使用 json.loads 解析 JSON 字符串
            parsed_json_plan = json.loads(final_json_string)
            logger.debug("[OutputParser] JSON 字符串解析成功. ")

            # --- 验证解析后的 JSON 结构是否符合 Agent 约定 ---
            # 检查是否是字典
            if not isinstance(parsed_json_plan, dict): 
                raise ValueError("解析结果不是一个 JSON 对象 (字典). ")
                
            # 检查必需的 is_tool_calls 字段
            if "is_tool_calls" not in parsed_json_plan or not isinstance(parsed_json_plan["is_tool_calls"], bool): 
                raise ValueError("JSON 对象缺少必需的布尔字段 'is_tool_calls',或其类型不正确. ")
            
            tool_list = parsed_json_plan.get("tool_list")
            direct_reply = parsed_json_plan.get("direct_reply")

            if parsed_json_plan["is_tool_calls"]:
                # 如果 is_tool_calls 为 true,验证 tool_list
                if not isinstance(tool_list, list): 
                    raise ValueError("当 'is_tool_calls' 为 true 时, 'tool_list' 字段必须是一个列表. ")
                if not tool_list: 
                    # 允许 tool_list 是空列表,但发出警告
                    logger.warning("[OutputParser] 验证警告: 'is_tool_calls' 为 true 但 'tool_list' 列表为空. ")
                
                indices_set = set() # 用于检查 index 是否重复和连续
                for i, tool_item in enumerate(tool_list):
                    if not isinstance(tool_item, dict): 
                        raise ValueError(f"'tool_list' 中索引 {i} 的元素不是字典. ")
                    # 检查工具名称字段
                    if not tool_item.get("toolname") or not isinstance(tool_item["toolname"], str) or not tool_item["toolname"].strip(): 
                        raise ValueError(f"'tool_list' 中索引 {i} 缺少有效的非空 'toolname' 字符串. ")
                    # 检查参数字段
                    if "params" not in tool_item or not isinstance(tool_item["params"], dict): 
                        raise ValueError(f"'tool_list' 中索引 {i} 缺少或 'params' 不是字典. ")
                    # 检查索引字段
                    if not isinstance(tool_item.get("index"), int) or tool_item.get("index", 0) <= 0: 
                        raise ValueError(f"'tool_list' 中索引 {i} 缺少有效正整数 'index'. ")
                        
                    current_index = tool_item["index"]
                    if current_index in indices_set: 
                        raise ValueError(f"'tool_list' 中索引 {i} 的 'index' 值 {current_index} 与之前的重复. ")
                    indices_set.add(current_index)
                    
                # 检查索引是否连续并从 1 开始 (仅当列表非空时)
                if tool_list:
                    max_index = max(indices_set) if indices_set else 0
                    if len(indices_set) != max_index or set(range(1, max_index + 1)) != indices_set:
                         logger.warning(f"[OutputParser] 验证警告: 'tool_list' 中的 'index' ({sorted(list(indices_set))}) 不连续或不从 1 开始. ")

                # 如果 is_tool_calls 为 true,direct_reply 必须是 null
                if direct_reply is not None and (not isinstance(direct_reply, str) or direct_reply.strip()):
                     raise ValueError("当 'is_tool_calls' 为 true 时, 'direct_reply' 字段必须是 null. ")

            else: # is_tool_calls 为 false
                # 如果 is_tool_calls 为 false,tool_list 必须是 null 或空列表
                if tool_list is not None and (not isinstance(tool_list, list) or tool_list):
                    raise ValueError("当 'is_tool_calls' 为 false 时, 'tool_list' 字段必须是 null 或一个空列表 []. ")

                # 如果 is_tool_calls 为 false,必须提供有效的 direct_reply
                if not isinstance(direct_reply, str) or not direct_reply.strip():
                    raise ValueError("当 'is_tool_calls' 为 false 时, 必须提供有效的非空 'direct_reply' 字符串. ")
                    
            logger.info("[OutputParser] 自定义 JSON 计划解析和验证成功!")

        except json.JSONDecodeError as json_err:
            # JSON 解析本身的错误
            parsed_json_plan = None
            # 错误信息包含原始 JSON 字符串的截断,方便调试
            error_message = f"解析 JSON 失败: {json_err}. 请检查 LLM 输出的 JSON 部分是否符合标准. Raw JSON string (截断): '{potential_json_part[:200]}...'"
            logger.error(f"[OutputParser] JSON 解析失败: {error_message}")
        except ValueError as validation_err:
            # 解析后的 JSON 结构不符合约定的错误
            parsed_json_plan = None
            error_message = f"JSON 结构验证失败: {validation_err}. "
            # 记录用于验证的 JSON 内容,可能已经被精准提取过或还是原始潜在部分
            json_content_for_log = final_json_string if final_json_string else potential_json_part[:200] + ('...' if len(potential_json_part) > 200 else '')
            logger.error(f"[OutputParser] JSON 结构验证失败: {error_message} JSON content (可能不完整): {json_content_for_log}")
        except Exception as e:
            # 捕获其他未知异常
            parsed_json_plan = None
            error_message = f"解析规划响应时发生未知错误: {e}"
            logger.error(f"[OutputParser] 解析时未知错误: {error_message}", exc_info=True)

        return thinking_process, parsed_json_plan, error_message

    def _parse_llm_text_content(self, text_content: str) -> Tuple[str, str]:
        """
        从 LLM 的最终文本响应中解析 `<think>...</think>` 思考过程和正式回复文本. 
        """
        logger.debug("[OutputParser._parse_llm_text_content] 正在解析最终文本内容...")
        
        if not text_content: 
            logger.warning("[OutputParser._parse_llm_text_content] 接收到空的文本内容. ")
            return "思考过程提取失败 (输入为空). ", "回复内容提取失败 (输入为空). "

        thinking_process = "未能提取思考过程. " # 默认思考过程
        formal_reply = text_content.strip() # 默认将整个内容视为正式回复

        # 使用正则表达式查找并提取 <think>...</think> 块
        think_match = re.search(r'<think>(.*?)</think>\s*\n*\s*\n*(.*)', text_content, re.IGNORECASE | re.DOTALL)
        
        if think_match:
            # 如果找到 <think> 块
            thinking_process = think_match.group(1).strip() # 提取第一个捕获组为思考过程
            formal_reply = think_match.group(2).strip() # 提取第二个捕获组 (</think> 后面的部分) 为正式回复
            
            # 检查 <think> 标签之前是否有内容 (这不符合约定的格式)
            content_before_think = text_content[:think_match.start()].strip()
            if content_before_think:
                logger.warning(f"[OutputParser._parse_llm_text_content] 在 <think> 标签之前检测到非空白内容: '{content_before_think[:50]}...'. ")
        else:
            # 如果没找到 <think> 块,记录警告,并将整个内容视为正式回复
            logger.warning("[OutputParser._parse_llm_text_content] 未找到 <think>...</think> 标签. 将整个内容视为正式回复,思考过程标记为提取失败. ")
            thinking_process = "未能提取思考过程 - LLM 可能未按预期包含<think>标签. "
            # formal_reply 已经是 text_content.strip()

        # 确保提取出的思考过程和回复文本不是空白
        thinking_process = thinking_process if thinking_process else "提取的思考过程为空白. "
        formal_reply = formal_reply if formal_reply else "LLM 未生成最终报告内容. "

        logger.debug(f"[OutputParser._parse_llm_text_content] 解析结果 - 思考长度: {len(thinking_process)}, 回复长度: {len(formal_reply)}")
        return thinking_process, formal_reply

# --- 模块化组件: ToolExecutor ---
class ToolExecutor:
    """
    负责执行 Agent 的内部工具(Action 方法),支持重试和失败中止. 
    它接收 LLM 规划阶段生成的工具调用列表,并按顺序调用对应的 Agent 方法. 
    """
    def __init__(self, agent_instance: 'CircuitDesignAgentV7', max_tool_retries: int = 2, tool_retry_delay_seconds: float = 1.0):
        logger.info("[ToolExecutor] 初始化工具执行器 (支持异步, 重试, 失败中止). ")
        
        # 验证 Agent 实例是否有效,需要访问其方法和 verbose 状态
        if not isinstance(agent_instance, CircuitDesignAgentV7):
            raise TypeError("ToolExecutor 需要一个 CircuitDesignAgentV7 实例. ")
            
        self.agent_instance = agent_instance # 保存 agent 实例引用
        
        # 验证 Agent 实例是否有 MemoryManager
        if not hasattr(agent_instance, 'memory_manager') or not isinstance(agent_instance.memory_manager, MemoryManager):
            raise TypeError("Agent 实例缺少有效的 MemoryManager. ")
            
        # **修改点**: 从 Agent 实例获取 verbose 标志
        self.verbose_mode = getattr(agent_instance, 'verbose_mode', True) # 默认为 True

        # 设置重试次数和延迟,确保非负和最小延迟
        self.max_tool_retries = max(0, max_tool_retries)
        self.tool_retry_delay_seconds = max(0.1, tool_retry_delay_seconds)
        
        logger.info(f"[ToolExecutor] 工具执行配置: 每个工具最多重试 {self.max_tool_retries} 次,重试间隔 {self.tool_retry_delay_seconds} 秒. Verbose Mode: {self.verbose_mode}")


    async def execute_tool_calls(self, mock_tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        按顺序异步协调执行工具调用列表. 
        每个工具调用会尝试执行 (最多重试 max_tool_retries 次). 
        如果任何工具在所有重试后依然失败,将中止后续工具的执行. 
        
        参数:
            mock_tool_calls: 一个列表,包含模拟的工具调用字典 (来自 LLM 解析的计划). 
                             结构模拟 OpenAI/ZhipuAI 的 tool_calls 格式,但实际上是 Agent 内部约定. 
                             例如: [{"id": "call_...", "type": "function", "function": {"name": "tool_name", "arguments": "json_string"}}]
                                  注意这里的 "arguments" 是一个包含参数的 JSON 字符串. 
        
        返回:
            一个列表,包含每个尝试执行的工具调用的结果字典. 
            结果字典结构例如: {"tool_call_id": "...", "result": {"status": "success"|"failure", "message": "...", "error": {}}}
        """
        logger.info(f"[ToolExecutor] 准备异步执行最多 {len(mock_tool_calls)} 个工具调用 (按顺序,支持重试,失败中止)...")
        execution_results = [] # 存储所有尝试执行的工具的结果

        if not mock_tool_calls:
            logger.info("[ToolExecutor] 没有工具需要执行. ")
            return []

        total_tools = len(mock_tool_calls)
        
        # 按顺序遍历计划中的每一个工具调用
        for i, mock_call in enumerate(mock_tool_calls):
            current_tool_index_in_plan = i + 1 # 在整个计划中的顺序 (从 1 开始)
            function_name = "unknown_function" # 默认函数名,以防解析失败
            tool_call_id_from_mock = mock_call.get('id', f'mock_id_fallback_{i}') # 获取模拟的 tool call ID
            action_result_final_for_tool = None # 存储当前工具的最终执行结果
            parsed_arguments = {} # 存储解析后的参数字典
            tool_display_name = "未知工具" # 用于日志和提示的工具显示名称
            tool_succeeded_after_all_retries = False # 标记当前工具是否最终执行成功

            try:
                # 提取工具名称和参数字符串
                func_info = mock_call.get('function')
                if not isinstance(func_info, dict) or 'name' not in func_info or 'arguments' not in func_info:
                     err_msg = f"模拟 ToolCall 对象结构无效 (ID: {tool_call_id_from_mock}). 缺少 function 或其 name/arguments 字段. "
                     logger.error(f"[ToolExecutor] {err_msg}")
                     # 记录失败结果,并设置状态为 failure
                     action_result_final_for_tool = {"status": "failure", "message": "错误: 内部工具调用结构无效. ", "error": {"type": "MalformedMockCall", "details": err_msg}}
                     execution_results.append({"tool_call_id": tool_call_id_from_mock, "result": action_result_final_for_tool})
                     # **修改点**: 使用新的 async_print,仅在详细模式下打印,并中止后续工具执行
                     await async_print(f"  ❌ [{current_tool_index_in_plan}/{total_tools}] 内部错误: 工具调用结构无效. 已中止后续操作. ", agent_verbose_flag=self.verbose_mode, verbose_only=True)
                     break # 结构无效是严重错误,中止整个批次

                function_name = func_info['name']
                function_args_str = func_info['arguments']
                # 生成一个更友好的工具显示名称
                tool_display_name = function_name.replace('_tool', '').replace('_', ' ').title()
                
                logger.info(f"[ToolExecutor] 处理工具调用 {current_tool_index_in_plan}/{total_tools}: Name='{function_name}', MockID='{tool_call_id_from_mock}'")
                logger.debug(f"[ToolExecutor] 原始参数 JSON 字符串: '{function_args_str}'")
                # **修改点**: 使用新的 async_print,仅在详细模式下打印准备执行信息
                await async_print(f"  [{current_tool_index_in_plan}/{total_tools}] 准备执行: {tool_display_name}...", agent_verbose_flag=self.verbose_mode, verbose_only=True)

                # 解析参数 JSON 字符串为字典
                try:
                    parsed_arguments = json.loads(function_args_str) if function_args_str and function_args_str.strip() else {}
                    if not isinstance(parsed_arguments, dict):
                         raise TypeError(f"参数必须是 JSON 对象 (字典),实际得到: {type(parsed_arguments).__name__}")
                    logger.debug(f"[ToolExecutor] 参数解析成功: {parsed_arguments}")
                except (json.JSONDecodeError, TypeError) as json_err:
                    # 参数 JSON 格式错误或类型不符
                    err_msg = f"工具 '{function_name}' (ID: {tool_call_id_from_mock}) 的参数 JSON 解析失败: {json_err}."
                    logger.error(f"[ToolExecutor] 参数解析错误: {err_msg}", exc_info=True)
                    action_result_final_for_tool = {"status": "failure", "message": f"错误: 工具 '{tool_display_name}' 的参数格式错误. ", "error": {"type": "ArgumentParsing", "details": err_msg}}
                    execution_results.append({"tool_call_id": tool_call_id_from_mock, "result": action_result_final_for_tool})
                    # **修改点**: 使用新的 async_print,仅在详细模式下打印失败信息并中止后续
                    await async_print(f"  ❌ [{current_tool_index_in_plan}/{total_tools}] 操作失败: {tool_display_name}. 错误: 参数解析失败. 已中止后续操作. ", agent_verbose_flag=self.verbose_mode, verbose_only=True)
                    break # 参数解析失败是严重错误,中止整个批次

                # 获取 Agent 实例中对应名称的工具方法
                tool_action_method = getattr(self.agent_instance, function_name, None)
                if not callable(tool_action_method):
                    # 如果方法不存在或不可调用
                    err_msg = f"Agent 未实现名为 '{function_name}' 的工具方法 (ID: {tool_call_id_from_mock}). "
                    logger.error(f"[ToolExecutor] 工具未实现: {err_msg}")
                    action_result_final_for_tool = {"status": "failure", "message": f"错误: {err_msg}", "error": {"type": "NotImplemented", "details": f"Action method '{function_name}' not found or not callable."}}
                    execution_results.append({"tool_call_id": tool_call_id_from_mock, "result": action_result_final_for_tool})
                     # **修改点**: 使用新的 async_print,仅在详细模式下打印失败信息并中止后续
                    await async_print(f"  ❌ [{current_tool_index_in_plan}/{total_tools}] 操作失败: {tool_display_name}. 错误: 工具未实现. 已中止后续操作. ", agent_verbose_flag=self.verbose_mode, verbose_only=True)
                    break # 工具不存在是严重错误,中止整个批次

                # --- 执行工具方法 (带重试循环) ---
                for retry_attempt in range(self.max_tool_retries + 1): # 包括首次尝试和所有重试
                    current_attempt_num = retry_attempt + 1
                    
                    if retry_attempt > 0:
                        # 如果是重试,先等待一段时间,并打印重试提示
                        logger.warning(f"[ToolExecutor] 工具 '{function_name}' (ID: {tool_call_id_from_mock}) 执行失败,正在进行第 {retry_attempt}/{self.max_tool_retries} 次重试...")
                        # **修改点**: 使用新的 async_print,仅在详细模式下打印重试提示
                        await async_print(f"  🔄 [{current_tool_index_in_plan}/{total_tools}] 操作 '{tool_display_name}' 失败,等待 {self.tool_retry_delay_seconds} 秒后重试 (尝试 {current_attempt_num}/{self.max_tool_retries + 1})...", agent_verbose_flag=self.verbose_mode, verbose_only=True)
                        await asyncio.sleep(self.tool_retry_delay_seconds)
                        await async_print(f"  🔄 [{current_tool_index_in_plan}/{total_tools}] 正在进行第 {retry_attempt} 次重试执行 '{tool_display_name}'...", agent_verbose_flag=self.verbose_mode, verbose_only=True)

                    logger.debug(f"[ToolExecutor] >>> 正在调用 Action 方法: '{function_name}' (ID: {tool_call_id_from_mock}, Attempt {current_attempt_num})")
                    action_result_this_attempt = None # 存储当前尝试的执行结果
                    
                    try:
                        # 调用工具方法,使用 asyncio.to_thread 将同步方法放到线程池中运行
                        # 假设所有工具方法都是同步的
                        action_result_this_attempt = await asyncio.to_thread(tool_action_method, arguments=parsed_arguments)
                        
                        # 验证工具方法的返回结果结构
                        if not isinstance(action_result_this_attempt, dict) or 'status' not in action_result_this_attempt or 'message' not in action_result_this_attempt:
                            err_msg_struct = f"Action '{function_name}' 返回的结构无效. 期望字典包含 'status' 和 'message'. "
                            logger.error(f"[ToolExecutor] Action 返回结构错误 (Attempt {current_attempt_num}): {err_msg_struct}")
                            # 如果返回结构无效,记录为失败结果
                            action_result_this_attempt = {"status": "failure", "message": f"错误: 工具 '{function_name}' 返回结果结构无效. ", "error": {"type": "InvalidActionResult", "details": err_msg_struct}}
                        else:
                             logger.info(f"[ToolExecutor] Action '{function_name}' (ID: {tool_call_id_from_mock}) 执行完毕 (Attempt {current_attempt_num}). 状态: {action_result_this_attempt.get('status', 'N/A')}")

                        # 检查当前尝试是否成功
                        if action_result_this_attempt.get("status") == "success":
                            tool_succeeded_after_all_retries = True # 标记成功
                            action_result_final_for_tool = action_result_this_attempt # 保存最终成功结果
                            break # 成功则跳出重试循环
                            
                        # 如果失败且还有重试机会,记录警告并继续重试循环
                        if retry_attempt < self.max_tool_retries:
                             logger.warning(f"[ToolExecutor] Action '{function_name}' (ID: {tool_call_id_from_mock}) 执行失败 (Attempt {current_attempt_num}). 将重试. ")
                        else:
                             # 如果失败且没有重试机会了,记录错误
                             logger.error(f"[ToolExecutor] Action '{function_name}' (ID: {tool_call_id_from_mock}) 在所有 {self.max_tool_retries + 1} 次尝试后仍失败. ")
                             action_result_final_for_tool = action_result_this_attempt # 保存最终失败结果
                             break # 没有重试机会,跳出循环
                             
                    except TypeError as te:
                        # 捕获调用工具方法时发生的类型错误 (如参数不匹配)
                        err_msg_type = f"调用 Action '{function_name}' 时参数不匹配或内部类型错误 (Attempt {current_attempt_num}): {te}."
                        logger.error(f"[ToolExecutor] Action 调用参数/类型错误: {err_msg_type}", exc_info=True)
                        action_result_this_attempt = {"status": "failure", "message": f"错误: 调用工具 '{function_name}' 时参数或内部类型错误. ", "error": {"type": "ArgumentOrInternalTypeError", "details": err_msg_type}}
                        action_result_final_for_tool = action_result_this_attempt # 保存失败结果
                        if retry_attempt == self.max_tool_retries: break # 如果没有重试机会了,跳出循环
                    except Exception as exec_err:
                        # 捕获工具方法执行期间发生的其他未期望的错误
                        err_msg_exec = f"Action '{function_name}' 执行期间发生意外内部错误 (Attempt {current_attempt_num}): {exec_err}"
                        logger.error(f"[ToolExecutor] Action 执行内部错误: {err_msg_exec}", exc_info=True)
                        action_result_this_attempt = {"status": "failure", "message": f"错误: 执行工具 '{function_name}' 时发生内部错误. ", "error": {"type": "ExecutionError", "details": str(exec_err)}}
                        action_result_final_for_tool = action_result_this_attempt # 保存失败结果
                        if retry_attempt == self.max_tool_retries: break # 如果没有重试机会了,跳出循环
                # --- 重试循环结束 ---
                
                # 确保无论如何,每个尝试的工具调用都有一个最终结果被记录
                if action_result_final_for_tool is None:
                     # 这是一个内部逻辑错误,应该不会发生,但为了鲁棒性添加检查
                     logger.error(f"[ToolExecutor] 内部逻辑错误: 工具 '{function_name}' 未在重试后生成任何最终结果. ")
                     action_result_final_for_tool = {"status": "failure", "message": f"错误: 工具 '{function_name}' 未返回结果. ", "error": {"type": "MissingResult"}}

                # 将当前工具的最终执行结果添加到结果列表中
                execution_results.append({"tool_call_id": tool_call_id_from_mock, "result": action_result_final_for_tool})
                logger.debug(f"[ToolExecutor] 已记录工具 '{tool_call_id_from_mock}' 的最终执行结果 (状态: {action_result_final_for_tool.get('status')}).")

                # 根据最终执行状态,打印用户可见(在详细模式下)的提示信息
                status_icon = "✅" if tool_succeeded_after_all_retries else "❌"
                msg_preview = action_result_final_for_tool.get('message', '无消息')[:80] + ('...' if len(action_result_final_for_tool.get('message', '')) > 80 else '')
                # **修改点**: 使用新的 async_print,仅在详细模式下打印执行结果摘要
                await async_print(f"  {status_icon} [{current_tool_index_in_plan}/{total_tools}] 操作完成: {tool_display_name}. 结果: {msg_preview}", agent_verbose_flag=self.verbose_mode, verbose_only=True)

                # 如果当前工具执行失败 (即使重试后),根据策略中止后续工具执行
                if not tool_succeeded_after_all_retries:
                    logger.warning(f"[ToolExecutor] 工具 '{function_name}' (Mock ID: {tool_call_id_from_mock}) 在所有重试后仍然失败. 中止本次计划中的后续工具执行. ")
                    # **修改点**: 使用新的 async_print,仅在详细模式下打印中止信息
                    await async_print(f"  ⚠️ 由于操作 '{tool_display_name}' 在重试后仍然失败,本次计划中的后续操作已中止. ", agent_verbose_flag=self.verbose_mode, verbose_only=True)
                    break # 中止循环,不再执行剩余工具

            except Exception as outer_err:
                 # 捕获处理单个工具调用时发生的顶层意外错误 (例如,获取方法、初始参数解析前的错误)
                 err_msg_outer = f"处理工具调用 '{function_name}' (Mock ID: {tool_call_id_from_mock}) 时发生顶层意外错误: {outer_err}"
                 logger.error(f"[ToolExecutor] 处理工具调用时顶层错误: {err_msg_outer}", exc_info=True)
                 action_result_final_for_tool = {"status": "failure", "message": f"错误: 处理工具 '{tool_display_name or function_name}' 时发生未知内部错误. ", "error": {"type": "UnexpectedToolSetupError", "details": str(outer_err)}}
                 execution_results.append({"tool_call_id": tool_call_id_from_mock, "result": action_result_final_for_tool})
                 # **修改点**: 使用新的 async_print,仅在详细模式下打印顶层错误信息并中止后续
                 await async_print(f"  ❌ [{current_tool_index_in_plan}/{total_tools}] 操作失败: {tool_display_name or function_name}. 错误: 未知内部错误. 已中止后续操作. ", agent_verbose_flag=self.verbose_mode, verbose_only=True)
                 break # 顶层错误,中止整个批次

        total_executed_or_attempted = len(execution_results)
        logger.info(f"[ToolExecutor] 所有 {total_executed_or_attempted}/{total_tools} 个计划中的工具调用已处理 (可能因失败提前中止). ")
        return execution_results

# --- Agent 核心类 (Orchestrator) ---
class CircuitDesignAgentV7:
    """
    电路设计 Agent V7.2.3 - 异步协调器, 带文件日志, 强化问答处理, 可选详细输出, 内部 LLM 流式交互. 
    负责协调整个 Agent 的工作流程: 接收用户指令 -> 规划 (调用 LLM) -> 行动 (执行工具) -> 观察 (处理工具结果) -> 响应 (调用 LLM 或直接回复) -> 循环. 
    """
    def __init__(self, api_key: str, model_name: str = "glm-4-flash-250414",
                 max_short_term_items: int = 25, max_long_term_items: int = 50,
                 planning_llm_retries: int = 1, max_tool_retries: int = 2,
                 tool_retry_delay_seconds: float = 1.0, max_replanning_attempts: int = 2,
                 verbose: bool = True): # **修改点**: 新增 verbose 参数控制详细输出
                 
        logger.info(f"\n{'='*30} Agent V7.2.3 初始化开始 (Async, Streaming LLM, Decorator Tools, File Logging, Enhanced Q&A, Verbose Switch) {'='*30}") # 版本号更新
        logger.info("[Agent Init] 正在启动电路设计助理 V7.2.3...") # 版本号更新

        self.api_key = api_key # 保存 API Key,供 LLMInterface 使用
        self.verbose_mode = verbose # 保存 verbose 状态,控制控制台输出详细程度

        # **修改点**: 根据 verbose 模式动态设置控制台日志级别
        global console_handler # 引用全局配置的 console_handler
        console_log_level = logging.DEBUG if self.verbose_mode else logging.INFO
        console_handler.setLevel(console_log_level)
        logger.info(f"[Agent Init] 控制台日志级别设置为: {logging.getLevelName(console_log_level)} (Verbose={self.verbose_mode})")

        try:
            # 初始化核心模块
            self.memory_manager = MemoryManager(max_short_term_items, max_long_term_items)
            # **修改点**: 将 self (agent 实例) 传递给 LLMInterface,以便其访问 api_key 和 verbose_mode
            self.llm_interface = LLMInterface(agent_instance=self, model_name=model_name)
            self.output_parser = OutputParser()
            # **修改点**: 将 self (agent 实例) 传递给 ToolExecutor,以便其访问 verbose_mode
            self.tool_executor = ToolExecutor(
                agent_instance=self,
                max_tool_retries=max_tool_retries,
                tool_retry_delay_seconds=tool_retry_delay_seconds
            )
        except (ValueError, ConnectionError, TypeError) as e:
            # 如果任何核心模块初始化失败,记录关键错误并退出
            logger.critical(f"[Agent Init] 核心模块初始化失败: {e}", exc_info=True)
            sys.stderr.write(f"\n🔴 Agent 核心模块初始化失败: {e}\n请检查配置或依赖!程序无法启动. \n")
            sys.stderr.flush()
            raise # 重新抛出异常,中止程序启动

        self.planning_llm_retries = max(0, planning_llm_retries) # 规划阶段 LLM 调用失败时的重试次数
        self.max_replanning_attempts = max(0, max_replanning_attempts) # 工具执行失败后的重规划尝试次数
        
        logger.info(f"[Agent Init] 规划 LLM 调用失败时将重试 {self.planning_llm_retries} 次. ")
        logger.info(f"[Agent Init] 工具执行失败后,最多允许重规划 {self.max_replanning_attempts} 次. ")

        # 动态发现并注册标记为工具的方法
        self.tools_registry: Dict[str, Dict[str, Any]] = {} # 存储工具名称到其 Schema 的映射
        logger.info("[Agent Init] 正在动态发现并注册已标记的工具...")
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            # 检查方法是否被 @register_tool 装饰过
            if hasattr(method, '_is_tool') and method._is_tool:
                schema = getattr(method, '_tool_schema', None)
                # 验证 Schema 结构是否完整
                if schema and isinstance(schema, dict) and 'description' in schema and 'parameters' in schema:
                    self.tools_registry[name] = schema # 注册工具
                    logger.info(f"[Agent Init] ✓ 已注册工具: '{name}'")
                else:
                    logger.warning(f"[Agent Init] 发现工具 '{name}' 但其 Schema 结构不完整或无效,已跳过注册. ")
                    
        if not self.tools_registry:
            logger.warning("[Agent Init] 未发现任何通过 @register_tool 注册的工具!Agent 将只能进行直接对话. ")
        else:
            logger.info(f"[Agent Init] 共发现并注册了 {len(self.tools_registry)} 个工具. ")
            # 在 DEBUG 模式下打印完整的工具注册表
            if logger.isEnabledFor(logging.DEBUG):
                try:
                    logger.debug(f"[Agent Init] 工具注册表详情:\n{json.dumps(self.tools_registry, indent=2, ensure_ascii=False)}")
                except Exception: pass # 序列化失败也不影响初始化流程

        logger.info(f"\n{'='*30} Agent V7.2.3 初始化成功 {'='*30}\n") # 版本号更新
        print("我是电路设计编程助理 V7.2.3!") # 版本号更新
        print(f"已准备好接收指令. 当前模式: {'详细' if self.verbose_mode else '简洁'}. ") # 显示当前模式
        print(f"日志文件位于: {os.path.abspath(log_file_name)}")
        print("-" * 70)
        sys.stdout.flush() # 确保初始化信息立即显示


    # --- Action Implementations (工具实现) ---
    # 这些是 Agent 能够执行的具体操作,对应 LLM 计划中的工具调用. 
    # 它们被 @register_tool 装饰,并由 ToolExecutor 调用. 
    # 这些方法的内部逻辑通常是同步的,但在 ToolExecutor 中通过 asyncio.to_thread 被包装成异步可等待的. 

    @register_tool(
        description="添加一个新的电路元件 (如电阻, 电容, 电池, LED, 开关, 芯片, 地线等). 如果用户未指定 ID,会自动生成. ",
        parameters={
            "type": "object",
            "properties": {
                "component_type": {"type": "string", "description": "元件的类型 (例如: '电阻', 'LED')."},
                "component_id": {"type": "string", "description": "可选的用户指定 ID. "},
                "value": {"type": "string", "description": "可选的元件值 (例如: '1k', '10uF')."}
            },
            "required": ["component_type"] # component_type 参数是必需的
        }
    )
    def add_component_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Action: 添加元件. 负责将参数转换为 CircuitComponent 对象并添加到 Circuit 实例. """
        logger.info("[Action: AddComponent] 执行添加元件操作. ")
        logger.debug(f"[Action: AddComponent] 收到参数: {arguments}")
        
        # 从参数字典中安全地获取参数值
        component_type = arguments.get("component_type")
        component_id_req = arguments.get("component_id")
        value_req = arguments.get("value")
        
        logger.info(f"[Action: AddComponent] 参数解析: Type='{component_type}', Requested ID='{component_id_req}', Value='{value_req}'")

        # 输入参数验证
        if not component_type or not isinstance(component_type, str) or not component_type.strip():
            msg="元件类型是必需的,并且必须是有效的非空字符串. "
            logger.error(f"[Action: AddComponent] 输入验证失败: {msg}")
            return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "InvalidInput", "details": msg}}

        target_id_final = None # 最终确定要使用的元件 ID
        id_was_generated_by_system = False # 标记最终 ID 是否由系统生成
        user_provided_id_was_validated = None # 存储经过验证的用户提供的 ID

        # 如果用户提供了 ID,先尝试验证和使用它
        if component_id_req and isinstance(component_id_req, str) and component_id_req.strip():
            user_provided_id_cleaned = component_id_req.strip().upper() # 清理并转换为大写
            # 简单的 ID 格式验证 (字母、数字、下划线、连字符,不能以下划线或连字符开头)
            if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$', user_provided_id_cleaned): # 修正正则,首字符不能是_-
                if user_provided_id_cleaned in self.memory_manager.circuit.components:
                    # 如果用户提供的 ID 已被占用,返回失败
                    msg=f"您提供的元件 ID '{user_provided_id_cleaned}' 已被占用. "
                    logger.error(f"[Action: AddComponent] ID 冲突: {msg}")
                    return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "IDConflict", "details": msg}}
                else:
                    # 用户提供的 ID 有效且未被占用,使用它
                    target_id_final = user_provided_id_cleaned
                    user_provided_id_was_validated = target_id_final
                    logger.debug(f"[Action: AddComponent] 将使用用户提供的有效 ID: '{target_id_final}'.")
            else:
                # 用户提供的 ID 格式无效,记录警告,转为自动生成
                logger.warning(f"[Action: AddComponent] 用户提供的 ID '{component_id_req}' 格式无效. 将自动生成 ID. ")

        # 如果最终 ID 仍未确定 (用户未提供、提供无效或发生冲突),则自动生成
        if target_id_final is None:
            try:
                target_id_final = self.memory_manager.circuit.generate_component_id(component_type)
                id_was_generated_by_system = True
                logger.debug(f"[Action: AddComponent] 已自动为类型 '{component_type}' 生成 ID: '{target_id_final}'.")
            except RuntimeError as e_gen_id:
                # 如果自动生成 ID 失败 (例如,计数器达到上限)
                msg=f"无法自动为类型 '{component_type}' 生成唯一 ID: {e_gen_id}"
                logger.error(f"[Action: AddComponent] ID 生成失败: {msg}", exc_info=True)
                return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "IDGenerationFailed", "details": str(e_gen_id)}}

        # 处理元件的值,如果提供了则转换为字符串并去除空白
        processed_value = str(value_req).strip() if value_req is not None and str(value_req).strip() else None

        try:
            # 再次检查最终 ID 是否已确定 (双重保险)
            if target_id_final is None: raise ValueError("内部错误: 未能最终确定元件 ID. ") 
            
            # 创建 CircuitComponent 对象并添加到电路
            new_component = CircuitComponent(target_id_final, component_type, processed_value)
            self.memory_manager.circuit.add_component(new_component)
            
            logger.info(f"[Action: AddComponent] 成功添加元件 '{new_component.id}' ({new_component.type}) 到电路. ")
            
            # 构建成功的消息,包含最终使用的 ID
            success_message_parts = [f"操作成功: 已添加元件 {str(new_component)}. "]
            if id_was_generated_by_system: 
                success_message_parts.append(f"(系统自动分配 ID '{new_component.id}')")
            elif user_provided_id_was_validated: 
                 success_message_parts.append(f"(使用了您指定的 ID '{user_provided_id_was_validated}')")
                 
            final_success_message = " ".join(success_message_parts)
            
            # 将操作结果添加到长期记忆
            self.memory_manager.add_to_long_term(f"添加了元件: {str(new_component)}")
            
            # 返回成功结果字典
            return {"status": "success", "message": final_success_message, "data": new_component.to_dict()}
            
        except ValueError as ve_comp:
            # 捕获 CircuitComponent 内部的验证错误
            msg=f"创建或添加元件对象时发生内部验证错误: {ve_comp}"
            logger.error(f"[Action: AddComponent] 元件创建/添加错误: {msg}", exc_info=True)
            return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "ComponentOperationError", "details": str(ve_comp)}}
        except Exception as e_add_comp:
            # 捕获其他未知的内部错误
            msg=f"添加元件时发生未知的内部错误: {e_add_comp}"
            logger.error(f"[Action: AddComponent] 未知错误: {msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 添加元件时发生未知内部错误. ", "error": {"type": "Unexpected", "details": str(e_add_comp)}}

    @register_tool(
        description="使用两个已存在元件的 ID 将它们连接起来. ",
        parameters={
            "type": "object",
            "properties": {
                "comp1_id": {"type": "string", "description": "第一个元件的 ID. "},
                "comp2_id": {"type": "string", "description": "第二个元件的 ID. "}
            },
            "required": ["comp1_id", "comp2_id"] # 这两个参数都是必需的
        }
    )
    def connect_components_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Action: 连接两个元件. 负责调用 Circuit 实例的方法建立连接. """
        logger.info("[Action: ConnectComponents] 执行连接元件操作. ")
        logger.debug(f"[Action: ConnectComponents] 收到参数: {arguments}")
        
        # 从参数字典中获取两个元件 ID
        comp1_id_req = arguments.get("comp1_id")
        comp2_id_req = arguments.get("comp2_id")
        logger.info(f"[Action: ConnectComponents] 参数解析: Comp1='{comp1_id_req}', Comp2='{comp2_id_req}'")

        # 输入参数验证: 确保提供了两个非空的字符串 ID
        if not comp1_id_req or not isinstance(comp1_id_req, str) or not comp1_id_req.strip() or \
           not comp2_id_req or not isinstance(comp2_id_req, str) or not comp2_id_req.strip():
            msg="必须提供两个有效的、非空的元件 ID 字符串. "
            logger.error(f"[Action: ConnectComponents] 输入验证失败: {msg}")
            return {"status": "failure", "message": f"错误: {msg}", "error": {"type": "InvalidInput", "details": msg}}

        # 清理 ID 并转换为大写
        id1_cleaned = comp1_id_req.strip().upper()
        id2_cleaned = comp2_id_req.strip().upper()

        try:
            # 调用 Circuit 实例的方法建立连接
            connection_was_new = self.memory_manager.circuit.connect_components(id1_cleaned, id2_cleaned)
            
            if connection_was_new:
                logger.info(f"[Action: ConnectComponents] 成功添加新连接: {id1_cleaned} <--> {id2_cleaned}")
                # 将新的连接信息添加到长期记忆
                self.memory_manager.add_to_long_term(f"连接了元件: {id1_cleaned} <--> {id2_cleaned}")
                # 返回成功结果
                return {"status": "success", "message": f"操作成功: 已将元件 '{id1_cleaned}' 与 '{id2_cleaned}' 连接起来. ", "data": {"connection": sorted((id1_cleaned, id2_cleaned))}}
            else:
                # 如果连接已经存在
                msg_exists = f"元件 '{id1_cleaned}' 和 '{id2_cleaned}' 之间已经存在连接. 无需重复操作. "
                logger.info(f"[Action: ConnectComponents] 连接已存在: {msg_exists}")
                # 返回成功状态,但消息提示连接已存在
                return {"status": "success", "message": f"注意: {msg_exists}", "data": {"connection": sorted((id1_cleaned, id2_cleaned)), "already_existed": True}}
                
        except ValueError as ve_connect:
            # 捕获 Circuit 实例抛出的验证错误 (如元件不存在、尝试自连接等)
            msg_val_err =f"连接元件时验证失败: {ve_connect}"
            logger.error(f"[Action: ConnectComponents] 连接验证错误: {msg_val_err}")
            # 根据错误信息判断错误类型,返回更具体的错误码给 LLM 参考
            error_type_detail = "CircuitValidationError"
            if "不存在" in str(ve_connect): error_type_detail = "ComponentNotFound"
            elif "连接到它自己" in str(ve_connect): error_type_detail = "SelfConnection"
            return {"status": "failure", "message": f"错误: {msg_val_err}", "error": {"type": error_type_detail, "details": str(ve_connect)}}
        except Exception as e_connect:
            # 捕获其他未知的内部错误
            msg_unexpected =f"连接元件时发生未知的内部错误: {e_connect}"
            logger.error(f"[Action: ConnectComponents] 未知错误: {msg_unexpected}", exc_info=True)
            return {"status": "failure", "message": "错误: 连接元件时发生未知内部错误. ", "error": {"type": "Unexpected", "details": str(e_connect)}}

    @register_tool(
        description="获取当前电路的详细描述. ",
        parameters={"type": "object", "properties": {}} # 这个工具没有参数
    )
    def describe_circuit_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Action: 描述当前电路. 负责调用 Circuit 实例的方法获取状态描述. """
        logger.info("[Action: DescribeCircuit] 执行描述电路操作. ")
        logger.debug(f"[Action: DescribeCircuit] 收到参数: {arguments}") # 通常 arguments 是空字典
        try:
            # 调用 Circuit 实例的方法获取电路状态描述文本
            description = self.memory_manager.circuit.get_state_description()
            logger.info("[Action: DescribeCircuit] 成功生成电路描述. ")
            # 返回成功结果,描述文本放在 data 字段中
            return {"status": "success", "message": "已成功获取当前电路的描述. ", "data": {"description": description}}
        except Exception as e_describe:
            # 捕获生成描述时可能发生的意外错误
            msg=f"生成电路描述时发生意外的内部错误: {e_describe}"
            logger.error(f"[Action: DescribeCircuit] 未知错误: {msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 获取电路描述时发生未知错误. ", "error": {"type": "Unexpected", "details": str(e_describe)}}

    @register_tool(
        description="彻底清空当前的电路设计. ",
        parameters={"type": "object", "properties": {}} # 这个工具没有参数
    )
    def clear_circuit_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Action: 清空电路. 负责调用 Circuit 实例的方法清除所有状态. """
        logger.info("[Action: ClearCircuit] 执行清空电路操作. ")
        logger.debug(f"[Action: ClearCircuit] 收到参数: {arguments}") # 通常 arguments 是空字典
        try:
            # 调用 Circuit 实例的方法清空电路
            self.memory_manager.circuit.clear()
            logger.info("[Action: ClearCircuit] 电路状态已成功清空. ")
            # 将清空操作添加到长期记忆
            self.memory_manager.add_to_long_term("执行了清空电路操作. ")
            # 返回成功结果
            return {"status": "success", "message": "操作成功: 当前电路已彻底清空. "}
        except Exception as e_clear:
            # 捕获清空电路时可能发生的意外错误
            msg=f"清空电路时发生意外的内部错误: {e_clear}"
            logger.error(f"[Action: ClearCircuit] 未知错误: {msg}", exc_info=True)
            return {"status": "failure", "message": "错误: 清空电路时发生未知错误. ", "error": {"type": "Unexpected", "details": str(e_clear)}}

    # --- Orchestration Layer Method (核心流程) ---
    async def process_user_request(self, user_request: str) -> str:
        """
        处理用户请求的核心异步流程. 
        实现了思考 -> 规划 -> 行动 -> 观察 -> 响应的循环,支持重规划以处理工具执行失败. 
        """
        request_start_time = time.monotonic() # 记录请求开始时间,用于计算总耗时
        logger.info(f"\n{'='*25} V7.2.3 开始处理用户请求 {'='*25}") # 版本号更新,日志标记开始
        logger.info(f"[Orchestrator] 收到用户指令: \"{user_request}\"")

        # 检查用户指令是否为空或仅包含空白字符
        if not user_request or user_request.isspace():
            logger.info("[Orchestrator] 用户指令为空或仅包含空白. ")
            # **修改点**: 使用 async_print 打印用户可见信息,不受 verbose 影响(错误或提示总是显示)
            await async_print("\n您的指令似乎是空的,请重新输入!", agent_verbose_flag=self.verbose_mode) # 实际打印不受 verbose 影响,但签名保留参数
            return "<think>用户输入为空或空白,无需处理. </think>\n\n请输入您的指令!" # 返回包含思考过程的格式化响应

        # 将用户指令添加到短期记忆 (对话历史)
        try:
            self.memory_manager.add_to_short_term({"role": "user", "content": user_request})
            logger.info("[Orchestrator] 用户指令已记录并添加到短期记忆. ")
        except Exception as e_mem_user:
            # 如果添加记忆失败,记录错误并返回错误信息给用户
            logger.error(f"[Orchestrator] 添加用户消息到短期记忆时出错: {e_mem_user}", exc_info=True)
            # **修改点**: 使用 async_print 打印用户可见错误信息
            await async_print(f"\n🔴 抱歉,我在记录您的指令时遇到了内部问题 ({e_mem_user})!请稍后重试. ", agent_verbose_flag=self.verbose_mode)
            return f"<think>添加用户消息到短期记忆失败: {e_mem_user}</think>\n\n抱歉,我在处理您的指令时遇到了内部记忆错误. "

        # --- 规划与行动循环 (支持重规划) ---
        replanning_loop_count = 0 # 当前重规划尝试次数 (0 表示首次尝试)
        final_plan_from_llm = None # 最终确定的有效计划 (JSON 对象)
        final_tool_execution_results = [] # 最终的工具执行结果列表
        llm_thinking_process_from_planning = "未能提取思考过程 (初始). " # 存储规划阶段提取的思考过程

        # 循环进行规划 -> 行动 -> 观察,直到成功或达到最大重规划次数
        while replanning_loop_count <= self.max_replanning_attempts:
            current_planning_attempt_num = replanning_loop_count + 1 # 当前是第几次规划尝试 (从 1 开始)
            logger.info(f"\n--- [规划/重规划阶段] 尝试第 {current_planning_attempt_num}/{self.max_replanning_attempts + 1} 次规划 ---")
            planning_phase_type_log_prefix = f"[Orchestrator - Planning Attempt {current_planning_attempt_num}]" # 日志前缀

            # 打印用户可见的提示信息(仅在详细模式下)
            if replanning_loop_count > 0:
                 # **修改点**: 使用新的 async_print,仅在详细模式下打印重规划提示
                 await async_print(f"--- 由于之前的操作失败,正在尝试第 {replanning_loop_count}/{self.max_replanning_attempts} 次重规划... ---", agent_verbose_flag=self.verbose_mode, verbose_only=True)
            else:
                 # **修改点**: 使用新的 async_print,仅在详细模式下打印首次规划提示
                 await async_print("--- 正在请求智能大脑分析指令并生成执行计划 (JSON)... ---", agent_verbose_flag=self.verbose_mode, verbose_only=True)

            # --- 准备规划阶段的 Prompt ---
            memory_context_for_prompt = self.memory_manager.get_memory_context_for_prompt() # 获取电路状态和长期记忆描述
            tool_schemas_for_llm_prompt = self._get_tool_schemas_for_prompt() # 获取可用工具的 Schema 描述
            system_prompt_for_planning = self._get_planning_prompt_v7(
                tool_schemas_for_llm_prompt, memory_context_for_prompt,
                is_replanning=(replanning_loop_count > 0) # 标记当前是否是重规划
            )
            # 构建发送给 LLM 的消息列表 (System 消息 + 对话历史)
            messages_for_llm_planning = [{"role": "system", "content": system_prompt_for_planning}] + self.memory_manager.short_term

            # --- 调用 LLM 进行规划 (带重试) ---
            llm_call_attempt_for_planning = 0 # 当前 LLM 调用尝试次数 (0 表示首次)
            parsed_plan_this_cycle = None # 本次循环解析出的计划
            parser_error_msg_this_cycle = "" # 本次循环解析错误信息

            while llm_call_attempt_for_planning <= self.planning_llm_retries: # 包括首次和重试
                current_llm_call_num = llm_call_attempt_for_planning + 1 # 当前是第几次 LLM 调用尝试 (从 1 开始)
                logger.info(f"{planning_phase_type_log_prefix} 调用规划 LLM (LLM Call Attempt {current_llm_call_num}/{self.planning_llm_retries + 1})...")
                # **修改点**: 使用新的 async_print,仅在详细模式下打印 LLM 调用尝试信息
                if current_llm_call_num > 1: await async_print(f"    (与大脑沟通尝试 {current_llm_call_num}/{self.planning_llm_retries + 1})...", agent_verbose_flag=self.verbose_mode, verbose_only=True)

                try:
                    # **修改点**: 调用 LLMInterface,它现在内部处理流式接收并返回完整对象
                    llm_response_for_planning = await self.llm_interface.call_llm(messages=messages_for_llm_planning, use_tools=False)
                    
                    logger.info(f"{planning_phase_type_log_prefix} LLM 调用完成 (LLM Call Attempt {current_llm_call_num}).")
                    
                    # 验证 LLM 响应基本结构
                    if not llm_response_for_planning or not llm_response_for_planning.get('choices') or len(llm_response_for_planning['choices']) == 0: 
                         raise ConnectionError("LLM 响应对象无效或缺少 choices. ")
                         
                    llm_message_obj = llm_response_for_planning['choices'][0]['message'] # 获取核心消息对象
                    logger.info(f"{planning_phase_type_log_prefix} 解析 LLM 的规划响应...")
                    
                    # 解析 LLM 返回的内容,提取思考过程和 JSON 计划
                    temp_thinking, temp_plan, temp_parser_error = self.output_parser.parse_planning_response(llm_message_obj)
                    llm_thinking_process_from_planning = temp_thinking # 存储本次解析出的思考过程
                    parsed_plan_this_cycle = temp_plan # 存储本次解析出的计划
                    parser_error_msg_this_cycle = temp_parser_error # 存储本次解析错误信息

                    # 如果成功解析并验证了 JSON 计划
                    if parsed_plan_this_cycle is not None and not parser_error_msg_this_cycle:
                        logger.info(f"{planning_phase_type_log_prefix} 成功解析并验证自定义 JSON 计划!")
                        try:
                            # 将 LLM 的原始规划响应添加到短期记忆
                            # 注意: 这里需要模拟 model_dump(exclude_unset=True) 的行为,或者直接存储字典
                            # 由于 call_llm 返回的是模拟字典,直接存储即可
                            self.memory_manager.add_to_short_term(llm_message_obj) # 直接存储字典
                            logger.debug(f"{planning_phase_type_log_prefix} LLM 的原始规划响应已添加至短期记忆. ")
                        except Exception as mem_err_plan: logger.error(f"{planning_phase_type_log_prefix} 添加 LLM 规划响应到短期记忆失败: {mem_err_plan}", exc_info=True)
                        break # 规划成功,跳出 LLM 调用重试循环
                    else:
                        # 如果解析失败,记录警告并尝试重试 LLM 调用
                        logger.warning(f"{planning_phase_type_log_prefix} 解析 JSON 失败: {parser_error_msg_this_cycle}. 尝试重试 LLM 调用. ")
                        # **修改点**: 使用新的 async_print,仅在详细模式下打印解析失败提示
                        if llm_call_attempt_for_planning < self.planning_llm_retries: await async_print(f"    (解析大脑计划失败,尝试重新沟通...)", agent_verbose_flag=self.verbose_mode, verbose_only=True)
                        
                except ConnectionError as conn_err_llm:
                    # 捕获 LLM 调用过程中的连接或 API 错误
                    logger.error(f"{planning_phase_type_log_prefix} LLM 调用失败 (连接/API错误): {conn_err_llm}", exc_info=True)
                    parser_error_msg_this_cycle = f"LLM 调用连接/API错误: {conn_err_llm}"
                    # **修改点**: 使用新的 async_print,仅在详细模式下打印连接失败提示
                    if llm_call_attempt_for_planning < self.planning_llm_retries: await async_print(f"    (与大脑连接失败,尝试重新连接...)", agent_verbose_flag=self.verbose_mode, verbose_only=True)
                except Exception as e_llm_call:
                    # 捕获 LLM 调用或规划解析过程中的其他意外错误
                    logger.error(f"{planning_phase_type_log_prefix} LLM 调用或规划解析过程中发生严重错误: {e_llm_call}", exc_info=True)
                    parser_error_msg_this_cycle = f"LLM 调用或响应解析时发生错误: {e_llm_call}"
                     # **修改点**: 使用新的 async_print,仅在详细模式下打印处理失败提示
                    if llm_call_attempt_for_planning < self.planning_llm_retries: await async_print(f"    (大脑处理计划失败,尝试重新沟通...)", agent_verbose_flag=self.verbose_mode, verbose_only=True)
                    
                llm_call_attempt_for_planning += 1 # LLM 调用尝试次数递增
            # --- LLM 调用重试循环结束 ---
            
            final_plan_from_llm = parsed_plan_this_cycle # 将本次循环解析出的计划设为最终计划 (如果成功的话)

            # --- 行动阶段 或 直接回复 ---
            if final_plan_from_llm is None:
                # 如果所有 LLM 调用尝试都未能获得有效计划
                logger.error(f"{planning_phase_type_log_prefix} 规划失败: 所有 LLM 调用尝试后,未能获取有效 JSON 计划. 最终解析错误: {parser_error_msg_this_cycle}")
                
                if replanning_loop_count >= self.max_replanning_attempts:
                     # 如果已经达到最大重规划次数,则彻底失败,中止整个流程
                     logger.critical(f"{planning_phase_type_log_prefix} 已达最大重规划尝试次数 ({self.max_replanning_attempts}),仍无法获得有效计划. 中止处理. ")
                     break # 跳出重规划循环
                else:
                     # 如果还有重规划次数,则记录警告,并在下一轮尝试重规划
                     logger.warning(f"{planning_phase_type_log_prefix} 规划失败,将在下一轮尝试重规划. ")
                     replanning_loop_count += 1
                     continue # 继续外层重规划循环

            logger.info(f"{planning_phase_type_log_prefix} 成功获取并验证自定义 JSON 计划. ")
            # 在 DEBUG 模式下打印解析出的计划详情
            if logger.isEnabledFor(logging.DEBUG):
                try: logger.debug(f"{planning_phase_type_log_prefix} 解析出的计划详情: {json.dumps(final_plan_from_llm, indent=2, ensure_ascii=False)}")
                except Exception: pass

            should_call_tools = final_plan_from_llm.get("is_tool_calls", False)
            tool_list_in_plan = final_plan_from_llm.get("tool_list")
            direct_reply_in_plan = final_plan_from_llm.get("direct_reply")

            if should_call_tools:
                logger.info(f"{planning_phase_type_log_prefix} 决策: 根据 JSON 计划执行工具操作. ")
                # 如果计划要求调用工具,但工具列表无效或为空
                if not isinstance(tool_list_in_plan, list) or not tool_list_in_plan:
                    err_msg_bad_list = "'is_tool_calls' 为 true 但 'tool_list' 不是有效的非空列表!这可能是 LLM 生成了无效计划. "
                    logger.error(f"{planning_phase_type_log_prefix} 规划错误: {err_msg_bad_list}")
                    # 生成一个表示规划错误的工具执行结果
                    final_tool_execution_results = [{"tool_call_id": "internal_planning_error_bad_tool_list", "result": {"status": "failure", "message": f"错误: 计划要求调用工具,但工具列表无效或为空. ", "error": {"type": "MalformedPlanToolList", "details": err_msg_bad_list}}}]
                    try: # 尝试将这个模拟错误结果添加到记忆
                        self.memory_manager.add_to_short_term({"role": "tool", "tool_call_id": "internal_planning_error_bad_tool_list", "content": json.dumps(final_tool_execution_results[0]['result'], default=str)})
                    except Exception as mem_err_sim: logger.error(f"{planning_phase_type_log_prefix} 添加模拟规划错误工具结果到记忆失败: {mem_err_sim}")
                    
                    if replanning_loop_count >= self.max_replanning_attempts: 
                        # 如果已经达到最大重规划次数,彻底失败
                        logger.critical(f"{planning_phase_type_log_prefix} 计划工具列表无效,已达最大重规划次数. 中止. ")
                        break # 跳出重规划循环
                    else: 
                        # 如果还有重规划次数,记录警告并尝试重规划
                        logger.warning(f"{planning_phase_type_log_prefix} 计划工具列表无效,将在下一轮尝试重规划. ")
                        replanning_loop_count += 1
                        continue # 继续外层重规划循环

                # --- 将计划中的工具列表转换为 ToolExecutor 期望的格式 ---
                mock_tool_calls_for_executor = []
                param_conversion_issues = False # 标记转换参数 JSON 字符串时是否遇到问题
                for tool_item_from_plan in tool_list_in_plan:
                    tool_name = tool_item_from_plan.get("toolname")
                    params_dict = tool_item_from_plan.get("params", {})
                    index_from_plan = tool_item_from_plan.get("index")
                    
                    # 生成一个模拟的 tool_call_id,包含索引、工具名和参数哈希,方便追溯
                    try: params_hash_str = format(hash(json.dumps(params_dict, sort_keys=True, ensure_ascii=False)) & 0xFFFF, 'x')
                    except Exception: params_hash_str = "nohash"
                    mock_tool_call_id = f"call_{index_from_plan}_{tool_name[:10].replace('_','-')}_{params_hash_str}"
                    
                    # 将参数字典转换为 JSON 字符串
                    try: params_json_str = json.dumps(params_dict, ensure_ascii=False)
                    except TypeError: param_conversion_issues = True; params_json_str = "{}" # 序列化失败则用空 JSON 字符串代替
                    
                    # 添加到模拟工具调用列表
                    mock_tool_calls_for_executor.append({"id": mock_tool_call_id, "type": "function", "function": {"name": tool_name, "arguments": params_json_str}})
                
                if param_conversion_issues: logger.warning(f"{planning_phase_type_log_prefix} 注意: 转换工具列表时部分参数序列化遇到问题. ")
                logger.info(f"{planning_phase_type_log_prefix} 成功将自定义工具列表转换为 {len(mock_tool_calls_for_executor)} 个模拟 ToolCall 对象. ")

                logger.info(f"\n--- [行动阶段 - 尝试 {current_planning_attempt_num}] 执行工具 ---")
                num_tools_in_current_plan = len(mock_tool_calls_for_executor)
                # **修改点**: 使用新的 async_print,仅在详细模式下打印行动阶段开始信息
                await async_print(f"--- 正在按计划执行 {num_tools_in_current_plan} 个操作... ---", agent_verbose_flag=self.verbose_mode, verbose_only=True)
                
                current_execution_results = [] # 存储本次行动阶段的工具执行结果
                try:
                    # 调用 ToolExecutor 执行工具调用
                    current_execution_results = await self.tool_executor.execute_tool_calls(mock_tool_calls_for_executor)
                    
                    num_actually_attempted_by_executor = len(current_execution_results)
                    logger.info(f"[Orchestrator - Action Phase] ToolExecutor 完成了 {num_actually_attempted_by_executor}/{num_tools_in_current_plan} 个工具执行. ")
                    if num_actually_attempted_by_executor < num_tools_in_current_plan: 
                        logger.warning(f"[Orchestrator - Action Phase] 由于中途失败,后续 {num_tools_in_current_plan - num_actually_attempted_by_executor} 个工具未执行. ")
                    # **修改点**: 使用新的 async_print,仅在详细模式下打印行动阶段结束信息
                    await async_print(f"--- {num_actually_attempted_by_executor}/{num_tools_in_current_plan} 个操作已执行 ---", agent_verbose_flag=self.verbose_mode, verbose_only=True)
                    
                except Exception as e_tool_exec_top:
                     # 捕获 ToolExecutor 层面发生的顶层意外错误
                     logger.error(f"[Orchestrator - Action Phase] ToolExecutor 执行过程中发生顶层意外错误: {e_tool_exec_top}", exc_info=True)
                     # 生成一个表示执行器错误的模拟工具执行结果
                     current_execution_results = [{"tool_call_id": "executor_internal_error", "result": {"status": "failure", "message": f"错误: 工具执行器层面发生严重错误: {e_tool_exec_top}", "error": {"type": "ToolExecutorError"}}}]
                     
                final_tool_execution_results = current_execution_results # 保存本次行动阶段的结果,作为最终结果(如果不再重规划)

                logger.info(f"\n--- [观察阶段 - 尝试 {current_planning_attempt_num}] 处理工具结果并更新记忆 ---")
                num_tool_results_added_to_memory = 0
                if final_tool_execution_results:
                    # 遍历所有已尝试执行的工具的结果
                    for tool_exec_res in final_tool_execution_results:
                        tool_call_id_for_mem = tool_exec_res.get('tool_call_id', 'unknown_mock_id')
                        result_dict_for_mem = tool_exec_res.get('result', {"status": "unknown", "message": "结果丢失"})
                        
                        # 确保结果是一个字典,方便 JSON 序列化
                        if not isinstance(result_dict_for_mem, dict): 
                            result_dict_for_mem = {"status": "unknown_format", "message": "非字典格式结果", "raw": str(result_dict_for_mem)}
                            
                        try: # 尝试将结果字典序列化为 JSON 字符串,用于存储在 tool 消息的 content 中
                            result_content_json_str = json.dumps(result_dict_for_mem, ensure_ascii=False, default=str) # default=str 处理不可序列化对象
                        except Exception as json_dump_err_observe: 
                            result_content_json_str = f'{{"status": "serialization_error_observe", "message": "序列化结果失败: {json_dump_err_observe}"}}'
                            logger.error(f"[Orchestrator - Observe] 序列化工具结果 '{tool_call_id_for_mem}' 失败: {json_dump_err_observe}", exc_info=True)
                            
                        # 构建 tool 消息并添加到短期记忆
                        tool_message_for_memory = {"role": "tool", "tool_call_id": tool_call_id_for_mem, "content": result_content_json_str}
                        try: 
                            self.memory_manager.add_to_short_term(tool_message_for_memory)
                            num_tool_results_added_to_memory += 1
                        except Exception as mem_err_tool_res: 
                            logger.error(f"[Orchestrator - Observe] 添加工具 {tool_call_id_for_mem} 结果到记忆失败: {mem_err_tool_res}", exc_info=True)
                            
                logger.info(f"[Orchestrator - Observe] {num_tool_results_added_to_memory}/{len(final_tool_execution_results)} 个工具执行结果已添加至短期记忆. ")

                # 检查本次行动阶段是否有任何工具执行失败
                any_tool_failed_in_this_run = any(res.get('result', {}).get('status') != 'success' for res in final_tool_execution_results) if final_tool_execution_results else False
                
                if any_tool_failed_in_this_run:
                    logger.warning(f"[Orchestrator - Observe] 检测到有工具执行失败. 检查是否需要重规划. ")
                    if replanning_loop_count < self.max_replanning_attempts:
                        # 如果还有重规划次数,则增加计数并继续下一轮重规划循环
                        logger.info(f"[Orchestrator - Observe] 将进行第 {replanning_loop_count + 1}/{self.max_replanning_attempts} 次重规划. ")
                        replanning_loop_count += 1
                        continue # 继续外层重规划循环
                    else:
                        # 如果没有重规划次数了,则彻底失败,中止整个流程
                        logger.critical(f"[Orchestrator - Observe] 已达最大重规划尝试次数 ({self.max_replanning_attempts}),工具执行仍有失败. 中止. ")
                        break # 跳出重规划循环
                else:
                    # 如果所有已执行工具都成功
                    logger.info(f"[Orchestrator - Observe] 所有已执行工具操作均成功. 流程成功. ")
                    break # 跳出重规划循环,进入响应阶段
                    
            else: # 计划是直接回复 (is_tool_calls 为 false)
                logger.info(f"{planning_phase_type_log_prefix} 决策: 根据 JSON 计划直接回复,不执行工具操作. ")
                # **修改点**: 使用新的 async_print,仅在详细模式下打印直接回复提示
                await async_print("--- 大脑认为无需执行操作,将直接回复... ---", agent_verbose_flag=self.verbose_mode, verbose_only=True)
                
                # 检查计划中是否提供了有效的 direct_reply 内容
                if direct_reply_in_plan and isinstance(direct_reply_in_plan, str) and direct_reply_in_plan.strip():
                    logger.info(f"{planning_phase_type_log_prefix} 使用计划中提供的 'direct_reply' 作为最终回复. ")
                    break # 直接回复,跳出重规划循环
                else:
                    # 如果计划指示直接回复但 direct_reply 无效,这是 LLM 的规划错误
                    err_msg_bad_direct_reply = "'is_tool_calls' 为 false 但 'direct_reply' 无效或缺失!这可能是 LLM 生成了无效计划. "
                    logger.error(f"{planning_phase_type_log_prefix} 规划错误: {err_msg_bad_direct_reply}")
                    # 生成一个表示规划错误的工具执行结果 (虽然没执行工具,但也用 tool 消息记录错误)
                    final_tool_execution_results = [{"tool_call_id": "internal_planning_error_bad_direct_reply", "result": {"status": "failure", "message": f"错误: 计划指示直接回复,但回复内容无效. ", "error": {"type": "MalformedPlanDirectReply"}}}]
                    try: # 尝试将这个模拟错误结果添加到记忆
                        self.memory_manager.add_to_short_term({"role": "tool", "tool_call_id": "internal_planning_error_bad_direct_reply", "content": json.dumps(final_tool_execution_results[0]['result'], default=str)})
                    except Exception as mem_err_sim_direct: logger.error(f"{planning_phase_type_log_prefix} 添加模拟直接回复错误到记忆失败: {mem_err_sim_direct}")
                    
                    if replanning_loop_count >= self.max_replanning_attempts: 
                        # 如果已经达到最大重规划次数,彻底失败
                        logger.critical(f"{planning_phase_type_log_prefix} 计划直接回复内容无效,已达最大重规划次数. 中止. ")
                        break # 跳出重规划循环
                    else: 
                        # 如果还有重规划次数,记录警告并尝试重规划
                        logger.warning(f"{planning_phase_type_log_prefix} 计划直接回复内容无效,将在下一轮尝试重规划. ")
                        replanning_loop_count += 1
                        continue # 继续外层重规划循环
        # --- 规划与行动循环结束 ---
        
        # --- 响应生成阶段 ---
        final_agent_response_str = "" # 最终返回给用户的文本响应
        overall_success = False # 标记整个请求处理流程是否成功

        # 判断整个流程是否成功
        # 流程成功定义: 
        # 1. 成功获取了计划 (final_plan_from_llm 不为 None)
        # 2. 如果计划是直接回复 (is_tool_calls=false),且 direct_reply 有效. 
        # 3. 如果计划是工具调用 (is_tool_calls=true),且所有尝试执行的工具都成功. 
        
        if final_plan_from_llm:
            if not final_plan_from_llm.get("is_tool_calls", False):
                # 计划是直接回复
                if final_plan_from_llm.get("direct_reply","").strip(): 
                    overall_success = True # 直接回复内容有效,成功
            else:
                # 计划是工具调用
                if final_tool_execution_results:
                    # 检查所有已尝试执行的工具是否都成功
                    all_attempted_tools_succeeded = not any(res.get('result', {}).get('status') != 'success' for res in final_tool_execution_results)
                    if all_attempted_tools_succeeded: 
                        overall_success = True # 所有尝试工具成功,成功
                elif not final_plan_from_llm.get("tool_list"):
                    # 计划是工具调用但工具列表为空(这种情况虽然是警告,但也视为成功完成了一个空操作计划)
                     overall_success = True 
        
        # 根据流程结果生成最终响应
        if final_plan_from_llm is None:
            # 如果最终未能获取有效计划 (在所有重规划尝试后)
            thinking_summary_for_report = llm_thinking_process_from_planning + f"\n最终规划失败. 原因: {parser_error_msg_this_cycle}"
            reply_text_for_report = f"抱歉,经过 {replanning_loop_count + 1} 次尝试,我还是无法从智能大脑获取一个有效的执行计划 ({parser_error_msg_this_cycle}). "
            # **修改点**: 使用 async_print 打印用户可见的失败提示
            await async_print("\n🔴 最终规划失败,无法继续. ", agent_verbose_flag=self.verbose_mode)
            # 构建最终响应字符串
            final_agent_response_str = f"<think>{thinking_summary_for_report}</think>\n\n{reply_text_for_report}".rstrip()
            
        elif final_plan_from_llm.get("is_tool_calls") and not overall_success:
            # 如果计划是工具调用,但工具执行过程中发生了失败,且已达到最大重规划次数
            thinking_summary_for_report = llm_thinking_process_from_planning + f"\n工具执行过程中发生了失败,或计划本身存在问题,且已达到最大重规划尝试次数. "
            
            # 收集失败工具的详细信息用于报告
            failure_details = "具体失败信息请参考日志. " # 默认信息
            if final_tool_execution_results:
                failed_tool_messages = [f"工具 '{res.get('tool_call_id','N/A').split('_')[2] if '_' in res.get('tool_call_id','N/A') else 'N/A'}': {res.get('result',{}).get('message','无消息')}" for res in final_tool_execution_results if res.get('result',{}).get('status') != 'success']
                if failed_tool_messages: 
                    failure_details = "最后一次尝试中失败的操作包括: \n- " + "\n- ".join(failed_tool_messages)
                    
            reply_text_for_report = f"抱歉,在执行您的指令时遇到了问题. 部分操作未能成功完成,且经过 {self.max_replanning_attempts + 1} 次尝试后仍然无法解决. \n{failure_details}"
            # **修改点**: 使用 async_print 打印用户可见的失败提示
            await async_print("\n🔴 工具执行失败或规划错误,且重规划未成功. ", agent_verbose_flag=self.verbose_mode)
            
            # 请求 LLM 生成失败情况的总结报告 (提供详细的上下文,让 LLM 根据 tool 消息总结失败原因)
            logger.info("\n--- [响应生成 - 失败报告] 请求 LLM 总结失败情况 ---")
            system_prompt_for_failure_report = self._get_response_generation_prompt_v7(
                self.memory_manager.get_memory_context_for_prompt(), 
                self._get_tool_schemas_for_prompt(), 
                tools_were_skipped_or_failed=True # 标记是失败报告,影响 Prompt 内容
            )
            messages_for_llm_failure_report = [{"role": "system", "content": system_prompt_for_failure_report}] + self.memory_manager.short_term
            
            try:
                 # **修改点**: 调用 LLMInterface 生成报告,它现在内部处理流式接收
                 llm_response_for_failure_report = await self.llm_interface.call_llm(messages=messages_for_llm_failure_report, use_tools=False)
                 
                 # 验证 LLM 响应基本结构
                 if llm_response_for_failure_report and llm_response_for_failure_report.get('choices') and llm_response_for_failure_report['choices'][0].get('message') and llm_response_for_failure_report['choices'][0]['message'].get('content'):
                     raw_final_content_from_llm = llm_response_for_failure_report['choices'][0]['message']['content']
                     # 解析 LLM 生成的报告内容,提取思考和正式回复
                     final_thinking_from_llm, final_reply_from_llm = self.output_parser._parse_llm_text_content(raw_final_content_from_llm)
                     try: # 将 LLM 的报告响应添加到短期记忆
                         self.memory_manager.add_to_short_term(llm_response_for_failure_report['choices'][0]['message']) # 直接存储字典
                     except Exception as mem_err_fail_rep: logger.error(f"[Orchestrator] 添加 LLM 失败报告到记忆失败: {mem_err_fail_rep}")
                     # 构建最终响应字符串
                     final_agent_response_str = f"<think>{final_thinking_from_llm}</think>\n\n{final_reply_from_llm}".rstrip()
                     logger.info("[Orchestrator] 已通过 LLM 生成失败情况的总结报告. ")
                 else:
                     # 如果 LLM 生成报告时响应无效,使用预设的备用报告
                     logger.error("[Orchestrator] 请求 LLM 生成失败报告时响应无效. 使用预设备用报告. ")
                     final_agent_response_str = f"<think>{thinking_summary_for_report}\n第二次 LLM 响应无效或内容为空,未能生成规范的失败报告. </think>\n\n{reply_text_for_report}".rstrip()
                     
            except Exception as e_llm_fail_report:
                 # 捕获调用 LLM 生成报告时发生的严重错误
                 logger.critical(f"[Orchestrator] 请求 LLM 生成失败报告时发生严重错误: {e_llm_fail_report}", exc_info=True)
                 # 构建包含错误信息的最终响应字符串
                 final_agent_response_str = f"<think>{thinking_summary_for_report}\n生成失败报告时出错: {e_llm_fail_report}</think>\n\n{reply_text_for_report}".rstrip()
                 
        else: # overall_success is True (规划成功且工具成功 或 规划直接回复成功)
            logger.info("[Orchestrator] 流程成功完成. 准备生成最终报告. ")
            
            if final_plan_from_llm.get("is_tool_calls"):
                # 如果是通过执行工具成功的,请求 LLM 总结成功结果
                logger.info("\n--- [响应生成 - 成功报告] 请求 LLM 总结成功结果 ---")
                system_prompt_for_success_report = self._get_response_generation_prompt_v7(
                    self.memory_manager.get_memory_context_for_prompt(), 
                    self._get_tool_schemas_for_prompt(), 
                    tools_were_skipped_or_failed=False # 标记是成功报告,影响 Prompt 内容
                )
                messages_for_llm_success_report = [{"role": "system", "content": system_prompt_for_success_report}] + self.memory_manager.short_term
                
                try:
                    # **修改点**: 调用 LLMInterface 生成报告,它现在内部处理流式接收
                    llm_response_for_success_report = await self.llm_interface.call_llm(messages=messages_for_llm_success_report, use_tools=False)
                    logger.info("[Orchestrator] 第二次 LLM 调用完成 (生成成功报告). ")
                    # **修改点**: 使用新的 async_print,仅在详细模式下打印报告生成完成信息
                    await async_print("--- 大脑已生成最终报告 ---", agent_verbose_flag=self.verbose_mode, verbose_only=True)
                    
                    # 验证 LLM 报告响应基本结构
                    if not llm_response_for_success_report or not llm_response_for_success_report.get('choices') or not llm_response_for_success_report['choices'][0].get('message') or not llm_response_for_success_report['choices'][0]['message'].get('content'):
                        logger.error("[Orchestrator] 第二次 LLM 响应无效或内容为空 (成功报告). ")
                        # 如果 LLM 生成报告时响应无效,使用预设的备用报告
                        final_agent_response_str = f"<think>{llm_thinking_process_from_planning}\n第二次 LLM 响应无效或内容为空. </think>\n\n所有操作均已成功执行,但我无法从智能大脑获取规范的总结报告. "
                    else:
                         final_response_message_obj = llm_response_for_success_report['choices'][0]['message'] # 获取核心消息对象
                         # 解析 LLM 生成的报告内容
                         final_thinking_from_llm, final_reply_from_llm = self.output_parser._parse_llm_text_content(final_response_message_obj['content'])
                         try: # 将 LLM 的报告响应添加到短期记忆
                            self.memory_manager.add_to_short_term(final_response_message_obj) # 直接存储字典
                         except Exception as mem_err_succ_rep: logger.error(f"[Orchestrator] 添加最终成功回复到记忆失败: {mem_err_succ_rep}")
                         # 构建最终响应字符串
                         final_agent_response_str = f"<think>{final_thinking_from_llm}</think>\n\n{final_reply_from_llm}".rstrip()
                         logger.info("[Orchestrator] 已通过 LLM 生成操作成功的总结报告. ")
                         
                except Exception as e_llm_succ_report:
                     # 捕获调用 LLM 生成报告时发生的严重错误
                     logger.critical(f"[Orchestrator] 第二次 LLM 调用或最终成功报告处理失败: {e_llm_succ_report}", exc_info=True)
                     # 构建包含错误信息的最终响应字符串
                     final_agent_response_str = f"<think>{llm_thinking_process_from_planning}\n第二次 LLM 调用失败: {e_llm_succ_report}</think>\n\n所有操作均已成功执行,但在为您准备最终报告时遇到了严重的内部错误!"
                     
            else:
                # 如果计划是直接回复成功的
                direct_reply_content = final_plan_from_llm.get("direct_reply", "未能获取直接回复内容. ")
                # 直接使用计划中的 direct_reply 内容构建最终响应
                final_agent_response_str = f"<think>{llm_thinking_process_from_planning}</think>\n\n{direct_reply_content}".rstrip()
                logger.info("[Orchestrator] 流程通过直接回复成功完成. ")

        request_end_time = time.monotonic() # 记录请求结束时间
        total_duration_seconds = request_end_time - request_start_time # 计算总耗时
        logger.info(f"\n{'='*25} V7.2.3 请求处理完毕 (总耗时: {total_duration_seconds:.3f} 秒) {'='*25}\n") # 版本号更新,日志标记结束
        
        return final_agent_response_str # 返回最终响应字符串


    # --- Helper Methods for Prompts (辅助生成提示) ---
    def _get_tool_schemas_for_prompt(self) -> str:
        """
        根据 Agent 内部的工具注册表,动态生成工具描述字符串,用于提供给 LLM. 
        """
        if not self.tools_registry: return "  (无可用工具)" # 如果没有注册工具,返回无工具提示
        
        tool_schemas_parts = []
        # 遍历所有注册的工具
        for tool_name, schema in self.tools_registry.items():
            desc = schema.get('description', '无描述. ') # 工具描述
            params_schema = schema.get('parameters', {}) # 参数 Schema
            props_schema = params_schema.get('properties', {}) # 参数属性
            req_params = params_schema.get('required', []) # 必需参数列表
            
            # 构建参数描述字符串列表
            param_desc_segments = [f"'{k}': ({v.get('type','any')}, {'必须' if k in req_params else '可选'}) {v.get('description','无描述')}" for k,v in props_schema.items()] if props_schema else ["无参数"]
            
            # 构建单个工具的描述字符串,并添加到列表
            tool_schemas_parts.append(f"  - 工具名称: `{tool_name}`\n    描述: {desc}\n    参数: {'; '.join(param_desc_segments)}")
            
        return "\n".join(tool_schemas_parts) # 将所有工具描述合并成一个字符串


    def _get_planning_prompt_v7(self, tool_schemas_desc: str, memory_context: str,
                                is_replanning: bool = False, 
                                previous_results: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        构建规划阶段调用的 System Prompt. 
        该 Prompt 指导 LLM 分析指令、上下文,并严格按照自定义 JSON 格式输出行动计划或直接回复. 
        V7.2.1 (老板的指示): 为直接问答/概念解释添加了明确指导和示例. 
        V7.2.3: 提示中已包含对 tool 消息的处理指导,因此 previous_results 参数虽保留但不直接用于构建 Prompt 文本,LLM 需要自行从 history 中理解. 
        """
        # 根据是否是重规划,生成不同的指导信息
        replanning_guidance = ""
        if is_replanning:
            replanning_guidance = (
                "\n【重要: 重规划指示】\n"
                "这是对您先前规划的修正尝试. 上次执行您的计划时,部分或全部工具操作遇到了问题,或者计划本身可能存在缺陷. 您必须仔细回顾完整的对话历史,特别是角色为 'tool' 的消息(它们包含了上次工具执行失败的详细原因),以及您自己之前的思考和规划. 请基于这些信息: \n"
                "1. 分析失败的根本原因. \n"
                "2. 提出一个能够克服先前问题的、全新的、经过深思熟虑的执行计划. \n"
                "3. 如果您认为用户指令本身有问题、无法通过现有工具完成,或者多次尝试后仍无法成功,您可以在新计划的 JSON 中将 `is_tool_calls` 设置为 `false`,并在 `direct_reply` 字段中提供一个清晰、礼貌的解释性回复给用户,说明情况和您的建议. \n"
                "不要简单重复失败的计划!展现您的智能和适应性. \n"
            )

        # ===================================================================================
        # 老板,这里是为处理概念性问题新增/强化的部分!
        # ===================================================================================
        direct_qa_guidance = (
            "\n【重要: 处理直接问答、概念解释或无需工具的请求】\n"
            "当用户的指令是提出一个概念性问题、请求解释、进行一般性对话,或任何你判断【不需要调用任何工具】就能直接回答的情况时,你【仍然必须严格遵循】下面的输出格式要求: \n"
            "1.  `<think>...</think>` 块: 如常进行思考,解释你为什么认为这是一个可以直接回答的问题,以及你打算如何回答. \n"
            "2.  紧随其后的 JSON 对象: 在此 JSON 对象中: \n"
            "    - `is_tool_calls` 字段【必须】设置为 `false`. \n"
            "    - `direct_reply` 字段【必须】包含你准备提供给用户的【完整、清晰、友好】的文本回答. 这个回答应该是最终的,不需要后续处理. \n"
            "    - `tool_list` 字段此时【必须】为 `null` 或者一个空数组 `[]`. \n"
            "简而言之: 即使是直接回答,也必须用我们约定的 `<think>` + JSON 结构来包装你的思考和回答内容. \n"
            "例如,如果用户问: “你好吗？”,你的输出应该是类似(仅为格式示例,具体思考和回复内容应根据实际情况): \n"
            "<think>\n用户在进行日常问候,这是一个可以直接回答的问题,不需要工具. 我将礼貌地回复. \n</think>\n"
            "{\n"
            "  \"is_tool_calls\": false,\n"
            "  \"tool_list\": null,\n" # 或者 [] 也可以,但 null 更简洁
            "  \"direct_reply\": \"您好!我目前一切正常,随时准备为您服务. 有什么可以帮您的吗？\"\n"
            "}\n"
        )
        # ===================================================================================
        # 新增/强化部分结束
        # ===================================================================================

        return (
            "你是一位顶尖的、极其严谨的电路设计编程助理. 你的行为必须专业、精确,并严格遵循指令. \n"
            "你的核心任务是: 深入分析用户的最新指令、完整的对话历史(包括你之前的思考、规划以及所有工具执行结果),以及当前的电路状态. 然后,你必须严格按照下面描述的固定格式,生成一个包含你行动计划的 JSON 对象. \n"
            f"{replanning_guidance}" # 如果是重规划,包含重规划的指导
            f"{direct_qa_guidance}"  # 处理直接问答的指导
            "【输出格式总览】\n"
            "你的输出必须由两部分组成,且严格按此顺序: \n"
            "1.  `<think>...</think>` XML 块: 在此块中,详细阐述你的思考过程. 这应包括: \n"
            "    - 对用户最新指令的精确理解. \n"
            "    - 对当前电路状态、历史对话和记忆的综合分析. \n"
            "    - 明确决定是否需要调用工具. 如果需要,调用哪些工具,为什么,以及参数如何从指令中提取. 如果不需要调用工具,则说明原因并准备直接回复. \n"
            "    - 规划具体的执行步骤和顺序(如果调用工具),或规划直接回复的内容(如果不调用工具). \n"
            "    - 对潜在问题的评估和预案. \n"
            "    - 如果是重规划,必须详细分析之前工具失败的原因或计划缺陷,并清晰说明新计划如何修正这些问题. \n"
            "2.  紧随其后,不加任何其他文字、解释或注释,必须是一个单一的、格式完全正确的 JSON 对象. 此 JSON 对象代表你最终的执行计划或直接回复. \n\n"
            "【JSON 对象格式规范 (必须严格遵守)】\n"
            "该 JSON 对象必须包含以下顶级字段: \n"
            "  A. `is_tool_calls` (boolean): 【必需】\n"
            "     - `true`: 如果分析后认为需要执行一个或多个工具操作来满足用户请求. \n"
            "     - `false`: 如果不需要执行任何工具(例如,可以直接回答问题、进行确认、或认为请求无法处理/需要澄清,此时答案放在`direct_reply`中). \n"
            "  B. `tool_list` (array<object> | null): 【必需】其内容严格依赖于 `is_tool_calls` 的值: \n"
            "     - 当 `is_tool_calls` 为 `true` 时: 此字段【必须】是一个包含一个或多个“工具调用对象”的【数组】. 数组中的对象必须按照你期望的执行顺序列出. \n"
            "     - 当 `is_tool_calls` 为 `false` 时: 此字段【必须】是 `null` 值或者一个【空数组 `[]`】. \n"
            "     【工具调用对象】结构 (如果 `tool_list` 非空):\n"
            "       1. `toolname` (string): 【必需】要调用的工具的精确名称. 必须是下方 [可用工具列表] 中列出的名称之一. \n"
            "       2. `params` (object): 【必需】一个包含调用该工具所需参数的 JSON 对象. 参数的键和值类型必须严格符合工具 Schema 中的定义. 如果无参数,则为空对象 `{}`. \n"
            "       3. `index` (integer): 【必需】表示此工具调用在当前规划批次中的执行顺序,从 `1` 开始的正整数,且连续. 这是为了确保工具按预期顺序执行. \n"
            "  C. `direct_reply` (string | null): 【必需】其内容严格依赖于 `is_tool_calls` 的值: \n"
            "     - 当 `is_tool_calls` 为 `false` 时: 此字段【必须】包含你准备直接回复给用户的最终、完整、友好的文本内容. 回复内容【禁止】为空字符串或仅包含空白. \n"
            "     - 当 `is_tool_calls` 为 `true` 时: 此字段【必须】是 `null` 值. \n\n"
            "【可用工具列表与参数规范】:\n"
            f"{tool_schemas_desc}\n\n" # 包含所有可用工具的 Schema 描述
            "【当前上下文信息】:\n"
            f"当前电路与记忆摘要:\n{memory_context}\n\n" # 包含电路状态和近期长期记忆的描述
            "【最后再次强调】: 你的回复格式必须严格是 `<think>思考过程</think>` 后面紧跟着一个符合上述所有规范的 JSON 对象. 不允许有任何偏差!请确保 JSON 格式完全正确,能够被程序解析. "
        )

    def _get_response_generation_prompt_v7(self, memory_context: str, tool_schemas_desc: str, tools_were_skipped_or_failed: bool) -> str:
        """
        构建最终响应生成阶段调用的 System Prompt. 
        该 Prompt 指导 LLM 根据完整的对话历史(特别是工具执行结果)生成面向用户的最终回复. 
        """
        # 根据工具执行是成功还是失败/跳过,提供不同的指导信息
        skipped_or_failed_guidance = ""
        if tools_were_skipped_or_failed:
            skipped_or_failed_guidance = (
                "\n【重要: 处理失败或跳过的工具】\n"
                "在之前的工具执行过程中,可能由于某个工具最终失败,导致了后续工具被中止执行；或者计划本身存在缺陷. 请在你的最终报告中: \n"
                "1. 明确指出哪些操作成功了,哪些失败了. \n"
                "2. 对于失败的操作,根据 'tool' 消息中的信息,向用户清晰、诚实地解释失败的原因及其影响. \n"
                "3. 如果有任务因此未能完成或被跳过,请明确说明. \n"
                "4. 总结本次处理的结果,并考虑下一步可以如何协助用户(例如,是否需要他们修改指令或提供更多信息). "
            )
        else:
             skipped_or_failed_guidance = (
                "\n【提示: 总结成功操作】\n"
                "之前计划的所有工具操作(如果有的话)均已成功执行. 请仔细阅读对话历史中角色为 'tool' 的消息,它们包含了每个已执行工具的详细结果. 您应该: \n"
                "1. 根据这些成功结果,向用户确认所有操作均已按预期完成. \n"
                "2. 综合所有操作的结果,形成一个连贯、完整、对用户有帮助的最终回复. \n"
                "3. 如果执行了改变电路状态的操作,可以在回复中提及当前电路的关键状态变化或引导用户询问当前电路状态. \n"
                "4. 考虑用户接下来可能需要什么帮助,并给出相应的建议或引导. "
            )
            
        return (
            "你是一位顶尖的电路设计编程助理,经验丰富,技术精湛,并且极其擅长清晰、准确、诚实地汇报工作结果. \n"
            "你当前的核心任务是: 基于到目前为止的【完整对话历史】(包括用户最初的指令、你之前的思考和规划、以及所有【已执行工具的结果详情】),生成最终的、面向用户的文本回复. 请重点关注历史中角色为 'tool' 的消息,它们是你的工作成果反馈. \n"
            "【关键信息来源】: 对话历史中角色为 'tool' 的消息,其 `content` 字段的 JSON 字符串包含了工具执行的 `status`, `message`, 和可能的 `error`. \n"
            "你的最终报告输出【必须】严格遵循以下两部分格式: \n"
            "1.  `<think>...</think>` XML 块: 进行详细的【反思和报告组织思路】. \n"
            f"    {skipped_or_failed_guidance}" # 包含针对成功或失败情况的总结指导
            "2.  正式回复文本: 在 `</think>` 标签【之后】,紧跟着面向用户的【正式文本回复】. 此回复应直接基于你在 `<think>` 块中的分析和规划. \n"
            "【最终输出格式示例 (必须严格遵守)】:\n"
            "`<think>\n在这里详细地写下你的思考过程,如何综合工具结果来形成回复...\n</think>\n\n您好!我已经成功为您完成了操作...`\n"
            "(注意: `</think>` 标签后必须恰好是【两个换行符 `\\n\\n`】,然后直接是正式回复文本. 不允许在它们之间有任何其他字符,包括空格. )\n"
            "【重要】: 在这个阶段,你【绝对不能】再生成任何工具调用或 JSON 对象. 你的唯一任务是生成最终的、用户友好的文本回复. \n\n"
            "【上下文参考信息 (仅供你回顾)】:\n"
            f"当前电路与记忆摘要:\n{memory_context}\n" # 提供电路状态和长期记忆作为参考
            f"我的可用工具列表 (仅供你参考,不要在这里生成工具调用):\n{tool_schemas_desc}\n" # 提供工具列表作为参考
            "请务必生成高质量、信息完整、格式正确的回复. 你的回复是用户体验的关键!"
        )


# --- 异步主函数 (应用程序入口) ---
# async def main():
#     """异步主函数,初始化 Agent 并启动主交互循环"""
#     # 使用 parse_known_args() 来解析命令行参数,并忽略任何未知参数 (这对于在 Jupyter 中运行时很有用,Jupyter 会传递额外的参数)
#     import argparse
#     parser = argparse.ArgumentParser(description="启动 OpenManus 电路设计 Agent V7.2.3") # 版本号更新
#     # 添加 --verbose 参数,如果出现则将 verbose 设为 True,默认也设为 True
#     parser.add_argument('--verbose', action='store_true', default=True, help='启用详细模式输出 (默认启用)')
#     # 添加 --concise 参数,如果出现则将 verbose 设为 False,覆盖 --verbose
#     parser.add_argument('--concise', action='store_false', dest='verbose', help='启用简洁模式输出 (覆盖 --verbose)')
    
#     # 使用 parse_known_args() 而不是 parse_args()
#     # 它会返回一个包含已知参数的命名空间和一个包含未知参数的列表
#     args, unknown = parser.parse_known_args() 
#     is_verbose = args.verbose # 获取解析后的 verbose 参数值

#     # 如果有无法识别的参数,打印一个警告(但程序继续执行)
#     if unknown:
#         logger.warning(f"[Main] 忽略了无法识别的命令行参数: {unknown}")
#         # 在Jupyter环境中,这通常是正常的,不需要向用户显示警告,但日志应该记录
#         # print(f"警告: 忽略了无法识别的命令行参数: {unknown}", file=sys.stderr) # 可以选择性地向stderr打印用户可见警告

#     # 在 Agent 初始化之前,根据解析到的 verbose 标志,调整控制台日志处理器的级别
#     # 这里的 async_print 需要 agent_verbose_flag,但 Agent 还没初始化,
#     # 暂时使用解析到的 is_verbose. Agent 初始化后,async_print 会使用 Agent 实例自己的 verbose_mode. 
#     global console_handler # 引用全局 console_handler
#     console_log_level = logging.DEBUG if is_verbose else logging.INFO
#     console_handler.setLevel(console_log_level)
    
#     await async_print("=" * 70, agent_verbose_flag=is_verbose) # 初始化打印也需要flag
#     await async_print("🚀 启动 OpenManus 电路设计 Agent (V7.2.3 Streaming LLM, Refactored with Verbose Switch) 🚀", agent_verbose_flag=is_verbose) # 版本号更新
#     await async_print("   特性: 异步核心, 对象化状态, 动态工具注册, LLM重试, 工具重试, 重规划,", agent_verbose_flag=is_verbose)
#     await async_print("         内存修剪, 文件日志, 强化问答, 可选详细输出, 内部 LLM 流式交互. ", agent_verbose_flag=is_verbose) # 添加流式特性描述
#     await async_print("=" * 70, agent_verbose_flag=is_verbose)
#     logger.info("[Main] 开始 Agent 初始化 (V7.2.3)...") # 版本号更新
#     logger.info(f"[Main] Verbose mode set to: {is_verbose}")

#     # 获取智谱AI API Key
#     # 先尝试从环境变量 ZHIPUAI_API_KEY 读取
#     api_key_env = os.environ.get("ZHIPUAI_API_KEY")
#     if not api_key_env:
#         # 如果环境变量未设置,提示用户手动输入
#         logger.warning("[Main] 环境变量 ZHIPUAI_API_KEY 未设置. 将提示用户输入. ")
#         # **修改点**: 使用 async_print 打印提示信息,确保异步环境安全,不受 verbose 影响
#         await async_print("\n为了连接智能大脑,我需要您的智谱AI API Key. ", agent_verbose_flag=True) 
#         try: 
#             # 使用 input 获取同步输入,但在 async 函数中,这会阻塞. 
#             # 在标准脚本的 asyncio.run 中,input 是可以工作的. 在 Jupyter 中,input 也工作. 
#             # 对于更复杂的异步应用,可能需要一个专门的异步输入机制,但此处场景可以接受. 
#             api_key_input = input("👉 请在此输入您的智谱AI API Key: ").strip()
#         except (EOFError, KeyboardInterrupt): 
#             # 捕获输入中断错误
#             await async_print("\nAPI Key 输入被中断. 程序退出. ", agent_verbose_flag=True) # 错误信息总是打印
#             return # 退出程序
#         if not api_key_input: 
#             # 如果用户未提供 API Key
#             await async_print("\n错误: 未提供 API Key. 程序退出. ", agent_verbose_flag=True) # 错误信息总是打印
#             return # 退出程序
#         final_api_key = api_key_input
#         logger.info("[Main] 已通过手动输入获取 API Key. ")
#     else:
#         final_api_key = api_key_env
#         logger.info("[Main] 已从环境变量 ZHIPUAI_API_KEY 获取 API Key. ")

#     agent_instance = None # Agent 实例变量
#     try:
#         # 初始化 Agent 实例
#         agent_instance = CircuitDesignAgentV7(
#             api_key=final_api_key,
#             model_name="glm-4-flash-250414", # 使用推荐的 flash 模型
#             planning_llm_retries=1, # 规划阶段 LLM 调用失败重试 1 次
#             max_tool_retries=2, # 工具执行失败最多重试 2 次
#             tool_retry_delay_seconds=0.5, # 工具重试间隔 0.5 秒
#             max_replanning_attempts=2, # 工具执行失败后最多重规划 2 次
#             max_short_term_items=25, # 短期记忆上限 25 条
#             verbose=is_verbose # 传入命令行解析到的 verbose 标志
#         )
#         # 现在 Agent 初始化成功后,agent_instance.verbose_mode 才可用
#         # 使用 agent_instance.verbose_mode 来控制后续的 async_print 输出
#         await async_print("\n🎉 Agent V7.2.3 初始化成功!已准备就绪. ", agent_verbose_flag=agent_instance.verbose_mode) # 版本号更新
#         await async_print(f"ℹ️  提示: 详细日志正被记录到文件: {os.path.abspath(log_file_name)}", agent_verbose_flag=agent_instance.verbose_mode)
#         await async_print("\n您可以尝试以下指令:", agent_verbose_flag=agent_instance.verbose_mode)
#         await async_print("  - '给我加个1k电阻R1和3V电池B1'", agent_verbose_flag=agent_instance.verbose_mode)
#         await async_print("  - '连接R1和B1'", agent_verbose_flag=agent_instance.verbose_mode)
#         await async_print("  - '电路现在什么样？'", agent_verbose_flag=agent_instance.verbose_mode)
#         await async_print("  - '这个电路是如何实现功能的？'", agent_verbose_flag=agent_instance.verbose_mode)
#         await async_print("  - '清空电路'", agent_verbose_flag=agent_instance.verbose_mode)
#         await async_print("  - 输入 '退出' 来结束程序", agent_verbose_flag=agent_instance.verbose_mode)
#         await async_print("  - '设计一个RC滤波电路,至少带五个元件,参数你自己决定'", agent_verbose_flag=agent_instance.verbose_mode)
#         await async_print("  - 输入 '帮助' 来查看更多指令", agent_verbose_flag=agent_instance.verbose_mode)
#         await async_print("-" * 70, agent_verbose_flag=agent_instance.verbose_mode)
        
#     except Exception as e_agent_init:
#         # 如果 Agent 初始化失败
#         logger.critical(f"[Main] Agent V7.2.3 初始化失败: {e_agent_init}", exc_info=True) # 版本号更新
#         error_msg_init = f"\n🔴 Agent 初始化失败!错误: {e_agent_init}. 程序退出. "
#         # 此时 agent_instance 可能为 None,所以直接用 True 打印错误,确保错误信息显示
#         await async_print(error_msg_init, agent_verbose_flag=True) 
#         sys.stderr.write(error_msg_init + "\n"); sys.stderr.flush()
#         return # 退出程序

#     # --- 主交互循环 ---
#     try:
#         while True:
#             user_input_str = ""
#             try: 
#                 # 获取用户输入
#                 user_input_str = input("用户 > ").strip()
#             except KeyboardInterrupt: 
#                 # 捕获用户通过 Ctrl+C 中断输入
#                 await async_print("\n用户中断输入. 输入 '退出' 以结束. ", agent_verbose_flag=agent_instance.verbose_mode); 
#                 continue # 继续循环,等待用户输入退出指令
#             except EOFError: 
#                 # 捕获输入流结束 (如文件重定向结束)
#                 await async_print("\n输入流结束. 正在退出...", agent_verbose_flag=agent_instance.verbose_mode); 
#                 break # 退出循环,程序结束

#             if user_input_str.lower() in ['退出', 'quit', 'exit', '再见', '结束', 'bye']:
#                 # 处理退出指令
#                 await async_print("\n收到退出指令. 感谢您的使用!👋", agent_verbose_flag=agent_instance.verbose_mode); 
#                 break # 退出循环,程序结束
                
#             if not user_input_str: 
#                 # 如果用户输入为空白,则跳过处理,继续等待输入
#                 continue

#             # --- 处理用户请求 ---
#             start_process_time_mono = time.monotonic() # 记录请求处理开始时间
#             agent_response_str = "" # 存储 Agent 生成的最终回复字符串
            
#             try: 
#                 # 调用 Agent 实例的处理方法
#                 agent_response_str = await agent_instance.process_user_request(user_input_str)
#             except KeyboardInterrupt:
#                 # 捕获用户在处理过程中通过 Ctrl+C 中断
#                 await async_print("\n用户操作被中断. ", agent_verbose_flag=agent_instance.verbose_mode)
#                 logger.warning(f"[Main Loop] 用户中断了对指令 '{user_input_str[:50]}...' 的处理. ")
#                 agent_response_str = "<think>用户中断了当前请求的处理. </think>\n\n操作已取消. " # 生成一个取消提示回复
#             except Exception as e_process_req:
#                 # 捕获处理请求过程中发生的任何其他意外错误
#                 logger.error(f"[Main Loop] 处理指令 '{user_input_str[:50]}...' 时发生意外错误: {e_process_req}", exc_info=True)
#                 # 将 traceback 截断后添加到思考过程,方便调试
#                 tb_str_for_think = traceback.format_exc().replace('\n', ' | ')
#                 agent_response_str = f"<think>处理指令时发生内部错误: {e_process_req}. Traceback: {tb_str_for_think[:500]}...</think>\n\n抱歉,我在执行您的指令时遇到了意外问题!"
            
#             process_duration_sec = time.monotonic() - start_process_time_mono # 计算请求处理总耗时

#             # 打印 Agent 的最终回复和耗时信息
#             # 响应头和分隔符总是打印,不受 verbose 影响
#             await async_print(f"\n📝 Agent 回复 (总耗时: {process_duration_sec:.3f} 秒):", agent_verbose_flag=True) 
#             await async_print(agent_response_str, agent_verbose_flag=True) # 响应内容总是打印
#             await async_print("-" * 70, agent_verbose_flag=True) # 分隔符总是打印

#     except Exception as outer_loop_err:
#         # 捕获主交互循环之外发生的未处理异常
#         logger.critical(f"[Main Loop] 主交互循环外发生未处理异常: {outer_loop_err}", exc_info=True)
#         await async_print(f"\n🔴 严重系统错误导致交互循环终止: {outer_loop_err}. ", agent_verbose_flag=True) # 错误总是打印
#     finally:
#         logger.info("[Main] 主交互循环结束. ")
#         await async_print("\n正在关闭 Agent V7.2.3...", agent_verbose_flag=True) # 关闭消息总是打印,版本号更新


# --- 用于 Jupyter/IPython 环境的辅助函数 ---
# async def run_agent_in_jupyter():
#     """
#     在 Jupyter/IPython 环境中安全启动 Agent 交互循环. 
#     在 Jupyter 中无法直接通过命令行参数控制 verbose,此函数默认以详细模式启动. 
#     """
#     print("正在尝试以 Jupyter/IPython 兼容模式启动 Agent V7.2.3 (默认详细模式)...") # 版本号更新
#     print("请在下方的输入提示处输入指令. 输入 '退出' 结束. ")
#     print(f"Jupyter 模式下,日志同样会记录到: {os.path.abspath(log_file_name) if 'log_file_name' in globals() else '日志文件路径未确定'}")
    
#     # 手动模拟设置 verbose=True (因为无法方便地从Jupyter传递命令行参数)
#     # 注意: 这里设置的 is_verbose 变量会影响 main 函数的逻辑,main 函数中的 arg parsing 仍然会运行,
#     # 但如果直接调用 main() 并且没有命令行参数,它的默认值通常也是 True. 
#     # 更安全的做法是让 main 函数接收 verbose 参数,然后在这里传递. 
#     # 为了保持与用户提供的代码结构一致,我们依赖 main 函数中的 args.verbose. 
#     # 但为了确保日志级别在Agent实例化前设置,我们需要在这里先行根据假定的 verbose 模式设置 console handler 级别. 
#     is_verbose_for_jupyter_setup = True # 在Jupyter中默认假定详细模式
    
#     # **重要**: 需要确保在Agent初始化前设置日志级别
#     global console_handler
#     console_log_level = logging.DEBUG if is_verbose_for_jupyter_setup else logging.INFO
#     console_handler.setLevel(console_log_level)
#     logger.info(f"[Jupyter Setup] 控制台日志级别设置为: {logging.getLevelName(console_log_level)} (Jupyter 默认 verbose=True). ")

#     try: 
#         # 直接调用 main 函数,main 函数内部会再次解析(或使用默认)参数来设置 agent 的 verbose 模式
#         # 由于我们在顶层模块已经配置了 console_handler 并设置了级别,这里不再需要额外操作. 
#         # main 函数内部会创建 Agent 实例,该实例会读取其自身的 verbose_mode 并用于 async_print. 
#         await main() 
#     except Exception as e_jupyter: 
#         print(f"\n🔴 Agent 在 Jupyter 模式下运行时遇到错误: {e_jupyter}")
#         logger.error(f"Jupyter 模式错误: {e_jupyter}", exc_info=True)
#     finally: 
#         print("Agent 交互已结束 (Jupyter 模式). ")


# # --- 标准 Python 脚本入口点 ---
# if __name__ == "__main__":
#     # 检测当前运行环境是否为 IPython/Jupyter
#     detected_shell_name = None
#     try: 
#         # get_ipython() 仅在 IPython 环境中存在
#         detected_shell_name = get_ipython().__class__.__name__
#     except NameError: 
#         # 如果 get_ipython() 不存在,则可能是标准 Python 环境
#         detected_shell_name = "StandardPython"
#     except Exception as e_get_ipython: 
#         # 捕获检测 IPython 时可能发生的其他错误
#         logger.warning(f"检测 IPython 环境出错: {e_get_ipython}. 将按标准 Python 环境处理. "); 
#         detected_shell_name = "StandardPython"

#     if detected_shell_name == 'ZMQInteractiveShell':
#         # 在 Jupyter Notebook 或 JupyterLab 环境中 (ZMQ 类型的 shell)
#         print("检测到 Jupyter/IPython (ZMQ) 环境. 请在 cell 中执行 `await run_agent_in_jupyter()` 启动. ")
#         logger.info("Jupyter/IPython (ZMQ) 环境检测到. 建议用户使用 await run_agent_in_jupyter(). ")
#         # 在这种环境下,__main__ 块的代码会执行一次,但不会进入交互循环,
#         # 用户需要在 cell 中 await run_agent_in_jupyter() 来启动实际的交互. 
#         # run_agent_in_jupyter 函数会处理日志级别和调用 main. 
        
#     elif detected_shell_name in ['TerminalInteractiveShell', 'StandardPython']:
#         # 在终端的 IPython 环境或标准的 Python 脚本执行环境中
#         if detected_shell_name == 'TerminalInteractiveShell': logger.info("Terminal IPython 环境检测到. 标准模式启动. ")
#         else: logger.info("标准 Python 环境检测到. 启动 Agent. ")
        
#         # 直接运行异步主函数 main
#         # main 函数内部会解析命令行参数 (如果提供了的话),并根据参数设置 verbose
#         try: 
#             asyncio.run(main())
#         except KeyboardInterrupt: 
#             print("\n程序被用户强制退出. "); 
#             logger.info("[Main Script] 程序被 KeyboardInterrupt 中断. ")
#         except Exception as e_top_level: 
#             # 捕获 main 函数中未被处理的顶层异常
#             print(f"\n程序因顶层错误而意外退出: {e_top_level}"); 
#             logger.critical(f"顶层异常: {e_top_level}", exc_info=True)
#         finally: 
#             print("Agent V7.2.3 程序已关闭. ") # 版本号更新
            
#     else:
#         # 检测到未知类型的 Shell
#         logger.warning(f"检测到未知的 Shell 类型: {detected_shell_name}. 尝试标准模式启动 (默认详细模式). ")
        
#         # 对于未知环境,也默认使用 verbose=True
#         # 这里需要手动设置 console handler 的级别,因为 main 函数的参数解析依赖命令行,未知环境可能没有
#         is_verbose_for_unknown_shell = True # 手动设置默认值
#         global console_handler # 引用全局 console_handler
#         console_log_level = logging.DEBUG if is_verbose_for_unknown_shell else logging.INFO
#         console_handler.setLevel(console_log_level)
#         logger.info(f"[Unknown Shell Setup] 控制台日志级别设置为: {logging.getLevelName(console_log_level)} (未知 Shell 默认 verbose=True). ")
        
#         try: 
#             # 运行异步主函数 main
#             # main 函数内部会读取其自身的 args.verbose,如果命令行没有则使用默认值 True
#             asyncio.run(main()) 
#         except KeyboardInterrupt: 
#             print("\n程序被用户强制退出. "); 
#             logger.info("[Main Script - Unknown Shell] 程序被 KeyboardInterrupt 中断. ")
#         except Exception as e_top_level_unknown: 
#             print(f"\n程序因顶层错误而意外退出: {e_top_level_unknown}"); 
#             logger.critical(f"顶层异常 (未知 Shell): {e_top_level_unknown}", exc_info=True)
#         finally: 
#             print("Agent V7.2.3 程序已关闭 (未知 Shell 环境). ") # 版本号更新
