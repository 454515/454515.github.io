"""Processor data models. See spec-03 §3."""
from dataclasses import dataclass, field


@dataclass
class CardResult:
    """Structured result of extracting fields from one card image."""

    card_type: str = ""                 # card type, e.g. "idcard"
    fields: dict[str, str] = field(default_factory=dict)   # extracted field values
    missing: list[str] = field(default_factory=list)        # missing/invalid field names
