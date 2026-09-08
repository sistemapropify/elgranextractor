"""Shared, browser-independent contracts for scraping runs."""
from dataclasses import dataclass


class ScrapingInterrupted(RuntimeError):
    """The job was stopped, paused during a write, or its owner changed."""


@dataclass
class Discovery:
    stop_reason: str = 'unknown'
    complete: bool = False
    pages: int = 0
    unique_ids: int = 0
    duplicates: int = 0
    invalid: int = 0
    details_failed: int = 0
    final_url: str = ''

    def as_dict(self):
        return dict(vars(self))


class ScrapeRows(list):
    """List compatibility for scripts, with explicit coverage for the worker."""
    def __init__(self, rows=(), *, discovery=None):
        super().__init__(rows)
        self.discovery = discovery or Discovery()


def outcome(rows):
    result = getattr(rows, 'discovery', None)
    return result.as_dict() if result else Discovery(stop_reason='legacy_result').as_dict()
