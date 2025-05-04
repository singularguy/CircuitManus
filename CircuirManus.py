# -*- coding: utf-8 -*-
# @FileName: openmanus_v8_refactored.py
# @Version: V8.0 - Refactored, Robust Single-Step Planning, Modular
# @Author: Your Most Loyal & Dedicated Programmer (Refactored V8)
# @Date: [Current Date]
# @License: Apache 2.0 (Anticipated)
# @Description:
# ==============================================================================================
#  Manus 系统 V8.0 技术实现说明 (重构版 - 应对无 Function Calling 模型)
# ==============================================================================================
# 老板您好！这是根据您的宝贵意见和我们深入讨论后，全面重构的 V8 版本。
# 核心目标：在确保代码健壮性、可维护性和优雅性的前提下，
#           特别优化了与不支持 Function Calling 的 LLM 的交互方式。
#
# 主要改进：
# 1.  **模块化设计:** 将代码拆分为配置、异常、工具、内存管理、LLM 接口、
#     输出解析、工具执行器、Agent 核心和主程序等独立模块 (在当前单文件
#     实现中，用清晰的类和函数划分模拟了模块化结构)。
# 2.  **单步规划循环:** 鉴于 LLM 不支持 Function Calling，我们不再要求它
#     一次生成复杂的多步计划。Agent 现在引导 LLM 进行单步规划：
#     LLM 要么决定调用 *一个* 工具，要么决定直接回复。Agent 执行工具后，
#     将结果反馈给 LLM，让其规划下一步，直至任务完成或 LLM 决定回复。
#     这极大地提高了规划的可靠性。
# 3.  **简化的 LLM 输出:** LLM 只需输出两种简单结构之一：
#     - 调用工具: `{"action": "tool_call", "tool_name": "...", "params": {...}}`
#     - 直接回复: `{"action": "direct_reply", "content": "..."}`
# 4.  **增强的 JSON 解析:** OutputParser 专注于解析这两种简单结构，并增加了
#     对 LLM 可能输出的无关文本的清理逻辑，提高了鲁棒性。
# 5.  **工具解耦:** 工具实现已移出 Agent 类，放在独立的 `CircuitTools` 类中，
#     通过依赖注入（将 `MemoryManager` 传递给工具方法）访问状态。
# 6.  **基于 Token 的短期记忆:** MemoryManager 使用 `tiktoken` (需安装)
#     精确计算 Token 数，实现更可靠的上下文窗口管理。
# 7.  **安全的 API Key 处理:** 强制从环境变量读取 API Key，移除了不安全的
#     `input()` 方式。
# 8.  **配置集中化:** 模型名称、API Key、Token 限制等放入 `AgentConfig` 类。
# 9.  **自定义异常:** 定义了专门的异常类，使错误处理更清晰。
# 10. **详尽注释:** 我添加了大量注释，解释每一部分的设计思路和实现细节。
#
# 我相信这个版本能更好地满足您的要求，并为未来的扩展打下坚实的基础。
# 请您审阅！如有任何疑问或新的指示，我随时待命！
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
from typing import List, Dict, Any, Optional, Tuple, Set, Union, Type

# --- 依赖库导入 (请确保已安装: pip install zhipuai tiktoken pydantic) ---
try:
    from zhipuai import ZhipuAI
except ImportError:
    print("错误：缺少 'zhipuai' 库。请运行 'pip install zhipuai'", file=sys.stderr)
    sys.exit(1)
try:
    import tiktoken
except ImportError:
    print("错误：缺少 'tiktoken' 库。请运行 'pip install tiktoken'", file=sys.stderr)
    sys.exit(1)
try:
    from pydantic import BaseModel, Field, ValidationError
except ImportError:
    print("错误：缺少 'pydantic' 库。请运行 'pip install pydantic'", file=sys.stderr)
    sys.exit(1)

