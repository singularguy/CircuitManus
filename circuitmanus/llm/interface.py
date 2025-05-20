# IDT_AGENT_Pro/circuitmanus/llm/interface.py
import time
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable

from zhipuai import ZhipuAI # 确保 zhipuai 库已安装

# 从当前包的根目录导入 Agent 类型提示，以解决循环依赖问题
# 这需要在 agent.py 定义 CircuitAgent 后才能完全生效，
# 但为了类型提示的完整性，我们先这样写。
# 或者使用 'typing.TYPE_CHECKING' 来处理
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..agent import CircuitAgent # 使用相对导入指向 agent.py 中的 CircuitAgent

logger = logging.getLogger(__name__)

class LLMInterface:
    """
    LLMInterface (LLM 交互接口) - V1.0.0
    负责与大语言模型 (例如智谱AI的GLM系列) 进行通信。
    它处理API请求的构建、发送、以及初步的响应处理。
    """
    def __init__(self, 
                 agent_instance: 'CircuitAgent', # 类型提示 CircuitAgent
                 model_name: str = "glm-z1-flash", # 默认模型
                 default_temperature: float = 0.01, 
                 default_max_tokens: int = 8190):
        """
        初始化 LLMInterface。

        Args:
            agent_instance (CircuitAgent): 对 CircuitAgent 主实例的引用。
                                           需要用它来获取 API key 和可能的其他配置。
            model_name (str): 要使用的LLM模型名称。
            default_temperature (float): LLM调用的默认温度参数。
            default_max_tokens (int): LLM调用的默认最大输出token数。

        Raises:
            ValueError: 如果 agent_instance 无效或缺少 API key。
            ConnectionError: 如果初始化 ZhipuAI 客户端失败。
        """
        logger.info(f"[LLMInterface V1.0.0] 初始化 LLM 接口,目标模型: {model_name}。")
        
        # 严格检查 agent_instance 和其上的 api_key
        if not agent_instance or not hasattr(agent_instance, 'api_key'):
             logger.critical("[LLMInterface V1.0.0] agent_instance 无效或缺少 'api_key' 属性。")
             raise ValueError("LLMInterface 需要一个包含 'api_key' 属性的 Agent 实例。")
        
        self.agent_instance: 'CircuitAgent' = agent_instance
        api_key = self.agent_instance.api_key
        if not api_key:
            logger.critical("[LLMInterface V1.0.0] 智谱 AI API Key 未提供或为空。")
            raise ValueError("智谱 AI API Key 不能为空。")

        try:
            # 初始化 ZhipuAI 客户端
            self.client = ZhipuAI(api_key=api_key)
            logger.info("[LLMInterface V1.0.0] 智谱 AI 客户端初始化成功。")
        except Exception as e:
            logger.critical(f"[LLMInterface V1.0.0] 初始化智谱 AI 客户端失败: {e}", exc_info=True)
            # 将原始异常包装在 ConnectionError 中，更符合其性质
            raise ConnectionError(f"初始化智谱 AI 客户端失败: {e}") from e

        self.model_name: str = model_name
        self.default_temperature: float = default_temperature
        self.default_max_tokens: int = default_max_tokens
        
        logger.info(f"[LLMInterface V1.0.0] LLM 接口初始化完成 (模型: {model_name}, 温度: {default_temperature}, 最大Token数: {default_max_tokens}, 流式输出: False)。")

    async def call_llm(self, 
                       messages: List[Dict[str, Any]], 
                       execution_phase: str, 
                       status_callback: Optional[Callable[[Dict], Awaitable[None]]] = None
                       ) -> Any: # 返回类型是 ZhipuAI 库的响应对象，这里用 Any 简化
        """
        异步调用大语言模型。

        Args:
            messages (List[Dict[str, Any]]): 发送给LLM的消息列表 (符合OpenAI/ZhipuAI格式)。
            execution_phase (str): 当前执行阶段 (例如 "planning", "response_generation")，用于日志和状态回调。
            status_callback (Optional[Callable[[Dict], Awaitable[None]]]): 
                一个异步回调函数，用于在LLM调用过程中发送状态更新。

        Returns:
            Any: LLM API的原始响应对象 (通常是 ZhipuAI SDK 定义的 ChatCompletion 对象)。

        Raises:
            ConnectionError: 如果API调用返回None或发生网络层面的错误。
            Exception: 其他API调用相关的未知错误。
        """
        call_args = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens,
            "stream": False, # 当前实现不支持流式输出
        }

        logger.info(f"[LLMInterface V1.0.0] 准备异步调用 LLM ({self.model_name}, 阶段: {execution_phase}, 期望输出格式: <think> 标签后跟 JSON)...")
        logger.debug(f"[LLMInterface V1.0.0] 发送的消息条数: {len(messages)}。")
        
        # 详细日志记录发送给LLM的消息内容 (特别是系统提示和最近的用户/助手消息)
        if logger.isEnabledFor(logging.DEBUG) and messages: # 检查是否有消息且日志级别允许
             try:
                 messages_content_for_log = []
                 for m_idx, m in enumerate(messages):
                     role = m.get("role")
                     content = str(m.get("content","")) # 确保内容是字符串
                     # 对系统提示可能很长，做截断；其他角色消息也做适度截断
                     if role == "system":
                         content_preview = content[:10000] + ("..." if len(content) > 10000 else "")
                     else:
                         content_preview = content[:1000] + ("..." if len(content) > 200 else "") # 原代码是1000/200
                     messages_content_for_log.append({
                         "index": m_idx, 
                         "role": role, 
                         "content_preview_length": len(content), # 记录原始长度
                         "content_preview": content_preview
                        })
                 # 使用 ensure_ascii=False 以正确显示中文等非ASCII字符
                 messages_summary = json.dumps(messages_content_for_log, ensure_ascii=False, indent=2)
                 logger.debug(f"[LLMInterface V1.0.0] 发送给 LLM 的消息列表 (预览):\n{messages_summary}")
             except Exception as e_json:
                 logger.warning(f"[LLMInterface V1.0.0] 无法序列化消息列表进行调试日志: {e_json}")

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
            # 关键：ZhipuAI的SDK `create` 方法是同步的，需要用 `asyncio.to_thread` 包装以在异步环境正确运行而不阻塞事件循环。
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
                if response.usage: 
                    logger.info(f"[LLMInterface V1.0.0] Token 统计: Prompt={response.usage.prompt_tokens}, Completion={response.usage.completion_tokens}, Total={response.usage.total_tokens}")
                if response.choices:
                    finish_reason = response.choices[0].finish_reason
                    logger.info(f"[LLMInterface V1.0.0] 完成原因: {finish_reason}")
                    if finish_reason == 'length': 
                        logger.warning("[LLMInterface V1.0.0] LLM 响应因达到最大 token 限制而被截断！这可能导致输出不完整或JSON解析失败！")
                    
                    # 提取原始响应内容，供 OutputParser 处理
                    raw_llm_content = response.choices[0].message.content
                    logger.debug(f"[LLMInterface V1.0.0] LLM 原始响应内容 (完整):\n{raw_llm_content}") # 日志中记录完整原始输出
                else:
                    logger.warning("[LLMInterface V1.0.0] LLM 响应中缺少 'choices' 字段。")
            else:
                 # 这种情况理论上不应该发生，如果 ZhipuAI 客户端调用成功，应该总是有 response 对象
                 logger.error("[LLMInterface V1.0.0] LLM API 调用返回了 None！这通常表示SDK内部错误或未预期的行为。")
                 raise ConnectionError("LLM API call returned None.")
            
            return response # 返回原始的 ZhipuAI 响应对象

        except Exception as e:
            # 捕获所有类型的异常，包括 ZhipuAI SDK 可能抛出的特定异常
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
            # 将异常重新抛出，让上层调用者 (例如 Agent 的主流程) 处理
            raise