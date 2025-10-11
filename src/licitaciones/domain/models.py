from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Dict, Any


@dataclass
class Bidder:
    name: str
    amount: float


@dataclass
class Tender:
    source: str
    country: str  # ISO-2 country code
    tender_id: str
    title: str
    description: str
    buyer_name: str
    item_code: Optional[str]
    currency: str
    amount: float
    publish_date: Optional[date]
    deadline: Optional[date] = None
    bidders: List[Bidder] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    level: str  # info|warning|critical
    message: str
    tender_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
