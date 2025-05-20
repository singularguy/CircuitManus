# IDT_AGENT_Pro/circuitmanus/__init__.py
"""
CircuitManus Agent Core Package.
This package contains all the core logic for the CircuitManus agent,
including domain models, memory management, LLM interaction, tools, and orchestration.
"""
import logging

# 可以在这里预先导入一些最顶层的类，方便外部直接从 circuitmanus 包导入
# 例如: from .agent import CircuitAgent
# 但为了保持模块间的解耦，也可以不在顶层 __init__ 中暴露过多内部实现

logger = logging.getLogger(__name__)
logger.info("CircuitManus core package initialized.")

# 版本信息可以放在这里
__version__ = "1.0.0_refactored"