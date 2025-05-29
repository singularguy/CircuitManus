# IDT_AGENT_NATIVE/circuitmanus/prompts/templates.py
import logging
from uuid import uuid4
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def get_tool_schemas_for_prompt(tools_registry: Dict[str, Dict[str, Any]]) -> str:
    """
    根据 Agent 的工具注册表，生成一段格式化的文本描述，供 LLM 在提示中使用。
    这段文本详细说明了每个可用工具的名称、描述和参数规范。
    (此函数无需修改，保持原样)
    """
    if not tools_registry:
        logger.warning("[PromptHelper] tools_registry 为空，将返回无可用工具的提示。")
        return "  (当前无可用工具)"
    
    tool_schemas_parts = []
    sorted_tool_names = sorted(tools_registry.keys()) 

    for tool_name in sorted_tool_names:
        schema = tools_registry[tool_name]
        desc = schema.get('description', '无描述。')
        params_schema = schema.get('parameters', {})
        props_schema = params_schema.get('properties', {})
        req_params = params_schema.get('required', [])

        param_desc_segments = []
        if props_schema:
            sorted_param_names = sorted(props_schema.keys())
            for param_name in sorted_param_names: 
                param_details_dict = props_schema[param_name]
                param_type = param_details_dict.get('type','any')
                is_required_str = "必须 (required)" if param_name in req_params else "可选 (optional)"
                param_description = param_details_dict.get('description','无参数描述')
                
                enum_values = param_details_dict.get('enum')
                enum_desc = ""
                if enum_values and isinstance(enum_values, list):
                    # 使用 repr(v) 来确保字符串值被正确引用，例如 "option1" 而不是 option1
                    enum_desc = f" 可选值: {', '.join(map(repr, enum_values))}。" 
                
                param_desc_segments.append(
                    f"    - 参数名 `{param_name}`:\n"
                    f"      - 类型: `{param_type}`\n"
                    f"      - 是否必需: {is_required_str}\n"
                    f"      - 描述: {param_description}{enum_desc}"
                )
        elif params_schema.get("type") == "object" and not props_schema :
             param_desc_segments = ["    - 此工具不接受任何参数(参数对象 `toolArguments` 应为空对象 `{}`)。"]
        else:
             param_desc_segments = ["    - (此工具的参数定义似乎不完整或无参数)"]

        tool_schemas_parts.append(
            f"  - 工具名称: `{tool_name}`\n"
            f"    工具描述: {desc}\n"
            f"  工具参数详情 (这些参数应放在 `toolArguments` 对象内部):\n"
            f"{chr(10).join(param_desc_segments)}" # 使用换行符 chr(10) 以确保格式正确
        )
    
    return "\n\n".join(tool_schemas_parts)


