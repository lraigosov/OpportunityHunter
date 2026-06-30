#!/usr/bin/env python3
"""
Herramienta para visualizar reportes de persistencia de la plataforma de licitaciones.
Muestra los datos persistidos de manera legible y organizada.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import click

# Add project root to path for imports
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from licitaciones.infrastructure.persistence import LocalFilePersistence
from licitaciones.app.use_cases import PersistenceManagementUseCase


def format_currency(amount: float, currency: str = "COP") -> str:
    """Formatea moneda de manera legible."""
    if currency == "COP":
        return f"${amount:,.0f} COP"
    return f"{amount:,.2f} {currency}"


def format_datetime(timestamp_str: str) -> str:
    """Formatea timestamp de manera legible."""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return timestamp_str


def display_alert_report(data: Dict[str, Any]) -> None:
    """Muestra reporte detallado de alertas."""
    execution_data = data.get("data", {})
    metadata = data.get("metadata", {})
    
    click.echo(f"📊 REPORTE DE ALERTAS")
    click.echo(f"⏰ Timestamp: {format_datetime(data.get('timestamp', ''))}")
    click.echo(f"🔍 Filtros aplicados: {len(metadata.get('filters', {}).get('keywords', []))} keywords")
    click.echo(f"🌎 Países: {', '.join(metadata.get('filters', {}).get('countries', []))}")
    click.echo("=" * 60)
    
    # Estadísticas generales
    stats = execution_data.get("summary_stats", {})
    click.echo(f"📈 ESTADÍSTICAS GENERALES:")
    click.echo(f"  • Total licitaciones analizadas: {execution_data.get('tenders_analyzed', 0)}")
    click.echo(f"  • Alertas generadas: {execution_data.get('alerts_count', 0)}")
    click.echo(f"  • Valor total: {format_currency(stats.get('total_amount', 0))}")
    click.echo(f"  • Valor promedio: {format_currency(stats.get('avg_amount', 0))}")
    click.echo(f"  • Fuentes: {', '.join(stats.get('sources', []))}")
    click.echo()
    
    # Alertas detalladas
    alerts = execution_data.get("alerts", [])
    if alerts:
        click.echo(f"🚨 ALERTAS GENERADAS ({len(alerts)}):")
        for i, alert in enumerate(alerts, 1):
            level_icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(alert.get("level", "info"), "•")
            click.echo(f"  {level_icon} {alert.get('message', 'Sin mensaje')}")
        click.echo()
    
    # Licitaciones que generaron alertas
    alert_tenders = execution_data.get("alert_tenders", [])
    if alert_tenders:
        click.echo(f"📋 LICITACIONES RELEVANTES ({len(alert_tenders)}):")
        for i, tender in enumerate(alert_tenders, 1):
            click.echo(f"  {i}. {tender.get('title', 'Sin título')}")
            click.echo(f"     💰 {format_currency(tender.get('amount', 0), tender.get('currency', 'COP'))}")
            click.echo(f"     🏢 {tender.get('buyer_name', 'Comprador desconocido')}")
            click.echo(f"     🌍 {tender.get('country', '')} • 📅 {tender.get('publish_date', 'Sin fecha')}")
            if tender.get('description'):
                desc = tender['description'][:150] + "..." if len(tender['description']) > 150 else tender['description']
                click.echo(f"     📝 {desc}")
            click.echo()


def display_full_execution_report(data: Dict[str, Any]) -> None:
    """Muestra reporte completo de ejecución."""
    execution_data = data.get("data", {})
    metadata = data.get("metadata", {})
    
    click.echo(f"🎯 REPORTE COMPLETO DE EJECUCIÓN")
    click.echo(f"⏰ Timestamp: {format_datetime(data.get('timestamp', ''))}")
    click.echo("=" * 60)
    
    # Estadísticas de ejecución
    exec_stats = execution_data.get("execution_stats", {})
    click.echo(f"📊 RESULTADOS DE ANÁLISIS:")
    click.echo(f"  • Alertas generadas: {exec_stats.get('alerts_count', 0)}")
    click.echo(f"  • Grupos de tendencias: {exec_stats.get('trends_count', 0)}")
    click.echo(f"  • Anomalías detectadas: {exec_stats.get('anomalies_count', 0)}")
    click.echo(f"  • Posibles colusiones: {exec_stats.get('collusions_count', 0)}")
    click.echo(f"  • Total licitaciones procesadas: {exec_stats.get('total_tenders_processed', 0)}")
    click.echo()
    
    # Resumen de datos
    data_summary = execution_data.get("data_summary", {})
    if data_summary:
        click.echo(f"📈 RESUMEN DE DATOS:")
        click.echo(f"  • Países: {', '.join(data_summary.get('countries', []))}")
        click.echo(f"  • Fuentes: {', '.join(data_summary.get('sources', []))}")
        click.echo(f"  • Valor total: {format_currency(data_summary.get('total_amount', 0))}")
        click.echo(f"  • Valor promedio: {format_currency(data_summary.get('average_amount', 0))}")
        
        amount_range = data_summary.get('amount_range', {})
        if amount_range:
            click.echo(f"  • Rango de valores: {format_currency(amount_range.get('min', 0))} - {format_currency(amount_range.get('max', 0))}")
        click.echo()
    
    # Análisis temporal
    temporal = execution_data.get("temporal_analysis")
    if temporal and temporal.get("summary"):
        temp_summary = temporal["summary"]
        click.echo(f"📅 ANÁLISIS TEMPORAL:")
        click.echo(f"  • Períodos analizados: {temp_summary.get('total_periods', 0)}")
        click.echo(f"  • Licitaciones en rango: {temp_summary.get('total_tenders', 0)}")
        date_range = temp_summary.get('date_range', {})
        if date_range:
            click.echo(f"  • Rango de fechas: {date_range.get('from', '')} → {date_range.get('to', '')}")
        click.echo()
    
    # Muestras de alertas
    alert_samples = execution_data.get("alert_samples", [])
    if alert_samples:
        click.echo(f"🚨 MUESTRA DE ALERTAS:")
        for alert in alert_samples[:5]:
            level_icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(alert.get("level", "info"), "•")
            click.echo(f"  {level_icon} {alert.get('message', 'Sin mensaje')}")
        if len(alert_samples) > 5:
            click.echo(f"  ... y {len(alert_samples) - 5} alertas más")
        click.echo()


@click.command()
@click.option("--type", "report_type", type=click.Choice(['alerts', 'trends', 'anomalies', 'collusion', 'temporal_analysis', 'full_execution', 'all']), 
              default='all', help="Tipo de reporte a mostrar")
@click.option("--limit", type=int, default=10, help="Número máximo de reportes a mostrar")
@click.option("--detailed", is_flag=True, help="Mostrar información detallada")
@click.option("--persistence-dir", type=click.Path(exists=True, file_okay=False), help="Directorio de persistencia personalizado")
def main(report_type: str, limit: int, detailed: bool, persistence_dir: Optional[str]) -> None:
    """
    Visualizador de reportes de persistencia de la plataforma de licitaciones.
    
    Muestra los datos persistidos de manera organizada y legible.
    """
    
    # Configurar persistencia
    if persistence_dir:
        persistence = LocalFilePersistence(Path(persistence_dir))
    else:
        persistence = LocalFilePersistence()
    
    persistence_mgmt = PersistenceManagementUseCase(persistence)
    
    click.echo("🔍 VISUALIZADOR DE REPORTES DE LICITACIONES")
    click.echo("=" * 60)
    
    # Mostrar estadísticas generales
    if hasattr(persistence, 'get_statistics'):
        stats = persistence.get_statistics()
        click.echo(f"📊 ESTADÍSTICAS DE PERSISTENCIA:")
        click.echo(f"  • Total archivos: {stats.get('total_files', 0)}")
        click.echo(f"  • Tamaño total: {stats.get('total_size_bytes', 0) / 1024:.1f} KB")
        
        by_type = stats.get('by_type', {})
        if by_type:
            click.echo(f"  • Por tipo:")
            for exec_type, type_stats in by_type.items():
                if type_stats['count'] > 0:
                    click.echo(f"    - {exec_type}: {type_stats['count']} archivos ({type_stats['size_bytes'] / 1024:.1f} KB)")
        click.echo()
    
    # Obtener y mostrar reportes
    if report_type == 'all':
        for exec_type in ['full_execution', 'alerts', 'trends', 'anomalies', 'collusion', 'temporal_analysis']:
            reports = persistence_mgmt.get_execution_history(exec_type, min(limit, 3))
            if reports:
                click.echo(f"📂 ÚLTIMOS REPORTES DE {exec_type.upper().replace('_', ' ')} ({len(reports)}):")
                for report in reports:
                    timestamp = format_datetime(report.get('timestamp', ''))
                    file_name = Path(report.get('file_path', '')).name
                    click.echo(f"  • {timestamp} - {file_name}")
                click.echo()
    else:
        reports = persistence_mgmt.get_execution_history(report_type if report_type != 'all' else None, limit)
        
        if not reports:
            click.echo(f"❌ No se encontraron reportes del tipo '{report_type}'")
            return
        
        click.echo(f"📋 REPORTES ENCONTRADOS: {len(reports)}")
        click.echo()
        
        for i, report in enumerate(reports, 1):
            click.echo(f"📄 REPORTE {i}/{len(reports)}")
            click.echo("-" * 40)
            
            if detailed:
                if report.get('execution_type') == 'alerts':
                    display_alert_report(report)
                elif report.get('execution_type') == 'full_execution':
                    display_full_execution_report(report)
                else:
                    # Mostrar formato genérico
                    click.echo(f"Tipo: {report.get('execution_type', 'Desconocido')}")
                    click.echo(f"Timestamp: {format_datetime(report.get('timestamp', ''))}")
                    click.echo(f"Archivo: {Path(report.get('file_path', '')).name}")
                    
                    data = report.get('data', {})
                    if data:
                        click.echo("Contenido:")
                        click.echo(json.dumps(data, indent=2, ensure_ascii=False)[:500] + "...")
            else:
                click.echo(f"• Tipo: {report.get('execution_type', 'Desconocido')}")
                click.echo(f"• Timestamp: {format_datetime(report.get('timestamp', ''))}")
                click.echo(f"• Archivo: {Path(report.get('file_path', '')).name}")
                click.echo(f"• Tamaño: {report.get('file_size', 0) / 1024:.1f} KB")
            
            click.echo()
            
            if i < len(reports):
                click.echo()


if __name__ == "__main__":
    main()