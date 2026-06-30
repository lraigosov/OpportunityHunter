#!/usr/bin/env python3
"""
Tool for managing persistence data in the licitaciones platform.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import click
import json

# Add project root to path for imports
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from licitaciones.infrastructure.persistence import LocalFilePersistence
from licitaciones.app.use_cases import PersistenceManagementUseCase


@click.group()
def cli():
    """Herramienta de gestión de persistencia para la plataforma de licitaciones."""
    pass


@cli.command()
@click.option("--directory", "-d", type=click.Path(), default="data/executions", 
              help="Directorio de persistencia")
@click.option("--limit", "-l", type=int, default=20, 
              help="Número máximo de registros a mostrar")
@click.option("--type", "-t", type=click.Choice(['alerts', 'trends', 'anomalies', 'collusion', 'temporal_analysis', 'opportunities_report', 'full_execution']),
              help="Filtrar por tipo de ejecución")
def history(directory: str, limit: int, type: str):
    """Muestra el historial de ejecuciones guardadas."""
    persistence_dir = Path(directory)
    if not persistence_dir.exists():
        click.echo(f"❌ Directorio de persistencia no existe: {persistence_dir}")
        return
    
    persistence = LocalFilePersistence(persistence_dir)
    mgmt = PersistenceManagementUseCase(persistence)
    
    click.echo("📚 Historial de Ejecuciones")
    click.echo("=" * 80)
    
    history_records = mgmt.get_execution_history(type, limit)
    
    if not history_records:
        click.echo("No hay registros de ejecución guardados.")
        return
    
    for i, record in enumerate(history_records, 1):
        timestamp = record.get('timestamp', 'N/A')[:19]
        exec_type = record.get('execution_type', 'N/A')
        file_size = record.get('file_size', 0)
        file_path = Path(record.get('file_path', '')).name
        
        # Extraer información clave de los datos
        data = record.get('data', {})
        
        summary = ""
        if exec_type == "alerts":
            summary = f"{data.get('alerts_count', 0)} alertas"
        elif exec_type == "trends":
            summary = f"{data.get('groups_analyzed', 0)} grupos"
        elif exec_type == "anomalies":
            summary = f"{data.get('anomalies_count', 0)} anomalías"
        elif exec_type == "collusion":
            summary = f"{data.get('collusions_count', 0)} colusiones"
        elif exec_type == "temporal_analysis":
            summary = f"{data.get('summary', {}).get('total_periods', 0)} períodos"
        elif exec_type == "opportunities_report":
            opp_count = data.get('execution_summary', {}).get('total_opportunities', 0)
            summary = f"{opp_count} oportunidades"
        elif exec_type == "active_opportunities":
            active_count = data.get('execution_summary', {}).get('total_active_opportunities', 0)
            total_count = data.get('execution_summary', {}).get('total_opportunities_analyzed', 0)
            summary = f"{active_count}/{total_count} activas"
        elif exec_type == "full_execution":
            summary = "Resumen completo"
        
        click.echo(f"{i:2d}. {timestamp} | {exec_type:15s} | {summary:20s} | {file_size:,} bytes | {file_path}")


@cli.command()
@click.option("--directory", "-d", type=click.Path(), default="data/executions", 
              help="Directorio de persistencia")
def stats(directory: str):
    """Muestra estadísticas de los archivos persistidos."""
    persistence_dir = Path(directory)
    if not persistence_dir.exists():
        click.echo(f"❌ Directorio de persistencia no existe: {persistence_dir}")
        return
    
    persistence = LocalFilePersistence(persistence_dir)
    statistics = persistence.get_statistics()
    
    click.echo("📊 Estadísticas de Persistencia")
    click.echo("=" * 50)
    click.echo(f"Total de archivos: {statistics['total_files']}")
    click.echo(f"Tamaño total: {statistics['total_size_bytes']:,} bytes ({statistics['total_size_bytes']/1024/1024:.2f} MB)")
    
    if statistics.get('oldest_file'):
        click.echo(f"Archivo más antiguo: {statistics['oldest_file']['timestamp'][:19]}")
    if statistics.get('newest_file'):
        click.echo(f"Archivo más reciente: {statistics['newest_file']['timestamp'][:19]}")
    
    click.echo("\n📈 Por tipo de ejecución:")
    for exec_type, stats in statistics['by_type'].items():
        if stats['count'] > 0:
            size_mb = stats['size_bytes'] / 1024 / 1024
            click.echo(f"  {exec_type:20s}: {stats['count']:3d} archivos, {size_mb:6.2f} MB")


@cli.command()
@click.option("--directory", "-d", type=click.Path(), default="data/executions", 
              help="Directorio de persistencia")
@click.option("--days", type=int, default=30, 
              help="Días de antigüedad para considerar archivos como viejos")
@click.option("--dry-run", is_flag=True, 
              help="Mostrar qué archivos se eliminarían sin eliminarlos realmente")
def cleanup(directory: str, days: int, dry_run: bool):
    """Limpia archivos de persistencia antiguos."""
    persistence_dir = Path(directory)
    if not persistence_dir.exists():
        click.echo(f"❌ Directorio de persistencia no existe: {persistence_dir}")
        return
    
    persistence = LocalFilePersistence(persistence_dir)
    
    if dry_run:
        cutoff_date = datetime.now() - timedelta(days=days)
        click.echo(f"🔍 Archivos que se eliminarían (más antiguos que {days} días - {cutoff_date.strftime('%Y-%m-%d')}):")
        
        count = 0
        total_size = 0
        
        for exec_type, type_dir in persistence.type_dirs.items():
            if not type_dir.exists():
                continue
            
            for file_path in type_dir.glob("*.json"):
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff_date:
                    file_size = file_path.stat().st_size
                    click.echo(f"  - {file_path.name} ({file_mtime.strftime('%Y-%m-%d %H:%M')} - {file_size:,} bytes)")
                    count += 1
                    total_size += file_size
        
        if count == 0:
            click.echo("  No hay archivos para eliminar.")
        else:
            click.echo(f"\nTotal: {count} archivos, {total_size:,} bytes ({total_size/1024/1024:.2f} MB)")
            click.echo("Ejecute sin --dry-run para eliminar realmente.")
    else:
        deleted_count = persistence.cleanup_old_files(days)
        if deleted_count > 0:
            click.echo(f"🗑️  Eliminados {deleted_count} archivos más antiguos que {days} días")
        else:
            click.echo("✨ No hay archivos antiguos para eliminar")


@cli.command()
@click.option("--directory", "-d", type=click.Path(), default="data/executions", 
              help="Directorio de persistencia")
@click.option("--file", "-f", type=click.Path(exists=True), required=True,
              help="Archivo JSON de ejecución a mostrar")
def show(directory: str, file: str):
    """Muestra el contenido detallado de un archivo de ejecución."""
    file_path = Path(file)
    
    if not file_path.exists():
        click.echo(f"❌ Archivo no existe: {file_path}")
        return
    
    if not file_path.suffix == '.json':
        click.echo(f"❌ El archivo debe ser un JSON: {file_path}")
        return
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        click.echo(f"📄 Contenido de: {file_path.name}")
        click.echo("=" * 80)
        
        # Información básica
        click.echo(f"Timestamp: {data.get('timestamp', 'N/A')}")
        click.echo(f"Tipo: {data.get('execution_type', 'N/A')}")
        
        # Metadatos
        metadata = data.get('metadata', {})
        if metadata:
            click.echo("\n🏷️  Metadatos:")
            for key, value in metadata.items():
                if isinstance(value, dict):
                    click.echo(f"  {key}: {json.dumps(value, ensure_ascii=False)}")
                else:
                    click.echo(f"  {key}: {value}")
        
        # Datos principales
        execution_data = data.get('data', {})
        if execution_data:
            click.echo("\n📊 Datos:")
            click.echo(json.dumps(execution_data, ensure_ascii=False, indent=2))
    
    except Exception as e:
        click.echo(f"❌ Error leyendo archivo: {e}")


if __name__ == "__main__":
    cli()