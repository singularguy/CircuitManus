# IDT_AGENT_Pro/circuitmanus/circuit_domain/components.py
from typing import Optional, Dict, Any
import logging

# 使用特定于此模块的 logger，而不是根 logger，便于追踪日志来源
logger = logging.getLogger(__name__)

class CircuitComponent:
    """
    代表电路中的一个基本元件。

    Attributes:
        id (str): 元件的唯一标识符 (通常是大写)。这是元件在电路中的主键。
        type (str): 元件的类型 (例如: "resistor", "capacitor", "led")。
        value (Optional[str]): 元件的可选值 (例如: "1kΩ", "10uF", "3V")。
                               如果元件没有特定值 (如地线、连接点)，则为 None。
    """
    # 使用 __slots__ 可以略微优化内存使用，并限制实例的属性，防止意外添加新属性。
    # 这对于频繁创建大量此类对象的场景比较有用。
    __slots__ = ['id', 'type', 'value']

    def __init__(self, component_id: str, component_type: str, value: Optional[str] = None):
        """
        初始化 CircuitComponent 实例。

        Args:
            component_id (str): 元件的ID。会被转换为大写并去除首尾空格。
                                 此ID在电路中应该是唯一的。
            component_type (str): 元件的类型。会被去除首尾空格。
            value (Optional[str]): 元件的值。如果提供，会被转换为字符串并去除首尾空格。
                                    如果传入 None 或空白字符串，最终 self.value 会是 None。

        Raises:
            ValueError: 如果 component_id 或 component_type 为空或无效。
        """
        if not isinstance(component_id, str) or not component_id.strip():
            # 元件ID是核心标识，必须有效
            logger.error(f"尝试创建元件时，ID无效: '{component_id}'")
            raise ValueError("元件 ID 必须是有效的非空字符串。")
        if not isinstance(component_type, str) or not component_type.strip():
            # 元件类型也是基本信息，不能为空
            logger.error(f"尝试创建元件 (ID: {component_id}) 时，类型无效: '{component_type}'")
            raise ValueError("元件类型必须是有效的非空字符串。")

        self.id: str = component_id.strip().upper()
        self.type: str = component_type.strip()
        
        # 处理元件值：确保空字符串或仅包含空格的字符串也被视作 None
        processed_value = str(value).strip() if value is not None and str(value).strip() else None
        self.value: Optional[str] = processed_value
        
        # logger.debug(f"CircuitComponent initialized: ID='{self.id}', Type='{self.type}', Value='{self.value}'")

    def __str__(self) -> str:
        """
        返回元件的字符串表示形式，方便阅读。
        例如: "元件: Resistor (ID: R1) (值: 1kΩ)" 或 "元件: LED (ID: LED1)"
        """
        value_str = f" (值: {self.value})" if self.value else ""
        return f"元件: {self.type} (ID: {self.id}){value_str}"

    def __repr__(self) -> str:
        """
        返回元件的官方字符串表示形式，通常用于调试。
        它应该能够被用来重新创建对象 (虽然这里没有完全做到，因为 value 可能为 None)。
        例如: "CircuitComponent(id='R1', type='Resistor', value='1kΩ')"
        """
        return f"CircuitComponent(id='{self.id}', type='{self.type}', value={repr(self.value)})"

    def to_dict(self) -> Dict[str, Any]:
        """
        将元件对象转换为字典格式，方便序列化 (例如转换为JSON)。

        Returns:
            Dict[str, Any]: 包含元件 id, type, 和 value 的字典。
        """
        return {"id": self.id, "type": self.type, "value": self.value}