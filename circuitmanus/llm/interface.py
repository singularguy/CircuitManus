# IDT_AGENT_NATIVE/circuitmanus/llm/interface.py (尝试兼容旧版 zhipuai SDK)
import time
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable

import httpx # ZhipuAI 内部使用 httpx, 可以用来配置超时

# --- ZhipuAI SDK 导入和兼容性处理 ---
try:
    from zhipuai import ZhipuAI, ZhipuAIAPIError # 尝试导入新版的特定API错误
except ImportError:
    logger_compat = logging.getLogger(__name__) # 获取logger实例
    logger_compat.warning(
        "Failed to import 'ZhipuAIAPIError' from 'zhipuai'. "
        "This might be due to an older version of the zhipuai SDK. "
        "Specific ZhipuAI API error handling will be limited. "
        "Consider upgrading the 'zhipuai' package (pip install --upgrade zhipuai)."
    )
    # 如果 ZhipuAIAPIError 不存在，我们定义一个假的占位符，
    # 或者在 except 块中捕获更通用的 Exception。
    # 为了让代码结构不变，我们定义一个假的，但实际捕获时，
    # 这个假的不会被匹配到，而是由更通用的 Exception 捕获。
    # 或者，更好的是，我们用一个变量来标记是否可用。
    try:
        from zhipuai import ZhipuAI # 确保 ZhipuAI 本身能导入
        ZhipuAIAPIError_AVAILABLE = False # 标记 ZhipuAIAPIError 不可用
        class ZhipuAIAPIError(Exception): # 定义一个假的，避免NameError，但它不会是真正的SDK错误
            pass 
    except ImportError: # 如果连 ZhipuAI 都导入不了，那是更严重的问题
        logger_compat.critical("CRITICAL: Failed to import 'ZhipuAI' base class. ZhipuAI SDK is not installed correctly or missing.")
        raise # 直接抛出原始的 ImportError

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..agent import CircuitAgent 

logger = logging.getLogger(__name__) # 模块级 logger

