from __future__ import annotations
from typing import Dict, Any, List, Iterable, Optional
from datetime import datetime, date
from ..domain.ports import TenderSourcePort, TenderRepositoryPort, NotifierPort, PersistencePort
from ..domain.services import AlertService, TrendService, AnomalyService, CollusionService, TemporalAnalysisService
from ..domain.models import Tender, Alert


class FetchTendersUseCase:
    def __init__(self, sources: List[TenderSourcePort], repo: TenderRepositoryPort) -> None:
        self._sources = sources
        self._repo = repo

    def execute(self, limit_by_source: Dict[str, int] | None = None) -> int:
        total = 0
        for src in self._sources:
            limit = None
            if limit_by_source and hasattr(src, "name"):
                limit = limit_by_source.get(getattr(src, "name"), None)
            count = self._repo.save_all(src.fetch(limit=limit))
            total += count
        return total


class AnalyzePricesUseCase:
    def __init__(self, repo: TenderRepositoryPort, persistence: Optional[PersistencePort] = None) -> None:
        self._repo = repo
        self._trend = TrendService()
        self._temporal = TemporalAnalysisService()
        self._persistence = persistence

    def execute(self, filters: Dict[str, Any], group_by: List[str]) -> Dict[str, Dict[str, float]]:
        tenders = self._repo.query(filters)
        
        # Aplicar filtros temporales si están especificados
        temporal_filters = {k: v for k, v in filters.items() if k in ['date_from', 'date_to', 'days_back']}
        if temporal_filters:
            tenders = self._temporal.filter_by_date_range(
                tenders,
                date_from=temporal_filters.get('date_from'),
                date_to=temporal_filters.get('date_to'),
                days_back=temporal_filters.get('days_back')
            )
        
        trends = self._trend.price_trends(tenders, group_by)
        
        # Persistir resultados si está habilitado
        if self._persistence:
            self._persistence.save_execution_results(
                execution_type="trends",
                data={
                    "trends": trends,
                    "groups_analyzed": len(trends),
                    "tenders_analyzed": len(tenders)
                },
                metadata={
                    "filters": filters,
                    "group_by": group_by,
                    "temporal_filters": temporal_filters
                }
            )
        
        return trends


class DetectAnomaliesUseCase:
    def __init__(self, repo: TenderRepositoryPort, persistence: Optional[PersistencePort] = None) -> None:
        self._repo = repo
        self._anomaly = AnomalyService()
        self._temporal = TemporalAnalysisService()
        self._persistence = persistence

    def execute(self, filters: Dict[str, Any], method: str = "zscore", **kwargs: Any) -> List[Alert]:
        tenders = self._repo.query(filters)
        
        # Aplicar filtros temporales si están especificados
        temporal_filters = {k: v for k, v in filters.items() if k in ['date_from', 'date_to', 'days_back']}
        if temporal_filters:
            tenders = self._temporal.filter_by_date_range(
                tenders,
                date_from=temporal_filters.get('date_from'),
                date_to=temporal_filters.get('date_to'),
                days_back=temporal_filters.get('days_back')
            )
        
        anomalies = []
        if method == "zscore":
            anomalies = self._anomaly.detect_price_anomalies(tenders, **kwargs)
        
        # Persistir resultados si está habilitado
        if self._persistence:
            anomalies_data = {
                "anomalies_count": len(anomalies),
                "anomalies": [
                    {
                        "level": anomaly.level,
                        "message": anomaly.message,
                        "data": anomaly.data
                    } for anomaly in anomalies
                ],
                "method": method,
                "tenders_analyzed": len(tenders)
            }
            
            self._persistence.save_execution_results(
                execution_type="anomalies",
                data=anomalies_data,
                metadata={
                    "filters": filters,
                    "method": method,
                    "parameters": kwargs,
                    "temporal_filters": temporal_filters
                }
            )
        
        return anomalies


