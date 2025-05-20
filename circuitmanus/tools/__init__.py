# IDT_AGENT_Pro/circuitmanus/tools/__init__.py
"""
Agent Tools: Definitions, Registration, and Execution.
This sub-package manages the tools available to the agent,
how they are registered, and how they are executed.
"""
from .base import register_tool
from .executor import ToolExecutor
# 具体工具函数将在各自模块定义，由 Agent 类导入和使用

__all__ = ["register_tool", "ToolExecutor"]