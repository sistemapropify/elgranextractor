"""Contexto de correlación entre una consulta y sus llamadas LLM."""

from contextvars import ContextVar, Token


_current_trace_id: ContextVar[str] = ContextVar(
    'intelligence_current_trace_id',
    default='',
)


def current_trace_id() -> str:
    return _current_trace_id.get()


def bind_trace_id(trace_id: str) -> Token:
    return _current_trace_id.set(str(trace_id or ''))


def release_trace_id(token: Token | None) -> None:
    if token is not None:
        _current_trace_id.reset(token)
