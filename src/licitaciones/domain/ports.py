from __future__ import annotations
from typing import Iterable, Protocol, List, Optional, Dict, Any
from .models import Tender, Alert


class TenderSourcePort(Protocol):
    def fetch(self, limit: Optional[int] = None) -> Iterable[Tender]:
        ...


class TenderRepositoryPort(Protocol):
    def save_all(self, tenders: Iterable[Tender]) -> int:
        ...

    def query(self, filters: Dict[str, Any]) -> List[Tender]:
        ...


class NotifierPort(Protocol):
    def notify(self, alerts: List[Alert]) -> None:
        ...


class ConfigPort(Protocol):
    def get(self) -> Dict[str, Any]:
        ...


class PersistencePort(Protocol):
    """Puerto para persistencia de datos con marca de tiempo."""
    
    def save_execution_results(self, execution_type: str, data: Dict[str, Any], 
                             metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Guarda resultados de ejecución con marca de tiempo.
        
        Args:
            execution_type: Tipo de ejecución (alerts, trends, anomalies, etc.)
            data: Datos a persistir
            metadata: Metadatos adicionales (filtros, configuración, etc.)
            
        Returns:
            ID o ruta del archivo generado
        """
        ...
    
    def load_execution_history(self, execution_type: Optional[str] = None, 
                             limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Carga historial de ejecuciones.
        
        Args:
            execution_type: Filtrar por tipo de ejecución
            limit: Límite de registros a retornar
            
        Returns:
            Lista de ejecuciones con sus datos y metadatos
        """
        ...
    
    def cleanup_old_files(self, days_old: int = 30) -> int:
        """
        Limpia archivos antiguos.
        
        Args:
            days_old: Días de antigüedad para considerar archivo como viejo
            
        Returns:
            Número de archivos eliminados
        """
        ...
