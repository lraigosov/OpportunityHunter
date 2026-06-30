"""
CLI module for the licitaciones platform.
Provides command-line interface functionality.
"""
from __future__ import annotations
import os
from pathlib import Path
import time
import click
import logging
from datetime import datetime
from typing import Optional

from licitaciones.infrastructure.config_loader import JsonConfigLoader
from licitaciones.infrastructure.repositories import InMemoryTenderRepository
from licitaciones.infrastructure.sources import JsonLinesSource
from licitaciones.infrastructure.notifiers import ConsoleNotifier, FileNotifier
from licitaciones.infrastructure.persistence import LocalFilePersistence
from licitaciones.app.use_cases import (
    FetchTendersUseCase,
    AnalyzePricesUseCase,
    DetectAnomaliesUseCase,
    DetectCollusionUseCase,
    GenerateAlertsUseCase,
    TemporalAnalysisUseCase,
    PersistenceManagementUseCase,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')


def run_once(cfg: dict, base_dir: Path, cli_options: Optional[dict] = None) -> None:
    """Execute the analysis pipeline once."""
    # Build sources based on configuration
    sources = []
    src_cfg = cfg.get("sources", {})
    
    # SECOP II
    if src_cfg.get("secop2", {}).get("enabled"):
        mode = src_cfg["secop2"].get("mode", "offline")
        if mode == "online":
            from licitaciones.infrastructure.sources import Secop2SocrataSource
            sources.append(Secop2SocrataSource(
                endpoint=src_cfg["secop2"].get("endpoint", "https://www.datos.gov.co/resource/p6dx-8zbt.json"),
                country="CO",
                app_token=src_cfg["secop2"].get("app_token")
            ))
        else:
            p = base_dir / Path(src_cfg["secop2"].get("sample_file", ""))
            sources.append(JsonLinesSource(p, "SECOP2", "CO"))
    
    # ChileCompra 
    if src_cfg.get("chilecompra", {}).get("enabled"):
        mode = src_cfg["chilecompra"].get("mode", "offline")
        if mode == "online":
            from licitaciones.infrastructure.sources import ChileCompraAPISource
            ticket_env = src_cfg["chilecompra"].get("ticket_env", "CHILECOMPRA_TICKET")
            sources.append(ChileCompraAPISource(
                endpoint=src_cfg["chilecompra"].get("endpoint", "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"),
                country="CL",
                ticket=src_cfg["chilecompra"].get("ticket") or os.getenv(ticket_env)
            ))
        else:
            p = base_dir / Path(src_cfg["chilecompra"].get("sample_file", ""))
            sources.append(JsonLinesSource(p, "ChileCompra", "CL"))
    
    # Compranet México
    if src_cfg.get("compranet", {}).get("enabled"):
        mode = src_cfg["compranet"].get("mode", "offline")
        if mode == "online":
            from licitaciones.infrastructure.sources import CompranetMexicoSource
            sources.append(CompranetMexicoSource(
                search_url=src_cfg["compranet"].get("endpoint", "https://datos.gob.mx/busca/api/3/action/package_list"),
                name="Compranet",
                country="MX",
                query=src_cfg["compranet"].get("query", "compranet")
            ))
        else:
            p = base_dir / Path(src_cfg["compranet"].get("sample_file", ""))
            sources.append(JsonLinesSource(p, "Compranet", "MX"))

    repo = InMemoryTenderRepository()

    fetch_uc = FetchTendersUseCase(sources, repo)
    n_loaded = fetch_uc.execute()
    click.echo(f"Cargadas {n_loaded} licitaciones desde fuentes configuradas")
    
    # Show statistics
    if n_loaded > 0:
        all_tenders = repo.query({})
        if all_tenders:
            total_amount = sum(t.amount for t in all_tenders if t.amount > 0)
            avg_amount = total_amount / len([t for t in all_tenders if t.amount > 0]) if any(t.amount > 0 for t in all_tenders) else 0
            countries = set(t.country for t in all_tenders)
            sources_found = set(t.source for t in all_tenders)
            click.echo(f"Países: {', '.join(countries)}")
            click.echo(f"Fuentes: {', '.join(sources_found)}")
            click.echo(f"Valor total: ${total_amount:,.0f}")
            click.echo(f"Valor promedio: ${avg_amount:,.0f}")

    filters = cfg.get("filters", {})
    analysis_cfg = cfg.get("analysis", {})
    
    # Add temporal filters from config
    temporal_cfg = cfg.get("temporal", {})
    if temporal_cfg.get("date_from"):
        filters["date_from"] = temporal_cfg["date_from"]
    if temporal_cfg.get("date_to"):
        filters["date_to"] = temporal_cfg["date_to"]
    if temporal_cfg.get("days_back"):
        filters["days_back"] = temporal_cfg["days_back"]

    # Initialize persistence if enabled
    persistence = None
    if cfg.get("persistence", {}).get("enabled", False):
        persistence_dir = base_dir / cfg.get("persistence", {}).get("directory", "data/executions")
        persistence = LocalFilePersistence(persistence_dir)
        click.echo(f"Persistencia habilitada: {persistence_dir}")

    # Generate opportunity alerts
    notifiers = []
    if cfg.get("alerts", {}).get("enabled"):
        notify = cfg["alerts"].get("notify", [])
        if "console" in notify:
            notifiers.append(ConsoleNotifier())
        if "file" in notify:
            notifiers.append(FileNotifier(cfg["alerts"].get("file_path", "data/alerts.log")))
    
    gen_alerts = GenerateAlertsUseCase(repo, notifiers, persistence)
    alerts = gen_alerts.execute(filters)
    click.echo(f"Se generaron {len(alerts)} alertas de oportunidad")

    # Price trends
    trend_uc = AnalyzePricesUseCase(repo, persistence)
    trends = trend_uc.execute(filters, analysis_cfg.get("price_trend", {}).get("group_by", ["item_code", "country"]))
    click.echo(f"Resumen de tendencias (grupos): {len(trends)}")

    # Anomalies
    anomaly_uc = DetectAnomaliesUseCase(repo, persistence)
    anomaly_cfg = analysis_cfg.get("anomaly", {})
    anomalies = anomaly_uc.execute(filters, method=anomaly_cfg.get("method", "zscore"), z=anomaly_cfg.get("z", 3.0), min_points=anomaly_cfg.get("min_points", 10))
    click.echo(f"Anomalías detectadas: {len(anomalies)}")

    # Collusion detection
    collusion_uc = DetectCollusionUseCase(repo, persistence)
    col_cfg = analysis_cfg.get("collusion", {})
    collusions = collusion_uc.execute(filters, min_bidders=col_cfg.get("min_bidders", 3), similarity_threshold=col_cfg.get("similarity_threshold", 0.95))
    click.echo(f"Posibles colusiones: {len(collusions)}")
    
    # Temporal analysis
    temporal_analysis = None
    if temporal_cfg.get("enabled", False):
        temporal_uc = TemporalAnalysisUseCase(repo, persistence)
        interval = temporal_cfg.get("interval", "monthly")
        temporal_analysis = temporal_uc.execute(filters, interval)
        click.echo(f"Análisis temporal ({interval}): {temporal_analysis.get('summary', {}).get('total_periods', 0)} períodos analizados")

    # Save full execution summary if persistence is enabled
    if persistence:
        # Obtener estadísticas detalladas
        all_tenders = repo.query({})
        countries = list(set(t.country for t in all_tenders))
        sources_found = list(set(t.source for t in all_tenders))
        amounts = [t.amount for t in all_tenders if t.amount > 0]
        total_amount = sum(amounts)
        avg_amount = total_amount / len(amounts) if amounts else 0
        
        execution_summary = {
            "execution_stats": {
                "alerts_count": len(alerts),
                "trends_count": len(trends),
                "anomalies_count": len(anomalies),
                "collusions_count": len(collusions),
                "total_tenders_processed": len(all_tenders)
            },
            "data_summary": {
                "countries": countries,
                "sources": sources_found,
                "total_amount": total_amount,
                "average_amount": avg_amount,
                "amount_range": {
                    "min": min(amounts) if amounts else 0,
                    "max": max(amounts) if amounts else 0
                },
                "tenders_with_amounts": len(amounts),
                "tenders_without_amounts": len(all_tenders) - len(amounts)
            },
            "temporal_analysis": temporal_analysis if temporal_analysis else None,
            "alert_samples": [
                {
                    "level": alert.level,
                    "message": alert.message[:100] + "..." if len(alert.message) > 100 else alert.message
                } for alert in alerts[:10]  # Primeras 10 alertas como muestra
            ],
            "trend_samples": {
                "top_groups": list(trends.keys())[:5] if trends else [],
                "sample_data": {k: v for k, v in list(trends.items())[:3]} if trends else {}
            }
        }
        
        persistence_mgmt = PersistenceManagementUseCase(persistence)
        summary_file = persistence_mgmt.save_full_execution_summary(
            execution_summary,
            {
                "config": cfg,
                "filters": filters,
                "execution_timestamp": datetime.now().isoformat(),
                "execution_duration": "N/A",  # Podríamos calcular esto si fuera necesario
                "cli_options": cli_options or {}
            }
        )
        click.echo(f"Resumen de ejecución guardado: {Path(summary_file).name}")


@click.command()
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), required=True, help="Ruta al config.json")
@click.option("--once/--schedule", default=True, help="Ejecutar una vez o con programador interno")
@click.option("--verbose", "-v", is_flag=True, help="Modo verbose")
@click.option("--date-from", type=str, help="Fecha inicio para filtro temporal (YYYY-MM-DD)")
@click.option("--date-to", type=str, help="Fecha fin para filtro temporal (YYYY-MM-DD)")
@click.option("--days-back", type=int, help="Días hacia atrás desde hoy para filtro temporal")
@click.option("--temporal-analysis", is_flag=True, help="Ejecutar análisis temporal")
@click.option("--temporal-interval", type=click.Choice(['daily', 'weekly', 'monthly']), default='monthly', help="Intervalo para análisis temporal")
@click.option("--enable-persistence", is_flag=True, help="Habilitar persistencia de resultados")
@click.option("--show-history", is_flag=True, help="Mostrar historial de ejecuciones")
@click.option("--cleanup-old", type=int, help="Limpiar archivos de persistencia más antiguos que N días")
def main(config_path: Path, once: bool, verbose: bool, date_from: str, date_to: str, days_back: int, temporal_analysis: bool, temporal_interval: str, enable_persistence: bool, show_history: bool, cleanup_old: int) -> None:
    """
    Plataforma de análisis de licitaciones para PyMEs.
    
    Analiza procesos de contratación de múltiples países para generar
    alertas de oportunidades, detectar anomalías y tendencias de precios.
    """
    # Configure logging
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    cfg = JsonConfigLoader(config_path).get()
    base_dir = config_path.parent.parent.resolve()
    
    # Override config with CLI options
    if date_from or date_to or days_back or temporal_analysis:
        if "temporal" not in cfg:
            cfg["temporal"] = {}
        if date_from:
            cfg["temporal"]["date_from"] = date_from
        if date_to:
            cfg["temporal"]["date_to"] = date_to
        if days_back:
            cfg["temporal"]["days_back"] = days_back
        if temporal_analysis:
            cfg["temporal"]["enabled"] = True
            cfg["temporal"]["interval"] = temporal_interval
    
    # Override persistence config with CLI options
    if enable_persistence:
        if "persistence" not in cfg:
            cfg["persistence"] = {}
        cfg["persistence"]["enabled"] = True
    
    # Handle persistence management operations
    if show_history or cleanup_old:
        persistence_dir = base_dir / cfg.get("persistence", {}).get("directory", "data/executions")
        persistence = LocalFilePersistence(persistence_dir)
        persistence_mgmt = PersistenceManagementUseCase(persistence)
        
        if show_history:
            click.echo("📚 Historial de Ejecuciones:")
            click.echo("=" * 50)
            history = persistence_mgmt.get_execution_history(limit=10)
            if not history:
                click.echo("No hay ejecuciones guardadas.")
            else:
                for i, execution in enumerate(history, 1):
                    timestamp = execution.get('timestamp', 'N/A')
                    exec_type = execution.get('execution_type', 'N/A')
                    file_size = execution.get('file_size', 0)
                    click.echo(f"{i:2d}. {timestamp[:19]} | {exec_type:15s} | {file_size:,} bytes")
        
        if cleanup_old:
            deleted = persistence_mgmt.cleanup_old_executions(cleanup_old)
            click.echo(f"🗑️  Eliminados {deleted} archivos más antiguos que {cleanup_old} días")
        
        if show_history or cleanup_old:
            return
    
    # Preparar opciones CLI para persistencia
    cli_options = {
        "date_from": date_from,
        "date_to": date_to,
        "days_back": days_back,
        "temporal_analysis": temporal_analysis,
        "temporal_interval": temporal_interval,
        "enable_persistence": enable_persistence,
        "verbose": verbose
    }
    
    if once or not cfg.get("scheduler", {}).get("enabled", False):
        run_once(cfg, base_dir, cli_options)
        return
    
    # Scheduler mode
    import schedule
    every_minutes = int(cfg.get("scheduler", {}).get("every_minutes", 60))
    click.echo(f"Scheduler activo cada {every_minutes} minutos")
    schedule.every(every_minutes).minutes.do(lambda: run_once(cfg, base_dir, cli_options))
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\nScheduler detenido")


if __name__ == "__main__":
    main()