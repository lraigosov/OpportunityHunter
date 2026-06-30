from __future__ import annotations
from typing import List, Dict, Any, Optional
from statistics import mean, pstdev
from datetime import datetime, timedelta
from .models import Tender, Alert


class AlertService:
    def build_opportunity_alerts(self, tenders: List[Tender], filters: Dict[str, Any]) -> List[Alert]:
        alerts: List[Alert] = []
        keywords = [k.lower() for k in filters.get("keywords", [])]
        for t in tenders:
            text = f"{t.title} {t.description}".lower()
            if any(k in text for k in keywords):
                alerts.append(Alert(level="info", message=f"Oportunidad: {t.title} ({t.country})", tender_id=t.tender_id))
        return alerts


class TrendService:
    def price_trends(self, tenders: List[Tender], group_by: List[str]) -> Dict[str, Dict[str, float]]:
        # Simple trend summary: average amount per group
        groups: Dict[str, List[float]] = {}
        for t in tenders:
            key_parts = []
            for g in group_by:
                key_parts.append(str(getattr(t, g, t.raw.get(g))))
            key = "|".join(key_parts)
            groups.setdefault(key, []).append(t.amount)
        result: Dict[str, Dict[str, float]] = {}
        for k, values in groups.items():
            if not values:
                continue
            mu = mean(values)
            sd = pstdev(values) if len(values) > 1 else 0.0
            result[k] = {"avg": mu, "std": sd, "count": len(values)}
        return result


class AnomalyService:
    def zscore(self, values: List[float]) -> List[float]:
        if not values:
            return []
        mu = mean(values)
        sd = pstdev(values) if len(values) > 1 else 0.0
        if sd == 0:
            return [0.0 for _ in values]
        return [(v - mu) / sd for v in values]

    def detect_price_anomalies(self, tenders: List[Tender], z: float = 3.0, min_points: int = 10) -> List[Alert]:
        if len(tenders) < min_points:
            return []
        vals = [t.amount for t in tenders]
        zs = self.zscore(vals)
        alerts: List[Alert] = []
        for t, zval in zip(tenders, zs):
            if abs(zval) >= z:
                alerts.append(Alert(level="warning", message=f"Anomalía de precio z={zval:.2f} en {t.tender_id}", tender_id=t.tender_id, data={"z": zval, "amount": t.amount}))
        return alerts


class CollusionService:
    # Heurística simple: si múltiples licitaciones comparten exactamente el mismo conjunto de postores y montos muy cercanos
    def detect(self, tenders: List[Tender], min_bidders: int = 3, similarity_threshold: float = 0.95) -> List[Alert]:
        alerts: List[Alert] = []
        # Mapa de firma de postores -> lista de licitaciones
        def bidder_signature(t: Tender) -> str:
            names = sorted([b.name for b in t.bidders])
            return "|".join(names)

        groups: Dict[str, List[Tender]] = {}
        for t in tenders:
            if len(t.bidders) >= min_bidders:
                groups.setdefault(bidder_signature(t), []).append(t)

        for sig, group in groups.items():
            if len(group) < 2:
                continue
            # Check similarity of bids across tenders
            def price_vector(t: Tender) -> List[float]:
                # order bidders by name
                order = [name for name in sorted([b.name for b in t.bidders])]
                amounts_by_name = {b.name: float(b.amount) for b in t.bidders}
                return [amounts_by_name[n] for n in order]

            ref = price_vector(group[0])
            for other in group[1:]:
                vec = price_vector(other)
                if len(ref) != len(vec) or not ref:
                    continue
                # cosine similarity
                import math
                dot = sum(a*b for a, b in zip(ref, vec))
                norm1 = math.sqrt(sum(a*a for a in ref))
                norm2 = math.sqrt(sum(b*b for b in vec))
                sim = dot / (norm1 * norm2) if norm1 and norm2 else 0.0
                if sim >= similarity_threshold:
                    ids = ", ".join(t.tender_id for t in group)
                    alerts.append(Alert(level="critical", message=f"Posible colusión (sim={sim:.2f}) entre licitaciones: {ids}", data={"similarity": sim, "signature": sig}))
                    break
        return alerts


