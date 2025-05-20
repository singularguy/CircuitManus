# IDT_AGENT_Pro/circuitmanus/tools/base.py
import functools
import inspect
from typing import Dict, Any, Callable, Awaitable, Union

# 这个模块主要提供工具注册的装饰器
# 未来如果需要通用的工具基类或接口，也可以放在这里

def register_tool(description: str, parameters: Dict[str, Any]):
    """
    一个装饰器，用于将一个 Agent 的方法注册为一个可被 LLM 调用的工具。

    被装饰的函数会被添加一个 `_is_tool` 属性 (设为 True) 和一个
    `_tool_schema` 属性，其中包含提供给 LLM 的工具描述和参数规范。

    Args:
        description (str): 对工具功能的自然语言描述，供 LLM 理解工具的用途。
        parameters (Dict[str, Any]): 一个符合 JSON Schema 规范的字典，
                                     描述工具接受的参数。通常包含:
                                     - "type": "object"
                                     - "properties": 一个字典，键是参数名 (snake_case)，
                                                     值是该参数的 schema (例如 {"type": "string", "description": "..."})。
                                     - "required": 一个可选的列表，包含所有必需参数的名称。

    Returns:
        Callable: 返回一个包装器函数，该函数会保留原函数的功能并添加额外的元数据。
                  如果原函数是异步的，包装器也是异步的；同步亦然。
    """
    if not isinstance(description, str) or not description.strip():
        raise ValueError("工具描述 (description) 必须是一个有效的非空字符串。")
    if not isinstance(parameters, dict): # 基本的类型检查
        raise ValueError("工具参数规范 (parameters) 必须是一个字典。")
    # 可以添加更严格的 parameters schema 校验，例如检查是否包含 'type': 'object' 和 'properties'
    # 但这里保持与原版一致的宽松度

    def decorator(func: Callable[..., Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]) -> Callable:
        # 将 schema 附加到函数对象上
        func._tool_schema = {"description": description, "parameters": parameters}
        func._is_tool = True # 标记这是一个已注册的工具

        # 使用 functools.wraps 来保留原函数的元数据 (如名称, docstring, 注解)，
        # 这对于 inspect.iscoroutinefunction 等内省机制正确工作非常重要。
        # 尤其是当装饰器本身返回一个新的函数（包装器）时。
        
        # 根据原函数是同步还是异步，创建相应的包装器
        # 这是为了确保装饰器能正确处理异步和同步函数，并保持其原始的调用方式 (awaitable or not)
        # 对于 Agent 工具，它们最终都应该返回一个 Dict[str, Any] 的结果。
        
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Dict[str, Any]:
                # 对于异步工具，直接 await 它
                # 这里的 args[0] 通常是 self (Agent 实例)
                # kwargs 通常是 { "arguments": {...} }
                return await func(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Dict[str, Any]:
                # 对于同步工具，直接调用它
                return func(*args, **kwargs)
            return sync_wrapper
            
    return decorator