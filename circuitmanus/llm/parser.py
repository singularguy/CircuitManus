# IDT_AGENT_Pro/circuitmanus/llm/parser.py
import re
import json
import logging
from uuid import uuid4
from typing import Tuple, Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class OutputParser:
    """
    OutputParser - V1.0.0
    负责解析来自LLM的响应 (通常是包含 <think> 块和后续 JSON 对象的字符串)，
    将其转换为结构化的 Python 字典，并进行初步的模式验证。
    此版本特别适配 ManusLLMResponse-V1.0.0 CamelCase JSON 结构。
    """
    def __init__(self, agent_tools_registry: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        初始化 OutputParser。

        Args:
            agent_tools_registry (Optional[Dict[str, Dict[str, Any]]]):
                Agent 的工具注册表。用于在解析工具调用请求时，验证工具名称和参数的有效性。
                键是工具的Python函数名，值是工具的Schema字典。
        """
        logger.info("[OutputParser] 初始化输出解析器 (适配 ManusLLMResponse-V1.0.0 CamelCase JSON结构,提取 <think> 标签,增强布尔解析)。")
        self.agent_tools_registry = agent_tools_registry if agent_tools_registry else {}
        if not self.agent_tools_registry:
            logger.warning("[OutputParser] 初始化时未提供工具注册表。工具参数校验功能将受限。")

    def _validate_tool_arguments(self, tool_name: str, tool_arguments: Dict[str, Any], tool_call_id: str) -> List[Dict[str, str]]:
        """
        内部辅助方法：根据工具注册表验证LLM生成的工具参数。

        Args:
            tool_name (str): LLM请求调用的工具名称。
            tool_arguments (Dict[str, Any]): LLM为该工具提供的参数字典。
            tool_call_id (str): 当前工具调用的ID，用于错误报告。

        Returns:
            List[Dict[str, str]]: 验证失败点的列表。每个失败点是一个字典，
                                   包含 "jsonPath" 和 "issue_description"。
                                   如果验证通过，则返回空列表。
        """
        validation_errors: List[Dict[str, str]] = []
        
        # 检查工具是否存在于注册表中
        if not self.agent_tools_registry or tool_name not in self.agent_tools_registry:
            validation_errors.append({
                "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolName",
                "issue_description": f"工具 '{tool_name}' 未在 Agent 的注册表中找到。"
            })
            # 如果工具名无效，后续参数校验意义不大，直接返回
            return validation_errors

        tool_schema = self.agent_tools_registry[tool_name]
        param_schema_props = tool_schema.get("parameters", {}).get("properties", {})
        required_params = tool_schema.get("parameters", {}).get("required", [])

        # 检查必需参数是否缺失
        for req_param in required_params:
            if req_param not in tool_arguments:
                validation_errors.append({
                    "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{req_param}",
                    "issue_description": f"工具 '{tool_name}' 的必需参数 '{req_param}' 缺失。"
                })

        # 检查提供的参数是否符合Schema定义 (名称、类型)
        for arg_name, arg_value in tool_arguments.items():
            if arg_name not in param_schema_props:
                # LLM可能生成了Schema中未定义的参数
                validation_errors.append({
                    "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                    "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 是未在 Schema 中定义的未知参数。"
                })
                continue # 跳过对此未知参数的类型检查

            expected_type_str = param_schema_props[arg_name].get("type")
            
            # 处理可选参数且值为 None 的情况：通常允许 null 值用于可选参数
            is_optional_and_null_like = (arg_name not in required_params) and (arg_value is None)

            # 类型校验逻辑 (与原版保持一致)
            if expected_type_str == "string":
                if not isinstance(arg_value, str) and not is_optional_and_null_like:
                    validation_errors.append({
                        "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                        "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是字符串,但得到的是 {type(arg_value).__name__} (值: '{str(arg_value)[:50]}...')."
                    })
            elif expected_type_str == "integer":
                 if not isinstance(arg_value, int) and not is_optional_and_null_like: 
                    validation_errors.append({
                        "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                        "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是整数,但得到的是 {type(arg_value).__name__} (值: '{str(arg_value)[:50]}...')."
                    })
            elif expected_type_str == "number": # number 可以是 int 或 float
                 if not isinstance(arg_value, (int, float)) and not is_optional_and_null_like:
                    validation_errors.append({
                        "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                        "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是数字 (整数或浮点数),但得到的是 {type(arg_value).__name__} (值: '{str(arg_value)[:50]}...')."
                    })
            elif expected_type_str == "boolean":
                 if not isinstance(arg_value, bool): # 布尔值通常不接受 null 作为有效值，除非 schema 明确定义
                    validation_errors.append({
                        "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                        "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是布尔值 (true/false),但得到的是 {type(arg_value).__name__} (值: '{str(arg_value)[:50]}...')."
                    })
            elif expected_type_str == "object":
                 if not isinstance(arg_value, dict) and not is_optional_and_null_like:
                    validation_errors.append({
                        "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                        "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是对象(字典),但得到的是 {type(arg_value).__name__}."
                    })
            elif expected_type_str == "array":
                 if not isinstance(arg_value, list) and not is_optional_and_null_like:
                    validation_errors.append({
                        "jsonPath": f"decision.toolCallRequests[toolCallId={tool_call_id}].toolArguments.{arg_name}",
                        "issue_description": f"工具 '{tool_name}' 的参数 '{arg_name}' 期望是数组(列表),但得到的是 {type(arg_value).__name__}."
                    })
            # 可以根据需要添加对其他类型 (如 null, enum) 的校验
        return validation_errors


    def parse_llm_response_to_structured_json(self, 
                                              llm_api_response_message: Any, # 来自 ZhipuAI SDK 的 Message 对象
                                              execution_phase: str
                                              ) -> Tuple[Optional[Dict[str, Any]], str, List[Dict[str,str]]]:
        """
        解析LLM API的响应消息，提取 <think> 块和后续的 JSON 对象。
        同时对提取的JSON对象进行V1.0.0-CamelCase规范的结构和基本内容校验。

        Args:
            llm_api_response_message (Any): LLM API返回的原始消息对象 
                                           (期望是 ZhipuAI SDK 的 `Message` 类型，至少包含 `content` 属性)。
            execution_phase (str): 当前的执行阶段 ("planning" 或 "response_generation")，
                                   用于校验LLM响应中的 `executionPhase` 字段。

        Returns:
            Tuple[Optional[Dict[str, Any]], str, List[Dict[str,str]]]:
            - 第一个元素: 如果解析和初步校验成功，则为解析后的JSON对象 (Python字典)；否则为 None。
                         此字典中的 `thoughtProcess` 字段会被优先替换为从 `<think>` 块提取的内容。
            - 第二个元素: 如果发生错误，则为错误消息字符串；否则为空字符串。
            - 第三个元素: 包含详细校验失败点的列表 (如果校验失败)；否则为空列表。
        """
        # 为每次解析生成一个唯一的ID，方便在日志中追踪特定解析过程
        parser_id = f"parse_{str(uuid4())[:8]}"
        logger.debug(f"[{parser_id}-OutputParser] 开始解析 LLM 响应 (阶段: {execution_phase})...")
        
        parsed_json_dict: Optional[Dict[str, Any]] = None
        error_message: str = ""
        failed_validation_points_list: List[Dict[str, str]] = [] # 存储结构或内容校验失败的点
        extracted_thought_process: Optional[str] = None

        # 1. 检查输入是否有效
        if llm_api_response_message is None or not hasattr(llm_api_response_message, 'content'):
            error_message = "LLM 响应对象 (Message) 为 None 或缺少 'content' 属性。"
            logger.error(f"[{parser_id}-OutputParser] 解析失败: {error_message}")
            return None, error_message, [{"jsonPath": "root.messageObject", "issue_description": error_message}]

        raw_content = getattr(llm_api_response_message, 'content', None)
        if not isinstance(raw_content, str) or not raw_content.strip(): # 确保是字符串且非空
            error_message = "LLM 响应内容 (content 字段) 为空、非字符串或仅包含空白字符。"
            logger.error(f"[{parser_id}-OutputParser] 解析失败: {error_message} (类型: {type(raw_content)})")
            return None, error_message, [{"jsonPath": "messageObject.content", "issue_description": error_message}]

        logger.debug(f"[{parser_id}-OutputParser] 接收到的原始 LLM content (完整):\n{raw_content}")

        # 2. 提取 <think>...</think> 块 (如果存在)
        content_to_parse_for_json = raw_content # 默认情况下，整个内容用于JSON解析
        # 使用 re.DOTALL 使 '.' 匹配换行符，re.IGNORECASE 忽略大小写
        think_match = re.search(r"<think>(.*?)</think>", raw_content, re.DOTALL | re.IGNORECASE)

        if think_match:
            extracted_thought_process = think_match.group(1).strip()
            # JSON内容被认为是 <think> 块之后的部分
            content_to_parse_for_json = raw_content[think_match.end():].strip() 
            logger.info(f"[{parser_id}-OutputParser] 成功提取到 <think>...</think> 内容。")
            logger.debug(f"[{parser_id}-OutputParser] 提取的思考过程 (预览):\n{extracted_thought_process[:1000]}...")
            logger.debug(f"[{parser_id}-OutputParser] 剩余内容待解析为JSON (预览):\n{content_to_parse_for_json[:1000]}...")
            if not content_to_parse_for_json: # 如果 <think> 块后没有任何内容
                 error_message = "LLM 响应包含 <think> 块但之后没有内容可解析为 JSON。"
                 logger.error(f"[{parser_id}-OutputParser] 解析失败: {error_message}")
                 return None, error_message, [{"jsonPath": "root_after_think_block", "issue_description": error_message}]
        else:
            logger.warning(f"[{parser_id}-OutputParser] 未在LLM响应中找到有效的 <think>...</think> 块。将尝试按旧方式解析整个内容为JSON。")

        # 3. 预处理 JSON 字符串 (移除 Markdown 代码块标记等)
        json_string_to_parse = content_to_parse_for_json.strip()
        
        # 尝试从 Markdown JSON 代码块中提取 (```json ... ```)
        # re.DOTALL 使得 '.' 可以匹配换行符，这对于跨越多行的JSON块很重要
        match_md_json = re.search(r"```json\s*(.*?)\s*```", json_string_to_parse, re.DOTALL | re.IGNORECASE)
        if match_md_json:
            json_string_to_parse = match_md_json.group(1).strip()
            logger.debug(f"[{parser_id}-OutputParser] 从 Markdown 代码块中提取到 JSON 字符串。")
        else:
            # 如果没有 Markdown 代码块，检查 JSON 是否被前缀文本污染
            first_brace = json_string_to_parse.find('{')
            # 确保找到的 '{' 确实是 JSON 对象的开始，而不是某个字符串值内部的 '{'
            # 简单的启发式：如果 '{' 前面有大量非空白文本，可能需要剥离
            if first_brace > 0 : # 如果 '{' 不是第一个字符
                # 检查 '{' 之前的文本是否真的是 "垃圾" 前缀
                # 一个更稳健的方法可能是尝试从第一个 '{' 开始解析，如果失败，再尝试其他策略
                # 但这里我们先采用原版的简单逻辑：如果前面有东西，就警告并尝试从 '{' 开始
                prefix_content = json_string_to_parse[:first_brace].strip()
                if prefix_content: # 只有当确有非空白前缀时才警告
                    logger.warning(f"[{parser_id}-OutputParser] 在预期的 JSON 开头 '{{' 之前检测到非空白内容: '{prefix_content[:1000]}...'。将尝试从 '{{' 开始解析。")
                json_string_to_parse = json_string_to_parse[first_brace:]
            elif first_brace == -1 : # 如果连 '{' 都找不到
                error_message = "无法在 LLM 响应内容 (post-<think>或完整) 中找到 JSON 对象的起始 '{'。"
                logger.error(f"[{parser_id}-OutputParser] 解析失败: {error_message} 原始响应预览 (post-<think>或完整): {json_string_to_parse[:1000]}...")
                return None, error_message, [{"jsonPath": "content_for_json_parsing", "issue_description": error_message}]
        
        # (可选) 进一步清理：移除可能存在的尾随非JSON字符，例如LLM有时会在JSON后添加额外的注释或句子
        # 但这需要更复杂的逻辑，例如找到匹配的最后一个 '}'，并确保其后的内容确实是多余的。
        # 为保持与原版一致，此处暂不添加此复杂清理。

        logger.debug(f"[{parser_id}-OutputParser] 预处理后,准备解析的 JSON 字符串 (完整):\n{json_string_to_parse}")

        # 4. 解析 JSON 字符串
        try:
            parsed_json_dict = json.loads(json_string_to_parse)
            logger.info(f"[{parser_id}-OutputParser] JSON 字符串成功解析为字典。")
        except json.JSONDecodeError as json_err:
            error_message = f"JSON 解析失败: {json_err}。"
            # 记录错误时，包含出错位置和部分原始字符串，有助于调试
            logger.error(f"[{parser_id}-OutputParser] {error_message} (位置: {json_err.pos}, 行: {json_err.lineno}, 列: {json_err.colno}). Raw JSON string (截断): '{json_string_to_parse[:1000]}...'")
            return None, error_message, [{"jsonPath": "root_json_parsing", "issue_description": f"JSONDecodeError: {json_err.msg} at pos {json_err.pos}"}]
        except Exception as e: # 捕获其他可能的解析时错误
            error_message = f"解析 LLM 响应时发生未知错误: {e}"
            logger.error(f"[{parser_id}-OutputParser] 解析时未知错误: {error_message}", exc_info=True)
            return None, error_message, [{"jsonPath": "root_json_parsing", "issue_description": f"Unexpected parsing error: {e}"}]

        # 5. 结构和内容校验 (针对V1.0.0-CamelCase规范)
        if not isinstance(parsed_json_dict, dict):
            error_message = "解析后的结果不是一个 JSON 对象 (字典)。"
            logger.error(f"[{parser_id}-OutputParser] 结构验证失败: {error_message} (得到类型: {type(parsed_json_dict)})")
            # 返回解析出的非字典内容，可能有助于调试LLM的输出
            return parsed_json_dict, error_message, [{"jsonPath": "root_json_parsing", "issue_description": error_message}]


        # 将提取的 <think> 块内容合并到解析后的 JSON 中
        if extracted_thought_process is not None:
            if "thoughtProcess" in parsed_json_dict and parsed_json_dict["thoughtProcess"] and \
               parsed_json_dict["thoughtProcess"].strip() != extracted_thought_process: # 检查是否与JSON内部已有的不同
                logger.warning(f"[{parser_id}-OutputParser] LLM提供了<think>块和JSON内部的thoughtProcess字段,内容不完全一致。将优先使用<think>块内容。JSON内部原文(部分): '{str(parsed_json_dict['thoughtProcess'])[:200]}...'")
            parsed_json_dict["thoughtProcess"] = extracted_thought_process
            logger.info(f"[{parser_id}-OutputParser] 已将<think>块内容置于parsed_json_dict['thoughtProcess']。")
        elif "thoughtProcess" not in parsed_json_dict or not parsed_json_dict.get("thoughtProcess", "").strip():
             # 如果没有<think>块，且JSON内部的thoughtProcess也为空或缺失
             logger.warning(f"[{parser_id}-OutputParser] LLM未提供<think>块,且JSON内部的thoughtProcess为空或缺失。思考过程可能不完整。")


        # --- 开始详细的字段校验 ---
        # 校验顶级必需字段
        required_top_level_fields = ["requestId", "llmInteractionId", "timestampUtc", "status", "executionPhase", "thoughtProcess", "decision"]
        for field in required_top_level_fields:
            if field not in parsed_json_dict:
                failed_validation_points_list.append({"jsonPath": field, "issue_description": f"缺少必需的顶级字段 '{field}'。"})

        # 校验 'status' 字段
        status_val = parsed_json_dict.get("status")
        if status_val not in ["success", "failure"]:
            failed_validation_points_list.append({"jsonPath": "status", "issue_description": f"字段 'status' 的值 '{status_val}' 无效,必须是 'success' 或 'failure'。"})

        # 校验 'executionPhase' 字段
        exec_phase_val = parsed_json_dict.get("executionPhase")
        if exec_phase_val not in ["planning", "response_generation"]:
            failed_validation_points_list.append({"jsonPath": "executionPhase", "issue_description": f"字段 'executionPhase' 的值 '{exec_phase_val}' 无效,必须是 'planning' 或 'response_generation'。"})
        elif exec_phase_val != execution_phase: # 确保LLM报告的阶段与Agent期望的阶段一致
             failed_validation_points_list.append({"jsonPath": "executionPhase", "issue_description": f"LLM报告的 'executionPhase' ('{exec_phase_val}') 与 Agent 期望的阶段 ('{execution_phase}') 不匹配。"})

        # 校验 'errorDetails' (当 status 为 'failure' 时)
        if status_val == "failure":
            error_details_obj = parsed_json_dict.get("errorDetails")
            if not isinstance(error_details_obj, dict):
                failed_validation_points_list.append({"jsonPath": "errorDetails", "issue_description": "当 'status' 为 'failure' 时, 'errorDetails' 必须是一个对象。"})
            else:
                # 检查 errorDetails 内部的必需字段
                if not isinstance(error_details_obj.get("errorType"), str) or not error_details_obj.get("errorType","").strip():
                    failed_validation_points_list.append({"jsonPath": "errorDetails.errorType", "issue_description": "'errorDetails' 对象中缺少有效的 'errorType' 字符串。"})
                if not isinstance(error_details_obj.get("errorCode"), str) or not error_details_obj.get("errorCode","").strip():
                    failed_validation_points_list.append({"jsonPath": "errorDetails.errorCode", "issue_description": "'errorDetails' 对象中缺少有效的 'errorCode' 字符串。"})
                if not isinstance(error_details_obj.get("technicalMessage"), str) or not error_details_obj.get("technicalMessage","").strip():
                    failed_validation_points_list.append({"jsonPath": "errorDetails.technicalMessage", "issue_description": "'errorDetails' 对象中缺少有效的 'technicalMessage' 字符串。"})
                # isDirectLlmFailure 字段是布尔型，必须存在
                if "isDirectLlmFailure" not in error_details_obj or not isinstance(error_details_obj.get("isDirectLlmFailure"), bool):
                    logger.warning(f"[{parser_id}-OutputParser] 'errorDetails.isDirectLlmFailure' 字段缺失或类型不为布尔。Agent将假定为False。LLM输出应包含此字段。")
                    failed_validation_points_list.append({"jsonPath": "errorDetails.isDirectLlmFailure", "issue_description": "'errorDetails' 对象中缺少有效的布尔字段 'isDirectLlmFailure'。"})
        elif status_val == "success" and parsed_json_dict.get("errorDetails") is not None: # status 为 success 时, errorDetails 应为 null
             failed_validation_points_list.append({"jsonPath": "errorDetails", "issue_description": "当 'status' 为 'success' 时, 'errorDetails' 字段必须为 null 或不存在。"})

        # 校验 'thoughtProcess' 字段 (即使优先用 <think> 块，JSON中的也应符合类型)
        if "thoughtProcess" in parsed_json_dict: # 检查字段是否存在
            if not isinstance(parsed_json_dict.get("thoughtProcess"), str):
                 # 如果存在但类型不正确 (例如 LLM 错误地给了一个对象或null以外的非字符串)
                 # 注意: 如果 <think> 块存在，它已经被强制设为字符串了。这里主要针对没有 <think> 块的情况。
                logger.warning(f"[{parser_id}-OutputParser] JSON内部的 'thoughtProcess' 字段存在但类型不正确 (应为字符串，得到 {type(parsed_json_dict.get('thoughtProcess')).__name__})。")
                failed_validation_points_list.append({"jsonPath": "thoughtProcess", "issue_description": "'thoughtProcess' 字段如果存在,必须是字符串。"})
            # 空字符串是允许的
        # 如果 thoughtProcess 字段不存在 (但它是必需的)，上面的 required_top_level_fields 检查会捕捉到。

        # 校验 'decision' 对象及其内部结构
        decision_obj = parsed_json_dict.get("decision")
        if not isinstance(decision_obj, dict):
            failed_validation_points_list.append({"jsonPath": "decision", "issue_description": "'decision' 字段必须是一个对象。"})
        else:
            # 校验 'decision.isCallTools'，并尝试转换字符串 'true'/'false' 为布尔值
            raw_is_call_tools_val = decision_obj.get("isCallTools")
            is_call_tools_val_parsed: Optional[bool] = None # 用于存储解析后的布尔值
            
            if isinstance(raw_is_call_tools_val, bool):
                is_call_tools_val_parsed = raw_is_call_tools_val
            elif isinstance(raw_is_call_tools_val, str):
                # 不区分大小写地比较
                if raw_is_call_tools_val.lower() == 'true':
                    is_call_tools_val_parsed = True
                elif raw_is_call_tools_val.lower() == 'false':
                    is_call_tools_val_parsed = False
            
            if is_call_tools_val_parsed is None: # 如果无法解析为布尔值
                failed_validation_points_list.append({"jsonPath": "decision.isCallTools", "issue_description": f"'decision.isCallTools' 值 '{raw_is_call_tools_val}' (类型: {type(raw_is_call_tools_val).__name__}) 无效。必须是布尔类型或可解析为布尔的字符串('true'/'false')。"})
            else:
                # 用解析后的布尔值覆盖原始值，方便后续处理
                decision_obj["isCallTools"] = is_call_tools_val_parsed 
                logger.debug(f"[{parser_id}-OutputParser] 'isCallTools' (原始值: {raw_is_call_tools_val}, 类型: {type(raw_is_call_tools_val).__name__}) 被解析为布尔值: {is_call_tools_val_parsed}。")

            # 校验 'decision.toolCallRequests'
            tool_call_requests = decision_obj.get("toolCallRequests")
            if is_call_tools_val_parsed is True: # 仅当计划调用工具时才深入校验
                if not isinstance(tool_call_requests, list):
                    failed_validation_points_list.append({"jsonPath": "decision.toolCallRequests", "issue_description": "当 'isCallTools' 为 True 时, 'toolCallRequests' 必须是一个列表。"})
                elif not tool_call_requests: # 列表为空但 isCallTools 为 True
                    logger.warning(f"[{parser_id}-OutputParser] 'isCallTools' 为 True 但 'toolCallRequests' 列表为空。这可能是一个规划逻辑问题，但符合 schema (空列表)。")
                    # 根据需求，这里也可以视为一个校验失败点，如果业务逻辑不允许这种情况
                elif tool_call_requests: # 列表非空，校验每一项
                    for i, tool_req_item in enumerate(tool_call_requests):
                        item_path_prefix = f"decision.toolCallRequests[{i}]"
                        if not isinstance(tool_req_item, dict):
                            failed_validation_points_list.append({"jsonPath": item_path_prefix, "issue_description": "列表中的每个工具调用请求必须是对象。"}); continue # 跳过对此项的后续校验

                        tool_call_id = tool_req_item.get("toolCallId")
                        if not isinstance(tool_call_id, str) or not tool_call_id.strip():
                            failed_validation_points_list.append({"jsonPath": f"{item_path_prefix}.toolCallId", "issue_description": "缺少有效的 'toolCallId' 字符串。"})

                        tool_name = tool_req_item.get("toolName")
                        if not isinstance(tool_name, str) or not tool_name.strip():
                            failed_validation_points_list.append({"jsonPath": f"{item_path_prefix}.toolName", "issue_description": "缺少有效的 'toolName' 字符串。"})

                        tool_arguments = tool_req_item.get("toolArguments")
                        if not isinstance(tool_arguments, dict):
                            failed_validation_points_list.append({"jsonPath": f"{item_path_prefix}.toolArguments", "issue_description": "'toolArguments' 必须是一个对象。"})
                        elif tool_name and isinstance(tool_name, str) and tool_name.strip(): # 仅当工具名有效时才校验参数
                            # 使用内部方法校验工具参数 (需要 agent_tools_registry)
                            arg_validation_errors = self._validate_tool_arguments(
                                tool_name, 
                                tool_arguments, 
                                tool_call_id if (tool_call_id and isinstance(tool_call_id, str) and tool_call_id.strip()) else f"index_{i}"
                            )
                            failed_validation_points_list.extend(arg_validation_errors)
                        
                        # uiHints 是可选的，但如果存在，必须是对象
                        ui_hints = tool_req_item.get("uiHints")
                        if ui_hints is not None and not isinstance(ui_hints, dict):
                            failed_validation_points_list.append({"jsonPath": f"{item_path_prefix}.uiHints", "issue_description": "'uiHints' 如果存在,必须是一个对象。"})

            elif is_call_tools_val_parsed is False: # 如果不调用工具
                # toolCallRequests 应该是 null 或空列表
                if tool_call_requests is not None and (not isinstance(tool_call_requests, list) or tool_call_requests): # 不是null, 也不是空列表
                    failed_validation_points_list.append({"jsonPath": "decision.toolCallRequests", "issue_description": "当 'isCallTools' 为 False 时, 'toolCallRequests' 必须是 null 或空列表 []。"})

            # 校验 'decision.responseToUser' 对象
            response_user_obj = decision_obj.get("responseToUser")
            if not isinstance(response_user_obj, dict):
                failed_validation_points_list.append({"jsonPath": "decision.responseToUser", "issue_description": "'responseToUser' 必须是一个对象。"})
            else:
                if not isinstance(response_user_obj.get("contentType"), str) or not response_user_obj.get("contentType","").strip():
                     failed_validation_points_list.append({"jsonPath": "decision.responseToUser.contentType", "issue_description": "'responseToUser' 对象缺少有效的 'contentType' 字符串。"})

                resp_content = response_user_obj.get("content") # content 可以是空字符串
                if not isinstance(resp_content, str): # 但必须是字符串类型
                     failed_validation_points_list.append({"jsonPath": "decision.responseToUser.content", "issue_description": "'responseToUser.content' 必须是字符串。"})
                
                # 特定逻辑：如果直接回复用户 (isCallTools=False)，则 content 不应为空（除非在规划阶段且有过渡消息）
                # 这个校验更偏向业务逻辑而非纯粹的schema校验，但LLM被指示这么做
                if is_call_tools_val_parsed is False and (resp_content is None or resp_content.strip() == ""):
                     # 在响应生成阶段，如果直接回复，content 必须非空
                     if execution_phase == "response_generation":
                         failed_validation_points_list.append({"jsonPath": "decision.responseToUser.content", "issue_description": "在响应生成阶段,当不调用工具时, 'responseToUser.content' 必须是有效的非空字符串。"})
                     # 在规划阶段，如果直接回复 (isCallTools=False)，content 也应该非空
                     # 但原版代码似乎对规划阶段的过渡消息 content 为空有容忍，这里保持一致，只在 response_generation 阶段强校验
                     # 若要更严格：else: failed_validation_points_list.append(...) for planning phase direct reply

                # 校验 'suggestionsForNextSteps' (可选)
                suggestions = response_user_obj.get("suggestionsForNextSteps")
                if suggestions is not None: # 如果存在
                    if not isinstance(suggestions, list):
                        failed_validation_points_list.append({"jsonPath": "decision.responseToUser.suggestionsForNextSteps", "issue_description": "'suggestionsForNextSteps' 如果存在,必须是一个列表。"})
                    else:
                        for j, sugg_item in enumerate(suggestions):
                            sugg_path_prefix = f"decision.responseToUser.suggestionsForNextSteps[{j}]"
                            if not isinstance(sugg_item, dict):
                                failed_validation_points_list.append({"jsonPath": sugg_path_prefix, "issue_description": "列表中的每个建议必须是对象。"}); continue
                            if not isinstance(sugg_item.get("textForUser"), str) or not sugg_item.get("textForUser","").strip():
                                failed_validation_points_list.append({"jsonPath": f"{sugg_path_prefix}.textForUser", "issue_description": "建议对象缺少有效的 'textForUser' 字符串。"})
                            # 可以添加对 actionType, actionPayload 等字段的进一步校验

                # 校验 'requiresUserClarificationForCurrentRequest' (可选)
                clarification_flag = response_user_obj.get("requiresUserClarificationForCurrentRequest")
                if clarification_flag is not None and not isinstance(clarification_flag, bool):
                     failed_validation_points_list.append({"jsonPath": "decision.responseToUser.requiresUserClarificationForCurrentRequest", "issue_description": "'requiresUserClarificationForCurrentRequest' 如果存在,必须是布尔类型。"})

        # 校验 'diagnostics' 对象 (可选)
        diagnostics_obj = parsed_json_dict.get("diagnostics")
        if diagnostics_obj is not None and not isinstance(diagnostics_obj, dict):
            failed_validation_points_list.append({"jsonPath": "diagnostics", "issue_description": "'diagnostics' 如果存在,必须是一个对象。"})
            # 可以添加对 diagnostics 内部字段的校验，如 llmConfidenceScoreForThisOutput 类型等

        # 6. 根据校验结果返回
        if failed_validation_points_list:
            # 构建包含所有失败点的错误消息
            error_message_parts = [f"JSON 结构或内容验证失败 (共 {len(failed_validation_points_list)} 点):"]
            for err_point in failed_validation_points_list:
                error_message_parts.append(f"  -路径 '{err_point['jsonPath']}': {err_point['issue_description']}")
            error_message = "\n".join(error_message_parts)

            # 记录详细错误和部分JSON内容
            json_content_for_log = "(无法序列化进行日志记录)"
            try:
                json_content_for_log = json.dumps(parsed_json_dict, indent=2, ensure_ascii=False)
            except Exception:
                json_content_for_log = str(parsed_json_dict)[:2000] # 尽力记录

            logger.error(f"[{parser_id}-OutputParser]\n{error_message}\n解析的 JSON 内容 (可能不完整或无效):\n{json_content_for_log}")
            # 返回解析出的字典（即使有错，可能部分有用），错误消息，和失败点列表
            return parsed_json_dict, error_message, failed_validation_points_list

        # 如果所有校验通过
        logger.info(f"[{parser_id}-OutputParser] LLM 响应 (阶段: {execution_phase}, LLM_ID: {parsed_json_dict.get('llmInteractionId', 'N/A')}) 已成功解析并验证为 ManusLLMResponse-V1.0.0兼容结构 (思考过程来源: {'<think> block' if extracted_thought_process else 'JSON field'})！")
        return parsed_json_dict, "", [] # 成功，无错误消息，无失败点