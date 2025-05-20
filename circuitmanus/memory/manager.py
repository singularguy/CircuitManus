# IDT_AGENT_Pro/circuitmanus/memory/manager.py
import logging
from typing import List, Dict, Any

# 从 circuit_domain 导入 Circuit 类
# 这是跨子包导入，使用相对导入 '.' 表示当前包 (circuitmanus), '..' 表示上级包
# 如果 manager.py 直接在 circuitmanus 下，可以用 from .circuit_domain.circuit import Circuit
# 如果此文件在 circuitmanus/memory/ 下，则需要 from ..circuit_domain.circuit import Circuit
from ..circuit_domain.circuit import Circuit #  memory 和 circuit_domain 都是 circuitmanus 的子包

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    管理 Agent 的记忆，包括短期对话历史、长期知识和当前的电路状态。

    Attributes:
        max_short_term_items (int): 短期记忆中允许存储的最大消息条数。
        max_long_term_items (int): 长期记忆中允许存储的最大知识片段条数。
        short_term (List[Dict[str, Any]]): 存储对话历史的列表，每条消息是一个字典 (通常包含 'role' 和 'content')。
        long_term (List[str]): 存储长期知识片段的列表，每个片段是一个字符串。
        circuit (Circuit): 一个 Circuit 类的实例，代表当前 Agent 正在操作的电路。
    """
    def __init__(self, max_short_term_items: int = 30, max_long_term_items: int = 200):
        """
        初始化 MemoryManager。

        Args:
            max_short_term_items (int): 短期记忆的最大条目数。必须大于1。
            max_long_term_items (int): 长期记忆的最大条目数。

        Raises:
            ValueError: 如果 max_short_term_items 小于或等于1。
        """
        logger.info("[MemoryManager] 初始化记忆模块...")
        if not isinstance(max_short_term_items, int) or max_short_term_items <= 1:
            # 短期记忆如果太小（比如只有1条），在LLM交互中通常没有意义，
            # 因为至少需要保留一条用户消息和一条系统消息/助手消息才能形成上下文。
            logger.error(f"max_short_term_items ({max_short_term_items}) 无效，必须是大于1的整数。")
            raise ValueError("参数 'max_short_term_items' 必须大于 1。")
        if not isinstance(max_long_term_items, int) or max_long_term_items < 0:
            logger.error(f"max_long_term_items ({max_long_term_items}) 无效，必须是非负整数。")
            raise ValueError("参数 'max_long_term_items' 必须是非负整数。")


        self.max_short_term_items: int = max_short_term_items
        self.max_long_term_items: int = max_long_term_items
        self.short_term: List[Dict[str, Any]] = []
        self.long_term: List[str] = []
        
        # 每个 MemoryManager 实例都拥有并管理一个独立的 Circuit 实例。
        # 这是核心设计，Agent 的所有电路操作都通过其 MemoryManager 间接作用于这个 Circuit 对象。
        self.circuit: Circuit = Circuit()

        logger.info(f"[MemoryManager] 记忆模块初始化完成。短期记忆上限: {max_short_term_items} 条, 长期记忆上限: {max_long_term_items} 条。")

    def add_to_short_term(self, message: Dict[str, Any]) -> None:
        """
        向短期记忆中添加一条消息，并根据需要进行修剪以保持在最大限制内。
        修剪策略：移除最旧的非系统 ('system' role) 消息。

        Args:
            message (Dict[str, Any]): 要添加的消息字典，通常包含 'role' 和 'content'。
        """
        if not isinstance(message, dict) or "role" not in message or "content" not in message:
            logger.warning(f"[MemoryManager] 尝试添加格式无效的消息到短期记忆: {message}")
            return # 或者可以抛出异常，取决于严格性要求

        logger.debug(f"[MemoryManager] 添加消息到短期记忆 (Role: {message.get('role', 'N/A')})。当前数量: {len(self.short_term)}。")
        self.short_term.append(message)
        
        current_size = len(self.short_term)
        if current_size > self.max_short_term_items:
            items_to_remove_count = current_size - self.max_short_term_items
            logger.debug(f"[MemoryManager] 短期记忆超限 ({current_size}/{self.max_short_term_items}),需要移除 {items_to_remove_count} 条消息。")
            
            # 查找可以被移除的非系统消息的索引
            # 通常，我们希望保留系统提示 (role='system')，它们通常位于列表的开头或具有特殊意义。
            # 因此，修剪时优先移除旧的用户 (role='user') 或助手 (role='assistant'/'tool') 消息。
            non_system_indices = [i for i, msg in enumerate(self.short_term) if msg.get("role") != "system"]
            
            num_to_actually_remove = min(items_to_remove_count, len(non_system_indices))

            if num_to_actually_remove > 0:
                # 从最旧的非系统消息开始移除
                indices_to_remove_set = set(non_system_indices[:num_to_actually_remove])
                
                removed_roles = [self.short_term[i].get('role', 'N/A') for i in sorted(list(indices_to_remove_set))]
                
                # 构建新的短期记忆列表，排除被选中的旧消息
                new_short_term = [msg for i, msg in enumerate(self.short_term) if i not in indices_to_remove_set]
                self.short_term = new_short_term
                
                logger.info(f"[MemoryManager] 短期记忆修剪完成,移除了 {num_to_actually_remove} 条最旧的非系统消息 (角色: {removed_roles})。")
            elif items_to_remove_count > 0:
                 # 如果需要移除，但所有消息都是系统消息，或者非系统消息不够移除
                 logger.warning(f"[MemoryManager] 短期记忆超限 ({current_size}/{self.max_short_term_items}) 但未能找到足够的非系统消息进行移除 ({len(non_system_indices)}条非系统消息存在)。这可能表示系统消息过多或max_short_term_items设置过小。")
        
        logger.debug(f"[MemoryManager] 添加后短期记忆数量: {len(self.short_term)}。")

    def add_to_long_term(self, knowledge_snippet: str) -> None:
        """
        向长期记忆中添加一个知识片段，并根据需要进行修剪。
        修剪策略：移除最早添加的知识片段。

        Args:
            knowledge_snippet (str): 要添加的知识字符串。
        """
        MAX_SNIPPET_LENGTH = 10000 # 限制单个长期记忆片段的最大长度，防止过大的条目。
        if not isinstance(knowledge_snippet, str):
            logger.warning(f"[MemoryManager] 尝试添加非字符串类型的知识到长期记忆: {type(knowledge_snippet)}")
            return

        if len(knowledge_snippet) > MAX_SNIPPET_LENGTH:
            logger.warning(f"[MemoryManager] 尝试添加的长期记忆片段过长 ({len(knowledge_snippet)} 字符),已截断为 {MAX_SNIPPET_LENGTH} 字符。")
            knowledge_snippet = knowledge_snippet[:MAX_SNIPPET_LENGTH] + "... (已截断)"

        logger.debug(f"[MemoryManager] 添加知识到长期记忆 (预览: '{knowledge_snippet[:100]}{'...' if len(knowledge_snippet) > 100 else ''}'). 当前数量: {len(self.long_term)}。")
        self.long_term.append(knowledge_snippet)
        
        if len(self.long_term) > self.max_long_term_items:
            removed_snippet = self.long_term.pop(0) # 移除列表头部的最旧条目
            logger.info(f"[MemoryManager] 长期记忆超限 ({len(self.long_term)}/{self.max_long_term_items}), 移除最旧知识 (预览: '{removed_snippet[:50]}...').")
        
        logger.debug(f"[MemoryManager] 添加后长期记忆数量: {len(self.long_term)}。")

    def get_circuit_state_description(self) -> str:
        """
        获取当前电路状态的文本描述。
        这是对 self.circuit.get_state_description() 的一个便捷封装。

        Returns:
            str: 电路状态的描述字符串。
        """
        return self.circuit.get_state_description()

    def get_memory_context_for_prompt(self, recent_long_term_count: int = 7) -> str:
        """
        格式化记忆上下文，用于构建LLM的系统提示。
        包含当前电路状态描述和最近的长期记忆片段。

        Args:
            recent_long_term_count (int): 要包含在上下文中的最近长期记忆条目数量。

        Returns:
            str: 格式化后的记忆上下文字符串。
        """
        logger.debug("[MemoryManager] 正在格式化记忆上下文用于 Prompt...")
        circuit_desc = self.get_circuit_state_description()
        
        long_term_str = ""
        if self.long_term:
            # 确保请求的数量不超过实际存在的长期记忆数量
            actual_count = min(recent_long_term_count, len(self.long_term))
            if actual_count > 0:
                # 获取列表末尾的N条最新记录
                recent_items = self.long_term[-actual_count:]
                # 在提示中，通常最新的信息放在最前面，所以倒序排列
                long_term_str = "\n\n【近期经验总结 (仅显示最近 N 条,按时间倒序排列,最新在前)】\n" + "\n".join(f"- {item}" for item in reversed(recent_items))
                logger.debug(f"[MemoryManager] 已提取最近 {len(recent_items)} 条长期记忆 (倒序)。")
        
        # 未来可以加入基于相关性检索的注释，提醒LLM当前记忆检索的局限性
        long_term_str += "\n(注: 当前仅使用最近期记忆,未来版本将实现基于相关性的检索。)"
        
        context = f"{circuit_desc}{long_term_str}".strip()
        logger.debug(f"[MemoryManager] 记忆上下文 (电路+长期) 格式化完成。")
        return context