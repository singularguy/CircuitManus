# IDT_AGENT_NATIVE/circuitmanus/agent.py
import os
import sys 
import json
import time
import inspect 
import logging
import asyncio
import traceback
import functools 
from uuid import uuid4
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Callable, Awaitable

from .utils.config_loader import ConfigLoader 
from .utils.logging_config import setup_logging 
from .memory.manager import MemoryManager 
from .llm.interface import LLMInterface   
from .llm.parser import OutputParser      
from .tools.base import register_tool     
from .tools.executor import ToolExecutor  
from .tools import circuit_ops            
from .tools import web_search             
from .prompts.templates import (          
    get_tool_schemas_for_prompt,
    get_planning_prompt,
    get_response_generation_prompt
)

class CircuitAgent:
    def __init__(self, 
                 config_yaml_path: str = "config.yaml", 
                 dotenv_path: Optional[str] = None
                 ):
        self.config_loader = ConfigLoader(yaml_config_path=config_yaml_path, dotenv_path=dotenv_path)
        self.api_key: str = self.config_loader.get_env_var("ZHIPUAI_API_KEY", "") 
        # ZhipuAI API Key 的检查逻辑保持，因为它是核心功能之一
        # DeepSeek Key 的检查将在下面模型可用性判断中进行

        self.current_request_id: Optional[str] = None 

        log_level_console_str: str = self.config_loader.get_config("agent_settings.logging.log_level_console", "INFO")
        log_level_file_str: str = self.config_loader.get_config("agent_settings.logging.log_level_file", "DEBUG")
        log_dir_cfg: Optional[str] = self.config_loader.get_config("agent_settings.logging.log_dir", None) 
        self.verbose_mode: bool = (log_level_console_str.upper() == "DEBUG")
        console_level_int = getattr(logging, log_level_console_str.upper(), logging.INFO)
        file_level_int = getattr(logging, log_level_file_str.upper(), logging.DEBUG)
        self.logger = setup_logging(
            console_log_level=console_level_int,
            file_log_level=file_level_int,
            log_dir_override=log_dir_cfg
        )
        
        self.default_llm_identifier: str = self.config_loader.get_config("agent_settings.llm.default_model_identifier", "zhipu-ai")
        self.default_enable_chinese_thinking: bool = self.config_loader.get_config("agent_settings.prompts.enable_deep_thinking_chinese_default", False)
        self.current_llm_identifier: str = self.default_llm_identifier
        self.current_enable_chinese_thinking: bool = self.default_enable_chinese_thinking

        # 【新增】判断并存储各模型可用性
        self.model_availability_details: List[Dict[str, Any]] = []
        configured_llm_identifiers = self.config_loader.get_config("agent_settings.llm.available_models", [])
        
        for model_id in configured_llm_identifiers:
            is_available = False
            display_name = model_id # 默认显示名称
            if model_id == "zhipu-ai":
                is_available = bool(self.api_key) # ZHIPUAI_API_KEY 存储在 self.api_key
                display_name = "智谱清言 (GLM)"
                if not is_available:
                    self.logger.warning("智谱AI API Key未配置，智谱模型将不可用。")
            elif model_id == "deepseek":
                deepseek_key = self.config_loader.get_env_var("DEEPSEEK_API_KEY")
                is_available = bool(deepseek_key)
                display_name = "DeepSeek 大模型"
                if not is_available:
                    self.logger.warning("DeepSeek API Key未配置，DeepSeek模型将不可用。")
            # 可以为未来其他模型添加类似的检查逻辑
            # else:
            #     self.logger.warning(f"配置文件中存在未知模型标识符 '{model_id}'，其可用性检查未实现。")

            self.model_availability_details.append({
                "id": model_id,
                "name": display_name, # 前端将使用这个名字作为选项文本
                "available": is_available
            })

        self.logger.info(f"\n{'='*30} CircuitAgent 初始化开始 (V1.1.1 - 动态模型可用性) {'='*30}")
        self.logger.info(f"Agent配置已从 '{os.path.abspath(config_yaml_path)}' 和 .env (如果存在) 加载。")
        self.logger.info(f"Agent verbose_mode (推导自 console_log_level='{log_level_console_str}'): {self.verbose_mode}")
        self.logger.info(f"默认LLM标识符: '{self.default_llm_identifier}', 默认中文深度思考: {self.default_enable_chinese_thinking}")
        self.logger.info(f"模型可用性详情: {json.dumps(self.model_availability_details, ensure_ascii=False)}")


        self.tools_registry: Dict[str, Dict[str, Any]] = {}
        self.logger.info("[Agent Init] 正在动态发现并注册工具...")
        tool_modules = [circuit_ops, web_search] 
        for module in tool_modules:
            for name, func in inspect.getmembers(module, inspect.isfunction):
                if hasattr(func, '_is_tool') and func._is_tool:
                    schema = getattr(func, '_tool_schema', None) 
                    if schema and isinstance(schema, dict) and 'description' in schema and 'parameters' in schema:
                        if inspect.iscoroutinefunction(func): 
                            async def async_bound_method_wrapper(arguments: Dict[str, Any], agent_self=self, original_func=func):
                                return await original_func(agent_self, arguments)
                            functools.update_wrapper(async_bound_method_wrapper, func) 
                            setattr(self, name, async_bound_method_wrapper) 
                        else: 
                            bound_method = functools.partial(func, self) 
                            functools.update_wrapper(bound_method, func) 
                            setattr(self, name, bound_method) 
                        self.tools_registry[name] = schema 
                        is_async_tool = inspect.iscoroutinefunction(func) 
                        self.logger.info(f"[Agent Init] ✓ 已动态绑定并注册工具: '{name}' (来自模块: {module.__name__}, 原始是否异步: {is_async_tool})。")
                    else:
                        self.logger.warning(f"[Agent Init] 在模块 {module.__name__} 中发现函数 '{name}' 被标记为工具,但其 Schema 结构不完整或无效,已跳过注册。")
        
        if not self.tools_registry:
            self.logger.warning("[Agent Init] 未发现任何通过 @register_tool 注册的工具！Agent 功能将受限。")
        else:
            self.logger.info(f"[Agent Init] 共动态绑定并注册了 {len(self.tools_registry)} 个工具。")
            if self.logger.isEnabledFor(logging.DEBUG):
                try:
                    self.logger.debug(f"[Agent Init] 工具注册表详情:\n{json.dumps(self.tools_registry, indent=2, ensure_ascii=False)}")
                except Exception as e_dump:
                    self.logger.debug(f"无法序列化工具注册表进行日志记录: {e_dump}")


        try:
            max_short_term = self.config_loader.get_config("agent_settings.memory.max_short_term_items", 30)
            max_long_term = self.config_loader.get_config("agent_settings.memory.max_long_term_items", 75)
            self.memory_manager = MemoryManager(max_short_term_items=max_short_term, max_long_term_items=max_long_term)

            self.llm_interface = LLMInterface(agent_instance=self)

            self.output_parser = OutputParser(agent_tools_registry=self.tools_registry)

            tool_retries_cfg = self.config_loader.get_config("agent_settings.tools.max_tool_retries", 1)
            tool_delay_cfg = self.config_loader.get_config("agent_settings.tools.tool_retry_delay_seconds", 1.0)
            self.tool_executor = ToolExecutor(
                agent_instance=self, 
                max_tool_retries=tool_retries_cfg,
                tool_retry_delay_seconds=tool_delay_cfg
            )
        except (ValueError, ConnectionError, TypeError) as e: 
            self.logger.critical(f"[Agent Init] 核心模块实例化失败: {e}", exc_info=True)
            raise 

        self.planning_llm_retries: int = self.config_loader.get_config("agent_settings.llm.planning_llm_retries", 3)
        self.response_generation_llm_retries: int = self.config_loader.get_config("agent_settings.llm.response_generation_llm_retries", 1)
        self.max_replanning_attempts: int = self.config_loader.get_config("agent_settings.orchestration.max_replanning_attempts", 2)
        
        self.logger.info(f"[Agent Init] LLM规划重试: {self.planning_llm_retries}, LLM响应生成重试: {self.response_generation_llm_retries}, 工具执行重试: {tool_retries_cfg}, 最大重规划尝试: {self.max_replanning_attempts}。")
        self.logger.info(f"\n{'='*30} CircuitAgent 初始化成功 (V1.1.1 - 动态模型可用性) {'='*30}\n") # 版本号微调

    async def process_user_request(self, 
                                 user_request: str, 
                                 status_callback: Callable[[Dict[str, Any]], Awaitable[None]],
                                 selected_llm_identifier_from_frontend: Optional[str] = None,
                                 enable_chinese_thinking_from_frontend: Optional[bool] = None
                                 ) -> None:
        request_start_time = time.monotonic()
        self.current_request_id = f"req_{str(uuid4())[:12]}" 

        final_llm_camelcase_json_for_reply: Optional[Dict[str, Any]] = None
        final_reply_for_user: str = self.config_loader.get_config(
            "agent_settings.general.default_user_facing_error_message", 
            "抱歉,处理您的请求时发生未知错误。" 
        )
        final_llm_interaction_id_for_user: Optional[str] = None
        active_llm_interaction_id: Optional[str] = None 

        # --- 更新当前请求使用的模型和中文思考设置 ---
        # 1. 模型选择
        if selected_llm_identifier_from_frontend:
            # 检查前端传来的模型是否在Agent的可用模型列表(基于API Key配置)中实际可用
            is_selected_model_actually_available = False
            for model_detail in self.model_availability_details:
                if model_detail["id"] == selected_llm_identifier_from_frontend and model_detail["available"]:
                    is_selected_model_actually_available = True
                    break
            if is_selected_model_actually_available:
                self.current_llm_identifier = selected_llm_identifier_from_frontend
            else:
                self.logger.warning(f"前端请求使用模型 '{selected_llm_identifier_from_frontend}'，但该模型当前不可用 (API Key可能未配置)。将回退到默认模型 '{self.default_llm_identifier}'。")
                self.current_llm_identifier = self.default_llm_identifier
                # 可以通过 status_callback 通知前端模型选择被覆盖
                await status_callback({
                    "type": "general_status", "request_id": self.current_request_id,
                    "stage": "llm_selection_override", "status": "warning",
                    "message": f"您选择的模型 '{selected_llm_identifier_from_frontend}' 当前不可用，已自动切换到默认模型 '{self.current_llm_identifier}'。",
                    "details": {"requested_model": selected_llm_identifier_from_frontend, "used_model": self.current_llm_identifier}
                })
        else:
            self.current_llm_identifier = self.default_llm_identifier
        
        # 2. 中文深度思考设置
        globally_enabled_chinese_thinking = self.config_loader.get_config("agent_settings.feature_flags.enable_chinese_deep_thinking_globally", True)
        if not globally_enabled_chinese_thinking:
            self.current_enable_chinese_thinking = False 
            self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 深度中文思考功能全局禁用。")
        elif enable_chinese_thinking_from_frontend is not None:
            self.current_enable_chinese_thinking = enable_chinese_thinking_from_frontend
        else:
            self.current_enable_chinese_thinking = self.default_enable_chinese_thinking
        # --- 模型和中文思考设置更新完毕 ---


        self.logger.info(f"\n{'='*25} CircuitAgent 开始处理用户请求 (ReqID: {self.current_request_id}) {'='*25}")
        self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 使用模型: '{self.current_llm_identifier}', 启用中文深度思考: {self.current_enable_chinese_thinking}")
        self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 收到用户指令 (预览): \"{user_request[:200]}{'...' if len(user_request)>200 else ''}\"")

        # ... (后续的 process_user_request 逻辑与上一版本 Agent.py 中基本一致，此处不再重复，
        #    关键在于 get_planning_prompt, get_response_generation_prompt, 和 llm_interface.call_llm
        #    现在会使用 self.current_llm_identifier 和 self.current_enable_chinese_thinking) ...
        # --- START OF ORCHESTRATION LOGIC (Copied and checked for new param usage) ---
        try:
            max_input_len = self.config_loader.get_config("agent_settings.security.max_input_length_user_request", 10000)
            if len(user_request) > max_input_len:
                original_length = len(user_request)
                user_request_truncated = user_request[:max_input_len]
                self.logger.warning(f"[Orchestrator - ReqID:{self.current_request_id}] 用户指令过长 (原始长度: {original_length}, 上限: {max_input_len})。已截断为: \"{user_request_truncated[:50]}...\"")
                user_request = user_request_truncated 
                await status_callback({ "type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "warning", "message": f"您的输入内容过长(原始长度{original_length}), 已被自动截断为{max_input_len}字符进行处理。", "details": {"original_length": original_length, "truncated_length": max_input_len} })

            if not user_request or user_request.strip() == "": 
                self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 用户指令为空或无效。")
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "ignored", "message": "用户输入为空或无效,已忽略。"})
                empty_input_err_json = { "requestId": self.current_request_id, "llmInteractionId": f"agent_input_err_{str(uuid4())[:6]}", "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure", "errorDetails": { "errorType": "USER_INPUT_ERROR", "errorCode": "EMPTY_OR_INVALID_USER_REQUEST", "messageToUser": "您的指令似乎是空的或无效的,请重新输入！", "technicalMessage": "User request was empty or whitespace.", "isDirectLlmFailure": False }, "executionPhase": "planning", "thoughtProcess": "Agent检测到用户输入为空或无效,无需进一步处理。", "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content": "您的指令似乎是空的或无效的,请重新输入！"}}}
                await status_callback({ "type": "final_response", "request_id": self.current_request_id, "llm_interaction_id": empty_input_err_json["llmInteractionId"], "content": empty_input_err_json["decision"]["responseToUser"]["content"], "final_camelcase_json_if_success": None })
                return

            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "received", "message": "收到用户指令,开始处理...", "details": {"user_request_preview": user_request[:1000]}})
            
            try: 
                self.memory_manager.add_to_short_term({"role": "user", "content": user_request})
            except Exception as e_mem_user:
                self.logger.error(f"[Orchestrator - ReqID:{self.current_request_id}] 添加用户消息到短期记忆时出错: {e_mem_user}", exc_info=True)
                err_msg_mem = f"记录用户指令时发生内部记忆错误: {e_mem_user}"
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "error", "message": err_msg_mem})
                mem_err_json = { "requestId": self.current_request_id, "llmInteractionId": f"agent_mem_err_{str(uuid4())[:6]}", "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure", "errorDetails": {"errorType": "INTERNAL_AGENT_ERROR", "errorCode": "MEMORY_ADD_USER_MSG_FAILED", "messageToUser": f"抱歉,我在记录您的指令时遇到了内部问题 ({e_mem_user})！请稍后重试。", "technicalMessage": err_msg_mem, "isDirectLlmFailure": False }, "executionPhase": "planning", "thoughtProcess": "Agent在将用户消息添加到短期记忆时遇到错误。", "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content": f"抱歉,我在记录您的指令时遇到了内部问题 ({e_mem_user})！请稍后重试。" }}}
                await status_callback({"type": "final_response", "request_id": self.current_request_id, "llm_interaction_id": mem_err_json["llmInteractionId"], "content": mem_err_json["decision"]["responseToUser"]["content"], "final_camelcase_json_if_success": None})
                return

            replanning_loop_count = 0
            current_llm_plan_camelcase_json_obj: Optional[Dict[str, Any]] = None
            agent_accepted_latest_plan_for_action = False 
            tool_execution_results_for_llm_history: List[Dict[str, Any]] = [] # 确保在循环外定义

            while replanning_loop_count <= self.max_replanning_attempts:
                current_planning_attempt_num = replanning_loop_count + 1
                log_prefix = f"[Orchestrator - PlanAttempt {current_planning_attempt_num} - ReqID: {self.current_request_id}]"
                self.logger.info(f"\n--- {log_prefix} 开始 ---")

                is_currently_replanning = (replanning_loop_count > 0)
                status_msg_planning_start = "正在分析指令并制定计划..." if not is_currently_replanning else f"正在尝试第 {replanning_loop_count +1 }/{self.max_replanning_attempts +1} 次重规划..." 
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "started", "message": status_msg_planning_start, "details": {"attempt_number": current_planning_attempt_num, "max_replanning_attempts": self.max_replanning_attempts}})

                recent_long_term_for_prompt = self.config_loader.get_config("agent_settings.memory.recent_long_term_count_for_prompt", 7)
                memory_context = self.memory_manager.get_memory_context_for_prompt(recent_long_term_count=recent_long_term_for_prompt)
                tool_schemas_for_llm = get_tool_schemas_for_prompt(self.tools_registry)
                
                system_prompt_planning = get_planning_prompt(
                    tool_schemas_desc=tool_schemas_for_llm, 
                    memory_context=memory_context, 
                    is_replanning=is_currently_replanning, 
                    request_id=self.current_request_id,
                    enable_deep_thinking_chinese=self.current_enable_chinese_thinking 
                )
                messages_for_planning = [{"role": "system", "content": system_prompt_planning}] + self.memory_manager.short_term

                llm_call_attempt_inner = 0 
                parsed_plan_camelcase_json_this_llm_call: Optional[Dict[str, Any]] = None
                parser_error_msg_this_llm_call: str = ""
                parsed_failed_validation_points_this_llm_call: List[Dict[str,str]] = []
                agent_accepted_latest_plan_for_action = False 

                while llm_call_attempt_inner <= self.planning_llm_retries: 
                    self.logger.info(f"{log_prefix} 调用规划 LLM (模型: {self.current_llm_identifier}, LLM Call Attempt {llm_call_attempt_inner + 1} of {self.planning_llm_retries + 1})...")
                    try:
                        llm_response_planning_raw = await self.llm_interface.call_llm( 
                            messages=messages_for_planning, 
                            execution_phase="planning", 
                            status_callback=status_callback,
                            selected_model_identifier=self.current_llm_identifier 
                        )
                        if not llm_response_planning_raw or not hasattr(llm_response_planning_raw, 'choices') or not llm_response_planning_raw.choices: 
                            raise ConnectionError("LLM规划响应无效或缺少choices。")
                        
                        llm_msg_obj_planning = llm_response_planning_raw.choices[0].message
                        
                        parsed_plan_camelcase_json_this_llm_call, parser_error_msg_this_llm_call, parsed_failed_validation_points_this_llm_call = \
                            self.output_parser.parse_llm_response_to_structured_json(llm_msg_obj_planning, "planning")

                        if parsed_plan_camelcase_json_this_llm_call:
                            active_llm_interaction_id = parsed_plan_camelcase_json_this_llm_call.get("llmInteractionId")
                            current_thought_process = parsed_plan_camelcase_json_this_llm_call.get("thoughtProcess")
                            if current_thought_process: await status_callback({"type": "thinking_log", "request_id": self.current_request_id, "llm_interaction_id": active_llm_interaction_id, "stage": "planning", "content": current_thought_process})

                        if parsed_plan_camelcase_json_this_llm_call and not parser_error_msg_this_llm_call and not parsed_failed_validation_points_this_llm_call:
                            if parsed_plan_camelcase_json_this_llm_call.get("status") == "success":
                                self.logger.info(f"{log_prefix} 规划LLM调用成功且响应有效 (LLM_ID: {active_llm_interaction_id})。Agent采纳此计划。")
                                agent_accepted_latest_plan_for_action = True
                            elif is_currently_replanning and parsed_plan_camelcase_json_this_llm_call.get("decision", {}).get("isCallTools") is True and \
                                 isinstance(parsed_plan_camelcase_json_this_llm_call.get("decision", {}).get("toolCallRequests"), list) and \
                                 parsed_plan_camelcase_json_this_llm_call.get("decision", {}).get("toolCallRequests"): 
                                self.logger.warning(f"{log_prefix} LLM在重规划时提供了新工具计划但顶层status为failure (LLM_ID: {active_llm_interaction_id})。Agent审慎采纳。错误: {parsed_plan_camelcase_json_this_llm_call.get('errorDetails')}")
                                agent_accepted_latest_plan_for_action = True 
                            else: 
                                error_detail_from_llm = parsed_plan_camelcase_json_this_llm_call.get("errorDetails", {}).get("technicalMessage", "LLM规划指示内部错误。")
                                self.logger.warning(f"{log_prefix} LLM报告规划状态为 'failure': {error_detail_from_llm} (LLM_ID: {active_llm_interaction_id})。不采纳，尝试让LLM修正。")
                                parser_error_msg_this_llm_call = f"LLM主动报告规划失败: {error_detail_from_llm}" 

                            if agent_accepted_latest_plan_for_action:
                                current_llm_plan_camelcase_json_obj = parsed_plan_camelcase_json_this_llm_call
                                try: 
                                    if hasattr(llm_msg_obj_planning, 'model_dump'):
                                        self.memory_manager.add_to_short_term(llm_msg_obj_planning.model_dump(exclude_unset=True))
                                    elif isinstance(llm_msg_obj_planning, dict):
                                         self.memory_manager.add_to_short_term(llm_msg_obj_planning)
                                    else: 
                                        self.memory_manager.add_to_short_term(llm_msg_obj_planning.dict(exclude_unset=True)) # type: ignore
                                except AttributeError as e_attr:
                                    self.logger.error(f"{log_prefix} 添加LLM规划响应到记忆时，message对象缺少model_dump或dict方法: {e_attr}。对象类型: {type(llm_msg_obj_planning)}")
                                except Exception as e_mem_add: 
                                    self.logger.error(f"{log_prefix} 添加LLM规划响应到记忆失败: {e_mem_add}")
                                break 
                        if not agent_accepted_latest_plan_for_action and llm_call_attempt_inner < self.planning_llm_retries:
                            error_to_report_cb = parser_error_msg_this_llm_call or "V1.0.0结构或内容校验失败。"
                            if parsed_failed_validation_points_this_llm_call: error_to_report_cb += " 失败点(部分): " + json.dumps(parsed_failed_validation_points_this_llm_call[:2], ensure_ascii=False) 
                            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "llm_retry_needed", "message": f"大脑计划处理遇问题,尝试重沟通 ({error_to_report_cb[:1000]})", "details": {"llm_call_attempt": llm_call_attempt_inner + 1}})
                            if parsed_plan_camelcase_json_this_llm_call and parsed_plan_camelcase_json_this_llm_call.get("status") == "failure":
                                try: 
                                    if hasattr(llm_msg_obj_planning, 'model_dump'):
                                        self.memory_manager.add_to_short_term(llm_msg_obj_planning.model_dump(exclude_unset=True))
                                    elif isinstance(llm_msg_obj_planning, dict):
                                        self.memory_manager.add_to_short_term(llm_msg_obj_planning)
                                    else:
                                        self.memory_manager.add_to_short_term(llm_msg_obj_planning.dict(exclude_unset=True)) # type: ignore
                                except AttributeError as e_attr:
                                     self.logger.error(f"{log_prefix} 添加LLM失败规划到记忆时，message对象缺少model_dump或dict方法: {e_attr}。")
                                except Exception as e_mem_add_fail: self.logger.error(f"{log_prefix} 添加LLM失败规划到记忆失败: {e_mem_add_fail}")
                            elif parser_error_msg_this_llm_call or parsed_failed_validation_points_this_llm_call:
                                 sim_err_plan_content = { "requestId": self.current_request_id, "llmInteractionId": f"agent_parser_err_{active_llm_interaction_id or str(uuid4())[:6]}", "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure", "errorDetails": { "errorType": "LLM_OUTPUT_VALIDATION_ERROR", "errorCode": "V1_CAMELCASE_JSON_VALIDATION_FAILED_BY_AGENT", "technicalMessage": parser_error_msg_this_llm_call or "Agent端JSON校验失败。", "isDirectLlmFailure": False, "failedValidationPoints": parsed_failed_validation_points_this_llm_call }, "executionPhase": "planning", "thoughtProcess": "Agent在解析或验证LLM上一次规划输出时发现以下问题,将请求LLM修正。", "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content":""}}}
                                 try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(sim_err_plan_content, ensure_ascii=False)})
                                 except Exception as e_mem_add_parse_err: self.logger.error(f"{log_prefix} 添加Agent解析错误到记忆失败: {e_mem_add_parse_err}")
                    except Exception as e_llm_call_level: 
                        self.logger.error(f"{log_prefix} LLM调用或规划解析时发生严重错误 (LLM Call Attempt {llm_call_attempt_inner + 1}): {e_llm_call_level}", exc_info=True)
                        parser_error_msg_this_llm_call = f"LLM调用/解析严重错误: {str(e_llm_call_level)[:1000]}"
                        parsed_failed_validation_points_this_llm_call = [{"jsonPath":"root.llmCallOrParse", "issue_description": parser_error_msg_this_llm_call}]
                        if llm_call_attempt_inner < self.planning_llm_retries: await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "llm_error_retrying", "message": f"与大脑沟通时发生严重错误,尝试重新连接 ({parser_error_msg_this_llm_call})", "details": {"llm_call_attempt": llm_call_attempt_inner + 1}})
                    llm_call_attempt_inner += 1
                    if agent_accepted_latest_plan_for_action: break 
                
                if not agent_accepted_latest_plan_for_action: 
                    error_summary_final_planning_llm_attempt = parser_error_msg_this_llm_call or "在多次LLM调用尝试后,未能从LLM获取可接受的规划。"
                    if parsed_failed_validation_points_this_llm_call: error_summary_final_planning_llm_attempt += " 最后一次校验失败点(部分): " + json.dumps(parsed_failed_validation_points_this_llm_call[:2], ensure_ascii=False)
                    await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "failed_after_llm_retries", "message": f"规划失败: {error_summary_final_planning_llm_attempt[:1000]}", "details": {"final_parser_error": parser_error_msg_this_llm_call, "final_validation_failures_count": len(parsed_failed_validation_points_this_llm_call), "thinking_log_from_last_attempt": parsed_plan_camelcase_json_this_llm_call.get("thoughtProcess") if parsed_plan_camelcase_json_this_llm_call else "N/A"}})
                    if replanning_loop_count >= self.max_replanning_attempts: 
                        self.logger.critical(f"{log_prefix} 已达最大重规划尝试次数,且本次规划最终失败。中止。")
                        final_reply_for_user = f"抱歉,多次尝试后未能为您的请求 '{user_request[:50]}...' 制定有效计划。错误: {error_summary_final_planning_llm_attempt[:500]}"
                        final_llm_interaction_id_for_user = active_llm_interaction_id or f"error_max_replan_{str(uuid4())[:6]}"
                        final_llm_camelcase_json_for_reply = None; break 
                    else: 
                        sim_fail_plan_content_for_replan = { "requestId": self.current_request_id, "llmInteractionId": f"agent_replan_trigger_{active_llm_interaction_id or str(uuid4())[:6]}", "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure", "errorDetails": {"errorType": "LLM_OUTPUT_VALIDATION_ERROR", "errorCode": "PLAN_VALIDATION_FAILED_IN_ATTEMPT", "technicalMessage": error_summary_final_planning_llm_attempt, "isDirectLlmFailure": False, "failedValidationPoints": parsed_failed_validation_points_this_llm_call }, "executionPhase": "planning", "thoughtProcess": f"Agent在第 {current_planning_attempt_num} 次规划尝试失败,将重规划。错误: {error_summary_final_planning_llm_attempt}", "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content":""}}}
                        try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(sim_fail_plan_content_for_replan, ensure_ascii=False)})
                        except Exception as e_mem_add_replan_trigger: self.logger.error(f"{log_prefix} 添加重规划触发信息到记忆出错: {e_mem_add_replan_trigger}")
                        replanning_loop_count += 1; continue 

                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "completed_and_validated", "message": "规划完成,准备执行或直接回复。", "details": {"plan_llm_id": current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else None}})
                
                tool_requests_from_plan = current_llm_plan_camelcase_json_obj.get("decision", {}).get("toolCallRequests", []) if current_llm_plan_camelcase_json_obj else []
                if isinstance(tool_requests_from_plan, list) and current_llm_plan_camelcase_json_obj and current_llm_plan_camelcase_json_obj.get("decision",{}).get("isCallTools") is True:
                    plan_details_for_ui = []
                    for req_idx, tool_req_in_plan in enumerate(tool_requests_from_plan): plan_details_for_ui.append({ "tool_call_id": tool_req_in_plan.get("toolCallId"), "tool_name": tool_req_in_plan.get("toolName"), "tool_arguments": tool_req_in_plan.get("toolArguments", {}), "ui_hints": tool_req_in_plan.get("uiHints", {}), "status": "pending", "order": req_idx + 1 })
                    await status_callback({ "type": "plan_details", "request_id": self.current_request_id, "llm_interaction_id": current_llm_plan_camelcase_json_obj.get("llmInteractionId"), "plan": plan_details_for_ui })
                
                decision_from_plan = current_llm_plan_camelcase_json_obj.get("decision", {}) if current_llm_plan_camelcase_json_obj else {}
                should_call_tools = decision_from_plan.get("isCallTools", False) 
                response_user_obj_from_plan = decision_from_plan.get("responseToUser")
                # tool_execution_results_for_llm_history: List[Dict[str, Any]] = [] # 已移到循环外

                if should_call_tools: 
                    tool_count_in_plan = len(tool_requests_from_plan) if isinstance(tool_requests_from_plan, list) else 0
                    self.logger.info(f"{log_prefix} 决策: 执行 {tool_count_in_plan} 个工具。")
                    await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "action_execution", "status": "started", "message": f"开始执行 {tool_count_in_plan} 个操作...", "details": {"tool_count": tool_count_in_plan}})
                    if isinstance(response_user_obj_from_plan, dict) and response_user_obj_from_plan.get("content","").strip():
                        transitional_reply_content = response_user_obj_from_plan["content"]
                        await status_callback({"type": "interim_response", "request_id": self.current_request_id, "llm_interaction_id": current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else None, "content": transitional_reply_content})
                    if not isinstance(tool_requests_from_plan, list) or not tool_requests_from_plan:
                        err_msg_list_tools_critical = "内部规划错误: isCallTools为True但toolCallRequests无效或为空。"
                        self.logger.error(f"{log_prefix} {err_msg_list_tools_critical}")
                        tool_execution_results_for_llm_history = [{"role":"tool", "tool_call_id":f"plan_integrity_err_{str(uuid4())[:6]}", "name":"plan_integrity_checker", "content":json.dumps({"status":"failure", "message":err_msg_list_tools_critical, "error": {"error_type":"INTERNAL_AGENT_ERROR", "error_code":"INVALID_TOOL_REQUEST_LIST", "technical_message": err_msg_list_tools_critical}})}]
                        try: self.memory_manager.add_to_short_term(tool_execution_results_for_llm_history[0])
                        except Exception as e_mem_add_integrity_err: self.logger.error(f"{log_prefix} 添加规划完整性错误到记忆失败: {e_mem_add_integrity_err}")
                        if replanning_loop_count >= self.max_replanning_attempts: final_reply_for_user = f"抱歉,系统准备执行操作时遇内部问题: {err_msg_list_tools_critical}"; final_llm_interaction_id_for_user = current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id; final_llm_camelcase_json_for_reply = None; break 
                        else: replanning_loop_count += 1; continue
                    
                    current_tool_exec_results_for_llm_hist = await self.tool_executor.execute_tool_calls( tool_requests_from_plan, status_callback )
                    tool_execution_results_for_llm_history.extend(current_tool_exec_results_for_llm_hist) 
                    
                    if tool_execution_results_for_llm_history: 
                        for res_msg_tool in tool_execution_results_for_llm_history:
                            try: self.memory_manager.add_to_short_term(res_msg_tool)
                            except Exception as e_mem_add_tool_res: self.logger.error(f"{log_prefix} 添加工具结果 {res_msg_tool.get('tool_call_id')} 到记忆失败: {e_mem_add_tool_res}")
                    
                    any_tool_failed_persistently = False; last_failed_tool_message_for_user = "一个或多个操作未能成功完成。" 
                    if tool_execution_results_for_llm_history:
                        for tool_res_for_hist in tool_execution_results_for_llm_history:
                            try:
                                tool_res_content_dict = json.loads(tool_res_for_hist.get("content","{}"))
                                if tool_res_content_dict.get("status") != "success": any_tool_failed_persistently = True; last_failed_tool_message_for_user = tool_res_content_dict.get("message", last_failed_tool_message_for_user)
                            except json.JSONDecodeError: self.logger.error(f"{log_prefix} 无法解析工具结果JSON: {str(tool_res_for_hist.get('content'))[:200]}"); any_tool_failed_persistently = True; last_failed_tool_message_for_user = "一个操作的结果格式不正确。"
                    
                    if any_tool_failed_persistently:
                        self.logger.warning(f"{log_prefix} 工具执行中发生持久性失败。")
                        await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "action_execution", "status": "tool_failure_detected", "message": "部分操作失败,准备评估是否重规划。", "details": {"last_error_message": last_failed_tool_message_for_user}})
                        if replanning_loop_count < self.max_replanning_attempts: replanning_loop_count += 1; continue 
                        else: self.logger.critical(f"{log_prefix} 已达最大重规划尝试次数,但工具执行仍失败。中止。"); final_reply_for_user = f"抱歉,执行请求时遇问题: {last_failed_tool_message_for_user} 请检查指令或稍后再试。"; final_llm_interaction_id_for_user = current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id; final_llm_camelcase_json_for_reply = None; break 
                    else: self.logger.info(f"{log_prefix} 所有工具成功执行。准备生成最终回复。"); break  # 成功则跳出重规划循环
                else: 
                    self.logger.info(f"{log_prefix} 决策: 直接回复。")
                    if isinstance(response_user_obj_from_plan, dict) and response_user_obj_from_plan.get("content") is not None and \
                       (isinstance(response_user_obj_from_plan.get("content"), str) and response_user_obj_from_plan.get("content","").strip()):
                        final_llm_camelcase_json_for_reply = current_llm_plan_camelcase_json_obj 
                        self.logger.info(f"{log_prefix} 规划阶段决定直接回复,内容有效。使用此JSON作最终输出。LLM_ID: {final_llm_camelcase_json_for_reply.get('llmInteractionId')}")
                        break # 直接回复成功，跳出重规划循环
                    else: 
                        err_msg_direct_content_critical = "内部规划错误: isCallTools为False但responseToUser.content无效或为空。"
                        self.logger.error(f"{log_prefix} {err_msg_direct_content_critical}")
                        tool_execution_results_for_llm_history = [{"role":"tool", "tool_call_id":f"direct_reply_integrity_err_{str(uuid4())[:6]}", "name":"direct_reply_integrity_checker", "content":json.dumps({"status":"failure", "message":err_msg_direct_content_critical, "error": {"error_type":"INTERNAL_AGENT_ERROR", "error_code":"INVALID_DIRECT_RESPONSE_CONTENT", "technical_message": err_msg_direct_content_critical}})}]
                        try: self.memory_manager.add_to_short_term(tool_execution_results_for_llm_history[0])
                        except Exception as e_mem_add_direct_reply_err: self.logger.error(f"{log_prefix} 添加直接回复完整性错误到记忆失败: {e_mem_add_direct_reply_err}")
                        if replanning_loop_count >= self.max_replanning_attempts: final_reply_for_user = f"抱歉,系统准备直接回复时遇内部问题: {err_msg_direct_content_critical}"; final_llm_interaction_id_for_user = current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id; final_llm_camelcase_json_for_reply = None; break 
                        else: replanning_loop_count += 1; continue
            
            self.logger.debug(f"[Orchestrator - ReqID:{self.current_request_id}] 重规划循环结束。")
            
            resp_gen_llm_retries = self.response_generation_llm_retries 

            # 只有在规划成功、需要调用工具、且工具执行也成功后，才进入响应生成阶段
            # 或者规划成功且是直接回复 (final_llm_camelcase_json_for_reply 已被设置)
            if final_llm_camelcase_json_for_reply is None and \
               current_llm_plan_camelcase_json_obj and \
               current_llm_plan_camelcase_json_obj.get("status") == "success" and \
               current_llm_plan_camelcase_json_obj.get("decision",{}).get("isCallTools") is True: 
                
                self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 工具执行流程完成,开始生成最终响应 (LLM: {self.current_llm_identifier}, 中文思考: {self.current_enable_chinese_thinking}, LLM重试上限: {resp_gen_llm_retries})...")
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "response_generation", "status": "started", "message": "正在总结结果并生成最终回复...", "details": {"reason": "Tool execution phase completed."}})
                memory_context_resp_gen = self.memory_manager.get_memory_context_for_prompt( recent_long_term_count=self.config_loader.get_config("agent_settings.memory.recent_long_term_count_for_prompt", 7) )
                tool_schemas_resp_gen = get_tool_schemas_for_prompt(self.tools_registry) 
                system_prompt_resp_gen = get_response_generation_prompt( 
                    memory_context=memory_context_resp_gen, 
                    tool_schemas_desc=tool_schemas_resp_gen, 
                    request_id=self.current_request_id,
                    enable_deep_thinking_chinese=self.current_enable_chinese_thinking
                )
                messages_for_resp_gen = [{"role": "system", "content": system_prompt_resp_gen}] + self.memory_manager.short_term
                
                llm_call_attempt_resp_gen = 0; parsed_final_camelcase_resp_json_this_attempt: Optional[Dict[str, Any]] = None
                while llm_call_attempt_resp_gen <= resp_gen_llm_retries:
                    self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 调用响应生成 LLM (模型: {self.current_llm_identifier}, 尝试 {llm_call_attempt_resp_gen + 1}/{resp_gen_llm_retries + 1})...")
                    try:
                        llm_response_final_gen_raw = await self.llm_interface.call_llm( 
                            messages=messages_for_resp_gen, 
                            execution_phase="response_generation", 
                            status_callback=status_callback,
                            selected_model_identifier=self.current_llm_identifier
                        )
                        if not llm_response_final_gen_raw or not hasattr(llm_response_final_gen_raw, 'choices') or not llm_response_final_gen_raw.choices: 
                            raise ConnectionError("LLM最终响应生成阶段响应无效。")
                        
                        llm_msg_obj_final_gen = llm_response_final_gen_raw.choices[0].message
                        parsed_final_camelcase_resp_json_this_attempt, final_parser_err_resp, final_validation_failures_resp = \
                            self.output_parser.parse_llm_response_to_structured_json(llm_msg_obj_final_gen, "response_generation")
                        
                        if parsed_final_camelcase_resp_json_this_attempt:
                            active_llm_interaction_id = parsed_final_camelcase_resp_json_this_attempt.get("llmInteractionId")
                            final_resp_thought_process = parsed_final_camelcase_resp_json_this_attempt.get("thoughtProcess")
                            if final_resp_thought_process: await status_callback({"type": "thinking_log", "request_id": self.current_request_id, "llm_interaction_id": active_llm_interaction_id, "stage": "response_generation", "content": final_resp_thought_process})
                        
                        if parsed_final_camelcase_resp_json_this_attempt and not final_parser_err_resp and not final_validation_failures_resp and \
                           parsed_final_camelcase_resp_json_this_attempt.get("status") == "success":
                            final_llm_camelcase_json_for_reply = parsed_final_camelcase_resp_json_this_attempt; final_llm_interaction_id_for_user = active_llm_interaction_id
                            self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 成功解析最终响应V1.0-JSON (LLM_ID: {final_llm_interaction_id_for_user})。")
                            try: 
                                if hasattr(llm_msg_obj_final_gen, 'model_dump'):
                                    self.memory_manager.add_to_short_term(llm_msg_obj_final_gen.model_dump(exclude_unset=True))
                                elif isinstance(llm_msg_obj_final_gen, dict):
                                     self.memory_manager.add_to_short_term(llm_msg_obj_final_gen)
                                else:
                                    self.memory_manager.add_to_short_term(llm_msg_obj_final_gen.dict(exclude_unset=True)) # type: ignore
                            except AttributeError as e_attr:
                                self.logger.error(f"添加最终LLM响应到记忆时，message对象缺少model_dump或dict方法: {e_attr}。")
                            except Exception as e_mem_add_final_resp: self.logger.error(f"添加最终LLM响应到记忆失败: {e_mem_add_final_resp}")
                            break 
                        else: 
                            err_msg_final_resp_gen = final_parser_err_resp or "V1.0.0最终响应JSON校验失败。"
                            if final_validation_failures_resp: err_msg_final_resp_gen += " 失败点(部分): " + json.dumps(final_validation_failures_resp[:2], ensure_ascii=False)
                            elif parsed_final_camelcase_resp_json_this_attempt and parsed_final_camelcase_resp_json_this_attempt.get("status") == "failure": err_msg_final_resp_gen = parsed_final_camelcase_resp_json_this_attempt.get("errorDetails",{}).get("technicalMessage", err_msg_final_resp_gen)
                            self.logger.error(f"[Orchestrator - ReqID:{self.current_request_id}] LLM未能生成有效最终回复 (尝试 {llm_call_attempt_resp_gen + 1}): {err_msg_final_resp_gen}")
                            if llm_call_attempt_resp_gen >= resp_gen_llm_retries: 
                                final_reply_for_user = f"抱歉,总结操作结果时发生问题。错误(部分): {err_msg_final_resp_gen[:500]}... "
                                final_llm_interaction_id_for_user = active_llm_interaction_id or (current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else f"error_resp_gen_{str(uuid4())[:6]}")
                                final_llm_camelcase_json_for_reply = None 
                                break 
                            try: 
                                if hasattr(llm_msg_obj_final_gen, 'model_dump'):
                                    self.memory_manager.add_to_short_term(llm_msg_obj_final_gen.model_dump(exclude_unset=True))
                                elif isinstance(llm_msg_obj_final_gen, dict):
                                     self.memory_manager.add_to_short_term(llm_msg_obj_final_gen)
                                else:
                                    self.memory_manager.add_to_short_term(llm_msg_obj_final_gen.dict(exclude_unset=True)) # type: ignore
                            except: pass 
                    except Exception as e_llm_final_gen_call: 
                        self.logger.critical(f"[Orchestrator - ReqID:{self.current_request_id}] LLM最终响应调用失败 (尝试 {llm_call_attempt_resp_gen + 1}): {e_llm_final_gen_call}", exc_info=True)
                        if llm_call_attempt_resp_gen >= resp_gen_llm_retries: 
                            final_reply_for_user = f"抱歉,系统准备最终报告时遇严重错误: {str(e_llm_final_gen_call)[:500]}... "
                            final_llm_interaction_id_for_user = (current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id or f"critical_err_resp_gen_{str(uuid4())[:6]}")
                            final_llm_camelcase_json_for_reply = None 
                            break 
                    llm_call_attempt_resp_gen +=1
            
            elif final_llm_camelcase_json_for_reply and final_llm_camelcase_json_for_reply.get("status") == "success" and \
                 final_llm_camelcase_json_for_reply.get("decision",{}).get("isCallTools") is False:
                self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 使用规划阶段的直接回复JSON作最终输出。")
                final_llm_interaction_id_for_user = final_llm_camelcase_json_for_reply.get("llmInteractionId")

            elif not final_llm_camelcase_json_for_reply : 
                 self.logger.error(f"[Orchestrator - ReqID:{self.current_request_id}] 流程结束时,final_llm_camelcase_json_for_reply为空,表明处理失败。")

            user_facing_thought_process_final_summary = "综合思考过程已在之前的日志中发送。" 
            if final_llm_camelcase_json_for_reply and final_llm_camelcase_json_for_reply.get("status") == "success":
                user_facing_thought_process_final_summary = final_llm_camelcase_json_for_reply.get("thoughtProcess", user_facing_thought_process_final_summary)
                resp_user_obj_final = final_llm_camelcase_json_for_reply.get("decision", {}).get("responseToUser", {})
                final_reply_for_user = resp_user_obj_final.get("content", final_reply_for_user) 
            
            await status_callback({ "type": "general_status", "request_id": self.current_request_id, "stage": "finalization", "status": "completed" if (final_llm_camelcase_json_for_reply and final_llm_camelcase_json_for_reply.get("status") == "success") else "failed", "message": "请求处理流程已结束。" })
            await status_callback({ "type": "final_response", "request_id": self.current_request_id, "llm_interaction_id": final_llm_interaction_id_for_user, "content": final_reply_for_user.strip() if final_reply_for_user else "抱歉,未能生成有效回复。", "final_camelcase_json_if_success": final_llm_camelcase_json_for_reply })
            
            if not (final_llm_camelcase_json_for_reply and final_llm_camelcase_json_for_reply.get("status") == "success"):
                final_assistant_synthetic_error_message_camelcase_json = { "requestId": self.current_request_id, "llmInteractionId": final_llm_interaction_id_for_user or f"agent_synth_final_err_{str(uuid4())[:6]}", "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure", "errorDetails": {"errorType": "AGENT_PROCESSING_FAILURE", "errorCode": "OVERALL_REQUEST_HANDLING_FAILED", "messageToUser": final_reply_for_user, "technicalMessage": "Agent failed to complete user request.", "isDirectLlmFailure": False }, "executionPhase": "final_error_synthesis", "thoughtProcess": user_facing_thought_process_final_summary or "Agent最终处理失败。", "decision": {"isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content": final_reply_for_user}}}
                try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(final_assistant_synthetic_error_message_camelcase_json, ensure_ascii=False)})
                except Exception as e_mem_add_synth_err: self.logger.error(f"添加Agent合成的最终错误到记忆失败: {e_mem_add_synth_err}")
        # --- END OF ORCHESTRATION LOGIC ---
        except Exception as e_process_top_level: 
            request_id_for_fatal = self.current_request_id or f"fatal_err_no_req_id_{str(uuid4())[:6]}"
            self.logger.critical(f"[Orchestrator - ReqID:{request_id_for_fatal}] 处理用户请求时发生顶层未捕获异常: {e_process_top_level}", exc_info=True)
            error_msg_for_user_fatal = self.config_loader.get_config("agent_settings.general.default_user_facing_error_message", "抱歉,处理您的请求时发生严重内部系统错误。")
            tb_str_for_thinking_log_fatal = traceback.format_exc().replace('\n', ' | ') 
            thinking_log_content_fatal = f"请求处理流程中发生顶层致命错误: {e_process_top_level}。Traceback: {tb_str_for_thinking_log_fatal[:1000]}..."
            fatal_llm_interaction_id = f"fatal_agent_err_{str(uuid4())[:6]}" 
            try:
                await status_callback({"type": "thinking_log", "request_id": request_id_for_fatal, "llm_interaction_id": fatal_llm_interaction_id, "stage": "fatal_error_capture", "content": thinking_log_content_fatal})
                await status_callback({"type": "general_status", "request_id": request_id_for_fatal, "stage": "fatal_error_handler", "status": "error", "message": f"请求处理失败,发生致命错误: {str(e_process_top_level)[:1000]}", "details": {"error_type": type(e_process_top_level).__name__}})
                await status_callback({"type": "final_response", "request_id": request_id_for_fatal, "llm_interaction_id": fatal_llm_interaction_id, "content": error_msg_for_user_fatal, "final_camelcase_json_if_success": None})
            except Exception as e_cb_fatal: self.logger.error(f"发送顶层致命错误的回调失败: {e_cb_fatal}", exc_info=True)
        finally:
            request_end_time = time.monotonic()
            duration_total = request_end_time - request_start_time
            self.logger.info(f"\n{'='*25} CircuitAgent 请求处理完毕 (ReqID: {self.current_request_id or 'N/A'}, 模型: {self.current_llm_identifier}, 总耗时: {duration_total:.3f} 秒) {'='*25}\n")
            self.current_request_id = None 
            self.current_llm_identifier = self.default_llm_identifier
            self.current_enable_chinese_thinking = self.default_enable_chinese_thinking