def get_planning_prompt(tool_schemas_desc: str,
                             memory_context: str,
                             is_replanning: bool = False,
                             request_id: Optional[str] = None,
                             # 新增参数: 是否启用中文深度思考
                             enable_deep_thinking_chinese: bool = False 
                             ) -> str:
    current_timestamp_utc = datetime.now(timezone.utc).isoformat()
    llm_interaction_id_example_plan_prefix = f"plan_ex_llm_id_{str(uuid4())[:6]}"
    example_prev_tool_call_id = f"tc_ex_prev_fail_{str(uuid4())[:6]}"

    # 根据 enable_deep_thinking_chinese 动态调整 <think> 块和 thoughtProcess JSON字段的语言提示后缀
    think_block_language_instruction = "并且【请使用中文进行思考和阐述此部分内容】" if enable_deep_thinking_chinese else ""
    json_thought_process_language_note = "（如果<think>块使用中文思考，此总结也建议使用中文）" if enable_deep_thinking_chinese else ""


    reasoning_model_instructions = (
        "\n【重要: Reasoning Model 输出规范 (V1.0.0)】\n"
        f"1.  **思考过程**: 您的详细思考过程、分析、逐步推理和决策逻辑【必须】包含在 `<think>...</think>` 标签内{think_block_language_instruction}，并放在您回复的最开始部分。\n"
        "2.  **JSON 输出**: 在 `</think>` 标签之后,您【必须】输出一个严格符合下面描述的V1.0-CamelCaseJSON格式的单个JSON对象。此JSON对象应被三个反引号和'json'标记包围 (即 ```json ... ```)。JSON中所有key【必须】使用camelCase (例如: `isCallTools`, `toolCallRequests`, `requestId`).\n"
        f"3.  **`thoughtProcess` 字段 (in JSON)**: JSON对象内部的 `thoughtProcess` 字段现在是次要的。它可以是一个简短的总结或留空 ( `\"\"` ){json_thought_process_language_note}，因为您的主要思考过程已在 `<think>...</think>` 块中。Agent将优先使用 `<think>` 块中的内容作为思考日志。\n"
    )

    replanning_guidance_think_instruction = f"请在您的 `<think>...</think>` 块中{think_block_language_instruction}：\n"
    replanning_guidance = ""
    if is_replanning:
        replanning_guidance = (
            "\n【重要: 重规划指示 (V1.0.0 - Reasoning Model)】\n"
            f"您当前正在进行重规划。这意味着您之前的规划或工具执行遇到了问题。{replanning_guidance_think_instruction}"
            "1.  **仔细分析失败原因**: 详细检查对话历史中的 `role: tool` 消息 (`content` JSON内的 `status: \"failure\"`, `message`, `errorDetails`) 和 `role: assistant` 消息中可能的Agent解析/校验错误 (`errorDetails.failedValidationPoints`)。\n"
            "2.  **参考当前电路状态**: 【务必】仔细查阅 `memory_context` 中的【当前电路状态】。您的新计划【必须】基于当前实际存在的元件和连接。不要不必要地重新添加已存在的元件。\n"
            "3.  **处理抽象节点**: 若涉及连接到 'INPUT', 'OUTPUT', 'GND' 等未作为元件存在的抽象节点失败,优先规划使用 `add_component_tool` (如 `component_type: 'Terminal'`) 创建它们,然后再连接。\n"
            "4.  **制定修正计划**: 基于以上分析,制定一个【全新的、修正了先前问题的计划】。这应在您的 `<think>...</think>` 块中清晰阐述。\n"
            "然后,在 `</think>` 之后输出符合V1.0-CamelCaseJSON规范的JSON。如果这个【新JSON本身的顶层 `status` 字段必须设置为 `'success'`】(因为您成功地为【当前这次思考和规划】输出了一个结构完整且逻辑合理的V1.0-CamelCaseJSON JSON)。\n"
            "5.  **无法解决的情况**: 如果分析后认为无法完成用户核心请求,则在 `<think>...</think>` 中解释,并在 `</think>` 后的JSON中制定一个【直接回复用户并解释情况的计划】 (`status: 'success'`, `isCallTools: False`).\n"
            "6.  **真正意义上的规划失败**: 只有当您在【当前这次重规划尝试中】,由于自身的理解困难、无法形成任何有效的 `<think>...</think>` 块或后续的V1.0-CamelCaseJSON JSON结构时,才应将后续JSON的顶层 `status` 字段设为 `'failure'`。\n"
            "**核心原则**: 不要因为*过去*的工具执行失败,就将您*当前新制定*的计划的JSON标记为 `status: 'failure'`. `status` 反映的是您【当前这次生成JSON这个行为本身】的成功与否。\n"
        )

    # JSON Schema 描述 (保持不变，此处不重复粘贴，确保与原文件一致)
    json_schema_description_for_prompt = """
```json
{
  "requestId": "string_or_null_当前用户请求周期的ID_如果系统提示中提供了此值请原样返回_否则为null",
  "llmInteractionId": "string_必须是本次LLM响应的唯一ID_例如_plan_llm_id_后跟8位随机字符_如_plan_llm_id_a1b2c3d4",
  "timestampUtc": "string_当前UTC时间戳_ISO_8601格式_例如_2024-07-16T12:00:00.000Z",
  "status": "string_必须是 'success' 或 'failure'._表示本次JSON输出是否由LLM为当前阶段成功生成。",
  "errorDetails": { 
    "errorType": "string_enum_高级错误类别_例如_PLANNING_ERROR_LLM_OUTPUT_VALIDATION_ERROR_INTERNAL_LOGIC_ERROR",
    "errorCode": "string_特定错误代码_例如_JSON_MALFORMED_MISSING_REQUIRED_FIELD_TOOL_PARAMS_INVALID",
    "messageToUser": "string_用户友好的解释_如果此错误与用户操作直接相关或适合用户查看。否则为通用Agent错误消息。",
    "technicalMessage": "string_详细的技术错误消息_用于日志记录和调试_这是LLM认为其自身输出生成过程中出现的问题。",
    "isDirectLlmFailure": "boolean_如果LLM明确表示无法完成请求或为本次尝试生成有效JSON则为True。如果错误是由于Agent端对LLM输出的JSON进行校验失败(即使JSON本身语法有效)_或LLM在格式良好的JSON中报告逻辑失败_则为False。",
    "failedValidationPoints": [ 
      {
        "jsonPath": "string_例如_decision.toolCallRequests[0].toolArguments.component_id",
        "issue_description": "string_例如_必需字段缺失_或_值必须是字符串但得到的是整数"
      }
    ]
  },
  "executionPhase": "string_对于此任务_必须是 'planning'",
  "thoughtProcess": "string_此字段现在是次要的_您的主要详细推理必须在初始的 `<think>...</think>` 块中_此JSON字段可以是简短总结或为空_Agent将优先使用 `<think>` 块内容。",
  "decision": {
    "isCallTools": "boolean_如果需要调用工具则为True_否则为False_也接受不区分大小写的字符串 'true'/'false'",
    "toolCallRequests": [ 
      {
        "toolCallId": "string_由您为本次特定工具调用生成的唯一ID_例如_tc_add_resistor_xyz123",
        "toolName": "string_要调用的工具名称_从可用工具列表中选择 (例如 add_component_tool)",
        "toolArguments": { 
        },
        "uiHints": { 
            "displayNameForTool": "string_optional_更用户友好的工具调用名称_例如_添加电阻R1",
            "estimatedDurationCategory": "string_enum_optional_short_medium_long_very_long",
            "showProgressGranularly": "boolean_optional_如果为True_UI可能会显示更细粒度的进度(如果工具支持)_默认为False"
        },
        "estimatedComplexityOrNotes": "string_optional_LLM对此调用的内部注释_依赖关系或置信度。"
      }
    ],
    "responseToUser": {
      "contentType": "string_例如_text/plain_或_application/markdown",
      "content": "string_如果isCallTools为False_这是您对用户的直接且完整的回复_它必须非空。如果isCallTools为True_这应该是一条有意义的过渡消息_反映计划的操作_例如_好的_我将添加元件X然后连接到Y_如果确实不需要过渡消息则可以为空字符串_但为了用户体验首选提供一条好的消息。",
      "suggestionsForNextSteps": [ 
        {
          "suggestionId": "string_optional_此建议的唯一ID_例如_sugg_ask_about_led_color",
          "textForUser": "string_向用户显示的建议文本_例如_您想指定LED颜色吗",
          "actionType": "string_enum_optional_USER_INPUT_EXPECTED_or_PREDEFINED_AGENT_ACTION_or_UI_NAVIGATION",
          "actionPayload": "object_or_string_optional_如果类型是PREDEFINED_AGENT_ACTION_这可能是简化的请求对象或命令字符串_供Agent在用户选择后处理"
        }
      ],
      "requiresUserClarificationForCurrentRequest": "boolean_optional_如果当前请求需要用户进一步输入才能继续_并且content正在请求该澄清_则设置为True_默认为False"
    }
  },
  "diagnostics": { 
      "llmConfidenceScoreForThisOutput": "float_optional_0.0_到_1.0_LLM对此JSON输出的正确性和完整性的自评估置信度",
      "alternativePlansConsideredCount": "integer_optional_如果LLM在确定此计划前考虑了多个计划",
      "parsingFeedbackFromPreviousAttemptId": "string_or_null_如果这是对先前格式错误的JSON的修正_则为该失败尝试的llmInteractionId"
  },
  "usageMetadata": null
}
```
"""
    # 示例中的 <think> 块也相应调整
    direct_qa_example_think_block_text = "用户询问电容的定义。这是一个概念性问题，我将直接回答，无需调用工具。我会解释电容的基本作用、单位和常见类型。"
    if enable_deep_thinking_chinese:
        direct_qa_example_think_block_text = "用户询问电容的定义。这是一个概念性问题，我将直接回答，无需调用工具。我会解释电容的基本作用、单位和常见类型。" # 这里已经是中文，如果需要特定指示，可以再强化
    else: # 如果不要求中文思考，可以用英文或模型的默认语言
        direct_qa_example_think_block_text = "The user is asking for the definition of a capacitor. This is a conceptual question that does not require any circuit design tools. I can answer it directly based on my knowledge base. I will provide an explanation of its basic function, unit, and common types, and offer a suggestion for a next step. My response will be clear and direct."


    direct_qa_example = (
        "\n【通用示例1: 直接回答用户问题 (无需工具) - V1.0.0 Reasoning Model Output】\n"
        "如果用户问: “你好,什么是电容？”\n"
        "您的输出应类似 (ID和时间戳会变化): \n"
        f"<think>\n{direct_qa_example_think_block_text}\n</think>\n"
        "```json\n"
        "{\n"
        "  \"requestId\": \"" + (request_id or "userReqExampleId123") + "\",\n"
        "  \"llmInteractionId\": \"" + llm_interaction_id_example_plan_prefix + "_directQaCap\",\n"
        "  \"timestampUtc\": \"" + current_timestamp_utc + "\",\n"
        "  \"status\": \"success\",\n"
        "  \"errorDetails\": null,\n"
        "  \"executionPhase\": \"planning\",\n"
        "  \"thoughtProcess\": \"用户询问电容定义,直接回答。(主要思考过程在 <think> 块中)\",\n"
        "  \"decision\": {\n"
        "    \"isCallTools\": false,\n"
        "    \"toolCallRequests\": [],\n"
        "    \"responseToUser\": {\n"
        "      \"contentType\": \"text/plain\",\n"
        "      \"content\": \"电容是一种能够储存电荷的电子元件,由两块导体板中间夹一层绝缘介质构成。它的主要特性是电容量,单位是法拉(F),常用单位有微法(μF)、纳法(nF)和皮法(pF). 电容在电路中常用于滤波、耦合、隔直流、储能等.\",\n"
        "      \"suggestionsForNextSteps\": [\n"
        "        {\"textForUser\": \"您想了解电容在具体电路中的应用吗？\", \"actionType\": \"USER_INPUT_EXPECTED\"},\n"
        "        {\"textForUser\": \"需要我帮您在当前电路中添加一个电容吗？\", \"actionType\": \"USER_INPUT_EXPECTED\", \"actionPayload\": \"请帮我添加一个10uF的电解电容\"}\n"
        "      ],\n"
        "      \"requiresUserClarificationForCurrentRequest\": false\n"
        "    }\n"
        "  },\n"
        "  \"diagnostics\": {\"llmConfidenceScoreForThisOutput\": 0.95},\n"
        "  \"usageMetadata\": null\n"
        "}\n"
        "```\n"
    )

    tool_call_example_think_block_text = "用户要求添加R1电阻，使用DuckDuckGo搜索“什么是LED”并返回2条结果，然后将R1连接到GND。我将按顺序规划这些工具调用，确保每个toolCallId唯一，并给用户过渡回复。GND可能需要先添加。"
    if enable_deep_thinking_chinese:
        tool_call_example_think_block_text = "用户需要执行三个操作: 1. 添加电阻R1 (1kΩ)。 2. 使用DuckDuckGo搜索'什么是LED'并明确要求返回2条结果。3. 添加GND (如果不存在)并连接R1和GND。我将按顺序规划这三个/四个工具调用。确保为每个工具调用生成唯一的toolCallId。并为用户提供一个过渡性的回复,表明我理解了请求并正在处理。电路状态目前为空,元件GND可能需要先添加。"
    else:
        tool_call_example_think_block_text = "The user wants to perform three actions: 1. Add resistor R1 (1kΩ). 2. Search 'what is LED' using DuckDuckGo and get 2 results. 3. Add GND (if it doesn't exist) and connect R1 to GND. I will plan these three/four tool calls sequentially. I'll ensure unique toolCallIds for each. I will also provide a transitional message to the user indicating I've understood and am processing the request. The circuit is currently empty, so GND might need to be added first."


    tool_call_example = (
        "\n【通用示例2: 需要调用工具时的输出V1.0-CamelCaseJSON Reasoning Model Output】\n"
        "如果用户说: “帮我加一个1k欧姆的电阻R1,再用DuckDuckGo搜索'什么是LED'并返回2条结果,然后把R1连到GND。”\n"
        "您的输出应类似 (ID和时间戳会变化,每个toolCallId必须唯一,由您生成): \n"
        f"<think>\n{tool_call_example_think_block_text}\n</think>\n"
        "```json\n"
        "{\n"
        "  \"requestId\": \"" + (request_id or "userReqExampleId456") + "\",\n"
        "  \"llmInteractionId\": \"" + llm_interaction_id_example_plan_prefix + "_multiToolSearchFix2\",\n"
        "  \"timestampUtc\": \"" + current_timestamp_utc + "\",\n"
        "  \"status\": \"success\",\n"
        "  \"errorDetails\": null,\n"
        "  \"executionPhase\": \"planning\",\n"
        "  \"thoughtProcess\": \"规划添加R1,搜索,连接GND。(主要思考过程在 <think> 块中)\",\n"
        "  \"decision\": {\n"
        "    \"isCallTools\": true,\n"
        "    \"toolCallRequests\": [\n"
        "      {\n"
        "        \"toolCallId\": \"tc_add_r1_" + str(uuid4())[:8] + "\",\n"
        "        \"toolName\": \"add_component_tool\",\n"
        "        \"toolArguments\": {\"component_type\": \"电阻\", \"component_id\": \"R1\", \"value\": \"1kΩ\"},\n"
        "        \"uiHints\": {\"displayNameForTool\": \"添加电阻 R1 (1kΩ)\"}\n"
        "      },\n"
        "      {\n"
        "        \"toolCallId\": \"tc_search_led_" + str(uuid4())[:8] + "\",\n"
        "        \"toolName\": \"duckduckgo_search_tool\",\n"
        "        \"toolArguments\": {\"query\": \"什么是LED\", \"num_results\": 2},\n"
        "        \"uiHints\": {\"displayNameForTool\": \"搜索LED定义(2条结果)\"}\n"
        "      },\n"
        "      {\n"
        "        \"toolCallId\": \"tc_add_gnd_" + str(uuid4())[:8] + "\",\n"
        "        \"toolName\": \"add_component_tool\",\n"
        "        \"toolArguments\": {\"component_type\": \"地\", \"component_id\": \"GND\"},\n"
        "        \"uiHints\": {\"displayNameForTool\": \"添加地线 GND (如果需要)\"}\n"
        "      },\n"
        "      {\n"
        "        \"toolCallId\": \"tc_conn_r1gnd_" + str(uuid4())[:8] + "\",\n"
        "        \"toolName\": \"connect_components_tool\",\n"
        "        \"toolArguments\": {\"comp1_id\": \"R1\", \"comp2_id\": \"GND\"},\n"
        "        \"uiHints\": {\"displayNameForTool\": \"连接 R1 与 GND\"}\n"
        "      }\n"
        "    ],\n"
        "    \"responseToUser\": {\n"
        "      \"contentType\": \"text/plain\",\n"
        "      \"content\": \"好的,我正在为您添加电阻R1 (1kΩ),搜索LED的定义(2条结果),并准备连接R1到GND。请稍候...\",\n"
        "      \"suggestionsForNextSteps\": []\n"
        "    }\n"
        "  },\n"
        "  \"diagnostics\": null,\n"
        "  \"usageMetadata\": null\n"
        "}\n"
        "```\n"
    )
    
    replan_example_think_block_text = "重规划开始。分析历史：用户想连接R10和C5。上一个计划调用 connect_components_tool 失败，原因是元件 'R10' 不存在。当前电路状态确认R10不存在，但C5存在。因此，新计划是首先添加R10（默认为1kΩ电阻），然后再连接R10和C5。本次规划逻辑清晰，JSON状态应为 'success'。"
    if enable_deep_thinking_chinese:
        replan_example_think_block_text = "重规划开始。分析历史: 用户想连接R10和C5。上一个计划 (llmInteractionId: " + example_prev_tool_call_id + "_plan) 中调用connect_components_tool (toolCallId: " + example_prev_tool_call_id + "_tool) 失败了,工具报告原因是元件 'R10' 在电路中不存在。当前电路状态也确认R10不在电路中，但C5存在。因此,我的新计划是首先添加R10 (用户未指定类型或值,我将默认为电阻,并提供一个常用值如1kΩ). 然后再调用connect_components_tool连接新创建的R10和已存在的C5。本次规划逻辑清晰，后续的JSON应标记为status: 'success'."
    else:
        replan_example_think_block_text = "Replanning started. Analyzing history: User wanted to connect R10 and C5. Previous plan (llmInteractionId: " + example_prev_tool_call_id + "_plan) called connect_components_tool (toolCallId: " + example_prev_tool_call_id + "_tool) which failed because component 'R10' does not exist in the circuit. Current circuit state also confirms R10 is missing, but C5 exists. Therefore, my new plan is to first add R10 (user didn't specify type/value, I'll default to resistor and a common value like 1kΩ). Then, I'll call connect_components_tool to connect the newly created R10 and existing C5. This plan is logically sound, so the subsequent JSON should be marked status: 'success'."


    replan_example = ""
    if is_replanning:
        replan_example = (
            "\n【重规划示例 (V1.0.0 Reasoning Model Output): 工具失败后,成功重规划并调用新/修正的工具】\n"
            "假设历史记录中有如下用户请求和失败的工具调用: \n"
            "  User: \"连接 R10 和 C5\"\n"
            "  Assistant (Previous Plan JSON): ... (Planned connect_components_tool for R10, C5, llmInteractionId: " + example_prev_tool_call_id + "_plan) ...\n"
            "  Tool (connect_components_tool, toolCallId: " + example_prev_tool_call_id + "_tool, name: connect_components_tool) result (in history): { \"role\": \"tool\", ..., \"content\": \"{\\\"status\\\": \\\"failure\\\", \\\"message\\\": \\\"错误: 元件 'R10' 在电路中不存在. \\\", \\\"error\\\": { \\\"error_type\\\": \\\"CIRCUIT_OPERATION_ERROR\\\", \\\"error_code\\\": \\\"COMPONENT_NOT_FOUND_FOR_CONNECTION\\\", ... }}\" }\n"
            "  Current Circuit State (in memory_context): (R10 does not exist, C5 exists)\n"
            "您在【当前重规划】时,您的新V1.0-CamelCaseJSON 输出应类似: \n"
            f"<think>\n{replan_example_think_block_text}\n</think>\n"
            "```json\n"
            "{\n"
            "  \"requestId\": \"" + (request_id or "userReqExampleId789Replan") + "\",\n"
            "  \"llmInteractionId\": \"" + llm_interaction_id_example_plan_prefix + "_replanAddConnectFix2\",\n"
            "  \"timestampUtc\": \"" + current_timestamp_utc + "\",\n"
            "  \"status\": \"success\",\n"
            "  \"errorDetails\": null,\n"
            "  \"executionPhase\": \"planning\",\n"
            "  \"thoughtProcess\": \"R10不存在,先添加再连接。(主要思考过程在 <think> 块中)\",\n"
            "  \"decision\": {\n"
            "    \"isCallTools\": true,\n"
            "    \"toolCallRequests\": [\n"
            "      {\n"
            "        \"toolCallId\": \"tc_replan_add_r10_" + str(uuid4())[:8] + "\",\n"
            "        \"toolName\": \"add_component_tool\",\n"
            "        \"toolArguments\": {\"component_type\": \"电阻\", \"component_id\": \"R10\", \"value\": \"1k\"},\n"
            "        \"uiHints\": {\"displayNameForTool\": \"(修正) 添加电阻 R10 (1kΩ)\"}\n"
            "      },\n"
            "      {\n"
            "        \"toolCallId\": \"tc_replan_connect_r10c5_" + str(uuid4())[:8] + "\",\n"
            "        \"toolName\": \"connect_components_tool\",\n"
            "        \"toolArguments\": {\"comp1_id\": \"R10\", \"comp2_id\": \"C5\"},\n"
            "        \"uiHints\": {\"displayNameForTool\": \"(修正) 连接 R10 与 C5\"}\n"
            "      }\n"
            "    ],\n"
            "    \"responseToUser\": {\n"
            "      \"contentType\": \"text/plain\",\n"
            "      \"content\": \"检测到元件R10之前不存在。我将先为您添加一个1kΩ的电阻R10,然后再将它与C5连接。\",\n"
            "      \"suggestionsForNextSteps\": [\n"
            "        {\"textForUser\": \"操作完成后显示电路状态.\"}\n"
            "      ],\n"
            "      \"requiresUserClarificationForCurrentRequest\": false\n"
            "    }\n"
            "  },\n"
            "  \"diagnostics\": {\"parsingFeedbackFromPreviousAttemptId\": \"" + example_prev_tool_call_id + "_plan\"},\n"
            "  \"usageMetadata\": null\n"
            "}\n"
            "```\n"
        )
    
    important_instructions_think_block_main = f"您的详细逐步推理**必须**在 `<think>...</think>` 标签内{think_block_language_instruction}，并置于回复最开始。"
    important_instructions_json_thought_process_main = f"此JSON字段现在是次要的。它可以是简短总结或空字符串 `\"\"`{json_thought_process_language_note}。`<think>...</think>` 块中的内容是主要的思考过程。"
    
    final_emphasize_think_block_main = f"您的输出【必须】以 `<think>...</think>` 块开始{think_block_language_instruction}，后跟一个被 ```json ... ``` 包围的、严格符合上述V1.0-CamelCaseJSON规范 (所有key使用camelCase) 的单个JSON对象。"


    prompt_parts = [
        "您是一位初版电路设计编程助理 (Agent Version V1.0.0, 11 Tools)。您的任务是理解用户指令,并据此规划行动或直接回复。\n",
        reasoning_model_instructions,
        "\n【核心任务: 规划阶段 (V1.0.0)】\n"
        f"请首先在 `<think>...</think>` 标签内深入分析用户的最新指令、完整的对话历史、当前的电路状态和记忆{think_block_language_instruction}。然后,在 `</think>` 标签之后,生成一个符合V1.0-CamelCaseJSON规范的JSON对象作为您的行动计划或直接回复。JSON中所有key【必须】使用camelCase (例如: `isCallTools`, `toolCallRequests`, `requestId`).\n",
        replanning_guidance if is_replanning else "",
        "【V1.0.0 输出格式规范 (在</think>之后输出, 必须严格遵守)】:\n",
        json_schema_description_for_prompt,
        "\n【重要指令与检查清单 (V1.0.0 - Planning)】:\n"
        f"1.  **`<think>` Block First**: {important_instructions_think_block_main}\n"
        "2.  **JSON After `</think>`**: V1.0.0 对象 (用 ```json ... ``` 包裹) **必须**紧跟 `</think>` 标签。此JSON中的所有键名必须是 camelCase (例如, `requestId`, `isCallTools`, `toolCallRequests`)。`toolArguments` 内部的键名 (例如, `component_type`) 应遵循下面工具 Schema 中提供的 snake_case 命名。\n"
        f"3.  **JSON `thoughtProcess` Field**: {important_instructions_json_thought_process_main}\n"
        "4.  **`decision.isCallTools`**: JSON中的此字段**必须**是布尔值 (`true` 或 `false`)。大小写不敏感的字符串 \"True\" 或 \"true\" 也可接受,Agent会将其解析为布尔值。\n"
        "5.  **其他 JSON 字段**: 严格遵循V1.0-CamelCaseJSON Schema 的JSON部分。\n"
        "6.  **电路状态感知**: 在规划涉及现有元件的工具调用前,请在 `memory_context` (当前电路状态) 中确认它们的存在。如果需要连接像 'INPUT' 这样的抽象节点而它们并非作为元件存在,请首先规划添加它们 (例如,作为 'Terminal')。\n\n",
        direct_qa_example,
        tool_call_example,
    ]
    if is_replanning:
        prompt_parts.append(replan_example)

    prompt_parts.extend([
        "\n【可用工具列表与参数规范 (V1.0.0 - 11 Tools)】:\n",
        tool_schemas_desc,
        "\n\n【当前上下文信息 (V1.0.0)】:\n"
        f"Current Request ID (如果可用,请在JSON的requestId字段中原样返回): {request_id or 'N/A_NOT_PROVIDED_IN_PROMPT_SET_TO_NULL'}\n"
        f"Current UTC Time (供您生成timestampUtc参考): {current_timestamp_utc}\n"
        f"当前电路与记忆摘要:\n{memory_context}\n\n"
        f"【最后再次强调】: {final_emphasize_think_block_main}JSON对象之外不应有任何其他文本。请务必仔细检查 `<think>` 块的使用以及JSON的语法和所有字段的类型及条件要求！"
    ])
    return "".join(prompt_parts)