# --- 全局异步事件循环 ---
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# --- 日志系统配置 ---
logging.basicConfig(
    level=logging.INFO, # 生产环境建议 INFO 或 WARNING，开发时可 DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s [%(module)s.%(funcName)s:%(lineno)d] - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)
# 降低依赖库日志级别
logging.getLogger("zhipuai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("tiktoken").setLevel(logging.WARNING)

# --- 异步友好的打印函数 ---
async def async_print(message: str, end: str = '\n', flush: bool = True):
    """在异步环境中安全地打印到标准输出。"""
    sys.stdout.write(message + end)
    if flush:
        sys.stdout.flush()

# --- 配置模块 (Config) ---
class AgentConfig:
    """集中管理 Agent 的配置信息"""
    # 强依赖：API Key 必须通过环境变量设置
    API_KEY: str = os.environ.get("ZHIPUAI_API_KEY")
    if not API_KEY:
        logger.critical("致命错误：环境变量 ZHIPUAI_API_KEY 未设置！程序无法启动。")
        # 在实际应用中，这里应该直接 sys.exit(1)
        # 为了让代码能被静态分析，这里暂时用 raise 代替
        raise ValueError("环境变量 ZHIPUAI_API_KEY 未设置！")

    # LLM 相关配置
    MODEL_NAME: str = "glm-4-flash" # 使用的模型
    DEFAULT_TEMPERATURE: float = 0.1 # 默认温度参数
    DEFAULT_MAX_TOKENS: int = 2000 # LLM 单次返回的最大 Token 数 (注意是completion, 不是总上下文)
    PLANNING_TIMEOUT_SECONDS: int = 120 # 规划阶段 LLM 调用的超时时间
    RESPONSE_TIMEOUT_SECONDS: int = 180 # 响应生成阶段 LLM 调用的超时时间

    # 内存相关配置
    # 注意：这个值需要根据 MODEL_NAME 的实际上下文窗口大小和预留的 Prompt/回复空间来调整
    MAX_SHORT_TERM_TOKENS: int = 3500 # 短期记忆允许的最大 Token 总量 (估算值)
    MAX_LONG_TERM_ITEMS: int = 50 # 长期记忆最大条目数 (简单 FIFO)
    # 用于 tiktoken 加载模型，需要确认 ZhipuAI 使用的编码方式
    # 对于 GLM-4 系列，通常兼容 cl100k_base (与 gpt-4 相同)
    TOKENIZER_MODEL: str = "cl100k_base"

    # Agent 行为配置
    MAX_PLANNING_RETRIES: int = 1 # 规划 LLM 调用失败或解析失败时的最大重试次数
    MAX_TOOL_STEPS: int = 10 # 单个用户请求允许执行的最大工具步骤数，防止无限循环

    # RAG 相关（占位）
    EMBEDDING_MODEL_NAME: str = "embedding-2" # 假设 Zhipu 提供此模型
    TOP_K_LONG_TERM_MEMORY: int = 3 # RAG 检索时返回的最相关记忆片段数量

    # 日志级别（可通过环境变量覆盖）
    LOG_LEVEL: str = os.environ.get("AGENT_LOG_LEVEL", "INFO").upper()

# 更新日志级别（基于配置）
log_level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}
effective_log_level = log_level_map.get(AgentConfig.LOG_LEVEL, logging.INFO)
logging.getLogger().setLevel(effective_log_level)
logger.info(f"日志级别设置为: {AgentConfig.LOG_LEVEL}")

# --- 自定义异常模块 (Exceptions) ---
class AgentError(Exception):
    """Agent 相关的基类异常"""
    pass

class ConfigurationError(AgentError):
    """配置错误异常"""
    pass

class MemoryError(AgentError):
    """内存操作错误异常"""
    pass

class LLMError(AgentError):
    """LLM 交互错误异常"""
    pass

class PlanningError(AgentError):
    """规划或计划解析错误异常"""
    pass

class ToolError(AgentError):
    """工具执行错误异常"""
    pass

class ToolNotFoundError(ToolError):
    """尝试调用不存在的工具"""
    pass

class ToolInputError(ToolError):
    """工具输入参数错误"""
    pass

# --- 工具注册与管理模块 (Tools Infrastructure) ---
_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {} # 全局工具注册表

def register_tool(description: str, parameters: Dict[str, Any]):
    """
    工具注册装饰器。将工具的 Schema 附加到函数上。
    现在这个装饰器本身不依赖于 Agent 类。
    """
    def decorator(func):
        if not asyncio.iscoroutinefunction(func) and not inspect.isfunction(func):
             raise TypeError(f"工具 '{func.__name__}' 必须是普通函数或 async def 函数。")

        # 检查函数签名是否接受依赖注入（例如 memory_manager）
        sig = inspect.signature(func)
        # 我们约定工具函数第一个参数是 arguments (dict)，第二个是 memory_manager (MemoryManager)
        # 这样 ToolExecutor 才知道如何传递依赖
        expected_params = ['arguments', 'memory_manager']
        actual_params = list(sig.parameters.keys())
        if len(actual_params) < len(expected_params) or actual_params[:len(expected_params)] != expected_params:
             logger.warning(f"工具 '{func.__name__}' 的签名不符合预期 ({expected_params})，可能无法正确接收依赖。实际签名: {actual_params}")
             # 可以选择更严格地抛出错误:
             # raise TypeError(f"工具 '{func.__name__}' 签名必须至少包含参数: {expected_params}")

        # 存储 Schema 和函数本身到全局注册表
        tool_name = func.__name__
        if tool_name in _TOOL_REGISTRY:
            logger.warning(f"重复注册工具: '{tool_name}'。后注册的将覆盖之前的。")

        _TOOL_REGISTRY[tool_name] = {
            "schema": {"description": description, "parameters": parameters},
            "function": func, # 直接存储函数对象
            "is_async": asyncio.iscoroutinefunction(func) # 标记是否是异步函数
        }
        logger.debug(f"工具 '{tool_name}' 已注册。")

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 包装器本身不改变行为
            return func(*args, **kwargs)
        return wrapper
    return decorator

def get_tool_registry() -> Dict[str, Dict[str, Any]]:
    """获取全局工具注册表"""
    return _TOOL_REGISTRY

def get_tool_schemas_for_prompt() -> str:
    """根据全局注册表动态生成工具描述字符串，用于注入 LLM Prompt。"""
    registry = get_tool_registry()
    if not registry:
        return "  (当前无可用工具)"

    tool_schemas = []
    for name, tool_info in registry.items():
        schema = tool_info.get("schema", {})
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

# --- 电路元件数据类 (保持不变) ---
class CircuitComponent:
    """标准化电路元件的数据结构"""
    __slots__ = ['id', 'type', 'value']
    def __init__(self, component_id: str, component_type: str, value: Optional[str] = None):
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError("元件 ID 必须是有效的非空字符串")
        if not isinstance(component_type, str) or not component_type.strip():
            raise ValueError("元件类型必须是有效的非空字符串")
        self.id: str = component_id.strip().upper()
        self.type: str = component_type.strip()
        self.value: Optional[str] = str(value).strip() if value is not None and str(value).strip() else None
        # logger.debug(f"成功创建元件对象: {self}") # 在 V8 中降低日志级别
    def __str__(self) -> str:
        value_str = f" (值: {self.value})" if self.value else ""
        return f"元件: {self.type} (ID: {self.id}){value_str}"
    def __repr__(self) -> str:
        return f"CircuitComponent(id='{self.id}', type='{self.type}', value={repr(self.value)})"

# --- 内存管理模块 (Memory) ---
class MemoryManager:
    """
    管理 Agent 的短期对话历史、长期知识（基础 RAG 占位）和电路状态。
    短期记忆使用 Token 计数进行管理。
    """
    def __init__(self, config: Type[AgentConfig]):
        logger.info("[MemoryManager] 初始化记忆模块...")
        self.config = config
        try:
            # 加载 Tokenizer
            self.tokenizer = tiktoken.get_encoding(config.TOKENIZER_MODEL)
            logger.info(f"[MemoryManager] Tokenizer ({config.TOKENIZER_MODEL}) 加载成功。")
        except Exception as e:
            logger.error(f"[MemoryManager] 加载 Tokenizer ({config.TOKENIZER_MODEL}) 失败: {e}", exc_info=True)
            raise ConfigurationError(f"无法加载 Tokenizer: {config.TOKENIZER_MODEL}") from e

        self.max_short_term_tokens = config.MAX_SHORT_TERM_TOKENS
        self.max_long_term_items = config.MAX_LONG_TERM_ITEMS

        # 短期记忆：存储消息字典，并维护 Token 总数
        self.short_term: List[Dict[str, Any]] = []
        self.short_term_token_count: int = 0

        # 长期记忆：基础 RAG 占位 (未来可替换为向量数据库)
        # 存储 (原始文本, embedding向量) 对
        self.long_term: List[Tuple[str, Optional[List[float]]]] = []
        # 简单的 Embedding 模型接口占位 (实际应使用 ZhipuAI 或其他 Embedding API)
        self._embedding_client = None # 未来初始化 Embedding 客户端
        logger.info("[MemoryManager] 长期记忆当前为基础占位模式 (无 Embedding/检索)。")

        # 电路知识库：结构化存储
        self.circuit_knowledge: Dict[str, Any] = {
            "components": {}, # {component_id: CircuitComponent}
            "connections": set(), # set of tuples (id1, id2) sorted
            "_component_counters": {
                'R': 0, 'L': 0, 'B': 0, 'S': 0, 'C': 0, 'V': 0, 'G': 0, 'U': 0, 'O': 0,
                'I': 0, 'A': 0, 'D': 0, 'P': 0, 'F': 0, 'H': 0
            }
        }
        self._system_prompt_token_count = 0 # 存储 System Prompt 的 Token 数，修剪时不移除
        logger.info(f"[MemoryManager] 记忆模块初始化完成。短期 Token 上限: {self.max_short_term_tokens}, 长期上限: {self.max_long_term_items} 条")

    def _count_message_tokens(self, message: Dict[str, Any]) -> int:
        """估算单个消息字典的 Token 数。需要根据模型优化。"""
        # 这是一个通用估算，实际 Token 数可能因模型和特殊字符处理而异
        # 参考 OpenAI cookbook: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
        tokens_per_message = 3 # 每个消息增加 3 个 token (role, \n\n ...)
        tokens_per_name = 1 # 如果有 name 字段
        count = tokens_per_message
        for key, value in message.items():
            try:
                # 确保 value 是字符串
                value_str = str(value) if value is not None else ""
                count += len(self.tokenizer.encode(value_str))
                if key == "name":
                    count += tokens_per_name
            except Exception as e:
                logger.warning(f"计算消息 Token 时出错 (key: {key}): {e}. Message: {message}", exc_info=False)
                # 出错时给一个保守的估计值
                count += len(str(value)) // 2 # 粗略估计
        return count

    def add_system_prompt(self, system_prompt: str):
        """添加系统提示并记录其 Token 数"""
        if self.short_term and self.short_term[0].get("role") == "system":
             logger.warning("[MemoryManager] 已存在系统提示，将被替换。")
             removed_msg = self.short_term.pop(0)
             self.short_term_token_count -= self._system_prompt_token_count

        message = {"role": "system", "content": system_prompt}
        self._system_prompt_token_count = self._count_message_tokens(message)
        self.short_term.insert(0, message)
        self.short_term_token_count += self._system_prompt_token_count
        logger.debug(f"[MemoryManager] 添加 System Prompt ({self._system_prompt_token_count} tokens)。")
        # 添加系统提示后也可能需要修剪
        self._prune_short_term_memory()

    def add_to_short_term(self, message: Dict[str, Any]):
        """
        添加消息到短期记忆，计算 Token 数，并执行基于 Token 的修剪。
        系统提示（如果有，在索引 0）永远不会被修剪。
        """
        role = message.get('role', 'N/A')
        logger.debug(f"[MemoryManager] 准备添加消息 (Role: {role}) 到短期记忆。当前 Token: {self.short_term_token_count}")
        try:
            message_tokens = self._count_message_tokens(message)
            logger.debug(f"[MemoryManager] 新消息 Token 数: {message_tokens}")

            # 检查添加后是否超限（仅估算，实际可能需要修剪更多）
            if self.short_term_token_count + message_tokens > self.max_short_term_tokens:
                logger.debug(f"[MemoryManager] 预估超限，执行预修剪...")
                self._prune_short_term_memory(required_space=message_tokens) # 尝试腾出空间

            # 再次检查（可能预修剪后仍不足）
            if self.short_term_token_count + message_tokens > self.max_short_term_tokens:
                 logger.warning(f"[MemoryManager] 即使尝试修剪后，添加新消息 ({message_tokens} tokens) 仍会超出上限 ({self.max_short_term_tokens})。当前 Token: {self.short_term_token_count}。可能会丢失重要上下文！")
                 # 策略选择：可以强制添加并再次强制修剪，或者拒绝添加并报错
                 # 这里选择强制添加并再次修剪
                 pass # 继续添加，之后会再次修剪

            self.short_term.append(message)
            self.short_term_token_count += message_tokens
            logger.debug(f"[MemoryManager] 消息已添加。当前 Token: {self.short_term_token_count}/{self.max_short_term_tokens}, 消息数: {len(self.short_term)}")

            # 执行最终修剪
            self._prune_short_term_memory()

        except Exception as e:
            logger.error(f"[MemoryManager] 添加短期记忆失败: {e}", exc_info=True)
            # 可以考虑抛出 MemoryError
            raise MemoryError(f"添加短期记忆失败: {e}") from e

    def _prune_short_term_memory(self, required_space: int = 0):
        """
        内部方法：基于 Token 数修剪短期记忆，保留系统提示。
        可以传入 required_space 来指示至少需要腾出多少 Token 空间。
        """
        if self.short_term_token_count <= self.max_short_term_tokens and required_space <= 0:
            return # 不需要修剪

        tokens_to_remove = max(0, self.short_term_token_count - self.max_short_term_tokens) + required_space
        if tokens_to_remove <= 0:
             return

        logger.debug(f"[MemoryManager] 需要修剪 {tokens_to_remove} tokens。当前: {self.short_term_token_count}/{self.max_short_term_tokens}")

        removed_tokens_total = 0
        indices_to_remove = []
        has_system_prompt = self.short_term and self.short_term[0].get("role") == "system"
        start_index = 1 if has_system_prompt else 0 # 从系统提示之后开始检查

        # 从最旧的非系统消息开始标记移除
        for i in range(start_index, len(self.short_term)):
            try:
                msg_tokens = self._count_message_tokens(self.short_term[i])
                indices_to_remove.append(i)
                removed_tokens_total += msg_tokens
                if removed_tokens_total >= tokens_to_remove:
                    break # 找到了足够数量的消息
            except Exception as e:
                 logger.warning(f"[MemoryManager] 计算待移除消息 {i} 的 Token 时出错: {e}。跳过此消息。")

        if not indices_to_remove:
            logger.warning("[MemoryManager] 短期记忆超限但未能找到可移除的消息（可能只有系统提示）。")
            return

        # 执行移除 (从后往前删除索引，避免影响前面的索引)
        removed_count = 0
        final_removed_tokens = 0
        new_short_term = []
        indices_to_remove_set = set(indices_to_remove)

        for i, item in enumerate(self.short_term):
             if i not in indices_to_remove_set:
                 new_short_term.append(item)
             else:
                 removed_count += 1
                 # 累加实际移除的token (如果之前计算失败，这里会是0)
                 final_removed_tokens += self._count_message_tokens(item) if i in indices_to_remove else 0

        self.short_term = new_short_term
        self.short_term_token_count -= final_removed_tokens # 更新 Token 总数

        if removed_count > 0:
            logger.info(f"[MemoryManager] 短期记忆修剪完成，移除了 {removed_count} 条最旧的非系统消息，释放约 {final_removed_tokens} tokens。")
            logger.debug(f"[MemoryManager] 修剪后 Token: {self.short_term_token_count}/{self.max_short_term_tokens}, 消息数: {len(self.short_term)}")
        # else: 没有移除任何消息

    def get_short_term_history(self) -> List[Dict[str, Any]]:
        """获取当前的短期记忆消息列表"""
        return list(self.short_term) # 返回副本

    def add_to_long_term(self, knowledge_snippet: str):
        """
        添加到长期记忆（基础 RAG 占位）。
        未来应包含 Embedding 和存储到向量数据库的逻辑。
        """
        logger.debug(f"[MemoryManager] 添加知识到长期记忆 (占位): '{knowledge_snippet[:100]}...'")
        # --- RAG Placeholder ---
        # 1. (未来) 调用 Embedding API/模型获取向量
        embedding = None # embedding = self._get_embedding(knowledge_snippet)
        # 2. 存储文本和向量
        self.long_term.append((knowledge_snippet, embedding))
        # 3. FIFO 修剪
        if len(self.long_term) > self.max_long_term_items:
            removed_item, _ = self.long_term.pop(0)
            logger.info(f"[MemoryManager] 长期记忆超限 ({self.max_long_term_items}), 移除最旧知识: '{removed_item[:50]}...'")
        # --- End RAG Placeholder ---

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """(未来实现) 调用 Embedding 模型获取文本向量"""
        if self._embedding_client:
             try:
                 # response = self._embedding_client.embed(text=text, model=self.config.EMBEDDING_MODEL_NAME)
                 # return response.embedding
                 logger.warning("_get_embedding 未实现")
                 return None
             except Exception as e:
                 logger.error(f"获取 Embedding 失败: {e}", exc_info=True)
                 return None
        return None

    def retrieve_relevant_long_term(self, query: str, top_k: Optional[int] = None) -> List[str]:
        """
        从长期记忆中检索相关片段（基础 RAG 占位）。
        未来应实现基于向量相似度的检索。
        """
        if top_k is None:
            top_k = self.config.TOP_K_LONG_TERM_MEMORY

        if not self.long_term:
            return []

        logger.debug(f"[MemoryManager] 正在检索与 '{query[:50]}...' 相关的长期记忆 (占位)...")
        # --- RAG Placeholder ---
        # 1. (未来) 获取查询向量: query_embedding = self._get_embedding(query)
        # 2. (未来) 在向量存储中执行相似度搜索
        # 3. 当前：返回最近添加的 top_k 条作为占位符
        num_items = len(self.long_term)
        actual_k = min(top_k, num_items)
        if actual_k <= 0:
            return []

        # 返回最后 K 个文本片段
        relevant_items = [item[0] for item in self.long_term[-actual_k:]]
        logger.debug(f"[MemoryManager] (占位) 检索到最近 {len(relevant_items)} 条长期记忆。")
        return relevant_items
        # --- End RAG Placeholder ---

    def get_memory_context_for_prompt(self, current_query: Optional[str] = None) -> str:
        """
        格式化非对话历史的记忆上下文（电路状态 + 相关长期记忆）用于注入 LLM Prompt。
        """
        logger.debug("[MemoryManager] 正在格式化记忆上下文用于 Prompt...")
        circuit_desc = self.get_circuit_state_description()

        # --- 长期记忆处理 (基础 RAG 占位) ---
        long_term_str = "【相关知识库 (基础检索)】\n"
        if current_query:
            relevant_knowledge = self.retrieve_relevant_long_term(current_query)
            if relevant_knowledge:
                long_term_str += "\n".join(f"- {item}" for item in relevant_knowledge)
            else:
                long_term_str += "(未找到相关知识)"
        else:
            long_term_str += "(无查询，未检索)"
        long_term_str += "\n(注: 当前为基础记忆检索，未来版本将实现基于语义相似度的检索)"

        # 组合电路描述和长期记忆上下文
        context = f"{circuit_desc}\n\n{long_term_str}".strip()
        logger.debug("[MemoryManager] 记忆上下文格式化完成。")
        return context

    # --- 电路状态管理方法 (基本保持不变，但增加日志和错误处理) ---
    def generate_component_id(self, component_type: str) -> str:
        """为给定类型的元件生成唯一的 ID。"""
        logger.debug(f"[MemoryManager] 正在为类型 '{component_type}' 生成唯一 ID...")
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
        # 确保计数器存在
        for code in type_map.values():
            self.circuit_knowledge["_component_counters"].setdefault(code, 0)

        cleaned_type = component_type.strip().lower()
        type_code = "O"; best_match_len = 0
        for keyword, code in type_map.items():
            if keyword in cleaned_type and len(keyword) > best_match_len:
                type_code = code; best_match_len = len(keyword)
        if type_code == "O" and cleaned_type not in ["component", "元件"]:
             logger.warning(f"[MemoryManager] 未找到类型 '{component_type}' 的特定前缀，使用通用 'O'。")

        MAX_ID_ATTEMPTS = 100
        for attempt in range(MAX_ID_ATTEMPTS):
            self.circuit_knowledge["_component_counters"][type_code] += 1
            gen_id = f"{type_code}{self.circuit_knowledge['_component_counters'][type_code]}"
            if gen_id not in self.circuit_knowledge["components"]:
                logger.debug(f"[MemoryManager] 生成唯一 ID: '{gen_id}' (尝试 {attempt + 1})")
                return gen_id
            logger.warning(f"[MemoryManager] ID '{gen_id}' 已存在，尝试下一个。")

        raise MemoryError(f"为类型 '{component_type}' (代码 '{type_code}') 生成唯一 ID 失败 ({MAX_ID_ATTEMPTS} 次尝试)。")

    def add_component(self, component: CircuitComponent):
        """向电路知识库添加一个 CircuitComponent 对象"""
        if component.id in self.circuit_knowledge["components"]:
             raise MemoryError(f"元件 ID '{component.id}' 已存在，无法重复添加。")
        self.circuit_knowledge["components"][component.id] = component
        logger.info(f"[MemoryManager] 元件 {component} 已添加到知识库。")

    def add_connection(self, comp1_id: str, comp2_id: str) -> bool:
        """添加元件连接，返回是否是新添加的连接"""
        id1 = comp1_id.strip().upper()
        id2 = comp2_id.strip().upper()
        if id1 == id2: raise ValueError("不能将元件连接到自身。")
        if id1 not in self.circuit_knowledge["components"]: raise ValueError(f"元件 '{id1}' 不存在。")
        if id2 not in self.circuit_knowledge["components"]: raise ValueError(f"元件 '{id2}' 不存在。")

        connection = tuple(sorted((id1, id2)))
        if connection in self.circuit_knowledge["connections"]:
            logger.debug(f"[MemoryManager] 连接 {id1}<->{id2} 已存在。")
            return False # 不是新连接
        else:
            self.circuit_knowledge["connections"].add(connection)
            logger.info(f"[MemoryManager] 连接 {id1}<->{id2} 已添加。")
            return True # 是新连接

    def get_circuit_state_description(self) -> str:
        """根据电路知识库生成当前电路状态的文本描述。"""
        # logger.debug("[MemoryManager] 正在生成电路状态描述...") # V8 中降低日志频率
        components = self.circuit_knowledge["components"]
        connections = self.circuit_knowledge["connections"]
        if not components and not connections: return "【当前电路状态】: 电路为空。"
        desc_lines = ["【当前电路状态】:"]
        desc_lines.append(f"  - 元件 ({len(components)}):")
        if components:
            sorted_ids = sorted(components.keys())
            for cid in sorted_ids: desc_lines.append(f"    - {str(components[cid])}")
        else: desc_lines.append("    (无)")
        desc_lines.append(f"  - 连接 ({len(connections)}):")
        if connections:
            sorted_connections = sorted(list(connections))
            for c1, c2 in sorted_connections: desc_lines.append(f"    - {c1} <--> {c2}")
        else: desc_lines.append("    (无)")
        return "\n".join(desc_lines)

    def clear_circuit(self):
        """清空当前电路的所有元件和连接，并重置 ID 计数器。"""
        logger.info("[MemoryManager] 正在清空电路状态...")
        comp_count = len(self.circuit_knowledge["components"])
        conn_count = len(self.circuit_knowledge["connections"])
        self.circuit_knowledge["components"] = {}
        self.circuit_knowledge["connections"] = set()
        self.circuit_knowledge["_component_counters"] = {k: 0 for k in self.circuit_knowledge["_component_counters"]}
        logger.info(f"[MemoryManager] 电路状态已清空 (移除 {comp_count} 元件, {conn_count} 连接, 重置计数器)。")

# --- LLM 接口模块 (LLM Interface) ---
class LLMInterface:
    """封装与大语言模型 (LLM) 的异步交互。"""
    def __init__(self, config: Type[AgentConfig]):
        logger.info(f"[LLMInterface] 初始化 LLM 接口，目标模型: {config.MODEL_NAME}")
        self.config = config
        try:
            self.client = ZhipuAI(api_key=config.API_KEY)
            # 未来可以添加检查 API Key 有效性的逻辑
            logger.info("[LLMInterface] 智谱 AI 客户端初始化成功。")
        except Exception as e:
            logger.critical(f"[LLMInterface] 初始化智谱 AI 客户端失败: {e}", exc_info=True)
            raise ConfigurationError(f"初始化智谱 AI 客户端失败: {e}") from e

    async def call_llm(self, messages: List[Dict[str, Any]], timeout: Optional[int] = None) -> Any:
        """
        异步调用 LLM API。使用 asyncio.to_thread 包装同步 SDK 调用。
        增加了超时控制。
        """
        call_args = {
            "model": self.config.MODEL_NAME,
            "messages": messages,
            "temperature": self.config.DEFAULT_TEMPERATURE,
            "max_tokens": self.config.DEFAULT_MAX_TOKENS,
        }
        effective_timeout = timeout if timeout is not None else self.config.PLANNING_TIMEOUT_SECONDS # 默认用规划超时
        logger.info(f"[LLMInterface] 准备异步调用 LLM ({self.config.MODEL_NAME})...")
        logger.debug(f"[LLMInterface] 发送消息数: {len(messages)}. 超时设置: {effective_timeout}s")
        # logger.debug(f"[LLMInterface] 消息列表: {messages}") # 调试时取消注释

        try:
            start_time = time.monotonic()
            # 使用 asyncio.wait_for 实现超时控制
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.chat.completions.create, # 同步方法
                    **call_args
                ),
                timeout=effective_timeout
            )
            duration = time.monotonic() - start_time
            logger.info(f"[LLMInterface] LLM 异步调用成功。耗时: {duration:.3f} 秒。")

            if response and response.usage:
                logger.info(f"[LLMInterface] Token 统计: Prompt={response.usage.prompt_tokens}, Completion={response.usage.completion_tokens}, Total={response.usage.total_tokens}")
            if not response or not response.choices:
                 logger.warning("[LLMInterface] LLM 响应无效或缺少 'choices' 字段。")
                 # 即使响应看似无效，也返回它，让调用者处理
                 # raise LLMError("LLM 响应无效或缺少 'choices' 字段。")

            return response

        except asyncio.TimeoutError:
            logger.error(f"[LLMInterface] LLM 调用超时 ({effective_timeout} 秒)！")
            raise LLMError(f"LLM 调用超时 ({effective_timeout} 秒)。") from None
        except Exception as e:
            # 捕获 ZhipuAI SDK 可能抛出的其他异常或 to_thread 的异常
            logger.error(f"[LLMInterface] LLM API 异步调用失败: {e}", exc_info=True)
            # 将原始异常包装后重新抛出
            raise LLMError(f"LLM API 调用失败: {e}") from e

