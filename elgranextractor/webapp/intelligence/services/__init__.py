"""
Paquete de servicios para la capa de inteligencia.
"""
from .memory import MemoryService
from .rag import RAGService
from .llm import LLMService
from .episodic_memory import EpisodicMemoryService
from .prompts import (
    PromptManager,
    format_episodic_context,
    format_memory_context,
    format_rag_context,
    build_full_prompt,
    build_orchestration_prompt,
    parse_orchestration_response,
    format_skills_for_prompt,
    format_conversation_history,
    OrchestrationDecision,
    DEFAULT_SYSTEM_PROMPT,
    ORCHESTRATION_SYSTEM_PROMPT,
)
from .metrics import MetricsService, StructuredLogger, log
from .intent_classifier import IntentClassifier, IntentType, IntentResult

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chat_processor import ChatProcessor, ChatResult, ChatContext, StreamChunk


def __getattr__(name: str):
    if name in {'ChatProcessor', 'ChatResult', 'ChatContext', 'StreamChunk'}:
        from .chat_processor import ChatProcessor, ChatResult, ChatContext, StreamChunk
        return locals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")

__all__ = [
    'MemoryService',
    'RAGService',
    'LLMService',
    'EpisodicMemoryService',
    'PromptManager',
    'format_episodic_context',
    'format_memory_context',
    'format_rag_context',
    'build_full_prompt',
    'build_orchestration_prompt',
    'parse_orchestration_response',
    'format_skills_for_prompt',
    'format_conversation_history',
    'OrchestrationDecision',
    'DEFAULT_SYSTEM_PROMPT',
    'ORCHESTRATION_SYSTEM_PROMPT',
    'MetricsService',
    'StructuredLogger',
    'log',
    'IntentClassifier',
    'IntentType',
    'IntentResult',
    'ChatProcessor',
    'ChatResult',
    'ChatContext',
    'StreamChunk',
]
