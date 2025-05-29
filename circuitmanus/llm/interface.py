# IDT_AGENT_NATIVE/circuitmanus/llm/interface.py
import time
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable

try:
    from zhipuai import ZhipuAI, ZhipuAIError
    ZHIPUAI_SDK_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning("无法导入 'zhipuai' SDK。智谱AI模型功能将不可用。")
    ZHIPUAI_SDK_AVAILABLE = False
    class ZhipuAI: pass
    class ZhipuAIAPIError(Exception): pass 

try:
    from openai import OpenAI, APIError as OpenAIApiError
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning("无法导入 'openai' SDK。DeepSeek 模型功能将不可用。")
    OPENAI_SDK_AVAILABLE = False
    class OpenAI: pass
    class OpenAIApiError(Exception): pass 

import httpx 

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..agent import CircuitAgent 

logger = logging.getLogger(__name__)

class LLMInterface:
    def __init__(self, 
                 agent_instance: 'CircuitAgent', 
                 default_temperature: float = 0.01, 
                 default_max_tokens: int = 8190,
                 api_timeout_seconds: int = 120, 
                 enable_detailed_llm_message_logging: bool = False 
                 ):
        
        self.agent_instance: 'CircuitAgent' = agent_instance
        self.config_loader = self.agent_instance.config_loader 
        
        self.default_temperature: float = self.config_loader.get_config("agent_settings.llm.default_temperature", default_temperature)
        self.default_max_tokens: int = self.config_loader.get_config("agent_settings.llm.default_max_tokens", default_max_tokens)
        self.api_timeout_seconds: float = float(self.config_loader.get_config("agent_settings.llm.api_timeout_seconds", api_timeout_seconds))
        self.enable_detailed_llm_message_logging: bool = self.config_loader.get_config("agent_settings.feature_flags.enable_detailed_llm_message_logging", enable_detailed_llm_message_logging)

        logger.info(f"[LLMInterface V1.1.1 DynamicAvailability] 初始化LLM接口。通用设置 - 温度: {self.default_temperature}, 最大Tokens: {self.default_max_tokens}, API超时: {self.api_timeout_seconds}s。")

        # 新增：用于存储各模型客户端的可用状态
        self.model_client_availability: Dict[str, bool] = {
            "zhipu-ai": False,
            "deepseek": False
            # 将来可以扩展更多模型
        }

        # 初始化 ZhipuAI 客户端
        self.zhipu_client: Optional[ZhipuAI] = None
        if ZHIPUAI_SDK_AVAILABLE:
            zhipu_api_key = self.agent_instance.api_key 
            if zhipu_api_key:
                try:
                    self.zhipu_client = ZhipuAI(api_key=zhipu_api_key, timeout=self.api_timeout_seconds) # type: ignore
                    logger.info(f"智谱AI客户端初始化成功 (Key: ...{zhipu_api_key[-4:] if len(zhipu_api_key) > 4 else '****'})。")
                    self.model_client_availability["zhipu-ai"] = True # 标记智谱客户端可用
                except Exception as e:
                    logger.error(f"初始化智谱AI客户端失败: {e}", exc_info=True)
            else:
                logger.warning("未找到ZHIPUAI_API_KEY，智谱AI模型将不可用。")
        
        # 初始化 DeepSeek (OpenAI) 客户端
        self.deepseek_client: Optional[OpenAI] = None
        if OPENAI_SDK_AVAILABLE:
            deepseek_api_key = self.config_loader.get_env_var("DEEPSEEK_API_KEY")
            deepseek_base_url = self.config_loader.get_config("agent_settings.llm.deepseek_settings.base_url", "https://api.deepseek.com/v1")
            if deepseek_api_key:
                try:
                    self.deepseek_client = OpenAI(api_key=deepseek_api_key, base_url=deepseek_base_url, timeout=self.api_timeout_seconds) # type: ignore
                    logger.info(f"DeepSeek客户端初始化成功 (Base URL: {deepseek_base_url}, Key: ...{deepseek_api_key[-4:] if len(deepseek_api_key) > 4 else '****'})。")
                    self.model_client_availability["deepseek"] = True # 标记DeepSeek客户端可用
                except Exception as e:
                    logger.error(f"初始化DeepSeek客户端失败: {e}", exc_info=True)
            else:
                logger.warning("未找到DEEPSEEK_API_KEY，DeepSeek模型将不可用。")

        if not any(self.model_client_availability.values()): # 检查是否有任何一个客户端可用
            logger.critical("LLMInterface: 没有任何LLM客户端成功初始化！Agent将无法调用任何大模型。")

    def get_model_availability(self) -> Dict[str, bool]:
        """新增方法：返回各模型客户端的可用状态。"""
        return self.model_client_availability

    async def call_llm(self, 
                       messages: List[Dict[str, Any]], 
                       execution_phase: str, 
                       status_callback: Optional[Callable[[Dict], Awaitable[None]]] = None,
                       selected_model_identifier: Optional[str] = None 
                       ) -> Any: 
        
        model_id_to_use = selected_model_identifier or self.config_loader.get_config("agent_settings.llm.default_model_identifier", "zhipu-ai")

        current_client: Any = None
        actual_model_name_for_api: Optional[str] = None
        is_deepseek_call = False

        if model_id_to_use == "zhipu-ai":
            if self.zhipu_client: # 检查客户端是否已初始化
                current_client = self.zhipu_client
                actual_model_name_for_api = self.config_loader.get_config("agent_settings.llm.zhipuai_settings.model_name", "glm-4") 
                logger.info(f"LLM调用将使用智谱AI模型: {actual_model_name_for_api}")
            else:
                logger.error("尝试使用智谱AI模型，但客户端未初始化。请检查API Key或SDK安装。")
                raise ConnectionError("智谱AI客户端未初始化或不可用。")
        elif model_id_to_use == "deepseek":
            if self.deepseek_client: # 检查客户端是否已初始化
                current_client = self.deepseek_client
                actual_model_name_for_api = self.config_loader.get_config("agent_settings.llm.deepseek_settings.model_name", "deepseek-chat")
                is_deepseek_call = True
                logger.info(f"LLM调用将使用DeepSeek模型: {actual_model_name_for_api}")
            else:
                logger.error("尝试使用DeepSeek模型，但客户端未初始化。请检查API Key或SDK安装。")
                raise ConnectionError("DeepSeek客户端未初始化或不可用。")
        else:
            logger.error(f"未知的模型标识符: '{model_id_to_use}'。无法选择LLM客户端。")
            raise ValueError(f"不支持的模型标识符: {model_id_to_use}")

        if not actual_model_name_for_api: 
            logger.error(f"未能确定用于API调用的实际模型名称 (标识符: {model_id_to_use})。")
            raise ValueError("无法确定API调用的模型名称。")

        call_args = {
            "model": actual_model_name_for_api,
            "messages": messages,
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens,
            "stream": False, 
        }

        logger.info(f"[LLMInterface V1.1.1] 准备异步调用 LLM ({actual_model_name_for_api}, 阶段: {execution_phase})...")
        if self.enable_detailed_llm_message_logging and logger.isEnabledFor(logging.DEBUG):
             try:
                 full_messages_json = json.dumps(messages, ensure_ascii=False, indent=2)
                 logger.debug(f"[LLMInterface V1.1.1] [DETAILED_LOG] 发送给 LLM 的完整消息列表 ({actual_model_name_for_api}):\n{full_messages_json}")
             except Exception as e_json_full:
                 logger.warning(f"[LLMInterface V1.1.1] 无法序列化完整消息列表进行详细调试日志: {e_json_full}")
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
                 logger.debug(f"[LLMInterface V1.1.1] 发送给 LLM 的消息列表 (预览, {actual_model_name_for_api}):\n{messages_summary}")
             except Exception as e_json_preview:
                 logger.warning(f"[LLMInterface V1.1.1] 无法序列化消息列表预览进行调试日志: {e_json_preview}")


        request_id_to_send = getattr(self.agent_instance, 'current_request_id', None)
        
        if status_callback:
            await status_callback({ "type": "llm_communication_status", "request_id": request_id_to_send, "llm_phase": execution_phase, "status": "started", "message": f"正在与智能大脑 ({actual_model_name_for_api}) 沟通 ({execution_phase})..." })

        response_from_sdk = None
        try:
            start_time = time.monotonic()
            response_from_sdk = await asyncio.to_thread(current_client.chat.completions.create, **call_args)
            duration = time.monotonic() - start_time
            logger.info(f"[LLMInterface V1.1.1] LLM ({actual_model_name_for_api}) 异步调用成功。耗时: {duration:.3f} 秒。")
            
            if status_callback:
                await status_callback({ "type": "llm_communication_status", "request_id": request_id_to_send, "llm_phase": execution_phase, "status": "completed", "message": f"与智能大脑 ({actual_model_name_for_api}) 沟通完成 ({execution_phase})。", "details": {"duration_seconds": duration} })

            if response_from_sdk:
                if hasattr(response_from_sdk, 'usage') and response_from_sdk.usage:
                    prompt_tokens = getattr(response_from_sdk.usage, 'prompt_tokens', 'N/A')
                    completion_tokens = getattr(response_from_sdk.usage, 'completion_tokens', 'N/A')
                    total_tokens = getattr(response_from_sdk.usage, 'total_tokens', 'N/A')
                    logger.info(f"[LLMInterface V1.1.1] Token 统计 ({actual_model_name_for_api}): Prompt={prompt_tokens}, Completion={completion_tokens}, Total={total_tokens}")

                raw_llm_content = "" 
                if hasattr(response_from_sdk, 'choices') and response_from_sdk.choices and len(response_from_sdk.choices) > 0:
                    first_choice = response_from_sdk.choices[0]
                    finish_reason = getattr(first_choice, 'finish_reason', 'N/A')
                    logger.info(f"[LLMInterface V1.1.1] 完成原因 ({actual_model_name_for_api}): {finish_reason}")
                    if finish_reason == 'length': 
                        logger.warning(f"[LLMInterface V1.1.1] LLM ({actual_model_name_for_api}) 响应因达到最大 token 限制而被截断！")
                    
                    if hasattr(first_choice, 'message') and first_choice.message:
                        raw_llm_content = getattr(first_choice.message, 'content', "") or ""
                    else:
                        logger.warning(f"[LLMInterface V1.1.1] LLM ({actual_model_name_for_api}) 响应的choices[0]中缺少message对象。")
                else: 
                    logger.warning(f"[LLMInterface V1.1.1] LLM ({actual_model_name_for_api}) 响应中缺少 'choices' 字段或choices为空。")

                if self.enable_detailed_llm_message_logging and logger.isEnabledFor(logging.DEBUG): 
                    logger.debug(f"[LLMInterface V1.1.1] [DETAILED_LOG] LLM ({actual_model_name_for_api}) 原始响应内容 (完整):\n{raw_llm_content}")
                elif logger.isEnabledFor(logging.DEBUG): 
                    logger.debug(f"[LLMInterface V1.1.1] LLM ({actual_model_name_for_api}) 原始响应内容 (预览):\n{raw_llm_content[:1000]}{'...' if len(raw_llm_content) > 1000 else ''}")
            else:
                 logger.error(f"[LLMInterface V1.1.1] LLM ({actual_model_name_for_api}) API 调用返回了 None！")
                 raise ConnectionError(f"LLM API ({actual_model_name_for_api}) 调用返回 None。")
            
            return response_from_sdk 
        
        except Exception as e:
            error_type_name = type(e).__name__
            error_message_str = str(e)
            error_details_for_cb = {"error": error_message_str, "error_type": error_type_name}
            
            if is_deepseek_call and OPENAI_SDK_AVAILABLE and isinstance(e, OpenAIApiError):
                status_code = getattr(e, 'status_code', 'N/A_SDK_STATUS_CODE')
                sdk_error_code = getattr(e, 'code', 'N/A_SDK_ERROR_CODE') 
                sdk_error_type = getattr(e, 'type', 'N/A_SDK_ERROR_TYPE') 
                logger.error(f"[LLMInterface V1.1.1] DeepSeek API ({actual_model_name_for_api}) 调用失败: "
                             f"HTTP Status={status_code}, SDK Error Type='{sdk_error_type}', SDK Code='{sdk_error_code}', Message='{error_message_str}'", 
                             exc_info=False) 
                error_details_for_cb.update({"sdk_error_code": sdk_error_code, "sdk_error_type": sdk_error_type, "http_status": status_code})
                if sdk_error_type in ['api_connection_error', 'internal_error', 'rate_limit_error']: 
                    raise ConnectionError(f"DeepSeek API Error ({sdk_error_type} - {sdk_error_code}): {error_message_str}") from e
                else: 
                    raise 
            elif not is_deepseek_call and ZHIPUAI_SDK_AVAILABLE and isinstance(e, ZhipuAIAPIError):
                error_code_val = getattr(e, 'code', 'UNKNOWN_ZHIPU_SDK_ERROR_CODE')
                logger.error(f"[LLMInterface V1.1.1] ZhipuAI API ({actual_model_name_for_api}) 调用失败: "
                             f"Code={error_code_val}, Message='{error_message_str}'", 
                             exc_info=False)
                error_details_for_cb.update({"sdk_error_code_zhipu": error_code_val})
                raise ConnectionError(f"ZhipuAI API Error (Code: {error_code_val}): {error_message_str}") from e
            elif isinstance(e, httpx.TimeoutException): 
                logger.error(f"[LLMInterface V1.1.1] LLM API ({actual_model_name_for_api}) 调用超时 (配置超时: {self.api_timeout_seconds}s): {error_message_str}", exc_info=True)
                raise ConnectionError(f"LLM API ({actual_model_name_for_api}) 调用在 {self.api_timeout_seconds}s 后超时。") from e
            elif isinstance(e, ConnectionError): 
                logger.error(f"[LLMInterface V1.1.1] LLM API ({actual_model_name_for_api}) 发生连接错误: {error_message_str}", exc_info=True)
                raise
            else: 
                logger.error(f"[LLMInterface V1.1.1] LLM API ({actual_model_name_for_api}) 异步调用发生未知失败: {error_message_str}", exc_info=True)
                raise RuntimeError(f"LLM调用 ({actual_model_name_for_api}) 期间发生未知错误: {error_message_str}") from e
            
            # 此处 status_callback 的调用实际上在 raise 之后不会执行，正确的做法是在每个 raise 之前调用
            # 但为了保持逻辑结构，如果需要，可以在每个raise之前添加status_callback调用
            # if status_callback:
            #      await status_callback({ ... })