class DetectCollusionUseCase:
    def __init__(self, repo: TenderRepositoryPort, persistence: Optional[PersistencePort] = None) -> None:
        self._repo = repo
        self._collusion = CollusionService()
        self._temporal = TemporalAnalysisService()
        self._persistence = persistence

    def execute(self, filters: Dict[str, Any], **kwargs: Any) -> List[Alert]:
        tenders = self._repo.query(filters)
        
        # Aplicar filtros temporales si están especificados
        temporal_filters = {k: v for k, v in filters.items() if k in ['date_from', 'date_to', 'days_back']}
        if temporal_filters:
            tenders = self._temporal.filter_by_date_range(
                tenders,
                date_from=temporal_filters.get('date_from'),
                date_to=temporal_filters.get('date_to'),
                days_back=temporal_filters.get('days_back')
            )
        
        collusions = self._collusion.detect(tenders, **kwargs)
        
        # Persistir resultados si está habilitado
        if self._persistence:
            collusions_data = {
                "collusions_count": len(collusions),
                "collusions": [
                    {
                        "level": collusion.level,
                        "message": collusion.message,
                        "data": collusion.data
                    } for collusion in collusions
                ],
                "tenders_analyzed": len(tenders)
            }
            
            self._persistence.save_execution_results(
                execution_type="collusion",
                data=collusions_data,
                metadata={
                    "filters": filters,
                    "parameters": kwargs,
                    "temporal_filters": temporal_filters
                }
            )
        
        return collusions


