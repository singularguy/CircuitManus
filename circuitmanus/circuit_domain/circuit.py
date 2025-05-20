# IDT_AGENT_NATIVE/circuitmanus/circuit_domain/circuit.py
import re
import logging
from typing import Dict, Set, Tuple, Optional, Any, List

# 从同一个子包 (circuit_domain) 中的 components.py 文件导入 CircuitComponent 类
# 这是正确的相对导入方式，确保模块间的依赖清晰。
from .components import CircuitComponent

logger = logging.getLogger(__name__)

class Circuit:
    """
    代表一个电路板，包含多个元件及其之间的连接。

    Attributes:
        components (Dict[str, CircuitComponent]): 一个字典，存储电路中的所有元件。
                                                  键是元件的ID (大写)，值是 CircuitComponent 对象。
        connections (Set[Tuple[str, str]]): 一个集合，存储元件之间的连接。
                                             每个连接是一个包含两个已排序元件ID的元组，
                                             以确保 (ID1, ID2) 和 (ID2, ID1) 被视为同一连接。
        _component_counters (Dict[str, int]): 一个内部字典，用于为不同类型的元件生成唯一的ID后缀。
                                              键是元件类型的前缀代码 (例如 "R", "C")，值是当前的计数。
    """
    def __init__(self):
        """初始化一个空的电路。"""
        logger.info("[Circuit] 初始化电路实体...")
        self.components: Dict[str, CircuitComponent] = {}
        self.connections: Set[Tuple[str, str]] = set()
        # 预定义一些常见的元件类型前缀及其计数器
        # 这些前缀用于自动生成元件ID，例如 R1, R2, C1, L1 等。
        self._component_counters: Dict[str, int] = {
            'R': 0, 'L': 0, 'B': 0, 'S': 0, 'C': 0, 'V': 0, 'G': 0, 'U': 0, 'O': 0,
            'I': 0, 'A': 0, 'D': 0, 'P': 0, 'F': 0, 'H': 0,
            'T': 0, 'N': 0, 'IN': 0, 'OUT': 0,
            'SRCH': 0  # 用于搜索记录这类特殊 "元件"
        }
        logger.info("[Circuit] 电路实体初始化完成。")

    def add_component(self, component: CircuitComponent) -> None:
        """
        向电路中添加一个新元件。

        Args:
            component (CircuitComponent): 要添加的元件对象。

        Raises:
            TypeError: 如果要添加的对象不是 CircuitComponent 的实例。
            ValueError: 如果具有相同ID的元件已存在于电路中。
        """
        if not isinstance(component, CircuitComponent):
            logger.error(f"尝试添加非 CircuitComponent 对象到电路: {type(component)}")
            raise TypeError("要添加的对象必须是 CircuitComponent 的实例。")
            
        if component.id in self.components:
            logger.warning(f"[Circuit] 尝试添加已存在的元件 ID '{component.id}'。")
            raise ValueError(f"元件 ID '{component.id}' 已被占用。")
        
        self.components[component.id] = component
        logger.debug(f"[Circuit] 元件 '{component.id}' ({component.type}) 已添加到电路。")

    def remove_component(self, component_id: str) -> Tuple[Dict[str, Any], int]:
        """
        从电路中移除一个元件及其所有相关的连接。

        Args:
            component_id (str): 要移除的元件的ID (不区分大小写，内部会转为大写)。

        Returns:
            Tuple[Dict[str, Any], int]: 一个元组，包含：
                - 被移除元件的详细信息 (字典格式，通过 component.to_dict() 获得)。
                - 被移除的连接数量。

        Raises:
            ValueError: 如果指定的元件ID在电路中不存在。
        """
        comp_id_upper = component_id.strip().upper()
        if comp_id_upper not in self.components:
            logger.warning(f"[Circuit] 尝试移除不存在的元件 ID '{comp_id_upper}'。")
            raise ValueError(f"元件 '{comp_id_upper}' 在电路中不存在。")
        
        # 获取待移除元件的字典表示，以便返回
        removed_component_details = self.components[comp_id_upper].to_dict()
        del self.components[comp_id_upper] # 从字典中删除元件
        
        # 查找并移除所有与该元件相关的连接
        connections_to_remove = set() # 使用集合避免重复记录要移除的连接
        for conn in self.connections:
            if comp_id_upper in conn: # 检查元件ID是否在连接元组中
                connections_to_remove.add(conn)
        
        removed_connections_count = len(connections_to_remove)
        for conn_to_remove in connections_to_remove: # 遍历要移除的连接集合
            if conn_to_remove in self.connections: # 再次确认连接存在（理论上应该存在）
                self.connections.remove(conn_to_remove)
                logger.debug(f"[Circuit] 移除了涉及元件 '{comp_id_upper}' 的连接 {conn_to_remove}。")
            else: # 防御性代码，理论上不应执行
                logger.warning(f"[Circuit] 尝试移除连接 {conn_to_remove} 时发现其已不存在。")

        logger.debug(f"[Circuit] 元件 '{comp_id_upper}' 及其相关 {removed_connections_count} 个连接已从电路中移除。")
        return removed_component_details, removed_connections_count

    def connect_components(self, id1: str, id2: str) -> bool:
        """
        连接电路中的两个元件。

        Args:
            id1 (str): 第一个元件的ID (不区分大小写)。
            id2 (str): 第二个元件的ID (不区分大小写)。

        Returns:
            bool: 如果成功创建了新的连接则返回 True，如果连接已存在则返回 False。

        Raises:
            ValueError: 如果任一元件ID不存在，或者尝试将元件连接到自身。
        """
        id1_upper = id1.strip().upper()
        id2_upper = id2.strip().upper()

        if id1_upper == id2_upper:
            logger.warning(f"[Circuit] 尝试将元件 '{id1_upper}' 连接到自身。")
            raise ValueError(f"不能将元件 '{id1_upper}' 连接到它自己。")
        if id1_upper not in self.components:
            logger.warning(f"[Circuit] 尝试连接时，元件 '{id1_upper}' 不存在。")
            raise ValueError(f"元件 '{id1_upper}' 在电路中不存在。")
        if id2_upper not in self.components:
            logger.warning(f"[Circuit] 尝试连接时，元件 '{id2_upper}' 不存在。")
            raise ValueError(f"元件 '{id2_upper}' 在电路中不存在。")
        
        # 使用排序后的元组作为连接的唯一标识，确保 (id1, id2) 和 (id2, id1) 等价
        connection = tuple(sorted((id1_upper, id2_upper)))
        if connection in self.connections:
             logger.info(f"[Circuit] 连接 '{id1_upper}' <--> '{id2_upper}' 已存在，无需重复添加。")
             return False  # 连接已存在
        
        self.connections.add(connection)
        logger.debug(f"[Circuit] 添加了连接: {id1_upper} <--> {id2_upper}。")
        return True # 成功添加新连接

    def disconnect_components(self, id1: str, id2: str) -> bool:
        """
        断开电路中两个元件之间的连接。

        Args:
            id1 (str): 第一个元件的ID (不区分大小写)。
            id2 (str): 第二个元件的ID (不区分大小写)。

        Returns:
            bool: 如果成功断开了连接则返回 True，如果连接原本就不存在则返回 False。
        """
        id1_upper = id1.strip().upper()
        id2_upper = id2.strip().upper()

        # 注意：此方法不显式检查元件 id1_upper 和 id2_upper 是否存在于 self.components 中。
        # 它的主要职责是处理 self.connections 集合。
        # 如果需要，调用者（例如工具函数）应该在调用此方法前验证元件的存在性。

        connection = tuple(sorted((id1_upper, id2_upper)))
        if connection not in self.connections:
             logger.info(f"[Circuit] 连接 '{id1_upper}' <--> '{id2_upper}' 不存在,无需断开。")
             return False # 连接不存在
        
        self.connections.remove(connection)
        logger.debug(f"[Circuit] 断开了连接: {id1_upper} <--> {id2_upper}。")
        return True # 成功断开连接

    def get_state_description(self) -> str:
        """
        生成当前电路状态的文本描述。

        Returns:
            str: 多行字符串，描述电路中的所有元件和连接。
                 如果电路为空，则返回特定消息。
        """
        logger.debug("[Circuit] 正在生成电路状态描述...")
        num_components = len(self.components)
        num_connections = len(self.connections)

        if num_components == 0 and num_connections == 0:
            return "【当前电路状态】: 电路为空。"

        desc_lines = ["【当前电路状态】:"]
        desc_lines.append(f"  - 元件 ({num_components}):")
        if self.components:
            # 按ID排序元件，确保输出顺序稳定
            sorted_ids = sorted(self.components.keys())
            for cid in sorted_ids:
                # 调用 CircuitComponent 实例的 __str__ 方法获取其描述
                desc_lines.append(f"    - {str(self.components[cid])}")
        else:
            desc_lines.append("    (无)")

        desc_lines.append(f"  - 连接 ({num_connections}):")
        if self.connections:
            # 按连接对排序，确保输出顺序稳定
            # (c1, c2) 元组本身就是可比较的，可以直接排序
            sorted_connections = sorted(list(self.connections)) 
            for c1, c2 in sorted_connections:
                desc_lines.append(f"    - {c1} <--> {c2}")
        else:
            desc_lines.append("    (无)")

        description = "\n".join(desc_lines)
        logger.debug("[Circuit] 电路状态描述生成完毕。")
        return description

    def generate_component_id(self, component_type: str) -> str:
        """
        为指定类型的元件生成一个唯一的ID。
        ID格式通常为 "类型前缀代码" + "数字计数"。 例如 "R1", "C5"。

        Args:
            component_type (str): 元件的类型 (例如 "电阻", "LED", "chip")。
                                  此函数会尝试将常见类型名映射到标准前缀。

        Returns:
            str: 生成的唯一元件ID。

        Raises:
            RuntimeError: 如果在多次尝试后仍未能生成唯一的ID (非常罕见)。
        """
        logger.debug(f"[Circuit] 正在为类型 '{component_type}' 生成唯一 ID...")
        
        # 元件类型关键字到其ID前缀的映射表。
        # 键是小写关键字，值是ID前缀代码。
        type_map = {
            "resistor": "R", "电阻": "R",
            "capacitor": "C", "电容": "C",
            "battery": "B", "电池": "B",
            "voltage source": "V", "voltage": "V", "电压源": "V", "电压": "V",
            "led": "L", "发光二极管": "L",
            "switch": "S", "开关": "S",
            "ground": "G", "地": "G",
            "ic": "U", "chip": "U", "芯片": "U", "集成电路": "U",
            "inductor": "I", "电感": "I",
            "current source": "A", "电流源": "A",
            "diode": "D", "二极管": "D",
            "potentiometer": "P", "电位器": "P",
            "fuse": "F", "保险丝": "F",
            "header": "H", "排针": "H",
            "terminal": "T", "端子": "T",
            "connection point": "P", # 与电位器 'P' 共享前缀，若要区分，需调整
            "node": "N", "节点": "N",
            "input": "IN", "输入": "IN",
            "output": "OUT", "输出": "OUT",
            "search_record": "SRCH", "搜索记录": "SRCH",
            "component": "O", "元件": "O",
        }

        # 确保所有在 type_map 中定义的前缀代码都在 _component_counters 中有初始计数
        for code in type_map.values():
            if code not in self._component_counters:
                 self._component_counters[code] = 0

        cleaned_type = component_type.strip().lower() # 清理并转小写以便匹配
        type_code = "O"  # 默认为通用元件前缀 "O" (Other)
        best_match_len = 0 # 用于找到最长（最具体）的关键字匹配

        # 特殊关键字优先处理或有特定逻辑
        if cleaned_type == "input": type_code = "IN"
        elif cleaned_type == "output": type_code = "OUT"
        elif cleaned_type == "ground" or cleaned_type == "地": type_code = "G"
        else:
            # 遍历映射表，查找最长匹配的关键字来确定类型代码
            for keyword, code in type_map.items():
                if keyword in cleaned_type and len(keyword) > best_match_len:
                    type_code = code
                    best_match_len = len(keyword)

        if type_code == "O" and cleaned_type not in ["component", "元件"]:
             logger.warning(f"[Circuit] 未找到类型 '{component_type}' 的特定前缀,将使用通用前缀 'O'。")

        MAX_ID_ATTEMPTS = 10000 # 防止无限循环的保护措施
        for attempt in range(MAX_ID_ATTEMPTS):
            self._component_counters[type_code] += 1 # 增加对应类型代码的计数器
            gen_id = f"{type_code}{self._component_counters[type_code]}" # 构造ID
            if gen_id not in self.components: # 检查生成的ID是否已存在
                logger.debug(f"[Circuit] 生成唯一 ID: '{gen_id}' (尝试 {attempt + 1})。")
                return gen_id
            logger.debug(f"[Circuit] ID '{gen_id}' 已存在,尝试下一个。(尝试 {attempt + 1})。")

        # 如果循环了 MAX_ID_ATTEMPTS 次仍然没有找到唯一的ID，则抛出运行时错误。
        logger.error(f"未能为类型 '{component_type}' (代码 '{type_code}') 生成唯一 ID ({MAX_ID_ATTEMPTS} 次尝试后)。")
        raise RuntimeError(f"未能为类型 '{component_type}' (代码 '{type_code}') 生成唯一 ID ({MAX_ID_ATTEMPTS} 次尝试后)。")

    def clear(self) -> None:
        """
        清空整个电路，移除所有元件和连接，并将所有元件ID计数器重置为0。
        此操作是不可逆的。
        """
        logger.info("[Circuit] 正在清空电路状态...")
        comp_count = len(self.components)
        conn_count = len(self.connections)

        self.components.clear() # 清空元件字典
        self.connections.clear() # 清空连接集合
        
        # 重置所有元件ID计数器
        for key in self._component_counters:
            self._component_counters[key] = 0
        # 或者更简洁: self._component_counters = {k: 0 for k in self._component_counters}

        logger.info(f"[Circuit] 电路状态已清空 (移除了 {comp_count} 个元件, {conn_count} 个连接,并重置了所有 ID 计数器)。")