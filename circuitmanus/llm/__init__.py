# IDT_AGENT_Pro/circuitmanus/llm/__init__.py
"""
LLM Interaction and Output Parsing.
Contains modules for communicating with the Language Model and
parsing its structured responses.
"""
from .interface import LLMInterface
from .parser import OutputParser

__all__ = ["LLMInterface", "OutputParser"]