# --- 输出解析模块 (Output Parser) ---
# Pydantic 模型用于定义期望的 LLM 输出结构 (简化后)
class LLMToolCallPlan(BaseModel):
    """定义 LLM 返回的工具调用计划结构"""
    action: str = Field(..., pattern="^tool_call$") # action 必须是 "tool_call"
    tool_name: str
    params: Dict[str, Any] = Field(default_factory=dict)

class LLMDirectReplyPlan(BaseModel):
    """定义 LLM 返回的直接回复计划结构"""
    action: str = Field(..., pattern="^direct_reply$") # action 必须是 "direct_reply"
    content: str

class OutputParser:
    """
    负责解析 LLM 返回的响应。
    V8 版本专注于解析简化的单步计划 JSON 或最终的文本回复。
    增加了对 JSON 前后无关内容的清理。
    """
    def __init__(self):
        logger.info("[OutputParser] 初始化输出解析器 (V8 - 简易 JSON 解析)。")
        # 预编译正则表达式以提高效率
        self.json_finder_regex = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```|(\{.*?\})", re.DOTALL)
        self.think_tag_regex = re.compile(r"<think>(.*?)</think>", re.IGNORECASE | re.DOTALL)

    def _extract_json_string(self, text: str) -> Optional[str]:
        """尝试从文本中提取第一个看起来像 JSON 对象的部分。"""
        if not text: return None
        text = text.strip()

        # 优先尝试匹配 Markdown 代码块中的 JSON
        match = self.json_finder_regex.search(text)
        if match:
            # group(1) 对应 ```json{...}```, group(2) 对应 {...}
            # 优先取 group(1) 或 group(2) 中非 None 的那个
            json_str = match.group(1) or match.group(2)
            if json_str:
                logger.debug(f"通过 Regex 找到 JSON 字符串: {json_str[:100]}...")
                return json_str.strip()

        # 如果正则没匹配到，尝试暴力查找第一个 '{' 和最后一个 '}'
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            potential_json = text[first_brace : last_brace + 1].strip()
            # 基本验证：确保大括号数量大致平衡（不完美但能过滤一些明显错误）
            if potential_json.count('{') == potential_json.count('}'):
                logger.debug(f"通过暴力查找找到潜在 JSON: {potential_json[:100]}...")
                return potential_json
            else:
                logger.warning("暴力查找的 JSON 大括号不匹配，可能无效。")
        
        logger.debug("未能从文本中提取出有效的 JSON 字符串。")
        return None

    def parse_planning_response(self, response_content: str) -> Tuple[str, Union[LLMToolCallPlan, LLMDirectReplyPlan, None], str]:
        """
        解析第一次 LLM 调用（规划阶段）的响应。
        期望格式：<think>...</think> 后跟一个简单的 JSON 对象。
        返回：思考过程、解析后的 Pydantic 模型 (成功) 或 None (失败)、错误信息。
        """
        logger.debug("[OutputParser] 开始解析规划响应 (V8 简易 JSON 模式)...")
        thinking_process = "未能提取思考过程。"
        parsed_plan = None
        error_message = ""

        if not response_content or not response_content.strip():
            error_message = "LLM 响应内容为空或仅包含空白。"
            logger.error(f"[OutputParser] 解析失败: {error_message}")
            return thinking_process, None, error_message

        # 1. 提取 <think> 块
        think_match = self.think_tag_regex.search(response_content)
        content_after_think = response_content # 默认从头开始找 JSON
        if think_match:
            thinking_process = think_match.group(1).strip()
            content_after_think = response_content[think_match.end():].strip()
            logger.debug("[OutputParser] 成功提取 <think> 内容。")
            # 检查 think 前面是否有非预期内容
            content_before_think = response_content[:think_match.start()].strip()
            if content_before_think:
                 logger.warning(f"[OutputParser] 在 <think> 标签前检测到内容: '{content_before_think[:50]}...'，已忽略。")
        else:
            thinking_process = "警告：未找到 <think> 标签。"
            logger.warning(f"[OutputParser] {thinking_process} 将尝试解析整个响应查找 JSON。")

        # 2. 从 <think> 之后的内容中提取 JSON 字符串
        json_string = self._extract_json_string(content_after_think)

        if not json_string:
            error_message = "未能从 LLM 响应中提取出有效的 JSON 字符串。"
            logger.error(f"[OutputParser] 解析失败: {error_message} Raw content after think: {content_after_think[:200]}...")
            return thinking_process, None, error_message

        # 3. 解析并验证 JSON 结构
        try:
            raw_json_data = json.loads(json_string)
            if not isinstance(raw_json_data, dict):
                raise ValueError("解析出的 JSON 不是一个对象 (字典)。")

            action = raw_json_data.get("action")
            if action == "tool_call":
                # 尝试按 ToolCall 结构验证
                parsed_plan = LLMToolCallPlan(**raw_json_data)
                logger.info(f"[OutputParser] 成功解析并验证为工具调用计划: {parsed_plan.tool_name}")
            elif action == "direct_reply":
                # 尝试按 DirectReply 结构验证
                parsed_plan = LLMDirectReplyPlan(**raw_json_data)
                logger.info("[OutputParser] 成功解析并验证为直接回复计划。")
            else:
                # action 字段无效或缺失
                raise ValueError(f"JSON 中的 'action' 字段无效或缺失: '{action}'. 必须是 'tool_call' 或 'direct_reply'。")

        except json.JSONDecodeError as json_err:
            error_message = f"解析 JSON 字符串失败: {json_err}. Raw JSON string: '{json_string[:200]}...'"
            logger.error(f"[OutputParser] JSON 解析失败: {error_message}")
            parsed_plan = None
        except ValidationError as pydantic_err:
            error_message = f"JSON 结构验证失败: {pydantic_err}. Raw JSON data: {raw_json_data if 'raw_json_data' in locals() else json_string[:200]}"
            logger.error(f"[OutputParser] Pydantic 验证失败: {error_message}")
            parsed_plan = None
        except ValueError as val_err:
            error_message = f"JSON 内容验证失败: {val_err}."
            logger.error(f"[OutputParser] 值验证失败: {error_message}")
            parsed_plan = None
        except Exception as e:
            error_message = f"解析规划响应时发生未知错误: {e}"
            logger.error(f"[OutputParser] 解析时未知错误: {error_message}", exc_info=True)
            parsed_plan = None

        if parsed_plan is None and not error_message:
             # 兜底错误信息
             error_message = "未能成功解析有效的计划。"

        return thinking_process, parsed_plan, error_message

    def parse_final_response(self, response_content: str) -> Tuple[str, str]:
        """解析最终 LLM 调用（总结阶段）的响应，提取思考和正式回复。"""
        logger.debug("[OutputParser] 开始解析最终文本响应...")
        if not response_content or not response_content.strip():
             logger.warning("[OutputParser] 最终响应内容为空。")
             return "思考过程为空。", "回复内容为空。"

        thinking_process = "未能提取思考过程。"
        formal_reply = response_content.strip() # 默认

        think_match = self.think_tag_regex.search(response_content)
        if think_match:
            thinking_process = think_match.group(1).strip()
            formal_reply = response_content[think_match.end():].strip()
            content_before_think = response_content[:think_match.start()].strip()
            if content_before_think:
                logger.warning(f"[OutputParser] 在最终响应的 <think> 前检测到内容: '{content_before_think[:50]}...'，已忽略。")
        else:
            logger.warning("[OutputParser] 未在最终响应中找到 <think> 标签。将整个内容视为回复。")
            thinking_process = "未能提取思考过程 - LLM 可能未按预期包含 <think> 标签。"

        # 确保即使提取失败，也返回非空的默认字符串
        thinking_process = thinking_process if thinking_process else "提取的思考过程为空白。"
        formal_reply = formal_reply if formal_reply else "LLM 未生成最终报告内容。"

        logger.debug(f"[OutputParser] 最终响应解析完毕。")
        return thinking_process, formal_reply

# --- 电路工具实现模块 (Tools Implementation) ---
class CircuitTools:
    """封装电路相关的工具方法。"""

    @register_tool(
        description="添加一个新的电路元件 (如电阻, 电容, 电池, LED, 开关, 芯片, 地线等)。如果用户未指定 ID，会自动生成。元件值是可选的。",
        parameters={
            "type": "object",
            "properties": {
                "component_type": {"type": "string", "description": "元件的类型 (例如: '电阻', 'LED', '9V 电池')."},
                "component_id": {"type": "string", "description": "可选的用户指定 ID。如果省略会自动生成。"},
                "value": {"type": "string", "description": "可选的元件值 (例如: '1k', '10uF', '9V')."}
            },
            "required": ["component_type"]
        }
    )
    # 注意：工具方法现在是普通函数或 async def 函数，并且接收 memory_manager 作为依赖
    def add_component_tool(self, arguments: Dict[str, Any], memory_manager: MemoryManager) -> Dict[str, Any]:
        """Action 实现：添加元件。同步执行。"""
        logger.info("[Tool:AddComponent] 执行添加元件操作。")
        logger.debug(f"[Tool:AddComponent] 收到参数: {arguments}")
        try:
            component_type = arguments.get("component_type")
            if not component_type or not isinstance(component_type, str) or not component_type.strip():
                raise ToolInputError("元件类型是必需的，并且必须是有效的字符串。")

            component_id_req = arguments.get("component_id")
            value = arguments.get("value")
            target_id = None; id_was_generated = False

            if component_id_req and isinstance(component_id_req, str) and component_id_req.strip():
                user_provided_id = component_id_req.strip().upper()
                if re.match(r'^[a-zA-Z0-9_][a-zA-Z0-9_-]*$', user_provided_id):
                    if user_provided_id in memory_manager.circuit_knowledge["components"]:
                         raise ToolInputError(f"元件 ID '{user_provided_id}' 已被占用。")
                    target_id = user_provided_id
                    logger.debug(f"[Tool:AddComponent] 使用用户提供的有效 ID: '{target_id}'.")
                else:
                    logger.warning(f"[Tool:AddComponent] 用户提供的 ID '{component_id_req}' 格式无效，将自动生成。")
            else:
                 logger.debug("[Tool:AddComponent] 用户未提供有效 ID，将自动生成。")

            if target_id is None:
                target_id = memory_manager.generate_component_id(component_type)
                id_was_generated = True
                logger.debug(f"[Tool:AddComponent] 自动生成 ID: '{target_id}'.")

            processed_value = str(value).strip() if value is not None and str(value).strip() else None
            new_component = CircuitComponent(target_id, component_type, processed_value)

            # 通过 MemoryManager 添加元件
            memory_manager.add_component(new_component)
            # 添加到长期记忆
            memory_manager.add_to_long_term(f"添加了元件: {str(new_component)}")

            success_message = f"操作成功: 已添加元件 {str(new_component)}。"
            if id_was_generated: success_message += f" (系统自动分配 ID '{new_component.id}')"

            return {"status": "success", "message": success_message, "data": {"id": new_component.id, "type": new_component.type, "value": new_component.value}}

        except (ToolInputError, ValueError, MemoryError) as e:
            logger.error(f"[Tool:AddComponent] 操作失败: {e}", exc_info=False) # 只记录错误信息，避免过多堆栈
            return {"status": "failure", "message": f"错误: {e}", "error": {"type": type(e).__name__, "details": str(e)}}
        except Exception as e:
            logger.error(f"[Tool:AddComponent] 发生未知内部错误: {e}", exc_info=True)
            return {"status": "failure", "message": "错误: 添加元件时发生未知内部错误。", "error": {"type": "Unexpected", "details": str(e)}}

    @register_tool(
        description="使用两个已存在元件的 ID 将它们连接起来。执行前会检查元件是否存在。",
        parameters={
            "type": "object",
            "properties": {
                "comp1_id": {"type": "string", "description": "第一个元件的 ID (通常大写)。"},
                "comp2_id": {"type": "string", "description": "第二个元件的 ID (通常大写)。"}
            },
            "required": ["comp1_id", "comp2_id"]
        }
    )
    def connect_components_tool(self, arguments: Dict[str, Any], memory_manager: MemoryManager) -> Dict[str, Any]:
        """Action 实现：连接两个元件。同步执行。"""
        logger.info("[Tool:ConnectComponents] 执行连接元件操作。")
        logger.debug(f"[Tool:ConnectComponents] 收到参数: {arguments}")
        try:
            comp1_id = arguments.get("comp1_id")
            comp2_id = arguments.get("comp2_id")
            if not comp1_id or not isinstance(comp1_id, str) or not comp1_id.strip() or \
               not comp2_id or not isinstance(comp2_id, str) or not comp2_id.strip():
                raise ToolInputError("必须提供两个有效的、非空的元件 ID。")

            # 通过 MemoryManager 添加连接
            id1 = comp1_id.strip().upper()
            id2 = comp2_id.strip().upper()
            is_new = memory_manager.add_connection(id1, id2)

            if is_new:
                message = f"操作成功: 已将元件 '{id1}' 与 '{id2}' 连接起来。"
                # 添加到长期记忆
                memory_manager.add_to_long_term(f"连接了元件: {id1} <--> {id2}")
                return {"status": "success", "message": message, "data": {"connection": sorted((id1, id2))}}
            else:
                message = f"注意: 元件 '{id1}' 和 '{id2}' 之间已经存在连接。"
                return {"status": "success", "message": message, "data": {"connection": sorted((id1, id2))}} # 连接已存在也算成功

        except (ToolInputError, ValueError, MemoryError) as e:
            logger.error(f"[Tool:ConnectComponents] 操作失败: {e}", exc_info=False)
            return {"status": "failure", "message": f"错误: {e}", "error": {"type": type(e).__name__, "details": str(e)}}
        except Exception as e:
            logger.error(f"[Tool:ConnectComponents] 发生未知内部错误: {e}", exc_info=True)
            return {"status": "failure", "message": "错误: 连接元件时发生未知内部错误。", "error": {"type": "Unexpected", "details": str(e)}}

    @register_tool(
        description="获取当前电路的详细描述，包括所有已添加的元件及其值（如果有）和所有连接。",
        parameters={"type": "object", "properties": {}}
    )
    def describe_circuit_tool(self, arguments: Dict[str, Any], memory_manager: MemoryManager) -> Dict[str, Any]:
        """Action 实现：描述当前电路。同步执行。"""
        logger.info("[Tool:DescribeCircuit] 执行描述电路操作。")
        try:
            description = memory_manager.get_circuit_state_description()
            logger.info("[Tool:DescribeCircuit] 成功生成电路描述。")
            # 注意：描述本身通常不直接给用户看，而是给 LLM 看，所以放在 data 里
            return {"status": "success", "message": "已成功获取当前电路的描述。", "data": {"description": description}}
        except Exception as e:
            logger.error(f"[Tool:DescribeCircuit] 发生未知内部错误: {e}", exc_info=True)
            return {"status": "failure", "message": "错误: 获取电路描述时发生未知错误。", "error": {"type": "Unexpected", "details": str(e)}}

    @register_tool(
        description="彻底清空当前的电路设计，移除所有已添加的元件和它们之间的连接，并重置所有 ID 计数器。",
        parameters={"type": "object", "properties": {}}
    )
    def clear_circuit_tool(self, arguments: Dict[str, Any], memory_manager: MemoryManager) -> Dict[str, Any]:
        """Action 实现：清空电路。同步执行。"""
        logger.info("[Tool:ClearCircuit] 执行清空电路操作。")
        try:
            memory_manager.clear_circuit()
            memory_manager.add_to_long_term("执行了清空电路操作。")
            success_message = "操作成功: 当前电路已彻底清空。"
            return {"status": "success", "message": success_message}
        except Exception as e:
            logger.error(f"[Tool:ClearCircuit] 发生未知内部错误: {e}", exc_info=True)
            return {"status": "failure", "message": "错误: 清空电路时发生未知错误。", "error": {"type": "Unexpected", "details": str(e)}}

    # 可以继续在这里添加更多工具方法...

# --- 工具执行器模块 (Tool Executor) ---
class ToolExecutor:
    """负责根据名称查找并执行已注册的工具。"""
    def __init__(self, tool_registry: Dict[str, Dict[str, Any]], memory_manager: MemoryManager):
        logger.info("[ToolExecutor] 初始化工具执行器...")
        self.tool_registry = tool_registry
        self.memory_manager = memory_manager # 工具可能需要访问内存
        if not tool_registry:
             logger.warning("[ToolExecutor] 工具注册表为空！")
        logger.info(f"[ToolExecutor] 初始化完成，可识别 {len(tool_registry)} 个工具。")

    async def execute_tool_call(self, tool_name: str, params: Dict[str, Any], tool_call_id: str) -> Dict[str, Any]:
        """
        查找并执行单个工具调用。
        根据工具是同步还是异步决定执行方式。
        向工具注入 memory_manager 依赖。
        """
        logger.info(f"[ToolExecutor] 准备执行工具: '{tool_name}' (ID: {tool_call_id})")
        logger.debug(f"[ToolExecutor] 参数: {params}")

        if tool_name not in self.tool_registry:
            logger.error(f"[ToolExecutor] 尝试调用未注册的工具: '{tool_name}'")
            raise ToolNotFoundError(f"工具 '{tool_name}' 未注册或不可用。")

        tool_info = self.tool_registry[tool_name]
        tool_function = tool_info["function"]
        is_async = tool_info["is_async"]
        action_result: Dict[str, Any] = {"status": "failure", "message": "执行器内部错误"} # 默认失败

        try:
            start_time = time.monotonic()
            if is_async:
                # 如果工具本身是 async def
                logger.debug(f"[ToolExecutor] 调用异步工具: {tool_name}")
                # 传递依赖
                action_result = await tool_function(arguments=params, memory_manager=self.memory_manager)
            else:
                # 如果工具是普通同步函数 (假设它相对较快，或本身就在线程中运行)
                logger.debug(f"[ToolExecutor] 调用同步工具: {tool_name}")
                # 传递依赖
                # 注意：如果同步工具确实非常耗时，这里仍然可以按需用 to_thread
                # action_result = await asyncio.to_thread(tool_function, arguments=params, memory_manager=self.memory_manager)
                action_result = tool_function(arguments=params, memory_manager=self.memory_manager)

            duration = time.monotonic() - start_time
            logger.info(f"[ToolExecutor] 工具 '{tool_name}' 执行完毕。耗时: {duration:.3f}s. 状态: {action_result.get('status', 'N/A')}")

            # 验证工具返回结果的基本结构
            if not isinstance(action_result, dict) or 'status' not in action_result or 'message' not in action_result:
                logger.error(f"[ToolExecutor] 工具 '{tool_name}' 返回结果结构无效: {str(action_result)[:200]}... 强制标记为失败。")
                action_result = {"status": "failure", "message": f"错误: 工具 '{tool_name}' 返回结果结构无效。", "error": {"type": "InvalidToolResult", "details": f"Missing 'status' or 'message'. Got: {str(action_result)[:100]}"}}

            return action_result

        except (ToolInputError, ValueError, MemoryError) as tool_err: # 捕获工具实现中预期的业务逻辑错误
             logger.error(f"[ToolExecutor] 工具 '{tool_name}' 执行失败 (业务逻辑错误): {tool_err}", exc_info=False)
             # 保持原始错误信息
             raise ToolExecutionError(f"执行工具 '{tool_name}' 时出错: {tool_err}") from tool_err
        except Exception as exec_err: # 捕获工具执行期间未预料的异常
            logger.error(f"[ToolExecutor] 工具 '{tool_name}' 执行期间发生意外错误: {exec_err}", exc_info=True)
            # 包装为 ToolExecutionError
            raise ToolExecutionError(f"执行工具 '{tool_name}' 时发生意外内部错误: {exec_err}") from exec_err

# --- Agent 核心逻辑模块 (Agent Core) ---
class CircuitDesignAgent:
    """
    电路设计 Agent V8 - 采用单步规划循环与不支持 Function Calling 的 LLM 交互。
    负责编排整个工作流程。
    """
    def __init__(self, config: Type[AgentConfig]):
        logger.info(f"\n{'='*30} Agent V8 初始化开始 {'='*30}")
        self.config = config
        try:
            # 初始化核心组件
            self.memory_manager = MemoryManager(config)
            self.llm_interface = LLMInterface(config)
            self.output_parser = OutputParser()

            # 发现并注册工具 (从全局注册表获取)
            self.tool_registry = get_tool_registry()
            logger.info(f"[Agent Init] 从全局注册表加载了 {len(self.tool_registry)} 个工具。")
            if not self.tool_registry:
                 logger.warning("[Agent Init] 未发现任何已注册的工具！Agent 无法执行操作。")

            # 初始化工具执行器，并传入依赖
            self.tool_executor = ToolExecutor(self.tool_registry, self.memory_manager)

        except (ConfigurationError, MemoryError, Exception) as e:
            logger.critical(f"[Agent Init] 核心模块初始化失败: {e}", exc_info=True)
            # 向上抛出，让主程序处理启动失败
            raise

        logger.info(f"\n{'='*30} Agent V8 初始化成功 {'='*30}\n")

    def _get_planning_prompt(self, current_query: str) -> str:
        """构建规划阶段的 System Prompt (V8 - 单步规划)"""
        tool_schemas_desc = get_tool_schemas_for_prompt()
        memory_context = self.memory_manager.get_memory_context_for_prompt(current_query)

        return (
            "你是一位顶尖的、极其严谨的电路设计编程助理。你的行为必须专业、精确，并严格遵循指令。\n"
            "你的当前任务是：基于用户的最新指令、完整的对话历史以及当前的电路状态和相关知识，**决定下一步应该执行什么操作**。\n"
            "**重要：你每次只能规划一步！** 要么是调用下面列表中的 **一个** 合适工具来推进任务，要么是认为任务已完成或无法继续而直接回复用户。\n"
            "你的输出**必须严格**遵循以下格式：\n"
            "1.  一个 `<think>...</think>` XML 块：在其中详细阐述你的思考过程。包括：理解用户意图，分析当前状态和历史，评估是否需要工具以及哪个工具最合适，或者为什么应该直接回复。\n"
            "2.  **紧随其后**，**必须**是一个**单一的、格式完全正确的 JSON 对象**。JSON 对象必须是以下两种结构之一：\n"
            "    a. **调用工具:** `{ \"action\": \"tool_call\", \"tool_name\": \"工具名称\", \"params\": { /* 参数对象 */ } }`\n"
            "       - `action`: 固定为 \"tool_call\".\n"
            "       - `tool_name`: 必须是下面“可用工具列表”中提供的**精确名称**。\n"
            "       - `params`: 调用该工具所需的参数对象。如果无参数，则为 `{}`。\n"
            "    b. **直接回复:** `{ \"action\": \"direct_reply\", \"content\": \"给用户的回复内容\" }`\n"
            "       - `action`: 固定为 \"direct_reply\".\n"
            "       - `content`: 你准备直接回复给用户的完整、友好的文本内容。\n\n"
            "**可用工具列表与参数规范:**\n"
            f"{tool_schemas_desc}\n\n"
            "**当前上下文信息:**\n"
            f"{memory_context}\n\n"
            "**再次强调：你的回复格式必须严格是 `<think>思考过程</think>` 后面紧跟着一个符合上述 a 或 b 两种结构之一的 JSON 对象。不要添加任何额外的文字或解释！**"
        )

    def _get_final_response_prompt(self) -> str:
        """构建最终响应生成阶段的 System Prompt (在工具循环结束后调用)"""
        memory_context = self.memory_manager.get_memory_context_for_prompt() # 获取最终状态
        tool_schemas_desc = get_tool_schemas_for_prompt() # 供参考

        return (
            "你是一位顶尖的电路设计编程助理，擅长总结工作并清晰地汇报。\n"
            "你的任务是：基于到目前为止的**完整对话历史**（包括用户最初的请求、你之前的思考、所有执行的工具调用及其结果），生成最终的、面向用户的文本回复。\n"
            "**关键信息来源是角色为 'tool' 的消息**: 每条 'tool' 消息的 `content` 是一个 JSON 字符串，包含了对应工具执行的 `status` 和 `message`。\n"
            "你的报告必须：\n"
            "1.  回顾整个交互过程，理解用户最终的目标和所有中间步骤。\n"
            "2.  准确总结所有**已执行**工具操作的结果（成功或失败），并根据 'tool' 消息中的信息向用户解释。\n"
            "3.  如果任务因工具失败而中断或未能完全完成，需明确说明当前状态。\n"
            "4.  提供一个连贯、完整的最终回复，回答用户的原始问题或确认任务的最终状态。\n"
            "5.  **严格按照以下固定格式**生成你的回复：\n"
            "   a. **思考过程:** 在 `<think>` 和 `</think>` 标签之间，详细阐述你的反思和报告组织思路。回顾整个流程，分析工具结果，评估任务完成度，规划最终回复内容。\n"
            "   b. **正式回复:** 在 `</think>` 标签之后，紧跟着面向用户的正式文本回复。\n"
            "**最终输出格式必须严格是:**\n"
            "`<think>你的详细思考过程</think>\n\n你的正式回复文本`\n"
            "(注意：`</think>` 标签后是两个换行符 `\\n\\n`，然后是正式回复。)\n"
            "**重要：** 在这个阶段，你**绝对不能**再生成任何工具调用或 JSON 对象。\n\n"
            "**上下文参考信息:**\n"
            "【当前电路状态与记忆】\n"
            f"{memory_context}\n"
            "【我的可用工具列表 (仅供你参考)】\n"
            f"{tool_schemas_desc}\n"
        )

    async def process_user_request(self, user_request: str) -> str:
        """
        处理用户请求的核心异步流程 (V8 - 单步规划循环)。
        """
        request_start_time = time.monotonic()
        logger.info(f"\n{'='*25} V8 开始处理用户请求 {'='*25}")
        logger.info(f"[Agent] 收到用户指令: \"{user_request}\"")

        if not user_request or user_request.isspace():
            logger.info("[Agent] 用户指令为空。")
            return "<think>用户输入为空，无需处理。</think>\n\n请输入您的指令！"

        # --- 1. 初始化交互状态 & 添加用户输入到记忆 ---
        try:
            # 注意：这里每次处理新请求时，短期记忆是持续累积的，
            # 如果希望每次请求都是独立的上下文，需要在开始时清空或重置短期记忆
            # (当前实现是持续对话模式)
            self.memory_manager.add_to_short_term({"role": "user", "content": user_request})
        except MemoryError as e:
             logger.error(f"[Agent] 添加用户消息到短期记忆失败: {e}", exc_info=True)
             return f"<think>添加用户消息到短期记忆失败: {e}</think>\n\n抱歉，我在记录您的指令时遇到了内部问题，请稍后重试。"

        # --- 2. 单步规划与执行循环 ---
        step_count = 0
        last_thinking_process = "未开始规划"
        planning_error_count = 0

        while step_count < self.config.MAX_TOOL_STEPS:
            step_count += 1
            logger.info(f"\n--- [步骤 {step_count}/{self.config.MAX_TOOL_STEPS}] 开始规划 ---")

            # --- 2a. 准备规划 Prompt 和消息 ---
            try:
                current_history = self.memory_manager.get_short_term_history()
                # 将最后一条用户消息作为当前查询，用于 RAG (如果需要)
                current_query = user_request if step_count == 1 else current_history[-1].get("content", "") if current_history else ""

                system_prompt = self._get_planning_prompt(current_query)
                # 更新或添加 System Prompt 到记忆的最前面
                self.memory_manager.add_system_prompt(system_prompt)
                # 获取包含最新 System Prompt 的完整历史
                messages_for_llm = self.memory_manager.get_short_term_history()

            except Exception as e:
                 logger.error(f"[Agent] 准备规划 Prompt 时出错: {e}", exc_info=True)
                 return f"<think>内部错误：准备规划信息时出错: {e}</think>\n\n抱歉，我在处理您的请求时遇到内部错误，请稍后再试。"

            # --- 2b. 调用 LLM 进行规划 (带重试) ---
            parsed_plan = None
            planning_error = ""
            for attempt in range(self.config.MAX_PLANNING_RETRIES + 1):
                logger.info(f"[Agent] 尝试第 {attempt + 1}/{self.config.MAX_PLANNING_RETRIES + 1} 次调用规划 LLM...")
                await async_print(f"    (思考中... 尝试 {attempt + 1})")
                try:
                    llm_response = await self.llm_interface.call_llm(
                        messages=messages_for_llm,
                        timeout=self.config.PLANNING_TIMEOUT_SECONDS
                    )
                    if not llm_response or not llm_response.choices or not llm_response.choices[0].message or not llm_response.choices[0].message.content:
                        raise LLMError("LLM 响应无效或内容为空。")

                    response_content = llm_response.choices[0].message.content
                    logger.debug(f"[Agent] LLM 规划响应原文 (前 500 字): {response_content[:500]}...")

                    # --- 2c. 解析 LLM 的单步规划 ---
                    thinking_process, parsed_plan_attempt, planning_error = self.output_parser.parse_planning_response(response_content)
                    last_thinking_process = thinking_process # 记录最后一次的思考过程

                    if parsed_plan_attempt:
                        parsed_plan = parsed_plan_attempt # 解析成功
                        planning_error = "" # 清除错误信息
                        # 将 LLM 的规划响应（原始文本）添加到记忆
                        # 注意：我们存储的是包含 <think> 和 JSON 的原始文本
                        self.memory_manager.add_to_short_term({"role": "assistant", "content": response_content})
                        break # 成功，跳出重试循环
                    else:
                         # 解析失败，记录错误，继续重试（如果还有次数）
                         logger.warning(f"[Agent] 第 {attempt + 1} 次规划解析失败: {planning_error}")

                except (LLMError, MemoryError) as e: # MemoryError 可能在添加 assistant 响应时发生
                     planning_error = f"LLM 调用或记忆错误: {e}"
                     logger.error(f"[Agent] 第 {attempt + 1} 次规划失败 ({type(e).__name__}): {e}", exc_info=False)
                     # 连接或严重错误可能不值得重试？或者继续尝试
                except Exception as e:
                     planning_error = f"规划或解析时发生未知严重错误: {e}"
                     logger.error(f"[Agent] 第 {attempt + 1} 次规划遭遇未知错误: {e}", exc_info=True)
                     # 出现未知错误，可能直接跳出重试？或者继续
                     # break # 遇到未知严重错误，停止重试

                # 如果是最后一次尝试且仍然失败
                if attempt == self.config.MAX_PLANNING_RETRIES and parsed_plan is None:
                    logger.error(f"[Agent] 所有规划尝试均失败。最后错误: {planning_error}")
                    planning_error_count += 1
                    # 连续多次规划失败，可能需要中止
                    if planning_error_count >= 2: # 例如连续两次规划都彻底失败
                         logger.critical("[Agent] 连续多次规划失败，中止处理！")
                         return f"<think>{last_thinking_process}\n错误：连续多次无法从 LLM 获取有效规划。最后错误: {planning_error}</think>\n\n抱歉，我在理解如何进行下一步时遇到了严重困难，无法继续处理您的请求。"
                    # 否则，继续循环，寄希望于下一步能自我纠正（如果下面没有 break 的话）

            # 如果所有重试后仍然没有有效计划
            if parsed_plan is None:
                logger.error("[Agent] 无法获取有效规划，中止当前请求处理。")
                return f"<think>{last_thinking_process}\n错误：未能获取有效的下一步规划。最后解析错误: {planning_error}</think>\n\n抱歉，我无法确定下一步该怎么做。请尝试更清晰地表述您的指令，或简化请求。"

            # --- 2d. 根据规划执行动作 ---
            if isinstance(parsed_plan, LLMDirectReplyPlan):
                # --- 情况 B: LLM 决定直接回复 ---
                logger.info("[Agent] 决策：直接回复用户。")
                await async_print("    (准备直接回复...)")
                # 回复内容已在 parsed_plan.content 中
                # 最终的回复格式化将在循环外进行（或在这里直接返回，取决于设计）
                # 为了统一，我们在循环结束后生成最终回复
                # 这里只需 break 循环
                break # 跳出规划-执行循环

            elif isinstance(parsed_plan, LLMToolCallPlan):
                # --- 情况 A: LLM 决定调用工具 ---
                tool_name = parsed_plan.tool_name
                params = parsed_plan.params
                # 生成一个唯一的 Tool Call ID，用于关联结果
                tool_call_id = f"toolcall_{step_count}_{tool_name[:10].replace('_','').lower()}_{hex(abs(hash(json.dumps(params, sort_keys=True))))[2:8]}"
                logger.info(f"[Agent] 决策：调用工具 '{tool_name}' (ID: {tool_call_id})")
                await async_print(f"    (准备执行操作: {tool_name}...)")

                # --- 2e. 执行工具 ---
                tool_result_dict = None
                try:
                    tool_result_dict = await self.tool_executor.execute_tool_call(tool_name, params, tool_call_id)
                    status = tool_result_dict.get("status", "failure")
                    message = tool_result_dict.get("message", "工具未提供消息")
                    await async_print(f"      - 操作状态: {status}. 结果: {message[:80]}{'...' if len(message)>80 else ''}")

                except ToolError as e: # ToolExecutor 或工具本身抛出的预期错误
                    logger.error(f"[Agent] 工具执行失败: {e}", exc_info=False)
                    tool_result_dict = {"status": "failure", "message": f"执行工具 '{tool_name}' 时出错: {e}", "error": {"type": type(e).__name__, "details": str(e)}}
                    await async_print(f"      - 操作失败: {e}")
                except Exception as e: # 未预料的执行错误
                     logger.error(f"[Agent] 工具执行期间发生意外严重错误: {e}", exc_info=True)
                     tool_result_dict = {"status": "failure", "message": f"执行工具 '{tool_name}' 时发生意外内部错误。", "error": {"type": "UnexpectedExecutionError", "details": str(e)}}
                     await async_print(f"      - 操作失败: 发生内部错误")

                # --- 2f. 添加工具结果到记忆 ---
                try:
                    # 将结果字典转换为 JSON 字符串存储
                    result_content_str = json.dumps(tool_result_dict, ensure_ascii=False, indent=2, default=str)
                    tool_message = {"role": "tool", "tool_call_id": tool_call_id, "content": result_content_str}
                    self.memory_manager.add_to_short_term(tool_message)
                    logger.debug(f"[Agent] 工具 '{tool_call_id}' 的结果已添加至短期记忆。")
                except MemoryError as e:
                     logger.error(f"[Agent] 添加工具结果到短期记忆失败: {e}. 请求可能无法完成。")
                     # 这是一个严重问题，可能导致 LLM 无法知道工具结果
                     return f"<think>{last_thinking_process}\n内部错误：无法记录工具执行结果: {e}</think>\n\n抱歉，我在记录操作结果时遇到了内部问题，无法继续。请稍后重试。"

                # 检查工具是否失败，如果失败是否需要中止？(当前策略：让 LLM 看到失败结果，自行决定下一步)
                if tool_result_dict.get("status") != "success":
                     logger.warning(f"[Agent] 工具 '{tool_name}' 执行失败，将结果反馈给 LLM 进行下一步规划。")
                     # 这里可以根据失败的严重程度决定是否直接中止，但目前让 LLM 决定
                     # planning_error_count += 1 # 也可以将工具失败计入错误计数

            else:
                # 解析器返回了未知的类型（理论上不应该发生）
                logger.error(f"[Agent] 解析器返回了未知的计划类型: {type(parsed_plan)}。中止处理。")
                return f"<think>{last_thinking_process}\n内部错误：无法识别的规划类型 {type(parsed_plan)}。</think>\n\n抱歉，处理过程中发生内部逻辑错误，请联系技术支持。"

            # 检查是否达到最大错误次数
            # if planning_error_count >= 2: # 如果工具失败也计入错误
            #      logger.critical("[Agent] 累计错误过多，中止处理！")
            #      return f"<think>{last_thinking_process}\n错误：处理过程中累计错误过多，无法继续。</think>\n\n抱歉，在处理您的请求过程中遇到了多次问题，无法继续执行。"

            # --- 继续下一次循环 ---

        # --- 循环结束 (达到最大步骤或 LLM 决定回复) ---
        logger.info(f"[Agent] 规划/执行循环结束。总步骤: {step_count-1 if isinstance(parsed_plan, LLMDirectReplyPlan) else step_count}")

        # --- 3. 生成最终响应 ---
        final_report = ""
        final_thinking = last_thinking_process # 使用循环中最后的思考

        if isinstance(parsed_plan, LLMDirectReplyPlan):
             # 情况1：循环因 LLM 直接回复而结束
             logger.info("[Agent] 使用 LLM 在规划阶段生成的直接回复。")
             final_reply = parsed_plan.content
             final_report = f"<think>{final_thinking}</think>\n\n{final_reply}".rstrip()
             # 该直接回复已在循环内添加到记忆中
        else:
             # 情况2：循环因达到最大步骤数结束，或因其他原因（如需要总结工具结果）
             logger.info("[Agent] 需要调用 LLM 生成最终的总结性回复。")
             await async_print("    (生成最终总结报告...)")
             try:
                 # 准备最终响应的 Prompt 和消息列表
                 final_system_prompt = self._get_final_response_prompt()
                 self.memory_manager.add_system_prompt(final_system_prompt) # 更新系统提示为总结模式
                 messages_for_final_llm = self.memory_manager.get_short_term_history()

                 # 调用 LLM 生成最终回复
                 final_llm_response = await self.llm_interface.call_llm(
                     messages=messages_for_final_llm,
                     timeout=self.config.RESPONSE_TIMEOUT_SECONDS
                 )

                 if not final_llm_response or not final_llm_response.choices or not final_llm_response.choices[0].message or not final_llm_response.choices[0].message.content:
                      raise LLMError("最终响应 LLM 调用返回无效或空内容。")

                 final_response_content = final_llm_response.choices[0].message.content
                 # 解析最终的思考和回复
                 final_thinking, final_reply = self.output_parser.parse_final_response(final_response_content)

                 # 将最终回复（原始文本）添加到记忆
                 self.memory_manager.add_to_short_term({"role": "assistant", "content": final_response_content})

                 final_report = f"<think>{final_thinking}</think>\n\n{final_reply}".rstrip()

             except (LLMError, MemoryError, Exception) as e:
                 logger.error(f"[Agent] 生成最终响应失败: {e}", exc_info=True)
                 # 生成一个备用的错误报告
                 fallback_thinking = f"{last_thinking_process}\n错误：生成最终总结报告失败: {e}"
                 fallback_reply = f"抱歉，在为您准备最终报告时遇到了问题 ({e})。请参考之前的步骤了解详情。"
                 final_report = f"<think>{fallback_thinking}</think>\n\n{fallback_reply}".rstrip()
                 # 尝试记录错误到记忆
                 try: self.memory_manager.add_to_short_term({"role": "assistant", "content": final_report})
                 except MemoryError: pass

        # --- 请求处理完毕 ---
        request_end_time = time.monotonic()
        duration = request_end_time - request_start_time
        logger.info(f"\n{'='*25} V8 请求处理完毕 (耗时: {duration:.3f} 秒) {'='*25}\n")
        return final_report