class TemporalAnalysisService:
    """Servicio para análisis temporal de licitaciones con filtros por fechas."""
    
    def filter_by_date_range(self, tenders: List[Tender], date_from: Optional[str] = None, 
                           date_to: Optional[str] = None, days_back: Optional[int] = None) -> List[Tender]:
        """
        Filtra licitaciones por rango de fechas.
        
        Args:
            tenders: Lista de licitaciones
            date_from: Fecha inicio en formato 'YYYY-MM-DD' 
            date_to: Fecha fin en formato 'YYYY-MM-DD'
            days_back: Número de días hacia atrás desde hoy (alternativa a date_from/date_to)
        """
        if not tenders:
            return []
        
        # Si se especifica days_back, calcular date_from
        if days_back and not date_from:
            date_from = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        # Si no hay filtros de fecha, retornar todas
        if not date_from and not date_to:
            return tenders
        
        filtered = []
        for tender in tenders:
            tender_date = self._extract_tender_date(tender)
            if not tender_date:
                continue
            
            # Aplicar filtros
            if date_from and tender_date < date_from:
                continue
            if date_to and tender_date > date_to:
                continue
                
            filtered.append(tender)
        
        return filtered
    
    def _extract_tender_date(self, tender: Tender) -> Optional[str]:
        """Extrae la fecha de publicación de una licitación."""
        # Intentar obtener fecha del campo publish_date si existe
        if hasattr(tender, 'publish_date') and tender.publish_date:
            if isinstance(tender.publish_date, str):
                # Convertir a formato YYYY-MM-DD si está en otro formato
                try:
                    # Si ya está en formato YYYY-MM-DD, devolverlo directamente
                    if len(tender.publish_date) >= 10 and tender.publish_date[4] == '-' and tender.publish_date[7] == '-':
                        return tender.publish_date[:10]
                    
                    # Intentar parsear formato ISO con diferentes variantes
                    date_text = tender.publish_date
                    if 'T' in date_text:
                        date_text = date_text.split('T')[0]
                    if '.' in date_text:
                        date_text = date_text.split('.')[0]
                    
                    # Validar formato básico YYYY-MM-DD
                    if len(date_text) == 10 and date_text[4] == '-' and date_text[7] == '-':
                        return date_text
                        
                except (AttributeError, TypeError, ValueError):
                    pass
        
        # Buscar en datos raw
        raw_date = tender.raw.get('fecha_de_publicacion_del') or tender.raw.get('publish_date') or tender.raw.get('fecha_publicacion')
        if raw_date and isinstance(raw_date, str):
            try:
                # Limpiar formato de fecha (remover timestamp)
                clean_date = raw_date.split('T')[0]
                if len(clean_date) == 10 and clean_date[4] == '-' and clean_date[7] == '-':
                    return clean_date
            except (AttributeError, TypeError, ValueError):
                pass
        
        return None
    
    def analyze_temporal_trends(self, tenders: List[Tender], interval: str = "monthly") -> Dict[str, Any]:
        """
        Analiza tendencias temporales de licitaciones.
        
        Args:
            tenders: Lista de licitaciones
            interval: Intervalo de análisis ('daily', 'weekly', 'monthly')
        """
        if not tenders:
            return {}
        
        # Agrupar por periodo
        periods: Dict[str, List[Tender]] = {}
        
        for tender in tenders:
            tender_date = self._extract_tender_date(tender)
            if not tender_date:
                continue
            
            try:
                date_obj = datetime.strptime(tender_date, '%Y-%m-%d')
                
                if interval == "daily":
                    period_key = date_obj.strftime('%Y-%m-%d')
                elif interval == "weekly":
                    # Inicio de semana (lunes)
                    start_of_week = date_obj - timedelta(days=date_obj.weekday())
                    period_key = start_of_week.strftime('%Y-%m-%d')
                else:  # monthly
                    period_key = date_obj.strftime('%Y-%m')
                
                periods.setdefault(period_key, []).append(tender)
            except (TypeError, ValueError):
                continue
        
        # Calcular estadísticas por periodo
        analysis = {}
        for period, period_tenders in periods.items():
            amounts = [t.amount for t in period_tenders if t.amount > 0]
            analysis[period] = {
                "count": len(period_tenders),
                "total_amount": sum(amounts),
                "avg_amount": mean(amounts) if amounts else 0,
                "countries": list(set(t.country for t in period_tenders)),
                "top_buyers": self._get_top_buyers(period_tenders, limit=3)
            }
        
        return {
            "interval": interval,
            "periods": analysis,
            "summary": {
                "total_periods": len(periods),
                "total_tenders": len(tenders),
                "date_range": {
                    "from": min(periods.keys()) if periods else None,
                    "to": max(periods.keys()) if periods else None
                }
            }
        }
    
    def _get_top_buyers(self, tenders: List[Tender], limit: int = 3) -> List[Dict[str, Any]]:
        """Obtiene los compradores más activos en un periodo."""
        buyer_stats: Dict[str, Dict[str, Any]] = {}
        
        for tender in tenders:
            buyer = tender.buyer_name or "Desconocido"
            if buyer not in buyer_stats:
                buyer_stats[buyer] = {"count": 0, "total_amount": 0}
            
            buyer_stats[buyer]["count"] += 1
            buyer_stats[buyer]["total_amount"] += tender.amount
        
        # Ordenar por número de licitaciones
        sorted_buyers = sorted(buyer_stats.items(), key=lambda x: x[1]["count"], reverse=True)
        
        return [
            {
                "name": buyer,
                "count": stats["count"],
                "total_amount": stats["total_amount"]
            }
            for buyer, stats in sorted_buyers[:limit]
        ]
