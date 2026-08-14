"""Processor registry: card_type -> processor. See spec-03 §4."""
from src.processors.base import BaseProcessor

_processors: dict[str, BaseProcessor] = {}


def register_processor(card_type: str, processor: BaseProcessor) -> None:
    """Register a processor for a card type (overwrites if present)."""
    _processors[card_type] = processor


def get_processor(card_type: str) -> BaseProcessor:
    """Return the processor registered for card_type."""
    return _processors[card_type]


def registered_types() -> list[str]:
    """List registered card types (sorted)."""
    return sorted(_processors)
