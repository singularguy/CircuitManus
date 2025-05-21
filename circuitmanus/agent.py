# IDT_AGENT_NATIVE/circuitmanus/agent.py
import os
import sys # 导入 sys 以便在早期错误时输出到 stderr
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

# --- 导入新拆分的模块 ---
from .utils.config_loader import ConfigLoader # 负责加载 .env 和 YAML 配置
from .utils.logging_config import setup_logging # 日志系统设置函数
# global_console_handler 不再从 logging_config 导入，因为 setup_logging 返回的 logger 已包含配置好的处理器
from .utils.async_setup import get_event_loop # 异步事件循环辅助函数 (当前Agent未使用，但可保留)

from .memory.manager import MemoryManager # 记忆管理模块
from .llm.interface import LLMInterface   # LLM 交互接口模块
from .llm.parser import OutputParser      # LLM 响应解析器模块
from .tools.base import register_tool     # 工具注册装饰器
from .tools.executor import ToolExecutor  # 工具执行器模块
from .tools import circuit_ops            # 电路操作相关的工具函数模块
from .tools import web_search             # 网络搜索相关的工具函数模块
from .prompts.templates import (          # LLM 系统提示模板生成函数模块
    get_tool_schemas_for_prompt,
    get_planning_prompt,
    get_response_generation_prompt
)