# --- 主程序入口 (main.py) ---
async def main_async():
    """异步主函数：初始化 Agent 并启动交互循环。"""
    await async_print("=" * 70)
    await async_print("🚀 启动 OpenManus 电路设计 Agent (V8 Refactored) 🚀")
    await async_print("   特性: 模块化, 单步健壮规划, Token 内存管理, 工具解耦")
    await async_print("=" * 70)
    logger.info("[Main] 开始 Agent 初始化...")

    # --- 加载配置并检查 API Key ---
    try:
        config = AgentConfig()
        # 再次确认 API Key (虽然类初始化时已检查)
        if not config.API_KEY:
             await async_print("错误：环境变量 ZHIPUAI_API_KEY 未设置。请设置后重启程序。")
             logger.critical("[Main] ZHIPUAI_API_KEY 未设置。")
             return
        logger.info("[Main] 配置加载成功，API Key 已找到。")
    except Exception as e:
         await async_print(f"错误：加载配置失败: {e}")
         logger.critical(f"[Main] 配置加载失败: {e}", exc_info=True)
         return

    # --- 初始化 Agent ---
    agent: Optional[CircuitDesignAgent] = None
    try:
        # 实例化 Agent 核心类
        agent = CircuitDesignAgent(config)
        await async_print("\n🎉 Agent V8 初始化成功！已准备就绪。")
        await async_print("\n您可以尝试以下指令:")
        await async_print("  - '给我加个1k电阻R1K和3V电池B3V'") # 测试多步工具调用
        await async_print("  - '连接R1K和B3V'")
        await async_print("  - '电路现在什么样？'")
        await async_print("  - '尝试连接 R1K 和一个不存在的元件 XYZ'") # 测试工具失败
        await async_print("  - '清空电路'")
        await async_print("  - '你好'") # 测试直接回复
        await async_print("  - 输入 '退出' 来结束程序")
        await async_print("-" * 70)
    except Exception as e:
        logger.critical(f"[Main] Agent V8 初始化失败: {e}", exc_info=True)
        await async_print(f"\n🔴 Agent 初始化失败！错误: {e}。请检查日志和配置。程序即将退出。")
        return

    # --- 主交互循环 ---
    try:
        while True:
            user_input = ""
            try:
                # 获取用户输入 (仍然是同步阻塞)
                user_input = input("用户 > ").strip()
            except (EOFError, KeyboardInterrupt):
                 await async_print("\n检测到中断信号...")
                 break # 跳出循环准备退出

            if user_input.lower() in ['退出', 'quit', 'exit', '再见', '结束', 'bye']:
                await async_print("\n收到退出指令。感谢您的使用！👋")
                logger.info("[Main] 收到退出指令，结束交互循环。")
                break

            if not user_input: continue

            # 调用 Agent 处理请求
            try:
                start_process_time = time.monotonic()
                response = await agent.process_user_request(user_input)
                process_duration = time.monotonic() - start_process_time

                await async_print(f"\n📝 Agent 回复 (耗时: {process_duration:.3f} 秒):")
                # 只打印面向用户的部分（去掉 <think> 块）
                think_match = re.match(r"<think>.*?</think>\s*\n\n(.*)", response, re.DOTALL | re.IGNORECASE)
                if think_match:
                    user_reply = think_match.group(1)
                else:
                    user_reply = response # 如果没有 think 块，就全部显示
                await async_print(user_reply)
                # 调试时可以打印完整响应
                # logger.debug(f"Agent 完整响应:\n{response}")
                await async_print("-" * 70)

            except Exception as agent_err: # 捕获 Agent 处理请求时未捕获的异常
                 logger.error(f"[Main] 处理指令 '{user_input[:50]}...' 时发生意外错误: {agent_err}", exc_info=True)
                 await async_print(f"\n🔴 Agent 运行时错误:")
                 # 避免再次调用 Agent 逻辑，直接生成错误报告
                 error_report = f"<think>处理指令 '{user_input[:50]}...' 时发生内部错误: {agent_err}\n{traceback.format_exc()}</think>\n\n抱歉，我在执行您的指令时遇到了意外问题 ({agent_err})！请尝试其他指令或检查日志。"
                 # 只显示给用户的部分
                 await async_print(f"抱歉，我在执行您的指令时遇到了意外问题 ({agent_err})！请尝试其他指令或检查日志。")
                 await async_print("-" * 70)
                 continue # 继续下一次循环

    except Exception as loop_err:
        logger.critical(f"[Main] 主交互循环外发生未处理异常: {loop_err}", exc_info=True)
        await async_print(f"\n🔴 严重系统错误导致交互循环终止: {loop_err}。")
    finally:
        logger.info("[Main] 主交互循环结束。")
        await async_print("\n正在关闭 Agent V8...")
        # 如果有需要，可以在这里添加 Agent 的清理逻辑
        # await agent.cleanup()

if __name__ == "__main__":
    # 在标准 Python 脚本中运行
    try:
        # 确保环境变量已设置是前提
        if not os.environ.get("ZHIPUAI_API_KEY"):
             print("错误：启动前请设置环境变量 ZHIPUAI_API_KEY。", file=sys.stderr)
             sys.exit(1)

        # 加载并实例化工具类，这样装饰器就会执行并填充全局注册表
        # 这一步很关键，确保在 Agent 初始化前工具已被注册
        _ = CircuitTools() # 实例化一次以触发工具注册

        asyncio.run(main_async())

    except KeyboardInterrupt:
        print("\n程序被用户强制退出 (KeyboardInterrupt)。")
        logger.info("[Main Script] 程序被 KeyboardInterrupt 中断。")
    except Exception as e:
        print(f"\n程序因顶层错误而意外退出: {e}", file=sys.stderr)
        logger.critical(f"脚本执行期间发生顶层异常: {e}", exc_info=True)
        sys.exit(1) # 非正常退出
    finally:
        print("Agent V8 程序已关闭。")