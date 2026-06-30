"""
Infrastructure adapters for data persistence.
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional


class LocalFilePersistence:
    """Implementación de persistencia en archivos locales con marca de tiempo."""
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Inicializa el adaptador de persistencia local.
        
        Args:
            base_dir: Directorio base para almacenar archivos. Por defecto: data/executions/
        """
        self.base_dir = base_dir or Path("data/executions")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Crear subdirectorios por tipo de ejecución
        self.type_dirs = {
            "alerts": self.base_dir / "alerts",
            "trends": self.base_dir / "trends", 
            "anomalies": self.base_dir / "anomalies",
            "collusion": self.base_dir / "collusion",
            "temporal_analysis": self.base_dir / "temporal_analysis",
            "opportunities_report": self.base_dir / "opportunities_report",
            "active_opportunities": self.base_dir / "active_opportunities",  # Nuevo tipo
            "full_execution": self.base_dir / "full_execution"
        }
        
        for dir_path in self.type_dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def save_execution_results(self, execution_type: str, data: Dict[str, Any], 
                             metadata: Optional[Dict[str, Any]] = None) -> str:
        """Guarda resultados de ejecución con marca de tiempo."""
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Incluir microsegundos
        
        # Preparar datos completos
        full_data = {
            "timestamp": timestamp.isoformat(),
            "execution_type": execution_type,
            "metadata": metadata or {},
            "data": data
        }
        
        # Determinar directorio y nombre de archivo
        type_dir = self.type_dirs.get(execution_type, self.base_dir / "other")
        type_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{execution_type}_{timestamp_str}.json"
        file_path = type_dir / filename
        
        # Guardar archivo
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(full_data, f, ensure_ascii=False, indent=2, default=str)
            
            return str(file_path)
        except Exception as e:
            raise RuntimeError(f"Error saving execution results: {e}")
    
    def load_execution_history(self, execution_type: Optional[str] = None, 
                             limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Carga historial de ejecuciones."""
        results = []
        
        # Determinar directorios a buscar
        if execution_type:
            search_dirs = [self.type_dirs.get(execution_type)]
            if search_dirs[0] is None:
                return []
        else:
            search_dirs = list(self.type_dirs.values()) + [self.base_dir / "other"]
        
        # Recopilar archivos JSON
        json_files = []
        for search_dir in search_dirs:
            if search_dir and search_dir.exists():
                json_files.extend(search_dir.glob("*.json"))
        
        # Ordenar por fecha de modificación (más reciente primero)
        json_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Aplicar límite si se especifica
        if limit:
            json_files = json_files[:limit]
        
        # Cargar archivos
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['file_path'] = str(file_path)
                    data['file_size'] = file_path.stat().st_size
                    results.append(data)
            except Exception as e:
                # Log error but continue with other files
                print(f"Warning: Could not load {file_path}: {e}")
                continue
        
        return results
    
    def cleanup_old_files(self, days_old: int = 30) -> int:
        """Limpia archivos antiguos."""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        deleted_count = 0
        
        # Buscar en todos los directorios
        all_dirs = list(self.type_dirs.values()) + [self.base_dir / "other"]
        
        for search_dir in all_dirs:
            if not search_dir.exists():
                continue
                
            for file_path in search_dir.glob("*.json"):
                try:
                    # Verificar fecha de modificación
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        file_path.unlink()
                        deleted_count += 1
                except Exception as e:
                    print(f"Warning: Could not delete {file_path}: {e}")
                    continue
        
        return deleted_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas de los archivos persistidos."""
        stats = {
            "total_files": 0,
            "total_size_bytes": 0,
            "by_type": {},
            "oldest_file": None,
            "newest_file": None
        }
        
        all_files = []
        
        # Recopilar estadísticas por tipo
        for exec_type, dir_path in self.type_dirs.items():
            if not dir_path.exists():
                continue
                
            type_files = list(dir_path.glob("*.json"))
            type_count = len(type_files)
            type_size = sum(f.stat().st_size for f in type_files)
            
            stats["by_type"][exec_type] = {
                "count": type_count,
                "size_bytes": type_size
            }
            
            all_files.extend(type_files)
        
        # Estadísticas globales
        stats["total_files"] = len(all_files)
        stats["total_size_bytes"] = sum(f.stat().st_size for f in all_files)
        
        if all_files:
            # Archivo más antiguo y más nuevo
            oldest = min(all_files, key=lambda x: x.stat().st_mtime)
            newest = max(all_files, key=lambda x: x.stat().st_mtime)
            
            stats["oldest_file"] = {
                "path": str(oldest),
                "timestamp": datetime.fromtimestamp(oldest.stat().st_mtime).isoformat()
            }
            stats["newest_file"] = {
                "path": str(newest),
                "timestamp": datetime.fromtimestamp(newest.stat().st_mtime).isoformat()
            }
        
        return stats


class JsonLinesPersistence:
    """Implementación alternativa usando formato JSON Lines para mejor rendimiento."""
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Inicializa el adaptador JSON Lines.
        
        Args:
            base_dir: Directorio base para almacenar archivos. Por defecto: data/history/
        """
        self.base_dir = base_dir or Path("data/history")
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def append_execution_record(self, execution_type: str, data: Dict[str, Any], 
                              metadata: Optional[Dict[str, Any]] = None) -> str:
        """Agrega un registro de ejecución al archivo de historial."""
        timestamp = datetime.now()
        
        record = {
            "timestamp": timestamp.isoformat(),
            "execution_type": execution_type,
            "metadata": metadata or {},
            "data": data
        }
        
        # Nombre de archivo por día
        date_str = timestamp.strftime("%Y%m%d")
        filename = f"executions_{date_str}.jsonl"
        file_path = self.base_dir / filename
        
        try:
            with open(file_path, 'a', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, default=str)
                f.write('\n')
            
            return str(file_path)
        except Exception as e:
            raise RuntimeError(f"Error appending execution record: {e}")
    
    def read_daily_records(self, date: str) -> List[Dict[str, Any]]:
        """Lee registros de un día específico (formato YYYYMMDD)."""
        filename = f"executions_{date}.jsonl"
        file_path = self.base_dir / filename
        
        if not file_path.exists():
            return []
        
        records = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
        
        return records