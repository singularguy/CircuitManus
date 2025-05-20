
# IDT_AGENT_NATIVE/circuitmanus/agent.py
import os
import json
import time
import inspect # 用于动态发现和注册工具
import logging
import asyncio
import traceback
from uuid import uuid4
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Callable, Awaitable

# --- 导入新拆分的模块 ---
# utils
from .utils.logging_config import setup_logging, console_handler as global_console_handler
from .utils.async_setup import get_event_loop

# memory
from .memory.manager import MemoryManager

# llm
from .llm.interface import LLMInterface
from .llm.parser import OutputParser 

# tools
from .tools.base import register_tool # register_tool 装饰器本身
from .tools.executor import ToolExecutor
# 导入具体的工具函数实现模块
from .tools import circuit_ops 
from .tools import web_search

# prompts (现在从这里导入提示生成函数)
from .prompts.templates import (
    get_tool_schemas_for_prompt,
    get_planning_prompt,
    get_response_generation_prompt
)

class CircuitAgent:
    """
    CircuitAgent V1.0.0 (Refactored - 11 Tools)
    核心智能助手类，负责处理用户请求、与LLM交互、执行工具以及管理记忆和电路状态。
    """
    def __init__(self, 
                 api_key: str, 
                 model_name: str = "glm-z1-flash",
                 max_short_term_items: int = 30, 
                 max_long_term_items: int = 75,
                 planning_llm_retries: int = 5, 
                 max_tool_retries: int = 3,
                 tool_retry_delay_seconds: float = 10.0, 
                 max_replanning_attempts: int = 3,
                 verbose: bool = True):
        
        self.api_key: str = api_key
        self.verbose_mode: bool = verbose
        self.current_request_id: Optional[str] = None 

        self.logger = setup_logging(verbose_mode=self.verbose_mode) 
        self.logger.info(f"\n{'='*30} CircuitAgent 初始化开始 (V1.0.0 Refactored - 11 Tools) {'='*30}")

        if global_console_handler: 
            console_log_level = logging.DEBUG if self.verbose_mode else logging.INFO
            global_console_handler.setLevel(console_log_level)
            self.logger.info(f"[Agent Init] 控制台日志级别已通过全局处理器设置为: {logging.getLevelName(console_log_level)} (详细模式: {self.verbose_mode})。")
        else:
            self.logger.warning("[Agent Init] 未找到全局控制台日志处理器引用,无法动态设置日志级别。")

        self.tools_registry: Dict[str, Dict[str, Any]] = {}
        self.logger.info("[Agent Init] 正在动态发现并注册工具...")
        
        tool_modules = [circuit_ops, web_search]
        for module in tool_modules:
            for name, func in inspect.getmembers(module, inspect.isfunction):
                if hasattr(func, '_is_tool') and func._is_tool:
                    schema = getattr(func, '_tool_schema', None)
                    if schema and isinstance(schema, dict) and 'description' in schema and 'parameters' in schema:
                        import functools # 移到需要的地方
                        # 为异步和同步函数创建正确的绑定方法
                        if inspect.iscoroutinefunction(func):
                            # 对于异步函数，我们需要创建一个新的异步包装器来传递self
                            async def async_bound_method_wrapper(arguments: Dict[str, Any], agent_self=self, original_func=func):
                                return await original_func(agent_self, arguments)
                            
                            # 复制元数据，特别是协程特性
                            functools.update_wrapper(async_bound_method_wrapper, func)
                            setattr(self, name, async_bound_method_wrapper)
                        else:
                            # 对于同步函数，functools.partial通常能很好地工作
                            bound_method = functools.partial(func, self)
                            functools.update_wrapper(bound_method, func) # 确保wraps的效果
                            setattr(self, name, bound_method)
                        
                        # 确保_is_tool和_tool_schema在绑定后的方法上仍然可访问（如果ToolExecutor直接检查实例方法）
                        # setattr的属性可能不会自动传递，需要显式设置在实例的方法上
                        # 或者 ToolExecutor 在获取方法后，检查其 __wrapped__ (如果使用 functools.wraps) 或原始 func。
                        # 为了简单，我们确保ToolExecutor检查的是注册表，而不是动态方法的属性。
                        # 但为了保险，如果ToolExecutor依赖于检查实例上的方法属性，这里需要处理：
                        # getattr(self, name)._is_tool = True # 确保绑定后的方法也有这些标记
                        # getattr(self, name)._tool_schema = schema

                        self.tools_registry[name] = schema
                        is_async_tool = inspect.iscoroutinefunction(func) 
                        self.logger.info(f"[Agent Init] ✓ 已动态绑定并注册工具: '{name}' (来自模块: {module.__name__}, 原始是否异步: {is_async_tool})。")
                    else:
                        self.logger.warning(f"[Agent Init] 在模块 {module.__name__} 中发现函数 '{name}' 被标记为工具,但其 Schema 结构不完整或无效,已跳过注册。")
        
        if not self.tools_registry:
            self.logger.warning("[Agent Init] 未发现任何通过 @register_tool 注册的工具！")
        else:
            self.logger.info(f"[Agent Init] 共动态绑定并注册了 {len(self.tools_registry)} 个工具。")
            if self.logger.isEnabledFor(logging.DEBUG):
                try: 
                    registry_for_log = { name: { "description": schema["description"] } for name, schema in self.tools_registry.items() }
                    self.logger.debug(f"[Agent Init] 工具注册表摘要:\n{json.dumps(registry_for_log, indent=2, ensure_ascii=False)}")
                except Exception as e_dump: 
                    self.logger.debug(f"无法序列化工具注册表摘要进行日志记录: {e_dump}")

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
            self.logger.critical(f"[Agent Init] 核心模块初始化失败: {e}", exc_info=True)
            raise 

        self.planning_llm_retries: int = max(0, planning_llm_retries)
        self.max_replanning_attempts: int = max(0, max_replanning_attempts)
        
        self.logger.info(f"[Agent Init] 规划LLM重试次数: {self.planning_llm_retries}, 工具执行重试次数: {max_tool_retries}, 最大重规划尝试次数: {self.max_replanning_attempts}。")
        self.logger.info(f"\n{'='*30} CircuitAgent 初始化成功 (V1.0.0 Refactored - 11 Tools) {'='*30}\n")

    async def process_user_request(self, user_request: str, status_callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        request_start_time = time.monotonic()
        self.current_request_id = f"req_{str(uuid4())[:12]}" 

        final_llm_camelcase_json_for_reply: Optional[Dict[str, Any]] = None
        final_reply_for_user: str = "抱歉,处理您的请求时发生未知错误。" 
        final_llm_interaction_id_for_user: Optional[str] = None
        active_llm_interaction_id: Optional[str] = None 

        self.logger.info(f"\n{'='*25} CircuitAgent 开始处理用户请求 (ReqID: {self.current_request_id}) {'='*25}")
        self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 收到用户指令: \"{user_request[:1000]}{'...' if len(user_request)>1000 else ''}\"")

        try:
            if not user_request or user_request.isspace():
                self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 用户指令为空。")
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
                await status_callback({
                    "type": "final_response", 
                    "request_id": self.current_request_id, 
                    "llm_interaction_id": empty_input_err_json["llmInteractionId"], 
                    "content": empty_input_err_json["decision"]["responseToUser"]["content"], 
                    "final_json_if_success": None 
                })
                return 

            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "received", "message": "收到用户指令,开始处理...", "details": {"user_request_preview": user_request[:1000]}})
            
            try:
                self.memory_manager.add_to_short_term({"role": "user", "content": user_request})
            except Exception as e_mem_user:
                self.logger.error(f"[Orchestrator - ReqID:{self.current_request_id}] 添加用户消息到短期记忆时出错: {e_mem_user}", exc_info=True)
                err_msg_mem = f"记录用户指令时发生内部记忆错误: {e_mem_user}"
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "error", "message": err_msg_mem})
                mem_err_json = {
                    "requestId": self.current_request_id, "llmInteractionId": f"agent_mem_err_{str(uuid4())[:6]}",
                    "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure",
                    "errorDetails": {"errorType": "INTERNAL_AGENT_ERROR", "errorCode": "MEMORY_ADD_USER_MSG_FAILED", "messageToUser": f"抱歉,我在记录您的指令时遇到了内部问题 ({e_mem_user})！请稍后重试。", "technicalMessage": err_msg_mem, "isDirectLlmFailure": False },
                    "executionPhase": "planning", "thoughtProcess": "Agent在将用户消息添加到短期记忆时遇到错误。",
                    "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content": f"抱歉,我在记录您的指令时遇到了内部问题 ({e_mem_user})！请稍后重试。" }}
                }
                await status_callback({"type": "final_response", "request_id": self.current_request_id, "llm_interaction_id": mem_err_json["llmInteractionId"], "content": mem_err_json["decision"]["responseToUser"]["content"], "final_json_if_success": None})
                return

            replanning_loop_count = 0
            current_llm_plan_camelcase_json_obj: Optional[Dict[str, Any]] = None
            agent_accepted_latest_plan_for_action = False 

            while replanning_loop_count <= self.max_replanning_attempts:
                current_planning_attempt_num = replanning_loop_count + 1
                log_prefix = f"[Orchestrator - PlanAttempt {current_planning_attempt_num} - ReqID: {self.current_request_id}]"
                self.logger.info(f"\n--- {log_prefix} 开始 ---")

                is_currently_replanning = (replanning_loop_count > 0)
                status_msg_planning_start = "正在分析指令并制定计划..." if not is_currently_replanning else f"正在尝试第 {replanning_loop_count}/{self.max_replanning_attempts} 次重规划..."
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "started", "message": status_msg_planning_start, "details": {"attempt_number": current_planning_attempt_num, "max_replanning_attempts": self.max_replanning_attempts}})

                memory_context = self.memory_manager.get_memory_context_for_prompt()
                tool_schemas_for_llm = get_tool_schemas_for_prompt(self.tools_registry) # 调用导入的函数
                
                system_prompt_planning = get_planning_prompt( # 调用导入的函数
                    tool_schemas_desc=tool_schemas_for_llm, 
                    memory_context=memory_context, 
                    is_replanning=is_currently_replanning, 
                    request_id=self.current_request_id
                )
                messages_for_planning = [{"role": "system", "content": system_prompt_planning}] + self.memory_manager.short_term

                llm_call_attempt_inner = 0 
                parsed_plan_camelcase_json_this_llm_call: Optional[Dict[str, Any]] = None
                parser_error_msg_this_llm_call: str = ""
                parsed_failed_validation_points_this_llm_call: List[Dict[str,str]] = []
                agent_accepted_latest_plan_for_action = False 

                while llm_call_attempt_inner <= self.planning_llm_retries:
                    self.logger.info(f"{log_prefix} 调用规划 LLM (LLM Call Attempt {llm_call_attempt_inner + 1} of {self.planning_llm_retries + 1})...")
                    try:
                        llm_response_planning_raw = await self.llm_interface.call_llm(
                            messages_for_planning, 
                            "planning", 
                            status_callback
                        )
                        if not llm_response_planning_raw or not llm_response_planning_raw.choices:
                            raise ConnectionError("LLM规划响应无效或缺少choices。")

                        llm_msg_obj_planning = llm_response_planning_raw.choices[0].message
                        parsed_plan_camelcase_json_this_llm_call, parser_error_msg_this_llm_call, parsed_failed_validation_points_this_llm_call = \
                            self.output_parser.parse_llm_response_to_structured_json(llm_msg_obj_planning, "planning")

                        if parsed_plan_camelcase_json_this_llm_call:
                            active_llm_interaction_id = parsed_plan_camelcase_json_this_llm_call.get("llmInteractionId")
                            current_thought_process = parsed_plan_camelcase_json_this_llm_call.get("thoughtProcess")
                            if current_thought_process: 
                                await status_callback({"type": "thinking_log", "request_id": self.current_request_id, "llm_interaction_id": active_llm_interaction_id, "stage": "planning", "content": current_thought_process})

                        if parsed_plan_camelcase_json_this_llm_call and \
                           not parser_error_msg_this_llm_call and \
                           not parsed_failed_validation_points_this_llm_call:
                            if parsed_plan_camelcase_json_this_llm_call.get("status") == "success":
                                self.logger.info(f"{log_prefix} 成功解析并验证V1.0-CamelCaseJSON计划。LLM报告状态为 'success' (LLM_ID: {active_llm_interaction_id})。Agent采纳此计划。")
                                agent_accepted_latest_plan_for_action = True
                            elif is_currently_replanning and \
                                 parsed_plan_camelcase_json_this_llm_call.get("decision", {}).get("isCallTools") is True and \
                                 isinstance(parsed_plan_camelcase_json_this_llm_call.get("decision", {}).get("toolCallRequests"), list) and \
                                 parsed_plan_camelcase_json_this_llm_call.get("decision", {}).get("toolCallRequests"): 
                                self.logger.warning(f"{log_prefix} LLM在重规划时提供了新的工具调用计划,但可能将其顶层status标记为 'failure' (LLM_ID: {active_llm_interaction_id})。Agent将审慎采纳此新计划以尝试修正。LLM报告的错误(如有): {parsed_plan_camelcase_json_this_llm_call.get('errorDetails')}")
                                agent_accepted_latest_plan_for_action = True 
                            else: 
                                error_detail_from_llm = parsed_plan_camelcase_json_this_llm_call.get("errorDetails", {}).get("technicalMessage", "LLM规划指示内部错误,但JSON结构有效。")
                                self.logger.warning(f"{log_prefix} LLM报告的V1.0-CamelCaseJSON计划状态为 'failure': {error_detail_from_llm} (LLM_ID: {active_llm_interaction_id})。Agent将不采纳此计划,并尝试让LLM修正。")
                                parser_error_msg_this_llm_call = f"LLM主动报告规划失败: {error_detail_from_llm}" 

                            if agent_accepted_latest_plan_for_action:
                                current_llm_plan_camelcase_json_obj = parsed_plan_camelcase_json_this_llm_call
                                try:
                                    self.memory_manager.add_to_short_term(llm_msg_obj_planning.model_dump(exclude_unset=True))
                                except Exception as e_mem_add: 
                                    self.logger.error(f"{log_prefix} 添加LLM规划响应到记忆失败: {e_mem_add}")
                                break 

                        if not agent_accepted_latest_plan_for_action and llm_call_attempt_inner < self.planning_llm_retries:
                            error_to_report_cb = parser_error_msg_this_llm_call or "V1.0.0结构或内容校验失败。"
                            if parsed_failed_validation_points_this_llm_call: 
                                error_to_report_cb += " 失败点(部分): " + json.dumps(parsed_failed_validation_points_this_llm_call[:2], ensure_ascii=False) 
                            
                            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "llm_retry_needed", "message": f"大脑计划处理遇到问题,尝试重新沟通 ({error_to_report_cb[:1000]})", "details": {"llm_call_attempt": llm_call_attempt_inner + 1, "parser_error": parser_error_msg_this_llm_call, "validation_failures_count": len(parsed_failed_validation_points_this_llm_call)}})
                            
                            if parsed_plan_camelcase_json_this_llm_call and parsed_plan_camelcase_json_this_llm_call.get("status") == "failure":
                                try: self.memory_manager.add_to_short_term(llm_msg_obj_planning.model_dump(exclude_unset=True))
                                except Exception as e_mem_add_fail: self.logger.error(f"{log_prefix} 添加LLM失败规划到记忆失败: {e_mem_add_fail}")
                            elif parser_error_msg_this_llm_call or parsed_failed_validation_points_this_llm_call:
                                 sim_err_plan_content = {
                                    "requestId": self.current_request_id, 
                                    "llmInteractionId": f"agent_parser_err_{active_llm_interaction_id or str(uuid4())[:6]}",
                                    "timestampUtc": datetime.now(timezone.utc).isoformat(), 
                                    "status": "failure", 
                                    "errorDetails": {
                                        "errorType": "LLM_OUTPUT_VALIDATION_ERROR", 
                                        "errorCode": "V1_CAMELCASE_JSON_VALIDATION_FAILED_BY_AGENT", 
                                        "technicalMessage": parser_error_msg_this_llm_call or "Agent端JSON校验失败。", 
                                        "isDirectLlmFailure": False, 
                                        "failedValidationPoints": parsed_failed_validation_points_this_llm_call 
                                    },
                                    "executionPhase": "planning", 
                                    "thoughtProcess": "Agent在解析或验证LLM上一次规划输出时发现以下问题,将请求LLM修正。",
                                    "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content":""}} 
                                 }
                                 try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(sim_err_plan_content, ensure_ascii=False)})
                                 except Exception as e_mem_add_parse_err: self.logger.error(f"{log_prefix} 添加Agent解析错误到记忆失败: {e_mem_add_parse_err}")
                        
                    except Exception as e_llm_call_level: 
                        self.logger.error(f"{log_prefix} LLM调用或规划解析时发生严重错误 (LLM Call Attempt {llm_call_attempt_inner + 1}): {e_llm_call_level}", exc_info=True)
                        parser_error_msg_this_llm_call = f"LLM调用/解析严重错误: {str(e_llm_call_level)[:1000]}"
                        parsed_failed_validation_points_this_llm_call = [{"jsonPath":"root.llmCallOrParse", "issue_description": parser_error_msg_this_llm_call}]
                        if llm_call_attempt_inner < self.planning_llm_retries:
                             await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "llm_error_retrying", "message": f"与大脑沟通时发生严重错误,尝试重新连接 ({parser_error_msg_this_llm_call})", "details": {"llm_call_attempt": llm_call_attempt_inner + 1}})
                    
                    llm_call_attempt_inner += 1
                    if agent_accepted_latest_plan_for_action: break 

                if not agent_accepted_latest_plan_for_action: 
                    error_summary_final_planning_llm_attempt = parser_error_msg_this_llm_call or "在多次LLM调用尝试后,未能从LLM获取可接受的规划。"
                    if parsed_failed_validation_points_this_llm_call:
                         error_summary_final_planning_llm_attempt += " 最后一次校验失败点(部分): " + json.dumps(parsed_failed_validation_points_this_llm_call[:2], ensure_ascii=False)

                    await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "failed_after_llm_retries", "message": f"规划失败: {error_summary_final_planning_llm_attempt[:1000]}", "details": {"final_parser_error": parser_error_msg_this_llm_call, "final_validation_failures_count": len(parsed_failed_validation_points_this_llm_call), "thinking_log_from_last_attempt": parsed_plan_camelcase_json_this_llm_call.get("thoughtProcess") if parsed_plan_camelcase_json_this_llm_call else "N/A"}})

                    if replanning_loop_count >= self.max_replanning_attempts: 
                        self.logger.critical(f"{log_prefix} 已达最大重规划尝试次数,且本次规划最终失败。中止。")
                        final_reply_for_user = f"抱歉,多次尝试后未能为您的请求 '{user_request[:50]}...' 制定有效计划。错误: {error_summary_final_planning_llm_attempt[:500]}"
                        final_llm_interaction_id_for_user = active_llm_interaction_id or f"error_max_replan_{str(uuid4())[:6]}"
                        final_llm_camelcase_json_for_reply = None 
                        break 
                    else: 
                        sim_fail_plan_content_for_replan = {
                            "requestId": self.current_request_id, "llmInteractionId": f"agent_replan_trigger_{active_llm_interaction_id or str(uuid4())[:6]}",
                            "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure",
                            "errorDetails": {"errorType": "LLM_OUTPUT_VALIDATION_ERROR", "errorCode": "PLAN_VALIDATION_FAILED_IN_ATTEMPT", "technicalMessage": error_summary_final_planning_llm_attempt, "isDirectLlmFailure": False, "failedValidationPoints": parsed_failed_validation_points_this_llm_call },
                            "executionPhase": "planning", "thoughtProcess": f"Agent在第 {current_planning_attempt_num} 次规划尝试失败,将重规划。错误: {error_summary_final_planning_llm_attempt}",
                            "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content":""}}
                        }
                        try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(sim_fail_plan_content_for_replan, ensure_ascii=False)})
                        except Exception as e_mem_add_replan_trigger: self.logger.error(f"{log_prefix} 添加重规划触发信息到记忆出错: {e_mem_add_replan_trigger}")
                        
                        replanning_loop_count += 1
                        continue 

                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "completed_and_validated", "message": "规划完成,准备执行或直接回复。", "details": {"plan_llm_id": current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else None}})

                tool_requests_from_plan = current_llm_plan_camelcase_json_obj.get("decision", {}).get("toolCallRequests", []) if current_llm_plan_camelcase_json_obj else []
                
                if isinstance(tool_requests_from_plan, list) and current_llm_plan_camelcase_json_obj and current_llm_plan_camelcase_json_obj.get("decision",{}).get("isCallTools") is True:
                    plan_details_for_ui = []
                    for req_idx, tool_req_in_plan in enumerate(tool_requests_from_plan): 
                        plan_details_for_ui.append({
                            "tool_call_id": tool_req_in_plan.get("toolCallId"), "tool_name": tool_req_in_plan.get("toolName"),
                            "tool_arguments": tool_req_in_plan.get("toolArguments", {}), "ui_hints": tool_req_in_plan.get("uiHints", {}),
                            "status": "pending", "order": req_idx + 1
                        })
                    await status_callback({ "type": "plan_details", "request_id": self.current_request_id, "llm_interaction_id": current_llm_plan_camelcase_json_obj.get("llmInteractionId"), "plan": plan_details_for_ui })

                decision_from_plan = current_llm_plan_camelcase_json_obj.get("decision", {}) if current_llm_plan_camelcase_json_obj else {}
                should_call_tools = decision_from_plan.get("isCallTools", False) 
                response_user_obj_from_plan = decision_from_plan.get("responseToUser")
                tool_execution_results_for_llm_history: List[Dict[str, Any]] = [] 

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

                        if replanning_loop_count >= self.max_replanning_attempts:
                            final_reply_for_user = f"抱歉,系统准备执行操作时遇内部问题: {err_msg_list_tools_critical}"
                            final_llm_interaction_id_for_user = current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id
                            final_llm_camelcase_json_for_reply = None
                            break 
                        else: 
                            replanning_loop_count += 1; continue

                    current_tool_exec_results_for_llm_hist = await self.tool_executor.execute_tool_calls( tool_requests_from_plan, status_callback )
                    tool_execution_results_for_llm_history.extend(current_tool_exec_results_for_llm_hist) 

                    if tool_execution_results_for_llm_history: 
                        for res_msg_tool in tool_execution_results_for_llm_history:
                            try: self.memory_manager.add_to_short_term(res_msg_tool)
                            except Exception as e_mem_add_tool_res: self.logger.error(f"{log_prefix} 添加工具结果 {res_msg_tool.get('tool_call_id')} 到记忆失败: {e_mem_add_tool_res}")

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
                                self.logger.error(f"{log_prefix} 无法解析工具结果JSON: {str(tool_res_for_hist.get('content'))[:200]}")
                                any_tool_failed_persistently = True
                                last_failed_tool_message_for_user = "一个操作的结果格式不正确。"
                    
                    if any_tool_failed_persistently:
                        self.logger.warning(f"{log_prefix} 工具执行中发生持久性失败。")
                        await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "action_execution", "status": "tool_failure_detected", "message": "部分操作失败,准备评估是否重规划。", "details": {"last_error_message": last_failed_tool_message_for_user}})
                        if replanning_loop_count < self.max_replanning_attempts: 
                            replanning_loop_count += 1; continue 
                        else: 
                            self.logger.critical(f"{log_prefix} 已达最大重规划次数,但工具执行仍失败。中止。")
                            final_reply_for_user = f"抱歉,执行请求时遇问题: {last_failed_tool_message_for_user} 请检查指令或稍后再试。"
                            final_llm_interaction_id_for_user = current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id
                            final_llm_camelcase_json_for_reply = None
                            break 
                    else: 
                        self.logger.info(f"{log_prefix} 所有工具成功执行。准备生成最终回复。")
                        break 

                else: 
                    self.logger.info(f"{log_prefix} 决策: 直接回复。")
                    if isinstance(response_user_obj_from_plan, dict) and \
                       response_user_obj_from_plan.get("content") is not None and \
                       (isinstance(response_user_obj_from_plan.get("content"), str) and response_user_obj_from_plan.get("content","").strip()):
                        final_llm_camelcase_json_for_reply = current_llm_plan_camelcase_json_obj 
                        self.logger.info(f"{log_prefix} 规划阶段决定直接回复,内容有效。使用此JSON作最终输出。LLM_ID: {final_llm_camelcase_json_for_reply.get('llmInteractionId')}")
                        break 
                    else: 
                        err_msg_direct_content_critical = "内部规划错误: isCallTools为False但responseToUser.content无效或为空。"
                        self.logger.error(f"{log_prefix} {err_msg_direct_content_critical}")
                        tool_execution_results_for_llm_history = [{"role":"tool", "tool_call_id":f"direct_reply_integrity_err_{str(uuid4())[:6]}", "name":"direct_reply_integrity_checker", "content":json.dumps({"status":"failure", "message":err_msg_direct_content_critical, "error": {"error_type":"INTERNAL_AGENT_ERROR", "error_code":"INVALID_DIRECT_RESPONSE_CONTENT", "technical_message": err_msg_direct_content_critical}})}]
                        try: self.memory_manager.add_to_short_term(tool_execution_results_for_llm_history[0])
                        except Exception as e_mem_add_direct_reply_err: self.logger.error(f"{log_prefix} 添加直接回复完整性错误到记忆失败: {e_mem_add_direct_reply_err}")

                        if replanning_loop_count >= self.max_replanning_attempts:
                            final_reply_for_user = f"抱歉,系统准备直接回复时遇内部问题: {err_msg_direct_content_critical}"
                            final_llm_interaction_id_for_user = current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id
                            final_llm_camelcase_json_for_reply = None
                            break 
                        else: 
                            replanning_loop_count += 1; continue
            
            self.logger.debug(f"[Orchestrator - ReqID:{self.current_request_id}] 重规划循环结束。")
            
            if current_llm_plan_camelcase_json_obj and \
               current_llm_plan_camelcase_json_obj.get("status") == "success" and \
               current_llm_plan_camelcase_json_obj.get("decision",{}).get("isCallTools") is True and \
               final_llm_camelcase_json_for_reply is None: 
                
                self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 工具执行流程完成,开始生成最终响应...")
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "response_generation", "status": "started", "message": "正在总结结果并生成最终回复...", "details": {"reason": "Tool execution phase completed."}})

                memory_context_resp_gen = self.memory_manager.get_memory_context_for_prompt()
                tool_schemas_resp_gen = get_tool_schemas_for_prompt(self.tools_registry) 
                
                system_prompt_resp_gen = get_response_generation_prompt( # 调用导入的函数
                    memory_context=memory_context_resp_gen,
                    tool_schemas_desc=tool_schemas_resp_gen,
                    request_id=self.current_request_id
                )
                messages_for_resp_gen = [{"role": "system", "content": system_prompt_resp_gen}] + self.memory_manager.short_term

                try:
                    llm_response_final_gen_raw = await self.llm_interface.call_llm(
                        messages_for_resp_gen, 
                        "response_generation", 
                        status_callback
                    )
                    if not llm_response_final_gen_raw or not llm_response_final_gen_raw.choices: 
                        raise ConnectionError("LLM最终响应生成阶段响应无效。")

                    llm_msg_obj_final_gen = llm_response_final_gen_raw.choices[0].message
                    parsed_final_camelcase_resp_json, final_parser_err_resp, final_validation_failures_resp = \
                        self.output_parser.parse_llm_response_to_structured_json(llm_msg_obj_final_gen, "response_generation")

                    if parsed_final_camelcase_resp_json:
                        active_llm_interaction_id = parsed_final_camelcase_resp_json.get("llmInteractionId")
                        final_resp_thought_process = parsed_final_camelcase_resp_json.get("thoughtProcess")
                        if final_resp_thought_process:
                             await status_callback({"type": "thinking_log", "request_id": self.current_request_id, "llm_interaction_id": active_llm_interaction_id, "stage": "response_generation", "content": final_resp_thought_process})
                    
                    if parsed_final_camelcase_resp_json and \
                       not final_parser_err_resp and \
                       not final_validation_failures_resp and \
                       parsed_final_camelcase_resp_json.get("status") == "success":
                        
                        final_llm_camelcase_json_for_reply = parsed_final_camelcase_resp_json
                        final_llm_interaction_id_for_user = active_llm_interaction_id
                        self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 成功解析最终响应V1.0-JSON (LLM_ID: {final_llm_interaction_id_for_user})。")
                        try:
                            self.memory_manager.add_to_short_term(llm_msg_obj_final_gen.model_dump(exclude_unset=True))
                        except Exception as e_mem_add_final_resp: 
                            self.logger.error(f"添加最终LLM响应到记忆失败: {e_mem_add_final_resp}")
                    else: 
                        err_msg_final_resp_gen = final_parser_err_resp or "V1.0.0最终响应JSON校验失败。"
                        if final_validation_failures_resp: 
                            err_msg_final_resp_gen += " 失败点(部分): " + json.dumps(final_validation_failures_resp[:2], ensure_ascii=False)
                        elif parsed_final_camelcase_resp_json and parsed_final_camelcase_resp_json.get("status") == "failure":
                             err_msg_final_resp_gen = parsed_final_camelcase_resp_json.get("errorDetails",{}).get("technicalMessage", err_msg_final_resp_gen)

                        self.logger.error(f"[Orchestrator - ReqID:{self.current_request_id}] LLM未能生成有效最终回复: {err_msg_final_resp_gen}")
                        final_reply_for_user = f"抱歉,总结操作结果时发生问题。错误(部分): {err_msg_final_resp_gen[:500]}... "
                        final_llm_interaction_id_for_user = active_llm_interaction_id or \
                                                            (current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else f"error_resp_gen_{str(uuid4())[:6]}")
                        final_llm_camelcase_json_for_reply = None 
                except Exception as e_llm_final_gen_call: 
                    self.logger.critical(f"[Orchestrator - ReqID:{self.current_request_id}] LLM最终响应调用失败: {e_llm_final_gen_call}", exc_info=True)
                    final_reply_for_user = f"抱歉,系统准备最终报告时遇严重错误: {str(e_llm_final_gen_call)[:500]}... "
                    final_llm_interaction_id_for_user = (current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id or f"critical_err_resp_gen_{str(uuid4())[:6]}")
                    final_llm_camelcase_json_for_reply = None 
            
            elif final_llm_camelcase_json_for_reply and \
                 final_llm_camelcase_json_for_reply.get("status") == "success" and \
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
            
            await status_callback({
                "type": "general_status", 
                "request_id": self.current_request_id, 
                "stage": "finalization", 
                "status": "completed" if (final_llm_camelcase_json_for_reply and final_llm_camelcase_json_for_reply.get("status") == "success") else "failed", 
                "message": "请求处理流程已结束。"
            })
            
            await status_callback({
                "type": "final_response",
                "request_id": self.current_request_id,
                "llm_interaction_id": final_llm_interaction_id_for_user, 
                "content": final_reply_for_user.strip() if final_reply_for_user else "抱歉,未能生成有效回复。",
                "final_json_if_success": final_llm_camelcase_json_for_reply 
            })

            if not (final_llm_camelcase_json_for_reply and final_llm_camelcase_json_for_reply.get("status") == "success"):
                final_assistant_synthetic_error_message_camelcase_json = {
                    "requestId": self.current_request_id,
                    "llmInteractionId": final_llm_interaction_id_for_user or f"agent_synth_final_err_{str(uuid4())[:6]}",
                    "timestampUtc": datetime.now(timezone.utc).isoformat(),
                    "status": "failure", 
                    "errorDetails": {"errorType": "AGENT_PROCESSING_FAILURE", "errorCode": "OVERALL_REQUEST_HANDLING_FAILED", "messageToUser": final_reply_for_user, "technicalMessage": "Agent failed to complete user request.", "isDirectLlmFailure": False },
                    "executionPhase": "final_error_synthesis", 
                    "thoughtProcess": user_facing_thought_process_final_summary or "Agent最终处理失败。",
                    "decision": {"isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content": final_reply_for_user}}
                }
                try: 
                    self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(final_assistant_synthetic_error_message_camelcase_json, ensure_ascii=False)})
                except Exception as e_mem_add_synth_err: 
                    self.logger.error(f"添加Agent合成的最终错误到记忆失败: {e_mem_add_synth_err}")

        except Exception as e_process_top_level: 
            request_id_for_fatal = self.current_request_id or f"fatal_err_no_req_id_{str(uuid4())[:6]}"
            self.logger.critical(f"[Orchestrator - ReqID:{request_id_for_fatal}] 处理用户请求时发生顶层未捕获异常: {e_process_top_level}", exc_info=True)
            
            error_msg_for_user_fatal = f"抱歉,处理您的请求 ('{user_request[:30]}...') 时发生严重内部系统错误。"
            tb_str_for_thinking_log_fatal = traceback.format_exc().replace('\n', ' | ') 
            thinking_log_content_fatal = f"请求处理流程中发生顶层致命错误: {e_process_top_level}。Traceback: {tb_str_for_thinking_log_fatal[:1000]}..."
            fatal_llm_interaction_id = f"fatal_agent_err_{str(uuid4())[:6]}" 
            
            try:
                await status_callback({"type": "thinking_log", "request_id": request_id_for_fatal, "llm_interaction_id": fatal_llm_interaction_id, "stage": "fatal_error_capture", "content": thinking_log_content_fatal})
                await status_callback({"type": "general_status", "request_id": request_id_for_fatal, "stage": "fatal_error_handler", "status": "error", "message": f"请求处理失败,发生致命错误: {str(e_process_top_level)[:1000]}", "details": {"error_type": type(e_process_top_level).__name__}})
                await status_callback({"type": "final_response", "request_id": request_id_for_fatal, "llm_interaction_id": fatal_llm_interaction_id, "content": error_msg_for_user_fatal, "final_json_if_success": None})
            except Exception as e_cb_fatal:
                self.logger.error(f"发送顶层致命错误的回调失败: {e_cb_fatal}", exc_info=True)
        finally:
            request_end_time = time.monotonic()
            duration_total = request_end_time - request_start_time
            self.logger.info(f"\n{'='*25} CircuitAgent 请求处理完毕 (ReqID: {self.current_request_id or 'N/A'}, 总耗时: {duration_total:.3f} 秒) {'='*25}\n")
            self.current_request_id = None 