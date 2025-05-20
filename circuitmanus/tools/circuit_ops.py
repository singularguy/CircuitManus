# IDT_AGENT_Pro/circuitmanus/tools/circuit_ops.py
import re
import logging
import traceback
from typing import Dict, Any, Tuple, TYPE_CHECKING

# 导入 register_tool 装饰器
from .base import register_tool

# TYPE_CHECKING 用于类型提示，避免运行时循环导入
if TYPE_CHECKING:
    from ..agent import CircuitAgent # 指向 agent.py 中的 CircuitAgent
    from ..circuit_domain.components import CircuitComponent # 指向 components.py

logger = logging.getLogger(__name__)

# 注意：以下所有工具函数的第一个参数 'self' 都期望是 CircuitAgent 的一个实例。
# ToolExecutor 在调用时会确保这一点，因为它通过 getattr(agent_instance, tool_name) 获取方法。

@register_tool(
    description="添加一个新的电路元件 (例如: 电阻, 电容, 电池, LED, 开关, 芯片, 地线, 端子/连接点等)。如果用户未指定 ID,系统会自动为其生成一个。",
    parameters={"type": "object", "properties": {"component_type": {"type": "string", "description": "元件的类型 (例如: '电阻', 'LED', 'Terminal', 'INPUT', 'GND')。"}, "component_id": {"type": "string", "description": "可选的用户为元件指定的ID。如果提供,则使用此ID; 如果不提供或提供格式无效,则由系统自动生成。"}, "value": {"type": "string", "description": "可选的元件值 (例如: '1k', '10uF', '3V')。"}}, "required": ["component_type"]}
)
def add_component_tool(self: 'CircuitAgent', arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Agent工具：向当前电路中添加一个新元件。
    LLM通过'toolArguments'提供元件类型、可选ID和可选值。
    如果ID未提供或无效，则由系统根据类型自动生成。
    """
    # 使用 self.current_request_id 和 self.memory_manager
    tool_call_logger_prefix = f"[Action-AddComponentTool-ReqID:{self.current_request_id or 'N/A'}]"
    logger.info(f"{tool_call_logger_prefix} 执行添加元件操作。")
    logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
    
    component_type = arguments.get("component_type")
    component_id_req = arguments.get("component_id") # 用户请求的ID
    value_req = arguments.get("value") # 用户请求的元件值

    # 1. 验证输入参数的有效性 (基本类型和存在性)
    if not component_type or not isinstance(component_type, str) or not component_type.strip():
        err_msg = "元件类型是必需的,并且必须是有效的非空字符串。"
        logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
        return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_TYPE", "technical_message": err_msg}}

    target_id_final: str # 最终确定的元件ID，确保它在后续逻辑中一定会被赋值
    id_was_generated_by_system = False
    user_provided_id_was_validated: str = "" # 用来记录用户提供的且通过验证的ID

    # 2. 确定元件ID：优先使用用户提供的ID (如果有效且不冲突)，否则自动生成
    if component_id_req and isinstance(component_id_req, str) and component_id_req.strip():
        user_provided_id_cleaned = component_id_req.strip().upper()
        # 简单的ID格式校验：允许字母、数字、下划线、连字符，且不能以下划线或连字符开头（除非是特定关键字）
        # 或者是一些预定义的特殊ID，如 "INPUT", "OUTPUT", "GND"
        if re.match(r'^[a-zA-Z0-9_][a-zA-Z0-9_-]*$', user_provided_id_cleaned) or \
           user_provided_id_cleaned in ["INPUT", "OUTPUT", "GND"]: # GND等特殊ID允许
            if user_provided_id_cleaned in self.memory_manager.circuit.components:
                err_msg = f"您提供的元件 ID '{user_provided_id_cleaned}' 已被占用。"
                logger.error(f"{tool_call_logger_prefix} ID 冲突: {err_msg}")
                return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "CIRCUIT_STATE_ERROR", "error_code": "COMPONENT_ID_CONFLICT", "technical_message": err_msg, "conflicting_id": user_provided_id_cleaned}}
            else:
                target_id_final = user_provided_id_cleaned
                user_provided_id_was_validated = target_id_final
                logger.debug(f"{tool_call_logger_prefix} 将使用用户提供的有效 ID: '{target_id_final}'。")
        else:
            logger.warning(f"{tool_call_logger_prefix} 用户提供的 ID '{component_id_req}' 格式无效。将自动生成 ID。")
            # 标记需要生成ID
            target_id_final = "" # 临时置空，下面会生成
            id_was_generated_by_system = True
    else:
        # 用户未提供ID，需要系统生成
        target_id_final = "" # 临时置空
        id_was_generated_by_system = True

    if id_was_generated_by_system: # 或者 target_id_final == ""
        try:
            # 调用 Circuit 对象的ID生成方法
            target_id_final = self.memory_manager.circuit.generate_component_id(component_type)
            logger.debug(f"{tool_call_logger_prefix} 已自动为类型 '{component_type}' 生成 ID: '{target_id_final}'。")
        except RuntimeError as e_gen_id:
            err_msg = f"无法自动为类型 '{component_type}' 生成唯一 ID: {e_gen_id}"
            logger.error(f"{tool_call_logger_prefix} ID 生成失败: {err_msg}", exc_info=True)
            return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "INTERNAL_AGENT_ERROR", "error_code": "COMPONENT_ID_GENERATION_FAILED", "technical_message": str(e_gen_id)}}
    
    # 3. 处理元件值
    # 如果 value_req 是 None 或者清理后是空字符串，则 processed_value 为 None
    processed_value = str(value_req).strip() if value_req is not None and str(value_req).strip() else None
    # 特殊情况：如果LLM明确传递了 "value": null (在JSON中)，arguments.get("value")会是None。
    # 如果LLM传递了 "value": "" (空字符串)，arguments.get("value")会是""。
    # 上述的 processed_value 逻辑都能正确处理这些情况，将其统一为 None 或非空字符串。

    # 4. 创建并添加元件
    try:
        # 确保 target_id_final 此时一定有值
        if not target_id_final: # 防御性编程，理论上不会到这里
            raise ValueError("内部错误: 在尝试创建元件之前,未能最终确定有效的元件 ID。")

        # 需要导入 CircuitComponent 类
        from ..circuit_domain.components import CircuitComponent
        new_component = CircuitComponent(target_id_final, component_type, processed_value)
        self.memory_manager.circuit.add_component(new_component)

        logger.info(f"{tool_call_logger_prefix} 成功添加元件 '{new_component.id}' ({new_component.type}) 到电路。")
        
        # 构建成功消息
        success_message_parts = [f"操作成功: 已添加元件 {str(new_component)}。"]
        if id_was_generated_by_system and not user_provided_id_was_validated: # 明确是系统生成的
            success_message_parts.append(f"(系统自动分配 ID '{new_component.id}')")
        elif user_provided_id_was_validated: # 明确是用户提供的且通过验证的
             success_message_parts.append(f"(使用了您指定的 ID '{user_provided_id_was_validated}')")
        final_success_message = " ".join(success_message_parts)
        
        # 添加到长期记忆
        self.memory_manager.add_to_long_term(f"添加了元件: {str(new_component)} (请求ID: {self.current_request_id or 'N/A'})")
        
        return {"status": "success", "message": final_success_message, "data": new_component.to_dict()}

    except ValueError as ve_comp: # 可能来自 CircuitComponent 构造或 circuit.add_component
        err_msg = f"创建或添加元件对象时发生内部验证错误: {ve_comp}"
        logger.error(f"{tool_call_logger_prefix} 元件创建/添加错误: {err_msg}", exc_info=True)
        return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": "COMPONENT_CREATION_OR_ADDITION_VALIDATION_FAILED", "technical_message": str(ve_comp)}}
    except Exception as e_add_comp: # 捕获其他未知异常
        err_msg = f"添加元件时发生未知的内部错误: {e_add_comp}"
        logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
        return {"status": "failure", "message": "错误: 添加元件时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "ADD_COMPONENT_UNEXPECTED_FAILURE", "technical_message": str(e_add_comp), "exception_details": traceback.format_exc(limit=3)}}

@register_tool(
    description="使用两个已存在元件的 ID 将它们连接起来。",
    parameters={"type": "object", "properties": {"comp1_id": {"type": "string", "description": "第一个元件的 ID。"}, "comp2_id": {"type": "string", "description": "第二个元件的 ID。"}}, "required": ["comp1_id", "comp2_id"]}
)
def connect_components_tool(self: 'CircuitAgent', arguments: Dict[str, Any]) -> Dict[str, Any]:
    tool_call_logger_prefix = f"[Action-ConnectComponentsTool-ReqID:{self.current_request_id or 'N/A'}]"
    logger.info(f"{tool_call_logger_prefix} 执行连接元件操作。")
    logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")

    comp1_id_req = arguments.get("comp1_id")
    comp2_id_req = arguments.get("comp2_id")

    if not comp1_id_req or not isinstance(comp1_id_req, str) or not comp1_id_req.strip() or \
       not comp2_id_req or not isinstance(comp2_id_req, str) or not comp2_id_req.strip():
        err_msg = "必须提供两个有效的、非空的元件 ID 字符串。"
        logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
        return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_IDS_FOR_CONNECTION", "technical_message": err_msg}}

    id1_cleaned = comp1_id_req.strip().upper()
    id2_cleaned = comp2_id_req.strip().upper()

    try:
        # 调用 Circuit 对象的连接方法
        connection_was_new = self.memory_manager.circuit.connect_components(id1_cleaned, id2_cleaned)
        if connection_was_new:
            logger.info(f"{tool_call_logger_prefix} 成功添加新连接: {id1_cleaned} <--> {id2_cleaned}。")
            self.memory_manager.add_to_long_term(f"连接了元件: {id1_cleaned} <--> {id2_cleaned} (请求ID: {self.current_request_id or 'N/A'})")
            return {"status": "success", "message": f"操作成功: 已将元件 '{id1_cleaned}' 与 '{id2_cleaned}' 连接起来。", "data": {"connection": sorted((id1_cleaned, id2_cleaned))}}
        else:
            # 连接已存在
            msg_exists = f"元件 '{id1_cleaned}' 和 '{id2_cleaned}' 之间已经存在连接。无需重复操作。"
            logger.info(f"{tool_call_logger_prefix} 连接已存在: {msg_exists}")
            return {"status": "success", "message": f"注意: {msg_exists}", "data": {"connection": sorted((id1_cleaned, id2_cleaned)), "already_existed": True}}
    except ValueError as ve_connect: # 来自 circuit.connect_components 的校验错误
        err_msg_val = str(ve_connect)
        logger.error(f"{tool_call_logger_prefix} 连接验证错误: {err_msg_val}")
        # 根据错误消息内容细化错误代码
        error_code_detail = "GENERIC_CIRCUIT_VALIDATION_ERROR"
        if "不存在" in err_msg_val: error_code_detail = "COMPONENT_NOT_FOUND_FOR_CONNECTION"
        elif "连接到它自己" in err_msg_val: error_code_detail = "SELF_CONNECTION_ATTEMPTED"
        return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": error_code_detail, "technical_message": err_msg_val}}
    except Exception as e_connect:
        err_msg = f"连接元件时发生未知的内部错误: {e_connect}"
        logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
        return {"status": "failure", "message": "错误: 连接元件时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "CONNECT_COMPONENTS_UNEXPECTED_FAILURE", "technical_message": str(e_connect), "exception_details": traceback.format_exc(limit=3)}}

@register_tool(description="获取当前电路的详细描述,包括所有元件及其连接情况。", parameters={"type": "object", "properties": {}})
def describe_circuit_tool(self: 'CircuitAgent', arguments: Dict[str, Any]) -> Dict[str, Any]:
    tool_call_logger_prefix = f"[Action-DescribeCircuitTool-ReqID:{self.current_request_id or 'N/A'}]"
    logger.info(f"{tool_call_logger_prefix} 执行描述电路操作。")
    try:
        # 调用 MemoryManager (间接调用 Circuit) 的方法
        description = self.memory_manager.get_circuit_state_description()
        logger.info(f"{tool_call_logger_prefix} 成功生成电路描述。")
        return {"status": "success", "message": "已成功获取当前电路的描述。", "data": {"description": description}}
    except Exception as e_describe:
        err_msg = f"生成电路描述时发生意外的内部错误: {e_describe}"
        logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
        return {"status": "failure", "message": "错误: 获取电路描述时发生未知错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "DESCRIBE_CIRCUIT_UNEXPECTED_FAILURE", "technical_message": str(e_describe), "exception_details": traceback.format_exc(limit=3)}}

@register_tool(description="彻底清空当前的电路设计,移除所有已添加的元件和它们之间的所有连接。此操作不可逆。", parameters={"type": "object", "properties": {}})
def clear_circuit_tool(self: 'CircuitAgent', arguments: Dict[str, Any]) -> Dict[str, Any]:
    tool_call_logger_prefix = f"[Action-ClearCircuitTool-ReqID:{self.current_request_id or 'N/A'}]"
    logger.info(f"{tool_call_logger_prefix} 执行清空电路操作。")
    try:
        # 调用 Circuit 对象的清空方法
        self.memory_manager.circuit.clear()
        logger.info(f"{tool_call_logger_prefix} 电路状态已成功清空。")
        self.memory_manager.add_to_long_term(f"执行了清空电路操作 (请求ID: {self.current_request_id or 'N/A'})。")
        return {"status": "success", "message": "操作成功: 当前电路已彻底清空。"}
    except Exception as e_clear:
        err_msg = f"清空电路时发生意外的内部错误: {e_clear}"
        logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
        return {"status": "failure", "message": "错误: 清空电路时发生未知错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "CLEAR_CIRCUIT_UNEXPECTED_FAILURE", "technical_message": str(e_clear), "exception_details": traceback.format_exc(limit=3)}}

@register_tool(
    description="从电路中移除一个指定的元件及其所有相关的连接。",
    parameters={"type": "object", "properties": {"component_id": {"type": "string", "description": "要移除的元件的 ID。"}}, "required": ["component_id"]}
)
def remove_component_tool(self: 'CircuitAgent', arguments: Dict[str, Any]) -> Dict[str, Any]:
    tool_call_logger_prefix = f"[Action-RemoveComponentTool-ReqID:{self.current_request_id or 'N/A'}]"
    logger.info(f"{tool_call_logger_prefix} 执行移除元件操作。")
    logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
    component_id_req = arguments.get("component_id")

    if not component_id_req or not isinstance(component_id_req, str) or not component_id_req.strip():
        err_msg = "必须提供一个有效的、非空的元件 ID 字符串。"
        logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
        return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_ID_FOR_REMOVAL", "technical_message": err_msg}}

    id_cleaned = component_id_req.strip().upper()
    try:
        # 调用 Circuit 对象的移除方法
        removed_comp_details, removed_conn_count = self.memory_manager.circuit.remove_component(id_cleaned)
        logger.info(f"{tool_call_logger_prefix} 成功移除元件 '{id_cleaned}' 及其 {removed_conn_count} 个连接。")
        self.memory_manager.add_to_long_term(f"移除了元件: ID '{id_cleaned}', 类型 '{removed_comp_details.get('type', 'N/A')}' (请求ID: {self.current_request_id or 'N/A'})")
        return {"status": "success", "message": f"操作成功: 已移除元件 '{id_cleaned}' 及其所有 {removed_conn_count} 个连接。", "data": {"removed_component": removed_comp_details, "connections_removed_count": removed_conn_count}}
    except ValueError as ve_remove: # 来自 circuit.remove_component
        err_msg_val = str(ve_remove)
        logger.error(f"{tool_call_logger_prefix} 移除验证错误: {err_msg_val}")
        # 通常是元件不存在
        return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": "COMPONENT_NOT_FOUND_FOR_REMOVAL", "technical_message": err_msg_val}}
    except Exception as e_remove:
        err_msg = f"移除元件时发生未知的内部错误: {e_remove}"
        logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
        return {"status": "failure", "message": "错误: 移除元件时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "REMOVE_COMPONENT_UNEXPECTED_FAILURE", "technical_message": str(e_remove), "exception_details": traceback.format_exc(limit=3)}}

@register_tool(
    description="断开两个指定元件之间的连接。如果它们之间原本就没有连接,则不执行任何操作。",
    parameters={"type": "object", "properties": {"comp1_id": {"type": "string", "description": "第一个元件的 ID。"}, "comp2_id": {"type": "string", "description": "第二个元件的 ID。"}}, "required": ["comp1_id", "comp2_id"]}
)
def disconnect_components_tool(self: 'CircuitAgent', arguments: Dict[str, Any]) -> Dict[str, Any]:
    tool_call_logger_prefix = f"[Action-DisconnectComponentsTool-ReqID:{self.current_request_id or 'N/A'}]"
    logger.info(f"{tool_call_logger_prefix} 执行断开元件连接操作。")
    logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
    comp1_id_req = arguments.get("comp1_id")
    comp2_id_req = arguments.get("comp2_id")

    if not comp1_id_req or not isinstance(comp1_id_req, str) or not comp1_id_req.strip() or \
       not comp2_id_req or not isinstance(comp2_id_req, str) or not comp2_id_req.strip():
        err_msg = "必须提供两个有效的、非空的元件 ID 字符串。"
        logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
        return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_IDS_FOR_DISCONNECTION", "technical_message": err_msg}}

    id1_cleaned = comp1_id_req.strip().upper()
    id2_cleaned = comp2_id_req.strip().upper()

    if id1_cleaned == id2_cleaned: # 不能断开自身与自身的连接（它们也不可能连接）
        err_msg = "不能断开一个元件与它自身的连接（它们本来就不可能连接）。"
        logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
        return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "SELF_DISCONNECTION_ATTEMPTED", "technical_message": err_msg}}
    
    try:
        # 在工具层面检查元件是否存在，Circuit.disconnect_components 本身可能不检查
        if id1_cleaned not in self.memory_manager.circuit.components:
            raise ValueError(f"元件 '{id1_cleaned}' 在电路中不存在,无法执行断开操作。")
        if id2_cleaned not in self.memory_manager.circuit.components:
            raise ValueError(f"元件 '{id2_cleaned}' 在电路中不存在,无法执行断开操作。")

        disconnected_successfully = self.memory_manager.circuit.disconnect_components(id1_cleaned, id2_cleaned)
        if disconnected_successfully:
            logger.info(f"{tool_call_logger_prefix} 成功断开连接: {id1_cleaned} <--> {id2_cleaned}。")
            self.memory_manager.add_to_long_term(f"断开了元件连接: {id1_cleaned} <--> {id2_cleaned} (请求ID: {self.current_request_id or 'N/A'})")
            return {"status": "success", "message": f"操作成功: 已断开元件 '{id1_cleaned}' 与 '{id2_cleaned}' 之间的连接。", "data": {"disconnected_pair": sorted((id1_cleaned, id2_cleaned))}}
        else:
            # 连接原本就不存在
            msg_not_exist = f"元件 '{id1_cleaned}' 和 '{id2_cleaned}' 之间原本就没有连接,无需断开。"
            logger.info(f"{tool_call_logger_prefix} 连接不存在: {msg_not_exist}")
            return {"status": "success", "message": f"注意: {msg_not_exist}", "data": {"disconnected_pair": sorted((id1_cleaned, id2_cleaned)), "already_disconnected_or_not_connected": True}}
    except ValueError as ve_disconnect: # 来自上面的元件存在性检查
        err_msg_val = str(ve_disconnect)
        logger.error(f"{tool_call_logger_prefix} 断开连接验证错误: {err_msg_val}")
        return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": "COMPONENT_NOT_FOUND_FOR_DISCONNECTION", "technical_message": err_msg_val}}
    except Exception as e_disconnect:
        err_msg = f"断开元件连接时发生未知的内部错误: {e_disconnect}"
        logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
        return {"status": "failure", "message": "错误: 断开元件连接时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "DISCONNECT_COMPONENTS_UNEXPECTED_FAILURE", "technical_message": str(e_disconnect), "exception_details": traceback.format_exc(limit=3)}}

@register_tool(
    description="更新电路中一个已存在元件的值 (例如电阻的欧姆值, 电容的法拉值, 电池的电压等)。",
    parameters={"type": "object", "properties": {"component_id": {"type": "string", "description": "要更新值的元件的 ID。"}, "new_value": {"type": "string", "description": "元件的新值。如果想要清除该元件的值,可以传入 null 或一个空字符串。"}}, "required": ["component_id", "new_value"]}
)
def update_component_value_tool(self: 'CircuitAgent', arguments: Dict[str, Any]) -> Dict[str, Any]:
    tool_call_logger_prefix = f"[Action-UpdateComponentValueTool-ReqID:{self.current_request_id or 'N/A'}]"
    logger.info(f"{tool_call_logger_prefix} 执行更新元件值操作。")
    logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
    component_id_req = arguments.get("component_id")
    new_value_req = arguments.get("new_value") # new_value 可以是 null (JSON) -> None (Python)

    if not component_id_req or not isinstance(component_id_req, str) or not component_id_req.strip():
        err_msg = "必须提供一个有效的、非空的元件 ID 字符串。"
        logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
        return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_ID_FOR_UPDATE", "technical_message": err_msg}}
    
    # new_value 可以是字符串或 None (用于清除值)。空字符串也会被处理成 None。
    if not isinstance(new_value_req, (str, type(None))):
        err_msg = f"元件的新值 'new_value' 必须是字符串或 null (用于清除值)。收到类型: {type(new_value_req).__name__}"
        logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
        return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "INVALID_NEW_VALUE_TYPE", "technical_message": err_msg}}

    id_cleaned = component_id_req.strip().upper()
    # 处理 new_value: 如果是 None 或清理后为空字符串，则设为 None，否则为清理后的字符串
    final_new_value = str(new_value_req).strip() if new_value_req is not None and str(new_value_req).strip() else None

    try:
        if id_cleaned not in self.memory_manager.circuit.components:
            raise ValueError(f"元件 '{id_cleaned}' 在电路中不存在,无法更新其值。")
        
        component_to_update = self.memory_manager.circuit.components[id_cleaned]
        old_value = component_to_update.value # 记录旧值用于消息反馈
        component_to_update.value = final_new_value # 直接更新 CircuitComponent 对象的 value 属性
        
        logger.info(f"{tool_call_logger_prefix} 成功更新元件 '{id_cleaned}' 的值从 '{old_value}' 到 '{final_new_value}'。")
        self.memory_manager.add_to_long_term(f"更新了元件 '{id_cleaned}' 的值: 旧值 '{old_value}', 新值 '{final_new_value}' (请求ID: {self.current_request_id or 'N/A'})")
        
        # 返回更新后的元件信息
        return {"status": "success", "message": f"操作成功: 元件 '{id_cleaned}' 的值已从 '{old_value if old_value else '(无值)'}' 更新为 '{final_new_value if final_new_value else '(无值)'}'。", "data": component_to_update.to_dict()}
    except ValueError as ve_update: # 来自上面的元件存在性检查
        err_msg_val = str(ve_update)
        logger.error(f"{tool_call_logger_prefix} 更新值验证错误: {err_msg_val}")
        return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_OPERATION_ERROR", "error_code": "COMPONENT_NOT_FOUND_FOR_VALUE_UPDATE", "technical_message": err_msg_val}}
    except Exception as e_update:
        err_msg = f"更新元件值时发生未知的内部错误: {e_update}"
        logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
        return {"status": "failure", "message": "错误: 更新元件值时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "UPDATE_COMPONENT_VALUE_UNEXPECTED_FAILURE", "technical_message": str(e_update), "exception_details": traceback.format_exc(limit=3)}}

@register_tool(
    description="根据提供的 ID 查找电路中的一个特定元件,并返回其详细信息 (类型、ID、值)。",
    parameters={"type": "object", "properties": {"component_id": {"type": "string", "description": "要查找的元件的 ID。"}}, "required": ["component_id"]}
)
def find_component_by_id_tool(self: 'CircuitAgent', arguments: Dict[str, Any]) -> Dict[str, Any]:
    tool_call_logger_prefix = f"[Action-FindComponentByIdTool-ReqID:{self.current_request_id or 'N/A'}]"
    logger.info(f"{tool_call_logger_prefix} 执行查找元件操作。")
    logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
    component_id_req = arguments.get("component_id")

    if not component_id_req or not isinstance(component_id_req, str) or not component_id_req.strip():
        err_msg = "必须提供一个有效的、非空的元件 ID 字符串。"
        logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
        return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_ID_FOR_FIND", "technical_message": err_msg}}

    id_cleaned = component_id_req.strip().upper()
    try:
        if id_cleaned in self.memory_manager.circuit.components:
            component_found = self.memory_manager.circuit.components[id_cleaned]
            logger.info(f"{tool_call_logger_prefix} 成功找到元件 '{id_cleaned}'。")
            return {"status": "success", "message": f"操作成功: 已找到元件 '{id_cleaned}'。", "data": component_found.to_dict()}
        else:
            # 元件未找到，这是一种预期的“失败”情况，但对于工具执行来说，应明确告知LLM
            logger.info(f"{tool_call_logger_prefix} 未找到元件 '{id_cleaned}'。")
            # 对于 "find" 操作，找不到元件通常不应是 status: "success"。
            # 应该返回一个明确的失败或未找到的状态，让LLM知道。
            # 原代码中没有明确的失败分支，这里补充。
            return {"status": "failure", "message": f"错误: 电路中不存在 ID 为 '{id_cleaned}' 的元件。", "error": {"error_type": "CIRCUIT_QUERY_ERROR", "error_code": "COMPONENT_NOT_FOUND_BY_ID", "technical_message": f"Component with ID '{id_cleaned}' not found in circuit."}}
    except Exception as e_find:
        err_msg = f"查找元件时发生未知的内部错误: {e_find}"
        logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
        return {"status": "failure", "message": "错误: 查找元件时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "FIND_COMPONENT_UNEXPECTED_FAILURE", "technical_message": str(e_find), "exception_details": traceback.format_exc(limit=3)}}

@register_tool(
    description="列出电路中所有属于指定类型的元件及其详细信息。",
    parameters={"type": "object", "properties": {"component_type": {"type": "string", "description": "要筛选的元件类型 (例如: '电阻', 'LED', '电池')。此匹配不区分大小写。"}}, "required": ["component_type"]}
)
def list_components_by_type_tool(self: 'CircuitAgent', arguments: Dict[str, Any]) -> Dict[str, Any]:
    tool_call_logger_prefix = f"[Action-ListComponentsByTypeTool-ReqID:{self.current_request_id or 'N/A'}]"
    logger.info(f"{tool_call_logger_prefix} 执行按类型列出元件操作。")
    logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
    component_type_req = arguments.get("component_type")

    if not component_type_req or not isinstance(component_type_req, str) or not component_type_req.strip():
        err_msg = "必须提供一个有效的、非空的元件类型字符串。"
        logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
        return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_TYPE_FOR_LIST", "technical_message": err_msg}}
    
    type_cleaned = component_type_req.strip().lower() # 类型匹配不区分大小写
    
    try:
        found_components = []
        for comp_id in self.memory_manager.circuit.components: # 遍历字典的键
            comp = self.memory_manager.circuit.components[comp_id]
            if comp.type.lower() == type_cleaned:
                found_components.append(comp.to_dict())
        
        if found_components:
            logger.info(f"{tool_call_logger_prefix} 成功找到 {len(found_components)} 个类型为 '{component_type_req}' 的元件。")
            return {"status": "success", "message": f"操作成功: 找到 {len(found_components)} 个类型为 '{component_type_req}' 的元件。", "data": {"components": found_components, "count": len(found_components)}}
        else:
            # 未找到匹配类型的元件，这是一种正常情况，应返回成功状态和空列表
            logger.info(f"{tool_call_logger_prefix} 未找到类型为 '{component_type_req}' 的元件。")
            return {"status": "success", "message": f"提示: 电路中没有找到类型为 '{component_type_req}' 的元件。", "data": {"components": [], "count": 0}}
    except Exception as e_list:
        err_msg = f"按类型列出元件时发生未知的内部错误: {e_list}"
        logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
        return {"status": "failure", "message": "错误: 按类型列出元件时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "LIST_COMPONENTS_UNEXPECTED_FAILURE", "technical_message": str(e_list), "exception_details": traceback.format_exc(limit=3)}}

@register_tool(
    description="获取指定元件当前连接到其他元件的数量。",
    parameters={"type": "object", "properties": {"component_id": {"type": "string", "description": "要查询连接数量的元件的 ID。"}}, "required": ["component_id"]}
)
def get_component_connection_count_tool(self: 'CircuitAgent', arguments: Dict[str, Any]) -> Dict[str, Any]:
    tool_call_logger_prefix = f"[Action-GetComponentConnectionCountTool-ReqID:{self.current_request_id or 'N/A'}]"
    logger.info(f"{tool_call_logger_prefix} 执行获取元件连接数操作。")
    logger.debug(f"{tool_call_logger_prefix} 收到参数: {arguments}")
    component_id_req = arguments.get("component_id")

    if not component_id_req or not isinstance(component_id_req, str) or not component_id_req.strip():
        err_msg = "必须提供一个有效的、非空的元件 ID 字符串。"
        logger.error(f"{tool_call_logger_prefix} 输入验证失败: {err_msg}")
        return {"status": "failure", "message": f"错误: {err_msg}", "error": {"error_type": "USER_INPUT_VALIDATION_ERROR", "error_code": "MISSING_OR_INVALID_COMPONENT_ID_FOR_CONNECTION_COUNT", "technical_message": err_msg}}

    id_cleaned = component_id_req.strip().upper()
    try:
        if id_cleaned not in self.memory_manager.circuit.components:
            raise ValueError(f"元件 '{id_cleaned}' 在电路中不存在,无法查询其连接数。")
        
        connection_count = 0
        # 遍历电路中的所有连接
        for conn_pair_tuple in self.memory_manager.circuit.connections:
            # conn_pair_tuple 是一个排序后的ID元组，例如 ('ID1', 'ID2')
            if id_cleaned in conn_pair_tuple:
                connection_count += 1
        
        logger.info(f"{tool_call_logger_prefix} 元件 '{id_cleaned}' 有 {connection_count} 个连接。")
        return {"status": "success", "message": f"操作成功: 元件 '{id_cleaned}' 当前有 {connection_count} 个连接。", "data": {"component_id": id_cleaned, "connection_count": connection_count}}
    except ValueError as ve_count: # 来自上面的元件存在性检查
        err_msg_val = str(ve_count)
        logger.error(f"{tool_call_logger_prefix} 获取连接数验证错误: {err_msg_val}")
        return {"status": "failure", "message": f"错误: {err_msg_val}", "error": {"error_type": "CIRCUIT_QUERY_ERROR", "error_code": "COMPONENT_NOT_FOUND_FOR_CONNECTION_COUNT", "technical_message": err_msg_val}}
    except Exception as e_count:
        err_msg = f"获取元件连接数时发生未知的内部错误: {e_count}"
        logger.error(f"{tool_call_logger_prefix} 未知错误: {err_msg}", exc_info=True)
        return {"status": "failure", "message": "错误: 获取元件连接数时发生未知内部错误。", "error": {"error_type": "UNEXPECTED_TOOL_ERROR", "error_code": "GET_CONNECTION_COUNT_UNEXPECTED_FAILURE", "technical_message": str(e_count), "exception_details": traceback.format_exc(limit=3)}}