class GenerateAlertsUseCase:
    def __init__(self, repo: TenderRepositoryPort, notifiers: List[NotifierPort], 
                 persistence: Optional[PersistencePort] = None) -> None:
        self._repo = repo
        self._notifiers = notifiers
        self._alert = AlertService()
        self._temporal = TemporalAnalysisService()
        self._persistence = persistence

    def execute(self, filters: Dict[str, Any]) -> List[Alert]:
        tenders = self._repo.query(filters)
        
        # Aplicar filtros temporales si están especificados
        temporal_filters = {k: v for k, v in filters.items() if k in ['date_from', 'date_to', 'days_back']}
        if temporal_filters:
            tenders = self._temporal.filter_by_date_range(
                tenders,
                date_from=temporal_filters.get('date_from'),
                date_to=temporal_filters.get('date_to'),
                days_back=temporal_filters.get('days_back')
            )
        
        alerts = self._alert.build_opportunity_alerts(tenders, filters)
        
        # Persistir resultados si está habilitado
        if self._persistence:
            tenders_by_id = {tender.tender_id: tender for tender in tenders if tender.tender_id}
            # Crear reporte detallado de oportunidades encontradas
            opportunities_report = []
            active_opportunities_report = []
            alert_tenders = []
            
            for alert in alerts:
                matched_tender = self._match_tender_for_alert(alert, tenders_by_id, tenders)
                
                if matched_tender:
                    opportunity = self._build_opportunity_report_entry(matched_tender, alert, filters)
                    opportunities_report.append(opportunity)
                    alert_tenders.append(opportunity["tender_details"])
                    
                    # Verificar si la oportunidad está activa (deadline no vencido)
                    if self._is_opportunity_active(matched_tender):
                        active_opportunities_report.append(opportunity)
            
            # Crear reporte completo de oportunidades
            complete_opportunities_report = {
                "execution_summary": {
                    "timestamp": self._get_current_timestamp(),
                    "total_opportunities": len(opportunities_report),
                    "total_tenders_analyzed": len(tenders),
                    "filters_applied": filters,
                    "temporal_filters": temporal_filters
                },
                "opportunities": opportunities_report,
                "statistics": {
                    "total_value": sum(opp["tender_details"]["amount"] for opp in opportunities_report),
                    "average_value": sum(opp["tender_details"]["amount"] for opp in opportunities_report) / max(len(opportunities_report), 1),
                    "countries": list(set(opp["tender_details"]["country"] for opp in opportunities_report)),
                    "sources": list(set(opp["tender_details"]["source"] for opp in opportunities_report)),
                    "value_ranges": self._categorize_by_value(opportunities_report),
                    "top_buyers": self._get_top_buyers_from_opportunities(opportunities_report)
                }
            }
            
            # Guardar reporte específico de oportunidades
            self._persistence.save_execution_results(
                execution_type="opportunities_report",
                data=complete_opportunities_report,
                metadata={
                    "filters": filters,
                    "temporal_filters": temporal_filters,
                    "total_opportunities": len(opportunities_report)
                }
            )
            
            # Crear y guardar reporte de oportunidades activas (deadline no vencido)
            if active_opportunities_report:
                active_opportunities_complete = {
                    "execution_summary": {
                        "timestamp": self._get_current_timestamp(),
                        "total_active_opportunities": len(active_opportunities_report),
                        "total_opportunities_analyzed": len(opportunities_report),
                        "filters_applied": filters,
                        "temporal_filters": temporal_filters
                    },
                    "active_opportunities": active_opportunities_report,
                    "statistics": {
                        "total_value": sum(opp.get('tender_details', {}).get('amount', 0) for opp in active_opportunities_report),
                        "average_value": sum(opp.get('tender_details', {}).get('amount', 0) for opp in active_opportunities_report) / len(active_opportunities_report) if active_opportunities_report else 0.0,
                        "countries": list(set(opp.get('tender_details', {}).get('country') for opp in active_opportunities_report if opp.get('tender_details', {}).get('country'))),
                        "sources": list(set(opp.get('tender_details', {}).get('source') for opp in active_opportunities_report if opp.get('tender_details', {}).get('source'))),
                        "value_ranges": self._categorize_by_value(active_opportunities_report),
                        "top_buyers": self._get_top_buyers_from_opportunities(active_opportunities_report)
                    }
                }
                
                self._persistence.save_execution_results(
                    execution_type="active_opportunities",
                    data=active_opportunities_complete,
                    metadata={
                        "filters": filters,
                        "temporal_filters": temporal_filters,
                        "total_active_opportunities": len(active_opportunities_report),
                        "total_opportunities_analyzed": len(opportunities_report)
                    }
                )
            
            # También mantener el reporte tradicional de alertas para compatibilidad
            alerts_data = {
                "alerts_count": len(alerts),
                "alerts": [
                    {
                        "level": alert.level,
                        "message": alert.message,
                        "tender_id": alert.tender_id,
                        "data": alert.data
                    } for alert in alerts
                ],
                "alert_tenders": alert_tenders,
                "tenders_analyzed": len(tenders),
                "summary_stats": {
                    "total_amount": sum(t.amount for t in tenders if t.amount > 0),
                    "avg_amount": sum(t.amount for t in tenders if t.amount > 0) / max(len([t for t in tenders if t.amount > 0]), 1),
                    "countries": list(set(t.country for t in tenders)),
                    "sources": list(set(getattr(t, 'source', 'unknown') for t in tenders))
                }
            }
            
            self._persistence.save_execution_results(
                execution_type="alerts",
                data=alerts_data,
                metadata={
                    "filters": filters,
                    "temporal_filters": temporal_filters,
                    "tenders_count": len(tenders)
                }
            )
        
        for n in self._notifiers:
            n.notify(alerts)
        return alerts

    def _match_tender_for_alert(
        self,
        alert: Alert,
        tenders_by_id: Dict[str, Tender],
        tenders: List[Tender],
    ) -> Optional[Tender]:
        """Resuelve la licitación de una alerta priorizando tender_id y usando texto solo como fallback."""
        if alert.tender_id and alert.tender_id in tenders_by_id:
            return tenders_by_id[alert.tender_id]

        alert_message = alert.message.upper()
        for tender in tenders:
            if (tender.title and tender.title.upper() in alert_message) or \
               (tender.buyer_name and tender.buyer_name.upper() in alert_message) or \
               (tender.tender_id and tender.tender_id in alert.message):
                return tender
        return None

    def _build_opportunity_report_entry(
        self,
        tender: Tender,
        alert: Alert,
        filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Construye una entrada de reporte a partir de una licitación y su alerta asociada."""
        return {
            "opportunity_id": f"{tender.source}_{tender.tender_id}",
            "alert_level": alert.level,
            "alert_message": alert.message,
            "tender_details": {
                "tender_id": tender.tender_id,
                "title": tender.title,
                "description": tender.description,
                "buyer_name": tender.buyer_name,
                "amount": tender.amount,
                "currency": tender.currency,
                "country": tender.country,
                "source": tender.source,
                "publish_date": tender.publish_date.isoformat() if tender.publish_date else None,
                "deadline": tender.deadline.isoformat() if tender.deadline else None,
                "item_code": tender.item_code,
                "bidders": [
                    {
                        "name": bidder.name,
                        "amount": bidder.amount,
                    }
                    for bidder in tender.bidders
                ],
                "raw_data": tender.raw,
            },
            "analysis_info": {
                "matched_keywords": [
                    kw for kw in filters.get("keywords", [])
                    if kw.lower() in (tender.title + " " + tender.description).lower()
                ],
                "amount_in_range": filters.get("min_amount", 0) <= tender.amount <= filters.get("max_amount", float("inf")),
                "country_match": tender.country in filters.get("countries", []),
                "opportunity_score": self._calculate_opportunity_score(tender, filters),
            },
        }
    
    def _calculate_opportunity_score(self, tender: Tender, filters: Dict[str, Any]) -> float:
        """Calcula un puntaje de oportunidad basado en criterios."""
        score = 0.0
        
        # Puntaje por coincidencia de keywords
        keywords = filters.get("keywords", [])
        text_content = (tender.title + " " + tender.description).lower()
        keyword_matches = sum(1 for kw in keywords if kw.lower() in text_content)
        score += keyword_matches * 10
        
        # Puntaje por monto (normalizado)
        if tender.amount > 0:
            if tender.amount <= 50000000:  # Hasta 50M COP - bueno para PyMEs
                score += 20
            elif tender.amount <= 200000000:  # Hasta 200M COP - mediano
                score += 15
            else:  # Más de 200M COP - grande
                score += 10
        
        # Puntaje por fecha (más reciente = mejor)
        if tender.publish_date:
            from datetime import date
            days_old = (date.today() - tender.publish_date).days
            if days_old <= 7:
                score += 15
            elif days_old <= 30:
                score += 10
            elif days_old <= 90:
                score += 5
        
        return min(score, 100.0)  # Máximo 100 puntos
    
    def _get_current_timestamp(self) -> str:
        """Obtiene timestamp actual en formato ISO."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _is_opportunity_active(self, tender: Tender) -> bool:
        """Verifica si una oportunidad está activa (deadline no vencido)."""
        if not tender.deadline:
            return True  # Si no hay deadline, se considera activa
        
        try:
            current_date = date.today()
            
            # Convertir deadline a fecha
            if isinstance(tender.deadline, str):
                # Parsear fecha en formato YYYY-MM-DD
                if len(tender.deadline) >= 10:
                    date_part = tender.deadline[:10]  # Tomar solo YYYY-MM-DD
                    deadline_date = datetime.strptime(date_part, '%Y-%m-%d').date()
                else:
                    return True  # Formato inválido, considerar activa
            elif isinstance(tender.deadline, datetime):
                deadline_date = tender.deadline.date()
            elif isinstance(tender.deadline, date):
                deadline_date = tender.deadline
            else:
                return True  # Tipo desconocido, considerar activa
            
            # Comparar con fecha actual
            return deadline_date >= current_date
        except (ValueError, AttributeError, TypeError):
            # Si hay error parsing fecha, se considera activa por defecto
            return True
    
    def _categorize_by_value(self, opportunities: List[Dict[str, Any]]) -> Dict[str, int]:
        """Categoriza oportunidades por rangos de valor."""
        ranges = {
            "hasta_50M": 0,
            "50M_200M": 0,
            "200M_500M": 0,
            "mas_500M": 0
        }
        
        for opp in opportunities:
            amount = opp["tender_details"]["amount"]
            if amount <= 50000000:
                ranges["hasta_50M"] += 1
            elif amount <= 200000000:
                ranges["50M_200M"] += 1
            elif amount <= 500000000:
                ranges["200M_500M"] += 1
            else:
                ranges["mas_500M"] += 1
        
        return ranges
    
    def _get_top_buyers_from_opportunities(self, opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Obtiene los compradores más frecuentes de las oportunidades."""
        buyer_stats = {}
        
        for opp in opportunities:
            buyer = opp["tender_details"]["buyer_name"]
            if buyer not in buyer_stats:
                buyer_stats[buyer] = {"count": 0, "total_value": 0}
            buyer_stats[buyer]["count"] += 1
            buyer_stats[buyer]["total_value"] += opp["tender_details"]["amount"]
        
        # Ordenar por número de oportunidades
        top_buyers = sorted(buyer_stats.items(), key=lambda x: x[1]["count"], reverse=True)[:5]
        
        return [
            {
                "buyer_name": buyer,
                "opportunities_count": stats["count"],
                "total_value": stats["total_value"],
                "average_value": stats["total_value"] / stats["count"]
            }
            for buyer, stats in top_buyers
        ]


class TemporalAnalysisUseCase:
    """Caso de uso para análisis temporal de licitaciones."""
    
    def __init__(self, repo: TenderRepositoryPort, persistence: Optional[PersistencePort] = None) -> None:
        self._repo = repo
        self._temporal = TemporalAnalysisService()
        self._persistence = persistence

    def execute(self, filters: Dict[str, Any], interval: str = "monthly") -> Dict[str, Any]:
        """
        Ejecuta análisis temporal de licitaciones.
        
        Args:
            filters: Filtros de consulta incluyendo filtros temporales
            interval: Intervalo de análisis ('daily', 'weekly', 'monthly')
        """
        tenders = self._repo.query(filters)
        
        # Aplicar filtros temporales
        temporal_filters = {k: v for k, v in filters.items() if k in ['date_from', 'date_to', 'days_back']}
        if temporal_filters:
            tenders = self._temporal.filter_by_date_range(
                tenders,
                date_from=temporal_filters.get('date_from'),
                date_to=temporal_filters.get('date_to'),
                days_back=temporal_filters.get('days_back')
            )
        
        analysis = self._temporal.analyze_temporal_trends(tenders, interval)
        
        # Persistir resultados si está habilitado
        if self._persistence:
            self._persistence.save_execution_results(
                execution_type="temporal_analysis",
                data=analysis,
                metadata={
                    "filters": filters,
                    "interval": interval,
                    "temporal_filters": temporal_filters,
                    "tenders_analyzed": len(tenders)
                }
            )
        
        return analysis


class PersistenceManagementUseCase:
    """Caso de uso para gestionar la persistencia de datos."""
    
    def __init__(self, persistence: PersistencePort) -> None:
        self._persistence = persistence
    
    def get_execution_history(self, execution_type: Optional[str] = None, 
                            limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Obtiene el historial de ejecuciones."""
        return self._persistence.load_execution_history(execution_type, limit)
    
    def cleanup_old_executions(self, days_old: int = 30) -> int:
        """Limpia ejecuciones antiguas."""
        return self._persistence.cleanup_old_files(days_old)
    
    def save_full_execution_summary(self, execution_data: Dict[str, Any], 
                                  metadata: Dict[str, Any]) -> str:
        """Guarda resumen completo de una ejecución."""
        return self._persistence.save_execution_results(
            execution_type="full_execution",
            data=execution_data,
            metadata=metadata
        )