def get_response_generation_prompt(memory_context: str,
                                        tool_schemas_desc: str,
                                        request_id: Optional[str] = None,
                                        # 新增参数: 是否启用中文深度思考
                                        enable_deep_thinking_chinese: bool = False 
                                        ) -> str:
    current_timestamp_utc = datetime.now(timezone.utc).isoformat()
    llm_interaction_id_example_resp_prefix = f"resp_ex_llm_id_{str(uuid4())[:6]}"

    think_block_language_instruction_resp = "，并且【请使用中文进行思考和阐述此部分内容】" if enable_deep_thinking_chinese else ""
    json_thought_process_language_note_resp = "（如果<think>块使用中文思考，此总结也建议使用中文）" if enable_deep_thinking_chinese else ""

    reasoning_model_instructions_resp_phase = (
        "\n【重要: Reasoning Model 输出规范 (V1.0.0 - Response Generation)】\n"
        f"1.  **思考过程**: 您的详细思考过程 (如何分析工具结果或决定直接回复, 以及如何构思最终回复) 【必须】包含在 `<think>...</think>` 标签内{think_block_language_instruction_resp}，并放在您回复的最开始部分。\n"
        "2.  **JSON 输出**: 在 `</think>` 标签之后,您【必须】输出一个严格符合下面描述的V1.0-CamelCaseJSON格式的单个JSON对象。此JSON对象应被三个反引号和'json'标记包围 (即 ```json ... ```)。JSON中所有key【必须】使用camelCase.\n"
        f"3.  **`thoughtProcess` 字段 (in JSON)**: JSON对象内部的 `thoughtProcess` 字段现在是次要的。它可以是一个简短的总结或留空 ( `\"\"` ){json_thought_process_language_note_resp}，因为您的主要思考过程已在 `<think>...</think>` 块中。Agent将优先使用 `<think>` 块中的内容作为思考日志。\n"
    )
    
    # JSON Schema 描述 (保持不变)
    json_schema_description_for_resp_phase = """
```json
{
  "requestId": "string_or_null_当前用户请求周期的ID_如果系统提示中提供了此值请原样返回_否则为null",
  "llmInteractionId": "string_必须是本次LLM响应的唯一ID_例如_resp_llm_id_后跟8位随机字符_如_resp_llm_id_e5f6g7h8",
  "timestampUtc": "string_当前UTC时间戳_ISO_8601格式_例如_2024-07-16T12:05:00.000Z",
  "status": "string_必须是 'success' 或 'failure'_表示您是否为本次尝试成功生成了此最终响应JSON_如果您现在无法构思出合适的摘要或回复_则设为failure",
  "errorDetails": {
    "errorType": "string_enum_例如_RESPONSE_GENERATION_ERROR_LLM_OUTPUT_VALIDATION_ERROR",
    "errorCode": "string_例如_JSON_MALFORMED_SUMMARY_LOGIC_ERROR",
    "messageToUser": "string_optional_用户友好的消息_如果适用",
    "technicalMessage": "string_本次响应生成尝试的详细技术错误消息。",
    "isDirectLlmFailure": "boolean_如果LLM明确表示无法完成请求或为本次尝试生成有效JSON则为True。如果错误是由于Agent端对LLM输出的JSON进行校验失败(即使JSON本身语法有效)_或LLM在格式良好的JSON中报告逻辑失败_则为False。",
    "failedValidationPoints": [ { "jsonPath": "...", "issue_description": "..." } ]
  },
  "executionPhase": "string_对于此任务_必须是 'response_generation'",
  "thoughtProcess": "string_此字段现在是次要的_您的主要详细推理必须在初始的 `<think>...</think>` 块中_此JSON字段可以是简短总结或为空_Agent将优先使用 `<think>` 块内容。",
  "decision": {
    "isCallTools": "boolean_在此响应生成阶段必须为false_也接受不区分大小写的字符串 'true'/'false'",
    "toolCallRequests": [],
    "responseToUser": {
      "contentType": "string_例如_text/plain_或_application/markdown",
      "content": "string_这是您对用户的最终且完整的回复_它必须非空。它应总结已采取的操作_报告结果_并根据工具输出(如果最初未调用工具_则根据您的直接知识)回应用户的原始请求。此内容是用户将看到的。",
      "suggestionsForNextSteps": [
        {
          "suggestionId": "string_optional_此建议的唯一ID_例如_sugg_ask_about_led_color",
          "textForUser": "string_向用户显示的建议文本_例如_您想指定LED颜色吗",
          "actionType": "string_enum_optional_USER_INPUT_EXPECTED_or_PREDEFINED_AGENT_ACTION_or_UI_NAVIGATION",
          "actionPayload": "object_or_string_optional_如果类型是PREDEFINED_AGENT_ACTION_这可能是简化的请求对象或命令字符串_供Agent在用户选择后处理"
        }
      ],
      "requiresUserClarificationForCurrentRequest": "boolean_optional_如果当前请求需要用户进一步输入才能继续_并且content正在请求该澄清_则设置为True_默认为False"
    }
  },
  "diagnostics": {
      "llmConfidenceScoreForThisOutput": "float_optional_0.0_到_1.0",
      "alternativePlansConsideredCount": "integer_optional",
      "parsingFeedbackFromPreviousAttemptId": "string_or_null"
  },
  "usageMetadata": null
}
```
"""
    # 示例中的 <think> 块也相应调整
    response_gen_example_think_block_text = "回顾工具执行结果：add_component_tool 成功添加了电阻R1。duckduckgo_search_tool 成功搜索了“LED”并返回结果。我将向用户清晰报告这两个操作的成功，并简要提及搜索到的信息。最终回复将整合这些信息，保持友好。"
    if enable_deep_thinking_chinese:
        response_gen_example_think_block_text = "回顾工具执行结果: add_component_tool (toolCallId: tc_xyz_add_r1) 成功添加了电阻R1。duckduckgo_search_tool (toolCallId: tc_abc_search_led) 成功搜索了'LED'并返回了结果。我需要向用户清晰地报告这两个操作的成功,并简要提及搜索到的信息。最终的回复将整合这些信息,保持友好和乐于助人的语气。"
    else:
        response_gen_example_think_block_text = "Reviewing tool execution results: add_component_tool (toolCallId: tc_xyz_add_r1) successfully added resistor R1. duckduckgo_search_tool (toolCallId: tc_abc_search_led) successfully searched for 'LED' and returned results. I need to clearly report the success of both operations to the user and briefly mention the information found. The final reply will integrate this information in a friendly and helpful tone."


    response_gen_example = (
        "\n【示例 (V1.0.0 Reasoning Model Output): 总结工具结果并生成最终回复】\n"
        "假设对话历史中包含以下工具执行结果 (工具1成功, 工具2是搜索工具也成功):\n"
        "  Tool Message 1 (for toolCallId: tc_xyz_add_r1): { \"role\": \"tool\", ..., \"content\": \"{\\\"status\\\": \\\"success\\\", \\\"message\\\": \\\"已添加电阻R1\\\", ...}\" }\n"
        "  Tool Message 2 (for toolCallId: tc_abc_search_led): { \"role\": \"tool\", ..., \"content\": \"{\\\"status\\\": \\\"success\\\", \\\"message\\\": \\\"已完成对'LED'的DuckDuckGo搜索,找到2条相关信息。\\\", \\\"data\\\": {\\\"query\\\": \\\"LED\\\", \\\"num_results_returned\\\": 2, \\\"results_json_string\\\": \\\"[{\\\\\\\"title\\\\\\\":\\\\\\\"LED - Wikipedia\\\\\\\", ...}]\\\"}}\" }\n"
        "您的输出V1.0-CamelCaseJSON JSON应类似 (ID和时间戳会变化): \n"
        f"<think>\n{response_gen_example_think_block_text}\n</think>\n"
        "```json\n"
        "{\n"
        "  \"requestId\": \"" + (request_id or "userReqExampleIdResp123") + "\",\n"
        "  \"llmInteractionId\": \"" + llm_interaction_id_example_resp_prefix + "_finalSummaryRSearchFix2\",\n" 
        "  \"timestampUtc\": \"" + current_timestamp_utc + "\",\n"
        "  \"status\": \"success\",\n"
        "  \"errorDetails\": null,\n"
        "  \"executionPhase\": \"response_generation\",\n"
        "  \"thoughtProcess\": \"总结R1添加成功,LED搜索成功。(主要思考过程在 <think> 块中)\",\n"
        "  \"decision\": {\n"
        "    \"isCallTools\": false, \n"
        "    \"toolCallRequests\": [], \n"
        "    \"responseToUser\": {\n"
        "      \"contentType\": \"text/plain\",\n"
        "      \"content\": \"您好,我已经成功为您添加了电阻R1。关于LED的DuckDuckGo搜索也已完成,我找到了2条相关信息,例如 'LED - Wikipedia'。您想了解更多搜索到的细节吗？\",\n"
        "      \"suggestionsForNextSteps\": [\n"
        "        {\"suggestionId\": \"sugg_show_search_details\", \"textForUser\": \"显示LED搜索结果的详细信息\", \"actionType\": \"USER_INPUT_EXPECTED\"},\n"
        "        {\"suggestionId\": \"sugg_view_circuit\", \"textForUser\": \"查看当前电路中已有的元件列表。\", \"actionType\": \"USER_INPUT_EXPECTED\", \"actionPayload\": \"当前电路什么样\"}\n"
        "      ],\n"
        "      \"requiresUserClarificationForCurrentRequest\": false \n"
        "    }\n"
        "  },\n"
        "  \"diagnostics\": {\"llmConfidenceScoreForThisOutput\": 0.98},\n"
        "  \"usageMetadata\": null\n"
        "}\n"
        "```\n"
    )
    
    important_instructions_resp_think_block_main = f"您的详细工具结果分析和回复构思**必须**在 `<think>...</think>` 标签内{think_block_language_instruction_resp}。"
    final_emphasize_resp_think_block_main = f"您的输出【必须】以 `<think>...</think>` 块开始{think_block_language_instruction_resp}，后跟一个被 ```json ... ``` 包围的、严格符合上述V1.0-CamelCaseJSON规范 (所有key使用camelCase) 的单个JSON对象。"

    return (
        "您是一位初版电路设计编程助理 (Agent Version V1.0.0, 11 Tools), 经验丰富,技术精湛,并且极其擅长清晰、准确、诚实地汇报工作结果。\n"
        f"{reasoning_model_instructions_resp_phase}\n"
        "【核心任务: 响应生成阶段 (V1.0.0)】\n"
        f"您当前的任务是: 基于到目前为止的【完整对话历史】(包括用户最初的指令、您在规划阶段生成的V1.0-CamelCaseJSON计划、以及所有【已执行工具的结果详情】,这些工具结果是以 'role: tool', 'toolCallId: ...', 'name: ...', 'content: JSON_string_of_tool_output' 的格式存在于历史记录中的), 首先在 `<think>...</think>` 标签内进行思考和总结{think_block_language_instruction_resp}, 然后在 `</think>` 之后生成【最终的、面向用户的V1.0-CamelCaseJSON回复】。JSON中所有key【必须】使用camelCase.\n\n"
        "【V1.0.0 输出格式规范 (在</think>之后输出, 与规划阶段结构相同,但有特定值要求 - 再次强调)】:\n"
        f"{json_schema_description_for_resp_phase}\n"
        "【重要指令与检查清单 (V1.0.0 - 响应生成阶段特定要求)】:\n"
        f"1.  **`<think>` Block First**: {important_instructions_resp_think_block_main}\n"
        "2.  **JSON After `</think>`**: V1.0.0 对象 (用 ```json ... ``` 包裹) **必须**紧跟 `</think>` 标签。此JSON中的所有键名必须是 camelCase。\n"
        "3.  **`executionPhase`**: 在此阶段,此值【必须】是 `\"response_generation\"`。\n"
        "4.  **`decision.isCallTools`**: 在此响应生成阶段,此值【必须】为 `false` (或可解析为`false`的字符串)。\n"
        "5.  **`decision.toolCallRequests`**: 在此响应生成阶段,此列表【必须】为 `[]` (空数组) 或 `null`。\n"
        "6.  **`decision.responseToUser.content`**: 这是您基于所有先前步骤生成的【最终、完整、友好】的文本回复。它【不能】为空字符串或仅包含空白。\n"
        "7.  **回顾工具结果**: 仔细检查对话历史中 `role: tool` 的消息。您的最终回复必须准确反映这些结果。\n\n"
        f"{response_gen_example}\n"
        "【上下文参考信息 (仅供你回顾 - V1.0.0)】:\n"
        f"Current Request ID (如果可用,请在JSON的requestId字段中原样返回): {request_id or 'N/A_NOT_PROVIDED_IN_PROMPT_SET_TO_NULL'}\n"
        f"Current UTC Time (供您生成timestampUtc参考): {current_timestamp_utc}\n"
        f"当前电路与记忆摘要:\n{memory_context}\n"
        f"我的可用工具列表 (共11个, 仅供你参考,此阶段不应再调用它们):\n{tool_schemas_desc}\n\n"
        f"【最后再次强调】: {final_emphasize_resp_think_block_main}在这个阶段,您【绝对不能】再请求调用任何新工具。您的任务是总结并回复。"
    )
