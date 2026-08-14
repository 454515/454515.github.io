# Field-extraction layer - per-card-type processors.
from src.processors.base import BaseProcessor
from src.processors.idcard import IDCardProcessor
from src.processors.invoice import InvoiceProcessor
from src.processors.models import CardResult
from src.processors.registry import get_processor, register_processor, registered_types

register_processor(IDCardProcessor.card_type, IDCardProcessor())
register_processor(InvoiceProcessor.card_type, InvoiceProcessor())