class CircuitAgent:
    """
    CircuitAgent V1.0.0 (Refactored & Configurable - 11 Tools)
    核心智能助手类，负责处理用户请求、与LLM交互、执行工具以及管理记忆和电路状态。
    通过外部配置文件 (config.yaml 和 .env) 进行高度可配置的初始化。
    """
    def __init__(self, 
                 config_yaml_path: str = "config.yaml", 
                 dotenv_path: Optional[str] = None
                 ):
        """
        初始化 CircuitAgent 实例。
        所有核心参数现在都从配置文件中读取。

        Args:
            config_yaml_path (str): YAML 配置文件的路径。
                                    默认为项目根目录下的 "config.yaml"。
            dotenv_path (Optional[str]): .env 文件的路径。如果为 None，
                                         python-dotenv 会在默认位置 (如当前工作目录) 查找 .env 文件。
        """
        # 步骤 0: 初始化配置加载器 ConfigLoader
        # ConfigLoader 是一个单例（或表现类似单例），确保在应用中只有一份配置数据被加载和管理。
        # 它会自动处理 .env 文件的加载（将变量设置到环境变量中）和 YAML 文件的解析。
        self.config_loader = ConfigLoader(yaml_config_path=config_yaml_path, dotenv_path=dotenv_path)

        # 步骤 1: 从配置中获取基础 Agent 属性
        # API Key 是最关键的敏感信息，必须从环境变量（由 .env 文件辅助加载）中获取。
        self.api_key: str = self.config_loader.get_env_var("ZHIPUAI_API_KEY", "") # 若未找到，默认为空字符串
        if not self.api_key:
            # 在日志系统完全建立之前，如果发生这种关键错误，直接打印到 stderr 并抛出异常。
            # 这是因为没有 API Key，Agent 的核心功能（与LLM交互）将无法工作。
            early_error_msg = "CRITICAL ERROR: ZHIPUAI_API_KEY not found in environment or .env file. Agent cannot initialize."
            print(early_error_msg, file=sys.stderr) 
            raise ValueError(early_error_msg)

        # Agent 当前正在处理的用户请求ID，在每个 process_user_request 开始时设置。
        self.current_request_id: Optional[str] = None 

        # --- 步骤 2: 配置日志系统 ---
        # 从 YAML 配置中读取日志相关的设置项。
        log_level_console_str: str = self.config_loader.get_config("agent_settings.logging.log_level_console", "INFO")
        log_level_file_str: str = self.config_loader.get_config("agent_settings.logging.log_level_file", "DEBUG")
        # log_dir_cfg 若为 None，则 setup_logging 会使用其内部定义的默认日志目录。
        log_dir_cfg: Optional[str] = self.config_loader.get_config("agent_settings.logging.log_dir", None) 
        
        # Agent 的 verbose_mode 属性现在根据配置的控制台日志级别推导。
        # 如果控制台日志级别被配置为 "DEBUG"，则认为启用了详细模式。
        self.verbose_mode: bool = (log_level_console_str.upper() == "DEBUG")

        # 将从配置文件读取的字符串日志级别 (如 "INFO", "DEBUG") 转换为 logging 模块对应的整数常量。
        # getattr 用于安全地获取 logging 模块的属性，如果字符串无效，则使用默认值。
        console_level_int = getattr(logging, log_level_console_str.upper(), logging.INFO)
        file_level_int = getattr(logging, log_level_file_str.upper(), logging.DEBUG)

        # 调用从 utils.logging_config 导入的 setup_logging 函数来初始化日志系统。
        # 传递从配置中解析得到的参数。setup_logging 会返回一个配置好的 logger 实例。
        self.logger = setup_logging(
            console_log_level=console_level_int,
            file_log_level=file_level_int,
            log_dir_override=log_dir_cfg # 允许通过配置覆盖默认日志目录
        )
        
        self.logger.info(f"\n{'='*30} CircuitAgent 初始化开始 (V1.0.0 Configurable - 11 Tools) {'='*30}")
        self.logger.info(f"Agent配置已从 '{os.path.abspath(config_yaml_path)}' 和 .env (如果存在) 加载。")
        self.logger.info(f"Agent verbose_mode (推导自 console_log_level='{log_level_console_str}'): {self.verbose_mode}")

        # --- 步骤 3: 动态发现并注册工具 ---
        # self.tools_registry 用于存储所有已注册工具的 schema，供 LLM 参考。
        self.tools_registry: Dict[str, Dict[str, Any]] = {}
        self.logger.info("[Agent Init] 正在动态发现并注册工具...")
        
        # 指定包含工具定义的模块列表。
        tool_modules = [circuit_ops, web_search] 
        for module in tool_modules:
            # 使用 inspect.getmembers 遍历模块中的所有函数成员。
            for name, func in inspect.getmembers(module, inspect.isfunction):
                # 检查函数是否被 @register_tool 装饰器标记过。
                if hasattr(func, '_is_tool') and func._is_tool:
                    schema = getattr(func, '_tool_schema', None) # 获取工具的 schema 定义。
                    if schema and isinstance(schema, dict) and 'description' in schema and 'parameters' in schema:
                        # 将工具函数（func）绑定到当前的 Agent 实例 (self) 上，
                        # 这样当 ToolExecutor 调用这些工具时，工具函数内部的 'self' 参数就能正确指向 Agent 实例，
                        # 从而可以访问 Agent 的属性（如 self.memory_manager, self.config_loader）。
                        if inspect.iscoroutinefunction(func): # 如果原始工具函数是异步的
                            # 创建一个异步包装器来正确传递 self。
                            async def async_bound_method_wrapper(arguments: Dict[str, Any], agent_self=self, original_func=func):
                                return await original_func(agent_self, arguments)
                            functools.update_wrapper(async_bound_method_wrapper, func) # 保留原函数元数据
                            setattr(self, name, async_bound_method_wrapper) # 将包装后的异步方法设置到Agent实例上
                        else: # 如果原始工具函数是同步的
                            # 使用 functools.partial 创建一个预先绑定了 self 参数的新函数。
                            bound_method = functools.partial(func, self) 
                            functools.update_wrapper(bound_method, func) # 保留原函数元数据
                            setattr(self, name, bound_method) # 将绑定后的同步方法设置到Agent实例上
                        
                        self.tools_registry[name] = schema # 将工具的 schema 添加到注册表
                        is_async_tool = inspect.iscoroutinefunction(func) 
                        self.logger.info(f"[Agent Init] ✓ 已动态绑定并注册工具: '{name}' (来自模块: {module.__name__}, 原始是否异步: {is_async_tool})。")
                    else:
                        self.logger.warning(f"[Agent Init] 在模块 {module.__name__} 中发现函数 '{name}' 被标记为工具,但其 Schema 结构不完整或无效,已跳过注册。")
        
        if not self.tools_registry:
            self.logger.warning("[Agent Init] 未发现任何通过 @register_tool 注册的工具！Agent 功能将受限。")
        else:
            self.logger.info(f"[Agent Init] 共动态绑定并注册了 {len(self.tools_registry)} 个工具。")
            # (Debug日志部分保持不变，用于记录注册表摘要)

        # --- 步骤 4: 初始化核心组件实例 (使用从配置中读取的值) ---
        try:
            # MemoryManager: 配置其短期和长期记忆的容量。
            max_short_term = self.config_loader.get_config("agent_settings.memory.max_short_term_items", 30)
            max_long_term = self.config_loader.get_config("agent_settings.memory.max_long_term_items", 75)
            self.memory_manager = MemoryManager(max_short_term_items=max_short_term, max_long_term_items=max_long_term)

            # LLMInterface: 配置LLM模型、温度、最大Token数、API超时和详细日志开关。
            llm_model_cfg = self.config_loader.get_config("agent_settings.llm.model_name", "glm-z1-flash")
            llm_temp_cfg = self.config_loader.get_config("agent_settings.llm.default_temperature", 0.01)
            llm_max_tokens_cfg = self.config_loader.get_config("agent_settings.llm.default_max_tokens", 8190)
            llm_api_timeout_cfg = self.config_loader.get_config("agent_settings.llm.api_timeout_seconds", 120)
            llm_detailed_log_cfg = self.config_loader.get_config("agent_settings.feature_flags.enable_detailed_llm_message_logging", False)

            self.llm_interface = LLMInterface(
                agent_instance=self, # LLMInterface 需要回引 Agent 实例以获取 API Key 等。
                model_name=llm_model_cfg,
                default_temperature=llm_temp_cfg,
                default_max_tokens=llm_max_tokens_cfg,
                api_timeout_seconds=llm_api_timeout_cfg, 
                enable_detailed_llm_message_logging=llm_detailed_log_cfg
            )

            # OutputParser: 初始化时传入工具注册表，用于校验LLM生成的工具调用参数。
            self.output_parser = OutputParser(agent_tools_registry=self.tools_registry)

            # ToolExecutor: 配置工具执行的重试次数和延迟。
            tool_retries_cfg = self.config_loader.get_config("agent_settings.tools.max_tool_retries", 1)
            tool_delay_cfg = self.config_loader.get_config("agent_settings.tools.tool_retry_delay_seconds", 1.0)
            self.tool_executor = ToolExecutor(
                agent_instance=self, # ToolExecutor 需要 Agent 实例来调用其绑定的工具方法。
                max_tool_retries=tool_retries_cfg,
                tool_retry_delay_seconds=tool_delay_cfg
            )
        except (ValueError, ConnectionError, TypeError) as e: # 捕获组件初始化可能发生的错误
            self.logger.critical(f"[Agent Init] 核心模块实例化失败: {e}", exc_info=True)
            raise # 初始化失败是严重问题，重新抛出。

        # --- 步骤 5: Agent 自身的其他配置参数 ---
        # LLM调用重试次数 (Agent层面，用于规划和响应生成阶段的LLM调用)
        self.planning_llm_retries: int = self.config_loader.get_config("agent_settings.llm.planning_llm_retries", 3)
        self.response_generation_llm_retries: int = self.config_loader.get_config("agent_settings.llm.response_generation_llm_retries", 1)
        # 最大重规划尝试次数 (当LLM规划或工具执行失败时，Agent尝试重规划的最大次数)
        self.max_replanning_attempts: int = self.config_loader.get_config("agent_settings.orchestration.max_replanning_attempts", 2)
        
        self.logger.info(f"[Agent Init] LLM规划重试: {self.planning_llm_retries}, LLM响应生成重试: {self.response_generation_llm_retries}, 工具执行重试: {tool_retries_cfg}, 最大重规划尝试: {self.max_replanning_attempts}。")
        self.logger.info(f"\n{'='*30} CircuitAgent 初始化成功 (V1.0.0 Configurable - 11 Tools) {'='*30}\n")

    async def process_user_request(self, user_request: str, status_callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """
        处理单个用户请求的核心编排逻辑。
        这是Agent的主要工作循环，包括输入验证、记忆更新、LLM规划、工具执行（如果需要）、
        LLM响应生成，并通过status_callback异步发送状态更新。
        """
        request_start_time = time.monotonic()
        self.current_request_id = f"req_{str(uuid4())[:12]}" 

        # 初始化最终回复相关变量
        final_llm_camelcase_json_for_reply: Optional[Dict[str, Any]] = None
        final_reply_for_user: str = self.config_loader.get_config(
            "agent_settings.general.default_user_facing_error_message", 
            "抱歉,处理您的请求时发生未知错误。" # 若配置缺失，则使用此硬编码默认值
        )
        final_llm_interaction_id_for_user: Optional[str] = None
        active_llm_interaction_id: Optional[str] = None # 用于追踪当前LLM交互的ID

        self.logger.info(f"\n{'='*25} CircuitAgent 开始处理用户请求 (ReqID: {self.current_request_id}) {'='*25}")
        self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 收到用户指令 (预览): \"{user_request[:200]}{'...' if len(user_request)>200 else ''}\"") # 预览长度调整

        try:
            # 步骤 1: 用户输入验证和处理 (例如长度限制)
            max_input_len = self.config_loader.get_config("agent_settings.security.max_input_length_user_request", 10000)
            if len(user_request) > max_input_len:
                original_length = len(user_request)
                user_request_truncated = user_request[:max_input_len]
                self.logger.warning(f"[Orchestrator - ReqID:{self.current_request_id}] 用户指令过长 (原始长度: {original_length}, 上限: {max_input_len})。已截断为: \"{user_request_truncated[:50]}...\"")
                user_request = user_request_truncated # 使用截断后的请求
                # 通过回调通知UI或调用者输入被截断
                await status_callback({
                    "type": "general_status", 
                    "request_id": self.current_request_id, 
                    "stage": "input_validation", 
                    "status": "warning", 
                    "message": f"您的输入内容过长(原始长度{original_length}), 已被自动截断为{max_input_len}字符进行处理。",
                    "details": {"original_length": original_length, "truncated_length": max_input_len}
                })

            if not user_request or user_request.strip() == "": # 再次检查截断后是否为空
                self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 用户指令为空或无效。")
                # ... (处理空输入的逻辑与上次 agent.py 一致) ...
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "ignored", "message": "用户输入为空或无效,已忽略。"})
                empty_input_err_json = { "requestId": self.current_request_id, "llmInteractionId": f"agent_input_err_{str(uuid4())[:6]}", "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure", "errorDetails": { "errorType": "USER_INPUT_ERROR", "errorCode": "EMPTY_OR_INVALID_USER_REQUEST", "messageToUser": "您的指令似乎是空的或无效的,请重新输入！", "technicalMessage": "User request was empty or whitespace.", "isDirectLlmFailure": False }, "executionPhase": "planning", "thoughtProcess": "Agent检测到用户输入为空或无效,无需进一步处理。", "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content": "您的指令似乎是空的或无效的,请重新输入！"}}}
                await status_callback({ "type": "final_response", "request_id": self.current_request_id, "llm_interaction_id": empty_input_err_json["llmInteractionId"], "content": empty_input_err_json["decision"]["responseToUser"]["content"], "final_camelcase_json_if_success": None })
                return

            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "received", "message": "收到用户指令,开始处理...", "details": {"user_request_preview": user_request[:1000]}})
            
            try: # 将（可能已截断的）用户请求添加到短期记忆
                self.memory_manager.add_to_short_term({"role": "user", "content": user_request})
            except Exception as e_mem_user:
                # ... (处理记忆添加失败的逻辑与上次 agent.py 一致) ...
                self.logger.error(f"[Orchestrator - ReqID:{self.current_request_id}] 添加用户消息到短期记忆时出错: {e_mem_user}", exc_info=True)
                err_msg_mem = f"记录用户指令时发生内部记忆错误: {e_mem_user}"
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "input_validation", "status": "error", "message": err_msg_mem})
                mem_err_json = { "requestId": self.current_request_id, "llmInteractionId": f"agent_mem_err_{str(uuid4())[:6]}", "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure", "errorDetails": {"errorType": "INTERNAL_AGENT_ERROR", "errorCode": "MEMORY_ADD_USER_MSG_FAILED", "messageToUser": f"抱歉,我在记录您的指令时遇到了内部问题 ({e_mem_user})！请稍后重试。", "technicalMessage": err_msg_mem, "isDirectLlmFailure": False }, "executionPhase": "planning", "thoughtProcess": "Agent在将用户消息添加到短期记忆时遇到错误。", "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content": f"抱歉,我在记录您的指令时遇到了内部问题 ({e_mem_user})！请稍后重试。" }}}
                await status_callback({"type": "final_response", "request_id": self.current_request_id, "llm_interaction_id": mem_err_json["llmInteractionId"], "content": mem_err_json["decision"]["responseToUser"]["content"], "final_camelcase_json_if_success": None})
                return

            # 步骤 2: 主编排循环 (规划 -> 工具执行 -> 重规划 -> 响应生成)
            replanning_loop_count = 0
            current_llm_plan_camelcase_json_obj: Optional[Dict[str, Any]] = None
            agent_accepted_latest_plan_for_action = False 

            while replanning_loop_count <= self.max_replanning_attempts:
                current_planning_attempt_num = replanning_loop_count + 1
                log_prefix = f"[Orchestrator - PlanAttempt {current_planning_attempt_num} - ReqID: {self.current_request_id}]"
                self.logger.info(f"\n--- {log_prefix} 开始 ---")

                is_currently_replanning = (replanning_loop_count > 0)
                status_msg_planning_start = "正在分析指令并制定计划..." if not is_currently_replanning else f"正在尝试第 {replanning_loop_count +1 }/{self.max_replanning_attempts +1} 次重规划..." # 用户看到的尝试次数从1开始计数
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "started", "message": status_msg_planning_start, "details": {"attempt_number": current_planning_attempt_num, "max_replanning_attempts": self.max_replanning_attempts}})

                # 准备规划阶段的LLM输入
                # 从配置中获取用于提示的近期长期记忆条目数
                recent_long_term_for_prompt = self.config_loader.get_config("agent_settings.memory.recent_long_term_count_for_prompt", 7)
                memory_context = self.memory_manager.get_memory_context_for_prompt(recent_long_term_count=recent_long_term_for_prompt)
                tool_schemas_for_llm = get_tool_schemas_for_prompt(self.tools_registry)
                
                system_prompt_planning = get_planning_prompt(
                    tool_schemas_desc=tool_schemas_for_llm, 
                    memory_context=memory_context, 
                    is_replanning=is_currently_replanning, 
                    request_id=self.current_request_id
                )
                messages_for_planning = [{"role": "system", "content": system_prompt_planning}] + self.memory_manager.short_term

                # 调用LLM进行规划 (包含内部重试)
                llm_call_attempt_inner = 0 
                parsed_plan_camelcase_json_this_llm_call: Optional[Dict[str, Any]] = None
                parser_error_msg_this_llm_call: str = ""
                parsed_failed_validation_points_this_llm_call: List[Dict[str,str]] = []
                agent_accepted_latest_plan_for_action = False # 重置此标记

                while llm_call_attempt_inner <= self.planning_llm_retries: # 使用 self.planning_llm_retries (来自配置)
                    self.logger.info(f"{log_prefix} 调用规划 LLM (LLM Call Attempt {llm_call_attempt_inner + 1} of {self.planning_llm_retries + 1})...")
                    # ... (LLM 调用、解析、校验、采纳或重试逻辑与上次 agent.py 版本一致) ...
                    # (这里不再重复粘贴这部分内循环的详细代码，因为它与上一个agent.py版本中的对应部分是相同的，
                    # 关键在于 self.planning_llm_retries 是从配置来的)
                    # ... (假设这部分代码被正确地从上一个 agent.py 版本复制过来) ...
                    # --- START OF INNER LLM CALL LOOP (Copied and checked) ---
                    try:
                        llm_response_planning_raw = await self.llm_interface.call_llm( messages_for_planning, "planning", status_callback )
                        if not llm_response_planning_raw or not llm_response_planning_raw.choices: raise ConnectionError("LLM规划响应无效或缺少choices。")
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
                                try: self.memory_manager.add_to_short_term(llm_msg_obj_planning.model_dump(exclude_unset=True))
                                except Exception as e_mem_add: self.logger.error(f"{log_prefix} 添加LLM规划响应到记忆失败: {e_mem_add}")
                                break 
                        if not agent_accepted_latest_plan_for_action and llm_call_attempt_inner < self.planning_llm_retries:
                            error_to_report_cb = parser_error_msg_this_llm_call or "V1.0.0结构或内容校验失败。"
                            if parsed_failed_validation_points_this_llm_call: error_to_report_cb += " 失败点(部分): " + json.dumps(parsed_failed_validation_points_this_llm_call[:2], ensure_ascii=False) 
                            await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "llm_retry_needed", "message": f"大脑计划处理遇问题,尝试重沟通 ({error_to_report_cb[:1000]})", "details": {"llm_call_attempt": llm_call_attempt_inner + 1}})
                            if parsed_plan_camelcase_json_this_llm_call and parsed_plan_camelcase_json_this_llm_call.get("status") == "failure":
                                try: self.memory_manager.add_to_short_term(llm_msg_obj_planning.model_dump(exclude_unset=True))
                                except Exception as e_mem_add_fail: self.logger.error(f"{log_prefix} 添加LLM失败规划到记忆失败: {e_mem_add_fail}")
                            elif parser_error_msg_this_llm_call or parsed_failed_validation_points_this_llm_call:
                                 sim_err_plan_content = { "requestId": self.current_request_id, "llmInteractionId": f"agent_parser_err_{active_llm_interaction_id or str(uuid4())[:6]}", "timestampUtc": datetime.now(timezone.utc).isoformat(), "status": "failure", "errorDetails": { "errorType": "LLM_OUTPUT_VALIDATION_ERROR", "errorCode": "V1_CAMELCASE_JSON_VALIDATION_FAILED_BY_AGENT", "technicalMessage": parser_error_msg_this_llm_call or "Agent端JSON校验失败。", "isDirectLlmFailure": False, "failedValidationPoints": parsed_failed_validation_points_this_llm_call }, "executionPhase": "planning", "thoughtProcess": "Agent在解析或验证LLM上一次规划输出时发现以下问题,将请求LLM修正。", "decision": { "isCallTools": False, "toolCallRequests": [], "responseToUser": {"contentType":"text/plain", "content":""}} }
                                 try: self.memory_manager.add_to_short_term({"role": "assistant", "content": json.dumps(sim_err_plan_content, ensure_ascii=False)})
                                 except Exception as e_mem_add_parse_err: self.logger.error(f"{log_prefix} 添加Agent解析错误到记忆失败: {e_mem_add_parse_err}")
                    except Exception as e_llm_call_level: 
                        self.logger.error(f"{log_prefix} LLM调用或规划解析时发生严重错误 (LLM Call Attempt {llm_call_attempt_inner + 1}): {e_llm_call_level}", exc_info=True)
                        parser_error_msg_this_llm_call = f"LLM调用/解析严重错误: {str(e_llm_call_level)[:1000]}"
                        parsed_failed_validation_points_this_llm_call = [{"jsonPath":"root.llmCallOrParse", "issue_description": parser_error_msg_this_llm_call}]
                        if llm_call_attempt_inner < self.planning_llm_retries: await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "planning", "status": "llm_error_retrying", "message": f"与大脑沟通时发生严重错误,尝试重新连接 ({parser_error_msg_this_llm_call})", "details": {"llm_call_attempt": llm_call_attempt_inner + 1}})
                    llm_call_attempt_inner += 1
                    if agent_accepted_latest_plan_for_action: break 
                # --- END OF INNER LLM CALL LOOP ---

                if not agent_accepted_latest_plan_for_action: 
                    # ... (处理LLM调用重试均失败的逻辑，与上次 agent.py 一致) ...
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
                
                # ... (后续的工具执行或直接回复逻辑，与上次 agent.py 一致) ...
                # --- START OF POST-PLANNING LOGIC (Copied and checked) ---
                tool_requests_from_plan = current_llm_plan_camelcase_json_obj.get("decision", {}).get("toolCallRequests", []) if current_llm_plan_camelcase_json_obj else []
                if isinstance(tool_requests_from_plan, list) and current_llm_plan_camelcase_json_obj and current_llm_plan_camelcase_json_obj.get("decision",{}).get("isCallTools") is True:
                    plan_details_for_ui = []
                    for req_idx, tool_req_in_plan in enumerate(tool_requests_from_plan): plan_details_for_ui.append({ "tool_call_id": tool_req_in_plan.get("toolCallId"), "tool_name": tool_req_in_plan.get("toolName"), "tool_arguments": tool_req_in_plan.get("toolArguments", {}), "ui_hints": tool_req_in_plan.get("uiHints", {}), "status": "pending", "order": req_idx + 1 })
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
                        else: self.logger.critical(f"{log_prefix} 已达最大重规划次数,但工具执行仍失败。中止。"); final_reply_for_user = f"抱歉,执行请求时遇问题: {last_failed_tool_message_for_user} 请检查指令或稍后再试。"; final_llm_interaction_id_for_user = current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id; final_llm_camelcase_json_for_reply = None; break 
                    else: self.logger.info(f"{log_prefix} 所有工具成功执行。准备生成最终回复。"); break 
                else: 
                    self.logger.info(f"{log_prefix} 决策: 直接回复。")
                    if isinstance(response_user_obj_from_plan, dict) and response_user_obj_from_plan.get("content") is not None and \
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
                        if replanning_loop_count >= self.max_replanning_attempts: final_reply_for_user = f"抱歉,系统准备直接回复时遇内部问题: {err_msg_direct_content_critical}"; final_llm_interaction_id_for_user = current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id; final_llm_camelcase_json_for_reply = None; break 
                        else: replanning_loop_count += 1; continue
                # --- END OF POST-PLANNING LOGIC ---
            
            self.logger.debug(f"[Orchestrator - ReqID:{self.current_request_id}] 重规划循环结束。")
            
            # 响应生成阶段的LLM调用重试次数 (从 self 属性获取，它已从配置初始化)
            resp_gen_llm_retries = self.response_generation_llm_retries 

            if current_llm_plan_camelcase_json_obj and \
               current_llm_plan_camelcase_json_obj.get("status") == "success" and \
               current_llm_plan_camelcase_json_obj.get("decision",{}).get("isCallTools") is True and \
               final_llm_camelcase_json_for_reply is None: 
                
                self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 工具执行流程完成,开始生成最终响应 (LLM重试上限: {resp_gen_llm_retries})...")
                # ... (响应生成阶段的逻辑，与上次 agent.py 一致，确保使用 self.response_generation_llm_retries) ...
                # --- START OF RESPONSE GENERATION LOGIC (Copied and checked) ---
                await status_callback({"type": "general_status", "request_id": self.current_request_id, "stage": "response_generation", "status": "started", "message": "正在总结结果并生成最终回复...", "details": {"reason": "Tool execution phase completed."}})
                memory_context_resp_gen = self.memory_manager.get_memory_context_for_prompt( recent_long_term_count=self.config_loader.get_config("agent_settings.memory.recent_long_term_count_for_prompt", 7) )
                tool_schemas_resp_gen = get_tool_schemas_for_prompt(self.tools_registry) 
                system_prompt_resp_gen = get_response_generation_prompt( memory_context=memory_context_resp_gen, tool_schemas_desc=tool_schemas_resp_gen, request_id=self.current_request_id )
                messages_for_resp_gen = [{"role": "system", "content": system_prompt_resp_gen}] + self.memory_manager.short_term
                llm_call_attempt_resp_gen = 0; parsed_final_camelcase_resp_json_this_attempt: Optional[Dict[str, Any]] = None
                while llm_call_attempt_resp_gen <= resp_gen_llm_retries:
                    self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 调用响应生成 LLM (尝试 {llm_call_attempt_resp_gen + 1}/{resp_gen_llm_retries + 1})...")
                    try:
                        llm_response_final_gen_raw = await self.llm_interface.call_llm( messages_for_resp_gen, "response_generation", status_callback )
                        if not llm_response_final_gen_raw or not llm_response_final_gen_raw.choices: raise ConnectionError("LLM最终响应生成阶段响应无效。")
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
                            try: self.memory_manager.add_to_short_term(llm_msg_obj_final_gen.model_dump(exclude_unset=True))
                            except Exception as e_mem_add_final_resp: self.logger.error(f"添加最终LLM响应到记忆失败: {e_mem_add_final_resp}")
                            break 
                        else: 
                            err_msg_final_resp_gen = final_parser_err_resp or "V1.0.0最终响应JSON校验失败。"
                            if final_validation_failures_resp: err_msg_final_resp_gen += " 失败点(部分): " + json.dumps(final_validation_failures_resp[:2], ensure_ascii=False)
                            elif parsed_final_camelcase_resp_json_this_attempt and parsed_final_camelcase_resp_json_this_attempt.get("status") == "failure": err_msg_final_resp_gen = parsed_final_camelcase_resp_json_this_attempt.get("errorDetails",{}).get("technicalMessage", err_msg_final_resp_gen)
                            self.logger.error(f"[Orchestrator - ReqID:{self.current_request_id}] LLM未能生成有效最终回复 (尝试 {llm_call_attempt_resp_gen + 1}): {err_msg_final_resp_gen}")
                            if llm_call_attempt_resp_gen >= resp_gen_llm_retries: final_reply_for_user = f"抱歉,总结操作结果时发生问题。错误(部分): {err_msg_final_resp_gen[:500]}... "; final_llm_interaction_id_for_user = active_llm_interaction_id or (current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else f"error_resp_gen_{str(uuid4())[:6]}"); final_llm_camelcase_json_for_reply = None; break 
                            try: self.memory_manager.add_to_short_term(llm_msg_obj_final_gen.model_dump(exclude_unset=True))
                            except: pass 
                    except Exception as e_llm_final_gen_call: 
                        self.logger.critical(f"[Orchestrator - ReqID:{self.current_request_id}] LLM最终响应调用失败 (尝试 {llm_call_attempt_resp_gen + 1}): {e_llm_final_gen_call}", exc_info=True)
                        if llm_call_attempt_resp_gen >= resp_gen_llm_retries: final_reply_for_user = f"抱歉,系统准备最终报告时遇严重错误: {str(e_llm_final_gen_call)[:500]}... "; final_llm_interaction_id_for_user = (current_llm_plan_camelcase_json_obj.get("llmInteractionId") if current_llm_plan_camelcase_json_obj else active_llm_interaction_id or f"critical_err_resp_gen_{str(uuid4())[:6]}"); final_llm_camelcase_json_for_reply = None; break 
                    llm_call_attempt_resp_gen +=1
                # --- END OF RESPONSE GENERATION LOGIC ---
            
            elif final_llm_camelcase_json_for_reply and final_llm_camelcase_json_for_reply.get("status") == "success" and \
                 final_llm_camelcase_json_for_reply.get("decision",{}).get("isCallTools") is False:
                self.logger.info(f"[Orchestrator - ReqID:{self.current_request_id}] 使用规划阶段的直接回复JSON作最终输出。")
                final_llm_interaction_id_for_user = final_llm_camelcase_json_for_reply.get("llmInteractionId")
            elif not final_llm_camelcase_json_for_reply :
                 self.logger.error(f"[Orchestrator - ReqID:{self.current_request_id}] 流程结束时,final_llm_camelcase_json_for_reply为空,表明处理失败。")

            # ... (最终响应的组装和发送，与上次 agent.py 一致) ...
            # --- START OF FINAL RESPONSE ASSEMBLY AND SEND (Copied and checked) ---
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
            # --- END OF FINAL RESPONSE ASSEMBLY AND SEND ---

        except Exception as e_process_top_level: 
            # ... (顶层异常处理，与上次 agent.py 一致) ...
            # --- START OF TOP LEVEL EXCEPTION HANDLING (Copied and checked) ---
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
            # --- END OF TOP LEVEL EXCEPTION HANDLING ---
        finally:
            request_end_time = time.monotonic()
            duration_total = request_end_time - request_start_time
            self.logger.info(f"\n{'='*25} CircuitAgent 请求处理完毕 (ReqID: {self.current_request_id or 'N/A'}, 总耗时: {duration_total:.3f} 秒) {'='*25}\n")
            self.current_request_id = None 