class LLMInterface:
    # ... ( __init__ 方法保持不变，它仍然会尝试使用配置的超时初始化 ZhipuAI ) ...
    def __init__(self, 
                 agent_instance: 'CircuitAgent', 
                 model_name: str = "glm-z1-flash", 
                 default_temperature: float = 0.01, 
                 default_max_tokens: int = 8190,
                 api_timeout_seconds: int = 120, 
                 enable_detailed_llm_message_logging: bool = False 
                 ):
        logger.info(f"[LLMInterface V1.0.0 Configurable] 初始化 LLM 接口, 目标模型: {model_name}, API超时: {api_timeout_seconds}s.")
        
        if not agent_instance or not hasattr(agent_instance, 'api_key'):
             logger.critical("[LLMInterface V1.0.0 Configurable] agent_instance 无效或缺少 'api_key' 属性。")
             raise ValueError("LLMInterface 需要一个包含 'api_key' 属性的 Agent 实例。")
        
        self.agent_instance: 'CircuitAgent' = agent_instance
        api_key = self.agent_instance.api_key
        if not api_key:
            logger.critical("[LLMInterface V1.0.0 Configurable] 智谱 AI API Key 未提供或为空。")
            raise ValueError("智谱 AI API Key 不能为空。")

        self.api_timeout_seconds = api_timeout_seconds
        self.enable_detailed_llm_message_logging = enable_detailed_llm_message_logging
        self._zhipuai_api_error_available = 'ZhipuAIAPIError' in globals() and not (globals()['ZhipuAIAPIError'] is Exception and ZhipuAIAPIError.__name__ == 'ZhipuAIAPIError')


        try:
            effective_timeout = float(self.api_timeout_seconds)
            self.client = ZhipuAI(api_key=api_key, timeout=effective_timeout) # type: ignore
            logger.info(f"[LLMInterface V1.0.0 Configurable] 智谱 AI 客户端初始化成功，全局超时设置为 {effective_timeout} 秒。")
        except Exception as e:
            logger.critical(f"[LLMInterface V1.0.0 Configurable] 初始化智谱 AI 客户端失败: {e}", exc_info=True)
            raise ConnectionError(f"初始化智谱 AI 客户端失败: {e}") from e

        self.model_name: str = model_name
        self.default_temperature: float = default_temperature
        self.default_max_tokens: int = default_max_tokens
        
        logger.info(f"[LLMInterface V1.0.0 Configurable] LLM 接口初始化完成 (模型: {model_name}, 温度: {default_temperature}, 最大Token数: {default_max_tokens})。")


    async def call_llm(self, 
                       messages: List[Dict[str, Any]], 
                       execution_phase: str, 
                       status_callback: Optional[Callable[[Dict], Awaitable[None]]] = None
                       ) -> Any: 
        # ... (call_args 和 日志记录逻辑保持不变) ...
        call_args = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens,
            "stream": False, 
        }

        logger.info(f"[LLMInterface V1.0.0 Configurable] 准备异步调用 LLM ({self.model_name}, 阶段: {execution_phase})...")
        logger.debug(f"[LLMInterface V1.0.0 Configurable] 发送的消息条数: {len(messages)}。")
        
        if self.enable_detailed_llm_message_logging and logger.isEnabledFor(logging.DEBUG):
             try:
                 full_messages_json = json.dumps(messages, ensure_ascii=False, indent=2)
                 logger.debug(f"[LLMInterface V1.0.0 Configurable] [DETAILED_LOG] 发送给 LLM 的完整消息列表:\n{full_messages_json}")
             except Exception as e_json_full:
                 logger.warning(f"[LLMInterface V1.0.0 Configurable] 无法序列化完整消息列表进行详细调试日志: {e_json_full}")
        elif logger.isEnabledFor(logging.DEBUG) and messages: 
             try:
                 messages_content_for_log = []
                 for m_idx, m in enumerate(messages):
                     role = m.get("role")
                     content = str(m.get("content","")) 
                     if role == "system": content_preview = content[:5000] + ("..." if len(content) > 5000 else "")
                     else: content_preview = content[:500] + ("..." if len(content) > 500 else "") 
                     messages_content_for_log.append({ "index": m_idx, "role": role, "content_preview_length": len(content), "content_preview": content_preview })
                 messages_summary = json.dumps(messages_content_for_log, ensure_ascii=False, indent=2)
                 logger.debug(f"[LLMInterface V1.0.0 Configurable] 发送给 LLM 的消息列表 (预览):\n{messages_summary}")
             except Exception as e_json_preview:
                 logger.warning(f"[LLMInterface V1.0.0 Configurable] 无法序列化消息列表预览进行调试日志: {e_json_preview}")

        request_id_to_send = getattr(self.agent_instance, 'current_request_id', None)
        
        if status_callback:
            await status_callback({ "type": "llm_communication_status", "request_id": request_id_to_send, "llm_phase": execution_phase, "status": "started", "message": f"正在与智能大脑 ({self.model_name}) 沟通 ({execution_phase})..." })

        response = None
        try:
            start_time = time.monotonic()
            response = await asyncio.to_thread(self.client.chat.completions.create, **call_args)
            duration = time.monotonic() - start_time
            logger.info(f"[LLMInterface V1.0.0 Configurable] LLM 异步调用成功。耗时: {duration:.3f} 秒。")
            
            if status_callback:
                await status_callback({ "type": "llm_communication_status", "request_id": request_id_to_send, "llm_phase": execution_phase, "status": "completed", "message": f"与智能大脑 ({self.model_name}) 沟通完成 ({execution_phase})。", "details": {"duration_seconds": duration} })

            if response:
                # ... (response 处理和日志记录逻辑不变) ...
                if response.usage: logger.info(f"[LLMInterface V1.0.0 Configurable] Token 统计: Prompt={response.usage.prompt_tokens}, Completion={response.usage.completion_tokens}, Total={response.usage.total_tokens}")
                raw_llm_content = "" 
                if response.choices:
                    finish_reason = response.choices[0].finish_reason
                    logger.info(f"[LLMInterface V1.0.0 Configurable] 完成原因: {finish_reason}")
                    if finish_reason == 'length': logger.warning("[LLMInterface V1.0.0 Configurable] LLM 响应因达到最大 token 限制而被截断！")
                    if response.choices[0].message: raw_llm_content = response.choices[0].message.content or "" 
                    else: logger.warning("[LLMInterface V1.0.0 Configurable] LLM响应的choices[0]中缺少message对象。")
                else: logger.warning("[LLMInterface V1.0.0 Configurable] LLM 响应中缺少 'choices' 字段。")
                if self.enable_detailed_llm_message_logging and logger.isEnabledFor(logging.DEBUG): logger.debug(f"[LLMInterface V1.0.0 Configurable] [DETAILED_LOG] LLM 原始响应内容 (完整):\n{raw_llm_content}")
                elif logger.isEnabledFor(logging.DEBUG): logger.debug(f"[LLMInterface V1.0.0 Configurable] LLM 原始响应内容 (预览):\n{raw_llm_content[:1000]}{'...' if len(raw_llm_content) > 1000 else ''}")
            else:
                 logger.error("[LLMInterface V1.0.0 Configurable] LLM API 调用返回了 None！")
                 raise ConnectionError("LLM API call returned None.")
            return response 
        
        # --- 修改后的异常捕获 ---
        except Exception as e:
            # 先判断是否是 ZhipuAIAPIError (如果可用且是其实例)
            # ZhipuAIAPIError_AVAILABLE 标记在 __init__ 中设置会更好，或者直接在全局
            # 修正：我们将 ZhipuAIAPIError_AVAILABLE 的检查移到模块加载时
            # 这里我们假设 ZhipuAIAPIError 是从 zhipuai 导入的，如果导入失败，它会是我们定义的假类
            # 所以 isinstance(e, ZhipuAIAPIError) 会尝试匹配，如果匹配到我们自己定义的假的，那不是SDK的错。
            # 一个更可靠的方法是在 try-except ImportError 时设置一个布尔标志。
            # 我们在模块顶部导入 ZhipuAIAPIError 时，如果导入失败，就将一个标志 ZHIPUAIAPIERROR_IMPORTED 设置为 False。
            
            # 从模块顶部的导入逻辑获取 ZhipuAIAPIError 是否真的被导入
            zhipuai_api_error_type = None
            try:
                from zhipuai import ZhipuAIAPIError as ActualZhipuAIAPIError # 再次尝试导入
                zhipuai_api_error_type = ActualZhipuAIAPIError
            except ImportError:
                pass # zhipuai_api_error_type 保持为 None

            if zhipuai_api_error_type and isinstance(e, zhipuai_api_error_type): # type: ignore
                # 这是 ZhipuAI SDK 抛出的特定 API 错误
                # ZhipuAIAPIError 有 .code 和 .message 属性
                error_code_val = getattr(e, 'code', 'UNKNOWN_SDK_ERROR_CODE')
                error_message_val = getattr(e, 'message', str(e))
                logger.error(f"[LLMInterface V1.0.0 Configurable] ZhipuAI API 调用失败: Code={error_code_val}, Message='{error_message_val}'", exc_info=False) # exc_info=False 避免重复打印已知错误堆栈
                if status_callback:
                     await status_callback({
                        "type": "llm_communication_status", "request_id": request_id_to_send,
                        "llm_phase": execution_phase, "status": "error",
                        "message": f"与智能大脑沟通失败 ({execution_phase}): API错误 {error_code_val}",
                        "details": {"error": error_message_val, "error_type": type(e).__name__, "error_code_sdk": error_code_val}
                     })
                raise ConnectionError(f"ZhipuAI API Error: {error_message_val} (Code: {error_code_val})") from e
            elif isinstance(e, httpx.TimeoutException): # 捕获 httpx 的超时异常
                logger.error(f"[LLMInterface V1.0.0 Configurable] LLM API 调用超时 (配置超时: {self.api_timeout_seconds}s): {e}", exc_info=True)
                if status_callback:
                     await status_callback({
                        "type": "llm_communication_status", "request_id": request_id_to_send,
                        "llm_phase": execution_phase, "status": "error",
                        "message": f"与智能大脑沟通超时 ({execution_phase})。",
                        "details": {"error": str(e), "error_type": type(e).__name__}
                     })
                raise ConnectionError(f"LLM API call timed out after {self.api_timeout_seconds}s.") from e
            else: # 其他所有未知异常
                logger.error(f"[LLMInterface V1.0.0 Configurable] LLM API 异步调用发生未知失败: {e}", exc_info=True)
                if status_callback:
                     await status_callback({
                        "type": "llm_communication_status", "request_id": request_id_to_send,
                        "llm_phase": execution_phase, "status": "error",
                        "message": f"与智能大脑沟通时发生未知错误 ({execution_phase})。",
                        "details": {"error": str(e), "error_type": type(e).__name__}
                     })
                raise # 将原始异常或包装后的异常重新抛出