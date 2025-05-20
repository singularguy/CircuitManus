# IDT_AGENT_Pro/circuitmanus/tools/executor.py
import asyncio
import json
import logging
import traceback
import inspect # 用于检查工具方法是否为协程
from uuid import uuid4
from typing import List, Dict, Any, Optional, Callable, Awaitable

# 再次使用 TYPE_CHECKING 来避免直接的循环导入
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..agent import CircuitAgent # 指向 agent.py 中的 CircuitAgent
    from ..memory.manager import MemoryManager # 指向 memory/manager.py 中的 MemoryManager

logger = logging.getLogger(__name__)

class ToolExecutor:
    """
    ToolExecutor (工具执行器) - V1.0.0 (深化修复异步调用)
    负责根据LLM的规划，执行一个或多个工具调用。
    它处理工具的查找、参数传递、执行 (包括异步工具的 await)、结果收集、
    重试逻辑、以及向UI发送状态更新。
    """
    def __init__(self, 
                 agent_instance: 'CircuitAgent', 
                 max_tool_retries: int = 3, # 与原代码 agent.__init__ 默认值不同，原为3
                 tool_retry_delay_seconds: float = 10.0):
        """
        初始化 ToolExecutor。

        Args:
            agent_instance (CircuitAgent): 对 CircuitAgent 主实例的引用。
                                           工具方法通常是 Agent 实例的方法。
            max_tool_retries (int): 单个工具执行失败时的最大重试次数。
            tool_retry_delay_seconds (float): 工具重试之间的延迟时间 (秒)。

        Raises:
            TypeError: 如果 agent_instance 不是 CircuitAgent 类型或缺少 MemoryManager。
        """
        # 在运行时进行类型检查，确保 agent_instance 的有效性
        # 注意：由于 'CircuitAgent' 可能尚未完全定义（如果此文件先被导入），
        # 这里的 isinstance 检查可能需要在 agent_instance 确实是 CircuitAgent 的最终实现后才可靠。
        # 更稳妥的方式是检查 agent_instance 是否具有预期的属性/方法。
        # from ..agent import CircuitAgent # 延迟导入以进行运行时检查
        # if not isinstance(agent_instance, CircuitAgent): # 这行可能会导致循环导入
        #    raise TypeError("ToolExecutor 需要一个 CircuitAgent 实例。")
        # 改为检查核心依赖
        if not hasattr(agent_instance, 'memory_manager') or \
           not hasattr(agent_instance, 'api_key'): # api_key 只是一个例子，代表它是 Agent
            # from ..memory.manager import MemoryManager # 延迟导入
            # if not isinstance(getattr(agent_instance, 'memory_manager', None), MemoryManager):
            #    raise TypeError("Agent 实例缺少有效的 MemoryManager。")
            # 上述 isinstance 检查同样有循环导入风险，改为鸭子类型检查或相信调用者
            logger.warning("[ToolExecutor] 初始化时 agent_instance 类型未严格校验为 CircuitAgent，依赖于调用者确保其兼容性。")


        logger.info("[ToolExecutor] 初始化工具执行器 (支持异步, 重试, 失败中止, UI回调增强 V1.0.0)。")
        self.agent_instance: 'CircuitAgent' = agent_instance
        
        # 获取 MemoryManager 的引用，虽然当前 ToolExecutor 本身不直接用，但这是 Agent 的核心组件
        # 保留此检查是为了与原代码结构对齐，并可能用于未来扩展
        if not hasattr(agent_instance, 'memory_manager'): # 再次检查以防万一
             raise TypeError("Agent 实例在 ToolExecutor 初始化时必须具有 'memory_manager' 属性。")
        # from ..memory.manager import MemoryManager # 延迟导入
        # if not isinstance(self.agent_instance.memory_manager, MemoryManager):
        #    raise TypeError("Agent 实例的 'memory_manager' 不是有效的 MemoryManager 类型。")


        self.verbose_mode: bool = getattr(agent_instance, 'verbose_mode', True) # 从Agent获取详细模式设置
        self.max_tool_retries: int = max(0, max_tool_retries) # 确保非负
        self.tool_retry_delay_seconds: float = max(0.1, tool_retry_delay_seconds) # 确保有最小延迟

        logger.info(f"[ToolExecutor] 工具执行配置: 每个工具最多重试 {self.max_tool_retries} 次,重试间隔 {self.tool_retry_delay_seconds} 秒。详细模式: {self.verbose_mode}。")

    async def _send_tool_status_update(
        self,
        status_callback: Optional[Callable[[Dict], Awaitable[None]]],
        tool_call_id: str,
        tool_name: str,
        tool_status: str, # e.g., "running", "succeeded", "failed", "retrying", "aborted_..."
        message: str,
        tool_arguments: Optional[Dict] = None,
        details: Optional[Dict] = None
    ) -> None:
        """
        内部辅助方法：发送工具执行状态更新到UI回调。
        """
        if status_callback:
            # 从 Agent 实例获取当前的请求ID
            request_id_to_send = getattr(self.agent_instance, 'current_request_id', None)
            
            arguments_summary_str = "N/A"
            if tool_arguments:
                try:
                    args_parts = []
                    for k, v in tool_arguments.items():
                        v_str = str(v) if v is not None else "None"
                        # 截断过长的参数值以优化状态消息
                        v_preview = v_str[:30] + '...' if len(v_str) > 30 else v_str
                        args_parts.append(f"{k}: {v_preview}")
                    arguments_summary_str = "; ".join(args_parts)
                    if not arguments_summary_str: arguments_summary_str = "(无参数)"
                except Exception as e_sum:
                    logger.warning(f"生成工具参数摘要时出错: {e_sum}")
                    arguments_summary_str = "(参数摘要生成错误)"
            
            update_payload = {
                "type": "tool_status_update",
                "request_id": request_id_to_send,
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "tool_arguments_summary_str": arguments_summary_str,
                "status": tool_status,
                "message": message,
                "details": details if details else {}
            }
            try:
                await status_callback(update_payload)
            except Exception as e_cb:
                logger.error(f"发送工具状态更新回调失败 (Tool: {tool_name}, Status: {tool_status}): {e_cb}", exc_info=True)


    async def execute_tool_calls(self, 
                                 tool_call_requests_from_plan: List[Dict[str, Any]], 
                                 status_callback: Optional[Callable[[Dict], Awaitable[None]]] = None
                                 ) -> List[Dict[str, Any]]:
        """
        执行LLM规划的一系列工具调用请求。

        Args:
            tool_call_requests_from_plan (List[Dict[str, Any]]): 
                一个列表，其中每个字典代表一个工具调用请求。
                每个请求字典应包含 "toolCallId", "toolName", "toolArguments", 和可选的 "uiHints"。
            status_callback (Optional[Callable[[Dict], Awaitable[None]]]): 
                用于发送实时状态更新的异步回调函数。

        Returns:
            List[Dict[str, Any]]: 
                一个列表，其中每个字典是符合LLM历史记录格式的工具结果消息。
                例如: {"role": "tool", "tool_call_id": ..., "name": ..., "content": JSON_string_of_result}
                如果某个工具失败并导致后续工具中止，中止的工具也会有对应的失败结果条目。
        """
        # 为本次执行批次生成唯一ID，方便日志追踪
        executor_id = f"exec_v1_1_3_{str(uuid4())[:8]}" 
        logger.info(f"[{executor_id}-ToolExecutor] 准备异步执行 {len(tool_call_requests_from_plan)} 个工具调用请求 (V1.0.0)...")
        
        execution_results_for_llm_history: List[Dict[str, Any]] = []

        if not tool_call_requests_from_plan:
            logger.info(f"[{executor_id}-ToolExecutor] 没有工具需要执行。")
            return []

        total_tools_in_plan = len(tool_call_requests_from_plan)

        for i, tool_request in enumerate(tool_call_requests_from_plan):
            # 从LLM的计划中提取工具调用信息
            llm_generated_tool_call_id = tool_request.get('toolCallId', f'fallback_tool_id_{str(uuid4())[:8]}')
            python_function_name = tool_request.get('toolName', 'unknown_function')
            parsed_arguments = tool_request.get('toolArguments', {}) # LLM提供的参数
            ui_hints_from_plan = tool_request.get('uiHints', {}) # LLM提供的UI提示
            
            # 构造一个用户友好的工具显示名称
            tool_display_name = ui_hints_from_plan.get('displayNameForTool') or \
                                python_function_name.replace('_tool', '').replace('_', ' ').title()

            action_result_final_for_tool: Optional[Dict[str, Any]] = None # 存储此工具最终的执行结果
            
            logger.info(f"[{executor_id}-ToolExecutor] 处理工具调用 {i + 1}/{total_tools_in_plan}: Name='{python_function_name}', LLM_ToolCallID='{llm_generated_tool_call_id}'。")
            logger.debug(f"[{executor_id}-ToolExecutor] 待执行工具 '{python_function_name}' 的参数: {parsed_arguments}。")

            # 发送 "正在运行" 状态更新
            await self._send_tool_status_update(
                status_callback, 
                llm_generated_tool_call_id, 
                python_function_name,
                "running", # 状态: 正在运行
                f"开始执行操作: {tool_display_name}...",
                tool_arguments=parsed_arguments,
                details={"ui_hints": ui_hints_from_plan}
            )

            # 从 Agent 实例中获取实际的工具方法
            tool_action_method = getattr(self.agent_instance, python_function_name, None)
            
            # 检查工具方法是否存在且是否被 @register_tool 正确标记
            if not callable(tool_action_method) or not getattr(tool_action_method, '_is_tool', False):
                err_msg_not_found = f"Agent 未实现名为 '{python_function_name}' 的已注册工具方法 (ID: {llm_generated_tool_call_id})。"
                logger.error(f"[{executor_id}-ToolExecutor] 工具未实现或未注册: {err_msg_not_found}")
                action_result_final_for_tool = {
                    "status": "failure", 
                    "message": err_msg_not_found, 
                    "error": {
                        "error_type": "TOOL_IMPLEMENTATION_ERROR", 
                        "error_code": "TOOL_NOT_FOUND_OR_NOT_REGISTERED", 
                        "technical_message": f"Action method '{python_function_name}' not found or not a registered tool in Agent."
                    }
                }
            else: # 工具方法有效，开始执行（包括重试逻辑）
                for retry_attempt in range(self.max_tool_retries + 1): # +1 因为第一次尝试不算重试
                    current_attempt_num = retry_attempt + 1 # 尝试编号从1开始
                    
                    if retry_attempt > 0: # 如果是重试
                        logger.warning(f"[{executor_id}-ToolExecutor] 工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 执行失败,正在进行第 {retry_attempt}/{self.max_tool_retries} 次重试...")
                        await self._send_tool_status_update(
                            status_callback, 
                            llm_generated_tool_call_id, 
                            python_function_name,
                            "retrying", # 状态: 正在重试
                            f"操作 '{tool_display_name}' 失败,等待 {self.tool_retry_delay_seconds} 秒后重试 (尝试 {current_attempt_num})...",
                            tool_arguments=parsed_arguments, 
                            details={"retry_count": retry_attempt, "max_retries": self.max_tool_retries, "ui_hints": ui_hints_from_plan}
                        )
                        await asyncio.sleep(self.tool_retry_delay_seconds) # 等待一段时间再重试

                    action_result_this_attempt: Optional[Dict[str, Any]] = None
                    try:
                        # 检查工具方法是同步还是异步
                        # inspect.iscoroutinefunction 需要检查原始函数，@functools.wraps 很重要
                        is_coro = inspect.iscoroutinefunction(tool_action_method)
                        logger.debug(f"[{executor_id}-ToolExecutor] (尝试 {current_attempt_num}) 调用工具 '{python_function_name}'. 是否为协程: {is_coro}.")
                        
                        if is_coro:
                            # 如果是异步工具，直接 await 调用
                            # 工具方法被期望接收一个名为 'arguments' 的字典参数
                            logger.debug(f"[{executor_id}-ToolExecutor] (尝试 {current_attempt_num}) 直接 awaiting coroutine: {python_function_name} with args: {parsed_arguments}")
                            action_result_this_attempt = await tool_action_method(arguments=parsed_arguments)
                        else:
                            # 如果是同步工具，使用 asyncio.to_thread 在单独线程中运行，避免阻塞事件循环
                            logger.debug(f"[{executor_id}-ToolExecutor] (尝试 {current_attempt_num}) running sync tool in thread: {python_function_name} with args: {parsed_arguments}")
                            action_result_this_attempt = await asyncio.to_thread(tool_action_method, arguments=parsed_arguments)
                        
                        logger.debug(f"[{executor_id}-ToolExecutor] (尝试 {current_attempt_num}) 工具 '{python_function_name}' 返回结果类型: {type(action_result_this_attempt)}, 内容预览: {str(action_result_this_attempt)[:500]}...")

                        # 校验工具返回结果的基本结构 (是否为字典，是否包含 'status' 和 'message')
                        if not isinstance(action_result_this_attempt, dict) or \
                           'status' not in action_result_this_attempt or \
                           'message' not in action_result_this_attempt:
                            err_msg_struct = f"工具 '{python_function_name}' 返回的内部结果结构无效。期望字典包含 'status' 和 'message'。"
                            logger.error(f"[{executor_id}-ToolExecutor] 工具返回结构错误 (尝试 {current_attempt_num}): {err_msg_struct}. 实际返回类型: {type(action_result_this_attempt)}, 内容(部分): {str(action_result_this_attempt)[:200]}")
                            # 强制转换为标准的失败结构，以便统一处理
                            action_result_this_attempt = { 
                                "status": "failure", 
                                "message": f"错误: 工具 '{python_function_name}' 内部返回结果结构无效。", 
                                "error": {
                                    "error_type": "TOOL_IMPLEMENTATION_ERROR", 
                                    "error_code": "INVALID_TOOL_ACTION_RESULT_STRUCTURE", 
                                    "technical_message": err_msg_struct, 
                                    "actual_return_type": str(type(action_result_this_attempt)), 
                                    "actual_return_preview": str(action_result_this_attempt)[:200]
                                }
                            }
                        else:
                            logger.info(f"[{executor_id}-ToolExecutor] 工具 '{python_function_name}' 执行完毕 (尝试 {current_attempt_num})。状态: {action_result_this_attempt.get('status', 'N/A')}。")

                        # 检查工具执行是否成功
                        if action_result_this_attempt.get("status") == "success":
                            action_result_final_for_tool = action_result_this_attempt
                            break # 成功执行，跳出重试循环
                        else: # status 不是 "success" (例如 "failure" 或其他自定义失败状态)
                            logger.warning(f"[{executor_id}-ToolExecutor] 工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 执行失败 (尝试 {current_attempt_num})。报告状态: {action_result_this_attempt.get('status')}, 消息: {action_result_this_attempt.get('message')}")
                            action_result_final_for_tool = action_result_this_attempt # 保存本次失败的结果，如果后续重试都失败，这将是最终结果

                    except TypeError as te:
                        # 通常是工具方法期望的参数与LLM提供的参数不匹配 (例如数量、名称或类型)
                        # 或者工具内部在处理参数时发生类型错误
                        err_msg_type = f"调用工具 '{python_function_name}' 时参数不匹配或内部类型错误: {te}。"
                        logger.error(f"[{executor_id}-ToolExecutor] 工具调用参数/类型错误 (尝试 {current_attempt_num}): {err_msg_type}", exc_info=True)
                        action_result_final_for_tool = {
                            "status": "failure", 
                            "message": f"错误: 调用工具 '{python_function_name}' 时参数或内部类型错误。", 
                            "error": {
                                "error_type": "TOOL_EXECUTION_ERROR", 
                                "error_code": "ARGUMENT_TYPE_MISMATCH_OR_INTERNAL_TYPE_ERROR", 
                                "technical_message": err_msg_type, 
                                "exception_details": traceback.format_exc(limit=3) # 包含部分堆栈信息
                            }
                        }
                        break # 参数错误通常是结构性问题，重试意义不大，直接跳出重试
                    except Exception as exec_err:
                        # 工具执行过程中发生未预期的其他异常
                        err_msg_exec = f"工具 '{python_function_name}' 执行期间发生意外内部错误 (尝试 {current_attempt_num}): {exec_err}"
                        logger.error(f"[{executor_id}-ToolExecutor] 工具执行内部错误: {err_msg_exec}", exc_info=True)
                        action_result_final_for_tool = {
                            "status": "failure", 
                            "message": f"错误: 执行工具 '{python_function_name}' 时发生内部错误。", 
                            "error": {
                                "error_type": "UNEXPECTED_TOOL_ERROR", 
                                "error_code": "UNEXPECTED_TOOL_EXECUTION_FAILURE", 
                                "technical_message": err_msg_exec, 
                                "exception_details": traceback.format_exc(limit=3)
                            }
                        }
                        # 对于未知错误，重试可能有效，所以不在这里 break，让重试循环继续（除非是最后一次尝试）
                    
                    # 如果这是最后一次允许的尝试 (包括初次尝试和所有重试)
                    if retry_attempt == self.max_tool_retries:
                        # 无论这次尝试是成功还是失败，它都将是此工具的最终结果
                        # action_result_final_for_tool 已经被设为最后一次尝试的结果
                        break # 退出重试循环

            # 确保 action_result_final_for_tool 有值 (理论上在循环结束后应该总是有值的)
            if action_result_final_for_tool is None:
                 # 这是一个防御性代码，正常逻辑下不应到达这里
                 logger.error(f"[{executor_id}-ToolExecutor] 内部逻辑错误: 工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 在所有重试后 action_result_final_for_tool 仍为 None。")
                 action_result_final_for_tool = {
                     "status": "failure", 
                     "message": f"错误: 工具 '{python_function_name}' 未能确定最终结果。", 
                     "error": {
                         "error_type": "TOOL_EXECUTION_ERROR", 
                         "error_code": "MISSING_TOOL_RESULT_LOGIC_ERROR", 
                         "technical_message": "Tool action_result_final_for_tool was None after retry loop."
                        }
                    }

            # 判断此工具最终是否成功
            tool_succeeded_this_cycle = (action_result_final_for_tool.get("status") == "success")

            # 发送最终状态更新 (成功或失败)
            final_tool_status_str_for_cb = "succeeded" if tool_succeeded_this_cycle else "failed"
            status_message_for_cb = action_result_final_for_tool.get('message', '操作处理完成,但无特定消息。')
            
            details_for_cb: Dict[str, Any] = {"ui_hints": ui_hints_from_plan}
            if not tool_succeeded_this_cycle: # 如果失败，附带错误信息
                details_for_cb["error"] = action_result_final_for_tool.get("error", {"error_type": "UNKNOWN_FAILURE", "technical_message": "工具最终失败,无详细错误信息。"})
            elif action_result_final_for_tool.get("data") is not None: # 如果成功且有数据，预览数据
                 try: 
                     # 尝试序列化数据并预览，避免状态消息过大
                     details_for_cb["result_data_preview"] = json.dumps(action_result_final_for_tool["data"], ensure_ascii=False, default=str, indent=None)[:1000]
                 except Exception: 
                     details_for_cb["result_data_preview"] = "(工具返回的 data 字段无法序列化进行预览)"

            await self._send_tool_status_update(
                status_callback, 
                llm_generated_tool_call_id, 
                python_function_name,
                final_tool_status_str_for_cb, 
                status_message_for_cb,
                tool_arguments=parsed_arguments, # 再次发送参数，以便UI在最终状态时仍能看到
                details=details_for_cb
            )

            # 构建用于LLM历史记录的工具结果消息
            tool_result_message_for_llm = {
                "role": "tool",
                "tool_call_id": llm_generated_tool_call_id, # 必须与LLM规划中的toolCallId对应
                "name": python_function_name, # 工具的名称
                "content": json.dumps(action_result_final_for_tool, ensure_ascii=False, default=str) # 将工具的完整结果 (包括status, message, error, data) 序列化为JSON字符串
            }
            execution_results_for_llm_history.append(tool_result_message_for_llm)
            logger.debug(f"[{executor_id}-ToolExecutor] 已记录工具 '{llm_generated_tool_call_id}' 的最终执行结果 (状态: {final_tool_status_str_for_cb}) 到LLM历史。")

            # 如果此工具执行失败，则中止后续所有工具的执行 (串行执行的关键逻辑)
            if not tool_succeeded_this_cycle:
                logger.warning(f"[{executor_id}-ToolExecutor] 工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 在所有重试后仍然失败。将中止后续计划中的工具执行。")
                # 如果当前失败的工具不是计划中的最后一个工具
                if i + 1 < total_tools_in_plan:
                    for k_aborted in range(i + 1, total_tools_in_plan):
                        aborted_tool_req = tool_call_requests_from_plan[k_aborted]
                        aborted_tool_id = aborted_tool_req.get('toolCallId', f'fallback_aborted_id_{str(uuid4())[:8]}')
                        aborted_tool_name = aborted_tool_req.get('toolName', 'unknown_aborted_tool')
                        aborted_ui_hints = aborted_tool_req.get('uiHints', {})
                        aborted_tool_display_name = aborted_ui_hints.get('displayNameForTool') or \
                                                    aborted_tool_name.replace('_tool','').replace('_',' ').title()

                        # 为被中止的工具发送状态更新
                        await self._send_tool_status_update(
                            status_callback, 
                            aborted_tool_id, 
                            aborted_tool_name,
                            "aborted_due_to_previous_failure", # 特殊状态
                            f"操作 '{aborted_tool_display_name}' 已中止,因为先前的工具 '{tool_display_name}' 执行失败。",
                            tool_arguments=aborted_tool_req.get('toolArguments',{}), # 发送其原计划参数
                            details={
                                "reason": f"Aborted due to failure of tool '{python_function_name}' (ID: {llm_generated_tool_call_id})", 
                                "ui_hints": aborted_ui_hints
                            }
                        )
                        # 为被中止的工具也生成一个失败的LLM历史记录条目
                        aborted_tool_result_for_llm_content = {
                                "status": "failure",
                                "message": f"工具 '{aborted_tool_name}' 未执行,因为前序工具 '{python_function_name}' (ID: {llm_generated_tool_call_id}) 失败。",
                                "error": {
                                    "error_type": "TOOL_CHAIN_ABORTED", 
                                    "error_code": "PRECEDING_TOOL_FAILURE", 
                                    "technical_message": f"Execution of '{aborted_tool_name}' was skipped due to the failure of tool '{python_function_name}' (ID: {llm_generated_tool_call_id})."
                                }
                            }
                        execution_results_for_llm_history.append({
                            "role": "tool", 
                            "tool_call_id": aborted_tool_id, 
                            "name": aborted_tool_name,
                            "content": json.dumps(aborted_tool_result_for_llm_content, ensure_ascii=False)
                        })
                        logger.info(f"[{executor_id}-ToolExecutor] 为中止的工具 '{aborted_tool_name}' (ID: {aborted_tool_id}) 添加了模拟失败记录到LLM历史。")
                break # 跳出主工具循环，不再执行后续工具

        total_processed_tools = len(execution_results_for_llm_history)
        logger.info(f"[{executor_id}-ToolExecutor] 工具执行流程完成。共处理/记录了 {total_processed_tools}/{total_tools_in_plan} 个计划中的工具调用 (可能因失败提前中止)。")
        return execution_results_for_llm_history