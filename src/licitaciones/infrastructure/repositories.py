from __future__ import annotations
from typing import Iterable, List, Dict, Any
from ..domain.models import Tender


class InMemoryTenderRepository:
    def __init__(self) -> None:
        self._items: List[Tender] = []

    def save_all(self, tenders: Iterable[Tender]) -> int:
        count = 0
        for t in tenders:
            self._items.append(t)
            count += 1
        return count

    def query(self, filters: Dict[str, Any]) -> List[Tender]:
        result: List[Tender] = []
        keywords = [k.lower() for k in filters.get("keywords", [])]
        countries = set(filters.get("countries", []))
        min_amount = filters.get("min_amount", 0)
        max_amount = filters.get("max_amount", float("inf"))
        buyer_names = [b.lower() for b in filters.get("buyer_names", [])]
        for t in self._items:
            if countries and t.country not in countries:
                continue
            if t.amount < min_amount or t.amount > max_amount:
                continue
            if buyer_names and t.buyer_name.lower() not in buyer_names:
                continue
            text = f"{t.title} {t.description}".lower()
            if keywords and not any(k in text for k in keywords):
                continue
            result.append(t)
        return result
