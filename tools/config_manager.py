#!/usr/bin/env python3
"""
Configuration management tool for the licitaciones platform.
"""
import json
from pathlib import Path
from typing import Dict, Any
import click


DEFAULT_CONFIG = {
    "sources": {
        "secop2": {
            "enabled": True,
            "mode": "online",
            "sample_file": "data/samples/secop2_sample.jsonl",
            "endpoint": "https://www.datos.gov.co/resource/p6dx-8zbt.json",
            "limit": 50
        },
        "chilecompra": {
            "enabled": False,
            "mode": "online",
            "sample_file": "data/samples/chilecompra_sample.jsonl",
            "endpoint": "https://www.mercadopublico.cl/Procurement/Modules/RFB/SearchProcurement.aspx",
            "limit": 50
        },
        "compranet": {
            "enabled": False,
            "mode": "online",
            "sample_file": "data/samples/compranet_sample.jsonl",
            "endpoint": "https://datos.gob.mx/busca/api/3/action/package_list",
            "query": "compranet",
            "limit": 20
        }
    },
    "filters": {
        "keywords": ["software", "servicios", "consultoría"],
        "countries": ["CO", "CL", "MX"],
        "min_amount": 0,
        "max_amount": 1000000000,
        "cpv_codes": [],
        "buyer_names": []
    },
    "alerts": {
        "enabled": True,
        "notify": ["console", "file"],
        "file_path": "data/alerts.log"
    },
    "analysis": {
        "price_trend": {
            "window_days": 180,
            "group_by": ["item_code", "country"]
        },
        "anomaly": {
            "method": "zscore",
            "z": 3.0,
            "min_points": 10
        },
        "collusion": {
            "method": "simple",
            "min_bidders": 3,
            "similarity_threshold": 0.95
        }
    },
    "scheduler": {
        "enabled": False,
        "every_minutes": 60
    }
}


@click.group()
def cli():
    """Configuration management for licitaciones platform."""
    pass


@cli.command()
@click.option('--output', '-o', default='config/config.json', help='Output file path')
@click.option('--force', is_flag=True, help='Overwrite existing file')
def create(output: str, force: bool):
    """Create a new configuration file with defaults."""
    output_path = Path(output)
    
    if output_path.exists() and not force:
        click.echo(f"Configuration file already exists: {output}")
        click.echo("Use --force to overwrite")
        return
    
    # Create directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write configuration
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
    
    click.echo(f"Configuration created: {output}")


@cli.command()
@click.argument('config_file')
def validate(config_file: str):
    """Validate a configuration file."""
    config_path = Path(config_file)
    
    if not config_path.exists():
        click.echo(f"Configuration file not found: {config_file}")
        return
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Basic validation
        required_sections = ['sources', 'filters', 'alerts', 'analysis']
        errors = []
        
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required section: {section}")
        
        # Validate sources
        if 'sources' in config:
            for source_name, source_config in config['sources'].items():
                if 'enabled' not in source_config:
                    errors.append(f"Source {source_name} missing 'enabled' field")
                if 'mode' not in source_config:
                    errors.append(f"Source {source_name} missing 'mode' field")
        
        if errors:
            click.echo("Configuration validation failed:")
            for error in errors:
                click.echo(f"  - {error}")
        else:
            click.echo("Configuration is valid ✓")
            
            # Show enabled sources
            enabled_sources = [name for name, cfg in config.get('sources', {}).items() 
                             if cfg.get('enabled', False)]
            click.echo(f"Enabled sources: {', '.join(enabled_sources) if enabled_sources else 'None'}")
    
    except json.JSONDecodeError as e:
        click.echo(f"Invalid JSON in configuration file: {e}")


@cli.command()
@click.argument('config_file')
@click.argument('source_name')
@click.option('--enable/--disable', default=True, help='Enable or disable the source')
def toggle_source(config_file: str, source_name: str, enable: bool):
    """Enable or disable a data source in the configuration."""
    config_path = Path(config_file)
    
    if not config_path.exists():
        click.echo(f"Configuration file not found: {config_file}")
        return
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if source_name not in config.get('sources', {}):
            click.echo(f"Source '{source_name}' not found in configuration")
            available = list(config.get('sources', {}).keys())
            click.echo(f"Available sources: {', '.join(available)}")
            return
        
        config['sources'][source_name]['enabled'] = enable
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        status = "enabled" if enable else "disabled"
        click.echo(f"Source '{source_name}' has been {status}")
        
    except json.JSONDecodeError as e:
        click.echo(f"Invalid JSON in configuration file: {e}")


if __name__ == "__main__":
    cli()